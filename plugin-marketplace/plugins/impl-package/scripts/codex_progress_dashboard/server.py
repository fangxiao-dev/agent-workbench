"""Serve a loopback-only live progress view for local Codex tasks."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sqlite3
import sys
import threading
import time
import uuid
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


PLUGIN_SCRIPTS = Path(__file__).resolve().parents[1]
if str(PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(PLUGIN_SCRIPTS))
import monitor_progress
from impl_package_runtime import engine as impl_package_engine

try:
    import review_track_stats
except Exception:  # pragma: no cover - the optional package helper may be absent during upgrades
    review_track_stats = None  # type: ignore[assignment]


HOST = "127.0.0.1"
PORT = 43187
APP_DIR = Path(__file__).resolve().parent
CODEX_HOME = Path.home() / ".codex"
DEFAULT_DB = CODEX_HOME / "state_5.sqlite"
THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
TICKET_ID_PATTERN = r"TKT-\d+(?:-[A-Za-z0-9]+)*"
TICKET_ID_RE = re.compile(rf"\b{TICKET_ID_PATTERN}\b", re.I)
TICKET_REFERENCE_RE = re.compile(r"\bTKT-?\d+(?:-[A-Za-z0-9]+)*\b", re.I)
TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")
TYPED_DEPENDENCY_RE = re.compile(
    rf"\b(implementation|acceptance|release)\s*:\s*({TICKET_ID_PATTERN})\b",
    re.I,
)
WINDOWS_PATH_RE = re.compile(r"(?:\\\\\?\\)?[A-Za-z]:[\\/][^\s`\"'<>\])]+")
SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|access[_-]?token|token|password|secret)\b\s*[:=]\s*[^\s,;]+"
)
IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]){11,30}\b")
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.I)
COMMIT_RE = re.compile(r"\b[0-9a-f]{40}\b", re.I)
MAX_ACTIVITY = 5
MAX_ACTIVITY_CHARS = 1200
MAX_TRAIL_SUMMARY_CHARS = 200
MAX_REQUEST_BODY_BYTES = 8192
REVIEW_TRACKS = ("Track A", "Track B", "Track C", "Track D")


class ObservationConflictError(ValueError):
    pass


def _iso_timestamp(value: Any) -> str | None:
    try:
        return datetime.fromtimestamp(float(value)).astimezone().isoformat(timespec="seconds")
    except (OSError, OverflowError, TypeError, ValueError):
        return None


def _normalise_path(value: str | Path) -> Path:
    text = str(value)
    if text.startswith("\\\\?\\"):
        text = text[4:]
    return Path(text).resolve()


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _safe_name(name: Any, updated_at: Any) -> str:
    if isinstance(name, str) and name.strip():
        return name.strip()[:100]
    stamp = _iso_timestamp(updated_at)
    suffix = stamp[:16].replace("T", " ") if stamp else "未知时间"
    return f"未命名任务 · {suffix}"


def _db_uri(path: Path) -> str:
    return f"file:{path.resolve().as_posix()}?mode=ro"


def _connect(db_path: Path) -> sqlite3.Connection:
    connection = sqlite3.connect(_db_uri(db_path), uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def list_tasks(db_path: Path = DEFAULT_DB, limit: int = 200) -> list[dict[str, Any]]:
    with _connect(db_path) as connection:
        rows = connection.execute(
            """
            SELECT id, name, updated_at, cwd, rollout_path
            FROM threads
            WHERE archived = 0
              AND rollout_path IS NOT NULL
              AND name IS NOT NULL
              AND TRIM(name) <> ''
            ORDER BY COALESCE(recency_at_ms, updated_at_ms, updated_at * 1000) DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    roots_by_workspace: dict[Path, list[Path]] = {}
    tasks = []
    for row in rows:
        if not isinstance(row["id"], str) or not THREAD_ID_RE.fullmatch(row["id"]):
            continue
        try:
            cwd, rollout = _task_paths(row, db_path)
        except (FileNotFoundError, ValueError):
            continue
        roots = roots_by_workspace.get(cwd)
        if roots is None:
            roots = _package_roots(cwd)
            roots_by_workspace[cwd] = roots
        current_package = next((item for item in find_packages(cwd, rollout, roots) if item["current"]), None)
        if current_package is None:
            continue
        package_root = (cwd / current_package["path"]).resolve()
        tasks.append(
            {
                "id": row["id"],
                "name": _safe_name(row["name"], row["updated_at"]),
                "updatedAt": _iso_timestamp(row["updated_at"]),
                "currentPackage": {
                    **current_package,
                    "identity": hashlib.sha256(
                        os.path.normcase(str(package_root)).encode("utf-8")
                    ).hexdigest(),
                    "workspaceName": cwd.name,
                },
            }
        )
    return tasks


def _task_row(thread_id: str, db_path: Path) -> sqlite3.Row:
    if not THREAD_ID_RE.fullmatch(thread_id):
        raise ValueError("invalid task id")
    with _connect(db_path) as connection:
        row = connection.execute(
            """
            SELECT id, name, updated_at, cwd, rollout_path, git_branch, git_sha
            FROM threads
            WHERE id = ? AND archived = 0
            """,
            (thread_id,),
        ).fetchone()
    if row is None:
        raise LookupError("task not found")
    return row


