from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/scripts/verify_stable_docs.py"


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def add_linked_worktree(repo: Path) -> Path:
    linked = repo.with_name(f"{repo.name}-linked")
    git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    return linked


class VerifierTests(unittest.TestCase):
    def fixture(self, *, with_pending: bool = False) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test")
        for value in ("docs/implementations/example", "docs/system", "docs/modules"):
            (repo / value).mkdir(parents=True, exist_ok=True)
        (repo / "docs/system/index.md").write_text("# System\n", encoding="utf-8")
        (repo / "docs/modules/example.md").write_text("# Module\n", encoding="utf-8")
        records: dict = {"pending": [], "done": "docs/done.json"}
        if with_pending:
            (repo / "docs/_pending.md").write_text("# Pending\n", encoding="utf-8")
            records["pending"] = ["docs/_pending.md"]
        config = {
            "targetBranch": "HEAD",
            "implementations": ["docs/implementations"],
            "stableDocs": {
                "systemKnowledge": ["docs/system"],
                "contextKnowledge": [],
                "moduleKnowledge": ["docs/modules"],
            },
            "ignore": [],
            "records": records,
        }
        (repo / ".stable-docs-backfill.json").write_text(json.dumps(config), encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return temp, repo

    def run_verify(self, repo: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(VERIFIER), "--project-root", str(repo), *extra], cwd=repo, capture_output=True, text=True, check=False)

    def test_healthy_repository_passes(self) -> None:
        temp, repo = self.fixture()
        self.addCleanup(temp.cleanup)
        result = self.run_verify(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])

    def test_linked_worktree_verifies_with_its_explicit_config(self) -> None:
        temp, repo = self.fixture()
        self.addCleanup(temp.cleanup)
        linked = add_linked_worktree(repo)
        self.addCleanup(
            lambda: subprocess.run(
                ["git", "worktree", "remove", "--force", str(linked)],
                cwd=repo,
                capture_output=True,
                check=False,
            )
        )
        config_path = linked / "backfill.json"
        config_path.write_text((linked / ".stable-docs-backfill.json").read_text(encoding="utf-8"), encoding="utf-8")
        (linked / ".stable-docs-backfill.json").unlink()
        (linked / "docs/implementations").mkdir(parents=True, exist_ok=True)
        (repo / ".stable-docs-backfill.json").unlink()

        result = self.run_verify(linked, "--config", str(config_path))

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(json.loads(result.stdout)["passed"])

    def test_missing_done_and_empty_pending_still_pass(self) -> None:
        temp, repo = self.fixture()
        self.addCleanup(temp.cleanup)
        result = self.run_verify(repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_missing_explicit_stable_path_fails(self) -> None:
        temp, repo = self.fixture()
        self.addCleanup(temp.cleanup)
        (repo / "docs/system/index.md").unlink()
        (repo / "docs/system").rmdir()
        result = self.run_verify(repo)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["passed"])

    def test_invalid_audit_shape_fails(self) -> None:
        temp, repo = self.fixture()
        self.addCleanup(temp.cleanup)
        audit = repo / "audit.json"
        audit.write_text(json.dumps({"mode": "audit", "items": [{"id": "x", "disposition": "unknown"}]}), encoding="utf-8")
        result = self.run_verify(repo, "--audit-json", str(audit))
        self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    unittest.main()
