from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "backfill-stable-docs" / "scripts" / "collect_sources.py"


def load_module():
    if str(SCRIPT.parent) not in sys.path:
        sys.path.insert(0, str(SCRIPT.parent))
    spec = importlib.util.spec_from_file_location("backfill_collect_sources", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(["git", *args], cwd=root, env=env, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def commit(root: Path, message: str) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = "2026-07-01T00:00:00+00:00"
    env["GIT_COMMITTER_DATE"] = "2026-07-01T00:00:00+00:00"
    git(root, "add", ".", env=env)
    git(root, "commit", "-m", message, env=env)
    return git(root, "rev-parse", "HEAD")


def config(implementations: str) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "repository": "example/project",
        "canonicalDocs": [{"path": "docs/module-knowledge", "role": "module", "owner": "owner", "moduleInventory": True}],
        "pendingPath": "docs/module-knowledge/_pending.md",
        "compactionPath": "docs/module-knowledge/_compaction",
        "statePath": "docs/module-knowledge/_compaction/state.json",
        "implementationsPath": implementations,
        "excludePaths": [],
        "dangerRules": [],
    }


class CollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.method = Path(self.temp.name) / "method"
        for root, remote in ((self.project, "https://github.com/example/project.git"), (self.method, "https://github.com/example/agent-workbench.git")):
            root.mkdir()
            git(root, "init")
            git(root, "config", "user.email", "test@example.com")
            git(root, "config", "user.name", "Test User")
            git(root, "remote", "add", "origin", remote)
        (self.method / "skills/backfill-stable-docs").mkdir(parents=True)
        (self.method / "skills/impl-package").mkdir(parents=True)
        (self.method / "skills/backfill-stable-docs/SKILL.md").write_text("backfill", encoding="utf-8")
        (self.method / "skills/impl-package/SKILL.md").write_text("impl", encoding="utf-8")
        self.method_commit = commit(self.method, "method")
        (self.project / "docs/module-knowledge/_compaction").mkdir(parents=True)
        (self.project / "docs/module-knowledge/_pending.md").write_text("", encoding="utf-8")
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(config("docs/implementations")), encoding="utf-8")
        self.watermark = commit(self.project, "baseline")
        for package in ("alpha", "bravo"):
            path = self.project / "docs/implementations" / package
            path.mkdir(parents=True)
            (path / "spec.md").write_text(f"# {package}\n", encoding="utf-8")
            commit(self.project, package)
        self.head = git(self.project, "rev-parse", "HEAD")

    def test_inventory_uses_repository_commit_method_activation(self) -> None:
        inventory = load_module().collect_inventory(mode="bootstrap", project_root=self.project, source_head=self.head, project_watermark=self.watermark, fixture_count=1, method_root=self.method)
        self.assertEqual(inventory["method_activation"], {"repository": "example/agent-workbench", "commit": self.method_commit})
        self.assertEqual(inventory["protected_fixtures"], ["alpha"])
        self.assertEqual(inventory["bootstrap_targets"], ["bravo"])
        self.assertEqual(inventory["packages"][0]["semantic_sources"], ["docs/implementations/alpha/spec.md"])

    def test_nested_monorepo_contexts_are_isolated(self) -> None:
        nested = self.project / "domains/payments/docs/implementations/ledger"
        nested.mkdir(parents=True)
        (nested / "spec.md").write_text("# ledger\n", encoding="utf-8")
        nested_head = commit(self.project, "nested package")
        nested_config = self.project / "payments.json"
        nested_config.write_text(json.dumps(config("domains/payments/docs/implementations")), encoding="utf-8")
        module = load_module()
        repo_wide = module.collect_inventory(mode="steady-state", project_root=self.project, source_head=nested_head, project_watermark=self.head, method_root=self.method)
        domain = module.collect_inventory(mode="steady-state", project_root=self.project, source_head=nested_head, project_watermark=self.head, method_root=self.method, config_path=nested_config)
        self.assertEqual(repo_wide["eligible_packages"], [])
        self.assertEqual(domain["eligible_packages"], ["ledger"])
        self.assertEqual(domain["config"]["implementations_path"], "domains/payments/docs/implementations")

    def test_missing_atomic_impl_package_rejects_method_root(self) -> None:
        (self.method / "skills/impl-package/SKILL.md").unlink()
        module = load_module()
        with self.assertRaisesRegex(Exception, "backfill-stable-docs and impl-package"):
            module.collect_inventory(mode="steady-state", project_root=self.project, source_head=self.head, project_watermark=self.watermark, method_root=self.method)


if __name__ == "__main__":
    unittest.main()