def _task_paths(row: sqlite3.Row, db_path: Path) -> tuple[Path, Path]:
    cwd = _normalise_path(row["cwd"])
    rollout = _normalise_path(row["rollout_path"])
    sessions_root = (db_path.resolve().parent / "sessions").resolve()
    if not cwd.is_dir():
        raise FileNotFoundError("task workspace is unavailable")
    if not rollout.is_file() or not _is_within(rollout, sessions_root):
        raise ValueError("task rollout is outside the Codex sessions directory")
    return cwd, rollout


def sanitise_activity(text: str) -> str:
    text = SECRET_RE.sub(lambda match: f"{match.group(1)}=[已隐藏]", text)
    text = IBAN_RE.sub("[IBAN 已隐藏]", text)
    text = EMAIL_RE.sub("[邮箱已隐藏]", text)
    text = WINDOWS_PATH_RE.sub("[本地路径]", text)
    text = COMMIT_RE.sub("[版本]", text)
    text = re.sub(r"```[\s\S]*?```", "[代码块已省略]", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    return text[:MAX_ACTIVITY_CHARS]


def _monitor_evaluation(value: dict[str, Any] | None) -> dict[str, Any] | None:
    if value is None:
        return None
    owner = sanitise_activity(value["owner"]) if value["owner"] else None
    return {
        "progress": sanitise_activity(value["progress"]),
        "improvements": [sanitise_activity(item) for item in value["improvements"]],
        "next": sanitise_activity(value["next"]),
        "owner": owner,
    }


def _observation_revision(value: dict[str, Any]) -> str:
    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _project_observation(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": value["id"],
        "kind": value["kind"],
        "topic": sanitise_activity(value["topic"]),
        "observedAt": value["confirmedAt"],
        "content": sanitise_activity(value["content"]),
        "revision": _observation_revision(value),
    }


def monitor_snapshot(workspace: Path, package_root: Path | None) -> dict[str, Any] | None:
    if package_root is None:
        return None
    projected = monitor_progress.latest_for_package(workspace, package_root)
    if projected is None:
        return None
    record = projected["monitor"]
    candidate = {
        "observedAt": record["observedAt"],
        "level": record["level"],
        "summary": sanitise_activity(record["summary"]),
        "monitorThreadId": record["monitorThreadId"],
        "observations": [_project_observation(item) for item in projected["observations"]],
        "observationAttempts": [
            {
                "attempt": item["attempt"],
                "current": item["current"],
                "available": item["available"],
                "observations": [_project_observation(observation) for observation in item["observations"]],
            }
            for item in projected["observationAttempts"]
        ],
    }
    evaluation = _monitor_evaluation(record["evaluation"])
    if evaluation:
        candidate["evaluation"] = evaluation
    return candidate


def update_observation_content(
    workspace: Path,
    package_root: Path,
    observation_id: str,
    content: Any,
    revision: Any,
) -> dict[str, Any]:
    projected = monitor_progress.latest_for_package(workspace, package_root)
    if projected is None:
        raise LookupError("monitor not found")
    record = next(
        (item for item in projected["observations"] if item["id"] == observation_id),
        None,
    )
    if record is None:
        raise LookupError("confirmed observation not found")
    if not isinstance(revision, str) or revision != _observation_revision(record):
        raise ObservationConflictError("纠偏内容已变化，请刷新后重试")
    result = monitor_progress.put_observation(
        workspace,
        projected["monitor"]["automationId"],
        {**record, "content": content},
    )
    return _project_observation(result["observation"])


def _message_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if not isinstance(content, list):
        return ""
    return " ".join(
        str(part.get("text", ""))
        for part in content
        if isinstance(part, dict) and isinstance(part.get("text"), str)
    ).strip()


@dataclass
class RolloutProjection:
    offset: int = 0
    activities: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=MAX_ACTIVITY))
    last_started: str | None = None
    last_completed: str | None = None
    last_aborted: str | None = None
    last_user: str | None = None
    last_assistant: str | None = None

    def apply(self, record: dict[str, Any]) -> None:
        kind = record.get("type")
        payload = record.get("payload")
        if not isinstance(payload, dict):
            return
        timestamp = str(record.get("timestamp") or "")
        payload_type = payload.get("type")
        if kind == "event_msg":
            if payload_type == "task_started":
                self.last_started = timestamp
            elif payload_type == "task_complete":
                self.last_completed = timestamp
            elif payload_type in {"task_aborted", "turn_aborted"}:
                self.last_aborted = timestamp
            return
        if kind != "response_item" or payload_type != "message":
            return
        role = payload.get("role")
        if role == "user":
            self.last_user = timestamp
            return
        if role != "assistant" or payload.get("phase") not in {"commentary", "final_answer"}:
            return
        self.last_assistant = timestamp
        text = sanitise_activity(_message_text(payload))
        if text:
            self.activities.append(
                {
                    "timestamp": timestamp,
                    "phase": str(payload.get("phase")),
                    "text": text,
                }
            )

    def status(self) -> str:
        if self.last_aborted and (not self.last_started or self.last_aborted >= self.last_started):
            return "已中断"
        if self.last_completed and (not self.last_started or self.last_completed >= self.last_started):
            return "本轮已完成"
        if self.last_user and (not self.last_assistant or self.last_user > self.last_assistant):
            return "等待回应"
        if self.last_started:
            return "进行中"
        return "状态未知"


