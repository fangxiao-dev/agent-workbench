from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "backfill-stable-docs" / "scripts"


def load_module(name: str):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.strip()


def init_repo(root: Path, remote: str) -> None:
    root.mkdir(parents=True, exist_ok=True)
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")
    git(root, "remote", "add", "origin", remote)


def commit(root: Path, message: str) -> str:
    git(root, "add", ".")
    git(root, "commit", "-m", message)
    return git(root, "rev-parse", "HEAD")


def base_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "schemaVersion": 3,
        "repository": "example/project",
        "targetBranch": "HEAD",
        "implementations": ["docs/implementations"],
        "stableDocs": {
            "systemKnowledge": ["docs/system-knowledge"],
            "moduleKnowledge": ["docs/module-knowledge"],
        },
        "ignore": [],
        "records": {
            "pending": "auto",
            "pendingOverrides": {},
            "done": "docs/_backfill/done.json",
            "reports": "docs/_backfill/reports",
        },
    }
    config.update(overrides)
    return config


class CollectorInventoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        init_repo(self.project, "https://github.com/example/project.git")
        (self.project / "docs/module-knowledge").mkdir(parents=True)
        (self.project / "docs/module-knowledge/_pending.md").write_text(
            "# Pending\n\n"
            "| Delta ID | Destination | Source | Statement |\n"
            "| --- | --- | --- | --- |\n"
            "| D-1 | module-spec/alpha | docs/implementations/pkg-referenced/spec.md | a durable delta |\n",
            encoding="utf-8",
        )
        for package, verdict in (
            ("pkg-open", "blocked"),
            ("pkg-referenced", "pass"),
            ("pkg-resolved", "pass"),
            ("pkg-gap", "defer"),
        ):
            path = self.project / "docs/implementations" / package
            path.mkdir(parents=True)
            (path / "spec.md").write_text(f"# {package}\n", encoding="utf-8")
            (path / "gate.md").write_text(f"## G1 · {verdict}\n", encoding="utf-8")
        (self.project / "docs/_backfill").mkdir(parents=True)
        (self.project / "docs/_backfill/done.json").write_text(
            json.dumps({"items": [{"itemId": "SDB-x", "sourcePackage": "pkg-resolved"}]}),
            encoding="utf-8",
        )
        (self.project / ".stable-docs-backfill.json").write_text(
            json.dumps(base_config()), encoding="utf-8"
        )
        commit(self.project, "baseline")

    def test_open_pending_reference_excludes_gap_and_retirement(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        by_id = {row["packageId"]: row for row in inventory["packages"]}
        self.assertFalse(by_id["pkg-open"]["gapCatchingCandidate"])
        self.assertFalse(by_id["pkg-referenced"]["gapCatchingCandidate"])
        self.assertFalse(by_id["pkg-referenced"]["retirementStructuralCandidate"])
        self.assertTrue(by_id["pkg-referenced"]["referencedInOpenPending"])

    def test_gap_catching_candidate_is_terminal_and_unreferenced_and_unresolved(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], ["pkg-gap"])

    def test_retirement_candidate_is_terminal_unreferenced_and_resolved_in_done_record(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        self.assertEqual(inventory["retirementStructuralCandidates"], ["pkg-resolved"])

    def test_blocked_gate_is_never_a_candidate(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        by_id = {row["packageId"]: row for row in inventory["packages"]}
        self.assertFalse(by_id["pkg-open"]["gapCatchingCandidate"])
        self.assertFalse(by_id["pkg-open"]["retirementStructuralCandidate"])

    def test_target_branch_is_resolved_with_git_rev_parse_and_reported(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        self.assertEqual(inventory["project"]["targetBranch"], "HEAD")
        self.assertEqual(inventory["project"]["targetBranchCommit"], git(self.project, "rev-parse", "HEAD"))
        self.assertIsNone(inventory["targetBranchConfigGap"])
        self.assertEqual(inventory["pendingConfigGaps"], [])
        self.assertEqual(len(inventory["pendingColdStarts"]), 1)

    def test_unresolvable_target_branch_is_reported_as_config_gap_without_stopping_inventory(self) -> None:
        config_path = self.project / ".stable-docs-backfill.json"
        config = json.loads(config_path.read_text(encoding="utf-8"))
        config["targetBranch"] = "origin/does-not-exist"
        config_path.write_text(json.dumps(config), encoding="utf-8")

        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        self.assertIsNone(inventory["project"]["targetBranchCommit"])
        self.assertIn("does not resolve", inventory["targetBranchConfigGap"])
        self.assertEqual(inventory["packageCount"], 4)


class LegacyGateFormatTest(unittest.TestCase):
    """A gate.md that predates the new `## <id> · <verdict>` heading must not be
    silently treated as "not terminal" — real dry-run against prj-supplyer-webapp
    showed every pre-redesign gate.md writes its verdict as free prose instead."""

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        init_repo(self.project, "https://github.com/example/project.git")
        (self.project / "docs/module-knowledge").mkdir(parents=True)
        (self.project / "docs/module-knowledge/_pending.md").write_text("# Pending\n", encoding="utf-8")
        package = self.project / "docs/implementations/legacy-pkg"
        package.mkdir(parents=True)
        (package / "spec.md").write_text("# legacy-pkg\n", encoding="utf-8")
        (package / "gate.md").write_text(
            "# Legacy Retirement Gate\n\n## Decision\n\nDecision：retirement scope closed。\n",
            encoding="utf-8",
        )
        (self.project / ".stable-docs-backfill.json").write_text(
            json.dumps(base_config()), encoding="utf-8"
        )
        commit(self.project, "baseline")

    def test_unparseable_legacy_gate_is_flagged_for_manual_review_not_silently_ignored(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        row = next(p for p in inventory["packages"] if p["packageId"] == "legacy-pkg")
        self.assertTrue(row["hasGate"])
        self.assertFalse(row["gateVerdictParsed"])
        self.assertTrue(row["needsManualGateReview"])
        self.assertFalse(row["gapCatchingCandidate"])
        self.assertFalse(row["retirementStructuralCandidate"])
        self.assertEqual(inventory["manualGateReviewCandidates"], ["legacy-pkg"])


class MonorepoPendingDiscoveryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "mono"
        init_repo(self.project, "https://github.com/example/mono.git")
        (self.project / "docs/system-knowledge").mkdir(parents=True)
        (self.project / "docs/domains/finance/module-knowledge").mkdir(parents=True)
        (self.project / "docs/domains/finance/context").mkdir(parents=True)
        (self.project / "docs/domains/finance/implementations/legacy-old").mkdir(parents=True)
        (self.project / "docs/domains/finance/implementations/legacy-old/spec.md").write_text(
            "legacy\n", encoding="utf-8"
        )
        (self.project / "docs/domains/finance/implementations/pkg-a").mkdir(parents=True)
        (self.project / "docs/domains/finance/implementations/pkg-a/spec.md").write_text(
            "# pkg-a\n", encoding="utf-8"
        )
        (self.project / "docs/domains/finance/_pending.md").write_text(
            "# pending\n\n"
            "| Delta ID | Destination | Source | Statement |\n"
            "| --- | --- | --- | --- |\n"
            "| D-1 | module-spec/finance | docs/domains/finance/implementations/pkg-a/spec.md | delta |\n",
            encoding="utf-8",
        )
        (self.project / "docs/domains/inventory/module-knowledge").mkdir(parents=True)
        (self.project / "docs/domains/inventory/implementations/pkg-b").mkdir(parents=True)
        (self.project / "docs/domains/inventory/implementations/pkg-b/spec.md").write_text(
            "# pkg-b\n", encoding="utf-8"
        )
        config = base_config(
            implementations=["docs/domains/*/implementations"],
            stableDocs={
                "systemKnowledge": ["docs/system-knowledge"],
                "contextKnowledge": ["docs/domains/*/context"],
                "moduleKnowledge": ["docs/domains/*/module-knowledge"],
            },
            ignore=[
                {
                    "paths": ["docs/domains/finance/implementations/legacy-old"],
                    "owner": "finance",
                    "reason": "pre-Impl-Package legacy, already absorbed",
                }
            ],
        )
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(config), encoding="utf-8")
        commit(self.project, "baseline")

    def test_parent_level_pending_is_discovered_for_finance_domain(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        finance = next(
            entry
            for entry in inventory["pendingDiscovery"]
            if entry["stableDocsLayer"] == "moduleKnowledge"
            and entry["stableDocsRoots"] == ["docs/domains/finance/module-knowledge"]
        )
        self.assertEqual(finance["status"], "ok")
        self.assertEqual(finance["pendingPath"], "docs/domains/finance/_pending.md")

    def test_missing_pending_is_flagged_as_config_gap_for_inventory_domain(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        gap_roots = {
            root
            for entry in inventory["pendingConfigGaps"]
            for root in entry["stableDocsRoots"]
        }
        self.assertIn("docs/domains/inventory/module-knowledge", gap_roots)

    def test_context_and_module_roots_share_one_pending_registration_without_duplication(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        finance_layers = {
            entry["stableDocsLayer"]
            for entry in inventory["pendingDiscovery"]
            if entry["pendingPath"] == "docs/domains/finance/_pending.md"
        }
        self.assertEqual(finance_layers, {"contextKnowledge", "moduleKnowledge"})
        self.assertEqual(inventory["pendingRegistrationCount"], 1)

    def test_owner_scoped_ignore_excludes_legacy_package(self) -> None:
        collector = load_module("collect_sources")
        inventory = collector.collect_inventory(project_root=self.project)
        package_ids = {row["packageId"] for row in inventory["packages"]}
        self.assertNotIn("legacy-old", package_ids)
        self.assertIn("pkg-a", package_ids)
        self.assertIn("pkg-b", package_ids)


class ConfigValidationTest(unittest.TestCase):
    def test_json_schema_matches_three_layer_contract_with_optional_context(self) -> None:
        schema = json.loads(
            (ROOT / "skills/backfill-stable-docs/config/repository-config.schema.json").read_text(
                encoding="utf-8"
            )
        )
        jsonschema.validate(base_config(), schema)

        legacy = base_config()
        legacy["stableDocs"] = {
            "topLevel": ["docs/top-level-knowledge"],
            "moduleKnowledge": ["docs/module-knowledge"],
        }
        with self.assertRaises(jsonschema.ValidationError):
            jsonschema.validate(legacy, schema)

    def test_repository_config_example_matches_schema_and_runtime_validator(self) -> None:
        config_dir = ROOT / "skills/backfill-stable-docs/config"
        schema = json.loads((config_dir / "repository-config.schema.json").read_text(encoding="utf-8"))
        example = json.loads((config_dir / "repository-config.example.json").read_text(encoding="utf-8"))
        jsonschema.validate(example, schema)

        config_module = load_module("stable_docs_config")
        validated = config_module.validate_config(example)
        self.assertEqual(validated["targetBranch"], "origin/develop")
        self.assertEqual(
            validated["stableDocs"]["contextKnowledge"],
            ["docs/platform/*/context", "docs/domains/*/context"],
        )

    def test_context_knowledge_is_optional_but_system_and_module_are_required(self) -> None:
        config_module = load_module("stable_docs_config")
        config = config_module.validate_config(base_config())
        self.assertEqual(config["stableDocs"]["contextKnowledge"], [])

        empty_context = base_config()
        empty_context["stableDocs"] = dict(
            empty_context["stableDocs"], contextKnowledge=[]
        )
        with self.assertRaisesRegex(config_module.ConfigError, "contextKnowledge"):
            config_module.validate_config(empty_context)

        for required_layer in ("systemKnowledge", "moduleKnowledge"):
            payload = base_config()
            payload["stableDocs"] = dict(payload["stableDocs"])
            del payload["stableDocs"][required_layer]
            with self.subTest(required_layer=required_layer):
                with self.assertRaisesRegex(config_module.ConfigError, required_layer):
                    config_module.validate_config(payload)

    def test_missing_system_pending_is_reported_as_cold_start_not_config_gap(self) -> None:
        config_module = load_module("stable_docs_config")
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "docs/module-knowledge").mkdir(parents=True)
            (project / "docs/module-knowledge/_pending.md").write_text("# pending\n", encoding="utf-8")
            config = config_module.validate_config(base_config())
            entries = config_module.discover_pending_paths(project, config)
            system = next(
                entry for entry in entries if entry["stableDocsLayer"] == "systemKnowledge"
            )
            self.assertEqual(system["status"], "cold-start")
            self.assertEqual(system["expectedPendingPath"], "docs/_pending.md")
            self.assertNotIn(
                system,
                [entry for entry in entries if entry["status"] in {"missing", "ambiguous"}],
            )

    def test_system_pending_outside_docs_root_is_not_accepted_as_canonical_cold_start(self) -> None:
        config_module = load_module("stable_docs_config")
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            (project / "docs/system-knowledge").mkdir(parents=True)
            (project / "docs/system-knowledge/_pending.md").write_text(
                "# misplaced pending\n", encoding="utf-8"
            )
            (project / "docs/module-knowledge").mkdir(parents=True)
            (project / "docs/module-knowledge/_pending.md").write_text("# pending\n", encoding="utf-8")
            config = config_module.validate_config(base_config())
            entries = config_module.discover_pending_paths(project, config)
            system = next(
                entry for entry in entries if entry["stableDocsLayer"] == "systemKnowledge"
            )
            self.assertEqual(system["status"], "ambiguous")
            self.assertEqual(system["expectedPendingPath"], "docs/_pending.md")

    def test_ignore_group_requires_owner_and_reason(self) -> None:
        config_module = load_module("stable_docs_config")
        payload = base_config(ignore=[{"paths": ["docs/x"]}])
        with self.assertRaisesRegex(config_module.ConfigError, "owner"):
            config_module.validate_config(payload)

    def test_repository_must_be_owner_slash_repo_not_local_folder_name(self) -> None:
        config_module = load_module("stable_docs_config")
        payload = base_config(repository="kaispan-dev")
        with self.assertRaises(config_module.ConfigError):
            config_module.validate_config(payload)

    def test_records_pending_must_equal_auto(self) -> None:
        config_module = load_module("stable_docs_config")
        payload = base_config()
        payload["records"] = dict(payload["records"], pending="docs/_backfill/pending.md")
        with self.assertRaisesRegex(config_module.ConfigError, "auto"):
            config_module.validate_config(payload)


if __name__ == "__main__":
    unittest.main()
