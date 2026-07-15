from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VERIFY = ROOT / "skills" / "backfill-stable-docs" / "scripts" / "verify_stable_docs.py"


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=root, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def load_verifier_module():
    scripts = VERIFY.parent
    if str(scripts) not in sys.path:
        sys.path.insert(0, str(scripts))
    import verify_stable_docs

    return verify_stable_docs


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


class ItemScopedFingerprintTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        git(self.project, "init")
        git(self.project, "config", "user.email", "test@example.com")
        git(self.project, "config", "user.name", "Test")
        git(self.project, "remote", "add", "origin", "https://github.com/example/project.git")
        for path in ("docs/module-knowledge/_compaction", "docs/implementations/alpha", "docs/implementations/bravo"):
            (self.project / path).mkdir(parents=True, exist_ok=True)
        (self.project / "docs/module-knowledge/_pending.md").write_text("", encoding="utf-8")
        (self.project / "docs/module-knowledge/alpha.md").write_text("# Alpha\n", encoding="utf-8")
        (self.project / "docs/module-knowledge/bravo.md").write_text("# Bravo\n", encoding="utf-8")
        (self.project / "docs/implementations/alpha/spec.md").write_text("alpha v1\n", encoding="utf-8")
        (self.project / "docs/implementations/bravo/spec.md").write_text("bravo v1\n", encoding="utf-8")
        config = {
            "schemaVersion": 1,
            "repository": "example/project",
            "canonicalDocs": [{"path": "docs/module-knowledge", "role": "module", "owner": "docs-owner"}],
            "pendingPath": "docs/module-knowledge/_pending.md",
            "compactionPath": "docs/module-knowledge/_compaction",
            "statePath": "docs/module-knowledge/_compaction/state.json",
            "implementationsPath": "docs/implementations",
            "excludePaths": [],
            "dangerRules": [],
        }
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(config), encoding="utf-8")
        verifier = load_verifier_module()
        self.method_activation = verifier.load_method_activation(verifier.METHOD_ROOT)
        state = {"method_activation": self.method_activation, "project": {"source_watermark": "HEAD"}, "carry_forward": []}
        (self.project / "docs/module-knowledge/_compaction/state.json").write_text(json.dumps(state), encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", "audit baseline")
        self.audit_head = git(self.project, "rev-parse", "HEAD")
        self.audit_path = self.project / "audit.json"
        self._write_audit(verifier)

    def _write_audit(self, verifier, *, schema_version: int = 2, repository: str = "example/project", method_repository: str | None = None) -> None:
        items = []
        for name in ("alpha", "bravo"):
            source = f"docs/implementations/{name}/spec.md"
            item = {
                "source": source,
                "destination": f"docs/module-knowledge/{name}.md",
                "statement": f"{name} contract",
                "disposition": "candidate",
                "authority": ["approved-design"],
                "evidence": [{"path": source, "blob": git(self.project, "rev-parse", f"{self.audit_head}:{source}")}],
                "canonicalOwner": "docs-owner",
            }
            item["id"] = verifier.make_item_id(item["source"], item["destination"], item["statement"])
            item["fingerprint"] = verifier._make_item_fingerprint(item)
            items.append(item)
        audit = {
            "schemaVersion": schema_version,
            "mode": "audit",
            "methodActivation": {"repository": method_repository or self.method_activation["repository"], "commit": "0" * 40},
            "project": {"repository": repository, "sourceHead": self.audit_head, "projectSourceWatermark": self.audit_head, "dirtyPaths": []},
            "configSha256": verifier.load_repository_config(self.project, None)[1]["sha256"],
            "moduleCoverage": [{"module": "all", "result": "candidate", "itemIds": [item["id"] for item in items]}],
            "items": items,
            "pending": [],
            "carryForward": [],
            "removedPackages": [],
            "blockers": [],
        }
        self.audit_path.write_text(json.dumps(audit), encoding="utf-8")

    def _verify(self) -> tuple[int, dict[str, object]]:
        completed = subprocess.run(["python", str(VERIFY), "--project-root", str(self.project), "--audit-json", str(self.audit_path)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return completed.returncode, json.loads(completed.stdout)

    def test_descendant_source_head_and_method_commit_only_invalidate_changed_item(self) -> None:
        (self.project / "docs/implementations/bravo/spec.md").write_text("bravo v2\n", encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", "change bravo")

        returncode, payload = self._verify()

        self.assertEqual(returncode, 0)
        status = payload["itemFingerprintStatus"]
        self.assertEqual(len(status["applyReadyItemIds"]), 1)
        self.assertEqual(len(status["pendingItemIds"]), 1)
        self.assertNotEqual(status["applyReadyItemIds"][0], status["pendingItemIds"][0])

    def test_legacy_schema_and_different_repository_fail_closed(self) -> None:
        verifier = load_verifier_module()
        self._write_audit(verifier, schema_version=1)
        returncode, payload = self._verify()
        self.assertEqual(returncode, 2)
        self.assertIn("legacy and cannot be applied", payload["checks"][3]["detail"])

        self._write_audit(verifier, repository="other/project")
        returncode, payload = self._verify()
        self.assertEqual(returncode, 2)
        self.assertIn("does not match the current project repository", payload["checks"][3]["detail"])

        self._write_audit(verifier, method_repository="other/agent-workbench")
        returncode, payload = self._verify()
        self.assertEqual(returncode, 2)
        self.assertIn("methodActivation repository does not match", payload["checks"][3]["detail"])

        config_path = self.project / ".stable-docs-backfill.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["excludePaths"] = ["docs/ignored"]
        config_path.write_text(json.dumps(config), encoding="utf-8")
        self._write_audit(verifier)
        config["excludePaths"] = []
        config_path.write_text(json.dumps(config), encoding="utf-8")
        returncode, payload = self._verify()
        self.assertEqual(returncode, 2)
        self.assertIn("configSha256 does not match", payload["checks"][3]["detail"])


if __name__ == "__main__":
    unittest.main()
