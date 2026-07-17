"""Small runtime-owned seams shared by the exploratory Harness pilots."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def digest(record: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()


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
