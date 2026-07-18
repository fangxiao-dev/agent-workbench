"""Small runtime-owned seams shared by the exploratory Harness pilots."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any


def digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()


class LeaseConflict(RuntimeError):
    """A continuation is already owned by another live controller."""


class LedgerIntegrityError(RuntimeError):
    """A resource ledger cannot be replayed without losing evidence."""


class ThreadLease:
    """Small runner-owned single-writer lease for one persistent thread."""

    def __init__(self, artifact_root: Path, thread_id: str, run_id: str, ttl_seconds: int = 300) -> None:
        if not thread_id or not run_id or ttl_seconds <= 0:
            raise ValueError("thread_id, run_id and a positive ttl_seconds are required")
        self.artifact_root = artifact_root
        self.thread_id = thread_id
        self.run_id = run_id
        self.ttl_seconds = ttl_seconds
        self.owner_token = uuid.uuid4().hex
        self.path = artifact_root / "leases" / f"{hashlib.sha256(thread_id.encode('utf-8')).hexdigest()}.json"
        self.acquired = False

    @staticmethod
    def _now() -> float:
        return time.time()

    def _payload(self) -> dict[str, Any]:
        now = self._now()
        return {
            "lease_version": "codex-harness.thread-lease.v0",
            "owner_token": self.owner_token,
            "run_id": self.run_id,
            "thread_id": self.thread_id,
            "acquired_at": now,
            "heartbeat_at": now,
            "expires_at": now + self.ttl_seconds,
        }

    def _read(self) -> dict[str, Any]:
        try:
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise LeaseConflict(f"lease file is unreadable: {self.path}") from exc
        required = ("lease_version", "owner_token", "run_id", "thread_id", "acquired_at", "heartbeat_at", "expires_at")
        numeric = ("acquired_at", "heartbeat_at", "expires_at")
        if (
            not isinstance(value, dict)
            or any(not isinstance(value.get(field), str) or not value[field] for field in ("lease_version", "owner_token", "run_id", "thread_id"))
            or value.get("lease_version") != "codex-harness.thread-lease.v0"
            or value.get("thread_id") != self.thread_id
            or any(isinstance(value.get(field), bool) or not isinstance(value.get(field), (int, float)) for field in numeric)
            or any(field not in value for field in required)
        ):
            raise LeaseConflict(f"lease file is malformed: {self.path}")
        return value

    def acquire(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = self._payload()
        for _ in range(2):
            try:
                with self.path.open("x", encoding="utf-8", newline="\n") as stream:
                    json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                self.acquired = True
                return payload
            except FileExistsError:
                current = self._read()
                if float(current["expires_at"]) >= self._now():
                    raise LeaseConflict(f"thread {self.thread_id} is leased by run {current.get('run_id')}")
                # Do not unlink a stale lease after a non-atomic read: a
                # concurrent heartbeat/reclaim could otherwise remove a new
                # owner's lease. Reconciliation is an explicit owner action.
                raise LeaseConflict(f"thread {self.thread_id} has an expired lease; reconcile before reacquiring")
        raise LeaseConflict(f"could not acquire thread lease: {self.path}")

    def heartbeat(self) -> dict[str, Any]:
        if not self.acquired:
            raise LeaseConflict("lease has not been acquired by this controller")
        current = self._read()
        if current.get("owner_token") != self.owner_token:
            raise LeaseConflict("lease owner token does not match")
        current["heartbeat_at"] = self._now()
        current["expires_at"] = current["heartbeat_at"] + self.ttl_seconds
        handle, temporary = tempfile.mkstemp(prefix=f".{self.path.name}.", suffix=".tmp", dir=self.path.parent)
        try:
            with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
                json.dump(current, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        except BaseException:
            try:
                os.unlink(temporary)
            except FileNotFoundError:
                pass
            raise
        return current

    def release(self) -> bool:
        if not self.path.exists():
            self.acquired = False
            return False
        if not self.acquired:
            raise LeaseConflict("lease has not been acquired by this controller")
        current = self._read()
        if current.get("owner_token") != self.owner_token:
            raise LeaseConflict("lease owner token does not match")
        self.path.unlink()
        self.acquired = False
        return True

    @classmethod
    def reconcile(cls, artifact_root: Path, now: float | None = None) -> list[dict[str, Any]]:
        current_time = cls._now() if now is None else now
        candidates: list[dict[str, Any]] = []
        lease_root = artifact_root / "leases"
        if not lease_root.is_dir():
            return candidates
        for path in sorted(lease_root.glob("*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError):
                candidates.append({"path": str(path), "reason": "unreadable"})
                continue
            if not isinstance(value, dict) or not isinstance(value.get("expires_at"), (int, float)):
                candidates.append({"path": str(path), "reason": "malformed"})
            elif float(value["expires_at"]) < current_time:
                candidates.append({"path": str(path), "reason": "expired", "lease": value})
        return candidates


class ResourceLedger:
    """Append-only, hash-chained lifecycle evidence for runner-owned resources."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.events: list[dict[str, Any]] = []
        if path.exists():
            try:
                self.events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise LedgerIntegrityError(f"resource ledger cannot be decoded: {path}") from exc
            self.verify()

    def verify(self) -> bool:
        if self.path.exists():
            try:
                self.events = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise LedgerIntegrityError(f"resource ledger cannot be decoded: {self.path}") from exc
        elif self.events:
            raise LedgerIntegrityError(f"resource ledger disappeared: {self.path}")
        previous: str | None = None
        event_ids: set[str] = set()
        for index, event in enumerate(self.events):
            if not isinstance(event, dict) or not isinstance(event.get("event_id"), str) or not event["event_id"] or event["event_id"] in event_ids:
                raise LedgerIntegrityError(f"resource ledger event identity is invalid at index {index}")
            if event.get("run_id") != self.run_id or event.get("prev_hash") != previous:
                raise LedgerIntegrityError(f"resource ledger chain predecessor is invalid at index {index}")
            content_hash = event.get("content_hash")
            payload = {key: value for key, value in event.items() if key != "content_hash"}
            if not isinstance(content_hash, str) or digest(payload) != content_hash:
                raise LedgerIntegrityError(f"resource ledger content hash is invalid at index {index}")
            event_ids.add(event["event_id"])
            previous = content_hash
        return True

    def append(self, resource_type: str, resource_id: str, operation: str, evidence: str, **fields: Any) -> dict[str, Any]:
        if not all(isinstance(value, str) and value for value in (resource_type, resource_id, operation, evidence)):
            raise ValueError("resource_type, resource_id, operation and evidence are required")
        self.verify()
        if operation != "terminal_disposition" and any(event.get("operation") == "terminal_disposition" for event in self.events):
            raise LedgerIntegrityError("resource ledger is terminal; append requires a new run")
        event: dict[str, Any] = {
            "event_id": uuid.uuid4().hex,
            "run_id": self.run_id,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "operation": operation,
            "observed_at": time.time(),
            "prev_hash": self.events[-1]["content_hash"] if self.events else None,
            "evidence": evidence,
        }
        event.update(fields)
        event["content_hash"] = digest(event)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8", newline="\n") as stream:
            stream.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.events.append(event)
        return event

    def terminal_disposition(self, disposition: str, evidence: str) -> dict[str, Any]:
        if disposition not in {"promote", "retry", "discard", "needs_owner"}:
            raise ValueError(f"unsupported terminal disposition: {disposition}")
        self.verify()
        existing = [event for event in self.events if event.get("operation") == "terminal_disposition"]
        if existing:
            current = existing[-1]
            if current.get("disposition") == disposition and current.get("evidence") == evidence:
                return current
            raise LedgerIntegrityError("terminal disposition is already fixed")
        return self.append("run", self.run_id, "terminal_disposition", evidence, disposition=disposition)


