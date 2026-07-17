#!/usr/bin/env python3
"""Use a real interrupted parent turn as a transient retry, then a fresh success."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from codex_harness_runtime import AttemptLedger, classify_live_result


def invoke(runner: Path, root: Path, scenario: str, timeout: int) -> tuple[int, dict]:
    started_at = time.time()
    completed = subprocess.run([sys.executable, str(runner), "--repository-root", str(root), "--timeout-seconds", str(timeout), "--scenario", scenario], cwd=root, capture_output=True, text=True, check=False)
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        candidates = sorted(
            (path for path in (root / ".codex" / "harness-runs").glob("*.app-server.summary.json") if path.stat().st_mtime >= started_at),
            key=lambda path: path.stat().st_mtime,
        )
        result = json.loads(candidates[-1].read_text(encoding="utf-8")) if candidates else {"status": "failed", "stdout_tail": completed.stdout[-500:], "stderr_tail": completed.stderr[-500:]}
    return completed.returncode, result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()
    runner = root / "scripts" / "run-codex-app-server-pilot.py"
    first_exit, first = invoke(runner, root, "timeout", 10)
    second_exit, second = invoke(runner, root, "simple", 240)
    output_dir = root / ".codex" / "harness-runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-live-retry"
    ledger = AttemptLedger(output_dir / f"{run_id}.ledger.jsonl", run_id)
    first_verdict, first_retry, first_reason = classify_live_result(first)
    second_verdict, second_retry, second_reason = classify_live_result(second)
    lineage = [
        ledger.append("live-1", first.get("run_id", ""), first_verdict, first_retry, first_reason),
        ledger.append("live-2", second.get("run_id", ""), second_verdict, second_retry, second_reason),
    ]
    passed = first_exit == 0 and first.get("status") == "interrupted" and second_exit == 0 and second.get("status") == "passed" and first.get("run_id") != second.get("run_id") and first.get("worktree_changed") is False and second.get("worktree_changed") is False
    passed = passed and lineage[0]["retry"] is True and lineage[1]["retry"] is False and lineage[0]["attempt_id"] != lineage[1]["attempt_id"]
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "lineage": lineage, "ledger": str(ledger.path), "first": first, "second": second}
    (output_dir / f"{summary['run_id']}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
