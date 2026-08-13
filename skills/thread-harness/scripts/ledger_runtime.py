#!/usr/bin/env python3
"""Runtime storage and append-only ledger primitives for thread-harness."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import time


# ``done`` is retained in the readable set for legacy rows, but is no longer a
# writable state for ``report``.  Keep the compatibility alias because the
# projection readers (and older callers importing ``STATE_VALUES``) still need
# to understand historical rows.
REPORT_STATE_VALUES = {"working", "awaiting_seam", "awaiting_owner", "ready_for_assignment"}
HISTORICAL_STATE_VALUES = {"done"}
READABLE_STATE_VALUES = REPORT_STATE_VALUES | HISTORICAL_STATE_VALUES
STATE_VALUES = READABLE_STATE_VALUES
STALL_LIMIT = 5
HEARTBEAT_LEAD_ROUNDS = 2
KNOWN_WORKING_STATUSES = {
    "idle",
    "notloaded",
    "not_loaded",
    "inactive",
    "running",
    "inprogress",
    "in_progress",
    "queued",
    "pending",
    "actionable",
    "actionablestatus",
    "turncompleted",
}
SEAM_STATUS_VALUES = {"assigned", "delivered"}
SESSIONS_ROOT_ENV = "THREAD_HARNESS_SESSIONS_ROOT"
BROKER_ROOT_ENV = "THREAD_HARNESS_BROKER_ROOT"
PREFLIGHT_CHILD_LIMIT = 8
PREFLIGHT_RUNTIME_FILES = ("progress.jsonl", "seams.jsonl", "decisions.jsonl", "acts.jsonl")
IDLE_STATUS_VALUES = {"idle", "inactive", "notloaded", "not_loaded"}
LEDGER_FILES = PREFLIGHT_RUNTIME_FILES
LEDGER_INTEGRITY_FAILED = 6
NON_RUNNABLE_STATES = {"awaiting_seam", "awaiting_owner", "ready_for_assignment", "done"}
REASSIGNMENT_STATES = {"ready_for_assignment", "done"}
INTEGRITY_GUARDED_COMMANDS = {
    "sync", "stall-check", "report", "seam", "decide", "act", "retire", "heartbeat", "status", "preflight"
}

SYNC_STATE_COUNTER_FIELDS = (
    "offset",
    "next_poll_seq",
    "next_act_seq",
    "next_ledger_seq",
    "dispatches_since_progress",
    "docs_only_advances",
    "invalid_rounds",
)
SYNC_STATE_REQUIRED_FIELDS = {
    "rollout_path",
    "offset",
    "compaction_observers",
    "budget_states",
    "next_poll_seq",
    "next_act_seq",
    "next_ledger_seq",
    "dispatches_since_progress",
    "docs_only_advances",
    "last_must_act_seq",
    "invalid_rounds",
    "stall_reset_seq",
}

PROGRESS_ROOT = Path(__file__).resolve().parents[3] / ".progress-record"
ACTIVE_REGISTRY_PATH: Path | None = None


def broker_dir() -> Path:
    """Return the runtime root used when no explicit registry is selected."""
    override = os.environ.get(BROKER_ROOT_ENV)
    return Path(override) if override else PROGRESS_ROOT


class LedgerError(Exception):
    pass


class UsageError(Exception):
    pass


class LedgerIntegrityError(LedgerError):
    def __init__(self, issues: list[tuple[str, int, str]]):
        self.issues = issues
        super().__init__("ledger integrity failed")


def valid_ledger_seq(value) -> bool:
    return type(value) is int and value >= 1

def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")

def to_local_iso(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat(timespec="seconds")
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return value

def parse_iso_ts(value) -> datetime | None:
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None

def ts_not_earlier(candidate, baseline) -> bool:
    candidate_dt = parse_iso_ts(candidate)
    baseline_dt = parse_iso_ts(baseline)
    if candidate_dt and baseline_dt:
        if candidate_dt.tzinfo and baseline_dt.tzinfo:
            return candidate_dt.astimezone(timezone.utc) >= baseline_dt.astimezone(timezone.utc)
        if not candidate_dt.tzinfo and not baseline_dt.tzinfo:
            return candidate_dt >= baseline_dt
        return False
    if isinstance(candidate, str) and isinstance(baseline, str):
        return candidate >= baseline
    return False

def runtime_dir(coordination_id: str) -> Path:
    return registry_path(coordination_id).parent / coordination_id

def registry_path(coordination_id: str) -> Path:
    if ACTIVE_REGISTRY_PATH is not None:
        return ACTIVE_REGISTRY_PATH
    return broker_dir() / f"{coordination_id}.json"

def jsonl_path(coordination_id: str, name: str) -> Path:
    return runtime_dir(coordination_id) / name

def ensure_runtime(coordination_id: str) -> Path:
    root = runtime_dir(coordination_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in LEDGER_FILES:
        jsonl_path(coordination_id, name).touch(exist_ok=True)
    return root

def append_jsonl(path: Path, row: dict) -> None:
    """Append one complete JSONL row and make it durable.

    Coordination serialization is provided by ``coordination_write_lock``.  This
    lower-level helper deliberately only owns the bytes/write/fsync contract so
    multi-file commands can keep all appends inside one lock.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
    fd = os.open(str(path), os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o666)
    try:
        offset = 0
        while offset < len(data):
            written = os.write(fd, data[offset:])
            if written <= 0:
                raise LedgerError(f"partial ledger write: {path.name}")
            offset += written
        os.fsync(fd)
    finally:
        os.close(fd)

