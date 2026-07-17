#!/usr/bin/env python3
"""Run the read-only parent pilot repeatedly and check process cleanup."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path


def process_snapshot() -> list[str]:
    completed = subprocess.run(["tasklist", "/FO", "CSV", "/NH"], capture_output=True, text=True, check=False)
    return [line for line in completed.stdout.splitlines() if "codex" in line.lower()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--rounds", type=int, default=20)
    args = parser.parse_args()
    root = args.repository_root.resolve()
    runner = root / "scripts" / "run-codex-app-server-pilot.py"
    before = process_snapshot()
    runs: list[dict] = []
    scenarios = ("simple", "parallel", "ambiguous", "timeout")
    for index in range(1, args.rounds + 1):
        scenario = scenarios[(index - 1) % len(scenarios)]
        deadline = "10" if scenario == "timeout" else "240"
        started_at = time.time()
        completed = subprocess.run([sys.executable, str(runner), "--repository-root", str(root), "--timeout-seconds", deadline, "--scenario", scenario], cwd=root, capture_output=True, text=True, check=False)
        try:
            summary = json.loads(completed.stdout)
        except json.JSONDecodeError as error:
            candidates = sorted(
                (path for path in (root / ".codex" / "harness-runs").glob("*.app-server.summary.json") if path.stat().st_mtime >= started_at),
                key=lambda path: path.stat().st_mtime,
            )
            if candidates:
                summary = json.loads(candidates[-1].read_text(encoding="utf-8"))
                summary["stdout_parse_fallback"] = {"error": str(error), "stdout_tail": completed.stdout[-500:], "stderr_tail": completed.stderr[-500:]}
            else:
                summary = {"status": "failed", "parse_error": str(error), "stdout_tail": completed.stdout[-500:], "stderr_tail": completed.stderr[-500:]}
        summary["round"] = index
        summary["soak_scenario"] = scenario
        summary["runner_exit_code"] = completed.returncode
        runs.append(summary)
        if completed.returncode != 0:
            break
    time.sleep(5)
    after = process_snapshot()
    def run_ok(run: dict) -> bool:
        if run.get("soak_scenario") == "timeout":
            return run.get("status") == "interrupted" and run.get("interrupted") is True and (run.get("terminal_event") or {}).get("params", {}).get("turn", {}).get("status") == "interrupted" and run.get("worktree_changed") is False
        return run.get("status") == "passed" and run.get("parent_result_valid") is True and run.get("worktree_changed") is False

    passed = len(runs) == args.rounds and all(run_ok(run) for run in runs) and len(after) <= len(before)
    artifact_dir = root / ".codex" / "harness-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-soak"
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "requested_rounds": args.rounds, "completed_rounds": len(runs), "scenarios": scenarios, "process_count_before": len(before), "process_count_after": len(after), "process_snapshot_before": before, "process_snapshot_after": after, "runs": runs}
    (artifact_dir / f"{run_id}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