def route_decision(policy_bundle: dict[str, Any], category: str, request_id: str | None = None, detail: str = "") -> dict[str, Any]:
    from codex_harness_policy import decision_audience

    audience = decision_audience(policy_bundle, category)
    return {
        "request_id": request_id or uuid.uuid4().hex,
        "category": category,
        "audience": audience,
        "detail": detail,
        "retryable": audience == "harness",
    }


class AttemptLedger:
    """Append-only attempt evidence with immutable record identity."""

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.records: list[dict[str, Any]] = []
        if self.path.exists():
            self.records = [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def append(self, attempt_id: str, source_run_id: str, verdict: str, retry: bool, reason: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        record = {
            "run_id": self.run_id,
            "attempt_id": attempt_id,
            "source_run_id": source_run_id,
            "verdict": verdict,
            "retry": retry,
            "reason": reason,
        }
        if extra:
            record.update(extra)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record, sort_keys=True) + "\n")
        self.records.append(record)
        return record

    def verify_append_only(self, before: list[dict[str, Any]]) -> bool:
        return self.records[: len(before)] == before and len(self.records) >= len(before)


def classify_live_result(summary: dict[str, Any]) -> tuple[str, bool, str]:
    if summary.get("status") == "interrupted":
        return "retryable", True, "turn interrupted within deadline"
    if summary.get("status") == "passed":
        return "succeeded", False, "external validator passed"
    return "failed", False, "non-transient or untrusted result"