class RolloutReader:
    """Incrementally projects complete JSONL records and retains no raw tool output."""

    def __init__(self) -> None:
        self._states: dict[Path, RolloutProjection] = {}
        self._lock = threading.Lock()

    def read(self, path: Path) -> dict[str, Any]:
        with self._lock:
            state = self._states.setdefault(path, RolloutProjection())
            size = path.stat().st_size
            if size < state.offset:
                state = RolloutProjection()
                self._states[path] = state
            with path.open("rb") as stream:
                stream.seek(state.offset)
                while True:
                    raw = stream.readline()
                    if not raw or not raw.endswith(b"\n"):
                        break
                    state.offset = stream.tell()
                    try:
                        record = json.loads(raw.decode("utf-8"))
                    except (UnicodeDecodeError, json.JSONDecodeError):
                        continue
                    if isinstance(record, dict):
                        state.apply(record)
            return {
                "status": state.status(),
                "activities": list(reversed(state.activities)),
                "offset": state.offset,
            }


ROLLOUT_READER = RolloutReader()


def _plan_name(package_root: Path) -> str:
    plan = package_root / "plan.md"
    if plan.is_file():
        try:
            for line in plan.read_text(encoding="utf-8", errors="replace").splitlines():
                if line.startswith("# "):
                    return line[2:].strip()[:120]
        except OSError:
            pass
    return package_root.name.replace("-", " ")


def _package_roots(cwd: Path) -> list[Path]:
    docs = cwd / "docs"
    if not docs.is_dir():
        return []
    return sorted({path.parent.parent for path in docs.rglob(".impl-package/state.json")})


def _package_binding_text(rollout: Path, limit: int = 1_000_000) -> str:
    try:
        with rollout.open("rb") as stream:
            stream.seek(max(0, rollout.stat().st_size - limit))
            tail = stream.read().decode("utf-8", errors="ignore")
    except OSError:
        return ""
    commands = []
    for line in tail.splitlines():
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        payload = record.get("payload")
        if not isinstance(payload, dict) or payload.get("type") != "custom_tool_call":
            continue
        tool_input = payload.get("input")
        if (
            payload.get("name") == "exec"
            and isinstance(tool_input, str)
            and "impl_package_state.py" in tool_input
            and "--package" in tool_input
        ):
            commands.append(tool_input)
    return "\n".join(commands)


def find_packages(cwd: Path, rollout: Path, roots: list[Path] | None = None) -> list[dict[str, Any]]:
    roots = _package_roots(cwd) if roots is None else roots
    rollout_text = _package_binding_text(rollout)
    packages = []
    for root in roots:
        relative = root.relative_to(cwd).as_posix()
        last_reference = max(rollout_text.rfind(relative), rollout_text.rfind(relative.replace("/", "\\\\")))
        packages.append(
            {
                "path": relative,
                "name": _plan_name(root),
                "referenced": last_reference >= 0,
                "lastReference": last_reference,
                "current": False,
            }
        )
    packages.sort(key=lambda item: (-item["lastReference"], item["name"].casefold()))
    if packages and packages[0]["referenced"]:
        packages[0]["current"] = True
    return packages


def _package_root(cwd: Path, relative: str | None) -> Path | None:
    if not relative:
        return None
    candidate = (cwd / unquote(relative)).resolve()
    if not _is_within(candidate, cwd) or not (candidate / ".impl-package" / "state.json").is_file():
        raise ValueError("invalid package path")
    return candidate


def _resolve_ticket_id(token: str, ticket_ids: list[str]) -> str:
    lowered = token.casefold()
    exact = next((ticket_id for ticket_id in ticket_ids if ticket_id.casefold() == lowered), None)
    if exact:
        return exact
    token_number = re.match(r"TKT-?(\d+)", token, re.I)
    prefix_matches = [
        ticket_id
        for ticket_id in ticket_ids
        if token_number
        and (candidate_number := re.match(r"TKT-?(\d+)", ticket_id, re.I))
        and int(candidate_number.group(1)) == int(token_number.group(1))
    ]
    return prefix_matches[0] if len(prefix_matches) == 1 else token.upper()


def _typed_dependencies(text: str, ticket_ids: list[str]) -> dict[str, list[str]]:
    result = {"implementation": [], "acceptance": [], "release": []}
    for match in TYPED_DEPENDENCY_RE.finditer(text):
        dependency_type = match.group(1).lower()
        ticket_id = _resolve_ticket_id(match.group(2), ticket_ids)
        if ticket_id not in result[dependency_type]:
            result[dependency_type].append(ticket_id)
    return result


def _plan_dependencies(package_root: Path, ticket_ids: list[str]) -> dict[str, dict[str, list[str]]]:
    plan = package_root / "plan.md"
    if not plan.is_file():
        return {}
    try:
        text = plan.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    result: dict[str, dict[str, list[str]]] = {}
    for line in text.splitlines():
        ticket_match = TICKET_ID_RE.search(line)
        if not ticket_match:
            continue
        ticket_id = _resolve_ticket_id(ticket_match.group(0), ticket_ids)
        if ticket_id not in ticket_ids:
            continue
        typed = _typed_dependencies(line, ticket_ids)
        if any(typed.values()):
            result[ticket_id] = typed
    return result


