from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "impl-package" / "backfill-stable-docs" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import collect_sources  # noqa: E402
import make_item_id  # noqa: E402
import stable_docs_config  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        git(self.project, "init")
        git(self.project, "config", "user.email", "test@example.com")
        git(self.project, "config", "user.name", "Test")
        for value in ("docs/implementations/example", "docs/system-knowledge", "docs/module-knowledge", "docs/reports"):
            (self.project / value).mkdir(parents=True, exist_ok=True)
        (self.project / "docs/system-knowledge/index.md").write_text("# System\n", encoding="utf-8")
        (self.project / "docs/module-knowledge/example.md").write_text("# Module\n", encoding="utf-8")
        (self.project / "docs/_pending.md").write_text("# Pending\n", encoding="utf-8")
        self.config = {
            "repository": "example/project", "targetBranch": "HEAD",
            "implementations": ["docs/implementations"],
            "stableDocs": {"systemKnowledge": ["docs/system-knowledge"], "contextKnowledge": [], "moduleKnowledge": ["docs/module-knowledge"]},
            "ignore": [],
            "records": {"pending": ["docs/_pending.md"], "done": "docs/done.json", "reports": "docs/reports"},
        }
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(self.config), encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", "fixture")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_config_uses_explicit_repository_relative_paths(self) -> None:
        validated = stable_docs_config.validate_config(self.config)
        self.assertEqual(validated["records"]["pending"], ["docs/_pending.md"])
        for invalid in ("C:/outside", "../outside", "docs/*"):
            changed = json.loads(json.dumps(self.config))
            changed["implementations"] = [invalid]
            with self.assertRaises(stable_docs_config.ConfigError):
                stable_docs_config.validate_config(changed)
        changed = json.loads(json.dumps(self.config))
        changed["ignore"] = [{"path": "docs/implementations/example", "owner": "repo-wide"}]
        with self.assertRaisesRegex(stable_docs_config.ConfigError, "owner, and reason"):
            stable_docs_config.validate_config(changed)
        changed["ignore"] = [{"path": "docs/implementations/example", "owner": "repo-wide", "reason": "fixture"}]
        validated = stable_docs_config.validate_config(changed)
        self.assertEqual(validated["ignore"][0]["owner"], "repo-wide")

    def test_inventory_enumerates_direct_packages_and_current_gate(self) -> None:
        head = git(self.project, "rev-parse", "HEAD")
        gate = self.project / "docs/implementations/example/gate.md"
        gate.write_text(f"# Gate\n\n- Verdict: pass\n- Attempt: initial\n- Comparison commit: {head}\n", encoding="utf-8")
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["packageCount"], 1)
        row = inventory["packages"][0]
        self.assertEqual(row["gateRecognition"], "current")
        self.assertTrue(row["durableDeltaCandidate"])
        self.assertTrue(row["targetReachable"])
        self.assertEqual(row["origin"], "gap-catching")
        self.assertEqual(inventory["sourceWorktree"]["head"], head)
        self.assertEqual(inventory["config"]["source"], ".stable-docs-backfill.json")

    def test_pending_registry_is_primary_even_without_terminal_gate(self) -> None:
        (self.project / "docs/_pending.md").write_text("- docs/implementations/example::DD-1\n", encoding="utf-8")
        inventory = collect_sources.collect_inventory(self.project)
        row = inventory["packages"][0]
        self.assertTrue(row["pendingRegistered"])
        self.assertEqual(row["origin"], "pending-registry")
        self.assertTrue(row["durableDeltaCandidate"])
        self.assertFalse(row["gapCatchingCandidate"])

    def test_readable_item_id_uses_source_and_delta(self) -> None:
        self.assertEqual(make_item_id.make_item_id("docs/implementations/example", "DD-1"), "docs/implementations/example::DD-1")
        with self.assertRaises(ValueError):
            make_item_id.make_item_id("../outside", "DD-1")


if __name__ == "__main__":
    unittest.main()
