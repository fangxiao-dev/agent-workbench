from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.codex_harness_workspace import WorkspaceError, serial_handoff_evidence, validate_serial_reuse


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


class CodexHarnessWorkspaceTest(unittest.TestCase):
    def test_accepted_clean_verified_workspace_can_be_reused(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            git(root, "init")
            git(root, "config", "user.email", "fixture@example.test")
            git(root, "config", "user.name", "Fixture")
            (root / "first.txt").write_text("first\n", encoding="utf-8")
            git(root, "add", "first.txt")
            git(root, "commit", "-m", "first assignment")
            handoff = serial_handoff_evidence(root, "HEAD", [{"command": "python -m unittest", "exit_code": 0}], "delivery-1")
            self.assertEqual(validate_serial_reuse(root, handoff, "delivery-1")["commit"], git(root, "rev-parse", "HEAD"))
            (root / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            with self.assertRaises(WorkspaceError):
                validate_serial_reuse(root, handoff, "delivery-1")


if __name__ == "__main__":
    unittest.main()
