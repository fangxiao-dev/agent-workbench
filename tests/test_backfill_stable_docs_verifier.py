from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "skills" / "backfill-stable-docs" / "scripts" / "verify_stable_docs.py"


class VerifierTest(unittest.TestCase):
    def test_plugin_era_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            project = Path(temporary)
            for path in ("docs/module-knowledge/_compaction", "docs/implementations"):
                (project / path).mkdir(parents=True)
            (project / "docs/module-knowledge/_pending.md").write_text("", encoding="utf-8")
            config = {
                "schemaVersion": 1,
                "canonicalDocs": [{"path": "docs/module-knowledge", "role": "module", "owner": "owner", "moduleInventory": True}],
                "pendingPath": "docs/module-knowledge/_pending.md",
                "compactionPath": "docs/module-knowledge/_compaction",
                "statePath": "docs/module-knowledge/_compaction/state.json",
                "implementationsPath": "docs/implementations",
                "excludePaths": [],
                "dangerRules": [],
            }
            (project / ".stable-docs-backfill.json").write_text(json.dumps(config), encoding="utf-8")
            (project / "docs/module-knowledge/_compaction/state.json").write_text(json.dumps({"method_activation": {"plugin": "stable-docs-backfill", "version": "0.1.0"}, "project": {"source_watermark": "HEAD"}, "carry_forward": []}), encoding="utf-8")
            subprocess.run(["git", "init"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=project, check=True)
            subprocess.run(["git", "config", "user.name", "Test"], cwd=project, check=True)
            subprocess.run(["git", "add", "."], cwd=project, check=True)
            subprocess.run(["git", "commit", "-m", "fixture"], cwd=project, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            completed = subprocess.run(["python", str(VERIFY), "--project-root", str(project)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.assertEqual(completed.returncode, 2)
            self.assertIn("Plugin-era state requires a fresh audit", completed.stdout)


if __name__ == "__main__":
    unittest.main()
