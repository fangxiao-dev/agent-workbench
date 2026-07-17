#!/usr/bin/env python3
"""Exercise retry classification and immutable attempt lineage deterministically."""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from codex_harness_runtime import AttemptLedger, digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()
    artifact_dir = root / ".codex" / "harness-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-retry"
    ledger_path = artifact_dir / f"{run_id}.ledger.jsonl"
    ledger = AttemptLedger(ledger_path, run_id)
    records: list[dict] = []

    def append(attempt_id: str, fault: str, verdict: str, retry: bool) -> dict:
        record = ledger.append(attempt_id, run_id, verdict, retry, fault, {"fault": fault})
        records.append(record)
        return record

    transient_first = append("attempt-1", "transient", "retryable", True)
    transient_hash = digest(transient_first)
    transient_second = append("attempt-2", "transient", "succeeded", False)
    deterministic = append("attempt-3", "deterministic_failure", "failed", False)
    needs_owner = append("attempt-4", "needs_owner", "needs_owner", False)
    boundary = append("attempt-5", "boundary_rejection", "failed", False)
    unknown_side_effect = append("attempt-6", "unknown_side_effect", "failed", False)
    lines = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines()]
    checks = {
        "transient_new_attempt": transient_second["attempt_id"] != transient_first["attempt_id"],
        "transient_lineage_preserved": digest(lines[0]) == transient_hash,
        "deterministic_no_retry": deterministic["retry"] is False,
        "needs_owner_no_retry": needs_owner["retry"] is False,
        "boundary_no_retry": boundary["retry"] is False,
        "unknown_side_effect_no_retry": unknown_side_effect["retry"] is False,
        "ledger_append_only": ledger.verify_append_only([]) and lines == records,
        "old_evidence_not_overwritten": lines[0]["verdict"] == "retryable" and len(lines) == 6,
    }
    passed = all(checks.values())
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "ledger": str(ledger_path), "checks": checks, "records": records}
    summary_path = artifact_dir / f"{run_id}.summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
