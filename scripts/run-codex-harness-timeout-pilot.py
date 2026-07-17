#!/usr/bin/env python3
"""Verify bounded turn interrupt followed by a fresh successful run."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def invoke(runner: Path, root: Path, scenario: str, timeout_seconds: int) -> tuple[int, dict]:
    completed = subprocess.run(
        [sys.executable, str(runner), "--repository-root", str(root), "--timeout-seconds", str(timeout_seconds), "--scenario", scenario],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    try:
        summary = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        summary = {"status": "failed", "parse_error": str(error), "stdout_tail": completed.stdout[-500:], "stderr_tail": completed.stderr[-500:]}
    return completed.returncode, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()
    runner = root / "scripts" / "run-codex-app-server-pilot.py"
    interrupt_exit, interrupted = invoke(runner, root, "timeout", 10)
    fresh_exit, fresh = invoke(runner, root, "simple", 240)
    terminal = interrupted.get("terminal_event", {}).get("params", {}).get("turn", {})
    passed = (
        interrupt_exit == 0
        and interrupted.get("status") == "interrupted"
        and interrupted.get("interrupted") is True
        and terminal.get("status") == "interrupted"
        and interrupted.get("interrupt_error") is None
        and interrupted.get("worktree_changed") is False
        and fresh_exit == 0
        and fresh.get("status") == "passed"
        and fresh.get("parent_result_valid") is True
        and fresh.get("worktree_changed") is False
    )
    run_id = interrupted.get("run_id", "timeout-pilot") + "-aggregate"
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "interrupt_run": interrupted, "fresh_run": fresh}
    output = root / ".codex" / "harness-runs" / f"{run_id}.summary.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