@contextmanager
def coordination_write_lock(coordination_id: str):
    """Serialize all ledger mutations for one coordination across processes."""
    root = runtime_dir(coordination_id)
    root.mkdir(parents=True, exist_ok=True)
    lock_path = root / ".ledger.write.lock"
    with lock_path.open("a+b") as lock_file:
        if lock_file.seek(0, os.SEEK_END) == 0:
            lock_file.write(b"\0")
            lock_file.flush()
        lock_file.seek(0)
        if os.name == "nt":
            import msvcrt

            while True:
                try:
                    msvcrt.locking(lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    time.sleep(0.01)
                    lock_file.seek(0)
            try:
                yield
            finally:
                lock_file.seek(0)
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)

def scan_jsonl(path: Path) -> tuple[list[dict], list[tuple[str, int, str]]]:
    rows = []
    issues = []
    if not path.exists():
        return rows, issues
    try:
        with path.open("rb") as fh:
            for line_no, raw in enumerate(fh, 1):
                if not raw.endswith(b"\n"):
                    issues.append((path.name, line_no, "truncated_line"))
                try:
                    line = raw.decode("utf-8").strip()
                except UnicodeDecodeError:
                    issues.append((path.name, line_no, "invalid_utf8"))
                    continue
                if not line:
                    issues.append((path.name, line_no, "empty_line"))
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    issues.append((path.name, line_no, "invalid_json"))
                    continue
                if not isinstance(value, dict):
                    issues.append((path.name, line_no, "row_not_object"))
                    continue
                if "ledger_seq" in value and not valid_ledger_seq(value.get("ledger_seq")):
                    issues.append((path.name, line_no, "invalid_ledger_seq"))
                if raw.endswith(b"\n"):
                    rows.append(value)
    except OSError as exc:
        issues.append((path.name, 0, f"unreadable:{exc.__class__.__name__}"))
    return rows, issues

def ledger_integrity_issues(coordination_id: str) -> list[tuple[str, int, str]]:
    issues = []
    for name in LEDGER_FILES:
        _, file_issues = scan_jsonl(jsonl_path(coordination_id, name))
        issues.extend(file_issues)
    return issues

def print_integrity_failure(issues: list[tuple[str, int, str]]) -> None:
    for index, (name, line_no, reason) in enumerate(issues):
        prefix = "LEDGER INTEGRITY FAILED" if index == 0 else "  also"
        location = f"{name}:{line_no}" if line_no else name
        print(f"{prefix}: {location} {reason}")

def assert_ledger_integrity(coordination_id: str) -> None:
    issues = ledger_integrity_issues(coordination_id)
    if issues:
        raise LedgerIntegrityError(issues)

def read_jsonl_with_corrupt(path: Path) -> tuple[list[dict], int]:
    rows, issues = scan_jsonl(path)
    return rows, len(issues)

def read_jsonl(path: Path) -> list[dict]:
    return read_jsonl_with_corrupt(path)[0]

def corrupt_ledger_lines(coordination_id: str) -> int:
    return len(ledger_integrity_issues(coordination_id))

