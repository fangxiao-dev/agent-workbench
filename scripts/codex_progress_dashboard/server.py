"""Serve a loopback-only live progress view for local Codex tasks."""

from __future__ import annotations

import json
import re
import sqlite3
import threading
import time
from collections import Counter, deque
from dataclasses import dataclass, field
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse


HOST = "127.0.0.1"
PORT = 43187
APP_DIR = Path(__file__).resolve().parent
CODEX_HOME = Path.home() / ".codex"
DEFAULT_DB = CODEX_HOME / "state_5.sqlite"
THREAD_ID_RE = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
TICKET_ID_PATTERN = r"TKT-\d+(?:-[A-Za-z0-9]+)*"
TICKET_ID_RE = re.compile(rf"\b{TICKET_ID_PATTERN}\b", re.I)
TICKET_REFERENCE_RE = re.compile(r"\bTKT-?\d+(?:-[A-Za-z0-9]+)*\b", re.I)
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
MONITOR_DIR = Path(".progress-record") / "codex-progress-dashboard" / "monitors"
MONITOR_LEVELS = {"normal", "attention", "abnormal"}


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
        tasks.append(
            {
                "id": row["id"],
                "name": _safe_name(row["name"], row["updated_at"]),
                "updatedAt": _iso_timestamp(row["updated_at"]),
                "currentPackage": current_package,
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


def monitor_snapshot(workspace: Path, package_root: Path | None) -> dict[str, str] | None:
    if package_root is None:
        return None
    directory = workspace / MONITOR_DIR
    if not directory.is_dir():
        return None

    newest: tuple[float, dict[str, str]] | None = None
    for path in directory.glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            observed_at = str(record["observedAt"])
            observed_timestamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00")).timestamp()
            monitor_thread_id = str(record["monitorThreadId"])
            target_thread_id = str(record["targetThreadId"])
            level = str(record["level"])
            summary = sanitise_activity(str(record["summary"]))
            package_path = _normalise_path(record["packagePath"])
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            continue
        if (
            record.get("version") != 1
            or not THREAD_ID_RE.fullmatch(monitor_thread_id)
            or not THREAD_ID_RE.fullmatch(target_thread_id)
            or level not in MONITOR_LEVELS
            or package_path != package_root
            or not summary
        ):
            continue
        candidate = {
            "observedAt": observed_at,
            "level": level,
            "summary": summary,
            "monitorThreadId": monitor_thread_id,
        }
        if newest is None or observed_timestamp > newest[0]:
            newest = (observed_timestamp, candidate)
    return newest[1] if newest else None


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


def _ticket_metadata(package_root: Path, ticket_ids: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    ticket_dir = package_root / "tickets"
    if not ticket_dir.is_dir():
        return result
    for path in sorted(ticket_dir.glob("*.md")):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        match = re.search(rf"Ticket ID\s*[：:]\s*({TICKET_ID_PATTERN})", text, re.I)
        if not match:
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


def _ticket_released(ticket_id: str, ticket_states: dict[str, Any], visiting: set[str] | None = None) -> bool:
    row = ticket_states.get(ticket_id)
    if not isinstance(row, dict):
        return False
    state = row.get("state")
    if state == "SATISFIED":
        return True
    if state != "RETIRED":
        return False
    if row.get("disposition") == "waived":
        return True
    successor = row.get("successor")
    if not isinstance(successor, str):
        return False
    visiting = set() if visiting is None else visiting
    if ticket_id in visiting:
        return False
    visiting.add(ticket_id)
    return _ticket_released(successor, ticket_states, visiting)


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


def _trail_identifier(row: dict[str, Any]) -> str | None:
    for name in ("seq", "id", "dispatch_id", "dispatchId", "decision_id", "decisionId"):
        if row.get(name) is not None:
            return str(row[name])
    return None


def _running_ticket_ids(package_root: Path, attempt_id: Any, ticket_ids: set[str]) -> list[str]:
    if not isinstance(attempt_id, str) or not attempt_id:
        return []
    rows = _trail_rows(package_root / "execution" / attempt_id / "trail.jsonl")
    if rows is None:
        return []
    result_ids = {
        str(row[name])
        for row in rows
        if row.get("kind") in {"result", "worker-return"}
        for name in ("of", "decision", "dispatch_id", "dispatchId", "decision_id", "decisionId")
        if row.get(name) is not None
    }
    running = []
    for row in rows:
        if row.get("kind") != "dispatch" or str(row.get("outcome", "")).upper() != "RUNNING" or row.get("returned") is not False:
            continue
        identifier = _trail_identifier(row)
        subject = row.get("subject")
        if identifier is not None and identifier in result_ids:
            continue
        if not isinstance(subject, str) or not subject.startswith("ticket:"):
            continue
        ticket_id = subject.removeprefix("ticket:")
        if ticket_id in ticket_ids and ticket_id not in running:
            running.append(ticket_id)
    return running


def package_snapshot(package_root: Path, activities: list[dict[str, str]]) -> dict[str, Any]:
    state_path = package_root / ".impl-package" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    ticket_states = state.get("tickets") if isinstance(state.get("tickets"), dict) else {}
    ticket_ids = [str(ticket_id) for ticket_id in ticket_states]
    metadata = _ticket_metadata(package_root, ticket_ids)
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
    ready_ticket_ids = [
        ticket["id"]
        for ticket in tickets
        if ticket["state"] == "PENDING"
        and ticket["id"].upper() in metadata
        and all(
            _ticket_released(dependency, ticket_state_rows)
            for dependency in ticket["dependencyTypes"]["implementation"]
        )
    ]
    attempt = state.get("attempt") if isinstance(state.get("attempt"), dict) else {}
    terminal_ticket_ids = {
        ticket["id"] for ticket in tickets if ticket["state"] in {"SATISFIED", "RETIRED"}
    }
    running_ticket_ids = [
        ticket_id
        for ticket_id in _running_ticket_ids(package_root, attempt.get("id"), set(ticket_ids))
        if ticket_id not in terminal_ticket_ids
    ]
    for ticket in tickets:
        ticket["runtimeState"] = (
            "RUNNING"
            if ticket["id"] in running_ticket_ids
            else "READY"
            if ticket["id"] in ready_ticket_ids
            else None
        )
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
        iter(running_ticket_ids or ready_ticket_ids),
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
    return {
        "name": _plan_name(package_root),
        "formalSummary": f"{satisfied}/{len(tickets)} 已正式验收",
        "gateLabel": gate_label,
        "gateValue": gate_value,
        "nextAction": next_action or "当前 package 没有登记下一动作。",
        "blocker": blocker,
        "discrepancy": discrepancy,
        "currentTicketId": current_ticket_id,
        "readyTicketIds": ready_ticket_ids,
        "runningTicketIds": running_ticket_ids,
        "tickets": tickets,
        "counts": dict(counts),
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
    server_version = "CodexProgressDashboard/1"

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

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler contract
        parsed = urlparse(self.path)
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


def create_server(db_path: Path = DEFAULT_DB, port: int = PORT) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((HOST, port), DashboardHandler)
    server.db_path = db_path.resolve()  # type: ignore[attr-defined]
    return server


def main() -> None:
    if not DEFAULT_DB.is_file():
        raise SystemExit(f"Codex state database not found: {DEFAULT_DB}")
    server = create_server()
    print(f"Codex progress dashboard: http://{HOST}:{PORT}")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
