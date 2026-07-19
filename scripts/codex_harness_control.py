"""Small persisted control requests shared by Codex Crew runners."""

from __future__ import annotations

import json
import os
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any


CANCEL_REQUEST_SCHEMA_VERSION = "codex-crew.cancel-request.v0.1"


class CancelRequestError(RuntimeError):
    """A persisted cancel request cannot be trusted or safely changed."""


def cancel_request_path(state_path: Path) -> Path:
    """Return the sidecar path associated with a canonical state file."""

    path = Path(state_path)
    return path.with_name(f"{path.name}.cancel-request.json")


@contextmanager
def _cancel_request_lock(path: Path, timeout_seconds: float = 5.0):
    """Acquire a process-exit-safe advisory lock for one cancel sidecar."""

    lock_path = path.with_name(f"{path.name}.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    if timeout_seconds < 0:
        raise ValueError("cancel request lock timeout cannot be negative")
    deadline = time.monotonic() + timeout_seconds
    stream = lock_path.open("a+b")
    if stream.seek(0, os.SEEK_END) == 0:
        stream.write(b"\0")
        stream.flush()
        os.fsync(stream.fileno())

    if os.name == "nt":
        import msvcrt

        def acquire() -> None:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)

        def release() -> None:
            stream.seek(0)
            msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
    else:  # pragma: no cover - exercised by non-Windows hosts
        import fcntl

        def acquire() -> None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

        def release() -> None:
            fcntl.flock(stream.fileno(), fcntl.LOCK_UN)

    try:
        while True:
            try:
                acquire()
                break
            except (OSError, PermissionError):
                if time.monotonic() >= deadline:
                    raise CancelRequestError(f"cancel request lock is busy: {lock_path}")
                time.sleep(0.01)
    except BaseException:
        stream.close()
        raise
    try:
        yield
    finally:
        try:
            release()
        finally:
            stream.close()


def _validate_cancel_request(value: Any, path: Path, expected_run_id: str | None = None) -> dict[str, Any]:
    required = {"schema_version", "request_id", "run_id", "reason", "provenance", "requested_at"}
    if not isinstance(value, dict) or set(value) != required:
        raise CancelRequestError(f"cancel request is malformed: {path}")
    if value.get("schema_version") != CANCEL_REQUEST_SCHEMA_VERSION:
        raise CancelRequestError(f"cancel request has an unsupported schema version: {path}")
    if any(not isinstance(value.get(field), str) or not value[field].strip() for field in ("request_id", "run_id", "reason", "provenance")):
        raise CancelRequestError(f"cancel request contains invalid identity or intent fields: {path}")
    requested_at = value.get("requested_at")
    if isinstance(requested_at, bool) or not isinstance(requested_at, (int, float)):
        raise CancelRequestError(f"cancel request contains an invalid requested_at: {path}")
    if expected_run_id is not None and value["run_id"] != expected_run_id:
        raise CancelRequestError(f"cancel request run_id does not match {expected_run_id}: {path}")
    return value


def _read_persisted(path: Path, expected_run_id: str | None = None) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CancelRequestError(f"cancel request cannot be read: {path}") from exc
    return _validate_cancel_request(value, path, expected_run_id)


def _write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def write_cancel_request(state_path: Path, run_id: str, reason: str, provenance: str = "owner", *, lock_timeout_seconds: float = 5.0) -> dict[str, Any]:
    """Persist a cancel request, reusing a valid pending request for the run."""

    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    if not isinstance(reason, str) or not reason.strip():
        raise ValueError("reason is required")
    if not isinstance(provenance, str) or not provenance.strip():
        raise ValueError("provenance is required")
    path = cancel_request_path(state_path)
    with _cancel_request_lock(path, timeout_seconds=lock_timeout_seconds):
        if path.exists():
            return _read_persisted(path, run_id)
        request = {
            "schema_version": CANCEL_REQUEST_SCHEMA_VERSION,
            "request_id": uuid.uuid4().hex,
            "run_id": run_id,
            "reason": reason,
            "provenance": provenance,
            "requested_at": time.time(),
        }
        _write_json_atomic(path, request)
        return request


def read_cancel_request(state_path: Path, run_id: str) -> dict[str, Any] | None:
    """Read a trusted request for the expected run, or return None if absent."""

    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    path = cancel_request_path(state_path)
    if not path.exists():
        return None
    return _read_persisted(path, run_id)


@contextmanager
def cancel_commit_guard(state_path: Path, run_id: str):
    """Linearize a short controller commit boundary against cancel creation.

    The guarded section must stay small: inspect or update controller state, or
    create one worktree.  It must never wrap an Agent turn.  A cancel request
    created before the guard is returned to the caller; a request created after
    the guard is ordered after the guarded commit and will be observed at the
    next role/control boundary.
    """

    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    path = cancel_request_path(state_path)
    with _cancel_request_lock(path):
        pending = _read_persisted(path, run_id) if path.exists() else None
        yield pending


def clear_cancel_request(state_path: Path, request_id: str) -> bool:
    """Remove the sidecar only when its persisted request identity matches."""

    if not isinstance(request_id, str) or not request_id.strip():
        raise ValueError("request_id is required")
    path = cancel_request_path(state_path)
    if not path.exists():
        return False
    current = _read_persisted(path)
    if current["request_id"] != request_id:
        return False
    try:
        path.unlink()
    except FileNotFoundError:
        return False
    return True
