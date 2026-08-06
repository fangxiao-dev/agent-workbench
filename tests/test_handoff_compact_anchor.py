from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/handoff/scripts/compact_anchor.py"


class CompactAnchorTests(unittest.TestCase):
    def test_reports_git_and_package_state_with_relative_dirty_paths(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            repo = Path(value)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
            package = repo / "docs/implementations/example"
            package.mkdir(parents=True)
            (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=repo, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
            head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()
            (repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--worktree", str(repo), "--expected-head", head, "--package-path", "docs/implementations/example"],
                cwd=repo, capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["headMatchesExpected"])
            self.assertIn("dirty.txt", payload["dirtyPaths"])
            self.assertEqual(payload["package"]["path"], "docs/implementations/example")
            self.assertFalse(payload["package"]["state"]["active"])


if __name__ == "__main__":
    unittest.main()
