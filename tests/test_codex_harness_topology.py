from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.codex_harness_topology import TopologyError, serial_handoff_evidence, validate_execution_topology, validate_serial_reuse


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def parent_serial_topology() -> dict:
    return {
        "schema_version": "codex-crew.execution-topology.v0",
        "execution_topology": "parent_serial",
        "dispatcher_required": False,
        "max_active_write_worktrees": 1,
        "workspace_reuse_policy": "same_delivery_after_committed_and_verified",
        "promotion_boundary": "committed_and_verified",
        "selection_rationale": "The issues share one write owner and must hand off in order.",
        "not_parallel_rationale": "Concurrent writes would overlap the handoff boundary.",
    }


class CodexHarnessTopologyTest(unittest.TestCase):
    def test_parent_serial_is_a_real_zero_worker_topology(self) -> None:
        topology = validate_execution_topology(parent_serial_topology())
        self.assertFalse(topology["dispatcher_required"])
        self.assertEqual(topology["max_active_write_worktrees"], 1)

    def test_fresh_parent_context_can_reuse_committed_verified_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            git(root, "init")
            git(root, "config", "user.email", "fixture@example.test")
            git(root, "config", "user.name", "Fixture")
            (root / "first.txt").write_text("first\n", encoding="utf-8")
            git(root, "add", "first.txt")
            git(root, "commit", "-m", "first work package")
            handoff = serial_handoff_evidence(root, "HEAD", [{"command": "python -m unittest", "exit_code": 0}], "delivery-1")
            self.assertEqual(validate_serial_reuse(root, handoff, "delivery-1")["commit"], git(root, "rev-parse", "HEAD"))
            (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaises(TopologyError):
                validate_serial_reuse(root, handoff, "delivery-1")


if __name__ == "__main__":
    unittest.main()
