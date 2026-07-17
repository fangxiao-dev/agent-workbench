#!/usr/bin/env python3
"""Trigger the live App Server process-kill fallback, then prove fresh recovery."""

from __future__ import annotations

import argparse
import importlib.util
import json
import time
import tomllib
from pathlib import Path


RUNNER_PATH = Path(__file__).with_name("run-codex-app-server-pilot.py")
SPEC = importlib.util.spec_from_file_location("codex_harness_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()
    with (root / ".codex" / "harness" / "parent.toml").open("rb") as stream:
        profile = tomllib.load(stream)
    artifact_dir = root / ".codex" / "harness-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-live-kill"
    stderr_path = artifact_dir / f"{run_id}.app-server.stderr.log"
    session = RUNNER.JsonRpcSession(RUNNER.app_server_command(), stderr_path)
    killed = False
    try:
        session.request(1, "initialize", {"clientInfo": {"name": "codex-harness-live-kill-pilot", "version": "0.1"}, "capabilities": {"experimentalApi": True}}, 30)
        started, _ = session.request(2, "thread/start", {"cwd": str(root), "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": False, "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
        thread_id = started["thread"]["id"]
        turn, _ = session.request(3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": RUNNER.build_prompt(run_id, "timeout")}], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly", "networkAccess": False}}, 30)
        time.sleep(3)
        session.process.kill()
        session.process.wait(timeout=10)
        killed = True
    finally:
        session.close()
    fresh_exit = RUNNER.run(root, 180, "simple")
    summaries = sorted((path for path in artifact_dir.glob("*.app-server.summary.json") if path.stat().st_mtime >= stderr_path.stat().st_mtime), key=lambda path: path.stat().st_mtime)
    fresh = json.loads(summaries[-1].read_text(encoding="utf-8")) if summaries else {}
    checks = {
        "live_process_kill_attempted": killed,
        "killed_turn_identity_recorded": bool(turn.get("turn", {}).get("id")),
        "fresh_run_exit_zero": fresh_exit == 0,
        "fresh_run_passed": fresh.get("status") == "passed" and fresh.get("parent_result_valid") is True,
        "fresh_worktree_unchanged": fresh.get("worktree_changed") is False,
    }
    passed = all(checks.values())
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "checks": checks, "killed_thread_id": thread_id, "killed_turn_id": turn.get("turn", {}).get("id"), "fresh_run_id": fresh.get("run_id"), "fresh": fresh, "scope": "live App Server kill fallback; isolated pilot process only"}
    (artifact_dir / f"{run_id}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