def _new_state() -> dict:
    return {
        "rollout_path": None,
        "offset": 0,
        "compaction_observers": {},
        "budget_states": {},
        "next_poll_seq": 0,
        "next_act_seq": 0,
        "next_ledger_seq": 0,
        "dispatches_since_progress": 0,
        "docs_only_advances": 0,
        "last_must_act_seq": None,
        "invalid_rounds": 0,
        "stall_reset_seq": None,
    }

def _invalid_state(path: Path, detail: str):
    raise LedgerError(
        f"sync-state invalid: {path}: {detail}; "
        "restore a valid sync-state.json before rerunning the broker"
    )

def _validate_state(state, path: Path) -> dict:
    if not isinstance(state, dict):
        _invalid_state(path, "root must be an object")
    missing = sorted(SYNC_STATE_REQUIRED_FIELDS - set(state))
    if missing:
        _invalid_state(path, f"missing required fields: {', '.join(missing)}")
    for field_name in SYNC_STATE_COUNTER_FIELDS:
        value = state.get(field_name)
        if type(value) is not int or value < 0:
            _invalid_state(path, f"{field_name} must be a non-negative integer")
    if state.get("rollout_path") is not None and not isinstance(state.get("rollout_path"), str):
        _invalid_state(path, "rollout_path must be a string or null")
    if not isinstance(state.get("compaction_observers"), dict):
        _invalid_state(path, "compaction_observers must be an object")
    budget_states = state.get("budget_states")
    if not isinstance(budget_states, dict):
        _invalid_state(path, "budget_states must be an object")
    for session_id, budget in budget_states.items():
        if not isinstance(budget, dict) or budget.get("stage") not in {"tracking", "handoff_due"}:
            _invalid_state(path, f"budget_states[{session_id!r}].stage is invalid")
    for field_name in ("last_must_act_seq", "stall_reset_seq"):
        value = state.get(field_name)
        if value is not None and (type(value) is not int or value < 0):
            _invalid_state(path, f"{field_name} must be a non-negative integer or null")
    return state

def load_state(coordination_id: str) -> dict:
    path = runtime_dir(coordination_id) / "sync-state.json"
    if not path.exists():
        return _new_state()
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _invalid_state(path, f"invalid JSON ({exc.msg} at line {exc.lineno} column {exc.colno})")
    except (OSError, UnicodeError) as exc:
        _invalid_state(path, f"unreadable ({exc})")
    return _validate_state(state, path)

def save_state(coordination_id: str, state: dict) -> None:
    path = runtime_dir(coordination_id) / "sync-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    _validate_state(state, path)
    try:
        data = json.dumps(state, ensure_ascii=False, indent=2) + "\n"
    except (TypeError, ValueError) as exc:
        raise LedgerError(f"unable to serialize sync-state {path}: {exc}") from exc

    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=str(path.parent),
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary = Path(stream.name)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(str(temporary), str(path))
        temporary = None
        if os.name != "nt":
            try:
                directory_fd = os.open(str(path.parent), os.O_RDONLY)
                try:
                    os.fsync(directory_fd)
                finally:
                    os.close(directory_fd)
            except OSError:
                pass
    except OSError as exc:
        raise LedgerError(f"unable to durably save sync-state {path}: {exc}") from exc
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass

def next_seq(state: dict, key: str) -> int:
    seq = int(state.get(key) or 0) + 1
    state[key] = seq
    return seq

def next_ledger_seq(coordination_id: str, state: dict) -> int:
    try:
        persisted_seq = int(state.get("next_ledger_seq") or 0)
    except (TypeError, ValueError):
        persisted_seq = 0
    observed_seq = max(
        (
            row.get("ledger_seq")
            for name in LEDGER_FILES
            for row in read_jsonl(jsonl_path(coordination_id, name))
            if valid_ledger_seq(row.get("ledger_seq"))
        ),
        default=0,
    )
    seq = max(persisted_seq, observed_seq) + 1
    state["next_ledger_seq"] = seq
    return seq

def ledger_event_after(candidate: dict, baseline: dict) -> bool:
    """Compare new rows by coordination order, with a legacy timestamp fallback."""
    candidate_seq = candidate.get("ledger_seq")
    baseline_seq = baseline.get("ledger_seq")
    if (
        valid_ledger_seq(candidate_seq)
        and valid_ledger_seq(baseline_seq)
    ):
        return candidate_seq > baseline_seq
    return ts_not_earlier(candidate.get("ts"), baseline.get("ts"))

__all__ = [name for name in globals() if not name.startswith("_")]