def _ticket_metadata(
    package_root: Path, ticket_ids: list[str], attempt_id: str | None = None
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    ticket_dir = package_root / "tickets"
    if not ticket_dir.is_dir():
        return result
    for path in sorted(ticket_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = re.search(
            rf"(?:\*\*)?Ticket ID(?:\*\*)?\s*[：:](?:\*\*)?\s*({TICKET_ID_PATTERN})",
            text,
            re.I,
        )
        if not match:
            continue
        if attempt_id is not None:
            attempt_match = re.search(
                r"(?:\*\*)?Attempt ID(?:\*\*)?\s*[：:](?:\*\*)?\s*([^\s*]+)",
                text,
                re.I,
            )
            if attempt_match and attempt_match.group(1) != attempt_id:
                continue
        ticket_id = _resolve_ticket_id(match.group(1), ticket_ids)
        heading = next((line[2:].strip() for line in text.splitlines() if line.startswith("# ")), ticket_id)
        heading = re.sub(r"^\d+\s*[—–-]\s*", "", heading).strip()
        hints = []
        for hint in re.findall(r"^-\s+\*\*(AC-\d+)[：:]\*\*\s*(.+)$", text, re.M):
            clean = re.sub(r"[`*_]", "", hint[1]).strip()
            hints.append(f"{hint[0]}：{clean[:180]}")
        dependency_section = re.search(r"## 阻塞依赖\s*(.*?)(?=\n## |\Z)", text, re.S)
        dependency_types = _typed_dependencies(dependency_section.group(1), ticket_ids) if dependency_section else {}
        dependencies = [
            dependency
            for dependency_type in ("implementation", "acceptance", "release")
            for dependency in dependency_types.get(dependency_type, [])
        ]
        result[ticket_id.upper()] = {
            "name": heading[:120],
            "completionHints": hints[:3],
            "dependencies": list(dict.fromkeys(dependencies)),
            "dependencyTypes": dependency_types,
        }
    return result


def _historical_attempt(
    package_root: Path, history: dict[str, Any]
) -> dict[str, Any]:
    attempt_id = str(history.get("id", ""))
    unavailable = {
        "id": attempt_id,
        "current": False,
        "available": False,
        "lifecycle": history.get("lifecycle"),
        "gate": history.get("gate"),
        "formalSummary": "Ticket 快照不可用",
        "tickets": [],
        "counts": {},
    }
    if re.fullmatch(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})", attempt_id) is None:
        return unavailable
    archive_path = package_root / ".impl-package" / "attempts" / f"{attempt_id}.json"
    try:
        archive = json.loads(archive_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return unavailable
    ticket_states = archive.get("tickets") if isinstance(archive, dict) else None
    if not isinstance(archive, dict) or archive.get("attempt") != attempt_id or not isinstance(ticket_states, dict):
        return unavailable
    ticket_ids = [str(ticket_id) for ticket_id in ticket_states]
    metadata = _ticket_metadata(package_root, ticket_ids, attempt_id)
    tickets = []
    for ticket_id, value in ticket_states.items():
        meta = metadata.get(str(ticket_id).upper(), {})
        dependency_types = {
            name: list(meta.get("dependencyTypes", {}).get(name, []))
            for name in ("implementation", "acceptance", "release")
        }
        dependencies = [
            dependency
            for dependency_type in ("implementation", "acceptance", "release")
            for dependency in dependency_types[dependency_type]
        ]
        tickets.append(
            {
                "id": str(ticket_id),
                "name": meta.get("name", str(ticket_id)),
                "state": str(value.get("state", "UNKNOWN")) if isinstance(value, dict) else "UNKNOWN",
                "completionHints": meta.get("completionHints", []),
                "dependencies": list(dict.fromkeys(dependencies)),
                "dependencyTypes": dependency_types,
                "runtimeState": None,
                "activeActions": [],
                "latestResult": None,
            }
        )
    counts = Counter(ticket["state"] for ticket in tickets)
    return {
        **unavailable,
        "available": True,
        "formalSummary": f"{counts.get('SATISFIED', 0)}/{len(tickets)} 已验收",
        "tickets": tickets,
        "counts": dict(counts),
    }


def _gate_label(state: dict[str, Any]) -> tuple[str, str]:
    history = state.get("attemptHistory")
    current = history[-1] if isinstance(history, list) and history else {}
    gate = current.get("gate") if isinstance(current, dict) else None
    if not gate:
        return "尚未关闭", "open"
    if isinstance(gate, dict):
        verdict = str(gate.get("verdict") or gate.get("status") or "unknown")
    else:
        verdict = str(gate)
    labels = {"pass": "最终门禁已通过", "blocked": "最终门禁受阻", "fail": "最终门禁未通过"}
    return labels.get(verdict.lower(), verdict), verdict


def _trail_rows(path: Path) -> list[dict[str, Any]] | None:
    if not path.is_file():
        return []
    try:
        data = path.read_bytes()
    except OSError:
        return None
    lines = data.splitlines(keepends=True)
    if lines and not lines[-1].endswith((b"\n", b"\r")):
        lines.pop()
    rows = []
    for line in lines:
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(row, dict):
            return None
        rows.append(row)
    return rows


def _attempt_trail_rows(package_root: Path, attempt_id: str) -> list[dict[str, Any]] | None:
    directory = package_root / "execution" / attempt_id
    archives = sorted(
        (
            (int(match.group(1)), path)
            for path in directory.iterdir()
            if path.is_file() and (match := TRAIL_ARCHIVE_RE.fullmatch(path.name))
        ),
        key=lambda item: item[0],
    ) if directory.is_dir() else []
    paths = [path for _, path in archives]
    current = directory / "trail.jsonl"
    if current.is_file():
        paths.append(current)
    rows = []
    for path in paths:
        current_rows = _trail_rows(path)
        if current_rows is None:
            return None
        rows.extend(current_rows)
    return rows


def _trail_identifiers(row: dict[str, Any]) -> set[str]:
    result = set()
    for name in ("seq", "id", "dispatch_id", "dispatchId", "decision_id", "decisionId"):
        if row.get(name) is not None:
            result.add(str(row[name]))
    return result


def _ticket_trail_projection(
    package_root: Path, attempt_id: Any, ticket_ids: list[str]
) -> tuple[list[str], list[str], dict[str, dict[str, Any]]]:
    if not isinstance(attempt_id, str) or not attempt_id:
        return [], [], {}
    rows = _attempt_trail_rows(package_root, attempt_id)
    if rows is None:
        return [], [], {}
    # Topic 的归属独立于派发/返回，可在旧记录之后补齐；只采信明确的 Ticket ID。
    topic_tickets: dict[str, list[str]] = {}
    for row in rows:
        subject = row.get("subject")
        bindings = row.get("ticketIds")
        if isinstance(subject, str) and subject.startswith("topic:") and isinstance(bindings, list):
            topic_tickets[subject] = list(dict.fromkeys(
                resolved for token in bindings if isinstance(token, str)
                if (resolved := _resolve_ticket_id(token, ticket_ids)) in ticket_ids
            ))
    expanded_rows = []
    for row in rows:
        subject = row.get("subject")
        if isinstance(subject, str) and subject.startswith("topic:"):
            expanded_rows.extend({**row, "subject": f"ticket:{ticket_id}"}
                                 for ticket_id in topic_tickets.get(subject, []))
        else:
            expanded_rows.append(row)
    rows = expanded_rows
    started: list[str] = []
    open_dispatches: list[dict[str, Any]] = []
    latest_results: dict[str, dict[str, Any]] = {}
    for row in rows:
        subject = row.get("subject")
        if not isinstance(subject, str) or not subject.startswith("ticket:"):
            continue
        ticket_id = _resolve_ticket_id(subject.removeprefix("ticket:"), ticket_ids)
        if ticket_id not in ticket_ids:
            continue
        kind = row.get("kind")
        if kind == "dispatch" and str(row.get("outcome", "")).upper() == "RUNNING" and row.get("returned") is False:
            if ticket_id not in started:
                started.append(ticket_id)
            open_dispatches.append({"ticketId": ticket_id, **row})
            continue
        if kind not in {"result", "worker-return"}:
            continue
        reference = next(
            (
                str(row[name])
                for name in ("of", "decision", "dispatch_id", "dispatchId", "decision_id", "decisionId")
                if row.get(name) is not None
            ),
            None,
        )
        match_index = None
        if reference is not None:
            match_index = next(
                (
                    index
                    for index in range(len(open_dispatches) - 1, -1, -1)
                    if open_dispatches[index]["ticketId"] == ticket_id
                    and reference in _trail_identifiers(open_dispatches[index])
                ),
                None,
            )
        elif isinstance(row.get("worker"), str):
            match_index = next(
                (
                    index
                    for index in range(len(open_dispatches) - 1, -1, -1)
                    if open_dispatches[index]["ticketId"] == ticket_id
                    and open_dispatches[index].get("worker") == row["worker"]
                ),
                None,
            )
        if match_index is not None:
            open_dispatches.pop(match_index)
        summary = row.get("summary")
        if not isinstance(summary, str) or not summary.strip():
            summary = "该执行步骤已返回，但没有登记摘要。"
        latest_results[ticket_id] = {
            "outcome": str(row.get("outcome") or "unknown"),
            "at": row.get("ts") if isinstance(row.get("ts"), str) else None,
            "summary": sanitise_activity(summary)[:MAX_TRAIL_SUMMARY_CHARS],
        }
    projections: dict[str, dict[str, Any]] = {}
    for ticket_id in ticket_ids:
        actions = []
        for row in open_dispatches:
            if row["ticketId"] != ticket_id:
                continue
            track = row.get("review_track")
            step = row.get("step")
            label = " · ".join(
                value.strip()
                for value in (track, step)
                if isinstance(value, str) and value.strip()
            )
            if not label:
                worker = row.get("worker")
                label = str(worker).rsplit("/", 1)[-1] if isinstance(worker, str) else "执行步骤"
            actions.append(
                {
                    "label": sanitise_activity(label)[:MAX_TRAIL_SUMMARY_CHARS],
                    "at": row.get("ts") if isinstance(row.get("ts"), str) else None,
                }
            )
        projections[ticket_id] = {
            "activeActions": actions,
            "latestResult": latest_results.get(ticket_id),
        }
    active = [ticket_id for ticket_id in ticket_ids if projections[ticket_id]["activeActions"]]
    return started, active, projections


def _empty_review_stats(warning: str) -> dict[str, Any]:
    return {
        "version": 1,
        "totals": {
            "unique": 0,
            "open": 0,
            "closed": 0,
            "trackContributions": 0,
            "unattributed": 0,
        },
        "tracks": {
            track: {"caught": 0, "open": 0, "closed": 0}
            for track in REVIEW_TRACKS
        },
        "tickets": {},
        "coverage": {"warnings": [warning]},
    }


def _valid_review_stats(value: Any) -> bool:
    if not isinstance(value, dict) or value.get("version") != 1:
        return False
    totals = value.get("totals")
    if not isinstance(totals, dict):
        return False
    if any(
        type(totals.get(key)) is not int or totals[key] < 0
        for key in ("unique", "open", "closed", "trackContributions", "unattributed")
    ):
        return False
    tracks = value.get("tracks")
    if not isinstance(tracks, dict):
        return False
    for track in REVIEW_TRACKS:
        counts = tracks.get(track)
        if not isinstance(counts, dict) or any(
            type(counts.get(key)) is not int or counts[key] < 0
            for key in ("caught", "open", "closed")
        ):
            return False
    return isinstance(value.get("tickets"), dict) and isinstance(value.get("coverage"), dict)


def review_stats_snapshot(package_root: Path) -> dict[str, Any]:
    if review_track_stats is None:
        return _empty_review_stats("Review statistics helper is unavailable.")
    try:
        result = review_track_stats.calculate_review_stats(package_root)
    except Exception:
        return _empty_review_stats("Review statistics could not be calculated.")
    if not _valid_review_stats(result):
        return _empty_review_stats("Review statistics returned an invalid result.")
    return result


def package_snapshot(package_root: Path, activities: list[dict[str, str]]) -> dict[str, Any]:
    state_path = package_root / ".impl-package" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ticket_states = state.get("tickets") if isinstance(state.get("tickets"), dict) else {}
    ticket_ids = [str(ticket_id) for ticket_id in ticket_states]
    attempt = state.get("attempt") if isinstance(state.get("attempt"), dict) else {}
    metadata = _ticket_metadata(package_root, ticket_ids, attempt.get("id"))
    plan_dependencies = _plan_dependencies(package_root, ticket_ids)
    tickets = []
    for ticket_id, value in ticket_states.items():
        formal_state = str(value.get("state", "UNKNOWN")) if isinstance(value, dict) else "UNKNOWN"
        meta = metadata.get(str(ticket_id).upper(), {})
        dependency_types = {"implementation": [], "acceptance": [], "release": []}
        for source in (meta.get("dependencyTypes", {}), plan_dependencies.get(str(ticket_id), {})):
            for dependency_type in dependency_types:
                for dependency in source.get(dependency_type, []):
                    if dependency not in dependency_types[dependency_type]:
                        dependency_types[dependency_type].append(dependency)
        dependencies = [
            dependency
            for dependency_type in ("implementation", "acceptance", "release")
            for dependency in dependency_types[dependency_type]
        ]
        tickets.append(
            {
                "id": str(ticket_id),
                "name": meta.get("name", str(ticket_id)),
                "state": formal_state,
                "completionHints": meta.get("completionHints", []),
                "dependencies": list(dict.fromkeys(dependencies)),
                "dependencyTypes": dependency_types,
            }
        )
    ticket_state_rows = {str(ticket_id): value for ticket_id, value in ticket_states.items()}
    readiness_dependencies = {
        ticket["id"]: [
            (dependency_type, dependency)
            for dependency_type in ("implementation", "acceptance", "release")
            for dependency in ticket["dependencyTypes"][dependency_type]
        ]
        for ticket in tickets
    }
    ready_ticket_ids = impl_package_engine.ready_tickets(readiness_dependencies, ticket_state_rows)
    terminal_ticket_ids = {
        ticket["id"] for ticket in tickets if ticket["state"] in {"SATISFIED", "RETIRED"}
    }
    trail_started_ticket_ids, trail_active_ticket_ids, trail_projection = _ticket_trail_projection(
        package_root, attempt.get("id"), ticket_ids
    )
    running_ticket_ids = [
        ticket_id
        for ticket_id in trail_started_ticket_ids
        if ticket_id not in terminal_ticket_ids and ticket_state_rows[ticket_id].get("state") == "PENDING"
    ]
    active_ticket_ids = [
        ticket_id for ticket_id in trail_active_ticket_ids if ticket_id not in terminal_ticket_ids
    ]
    for ticket in tickets:
        runtime_state = (
            "DEVELOPING"
            if ticket["id"] in running_ticket_ids and ticket["id"] in ready_ticket_ids
            else "INVESTIGATING"
            if ticket["id"] in running_ticket_ids
            else "READY"
            if ticket["id"] in ready_ticket_ids
            else None
        )
        ticket["runtimeState"] = runtime_state
        projection = trail_projection.get(ticket["id"], {"activeActions": [], "latestResult": None})
        if ticket["id"] in terminal_ticket_ids:
            projection = {**projection, "activeActions": []}
        ticket.update(projection)
    counts = Counter(ticket["state"] for ticket in tickets)
    checkpoints = state.get("activeCheckpoints")
    checkpoint = checkpoints.get("attempt", {}) if isinstance(checkpoints, dict) else {}
    next_action = checkpoint.get("next") if isinstance(checkpoint, dict) else None
    blocker = checkpoint.get("blocker") if isinstance(checkpoint, dict) else None
    gate_label, gate_value = _gate_label(state)
    mentioned = {
        _resolve_ticket_id(match.group(0), ticket_ids)
        for activity in activities
        for match in TICKET_REFERENCE_RE.finditer(activity.get("text", ""))
    }
    pending_mentions = [
        ticket["id"]
        for ticket in tickets
        if ticket["state"] in {"PENDING", "NEEDS-REVALIDATION"} and ticket["id"] in mentioned
    ]
    current_ticket_id = next(
        iter(active_ticket_ids or running_ticket_ids or ready_ticket_ids),
        next(
            (ticket["id"] for ticket in tickets if ticket["state"] not in {"SATISFIED", "RETIRED"}),
            tickets[0]["id"] if tickets else None,
        ),
    )
    discrepancy = None
    if pending_mentions:
        discrepancy = (
            f"主会话已经报告 {', '.join(pending_mentions)} 的实际工作进展，"
            "但正式验收状态仍未关闭；两种口径已分开保留。"
        )
    satisfied = counts.get("SATISFIED", 0)
    current_attempt = attempt.get("id")
    history = state.get("attemptHistory") if isinstance(state.get("attemptHistory"), list) else []
    current_history = next(
        (row for row in history if isinstance(row, dict) and row.get("id") == current_attempt),
        {},
    )
    attempts = [
        {
            "id": current_attempt,
            "current": True,
            "available": True,
            "lifecycle": current_history.get("lifecycle", "active"),
            "gate": current_history.get("gate"),
            "formalSummary": f"{satisfied}/{len(tickets)} 已验收",
            "tickets": tickets,
            "counts": dict(counts),
        },
        *[
            _historical_attempt(package_root, row)
            for row in reversed(history)
            if isinstance(row, dict) and row.get("id") != current_attempt
        ],
    ]
    return {
        "name": _plan_name(package_root),
        "formalSummary": f"{satisfied}/{len(tickets)} 已验收",
        "gateLabel": gate_label,
        "gateValue": gate_value,
        "nextAction": next_action or "当前 package 没有登记下一动作。",
        "blocker": blocker,
        "discrepancy": discrepancy,
        "currentTicketId": current_ticket_id,
        "readyTicketIds": ready_ticket_ids,
        "runningTicketIds": running_ticket_ids,
        "tickets": tickets,
        "attempts": attempts,
        "counts": dict(counts),
        "reviewStats": review_stats_snapshot(package_root),
        "audit": {
            "relativePath": package_root.name,
            "attempt": attempt.get("id"),
            "formatVersion": state.get("formatVersion"),
            "stateModifiedAt": datetime.fromtimestamp(state_path.stat().st_mtime).astimezone().isoformat(timespec="seconds"),
        },
    }


def build_snapshot(thread_id: str, package: str | None, db_path: Path = DEFAULT_DB) -> dict[str, Any]:
    row = _task_row(thread_id, db_path)
    cwd, rollout = _task_paths(row, db_path)
    projection = ROLLOUT_READER.read(rollout)
    package_root = _package_root(cwd, package)
    package_data = package_snapshot(package_root, projection["activities"]) if package_root else None
    return {
        "task": {
            "id": row["id"],
            "name": _safe_name(row["name"], row["updated_at"]),
            "status": projection["status"],
            "updatedAt": _iso_timestamp(row["updated_at"]),
        },
        "actualProgress": {
            "summary": projection["activities"][0]["text"] if projection["activities"] else "尚未观察到用户可见进展。",
            "activities": projection["activities"],
        },
        "package": package_data,
        "monitor": monitor_snapshot(cwd, package_root),
        "audit": {
            "taskId": row["id"],
            "workspace": str(cwd),
            "branch": row["git_branch"],
            "revision": row["git_sha"],
            "rolloutOffset": projection["offset"],
        },
    }


class DashboardHandler(BaseHTTPRequestHandler):
    server_version = "CodexProgressDashboard/2"

    @property
    def db_path(self) -> Path:
        return self.server.db_path  # type: ignore[attr-defined]

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")

    def _headers(self, content_type: str, status: HTTPStatus = HTTPStatus.OK) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
            "img-src 'self' data:; base-uri 'none'; form-action 'none'; frame-ancestors 'none'",
        )

    def _json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers("application/json; charset=utf-8", status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json({"error": message}, status)

    def _static(self, filename: str, content_type: str) -> None:
        body = (APP_DIR / filename).read_bytes()
        self._headers(content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _route(self) -> tuple[str, str | None, str | None]:
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[:2] == ["api", "tasks"]:
            thread_id = parts[2]
            action = parts[3] if len(parts) == 4 else None
            return thread_id, action, parse_qs(parsed.query).get("package", [None])[0]
        return "", None, None

    def _request_json(self, fields: set[str]) -> dict[str, Any]:
        origin = self.headers.get("Origin")
        expected_origin = f"http://{HOST}:{self.server.server_address[1]}"  # type: ignore[attr-defined]
        if origin and origin != expected_origin:
            raise PermissionError("cross-origin write rejected")
        if self.headers.get_content_type() != "application/json":
            raise ValueError("content type must be application/json")
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError as exc:
            raise ValueError("invalid content length") from exc
        if not 0 < length <= MAX_REQUEST_BODY_BYTES:
            raise ValueError("request body is empty or too large")
        payload = json.loads(self.rfile.read(length))
        if not isinstance(payload, dict) or set(payload) != fields:
            raise ValueError(f"request fields must be {sorted(fields)}")
        return payload

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._json(
                {
                    "rendererVersion": 2,
                    "monitorProgressProtocol": monitor_progress.PROTOCOL_VERSION,
                    "instanceId": self.server.instance_id,  # type: ignore[attr-defined]
                    "pid": os.getpid(),
                    "startedAt": self.server.started_at,  # type: ignore[attr-defined]
                }
            )
            return
        if parsed.path == "/":
            self._static("index.html", "text/html; charset=utf-8")
            return
        if parsed.path == "/app.js":
            self._static("app.js", "text/javascript; charset=utf-8")
            return
        if parsed.path == "/style.css":
            self._static("style.css", "text/css; charset=utf-8")
            return
        if parsed.path == "/api/tasks":
            self._json({"tasks": list_tasks(self.db_path)})
            return
        thread_id, action, package = self._route()
        try:
            if action == "packages":
                row = _task_row(thread_id, self.db_path)
                cwd, rollout = _task_paths(row, self.db_path)
                self._json({"packages": find_packages(cwd, rollout)})
            elif action == "snapshot":
                self._json(build_snapshot(thread_id, package, self.db_path))
            elif action == "events":
                self._events(thread_id, package)
            else:
                self._error(HTTPStatus.NOT_FOUND, "not found")
        except (FileNotFoundError, LookupError) as exc:
            self._error(HTTPStatus.NOT_FOUND, str(exc))
        except (json.JSONDecodeError, OSError, sqlite3.Error, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def do_PATCH(self) -> None:  # noqa: N802 - stdlib handler contract
        thread_id, action, package = self._route()
        if action != "observation":
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            payload = self._request_json({"id", "content", "revision"})
            row = _task_row(thread_id, self.db_path)
            cwd, _ = _task_paths(row, self.db_path)
            package_root = _package_root(cwd, package)
            if package_root is None:
                raise ValueError("package is required")
            observation = update_observation_content(
                cwd,
                package_root,
                payload["id"],
                payload["content"],
                payload["revision"],
            )
            self._json({"observation": observation})
        except PermissionError as exc:
            self._error(HTTPStatus.FORBIDDEN, str(exc))
        except ObservationConflictError as exc:
            self._error(HTTPStatus.CONFLICT, str(exc))
        except (FileNotFoundError, LookupError) as exc:
            self._error(HTTPStatus.NOT_FOUND, str(exc))
        except (json.JSONDecodeError, OSError, sqlite3.Error, ValueError) as exc:
            self._error(HTTPStatus.BAD_REQUEST, str(exc))

    def _events(self, thread_id: str, package: str | None) -> None:
        self._headers("text/event-stream; charset=utf-8")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        last_payload = ""
        try:
            while True:
                payload = json.dumps(build_snapshot(thread_id, package, self.db_path), ensure_ascii=False)
                if payload != last_payload:
                    self.wfile.write(f"event: snapshot\ndata: {payload}\n\n".encode("utf-8"))
                    self.wfile.flush()
                    last_payload = payload
                else:
                    self.wfile.write(b": keepalive\n\n")
                    self.wfile.flush()
                time.sleep(1)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            return
        finally:
            self.close_connection = True


def create_server(
    db_path: Path = DEFAULT_DB,
    port: int = PORT,
    instance_id: str = "embedded",
    started_at: str | None = None,
) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, port), DashboardHandler)
    server.db_path = db_path.resolve()  # type: ignore[attr-defined]
    server.instance_id = instance_id  # type: ignore[attr-defined]
    server.started_at = started_at or datetime.now().astimezone().isoformat(timespec="seconds")  # type: ignore[attr-defined]
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Local Codex implementation progress dashboard")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--port", type=int, default=PORT)
    parser.add_argument("--instance-id", default=uuid.uuid4().hex)
    parser.add_argument("--started-at", default=datetime.now().astimezone().isoformat(timespec="seconds"))
    args = parser.parse_args(argv)
    if not args.db.is_file():
        raise SystemExit(f"Codex state database not found: {args.db}")
    if not 1 <= args.port <= 65535:
        raise SystemExit("port must be between 1 and 65535")
    server = create_server(args.db, args.port, args.instance_id, args.started_at)
    print(f"Codex progress dashboard: http://{HOST}:{args.port}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
