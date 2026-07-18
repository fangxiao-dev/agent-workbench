#!/usr/bin/env python3
"""Exercise deterministic lifecycle fallbacks without starting another App Server."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

try:
    from codex_harness_cli import JsonRpcSession
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession


class FakeProcess:
    def __init__(self) -> None:
        self.terminated = False
        self.killed = False
        self.wait_calls = 0
        self.returncode = None

    def poll(self):
        return None if not self.killed else -9

    def terminate(self):
        self.terminated = True

    def kill(self):
        self.killed = True

    def wait(self, timeout=None):
        self.wait_calls += 1
        if not self.killed:
            raise subprocess.TimeoutExpired("fake-codex", timeout or 0)
        self.returncode = -9
        return self.returncode


class FakeReader:
    def __init__(self) -> None:
        self.join_calls = 0

    def join(self, timeout=None):
        self.join_calls += 1


def main() -> int:
    process = FakeProcess()
    reader = FakeReader()
    session = object.__new__(JsonRpcSession)
    session.process = process
    session.reader = reader
    session.close()
    checks = {
        "terminate_attempted": process.terminated,
        "kill_fallback_attempted": process.killed,
        "wait_completed": process.wait_calls == 2,
        "reader_joined": reader.join_calls == 1,
    }
    passed = all(checks.values())
    artifact_dir = Path(__file__).resolve().parents[1] / ".codex" / "harness-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-lifecycle-fixtures"
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "checks": checks, "scope": "deterministic close() fallback fixture; no live process was killed"}
    (artifact_dir / f"{run_id}.summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
