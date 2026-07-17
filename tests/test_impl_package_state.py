from __future__ import annotations

import hashlib
import json
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
CONFIG_PATH = ROOT / "skills" / "impl-package" / "assets" / "impl-package-state-config.json"


def run_cli(package: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--package", str(package), *args],
        text=True,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.strip()


def init_repo(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")


class DataDrivenConfigTest(unittest.TestCase):
    def test_versioned_skill_config_is_injectable_and_fails_closed(self) -> None:
        spec = importlib.util.spec_from_file_location("impl_package_state_config_test", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        base = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "config.json"
            configured = json.loads(json.dumps(base))
            configured["stateVocabulary"]["task"].append("CUSTOM")
            configured["documents"]["attemptPattern"] = r"Attempt=([^\s]+)"
            configured["projections"]["revisionSet"]["design"] = "D={design}"
            configured["gate"]["scaffoldNoneToken"] = "无"
            path.write_text(json.dumps(configured), encoding="utf-8")
            loaded = module._load_config(path)
            self.assertIn("CUSTOM", loaded["stateVocabulary"]["task"])
            original_config = module.CONFIG
            try:
                module.CONFIG = loaded
                self.assertEqual(module._document_attempt("Attempt=patch-1"), "patch-1")
                self.assertEqual(module._revision_projection({"current": {"design": {"revision": "D7"}}}, "design"), "D=D7")
                self.assertIn("取代（Supersedes）：无", module._gate_scaffold("patch-G1", "patch", None))
            finally:
                module.CONFIG = original_config

            configured["schemaVersion"] = 99
            path.write_text(json.dumps(configured), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsupported.*schemaVersion"):
                module._load_config(path)

            invalid_projection = json.loads(json.dumps(base))
            invalid_projection["projections"]["runtimeTicket"] = "state={state}"
            path.write_text(json.dumps(invalid_projection), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "placeholders"):
                module._load_config(path)

            unsafe_heading = json.loads(json.dumps(base))
            unsafe_heading["gate"]["headingPattern"] += ".*"
            path.write_text(json.dumps(unsafe_heading), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "entry span"):
                module._load_config(path)

            invalid_capture = json.loads(json.dumps(base))
            invalid_capture["documents"]["compositionPattern"] = r"Composition"
            path.write_text(json.dumps(invalid_capture), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "exactly 2 capture groups"):
                module._load_config(path)

            invalid_revision_set = json.loads(json.dumps(base))
            invalid_revision_set["gate"]["revisionSetFieldPattern"] = r"Revision set: (D\d+) / (S\d+)"
            path.write_text(json.dumps(invalid_revision_set), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "required capture groups"):
                module._load_config(path)


class InitStateTest(unittest.TestCase):
    def test_init_creates_empty_runtime_state_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            package.mkdir()

            first = run_cli(package, "init", "--package-id", package.name)
            second = run_cli(package, "init", "--package-id", package.name)

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            state = json.loads((package / ".impl-package" / "runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual(
                state,
                {
                    "schemaVersion": 1,
                    "purpose": "internal-machine-sidecar",
                    "ownerFacing": False,
                    "packageId": package.name,
                    "tasks": [],
                    "tickets": [],
                    "artifacts": [],
                    "gate": {"allocations": [], "entries": []},
                },
            )


class RevisionMigrationTest(unittest.TestCase):
    def test_migrate_v1_preserves_current_and_adds_deterministic_binding_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            package.mkdir(parents=True)
            (package / "spec.md").write_text(
                "# Spec\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：D1\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            blob = git(repo, "hash-object", "-w", "--", str(package / "spec.md"))
            sidecar.parent.mkdir()
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {
                            "design": {"artifact": "spec.md", "revision": "D1"},
                            "spec": {"artifact": "spec.md", "revision": "S1"},
                        },
                        "bindings": [
                            {"artifact": "spec.md", "revision": "D1", "mode": "exact-blob", "blob": blob},
                            {"artifact": "spec.md", "revision": "S1", "mode": "exact-blob", "blob": blob},
                        ],
                    }
                ),
                encoding="utf-8",
            )

            run_cli(package, "migrate", "--evidence", "plan.md#ER-1")
            first = sidecar.read_text(encoding="utf-8")
            run_cli(package, "migrate", "--evidence", "plan.md#ER-1")

            migrated = json.loads(first)
            self.assertEqual(sidecar.read_text(encoding="utf-8"), first)
            self.assertEqual(migrated["schemaVersion"], 2)
            self.assertEqual(migrated["current"]["spec"]["revision"], "S1")
            self.assertEqual(
                [row["id"] for row in migrated["bindings"]],
                [f"D1@{blob}", f"S1@{blob}"],
            )
            self.assertTrue(all(row["evidence"] == "plan.md#ER-1" for row in migrated["bindings"]))

    def test_invalid_v1_migration_leaves_source_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/2026-07-17-invalid"
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            invalid = {
                "schemaVersion": 1, "purpose": "internal-machine-sidecar", "ownerFacing": False,
                "current": {"spec": {"artifact": "spec.md", "revision": "X1"}},
                "bindings": [{"artifact": "spec.md", "revision": "X1", "mode": "exact-blob", "blob": "0" * 40}],
            }
            original = json.dumps(invalid)
            sidecar.write_text(original, encoding="utf-8")
            failed = run_cli(package, "migrate", "--evidence", "spec.md#gate", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("revision alias", failed.stderr)
            self.assertEqual(sidecar.read_text(encoding="utf-8"), original)


class RevisionRegistrationTest(unittest.TestCase):
    def test_validate_rejects_revision_declaration_outside_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            for declaration in (
                "Spec Revision: S1",
                "**Spec Revision:** S1",
                "**规格修订（Spec Revision）：** S1 <!-- stale -->",
            ):
                content = (
                    "# Spec S1\n\n"
                    f"{declaration}\n\n"
                    "<!-- impl-package:projection revision-set begin -->\n"
                    "设计修订（Design Revision）：N/A\n规格修订（Spec Revision）：S1\n"
                    "<!-- impl-package:projection revision-set end -->\n"
                )
                (package / "spec.md").write_text(content, encoding="utf-8")
                blob = git(repo, "hash-object", "-w", "--", str(package / "spec.md"))
                sidecar.write_text(
                    json.dumps(
                        {
                            "schemaVersion": 2,
                            "purpose": "internal-machine-sidecar",
                            "ownerFacing": False,
                            "current": {"spec": {"artifact": "spec.md", "revision": "S1"}},
                            "bindings": [
                                {
                                    "artifact": "spec.md",
                                    "revision": "S1",
                                    "mode": "exact-blob",
                                    "blob": blob,
                                    "id": f"S1@{blob}",
                                    "supersedes": None,
                                    "evidence": "spec.md#gate",
                                }
                            ],
                        }
                    ),
                    encoding="utf-8",
                )

                failed = run_cli(package, "validate", "--working-tree", check=False)

                self.assertNotEqual(failed.returncode, 0)
                self.assertIn("revision declaration outside machine-owned projection", failed.stderr)

    def test_register_revision_supports_worktree_then_committed_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "spec.md").write_text(
                "# Spec S1\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：N/A\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )

            run_cli(
                package,
                "register-revision",
                "spec",
                "S1",
                "--artifact",
                "spec.md",
                "--evidence",
                "spec.md#spec-gate",
            )
            run_cli(package, "validate", "--working-tree")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "publish S1")
            run_cli(package, "validate", "--committed")

            registered = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(registered["current"]["spec"], {"artifact": "spec.md", "revision": "S1"})
            self.assertEqual(len(registered["bindings"]), 1)
            (package / "spec.md").write_text("# drift\n", encoding="utf-8")
            failed = run_cli(package, "validate", "--working-tree", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("binding mismatch", failed.stderr)


class PlanContractValidationTest(unittest.TestCase):
    def test_plan_contract_allows_execution_record_append_but_rejects_strategy_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            plan = package / "plan.md"
            plan.write_text(
                "# Plan\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "## Strategy\n\nKeep this.\n\n## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(
                package,
                "register-revision",
                "plan",
                "P1",
                "--attempt",
                "initial",
                "--artifact",
                "plan.md",
                "--evidence",
                "plan.md#publication",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "publish plan")

            plan.write_text(plan.read_text(encoding="utf-8") + "\n### ER-1\n\n- result: pass\n", encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "append ER")
            run_cli(package, "validate", "--committed")

            appended = plan.read_text(encoding="utf-8")
            plan.write_text(appended.replace("Keep this.", "Changed strategy."), encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "drift strategy")
            failed = run_cli(package, "validate", "--committed", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("plan contract mismatch", failed.stderr)

            plan.write_text(appended, encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "restore strategy")
            run_cli(package, "validate", "--committed")

            plan.write_text(appended.replace("result: pass", "result: rewritten"), encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "rewrite ER")
            rewritten = run_cli(package, "validate", "--committed", check=False)
            self.assertNotEqual(rewritten.returncode, 0)
            self.assertIn("append-only", rewritten.stderr)


class RuntimeStateTransitionTest(unittest.TestCase):
    def test_init_imports_earned_records_and_set_state_is_cas_lite_and_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "plan.md").write_text(
                "# Plan\n\n执行组合（Composition）：tickets=true, dag=true\n", encoding="utf-8"
            )
            (package / "dag.md").write_text(
                "# DAG\n\n执行尝试 ID（Attempt ID）：initial\n\n### T1: Build\n\n- 状态：PENDING\n\n"
                "## DAG 看板\n\n<!-- impl-package:projection runtime-state begin -->\n"
                "| 任务 | 状态 | 证据 |\n| --- | --- | --- |\n| T1 | PENDING | dag.md#T1 |\n"
                "<!-- impl-package:projection runtime-state end -->\n",
                encoding="utf-8",
            )
            tickets = package / "tickets"
            tickets.mkdir()
            (tickets / "01-alpha.md").write_text(
                "# Alpha\n\n**Ticket ID：** alpha\n**执行尝试 ID（Attempt ID）：** initial\n\n## 运行时验收状态（Runtime Acceptance Status）\n\n"
                "<!-- impl-package:projection runtime-state begin -->\n"
                "- 值：[unrecorded]\n- 直接证据：[unrecorded]\n"
                "<!-- impl-package:projection runtime-state end -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {
                            "attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"}
                        },
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )

            run_cli(package, "init", "--package-id", package.name)
            state_path = package / ".impl-package" / "runtime-state.json"
            initial = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(initial["tasks"], [{"attempt": "initial", "id": "T1", "state": "PENDING", "evidence": "dag.md#T1"}])
            self.assertEqual(initial["tickets"][0]["state"], "UNRECORDED")

            args = (
                "set-state",
                "task",
                "T1",
                "DONE",
                "--attempt",
                "initial",
                "--expect",
                "PENDING",
                "--evidence",
                "plan.md#ER-2",
            )
            run_cli(package, *args)
            run_cli(package, *args)
            updated = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["tasks"][0]["state"], "DONE")
            self.assertEqual(updated["tasks"][0]["evidence"], "plan.md#ER-2")
            self.assertIn("| T1 | DONE | plan.md#ER-2 |", (package / "dag.md").read_text(encoding="utf-8"))

            stale = run_cli(
                package,
                "set-state",
                "task",
                "T1",
                "RUNNING",
                "--attempt",
                "initial",
                "--expect",
                "PENDING",
                "--evidence",
                "plan.md#ER-3",
                check=False,
            )
            self.assertNotEqual(stale.returncode, 0)
            self.assertIn("expected state", stale.stderr)

    def test_init_selects_earned_artifacts_by_current_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "plan.md").write_text("# Initial\n\n执行组合（Composition）：tickets=true, dag=true\n", encoding="utf-8")
            (package / "dag.md").write_text("# Initial DAG\n\n执行尝试 ID（Attempt ID）：initial\n\n### T1: Old\n", encoding="utf-8")
            tickets = package / "tickets"
            tickets.mkdir()
            (tickets / "01-old.md").write_text("# Old\n\n**Ticket ID：** old\n**执行尝试 ID（Attempt ID）：** initial\n", encoding="utf-8")
            revision = {
                "schemaVersion": 2, "purpose": "internal-machine-sidecar", "ownerFacing": False,
                "current": {"attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"}}, "bindings": [],
            }
            sidecar.write_text(json.dumps(revision), encoding="utf-8")
            run_cli(package, "init", "--package-id", package.name)

            patch_id = "20260717-1200-fix"
            patch_plan = f"{patch_id}.patch-plan.md"
            (package / patch_plan).write_text("# Patch\n\n执行组合（Composition）：tickets=true, dag=true\n", encoding="utf-8")
            (package / f"{patch_id}.patch-dag.md").write_text(
                f"# Patch DAG\n\n执行尝试 ID（Attempt ID）：{patch_id}\n\n### T2: New\n", encoding="utf-8"
            )
            (tickets / "02-new.md").write_text(
                f"# New\n\n**Ticket ID：** new\n**执行尝试 ID（Attempt ID）：** {patch_id}\n", encoding="utf-8"
            )
            revision["current"]["attempt"] = {"id": patch_id, "plan": patch_plan, "revision": "P1"}
            sidecar.write_text(json.dumps(revision), encoding="utf-8")
            run_cli(package, "init", "--package-id", package.name)

            runtime = json.loads((package / ".impl-package/runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual([(row["attempt"], row["id"]) for row in runtime["tasks"]], [("initial", "T1"), (patch_id, "T2")])
            self.assertEqual([(row["attempt"], row["id"]) for row in runtime["tickets"]], [("initial", "old"), (patch_id, "new")])


class ArtifactChainTest(unittest.TestCase):
    def test_external_artifacts_are_identified_by_hash_and_updated_append_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            package = root / "2026-07-17-example"
            package.mkdir()
            external = root / "submissions" / "bundle.zip"
            external.parent.mkdir()
            external.write_bytes(b"first")
            run_cli(package, "init", "--package-id", package.name)

            record = (
                "record-artifact",
                "delivery",
                str(external),
                "--kind",
                "package",
                "--evidence",
                "plan.md#ER-4",
            )
            run_cli(package, *record)
            run_cli(package, *record)
            external.write_bytes(b"second")
            run_cli(
                package,
                "supersede-artifact",
                "delivery",
                "delivery-v2",
                str(external),
                "--kind",
                "package",
                "--evidence",
                "plan.md#ER-5",
            )
            run_cli(
                package,
                "tombstone-artifact",
                "bad-record",
                "--target",
                "delivery-v2",
                "--evidence",
                "plan.md#ER-6",
            )
            rejected = run_cli(
                package,
                "supersede-artifact",
                "delivery",
                "delivery-v3",
                str(external),
                "--kind",
                "package",
                "--evidence",
                "plan.md#ER-7",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("active record", rejected.stderr)

            state = json.loads((package / ".impl-package" / "runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual([row["id"] for row in state["artifacts"]], ["delivery", "delivery-v2", "bad-record"])
            self.assertNotEqual(state["artifacts"][0]["hash"]["value"], state["artifacts"][1]["hash"]["value"])
            self.assertEqual(state["artifacts"][1]["supersedes"], ["delivery"])
            self.assertEqual(state["artifacts"][2]["tombstones"], "delivery-v2")
            self.assertEqual(state["artifacts"][0]["path"], str(external))


class GateIndexTest(unittest.TestCase):
    def test_indexed_historical_gate_does_not_resolve_current_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-revision-drift"
            package.mkdir()
            (package / "plan.md").write_text(
                "# Plan\n\n执行尝试 ID（Attempt ID）：initial\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n",
                encoding="utf-8",
            )
            sidecar = package / ".impl-package"
            sidecar.mkdir()
            (sidecar / "revision-bindings.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {
                            "design": {"artifact": "design.md", "revision": "D2"},
                            "spec": {"artifact": "spec.md", "revision": "S2"},
                            "attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"},
                        },
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            gate_block = (
                "## initial-G1 · pass\n\n"
                "- 执行尝试 ID（Attempt ID）：initial\n"
                "- 取代（Supersedes）：none\n"
                "- 修订集合（Revision set）：D1 / S1 / P1\n"
                "- 判决理由（Verdict reason）：historical only\n"
            )
            (package / "gate.md").write_text(gate_block, encoding="utf-8")
            digest = hashlib.sha256(gate_block.encode("utf-8")).hexdigest()
            (sidecar / "runtime-state.json").write_text(
                json.dumps(
                    {
                        "schemaVersion": 1,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "packageId": package.name,
                        "tasks": [],
                        "tickets": [],
                        "artifacts": [],
                        "gate": {
                            "allocations": [
                                {
                                    "operationId": "gate-evaluation-1",
                                    "attempt": "initial",
                                    "number": 1,
                                    "entryId": "initial-G1",
                                }
                            ],
                            "entries": [
                                {
                                    "id": "initial-G1",
                                    "attempt": "initial",
                                    "number": 1,
                                    "verdict": "pass",
                                    "supersedes": None,
                                    "entry": {
                                        "path": "gate.md",
                                        "anchor": "initial-G1",
                                        "bindingMode": "gate-entry-v1",
                                        "contentSha256": digest,
                                    },
                                }
                            ],
                        },
                    }
                ),
                encoding="utf-8",
            )

            resolution = json.loads(run_cli(package, "resolve-gate").stdout)

            self.assertEqual(resolution["kind"], "indexed")
            self.assertEqual(resolution["entryId"], "initial-G1")
            self.assertIsNone(resolution["gateResolution"])
            self.assertFalse(resolution["appliesToCurrentRevision"])
            self.assertFalse(resolution["needsManualGateReview"])

            patch_attempt = "20260717-1700-current"
            patch_plan = f"{patch_attempt}.patch-plan.md"
            (package / patch_plan).write_text(
                "# Patch plan\n\n"
                f"执行尝试 ID（Attempt ID）：{patch_attempt}\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n",
                encoding="utf-8",
            )
            revision_state = json.loads((sidecar / "revision-bindings.json").read_text(encoding="utf-8"))
            revision_state["current"]["attempt"] = {"id": patch_attempt, "plan": patch_plan, "revision": "P1"}
            (sidecar / "revision-bindings.json").write_text(json.dumps(revision_state), encoding="utf-8")

            new_attempt_resolution = json.loads(run_cli(package, "resolve-gate").stdout)

            self.assertEqual(new_attempt_resolution["kind"], "indexed")
            self.assertEqual(new_attempt_resolution["entryId"], "initial-G1")
            self.assertIsNone(new_attempt_resolution["gateResolution"])
            self.assertFalse(new_attempt_resolution["appliesToCurrentRevision"])
            self.assertFalse(new_attempt_resolution["needsManualGateReview"])

            runtime_state = json.loads((sidecar / "runtime-state.json").read_text(encoding="utf-8"))
            runtime_state["gate"] = {"allocations": [], "entries": []}
            (sidecar / "runtime-state.json").write_text(json.dumps(runtime_state), encoding="utf-8")
            (package / "gate.md").write_text("# Gate\n", encoding="utf-8")

            empty_gate_resolution = json.loads(run_cli(package, "resolve-gate").stdout)

            self.assertIsNone(empty_gate_resolution["kind"])
            self.assertTrue(empty_gate_resolution["hasGate"])
            self.assertIsNone(empty_gate_resolution["gateResolution"])
            self.assertFalse(empty_gate_resolution["needsManualGateReview"])

    def test_gate_allocation_is_idempotent_and_finalized_index_is_content_bound(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            package.mkdir()
            (package / "plan.md").write_text("# Plan\n\n执行组合（Composition）：tickets=false, dag=false\n", encoding="utf-8")
            revision_path = package / ".impl-package/revision-bindings.json"
            revision_path.parent.mkdir()
            revision_path.write_text(
                json.dumps({
                    "schemaVersion": 2,
                    "purpose": "internal-machine-sidecar",
                    "ownerFacing": False,
                    "current": {"attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"}},
                    "bindings": [],
                }),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)

            first = run_cli(
                package,
                "new-gate-entry",
                "--attempt",
                "initial",
                "--operation-id",
                "gate-evaluation-1",
            )
            second = run_cli(
                package,
                "new-gate-entry",
                "--attempt",
                "initial",
                "--operation-id",
                "gate-evaluation-1",
            )
            self.assertEqual(json.loads(first.stdout)["entryId"], "initial-G1")
            self.assertEqual(json.loads(second.stdout)["entryId"], "initial-G1")
            gate_path = package / "gate.md"
            self.assertEqual(gate_path.read_text(encoding="utf-8").count("## initial-G1"), 1)

            gate_path.write_text(
                gate_path.read_text(encoding="utf-8").replace(
                    "## initial-G1 · <pass|fail|blocked|defer>", "## initial-G1 · pass"
                ).replace(
                    "- 修订集合（Revision set）：",
                    "- 修订集合（Revision set）：D1 / S1 / P1",
                ),
                encoding="utf-8",
            )
            rejected = run_cli(package, "finalize-gate-entry", "initial-G1", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("does not match current revisions", rejected.stderr)
            state = json.loads((package / ".impl-package" / "runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["gate"]["entries"], [])
            gate_path.write_text(
                gate_path.read_text(encoding="utf-8").replace(
                    "D1 / S1 / P1", "N/A / N/A / P1"
                ),
                encoding="utf-8",
            )
            run_cli(package, "finalize-gate-entry", "initial-G1")
            run_cli(package, "finalize-gate-entry", "initial-G1")
            resolution = json.loads(run_cli(package, "resolve-gate").stdout)
            self.assertEqual(resolution["kind"], "indexed")
            self.assertEqual(resolution["gateResolution"], "pass")
            self.assertTrue(resolution["appliesToCurrentRevision"])
            gate_path.write_bytes(gate_path.read_text(encoding="utf-8").replace("\n", "\r\n").encode("utf-8"))
            self.assertEqual(json.loads(run_cli(package, "resolve-gate").stdout)["kind"], "indexed")

            state_path = package / ".impl-package" / "runtime-state.json"
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(len(state["gate"]["allocations"]), 1)
            self.assertEqual(len(state["gate"]["entries"]), 1)
            state["gate"]["entries"][0]["verdict"] = "fail"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            mismatch = json.loads(run_cli(package, "resolve-gate").stdout)
            self.assertEqual(mismatch["kind"], "mismatch")
            self.assertIsNone(mismatch["gateResolution"])
            self.assertTrue(mismatch["needsManualGateReview"])


class ProjectionRebindTest(unittest.TestCase):
    def test_refresh_updates_revision_projection_and_rebinds_same_plan_alias_only_for_marker_diff(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "design.md").write_text(
                "# Design D1\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：D1\n<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            (package / "spec.md").write_text(
                "# Spec S1\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：D1\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            plan = package / "plan.md"
            plan.write_text(
                "# Plan\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：D1\n规格修订（Spec Revision）：S1\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n"
                "## Strategy\n\nKeep this.\n\n## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            for kind, alias, artifact in (
                ("design", "D1", "design.md"),
                ("spec", "S1", "spec.md"),
            ):
                run_cli(
                    package,
                    "register-revision",
                    kind,
                    alias,
                    "--artifact",
                    artifact,
                    "--evidence",
                    f"{artifact}#gate",
                )
            run_cli(
                package,
                "register-revision",
                "plan",
                "P1",
                "--attempt",
                "initial",
                "--artifact",
                "plan.md",
                "--evidence",
                "plan.md#publication",
            )
            git(repo, "add", ".")
            git(repo, "commit", "-m", "publish D1 S1 P1")

            (package / "spec.md").write_text(
                "# Spec S2\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：D1\n规格修订（Spec Revision）：S2\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            run_cli(
                package,
                "register-revision",
                "spec",
                "S2",
                "--artifact",
                "spec.md",
                "--evidence",
                "spec.md#spec-gate-2",
            )
            run_cli(package, "refresh-projections")
            self.assertIn("规格修订（Spec Revision）：S2", plan.read_text(encoding="utf-8"))
            state = json.loads(sidecar.read_text(encoding="utf-8"))
            p1 = [row for row in state["bindings"] if row["revision"] == "P1"]
            self.assertEqual(len(p1), 2)
            self.assertEqual(p1[1]["supersedes"], p1[0]["id"])

            plan.write_text(plan.read_text(encoding="utf-8").replace("Keep this.", "Changed strategy."), encoding="utf-8")
            failed = run_cli(
                package,
                "rebind",
                "P1",
                "--reason",
                "projection",
                "--evidence",
                "plan.md#projection",
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("marker regions", failed.stderr)

    def test_register_patch_with_existing_runtime_refreshes_revision_and_gate_projections(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/2026-07-17-patch"
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            plan_body = (
                "<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n## Execution Record\n\n<!-- append only -->\n"
            )
            (package / "plan.md").write_text("# Initial\n\n" + plan_body, encoding="utf-8")
            sidecar.write_text(json.dumps({
                "schemaVersion": 2, "purpose": "internal-machine-sidecar", "ownerFacing": False,
                "current": {}, "bindings": [],
            }), encoding="utf-8")
            run_cli(package, "register-revision", "plan", "P1", "--attempt", "initial", "--artifact", "plan.md", "--evidence", "plan.md#publication")
            run_cli(package, "init", "--package-id", package.name)
            run_cli(package, "new-gate-entry", "--attempt", "initial", "--operation-id", "initial-gate")
            gate_path = package / "gate.md"
            gate_path.write_text(
                gate_path.read_text(encoding="utf-8")
                .replace("## initial-G1 · <pass|fail|blocked|defer>", "## initial-G1 · pass")
                .replace(
                    "- 修订集合（Revision set）：",
                    "- 修订集合（Revision set）：N/A / N/A / P1",
                ),
                encoding="utf-8",
            )
            run_cli(package, "finalize-gate-entry", "initial-G1")

            patch_id = "20260717-1300-fix"
            patch_plan = f"{patch_id}.patch-plan.md"
            (package / patch_plan).write_text("# Patch\n\n" + plan_body, encoding="utf-8")
            run_cli(package, "register-revision", "plan", "P1", "--attempt", patch_id, "--artifact", patch_plan, "--evidence", f"{patch_plan}#publication")

            revision = json.loads(sidecar.read_text(encoding="utf-8"))
            self.assertEqual(revision["current"]["attempt"]["id"], patch_id)
            self.assertIn("状态：尚无已定稿门禁记录", gate_path.read_text(encoding="utf-8"))
            run_cli(package, "validate", "--working-tree")


class RuntimeProjectionValidationTest(unittest.TestCase):
    def test_validate_rejects_runtime_projection_drift(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "plan.md").write_text(
                "# Plan\n\n<!-- impl-package:projection revision-set begin -->\n"
                "设计修订（Design Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=true\n\n"
                "## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            dag = package / "dag.md"
            dag.write_text(
                "# DAG\n\n执行尝试 ID（Attempt ID）：initial\n\n### T1: Build\n\n- 运行时状态与证据：见看板。\n\n"
                "## DAG 看板\n\n<!-- impl-package:projection runtime-state begin -->\n"
                "| 任务 | 状态 | 证据 |\n| --- | --- | --- |\n| T1 | PENDING | dag.md#T1 |\n"
                "<!-- impl-package:projection runtime-state end -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "schemaVersion": 2,
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(
                package,
                "register-revision",
                "plan",
                "P1",
                "--attempt",
                "initial",
                "--artifact",
                "plan.md",
                "--evidence",
                "plan.md#publication",
            )
            run_cli(package, "init", "--package-id", package.name)
            git(repo, "add", ".")
            git(repo, "commit", "-m", "publish package")
            run_cli(package, "validate", "--committed")

            committed_copies = {
                path: path.read_bytes()
                for path in (package / "plan.md", dag, sidecar, package / ".impl-package/runtime-state.json")
            }
            for path in committed_copies:
                path.unlink()
            run_cli(package, "validate", "--committed")
            for path, payload in committed_copies.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)

            original_dag = dag.read_text(encoding="utf-8")
            dag.write_text(original_dag.replace("<!-- impl-package:projection runtime-state begin -->", "<!-- missing runtime marker -->"), encoding="utf-8")
            missing_marker = run_cli(package, "validate", "--working-tree", check=False)
            self.assertNotEqual(missing_marker.returncode, 0)
            self.assertIn("runtime-state", missing_marker.stderr)
            dag.write_text(original_dag, encoding="utf-8")

            dag.write_text(dag.read_text(encoding="utf-8").replace("| T1 | PENDING |", "| T1 | DONE |"), encoding="utf-8")
            git(repo, "add", ".")
            git(repo, "commit", "-m", "drift projection")
            failed = run_cli(package, "validate", "--committed", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("runtime projection mismatch", failed.stderr)


if __name__ == "__main__":
    unittest.main()
