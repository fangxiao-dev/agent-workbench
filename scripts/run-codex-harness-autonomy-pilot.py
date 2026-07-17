#!/usr/bin/env python3
"""Run the parent-only autonomy comparison across three task shapes."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path


def run_scenario(runner: Path, repository_root: Path, scenario: str, timeout_seconds: int) -> dict:
    started_at = time.time()
    completed = subprocess.run(
        [sys.executable, str(runner), "--repository-root", str(repository_root), "--timeout-seconds", str(timeout_seconds), "--scenario", scenario],
        cwd=repository_root,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        # On Windows the app-server child can finish after stdout is closed while
        # still persisting its canonical summary. Prefer that artifact over a
        # transport wrapper's empty stdout, but retain the parse diagnostics.
        candidates = sorted(
            (path for path in (repository_root / ".codex" / "harness-runs").glob("*.app-server.summary.json") if path.stat().st_mtime >= started_at),
            key=lambda path: path.stat().st_mtime,
        )
        if candidates:
            summary = json.loads(candidates[-1].read_text(encoding="utf-8"))
            summary["stdout_parse_fallback"] = {"error": str(error), "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]}
        else:
            summary = {"status": "failed", "parse_error": str(error), "stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]}
    summary["runner_exit_code"] = completed.returncode
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout-seconds", type=int, default=240)
    args = parser.parse_args()
    repository_root = args.repository_root.resolve()
    runner = repository_root / "scripts" / "run-codex-app-server-pilot.py"
    scenarios = ("simple", "parallel", "ambiguous")
    results = [run_scenario(runner, repository_root, scenario, args.timeout_seconds) for scenario in scenarios]
    normalized = [
        {
            "status": result.get("status"),
            "parent_result_valid": result.get("parent_result_valid"),
            "parent_status": (result.get("parent_result") or {}).get("status"),
            "boundary_violations": (result.get("parent_result") or {}).get("boundary_violations"),
            "worktree_changed": result.get("worktree_changed"),
        }
        for result in results
    ]
    passed = all(item == normalized[0] for item in normalized) and normalized[0] == {
        "status": "passed",
        "parent_result_valid": True,
        "parent_status": "succeeded",
        "boundary_violations": [],
        "worktree_changed": False,
    }
    artifacts = repository_root / ".codex" / "harness-runs"
    artifacts.mkdir(parents=True, exist_ok=True)
    aggregate = {
        "run_id": time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8] + "-autonomy",
        "status": "passed" if passed else "failed",
        "scenarios": scenarios,
        "normalized_verdicts": normalized,
        "child_telemetry_ignored_for_verdict": True,
        "runs": results,
    }
    output = artifacts / f"{aggregate['run_id']}.summary.json"
    output.write_text(json.dumps(aggregate, indent=2), encoding="utf-8")
    print(json.dumps(aggregate, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
