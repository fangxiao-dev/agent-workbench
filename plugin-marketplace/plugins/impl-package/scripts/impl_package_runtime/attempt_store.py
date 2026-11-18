"""Attempt archive, trail ledger store, lifecycle/gate lookup and execution-record files."""

from __future__ import annotations

import json
import os
import re
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .state_core import (
    ACTIVE_TRAIL_NAME,
    ATTEMPT_ARCHIVE_PATH,
    ATTEMPT_ID_RE,
    ER_ENTRY_RE,
    EXECUTION_PATH,
    GATE_PATH,
    Lifecycle,
    PUBLICATION_RE,
    RETIRED_DISPATCH_FIELDS,
    StateError,
    TERMINAL_VERDICTS,
    TICKET_STATES,
    TRAIL_ARCHIVE_RE,
    TRAIL_COMMON_FIELDS,
    _load_json,
    _read,
    _repo_root,
    _run_git,
    _validate_commit,
    _write_json,
    _write_text,
)


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


def _best_effort_result(package: Path, attempt: str, event: dict[str, Any]) -> None:
    try:
        event = {"kind": "result", **event}
        if any(row.get("kind") == "result" and _same_event(row, event) for row in _active_trail_rows(package, attempt)):
            return
        _append_trail(package, attempt, event)
    except Exception as exc:  # trail is observational; state remains authoritative
        print(f"warning: state mutation committed but trail append failed (result): {exc}", file=sys.stderr)


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


def _valid_successor(package: Path, successor: Any, identifier: str, attempt: str, ticket_ids: set[str]) -> bool:
    """Successor is a same-Attempt Ticket ID, or `<attempt>/<ticket>` naming another Attempt's Ticket."""
    if not isinstance(successor, str):
        return False
    if "/" not in successor:
        return successor in ticket_ids and successor != identifier
    other, _, ticket = successor.partition("/")
    if other == attempt:
        return ticket in ticket_ids and ticket != identifier
    if ATTEMPT_ID_RE.fullmatch(other) is None or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", ticket) is None:
        return False
    # The other Attempt may not exist yet (successor planned in the next Attempt); only check when its tickets are readable.
    archive = _attempt_archive_path(package, other)
    if archive.is_file():
        try:
            return ticket in _load_json(archive).get("tickets", {})
        except (StateError, AttributeError):
            return False
    return True


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


def _trail_text_field(event: dict[str, Any], field: str, kind: str) -> None:
    value = event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"trail {kind} requires a non-empty {field}")


def _active_trail_rows(package: Path, attempt: str) -> list[dict[str, Any]]:
    path = _trail_path(package, attempt)
    rows: list[dict[str, Any]] = []
    sources = sorted(path.parent.glob("trail.[0-9][0-9][0-9].jsonl")) if path.parent.is_dir() else []
    sources.append(path)
    for source in sources:
        if not source.is_file():
            continue
        for line in source.read_text(encoding="utf-8-sig").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _same_event(existing: dict[str, Any], event: dict[str, Any]) -> bool:
    automatic = TRAIL_COMMON_FIELDS | RETIRED_DISPATCH_FIELDS
    return (
        {key: value for key, value in existing.items() if key not in automatic}
        == {key: value for key, value in event.items() if key not in automatic}
    )
