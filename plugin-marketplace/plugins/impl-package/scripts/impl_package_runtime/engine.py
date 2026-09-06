"""Ticket-first Impl-Package state runtime (format 3.5).

The 3.5 runtime intentionally has one state axis: Tickets.  A one-time
migration validator may read 3.4 packages, but this runtime never dual-reads
the legacy state shape.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from situation import (
    FACT_KEYS,
    REVIEW_PHASES,
    REVIEW_PHASE_VALUES,
    REVIEW_TRACKS,
    REVIEW_TRACK_VALUES,
    describe_unknown_fact_keys,
    live_package_reference_fact,
)

STATE_PATH = Path(".impl-package/state.json")
ATTEMPT_ARCHIVE_PATH = Path(".impl-package/attempts")
PROGRESS_PATH = Path("progress.md")
EXECUTION_PATH = Path("execution")
ACTIVE_TRAIL_NAME = "trail.jsonl"
TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")
GATE_PATH = Path("gate.md")
FORMAT_VERSION = "3.5"

TICKET_STATES = {"PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED"}
TERMINAL_VERDICTS = {"pass", "fail", "defer"}
VERDICTS = TERMINAL_VERDICTS | {"blocked"}
TIMINGS = {"early-falsification", "remaining-completion"}
CONCLUSIONS = {"supporting", "contradictory", "inconclusive"}
DISPOSITIONS = {"waived", "superseded"}
TRAIL_APPEND_KINDS = frozenset({"dispatch", "escape", "fact", "worker-return"})
TRAIL_COMMON_FIELDS = frozenset({"v", "seq", "ts", "head"})
TRAIL_DIGEST_RE = re.compile(r"^[0-9a-fA-F]{12}$")
SITUATION_DIGEST_NAME = "situation-digest.json"
DISPATCH_DIGEST_GUIDANCE = "dispatch 需要当前处境的 digest：先运行 situation.py render 取 digest，再重写这条 dispatch"

ATTEMPT_RE = re.compile(r"(?m)^(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:](?:\*\*)?\s*([^\s*]+)")
COMPOSITION_RE = re.compile(r"Composition[^\n]*tickets=(true|false),\s*dag=(true|false)", re.I)
DECISION_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Decision Revision|决策修订（Decision Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(D\d+)\b")
SPEC_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Spec Revision|规格修订（Spec Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(S\d+)\b")
PLAN_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Plan Revision|计划修订（Plan Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(P\d+)\b")
PREDECESSORS_RE = re.compile(r"(?m)^\s*-\s*前置包\s*(?:（Predecessors）|\(Predecessors\))\s*[：:]\s*(.*?)\s*$")
TICKET_ID_RE = re.compile(r"(?m)^\s*(?:\*\*)?Ticket ID\s*[：:](?:\*\*)?\s*([^\s*]+)")
PUBLICATION_RE = re.compile(r"(?m)^(\s*(?:\*\*)?(?:Publication Status|发布状态（Publication Status）)\s*[：:](?:\*\*)?\s*)(Draft|Approved)\s*$")
CLAIM_RE = re.compile(r"Stable claim ID：\s*`([^`]+)`")
TIMING_RE = re.compile(r"证据时机：\s*`([^`]+)`")
ARRIVAL_PATH_RE = re.compile(r"(?m)^\s*-\s*到达路径\s*[：:]\s*(.*?)\s*$")
ARRIVAL_SEGMENT_RE = re.compile(r"^(EXISTS|NEW)\s*:\s*(.+?)\s*$")
ER_ENTRY_RE = re.compile(r"(?m)^## ([^\s]+-ER-(\d{3})) · (checkpoint|judgment)\s*$")
COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
PACKAGE_ID_RE = re.compile(r"^(?:\d{6}|\d{8}|\d{4}-\d{2}-\d{2})[-_][A-Za-z0-9].+")
ATTEMPT_ID_RE = re.compile(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})")

class StateError(RuntimeError):
    pass


@dataclass(frozen=True)
class Lifecycle:
    attempt: str
    value: str
    gate: dict[str, Any] | None

    @property
    def frozen(self) -> bool:
        return self.value == "frozen"

    @property
    def gate_verdict(self) -> str:
        return self.gate["verdict"] if self.gate else "open"


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise StateError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _repo_root(package: Path) -> Path:
    return Path(_run_git(package, "rev-parse", "--show-toplevel")).resolve()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"{path} must contain a JSON object")
    return value


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _attempt_archive_path(package: Path, attempt: str) -> Path:
    if ATTEMPT_ID_RE.fullmatch(attempt) is None:
        raise StateError(f"invalid Attempt ID: {attempt!r}")
    return package / ATTEMPT_ARCHIVE_PATH / f"{attempt}.json"


def _ticket_snapshot(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        raise StateError("Attempt Ticket snapshot must be an object")
    snapshot: dict[str, dict[str, Any]] = {}
    for ticket_id, row in value.items():
        if not isinstance(ticket_id, str) or not ticket_id or not isinstance(row, dict):
            raise StateError("Attempt Ticket snapshot contains an invalid Ticket")
        if row.get("state") not in TICKET_STATES:
            raise StateError(f"Attempt Ticket snapshot has invalid state for {ticket_id}")
        snapshot[ticket_id] = json.loads(json.dumps(row, ensure_ascii=False))
    return snapshot


def _write_attempt_archive(package: Path, attempt: str, tickets: Any) -> bool:
    payload = {"attempt": attempt, "tickets": _ticket_snapshot(tickets)}
    path = _attempt_archive_path(package, attempt)
    if path.is_file():
        if _load_json(path) != payload:
            raise StateError(f"attempt archive conflict: {attempt}")
        return False
    _write_json(path, payload)
    return True


def command_archive_attempt(package: Path, attempt: str, revision: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    history = next((row for row in summary["_history"] if row["id"] == attempt), None)
    if history is None or history["lifecycle"] != "frozen":
        raise StateError(f"Attempt {attempt} is not frozen in current history")
    repo = _repo_root(package)
    resolved = _validate_commit(repo, revision)
    state_path = (package / STATE_PATH).resolve().relative_to(repo).as_posix()
    try:
        historical = json.loads(_run_git(repo, "show", f"{resolved}:{state_path}"))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid historical state at {resolved}") from exc
    if not isinstance(historical, dict):
        raise StateError(f"historical state at {resolved} must be an object")
    historical_attempt = historical.get("attempt")
    if not isinstance(historical_attempt, dict) or historical_attempt.get("id") != attempt:
        raise StateError(f"historical state at {resolved} does not belong to Attempt {attempt}")
    tickets = _ticket_snapshot(historical.get("tickets"))
    document_ids = {document["id"] for document in _ticket_documents(package, attempt)}
    if set(tickets) != document_ids:
        raise StateError(f"historical Ticket state does not match Attempt {attempt} Ticket files")
    created = _write_attempt_archive(package, attempt, tickets)
    return {"attempt": attempt, "revision": resolved, "idempotent": not created}


def _trail_path(package: Path, attempt: str) -> Path:
    return package / EXECUTION_PATH / attempt / ACTIVE_TRAIL_NAME


def _trail_identity(row: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in row.items() if key not in {"seq", "ts"}}


@contextmanager
def _trail_append_lock(path: Path):
    lock_path = path.with_name(path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+b") as lock:
        lock.seek(0, os.SEEK_END)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        locked = False
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
            locked = True
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
            locked = True
        try:
            yield
        finally:
            if locked:
                if os.name == "nt":
                    msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _trail_next_seq(path: Path) -> int:
    maximum = 0
    sources = [path]
    if path.parent.is_dir():
        sources.extend(
            candidate
            for candidate in path.parent.iterdir()
            if candidate.is_file() and TRAIL_ARCHIVE_RE.fullmatch(candidate.name)
        )
    for source in sources:
        if not source.exists():
            continue
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict) and isinstance(row.get("seq"), int) and not isinstance(row.get("seq"), bool):
                maximum = max(maximum, row["seq"])
    return maximum + 1


def _append_trail(package: Path, attempt: str, event: dict[str, Any]) -> bool:
    path = _trail_path(package, attempt)
    with _trail_append_lock(path):
        repo = _repo_root(package)
        head = _run_git(repo, "rev-parse", "HEAD")
        row = {
            "v": 1,
            "seq": _trail_next_seq(path),
            "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **event,
            "head": head,
        }
        if path.exists():
            for line in path.read_text(encoding="utf-8-sig").splitlines():
                if not line.strip():
                    continue
                try:
                    previous = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(previous, dict) and _trail_identity(previous) == _trail_identity(row):
                    return False
        with path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":"), sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return True


def _best_effort_trail(package: Path, attempt: str, event: dict[str, Any]) -> None:
    try:
        _append_trail(package, attempt, event)
    except Exception as exc:  # trail is observational; state remains authoritative
        print(
            f"warning: state mutation committed but trail append failed ({event.get('kind', 'event')}): {exc}",
            file=sys.stderr,
        )


def _next_trail_archive(path: Path) -> Path:
    maximum = 0
    if path.parent.is_dir():
        for candidate in path.parent.iterdir():
            match = TRAIL_ARCHIVE_RE.fullmatch(candidate.name)
            if match and candidate.is_file():
                maximum = max(maximum, int(match.group(1)))
    if maximum >= 999:
        raise StateError("trail archive sequence exhausted at trail.999.jsonl")
    return path.with_name(f"trail.{maximum + 1:03d}.jsonl")


def _rotate_trail(package: Path, attempt: str) -> Path | None:
    path = _trail_path(package, attempt)
    with _trail_append_lock(path):
        if not path.exists():
            _write_text(path, "")
            return None
        if not path.is_file():
            raise StateError(f"active trail is not a file: {path}")
        archive = _next_trail_archive(path)
        if archive.exists():
            raise StateError(f"trail archive already exists: {archive}")
        path.replace(archive)
        _write_text(path, "")
        return archive


def _best_effort_trail_rotation(package: Path, attempt: str) -> None:
    try:
        _rotate_trail(package, attempt)
    except Exception as exc:  # state is authoritative; rotation is observational
        print(
            f"warning: state mutation committed but trail rotation failed: {exc}",
            file=sys.stderr,
        )


def _field(pattern: re.Pattern[str], text: str, label: str, *, optional: bool = False) -> str | None:
    match = pattern.search(text)
    if match:
        return match.group(1)
    if optional:
        return None
    raise StateError(f"missing {label}")


def _repo_relative(repo: Path, value: str, field: str, *, must_exist: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{field} must be a non-empty repository-relative path")
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw.split("#", 1)[0])
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw) or raw.startswith("//") or ".." in path.parts or str(path) in {"", "."}:
        raise StateError(f"{field} must be a repository-relative path: {value!r}")
    resolved = (repo / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError as exc:
        raise StateError(f"{field} escapes the repository: {value!r}") from exc
    if must_exist and not resolved.exists():
        raise StateError(f"{field} does not exist: {path.as_posix()}")
    anchor = "#" + raw.split("#", 1)[1] if "#" in raw else ""
    return path.as_posix() + anchor


def _predecessors_from_plan(package: Path, repo: Path, text: str) -> list[str] | None:
    matches = list(PREDECESSORS_RE.finditer(text))
    if len(matches) != 1:
        raise StateError("plan must declare 前置包（Predecessors） exactly once")
    raw = matches[0].group(1).strip()
    if raw.casefold() == "none":
        return None
    if not raw:
        raise StateError("前置包（Predecessors） must be None or a repository-relative directory list")
    values = [item.strip() for item in raw.split(",")]
    if any(not item or item.casefold() == "none" for item in values):
        raise StateError("前置包（Predecessors） cannot mix None with paths or contain an empty path")
    result: list[str] = []
    for value in values:
        normalized = _repo_relative(repo, value, "predecessor")
        if "#" in normalized:
            raise StateError("predecessor must not contain a text anchor")
        path = repo / Path(*normalized.split("/"))
        if not path.is_dir():
            raise StateError(f"predecessor must be a directory: {normalized}")
        if path.resolve() == package.resolve():
            raise StateError("a package cannot declare itself as a predecessor")
        if normalized in result:
            raise StateError(f"duplicate predecessor: {normalized}")
        result.append(normalized)
    return result


def _normalize_state_predecessors(package: Path, repo: Path, value: Any) -> list[str] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not value:
        raise StateError("state predecessors must be null or a non-empty list")
    result: list[str] = []
    for item in value:
        if not isinstance(item, str):
            raise StateError("state predecessors must contain repository-relative paths")
        normalized = _repo_relative(repo, item, "state predecessor")
        if "#" in normalized or not (repo / Path(*normalized.split("/"))).is_dir():
            raise StateError(f"state predecessor must be an existing directory: {normalized}")
        if normalized in result:
            raise StateError(f"duplicate state predecessor: {normalized}")
        if (repo / Path(*normalized.split("/"))).resolve() == package.resolve():
            raise StateError("state cannot declare the current package as a predecessor")
        result.append(normalized)
    return result


def _package_relative(package: Path, path: Path) -> str:
    return path.resolve().relative_to(package.resolve()).as_posix()


def _plan_info(package: Path, repo: Path, plan_value: str) -> dict[str, Any]:
    plan_rel = _repo_relative(repo, plan_value, "plan")
    plan_path = repo / plan_rel.split("#", 1)[0]
    try:
        plan_path.resolve().relative_to(package.resolve())
    except ValueError as exc:
        raise StateError("current plan must be inside the package") from exc
    if not (package / "spec.md").is_file():
        raise StateError("spec.md is required for an active Attempt")
    text = _read(plan_path)
    composition = COMPOSITION_RE.search(text)
    if composition is None:
        raise StateError("plan is missing Composition tickets/dag fields")
    tickets = composition.group(1).lower() == "true"
    dag = composition.group(2).lower() == "true"
    if dag or not tickets:
        raise StateError("format 3.5 accepts only tickets=true, dag=false; migrate legacy packages first")
    attempt = _field(ATTEMPT_RE, text, "Attempt ID")
    if not isinstance(attempt, str) or ATTEMPT_ID_RE.fullmatch(attempt) is None:
        raise StateError(f"invalid Attempt ID: {attempt!r}")
    return {"path": plan_rel, "attempt": attempt, "decision": _field(DECISION_RE, text, "Decision Revision", optional=True), "spec": _field(SPEC_RE, text, "Spec Revision", optional=True), "plan": _field(PLAN_RE, text, "Plan Revision", optional=True), "predecessors": _predecessors_from_plan(package, repo, text), "tickets": tickets, "dag": False}


def _arrival_paths(text: str, ticket_id: str, path: Path) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for match in ARRIVAL_PATH_RE.finditer(text):
        line = text.count("\n", 0, match.start()) + 1
        segments = re.split(r"\s*(?:→|->)\s*", match.group(1).strip())
        if len(segments) < 2 or segments[0].casefold() != "entry" or segments[-1].casefold() != "arrival":
            raise StateError(f"Ticket {ticket_id} arrival path in {path.name}:{line} must use entry → ... → arrival")
        nodes: list[dict[str, str]] = []
        for segment in segments[1:-1]:
            marked = ARRIVAL_SEGMENT_RE.fullmatch(segment.strip())
            if marked is None:
                raise StateError(
                    f"Ticket {ticket_id} arrival path in {path.name}:{line} has an unmarked segment: {segment!r}; use EXISTS: or NEW:"
                )
            symbol = marked.group(2).strip()
            if symbol.startswith("`") and symbol.endswith("`"):
                symbol = symbol[1:-1].strip()
            if not symbol:
                raise StateError(f"Ticket {ticket_id} arrival path in {path.name}:{line} has an empty symbol")
            nodes.append({"kind": marked.group(1), "symbol": symbol})
        result.append({"line": line, "nodes": nodes})
    return result


def _ticket_documents(package: Path, attempt: str) -> list[dict[str, Any]]:
    directory = package / "tickets"
    if not directory.is_dir():
        raise StateError("Composition earns tickets but tickets/ is missing")
    result: list[dict[str, Any]] = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        if not child.is_file() or child.suffix.lower() != ".md":
            continue
        text = _read(child)
        identifier = _field(TICKET_ID_RE, text, f"Ticket ID in {child.name}")
        ticket_attempt = _field(ATTEMPT_RE, text, f"Attempt ID in {child.name}")
        if ticket_attempt != attempt:
            continue
        if any(row["id"] == identifier for row in result):
            raise StateError(f"duplicate Ticket ID for Attempt {attempt}: {identifier}")
        publication = PUBLICATION_RE.search(text)
        if publication is None:
            raise StateError(f"missing Publication Status in {child.name}")
        if "impl-package:projection runtime-acceptance" in text:
            raise StateError(f"Ticket {identifier} contains retired Runtime Acceptance projection")
        arrival_paths = _arrival_paths(text, str(identifier), child)
        matches = list(CLAIM_RE.finditer(text))
        claims = list(dict.fromkeys(match.group(1) for match in matches))
        if not claims:
            raise StateError(f"Ticket {identifier} has no stable claim IDs")
        claim_timings: dict[str, str] = {}
        for index, match in enumerate(matches):
            claim = match.group(1)
            segment = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
            timing_values = [match.group(1) for line in segment.splitlines() if re.match(r"^\s*-\s*证据时机：", line) for match in [TIMING_RE.search(line)] if match]
            if not timing_values:
                heading_start = text.rfind("## ", 0, match.start())
                heading_end = text.find("\n", heading_start)
                heading = text[heading_start:heading_end if heading_end >= 0 else len(text)]
                if "安全不变量" in heading:
                    timing_value = "early-falsification"
                else:
                    raise StateError(f"Ticket {identifier} claim {claim} has no evidence timing")
            else:
                if len(set(timing_values)) != 1:
                    raise StateError(f"Ticket {identifier} claim {claim} has conflicting evidence timing")
                timing_value = timing_values[0]
            if timing_value not in TIMINGS:
                raise StateError(f"Ticket {identifier} has invalid evidence timing")
            if claim in claim_timings and claim_timings[claim] != timing_value:
                raise StateError(f"Ticket {identifier} claim {claim} has conflicting evidence timing")
            claim_timings[claim] = timing_value
        result.append({"id": str(identifier), "path": child, "text": text, "publication": "Approved" if PUBLICATION_RE.search(text).group(2) == "Approved" else "Draft", "claims": claims, "claimTimings": claim_timings, "timings": sorted(set(claim_timings.values())), "arrivalPaths": arrival_paths})
    if not result and directory.exists():
        raise StateError(f"Composition earns tickets but no Ticket belongs to Attempt {attempt}")
    return result


def _ticket_dependencies(documents: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    identifiers = {row["id"] for row in documents}
    result: dict[str, list[tuple[str, str]]] = {}
    for row in documents:
        section = re.search(r"(?ms)^## 阻塞依赖\s*$\n(.*?)(?=^## |\Z)", row["text"])
        dependencies: list[tuple[str, str]] = []
        if section:
            for line in section.group(1).splitlines():
                stripped = line.strip()
                if not stripped.startswith("-") or stripped.lower() in {"- none", "- 无"}:
                    continue
                match = re.fullmatch(r"-\s*(implementation|acceptance|release)\s*:\s*([^\s]+)", stripped)
                if match is None:
                    raise StateError(f"Ticket {row['id']} has invalid typed dependency: {stripped}")
                if match.group(2) not in identifiers:
                    raise StateError(f"Ticket {row['id']} has unknown dependency: {match.group(2)}")
                dependencies.append((match.group(1), match.group(2)))
        result[row["id"]] = dependencies
    _reject_cycles({key: [item for _, item in value] for key, value in result.items()}, "Ticket dependency graph")
    return result


def _reject_cycles(graph: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise StateError(f"{label} contains a cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _validate_commit(repo: Path, commit: str) -> str:
    if not isinstance(commit, str) or COMMIT_RE.fullmatch(commit) is None:
        raise StateError(f"invalid Git commit ID: {commit!r}")
    return _run_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")


def _gate_info(package: Path, repo: Path) -> dict[str, Any] | None:
    path = package / GATE_PATH
    if not path.exists():
        return None
    text = _read(path)
    verdict = re.search(r"(?m)^- Verdict:\s*(pass|fail|blocked|defer)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    commit = re.search(r"(?m)^- Comparison commit:\s*([0-9a-fA-F]{7,64})\s*$", text)
    if not verdict or not attempt or not commit:
        raise StateError("gate.md is missing Verdict, Attempt, or Comparison commit")
    return {"verdict": verdict.group(1), "attempt": attempt.group(1), "commit": _validate_commit(repo, commit.group(1))}


def _lifecycle(package: Path, attempt: str, repo: Path) -> Lifecycle:
    gate = _gate_info(package, repo)
    if gate and gate["attempt"] == attempt and gate["verdict"] in TERMINAL_VERDICTS:
        return Lifecycle(attempt, "frozen", gate)
    return Lifecycle(attempt, "active", gate if gate and gate["attempt"] == attempt else None)


def _approve_ticket(document: dict[str, Any]) -> None:
    """Publish a Draft Ticket once; runtime state never projects into it."""
    if document["publication"] == "Approved":
        return
    text = PUBLICATION_RE.sub(lambda match: f"{match.group(1)}Approved", document["text"], count=1)
    _write_text(document["path"], text)
    document.update({"text": text, "publication": "Approved"})


def _execution_record_path(package: Path, attempt: str) -> Path:
    return package / EXECUTION_PATH / attempt / "execution-record.md"


def _new_execution_record(attempt: str) -> str:
    return f"# Execution Record · {attempt}\n\n- Attempt: {attempt}\n- Lifecycle: active\n- Gate: open\n\n> 记录执行 judgment 与审计上下文；active checkpoint 由 state.json 管理。\n"


def _ensure_execution_record(package: Path, attempt: str) -> Path:
    path = _execution_record_path(package, attempt)
    if not path.exists():
        _write_text(path, _new_execution_record(attempt))
    metadata = _parse_execution_record(path, attempt, entries=False)[0]
    if metadata["attempt"] != attempt:
        raise StateError(f"Execution Record Attempt mismatch: {path}")
    return path


def _entry_field(block: str, name: str, *, optional: bool = False) -> str | None:
    match = re.search(rf"(?m)^- {re.escape(name)}:\s*(.*?)\s*$", block)
    if match:
        return match.group(1)
    if optional:
        return None
    raise StateError(f"Execution Record entry is missing {name}")


def _parse_execution_record(path: Path, expected_attempt: str | None = None, *, entries: bool = True) -> tuple[dict[str, str], list[dict[str, Any]]]:
    text = _read(path)
    heading = re.search(r"(?m)^# Execution Record · ([^\s]+)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    lifecycle = re.search(r"(?m)^- Lifecycle:\s*(active|frozen)\s*$", text)
    gate = re.search(r"(?m)^- Gate:\s*(open|pass|fail|blocked|defer)\s*$", text)
    if not heading or not attempt or not lifecycle or not gate:
        raise StateError(f"invalid Execution Record header: {path}")
    if heading.group(1) != attempt.group(1) or (expected_attempt and attempt.group(1) != expected_attempt):
        raise StateError(f"Execution Record Attempt mismatch: {path}")
    if not entries:
        return {"attempt": attempt.group(1), "lifecycle": lifecycle.group(1), "gate": gate.group(1)}, []
    matches = list(ER_ENTRY_RE.finditer(text))
    parsed: list[dict[str, Any]] = []
    previous = 0
    seen: set[str] = set()
    for index, match in enumerate(matches):
        record_id, number, purpose = match.group(1), int(match.group(2)), match.group(3)
        if not record_id.startswith(attempt.group(1) + "-ER-") or record_id in seen or number <= previous:
            raise StateError(f"invalid Execution Record ID sequence: {record_id}")
        seen.add(record_id)
        previous = number
        block = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        sections = re.search(r"(?ms)^### Evidence\s*$\n(.*?)^### Content\s*$\n(.*)\Z", block.strip())
        if sections is None:
            raise StateError(f"Execution Record {record_id} is missing Evidence or Content")
        evidence = [line[2:].strip() for line in sections.group(1).strip().splitlines() if line.strip() not in {"- none", ""} and line.startswith("- ")]
        parsed.append({"id": record_id, "number": number, "purpose": purpose, "subject": _entry_field(block, "Subject"), "title": _entry_field(block, "Title"), "nextAction": _entry_field(block, "Next action", optional=True), "evidence": evidence, "content": sections.group(2).strip()})
    return {"attempt": attempt.group(1), "lifecycle": lifecycle.group(1), "gate": gate.group(1)}, parsed


def _set_execution_record_status(package: Path, attempt: str, lifecycle: str, gate: str) -> None:
    path = _ensure_execution_record(package, attempt)
    text = _read(path)
    text = re.sub(r"(?m)^- Lifecycle:\s*(?:active|frozen)\s*$", f"- Lifecycle: {lifecycle}", text, count=1)
    text = re.sub(r"(?m)^- Gate:\s*(?:open|pass|fail|blocked|defer)\s*$", f"- Gate: {gate}", text, count=1)
    _write_text(path, text)


def _ticket_claims(documents: list[dict[str, Any]]) -> dict[str, set[str]]:
    return {row["id"]: set(row["claims"]) for row in documents}


def _ticket_claim_timings(documents: list[dict[str, Any]]) -> dict[str, dict[str, str]]:
    return {row["id"]: dict(row["claimTimings"]) for row in documents}


def _evidence_coverage_for(claims: dict[str, set[str]], evidence: dict[str, dict[str, list[dict[str, Any]]]], ticket: str, revision: str, environment: str) -> tuple[list[str], list[str]]:
    missing: list[str] = []
    conflicting: list[str] = []
    for claim in claims[ticket]:
        records = evidence.get(ticket, {}).get(claim, [])
        current = [row for row in records if row["revision"] == revision and row["environment"] == environment and not row.get("invalidatedBy")]
        if not any(row["conclusion"] == "supporting" for row in current):
            missing.append(claim)
        if any(row["conclusion"] in {"contradictory", "inconclusive"} for row in current):
            conflicting.append(claim)
    return missing, conflicting


def _validate_evidence_index(repo: Path, index: Any, claims: dict[str, set[str]], claim_timings: dict[str, dict[str, str]], *, live: bool) -> dict[str, dict[str, list[dict[str, Any]]]]:
    if not isinstance(index, dict):
        raise StateError("evidenceIndex must be an object keyed by Ticket")
    unknown = set(index) - set(claims)
    if unknown:
        raise StateError(f"evidenceIndex has unknown Tickets: {', '.join(sorted(unknown))}")
    normalized: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for ticket, claim_map in index.items():
        if not isinstance(claim_map, dict):
            raise StateError(f"evidenceIndex[{ticket}] must be an object keyed by claim")
        unknown_claims = set(claim_map) - claims[ticket]
        if unknown_claims:
            raise StateError(f"evidenceIndex[{ticket}] has unknown claims: {', '.join(sorted(unknown_claims))}")
        normalized[ticket] = {}
        for claim, records in claim_map.items():
            if not isinstance(records, list):
                raise StateError(f"evidenceIndex[{ticket}][{claim}] must be a list")
            normalized[ticket][claim] = []
            for record in records:
                if not isinstance(record, dict):
                    raise StateError("evidence record must be an object")
                required = {"timing", "artifact", "revision", "environment", "conclusion"}
                if not required <= set(record):
                    raise StateError(f"evidence record for {ticket}/{claim} is missing required fields")
                if record["timing"] not in TIMINGS or record["conclusion"] not in CONCLUSIONS:
                    raise StateError(f"invalid evidence timing/conclusion for {ticket}/{claim}")
                expected_timing = claim_timings[ticket].get(claim)
                if expected_timing and record["timing"] != expected_timing:
                    raise StateError(f"evidence timing does not match Ticket claim {ticket}/{claim}")
                normalized_artifact = _repo_relative(repo, record["artifact"], f"evidence {ticket}/{claim}", must_exist=live)
                for field in ("revision", "environment"):
                    if not isinstance(record[field], str) or not record[field].strip():
                        raise StateError(f"evidence {ticket}/{claim} {field} must be non-empty")
                resolved_revision = _validate_commit(repo, record["revision"])
                copy = dict(record)
                copy["artifact"] = normalized_artifact
                copy["revision"] = resolved_revision
                if copy.get("invalidatedBy") is not None and (not isinstance(copy["invalidatedBy"], str) or not copy["invalidatedBy"].strip()):
                    raise StateError(f"evidence {ticket}/{claim} invalidatedBy must be text or null")
                normalized[ticket][claim].append(copy)
    return normalized


def _validate_checkpoints(repo: Path, checkpoints: Any, ticket_ids: set[str], *, live: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(checkpoints, dict):
        raise StateError("activeCheckpoints must be an object")
    result: dict[str, dict[str, Any]] = {}
    for subject, value in checkpoints.items():
        if subject != "attempt":
            match = re.fullmatch(r"ticket:([^\s]+)", subject)
            if not match or match.group(1) not in ticket_ids:
                raise StateError(f"invalid active checkpoint subject: {subject}")
        if not isinstance(value, dict) or set(value) != {"next", "blocker", "evidence"}:
            raise StateError(f"activeCheckpoints[{subject}] must contain next, blocker, evidence")
        if not isinstance(value["next"], str) or not value["next"].strip():
            raise StateError(f"activeCheckpoints[{subject}].next must be non-empty")
        if value["blocker"] is not None and (not isinstance(value["blocker"], str) or not value["blocker"].strip()):
            raise StateError(f"activeCheckpoints[{subject}].blocker must be null or non-empty")
        if not isinstance(value["evidence"], list) or any(not isinstance(item, str) for item in value["evidence"]):
            raise StateError(f"activeCheckpoints[{subject}].evidence must be a list")
        result[subject] = dict(value)
        result[subject]["evidence"] = [_repo_relative(repo, item, f"checkpoint {subject} evidence", must_exist=live) for item in value["evidence"]]
    return result


def _attempt_history(state: dict[str, Any], package: Path) -> list[dict[str, Any]]:
    history = state.get("attemptHistory")
    if not isinstance(history, list):
        raise StateError("attemptHistory must be a list")
    repo = _repo_root(package)
    result = []
    for row in history:
        if not isinstance(row, dict) or set(row) != {"id", "plan", "lifecycle", "gate", "executionRecord"}:
            raise StateError("invalid attemptHistory record")
        if not isinstance(row["id"], str) or ATTEMPT_ID_RE.fullmatch(row["id"]) is None:
            raise StateError("attemptHistory id must be valid")
        if row["lifecycle"] not in {"active", "frozen"}:
            raise StateError("attemptHistory lifecycle must be active or frozen")
        plan = _repo_relative(repo, row["plan"], "attemptHistory plan")
        execution_record = _repo_relative(package, row["executionRecord"], "attemptHistory executionRecord")
        gate = row["gate"]
        if gate is not None:
            if not isinstance(gate, dict) or set(gate) - {"verdict", "commit", "environment"} or not {"verdict", "commit"} <= set(gate):
                raise StateError("attemptHistory gate must be null or contain verdict and commit")
            if gate["verdict"] not in {"pass", "fail", "defer", "blocked"}:
                raise StateError("invalid attemptHistory gate verdict")
            gate = dict(gate)
            gate["commit"] = _validate_commit(repo, gate["commit"])
        result.append({**row, "plan": plan, "executionRecord": execution_record, "gate": gate})
    return result


def ready_tickets(dependencies: dict[str, list[tuple[str, str]]], tickets: dict[str, Any]) -> list[str]:
    return [identifier for identifier, edges in dependencies.items() if tickets[identifier]["state"] == "PENDING" and all(_ticket_released(tickets, item) for kind, item in edges if kind == "implementation")]


def _ticket_released(tickets: dict[str, Any], identifier: str, visiting: set[str] | None = None) -> bool:
    visiting = set() if visiting is None else visiting
    if identifier in visiting:
        return False
    visiting.add(identifier)
    row = tickets.get(identifier)
    if not isinstance(row, dict):
        return False
    if row["state"] == "SATISFIED":
        return True
    if row["state"] != "RETIRED":
        return False
    if row.get("disposition") == "waived":
        return True
    successor = row.get("successor")
    return isinstance(successor, str) and successor in tickets and _ticket_released(tickets, successor, visiting)


def _validate_state(package: Path, state: dict[str, Any], *, projections: bool = True) -> dict[str, Any]:
    expected = {"formatVersion", "attempt", "attemptHistory", "predecessors", "tickets", "evidenceIndex", "activeCheckpoints"}
    if set(state) != expected:
        raise StateError("state.json must use formatVersion 3.5 and contain attempt, attemptHistory, predecessors, tickets, evidenceIndex, activeCheckpoints")
    if state["formatVersion"] != FORMAT_VERSION:
        raise StateError(f"unsupported state formatVersion {state['formatVersion']!r}; expected {FORMAT_VERSION!r}")
    repo = _repo_root(package)
    attempt = state["attempt"]
    if not isinstance(attempt, dict) or set(attempt) != {"id", "plan"} or not isinstance(attempt["id"], str) or ATTEMPT_ID_RE.fullmatch(attempt["id"]) is None:
        raise StateError("state attempt must contain a valid id and plan")
    info = _plan_info(package, repo, attempt["plan"])
    if info["attempt"] != attempt["id"]:
        raise StateError("state Attempt ID does not match current plan")
    predecessors = _normalize_state_predecessors(package, repo, state["predecessors"])
    if predecessors != info["predecessors"]:
        raise StateError("state predecessors do not match the current plan")
    if not info["tickets"]:
        raise StateError("format 3.5 requires tickets=true")
    lifecycle = _lifecycle(package, attempt["id"], repo)
    documents = _ticket_documents(package, attempt["id"])
    ticket_ids = {row["id"] for row in documents}
    tickets = state["tickets"]
    if not isinstance(tickets, dict) or set(tickets) != ticket_ids:
        raise StateError("ticket state does not match current Attempt Ticket files")
    for identifier, row in tickets.items():
        if not isinstance(row, dict) or row.get("state") not in TICKET_STATES:
            raise StateError(f"invalid Ticket state record: {identifier}")
        if row["state"] == "RETIRED":
            allowed_retired = {"state", "disposition", "evidence"} | ({"successor"} if row.get("disposition") == "superseded" else set())
            if set(row) != allowed_retired or row["disposition"] not in DISPOSITIONS or not isinstance(row["evidence"], str):
                raise StateError(f"RETIRED Ticket {identifier} requires disposition")
            _repo_relative(repo, row["evidence"], f"RETIRED {identifier} evidence", must_exist=lifecycle.value == "active")
            if row["disposition"] == "superseded" and (row.get("successor") not in ticket_ids or row.get("successor") == identifier):
                raise StateError(f"RETIRED superseded Ticket {identifier} requires a valid successor")
        elif row["state"] == "SATISFIED":
            if set(row) != {"state", "acceptance"} or not isinstance(row["acceptance"], dict) or set(row["acceptance"]) != {"revision", "environment"}:
                raise StateError(f"SATISFIED Ticket {identifier} requires acceptance revision/environment")
            _validate_commit(repo, row["acceptance"]["revision"])
            if not isinstance(row["acceptance"]["environment"], str) or not row["acceptance"]["environment"].strip():
                raise StateError(f"SATISFIED Ticket {identifier} acceptance environment must be non-empty")
        elif row["state"] == "BLOCKED":
            if set(row) != {"state", "evidence"} or not isinstance(row["evidence"], str):
                raise StateError(f"BLOCKED Ticket {identifier} requires evidence")
            _repo_relative(repo, row["evidence"], f"BLOCKED {identifier} evidence", must_exist=lifecycle.value == "active")
        elif row["state"] == "NEEDS-REVALIDATION":
            if set(row) not in ({"state"}, {"state", "evidence"}):
                raise StateError(f"invalid NEEDS-REVALIDATION record: {identifier}")
            if "evidence" in row:
                _repo_relative(repo, row["evidence"], f"revalidation {identifier} evidence", must_exist=lifecycle.value == "active")
        elif set(row) != {"state"}:
            raise StateError(f"invalid Ticket state record: {identifier}")
    dependencies = _ticket_dependencies(documents)
    for retired_ticket, row in tickets.items():
        if row["state"] != "RETIRED" or row.get("disposition") != "superseded":
            continue
        inbound = [
            (ticket, kind)
            for ticket, edges in dependencies.items()
            for kind, dependency in edges
            if dependency == retired_ticket
        ]
        if inbound:
            raise StateError(f"superseded Ticket {retired_ticket} still has inbound edges: {inbound}")
    claims = _ticket_claims(documents)
    claim_timings = _ticket_claim_timings(documents)
    evidence = _validate_evidence_index(repo, state["evidenceIndex"], claims, claim_timings, live=lifecycle.value == "active")
    for identifier, row in tickets.items():
        if row["state"] != "SATISFIED":
            continue
        acceptance = row["acceptance"]
        acceptance_revision = _validate_commit(repo, acceptance["revision"])
        missing, conflicts = _evidence_coverage_for(claims, evidence, identifier, acceptance_revision, acceptance["environment"])
        if missing or conflicts:
            raise StateError(f"SATISFIED Ticket {identifier} has incomplete current evidence")
    checkpoints = _validate_checkpoints(repo, state["activeCheckpoints"], ticket_ids, live=lifecycle.value == "active")
    history = _attempt_history(state, package)
    if not history or history[-1]["id"] != attempt["id"]:
        raise StateError("attemptHistory must end with current Attempt")
    summary = {"formatVersion": FORMAT_VERSION, "attempt": attempt["id"], "revisions": {"decision": info["decision"], "spec": info["spec"], "plan": info["plan"]}, "predecessors": predecessors, "composition": {"tickets": True, "dag": False}, "tasks": 0, "tickets": len(tickets), "readyTickets": ready_tickets(dependencies, tickets), "gate": lifecycle.gate, "_lifecycle": lifecycle, "_info": info, "_documents": documents, "_ticketDependencies": dependencies, "_claims": claims, "_claimTimings": claim_timings, "_evidence": evidence, "_checkpoints": checkpoints, "_history": history}
    if projections:
        _validate_projections(package, state, summary)
    return summary


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format_aliases(revisions: dict[str, str | None]) -> str:
    values = [value for value in revisions.values() if value]
    return " / ".join(values) if values else "none (Git commit is the history anchor)"


def _render_progress(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> str:
    lifecycle: Lifecycle = summary["_lifecycle"]
    blockers = [f"ticket:{key}" for key, row in state["tickets"].items() if row["state"] == "BLOCKED"]
    lines = [f"# Attempt Progress · {summary['attempt']}", "", "> machine-owned projection；使用 `refresh-progress` 重建，不直接编辑。", "", f"- Attempt: {summary['attempt']}", f"- Contract aliases: {_format_aliases(summary['revisions'])}", "- Composition: tickets=true, dag=false", f"- Lifecycle: {lifecycle.value}", f"- Latest gate: {lifecycle.gate_verdict}", f"- Blockers: {', '.join(blockers) if blockers else 'none'}", "", "## Ticket Acceptance", "", "| Ticket | State | Evidence |", "| --- | --- | --- |"]
    for identifier, row in state["tickets"].items():
        claims = ", ".join(sorted(state["evidenceIndex"].get(identifier, {}))) or "none"
        lines.append(f"| {identifier} | {row['state']} | {_escape(claims)} |")
    lines.extend(["", "## Active Checkpoints", "", "| Subject | Status | Next action | Evidence |", "| --- | --- | --- | --- |"])
    checkpoints = state["activeCheckpoints"] if not lifecycle.frozen else {}
    if checkpoints:
        for subject, row in checkpoints.items():
            lines.append(f"| {subject} | active | {_escape(row['next'])} | {_escape(', '.join(row['evidence']) or 'none')} |")
    else:
        lines.append("| none | none | none | none |")
    lines.extend(["", "## Attempt History", "", "| Attempt | Lifecycle | Gate | Execution Record |", "| --- | --- | --- | --- |"])
    for row in state["attemptHistory"]:
        gate = row["gate"].get("verdict", "open") if isinstance(row["gate"], dict) else "open"
        lines.append(f"| {row['id']} | {row['lifecycle']} | {gate} | {row['executionRecord']} |")
    return "\n".join(lines) + "\n"


def _refresh_projections(package: Path, state: dict[str, Any]) -> dict[str, Any]:
    summary = _validate_state(package, state, projections=False)
    _ensure_execution_record(package, summary["attempt"])
    _write_text(package / PROGRESS_PATH, _render_progress(package, state, summary))
    _validate_projections(package, state, summary)
    return summary


def _validate_projections(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> None:
    for document in summary["_documents"]:
        if document["publication"] != "Approved":
            raise StateError(f"Ticket {document['id']} must be Approved")
    er_path = _execution_record_path(package, summary["attempt"])
    metadata, _ = _parse_execution_record(er_path, summary["attempt"], entries=False)
    lifecycle: Lifecycle = summary["_lifecycle"]
    if metadata != {"attempt": lifecycle.attempt, "lifecycle": lifecycle.value, "gate": lifecycle.gate_verdict}:
        raise StateError("current Attempt Execution Record lifecycle projection mismatch")
    expected_progress = _render_progress(package, state, summary)
    if not (package / PROGRESS_PATH).is_file() or _read(package / PROGRESS_PATH) != expected_progress:
        raise StateError("progress projection mismatch; run refresh-progress")


def _public(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def _git_grep_symbol(repo: Path, commit: str, symbol: str, paths: list[str], excluded: list[str]) -> list[str]:
    command = ["git", "-C", str(repo), "grep", "-I", "-F", "-l", "-e", symbol, commit, "--"]
    command.extend(paths or ["."])
    command.extend(f":!(exclude){path}" for path in excluded)
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    if result.returncode == 1:
        return []
    if result.returncode != 0:
        raise StateError(result.stderr.strip() or f"cannot search comparison commit {commit}")
    return [line for line in result.stdout.splitlines() if line.strip()]


PLAN_GATE_RE = re.compile(r"(?:不派发|不进入|必须先[^。；;\n]*?PASS|失败时不[^。；;\n]*)", re.I)
CONTRACT_DOC_NAMES = ("decision.md", "spec.md", "contract-design.md")


def _contains_ticket_id(text: str, ticket: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9_-]){re.escape(ticket)}(?![A-Za-z0-9_-])", text) is not None


def _contract_doc_name_findings(package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    ticket_ids = sorted(
        document["id"] for document in summary["_documents"] if document["publication"] == "Approved"
    )
    findings: list[dict[str, Any]] = []
    for name in CONTRACT_DOC_NAMES:
        path = package / name
        if not path.is_file():
            continue
        try:
            text = _read(path)
        except StateError:
            continue
        hits = {
            ticket: len(re.findall(rf"(?<![A-Za-z0-9_-]){re.escape(ticket)}(?![A-Za-z0-9_-])", text))
            for ticket in ticket_ids
        }
        matched = {ticket: count for ticket, count in hits.items() if count}
        if matched:
            findings.append(
                {
                    "code": "contract-doc-names-ticket",
                    "path": _package_relative(package, path),
                    "hitCount": sum(matched.values()),
                    "ticketIds": sorted(matched),
                }
            )
    return findings


def _uniform_ticket_timing_findings(summary: dict[str, Any]) -> list[dict[str, Any]]:
    claims = _ticket_claims(summary["_documents"])
    claim_timings = _ticket_claim_timings(summary["_documents"])
    findings: list[dict[str, Any]] = []
    for ticket in sorted(claims):
        values = {claim_timings[ticket][claim] for claim in claims[ticket]}
        if len(values) == 1:
            findings.append(
                {
                    "code": "ticket-evidence-timing-uniform",
                    "ticket": ticket,
                    "timing": next(iter(values)),
                    "claimCount": len(claims[ticket]),
                }
            )
    return findings


def _plan_prose_gate_findings(repo: Path, package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    plan_path = repo / Path(*summary["_info"]["path"].split("#", 1)[0].split("/"))
    try:
        plan_text = _read(plan_path)
    except StateError:
        return []
    inbound: dict[str, list[tuple[str, str]]] = {ticket: [] for ticket in summary["_ticketDependencies"]}
    for source, edges in summary["_ticketDependencies"].items():
        for kind, target in edges:
            inbound.setdefault(target, []).append((kind, source))
    plan_relative = _package_relative(package, plan_path)
    findings: list[dict[str, Any]] = []
    for line_number, line in enumerate(plan_text.splitlines(), start=1):
        for match in PLAN_GATE_RE.finditer(line):
            phrase = match.group(0)
            tickets = [ticket for ticket in inbound if _contains_ticket_id(phrase, ticket)]
            if not tickets:
                tickets = [ticket for ticket in inbound if _contains_ticket_id(line, ticket)]
            for ticket in tickets:
                inbound_types = sorted({kind for kind, _source in inbound[ticket]})
                if inbound_types != ["acceptance"]:
                    continue
                findings.append(
                    {
                        "code": "plan-prose-gates-acceptance-edge",
                        "ticket": ticket,
                        "path": plan_relative,
                        "line": line_number,
                        "detail": phrase,
                        "inboundTypes": inbound_types,
                    }
                )
    return findings


def _arrival_path_absent_findings(package: Path, summary: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        {
            "code": "ticket-arrival-path-absent",
            "ticket": document["id"],
            "path": _package_relative(package, document["path"]),
        }
        for document in summary["_documents"]
        if not document["arrivalPaths"]
    ]


def _arrival_findings(repo: Path, package: Path, summary: dict[str, Any], comparison_commit: str) -> list[dict[str, Any]]:
    package_rel = package.resolve().relative_to(repo.resolve()).as_posix()
    excluded = [package_rel, f"{package_rel}/**", "**/*.md"]
    predecessors = summary.get("predecessors") or []
    findings: list[dict[str, Any]] = []
    for document in summary["_documents"]:
        document_rel = _package_relative(package, document["path"])
        for route in document.get("arrivalPaths", []):
            for node in route["nodes"]:
                if node["kind"] != "EXISTS":
                    continue
                symbol = node["symbol"]
                if predecessors and _git_grep_symbol(repo, comparison_commit, symbol, predecessors, excluded):
                    continue
                if _git_grep_symbol(repo, comparison_commit, symbol, [], excluded):
                    continue
                findings.append(
                    {
                        "code": "arrival-exists-symbol-not-found",
                        "ticket": document["id"],
                        "path": document_rel,
                        "line": route["line"],
                        "symbol": symbol,
                        "comparisonCommit": comparison_commit,
                    }
                )
    return findings


def command_init(package: Path, attempt: str, plan: str) -> dict[str, Any]:
    if PACKAGE_ID_RE.fullmatch(package.name) is None:
        raise StateError("package directory must use an immutable date-prefixed ID")
    repo = _repo_root(package)
    info = _plan_info(package, repo, plan)
    if info["attempt"] != attempt:
        raise StateError("--attempt does not match the plan Attempt ID")
    path = package / STATE_PATH
    if path.exists():
        current = _load_json(path)
        current_summary = _validate_state(package, current, projections=False)
        if current_summary["attempt"] == attempt:
            for document in current_summary["_documents"]:
                _approve_ticket(document)
            _refresh_projections(package, current)
            return _public(_validate_state(package, current))
        if not current_summary["_lifecycle"].frozen:
            raise StateError("current Attempt is not terminal; refusing to replace state")
        _write_attempt_archive(package, current_summary["attempt"], current["tickets"])
        previous = current["attemptHistory"]
    else:
        previous = []
    documents = _ticket_documents(package, attempt)
    dependencies = _ticket_dependencies(documents)
    del dependencies
    history = list(previous)
    history.append({"id": attempt, "plan": info["path"], "lifecycle": "active", "gate": None, "executionRecord": f"execution/{attempt}/execution-record.md"})
    state: dict[str, Any] = {"formatVersion": FORMAT_VERSION, "attempt": {"id": attempt, "plan": info["path"]}, "attemptHistory": history, "predecessors": info["predecessors"], "tickets": {document["id"]: {"state": "PENDING"} for document in documents}, "evidenceIndex": {}, "activeCheckpoints": {}}
    execution_record = _execution_record_path(package, attempt)
    created_execution_record = not execution_record.exists()
    if created_execution_record:
        _ensure_execution_record(package, attempt)
    try:
        _validate_state(package, state, projections=False)
        _write_json(path, state)
    except Exception:
        if created_execution_record and execution_record.exists():
            execution_record.unlink()
        raise
    for document in documents:
        _approve_ticket(document)
    _refresh_projections(package, state)
    return _public(_validate_state(package, state))


def command_validate(package: Path, commit: str | None, *, check_arrival_paths: bool = True) -> dict[str, Any]:
    repo = _repo_root(package)
    resolved = _validate_commit(repo, commit) if commit else None
    path = package / STATE_PATH
    if not path.exists():
        result = {"active": False, "reason": "no-active-attempt", "commit": resolved}
        if check_arrival_paths:
            result["findings"] = []
        return result
    summary = _validate_state(package, _load_json(path))
    result = _public(summary)
    if check_arrival_paths:
        comparison_commit = resolved or _run_git(repo, "rev-parse", "HEAD")
        result["findings"] = (
            _contract_doc_name_findings(package, summary)
            + _uniform_ticket_timing_findings(summary)
            + _plan_prose_gate_findings(repo, package, summary)
            + _arrival_path_absent_findings(package, summary)
            + _arrival_findings(repo, package, summary, comparison_commit)
        )
        result["comparisonCommit"] = comparison_commit
    result.update({"active": True, "commit": resolved})
    return result


def command_refresh_progress(package: Path) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _refresh_projections(package, state)
    return {"attempt": summary["attempt"], "progress": _package_relative(package, package / PROGRESS_PATH)}


def _assert_mutable(summary: dict[str, Any]) -> None:
    if summary["_lifecycle"].frozen:
        raise StateError(f"Attempt {summary['attempt']} is frozen by terminal Gate {summary['_lifecycle'].gate_verdict}")


def _evidence_coverage(summary: dict[str, Any], ticket: str, revision: str, environment: str) -> tuple[list[str], list[str]]:
    return _evidence_coverage_for(summary["_claims"], summary["_evidence"], ticket, revision, environment)


def command_evidence_add(package: Path, payload_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(payload_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"evidence-add input is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateError("evidence-add input must be an object")
    required = {"ticket", "claim", "timing", "artifact", "revision", "environment", "conclusion"}
    if set(payload) - required - {"invalidatedBy"} or not required <= set(payload):
        raise StateError("evidence-add requires ticket, claim, timing, artifact, revision, environment, conclusion")
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    ticket, claim = payload["ticket"], payload["claim"]
    if ticket not in summary["_claims"] or claim not in summary["_claims"][ticket]:
        raise StateError(f"unknown Ticket/claim: {ticket}/{claim}")
    repo = _repo_root(package)
    record = dict(payload)
    record["artifact"] = _repo_relative(repo, record["artifact"], "evidence artifact")
    if record["timing"] not in TIMINGS or record["conclusion"] not in CONCLUSIONS:
        raise StateError("invalid evidence timing or conclusion")
    for field in ("revision", "environment"):
        if not isinstance(record[field], str) or not record[field].strip():
            raise StateError(f"evidence {field} must be non-empty")
    record["revision"] = _validate_commit(repo, record["revision"])
    records = state["evidenceIndex"].setdefault(ticket, {}).setdefault(claim, [])
    if record in records:
        return {"ticket": ticket, "claim": claim, "idempotent": True}
    records.append(record)
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    return {"ticket": ticket, "claim": claim, "idempotent": False}


def command_evidence_invalidate(package: Path, ticket: str, claim: str, artifact: str, invalidated_by: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if not isinstance(invalidated_by, str) or not invalidated_by.strip():
        raise StateError("invalidated-by must be non-empty")
    normalized = _repo_relative(_repo_root(package), artifact, "evidence artifact", must_exist=False)
    records = state["evidenceIndex"].get(ticket, {}).get(claim, [])
    for record in records:
        if record["artifact"] == normalized:
            record["invalidatedBy"] = invalidated_by
            _validate_state(package, state, projections=False)
            _write_json(package / STATE_PATH, state)
            _refresh_projections(package, state)
            return {"ticket": ticket, "claim": claim, "invalidated": True}
    raise StateError("evidence record not found")


def command_evidence_retire_claim(package: Path, ticket: str, claim: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    attempt = state.get("attempt")
    attempt_id = attempt.get("id") if isinstance(attempt, dict) else None
    if not isinstance(attempt_id, str) or ATTEMPT_ID_RE.fullmatch(attempt_id) is None:
        raise StateError("state attempt must contain a valid id")

    repo = _repo_root(package)
    if _lifecycle(package, attempt_id, repo).frozen:
        raise StateError(f"Attempt {attempt_id} is frozen")

    claims = _ticket_claims(_ticket_documents(package, attempt_id))
    if ticket not in claims:
        raise StateError(f"unknown Ticket: {ticket}")
    if claim in claims[ticket]:
        raise StateError(f"Ticket claim is still current: {ticket}/{claim}")

    evidence_index = state.get("evidenceIndex")
    if not isinstance(evidence_index, dict):
        raise StateError("evidenceIndex must be an object keyed by Ticket")
    ticket_index = evidence_index.get(ticket)
    if not isinstance(ticket_index, dict) or claim not in ticket_index:
        raise StateError(f"evidence claim not found: {ticket}/{claim}")
    records = ticket_index[claim]
    if not isinstance(records, list) or not records:
        raise StateError(f"evidence {ticket}/{claim} must contain records")
    if any(
        not isinstance(record, dict)
        or not isinstance(record.get("invalidatedBy"), str)
        or not record["invalidatedBy"].strip()
        for record in records
    ):
        raise StateError(f"evidence {ticket}/{claim} must be fully invalidated before retirement")

    candidate = json.loads(json.dumps(state, ensure_ascii=False))
    del candidate["evidenceIndex"][ticket][claim]
    _validate_state(package, candidate, projections=False)
    _write_json(package / STATE_PATH, candidate)
    _refresh_projections(package, candidate)
    return {"ticket": ticket, "claim": claim, "retired": True, "removedRecords": len(records)}


def command_set_state(
    package: Path,
    identifier: str,
    target: str,
    expect: str,
    revision: str | None,
    environment: str | None,
    disposition: str | None,
    successor: str | None,
    evidence: str | None,
    revalidation_plan: str | None,
    claims: list[str] | None = None,
    invalidated_by: str | None = None,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if identifier not in state["tickets"] or target not in TICKET_STATES:
        raise StateError(f"unknown Ticket or invalid state: {identifier}/{target}")
    current = state["tickets"][identifier]["state"]
    if current != expect:
        raise StateError(f"stale ticket transition for {identifier}: expected {expect}, found {current}")
    repo = _repo_root(package)
    selected_claims = list(dict.fromkeys(claims or []))
    if target != "NEEDS-REVALIDATION" and (selected_claims or invalidated_by is not None):
        raise StateError("--claim and --invalidated-by are only valid for NEEDS-REVALIDATION")

    if current == "RETIRED":
        if target != "RETIRED":
            raise StateError(f"RETIRED Ticket {identifier} is terminal; create a patch Attempt to continue")
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("repeating RETIRED requires the original --disposition and --evidence")
        normalized_retired = _repo_relative(repo, evidence, "retired evidence")
        existing = state["tickets"][identifier]
        if (
            disposition != existing.get("disposition")
            or normalized_retired != existing.get("evidence")
            or successor != existing.get("successor")
        ):
            raise StateError(f"RETIRED Ticket {identifier} is terminal; only an identical retry is idempotent")
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    if current == target and target != "NEEDS-REVALIDATION":
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    invalidated_count = 0
    if target == "NEEDS-REVALIDATION":
        if not selected_claims:
            raise StateError("NEEDS-REVALIDATION requires at least one --claim")
        if not isinstance(invalidated_by, str) or not invalidated_by.strip():
            raise StateError("NEEDS-REVALIDATION requires a non-empty --invalidated-by")
        unknown = set(selected_claims) - summary["_claims"][identifier]
        if unknown:
            raise StateError(f"unknown Ticket claim for revalidation: {identifier}/{', '.join(sorted(unknown))}")
        records_by_claim = state["evidenceIndex"].get(identifier, {})
        for claim in selected_claims:
            for record in records_by_claim.get(claim, []):
                previous = record.get("invalidatedBy")
                if previous is None:
                    record["invalidatedBy"] = invalidated_by.strip()
                    invalidated_count += 1
                elif previous != invalidated_by.strip():
                    raise StateError(f"evidence {identifier}/{claim} is already invalidated by {previous}")
        if current == target and invalidated_count == 0:
            return {
                "kind": "ticket",
                "id": identifier,
                "state": target,
                "idempotent": True,
                "claims": selected_claims,
                "invalidatedEvidence": 0,
            }

    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"} and not revalidation_plan:
        raise StateError("returning to PENDING requires --revalidation-plan")
    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"}:
        _repo_relative(repo, revalidation_plan, "revalidation plan")
    if target == "SATISFIED":
        if not revision or not environment:
            raise StateError("SATISFIED requires --revision and --environment")
        revision = _validate_commit(repo, revision)
        missing, conflicts = _evidence_coverage(summary, identifier, revision, environment)
        if missing:
            raise StateError(f"SATISFIED missing claims: {', '.join(missing)}")
        if conflicts:
            raise StateError(f"SATISFIED has contradictory evidence: {', '.join(conflicts)}")
        if any(not _ticket_released(state["tickets"], dep) for kind, dep in summary["_ticketDependencies"][identifier] if kind in {"implementation", "acceptance"}):
            raise StateError("Ticket implementation or acceptance dependencies are not released")
    if target == "BLOCKED" and not evidence:
        raise StateError("BLOCKED requires --evidence")
    normalized_evidence = _repo_relative(repo, evidence, "Ticket evidence") if evidence else None
    if target == "RETIRED":
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("RETIRED requires --disposition and --evidence")
        if disposition == "superseded" and not successor:
            raise StateError("superseded RETIRED requires --successor")
        state["tickets"][identifier] = {"state": "RETIRED", "disposition": disposition, "evidence": _repo_relative(repo, evidence, "retired evidence")}
        if successor:
            state["tickets"][identifier]["successor"] = successor
    if target != "RETIRED":
        state["tickets"][identifier] = {"state": target}
        if normalized_evidence and target in {"BLOCKED", "NEEDS-REVALIDATION"}:
            state["tickets"][identifier]["evidence"] = normalized_evidence
        if target == "SATISFIED":
            state["tickets"][identifier] = {"state": target, "acceptance": {"revision": revision, "environment": environment}}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    result = {"kind": "ticket", "id": identifier, "state": target, "idempotent": False}
    if target == "NEEDS-REVALIDATION":
        result.update({"claims": selected_claims, "invalidatedEvidence": invalidated_count})
    if target in {"SATISFIED", "RETIRED"}:
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": f"ticket:{identifier}",
                "kind": "result",
                "transition": "ticket-state",
                "from": current,
                "to": target,
                "outcome": target,
            },
        )
    return result


def _add_judgment(package: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if payload.get("purpose") != "judgment":
        raise StateError("3.5 er-add accepts judgment only; use checkpoint command")
    subject = payload.get("subject", "attempt")
    if subject != "attempt" and (not isinstance(subject, str) or not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid judgment subject: {subject}")
    title, content = payload.get("title"), payload.get("content")
    if not isinstance(title, str) or not title.strip() or "\n" in title or not isinstance(content, str) or not content.strip():
        raise StateError("judgment requires one-line title and non-empty content")
    evidence = payload.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        raise StateError("judgment evidence must be a path or list")
    repo = _repo_root(package)
    normalized = [_repo_relative(repo, item, "judgment evidence") for item in evidence]
    path = _ensure_execution_record(package, summary["attempt"])
    _, entries = _parse_execution_record(path, summary["attempt"])
    same = next((row for row in entries if row["purpose"] == "judgment" and row["subject"] == subject and row["title"] == title.strip() and row["content"] == content.strip() and row["evidence"] == normalized), None)
    if same:
        return {"recordId": same["id"], "attempt": summary["attempt"], "idempotent": True}
    number = max((row["number"] for row in entries), default=0) + 1
    record_id = f"{summary['attempt']}-ER-{number:03d}"
    evidence_text = "\n".join(f"- {item}" for item in normalized) or "- none"
    block = f"\n## {record_id} · judgment\n\n- Subject: {subject}\n- Title: {title.strip()}\n- Next action: none\n\n### Evidence\n\n{evidence_text}\n\n### Content\n\n{content.strip()}\n"
    _write_text(path, _read(path).rstrip() + block)
    _refresh_projections(package, state)
    return {"recordId": record_id, "attempt": summary["attempt"], "idempotent": False}


def command_er_add(package: Path, input_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"er-add input is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateError("er-add input must be an object")
    return _add_judgment(package, payload)


def _trail_text_field(event: dict[str, Any], field: str, kind: str) -> None:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"trail {kind} requires a non-empty {field}")


def _validate_dispatch_situation_digest(package: Path, attempt: str, event: dict[str, Any]) -> None:
    credential_path = package / EXECUTION_PATH / attempt / SITUATION_DIGEST_NAME
    if not credential_path.is_file():
        raise StateError(f"{DISPATCH_DIGEST_GUIDANCE}；未找到 {SITUATION_DIGEST_NAME} 凭据文件")
    try:
        credential = _load_json(credential_path)
    except StateError as exc:
        raise StateError(f"{DISPATCH_DIGEST_GUIDANCE}；未找到 {SITUATION_DIGEST_NAME} 凭据文件") from exc
    if credential.get("digest") != event["situation_digest"]:
        raise StateError(f"{DISPATCH_DIGEST_GUIDANCE}；digest 不匹配，凭据是 {credential.get('digest')}")
    try:
        state_sha256 = hashlib.sha256((package / STATE_PATH).read_bytes()).hexdigest()
    except OSError as exc:
        raise StateError(f"{DISPATCH_DIGEST_GUIDANCE}；无法读取当前 state.json：{exc}") from exc
    if credential.get("state_sha256") != state_sha256:
        raise StateError(
            f"{DISPATCH_DIGEST_GUIDANCE}；处境已变，凭据渲染于 {credential.get('ts')} 之后 state.json 已更新"
        )


def _validate_review_dispatch_fields(event: dict[str, Any]) -> None:
    has_phase = "review_phase" in event
    has_track = "review_track" in event
    phase_values = " | ".join(REVIEW_PHASE_VALUES)
    track_values = " | ".join(REVIEW_TRACK_VALUES)
    if has_phase != has_track:
        raise StateError(
            "review_phase 与 review_track 必须同时出现；"
            f"review_phase 合法值：{phase_values}；review_track 合法值：{track_values}"
        )
    if has_phase:
        phase = event["review_phase"]
        if not isinstance(phase, str) or phase not in REVIEW_PHASES:
            raise StateError(f"review_phase 合法值：{phase_values}；收到 {phase!r}")
        track = event["review_track"]
        if not isinstance(track, str) or track not in REVIEW_TRACKS:
            raise StateError(f"review_track 合法值：{track_values}；收到 {track!r}")
    if "review_recheck" in event and type(event["review_recheck"]) is not bool:
        raise StateError("review_recheck 必须是 boolean")


def _merge_trail_named_fields(event: dict[str, Any], named_fields: dict[str, Any]) -> dict[str, Any]:
    for field, value in named_fields.items():
        if value is None:
            continue
        if field in event:
            same = type(event[field]) is type(value) and event[field] == value
            if not same:
                option = f"--{field.replace('_', '-')}"
                raise StateError(f"trail append {option} conflicts with stdin {field}")
        else:
            event[field] = value
    return event


def _validate_trail_event(event: dict[str, Any]) -> dict[str, Any]:
    supplied_common = sorted(TRAIL_COMMON_FIELDS & event.keys())
    if supplied_common:
        fields = ", ".join(supplied_common)
        raise StateError(f"trail append fills {fields}; omit them from stdin JSON")
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in TRAIL_APPEND_KINDS:
        supported = ", ".join(sorted(TRAIL_APPEND_KINDS))
        raise StateError(f"invalid trail kind {kind!r}; trail append supports: {supported}")
    _trail_text_field(event, "subject", kind)
    if kind == "fact":
        key = event.get("key")
        if not isinstance(key, str) or not key.strip():
            raise StateError("trail fact requires a non-empty key")
        if key not in FACT_KEYS:
            raise StateError(f"trail append rejected fact key {key!r}：{describe_unknown_fact_keys((key,))}")
        if "value" not in event:
            raise StateError("trail fact requires value")
    elif kind == "escape":
        _trail_text_field(event, "deviation", kind)
        _trail_text_field(event, "reason", kind)
    elif kind == "dispatch":
        _trail_text_field(event, "worker", kind)
        if event.get("outcome") != "RUNNING" or event.get("returned") is not False:
            raise StateError("trail dispatch requires outcome=RUNNING and returned=false")
        _validate_review_dispatch_fields(event)
        if "situation_digest" not in event:
            raise StateError(f"{DISPATCH_DIGEST_GUIDANCE}；事件缺少 situation_digest")
        if (
            not isinstance(event["situation_digest"], str)
            or TRAIL_DIGEST_RE.fullmatch(event["situation_digest"]) is None
        ):
            raise StateError("trail dispatch situation_digest must be a 12-character hex digest")
    else:
        _trail_text_field(event, "outcome", kind)
    return event


def command_trail_append(
    package: Path,
    input_text: str,
    named_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        event = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"trail append input is invalid JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise StateError("trail append input must be an object")
    if named_fields:
        event = _merge_trail_named_fields(event, named_fields)
    event = _validate_trail_event(event)
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if event["kind"] == "dispatch":
        _validate_dispatch_situation_digest(package, summary["attempt"], event)
    appended = _append_trail(package, summary["attempt"], event)
    return {
        "attempt": summary["attempt"],
        "kind": event["kind"],
        "path": f"execution/{summary['attempt']}/{ACTIVE_TRAIL_NAME}",
        "appended": appended,
    }


def command_checkpoint(
    package: Path,
    subject: str,
    next_action: str,
    blocker: str | None,
    evidence: list[str],
    handoff: bool = False,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if subject != "attempt" and (not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid checkpoint subject: {subject}")
    repo = _repo_root(package)
    state["activeCheckpoints"][subject] = {"next": next_action.strip(), "blocker": blocker.strip() if blocker else None, "evidence": [_repo_relative(repo, item, "checkpoint evidence") for item in evidence]}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    _best_effort_trail(
        package,
        summary["attempt"],
        {
            "subject": subject,
            "kind": "checkpoint",
            "checkpoint": True,
            **state["activeCheckpoints"][subject],
        },
    )
    if handoff:
        _best_effort_trail_rotation(package, summary["attempt"])
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": subject,
                "kind": "handoff",
                "checkpoint": True,
                **state["activeCheckpoints"][subject],
            },
        )
    return {"subject": subject, "checkpoint": state["activeCheckpoints"][subject], "idempotent": False}


def _update_history(state: dict[str, Any], attempt: str, lifecycle: str, gate: dict[str, Any] | None) -> None:
    for row in state["attemptHistory"]:
        if row["id"] == attempt:
            row["lifecycle"] = lifecycle
            row["gate"] = gate
            return


def command_gate(package: Path, verdict: str, commit: str, reason: str, evidence: list[str], durable: list[str], no_durable_reason: str | None, environment: str | None) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    repo = _repo_root(package)
    resolved = _validate_commit(repo, commit)
    lifecycle: Lifecycle = summary["_lifecycle"]
    if lifecycle.frozen:
        if lifecycle.gate and lifecycle.gate["verdict"] == verdict and lifecycle.gate["commit"] == resolved:
            _write_attempt_archive(package, summary["attempt"], state["tickets"])
            return {"formatVersion": FORMAT_VERSION, "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": True}
        raise StateError(f"Attempt {summary['attempt']} is already frozen by terminal Gate {lifecycle.gate_verdict}")
    if verdict in TERMINAL_VERDICTS and resolved != _run_git(repo, "rev-parse", "HEAD"):
        raise StateError("terminal Gate comparison commit must equal current HEAD")
    if verdict in TERMINAL_VERDICTS and not durable and not (no_durable_reason and no_durable_reason.strip()):
        raise StateError("terminal Gate requires --durable-delta or --no-durable-delta-reason")
    if verdict == "pass":
        unfinished = [key for key in state["tickets"] if not _ticket_released(state["tickets"], key)]
        if unfinished:
            raise StateError(f"pass Gate has unfinished Tickets: {', '.join(unfinished)}")
        for ticket, edges in summary["_ticketDependencies"].items():
            if any(kind == "release" and not _ticket_released(state["tickets"], dep) for kind, dep in edges):
                raise StateError(f"pass Gate has unreleased release dependency for {ticket}")
        for ticket, row in state["tickets"].items():
            if row["state"] != "SATISFIED":
                continue
            acceptance = row["acceptance"]
            acceptance_revision = _validate_commit(repo, acceptance["revision"])
            missing, conflicts = _evidence_coverage(summary, ticket, acceptance_revision, acceptance["environment"])
            if missing or conflicts or acceptance_revision != resolved:
                raise StateError(f"pass Gate evidence is not current for {ticket}")
        live_references = live_package_reference_fact(package)
        if live_references.known and live_references.value is True:
            raise StateError(
                "pass Gate rejected: "
                + (live_references.reason or "package 引用了活体 package")
                + "；先将每条引用通过 /impl-package:backfill-stable-docs 吸收进 stable docs，"
                "再把当前 package 改为引用 stable docs"
            )
    normalized_evidence = [_repo_relative(repo, item, "gate evidence") for item in evidence]
    if verdict in TERMINAL_VERDICTS:
        state["activeCheckpoints"] = {}
    gate = {"verdict": verdict, "commit": resolved, "environment": environment}
    _update_history(state, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", gate)
    lines = ["# Gate\n", f"- Verdict: {verdict}\n", f"- Attempt: {summary['attempt']}\n", f"- Comparison commit: {resolved}\n", f"- Reason: {reason.strip()}\n", "\n## Evidence\n"]
    lines.extend(f"- {item}\n" for item in normalized_evidence) or lines.append("- none\n")
    lines.append("\n## Durable Deltas\n")
    lines.extend(f"- {item}\n" for item in durable) or lines.append(f"- Reason: {no_durable_reason or 'none'}\n")
    _write_text(package / GATE_PATH, "".join(lines))
    _set_execution_record_status(package, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", verdict)
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    if verdict in TERMINAL_VERDICTS:
        _write_attempt_archive(package, summary["attempt"], state["tickets"])
    return {"formatVersion": FORMAT_VERSION, "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": False}
