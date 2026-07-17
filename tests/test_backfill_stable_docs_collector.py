from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import jsonschema


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "backfill-stable-docs" / "scripts"
IMPL_STATE = ROOT / "skills" / "impl-package" / "scripts" / "impl_package_state.py"


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
        self.assertEqual(inventory["schemaVersion"], 4)

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
        self.assertEqual(row["gateRecognition"], "manual")
        self.assertIsNone(row["gateResolution"])
        self.assertIn("no structured index", row["reason"])
        self.assertTrue(row["needsManualGateReview"])
        self.assertFalse(row["gapCatchingCandidate"])
        self.assertFalse(row["retirementStructuralCandidate"])
        self.assertEqual(inventory["manualGateReviewCandidates"], ["legacy-pkg"])


class GateRecognitionV4Test(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        init_repo(self.project, "https://github.com/example/project.git")
        (self.project / "docs/module-knowledge").mkdir(parents=True)
        (self.project / "docs/module-knowledge/_pending.md").write_text("# Pending\n", encoding="utf-8")
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(base_config()), encoding="utf-8")

    def _package(self, name: str, gate: str | None, runtime: object = ...,) -> Path:
        package = self.project / "docs/implementations" / name
        package.mkdir(parents=True)
        (package / "spec.md").write_text(f"# {name}\n", encoding="utf-8")
        if gate is not None:
            (package / "gate.md").write_text(gate, encoding="utf-8", newline="\n")
        if runtime is not ...:
            sidecar = package / ".impl-package"
            sidecar.mkdir()
            (package / "plan.md").write_text("# Plan\n", encoding="utf-8")
            (sidecar / "revision-bindings.json").write_text(
                json.dumps({"schemaVersion": 2, "current": {"attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"}}, "bindings": []}),
                encoding="utf-8",
            )
            if isinstance(runtime, str):
                (sidecar / "runtime-state.json").write_text(runtime, encoding="utf-8")
            else:
                (sidecar / "runtime-state.json").write_text(json.dumps(runtime), encoding="utf-8")
        return package

    @staticmethod
    def _gate_text(verdict: str = "pass", entry_id: str = "initial-G1", attempt: str = "initial") -> str:
        return (
            f"## {entry_id} · {verdict}\n\n"
            f"- 执行尝试 ID（Attempt ID）：{attempt}\n"
            "- 取代（Supersedes）：none\n"
            "- 判决理由（Verdict reason）：fixture\n"
        )

    @staticmethod
    def _runtime(gate_text: str, *, entry_id: str = "initial-G1", verdict: str = "pass", digest: str | None = None) -> dict[str, object]:
        digest = digest or hashlib.sha256((gate_text.rstrip("\n") + "\n").encode("utf-8")).hexdigest()
        return {
            "schemaVersion": 1,
            "packageId": "fixture",
            "gate": {
                "allocations": [{"operationId": "op-1", "attempt": "initial", "number": 1, "entryId": "initial-G1"}],
                "entries": [{
                    "id": entry_id,
                    "attempt": "initial",
                    "number": 1,
                    "verdict": verdict,
                    "supersedes": None,
                    "entry": {"path": "gate.md", "anchor": entry_id, "bindingMode": "gate-entry-v1", "contentSha256": digest},
                }],
            },
        }

    def _inventory(self) -> dict[str, dict[str, object]]:
        commit(self.project, "gate fixtures")
        collector = load_module("collect_sources")
        return {row["packageId"]: row for row in collector.collect_inventory(project_root=self.project)["packages"]}

    def test_four_results_and_no_gate_open_state(self) -> None:
        valid = self._gate_text()
        self._package("indexed", valid, self._runtime(valid))
        self._package("legacy-heading", self._gate_text("fail"))
        self._package("manual", "# Gate\n\nVerdict: prose only\n")
        self._package("no-gate", None)
        rows = self._inventory()

        self.assertEqual((rows["indexed"]["gateRecognition"], rows["indexed"]["gateResolution"]), ("indexed", "pass"))
        self.assertEqual((rows["legacy-heading"]["gateRecognition"], rows["legacy-heading"]["gateResolution"]), ("legacy-heading", "fail"))
        self.assertEqual((rows["manual"]["gateRecognition"], rows["manual"]["gateResolution"]), ("manual", None))
        self.assertEqual((rows["no-gate"]["gateRecognition"], rows["no-gate"]["gateResolution"]), (None, None))
        self.assertFalse(rows["no-gate"]["needsManualGateReview"])
        self.assertNotIn("gateVerdict", rows["indexed"])
        self.assertNotIn("gateVerdictParsed", rows["indexed"])

    def test_runtime_state_failures_are_mismatch_without_heading_fallback(self) -> None:
        valid = self._gate_text()
        missing_hash = self._runtime(valid)
        del missing_hash["gate"]["entries"][0]["entry"]["contentSha256"]  # type: ignore[index]
        missing_id = self._runtime(valid)
        del missing_id["gate"]["entries"][0]["id"]  # type: ignore[index]
        missing_verdict = self._runtime(valid)
        del missing_verdict["gate"]["entries"][0]["verdict"]  # type: ignore[index]
        empty_operation = self._runtime(valid)
        empty_operation["gate"]["allocations"][0]["operationId"] = ""  # type: ignore[index]
        cases: dict[str, object] = {
            "missing-entry": {"schemaVersion": 1, "gate": {"entries": []}},
            "missing-hash": missing_hash,
            "missing-id": missing_id,
            "missing-verdict": missing_verdict,
            "bad-hash": self._runtime(valid, digest="0" * 64),
            "bad-id": self._runtime(valid, entry_id="initial-G2"),
            "bad-verdict": self._runtime(valid, verdict="fail"),
            "empty-operation": empty_operation,
            "bad-schema": {"schemaVersion": 99, "gate": self._runtime(valid)["gate"]},
            "corrupt-json": "{not json",
        }
        for name, runtime in cases.items():
            self._package(name, valid, runtime)
        stale = "## initial-G2 · pass\n\n- 执行尝试 ID（Attempt ID）：initial\n- 取代（Supersedes）：initial-G1\n\n" + valid
        self._package("stale", stale, self._runtime(valid))
        rows = self._inventory()
        for name in cases.keys() | {"stale"}:
            with self.subTest(name=name):
                self.assertEqual(rows[name]["gateRecognition"], "mismatch")
                self.assertIsNone(rows[name]["gateResolution"])
                self.assertTrue(rows[name]["needsManualGateReview"])
                self.assertTrue(rows[name]["reason"])

    def test_current_attempt_and_matching_allocation_control_indexed_resolution(self) -> None:
        initial = self._gate_text("pass", "initial-G1", "initial")
        patch = self._gate_text("defer", "patch-G1", "patch")
        package = self._package("attempt-local", patch + "\n" + initial, self._runtime(initial))
        runtime_path = package / ".impl-package/runtime-state.json"
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        runtime["gate"]["allocations"].append({"operationId": "op-patch", "attempt": "patch", "number": 1, "entryId": "patch-G1"})
        runtime["gate"]["entries"].append({
            "id": "patch-G1", "attempt": "patch", "number": 1, "verdict": "defer", "supersedes": None,
            "entry": {"path": "gate.md", "anchor": "patch-G1", "bindingMode": "gate-entry-v1", "contentSha256": hashlib.sha256((patch.rstrip("\n") + "\n").encode("utf-8")).hexdigest()},
        })
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        revision_path = package / ".impl-package/revision-bindings.json"
        revision = json.loads(revision_path.read_text(encoding="utf-8"))
        revision["current"]["attempt"] = {"id": "patch", "plan": "patch.md", "revision": "P1"}
        revision_path.write_text(json.dumps(revision), encoding="utf-8")
        (package / "patch.md").write_text("# Patch\n", encoding="utf-8")
        rows = self._inventory()
        self.assertEqual((rows["attempt-local"]["gateRecognition"], rows["attempt-local"]["gateResolution"]), ("indexed", "defer"))
        spec = importlib.util.spec_from_file_location("impl_package_state_attempt_test", IMPL_STATE)
        assert spec is not None and spec.loader is not None
        canonical = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(canonical)
        self.assertEqual(canonical.resolve_gate(package)["gateResolution"], "defer")

        runtime["gate"]["allocations"] = [row for row in runtime["gate"]["allocations"] if row["entryId"] != "patch-G1"]
        runtime_path.write_text(json.dumps(runtime), encoding="utf-8")
        commit(self.project, "remove matching allocation")
        collector = load_module("collect_sources")
        row = next(row for row in collector.collect_inventory(project_root=self.project)["packages"] if row["packageId"] == "attempt-local")
        self.assertEqual(row["gateRecognition"], "mismatch")

    def test_invalid_supersedes_chain_has_canonical_backfill_parity(self) -> None:
        first = self._gate_text("pass", "initial-G1", "initial")
        second = self._gate_text("defer", "initial-G2", "initial")
        runtime = self._runtime(first)
        runtime["gate"]["allocations"].append({"operationId": "op-2", "attempt": "initial", "number": 2, "entryId": "initial-G2"})
        runtime["gate"]["entries"].append({
            "id": "initial-G2", "attempt": "initial", "number": 2, "verdict": "defer", "supersedes": None,
            "entry": {"path": "gate.md", "anchor": "initial-G2", "bindingMode": "gate-entry-v1", "contentSha256": hashlib.sha256((second.rstrip("\n") + "\n").encode("utf-8")).hexdigest()},
        })
        package = self._package("invalid-chain", second + "\n" + first, runtime)
        rows = self._inventory()
        self.assertEqual(rows["invalid-chain"]["gateRecognition"], "mismatch")
        spec = importlib.util.spec_from_file_location("impl_package_state_chain_test", IMPL_STATE)
        assert spec is not None and spec.loader is not None
        canonical = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(canonical)
        self.assertEqual(canonical.resolve_gate(package)["kind"], "mismatch")

    def test_invalid_current_plan_pointer_is_mismatch(self) -> None:
        valid = self._gate_text()
        package = self._package("invalid-plan-pointer", valid, self._runtime(valid))
        revision_path = package / ".impl-package/revision-bindings.json"
        revision = json.loads(revision_path.read_text(encoding="utf-8"))
        revision["current"]["attempt"]["plan"] = "../outside.md"
        revision_path.write_text(json.dumps(revision), encoding="utf-8")
        row = self._inventory()["invalid-plan-pointer"]
        self.assertEqual(row["gateRecognition"], "mismatch")
        self.assertIn("escapes package", row["reason"])

    def test_fail_is_terminal_only_when_indexed_or_legacy_heading_is_trusted(self) -> None:
        indexed_fail = self._gate_text("fail")
        self._package("indexed-fail", indexed_fail, self._runtime(indexed_fail, verdict="fail"))
        self._package("legacy-fail", self._gate_text("fail"))
        self._package("mismatch-fail", indexed_fail, self._runtime(indexed_fail, verdict="fail", digest="0" * 64))
        rows = self._inventory()
        self.assertTrue(rows["indexed-fail"]["gapCatchingCandidate"])
        self.assertTrue(rows["legacy-fail"]["gapCatchingCandidate"])
        self.assertFalse(rows["mismatch-fail"]["gapCatchingCandidate"])

    def test_referenced_mismatch_remains_visible_and_never_becomes_candidate(self) -> None:
        package = self._package("referenced-mismatch", self._gate_text(), self._runtime(self._gate_text(), digest="0" * 64))
        pending = self.project / "docs/module-knowledge/_pending.md"
        pending.write_text(
            "# Pending\n\n| Delta ID | Destination | Source | Statement |\n| --- | --- | --- | --- |\n"
            f"| D-1 | module | {package.relative_to(self.project).as_posix()}/spec.md | delta |\n",
            encoding="utf-8",
        )
        row = self._inventory()["referenced-mismatch"]
        self.assertTrue(row["referencedInOpenPending"])
        self.assertTrue(row["needsManualGateReview"])
        self.assertFalse(row["gapCatchingCandidate"])
        self.assertFalse(row["retirementStructuralCandidate"])

    def test_indexed_resolution_matches_canonical_helper_on_shared_package_fixture(self) -> None:
        valid = self._gate_text()
        package = self._package("shared-valid", valid, self._runtime(valid))
        commit(self.project, "shared canonical fixture")
        spec = importlib.util.spec_from_file_location("impl_package_state_for_backfill_test", IMPL_STATE)
        assert spec is not None and spec.loader is not None
        canonical = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(canonical)
        collector = load_module("collect_sources")
        row = next(p for p in collector.collect_inventory(project_root=self.project)["packages"] if p["packageId"] == "shared-valid")
        canonical_result = canonical.resolve_gate(package)
        self.assertEqual(row["gateRecognition"], canonical_result["kind"])
        self.assertEqual(row["gateResolution"], canonical_result["gateResolution"])

    def test_markdown_inventory_summarizes_recognition_and_resolution_separately(self) -> None:
        valid = self._gate_text()
        self._package("indexed", valid, self._runtime(valid))
        commit(self.project, "markdown fixture")
        collector = load_module("collect_sources")
        markdown = collector._render_markdown(collector.collect_inventory(project_root=self.project))
        self.assertIn("| Package | Gate recognition | Gate resolution |", markdown)
        self.assertIn("| indexed | indexed | pass |", markdown)
        self.assertIn("Needs manual gate review (mismatch/manual)", markdown)


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
