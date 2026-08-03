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


def run_cli(
    package: Path,
    *args: str,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--package", str(package), *args],
        text=True,
        check=check,
        input=input_text,
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
            configured["projections"]["revisionSet"]["decision"] = "D={decision}"
            configured["gate"]["scaffoldNoneToken"] = "无"
            path.write_text(json.dumps(configured), encoding="utf-8")
            loaded = module._load_config(path)
            self.assertIn("CUSTOM", loaded["stateVocabulary"]["task"])
            original_config = module.CONFIG
            try:
                module.CONFIG = loaded
                self.assertEqual(module._document_attempt("Attempt=patch-1"), "patch-1")
                self.assertEqual(module._revision_projection({"current": {"decision": {"revision": "D7"}}}, "decision"), "D=D7")
                self.assertIn("取代（Supersedes）：无", module._gate_scaffold("patch-G1", "patch", None))
            finally:
                module.CONFIG = original_config

            configured["contractVersion"] = "3.3"
            path.write_text(json.dumps(configured), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "unsupported.*contractVersion"):
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

            invalid_legacy_task_state = json.loads(json.dumps(base))
            invalid_legacy_task_state["stateVocabulary"]["legacyTaskRead"] = ["PENDING"]
            path.write_text(json.dumps(invalid_legacy_task_state), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "legacyTaskRead"):
                module._load_config(path)

            invalid_revision_set = json.loads(json.dumps(base))
            invalid_revision_set["gate"]["revisionSetFieldPattern"] = r"Revision set: (D\d+) / (S\d+)"
            path.write_text(json.dumps(invalid_revision_set), encoding="utf-8")
            with self.assertRaisesRegex(RuntimeError, "required capture groups"):
                module._load_config(path)


class InitStateTest(unittest.TestCase):
    def test_init_creates_both_empty_sidecars_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            package.mkdir()

            first = run_cli(package, "init", "--package-id", package.name)
            second = run_cli(package, "init", "--package-id", package.name)

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            state = json.loads((package / ".impl-package" / "runtime-state.json").read_text(encoding="utf-8"))
            revisions = json.loads((package / ".impl-package" / "revision-bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(
                state,
                {
                    "contractVersion": "3.2",
                    "purpose": "internal-machine-sidecar",
                    "ownerFacing": False,
                    "packageId": package.name,
                    "tasks": [],
                    "tickets": [],
                    "artifacts": [],
                    "gate": {"allocations": [], "entries": []},
                },
            )
            self.assertEqual(
                revisions,
                {
                    "contractVersion": "3.2",
                    "purpose": "internal-machine-sidecar",
                    "ownerFacing": False,
                    "current": {},
                    "bindings": [],
                },
            )

    def test_new_package_can_register_decision_and_spec_immediately_after_init(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/260717-example"
            package.mkdir(parents=True)
            (package / "decision.md").write_text(
                "# 决策\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            (package / "spec.md").write_text(
                "# 规格\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n"
                "规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )

            run_cli(package, "init", "--package-id", package.name)
            run_cli(
                package,
                "register-revision",
                "decision",
                "D1",
                "--artifact",
                "decision.md",
                "--evidence",
                "decision.md#decision-gate",
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

            revisions = json.loads((package / ".impl-package/revision-bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(revisions["current"]["decision"]["revision"], "D1")
            self.assertEqual(revisions["current"]["spec"]["revision"], "S1")
            run_cli(package, "validate", "--working-tree")

    def test_register_revision_still_fails_closed_without_explicit_init(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/260717-uninitialized"
            package.mkdir(parents=True)
            (package / "decision.md").write_text("# 决策\n", encoding="utf-8")

            result = run_cli(
                package,
                "register-revision",
                "decision",
                "D1",
                "--artifact",
                "decision.md",
                "--evidence",
                "decision.md#decision-gate",
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("revision sidecar does not exist", result.stderr)


class ContractStatusTest(unittest.TestCase):
    def _write_components(self, package: Path, revision: object, runtime: object) -> None:
        sidecar = package / ".impl-package"
        sidecar.mkdir(parents=True)
        (sidecar / "revision-bindings.json").write_text(json.dumps(revision), encoding="utf-8")
        (sidecar / "runtime-state.json").write_text(json.dumps(runtime), encoding="utf-8")

    def test_contract_status_reports_current_and_is_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            package.mkdir()
            current = {"contractVersion": "3.2"}
            self._write_components(package, current, current)
            result = run_cli(package, "contract-status")
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["status"], "current")
            self.assertEqual(payload["contractVersion"], "3.2")
            self.assertEqual(payload["currentContractVersion"], "3.2")

    def test_contract_status_classifies_old_future_and_invalid_versions(self) -> None:
        cases = (
            ({"contractVersion": "3.1"}, {"contractVersion": "3.2"}, "upgradeRequired", 3),
            ({"contractVersion": "3.1", "current": {"design": {"artifact": "design.md"}}}, {"contractVersion": "3.2"}, "upgradeRequired", 3),
            ({"contractVersion": "3.3"}, {"contractVersion": "3.2"}, "unsupportedFuture", 4),
            ({"contractVersion": 3.2}, {"contractVersion": "3.2"}, "invalid", 2),
            ({"contractVersion": "3.2", "schemaVersion": 2}, {"contractVersion": "3.2"}, "invalid", 2),
            ({"contractVersion": "3.2", "current": {"design": {"artifact": "design.md"}}}, {"contractVersion": "3.2"}, "invalid", 2),
        )
        for revision, runtime, expected_status, expected_exit in cases:
            with self.subTest(expected_status=expected_status), tempfile.TemporaryDirectory() as temp:
                package = Path(temp) / "2026-07-17-example"
                package.mkdir()
                self._write_components(package, revision, runtime)
                result = run_cli(package, "contract-status", check=False)
                payload = json.loads(result.stdout)
                self.assertEqual(result.returncode, expected_exit)
                self.assertEqual(payload["status"], expected_status)

    def test_migrate_command_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            package.mkdir()
            result = run_cli(package, "migrate", "--evidence", "old", check=False)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("invalid choice", result.stderr)


class DecisionArtifactContractTest(unittest.TestCase):
    def test_current_reader_rejects_legacy_design_path_and_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/2026-07-17-legacy-design"
            package.mkdir(parents=True)
            content = (
                "# Decision D1\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n"
                "<!-- impl-package:projection revision-set end -->\n"
            )
            legacy = package / "design.md"
            legacy.write_text(content, encoding="utf-8")
            blob = git(repo, "hash-object", "-w", "--", str(legacy))
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir()
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {"design": {"artifact": "design.md", "revision": "D1"}},
                        "bindings": [
                            {
                                "artifact": "design.md",
                                "revision": "D1",
                                "mode": "exact-blob",
                                "blob": blob,
                                "id": f"D1@{blob}",
                                "supersedes": None,
                                "evidence": "design.md#revision-history",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rejected = run_cli(package, "validate", "--working-tree", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("legacy design.md artifact is not supported", rejected.stderr)

    def test_mechanical_rename_updates_path_but_keeps_alias_blob_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/2026-07-17-rename"
            package.mkdir(parents=True)
            decision = package / "decision.md"
            decision.write_text(
                "# Decision D1\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir()
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {"decision": {"artifact": "decision.md", "revision": "D1"}},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
            run_cli(
                package,
                "register-revision",
                "decision",
                "D1",
                "--artifact",
                "decision.md",
                "--evidence",
                "decision.md#revision-history",
            )
            state = json.loads(sidecar.read_text(encoding="utf-8"))
            binding = state["bindings"][0]
            self.assertEqual(binding["id"], f"D1@{binding['blob']}")
            self.assertEqual(binding["artifact"], "decision.md")
            self.assertEqual(state["current"], {"decision": {"artifact": "decision.md", "revision": "D1"}})
            run_cli(package, "validate", "--working-tree")

    def test_investigations_are_rejected_from_revision_bindings(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/2026-07-17-investigation-binding"
            package.mkdir(parents=True)
            artifact = package / "investigations/spec.md"
            artifact.parent.mkdir()
            artifact.write_text(
                "# Spec S1\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            blob = git(repo, "hash-object", "-w", "--", str(artifact))
            sidecar = package / ".impl-package/revision-bindings.json"
            sidecar.parent.mkdir()
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {"spec": {"artifact": "investigations/spec.md", "revision": "S1"}},
                        "bindings": [
                            {
                                "artifact": "investigations/spec.md",
                                "revision": "S1",
                                "mode": "exact-blob",
                                "blob": blob,
                                "id": f"S1@{blob}",
                                "supersedes": None,
                                "evidence": "investigations/spec.md#revision-history",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            rejected = run_cli(package, "validate", "--working-tree", check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("investigations are not structured runtime artifacts", rejected.stderr)


class RevisionRegistrationTest(unittest.TestCase):
    def test_register_revisions_supports_lightweight_decision_and_atomic_dsp_selection(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs" / "implementations" / "2026-07-18-lightweight"
            package.mkdir(parents=True)
            (package / "spec.md").write_text(
                "# Spec\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            (package / "patch.md").write_text(
                "# Patch\n\n执行尝试 ID（Attempt ID）：initial\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n规格修订（Spec Revision）：S1\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n## Execution Record\n\n",
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
            run_cli(
                package,
                "register-revisions",
                "--decision", "D1", "--decision-artifact", "spec.md", "--decision-evidence", "spec.md#decision",
                "--spec", "S1", "--spec-artifact", "spec.md", "--spec-evidence", "spec.md#spec",
                "--plan", "P1", "--plan-artifact", "patch.md", "--attempt", "initial", "--plan-evidence", "patch.md#plan",
            )
            state = json.loads((package / ".impl-package/revision-bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(state["current"]["decision"], {"artifact": "spec.md", "revision": "D1"})
            self.assertEqual(state["current"]["spec"], {"artifact": "spec.md", "revision": "S1"})
            self.assertEqual(state["current"]["attempt"], {"id": "initial", "plan": "patch.md", "revision": "P1"})
            run_cli(package, "validate", "--working-tree")

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
                    "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：S1\n"
                    "<!-- impl-package:projection revision-set end -->\n"
                )
                (package / "spec.md").write_text(content, encoding="utf-8")
                blob = git(repo, "hash-object", "-w", "--", str(package / "spec.md"))
                sidecar.write_text(
                    json.dumps(
                        {
                            "contractVersion": "3.2",
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
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)

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
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n"
                "## Strategy\n\nKeep this.\n\n## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
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
                        "contractVersion": "3.2",
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
            self.assertEqual(initial["tickets"][0]["state"], "PENDING")

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
                "contractVersion": "3.2", "purpose": "internal-machine-sidecar", "ownerFacing": False,
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

    def test_minimal_task_table_rejects_new_needs_seam_but_reads_legacy_state(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-example"
            sidecar = package / ".impl-package" / "revision-bindings.json"
            sidecar.parent.mkdir(parents=True)
            (package / "plan.md").write_text(
                "# Plan\n\n执行组合（Composition）：tickets=false, dag=true\n", encoding="utf-8"
            )
            (package / "dag.md").write_text(
                "# Task DAG\n\n执行尝试 ID（Attempt ID）：initial\n\n## Task DAG\n\n"
                "| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |\n"
                "| --- | --- | --- | --- | --- |\n"
                "| T1 | runner | none | none | none |\n\n"
                "<!-- impl-package:projection runtime-state begin -->\n"
                "| 任务 | 状态 | 证据 |\n| --- | --- | --- |\n| T1 | PENDING | dag.md#T1 |\n"
                "<!-- impl-package:projection runtime-state end -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {"attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"}},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)

            rejected = run_cli(
                package,
                "set-state",
                "task",
                "T1",
                "NEEDS_SEAM",
                "--attempt",
                "initial",
                "--expect",
                "PENDING",
                "--evidence",
                "dag.md#T1",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("unsupported task state", rejected.stderr)

            state_path = package / ".impl-package" / "runtime-state.json"
            runtime = json.loads(state_path.read_text(encoding="utf-8"))
            runtime["tasks"][0]["state"] = "NEEDS_SEAM"
            state_path.write_text(json.dumps(runtime), encoding="utf-8")
            run_cli(
                package,
                "set-state",
                "task",
                "T1",
                "BLOCKED",
                "--attempt",
                "initial",
                "--expect",
                "NEEDS_SEAM",
                "--evidence",
                "tasks/T1-progress.md",
            )
            self.assertEqual(json.loads(state_path.read_text(encoding="utf-8"))["tasks"][0]["state"], "BLOCKED")


class CandidateRegistrationTest(unittest.TestCase):
    def test_preflight_seeds_candidate_uses_allocator_and_leaves_no_partial_state_on_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            repo = Path(temp) / "repo"
            repo.mkdir()
            init_repo(repo)
            package = repo / "docs/implementations/260723-candidate"
            package.mkdir(parents=True)
            (package / "plan.md").write_text(
                "# Plan\n\n<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=true\n\n## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            dag = package / "dag.md"
            dag.write_text(
                "# DAG\n\n执行尝试 ID（Attempt ID）：initial\n\n"
                "| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |\n"
                "| --- | --- | --- | --- | --- |\n| T1 | owner | none | none | none |\n\n"
                "<!-- impl-package:projection runtime-state begin -->\n| 任务 | 状态 | 证据 |\n| --- | --- | --- |\n"
                "| T1 | PENDING | dag.md#T1 |\n<!-- impl-package:projection runtime-state end -->\n",
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
            args = ("--plan", "P1", "--plan-artifact", "plan.md", "--plan-evidence", "plan.md#publication", "--attempt", "initial")
            preflight = json.loads(run_cli(package, "preflight-register", *args).stdout)
            self.assertEqual(preflight["taskIds"], ["T1"])
            self.assertEqual(json.loads(run_cli(package, "allocate-task-id", "--attempt", "initial").stdout)["identity"], "initial:T2")
            run_cli(package, "register-revisions", *args)
            self.assertEqual(
                json.loads((package / ".impl-package/runtime-state.json").read_text(encoding="utf-8"))["tasks"],
                [{"attempt": "initial", "id": "T1", "state": "PENDING", "evidence": "dag.md#T1"}],
            )
            module_spec = importlib.util.spec_from_file_location("impl_package_state_recovery_test", SCRIPT)
            assert module_spec is not None and module_spec.loader is not None
            module = importlib.util.module_from_spec(module_spec)
            module_spec.loader.exec_module(module)
            state_path = package / ".impl-package/runtime-state.json"
            original_state = state_path.read_bytes()
            module._journal_snapshot(package, {state_path: original_state})
            state_path.write_text("{}\n", encoding="utf-8")
            run_cli(package, "validate", "--working-tree")
            self.assertEqual(state_path.read_bytes(), original_state)
            self.assertFalse((package / ".impl-package/registration-transaction.json").exists())
            before = (package / ".impl-package/runtime-state.json").read_bytes()
            dag.write_text(dag.read_text(encoding="utf-8").replace("runtime-state begin", "missing-state begin"), encoding="utf-8")
            rejected = run_cli(package, "register-revisions", *args, check=False)
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual((package / ".impl-package/runtime-state.json").read_bytes(), before)


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

    def test_investigations_are_not_runtime_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "2026-07-17-investigation"
            package.mkdir()
            source = package / "investigations" / "raw.md"
            source.parent.mkdir()
            source.write_text("raw evidence", encoding="utf-8")
            run_cli(package, "init", "--package-id", package.name)
            rejected = run_cli(
                package,
                "record-artifact",
                "investigation-1",
                str(source),
                "--kind",
                "investigations",
                "--evidence",
                "decision.md#investigation",
                check=False,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("not structured runtime artifacts", rejected.stderr)
            state = json.loads((package / ".impl-package/runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["artifacts"], [])


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
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {
                            "decision": {"artifact": "decision.md", "revision": "D2"},
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
                        "contractVersion": "3.2",
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
                    "contractVersion": "3.2",
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
            (package / "decision.md").write_text(
                "# Decision D1\n\n<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            (package / "spec.md").write_text(
                "# Spec S1\n\n<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n规格修订（Spec Revision）：S1\n"
                "<!-- impl-package:projection revision-set end -->\n",
                encoding="utf-8",
            )
            plan = package / "plan.md"
            plan.write_text(
                "# Plan\n\n"
                "<!-- impl-package:projection revision-set begin -->\n"
                "决策修订（Decision Revision）：D1\n规格修订（Spec Revision）：S1\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n"
                "## Strategy\n\nKeep this.\n\n## Execution Record\n\n<!-- append only -->\n",
                encoding="utf-8",
            )
            sidecar.write_text(
                json.dumps(
                    {
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
            for kind, alias, artifact in (
                ("decision", "D1", "decision.md"),
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
                "决策修订（Decision Revision）：D1\n规格修订（Spec Revision）：S2\n"
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
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
                "<!-- impl-package:projection revision-set end -->\n\n"
                "执行组合（Composition）：tickets=false, dag=false\n\n## Execution Record\n\n<!-- append only -->\n"
            )
            (package / "plan.md").write_text("# Initial\n\n" + plan_body, encoding="utf-8")
            sidecar.write_text(json.dumps({
                "contractVersion": "3.2", "purpose": "internal-machine-sidecar", "ownerFacing": False,
                "current": {}, "bindings": [],
            }), encoding="utf-8")
            run_cli(package, "init", "--package-id", package.name)
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
    def test_terminal_gate_rejects_stale_dag_revision_binding(self) -> None:
        spec = importlib.util.spec_from_file_location("impl_package_state_gate_binding_test", SCRIPT)
        assert spec is not None and spec.loader is not None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            sidecar = package / ".impl-package"
            sidecar.mkdir(parents=True)
            (package / "plan.md").write_text(
                "执行组合（Composition）：tickets=false, dag=true\n", encoding="utf-8"
            )
            (package / "dag.md").write_text(
                "执行尝试 ID（Attempt ID）：initial\n"
                "- 修订集合（Revision set）：D1 / S1 / P1\n", encoding="utf-8"
            )
            (sidecar / "revision-bindings.json").write_text(json.dumps({
                "contractVersion": "3.2", "purpose": "internal-machine-sidecar", "ownerFacing": False,
                "current": {"decision": {"revision": "D1"}, "spec": {"revision": "S2"},
                            "attempt": {"id": "initial", "plan": "plan.md", "revision": "P2"}},
                "bindings": [],
            }), encoding="utf-8")
            with self.assertRaisesRegex(module.StateError, "DAG revision binding"):
                module._assert_attempt_decomposition_revision_bindings(
                    package, "initial", {"decision": "D1", "spec": "S2", "plan": "P2"}
                )

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
                "决策修订（Decision Revision）：N/A\n规格修订（Spec Revision）：N/A\n计划修订（Plan Revision）：P1\n"
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
                        "contractVersion": "3.2",
                        "purpose": "internal-machine-sidecar",
                        "ownerFacing": False,
                        "current": {},
                        "bindings": [],
                    }
                ),
                encoding="utf-8",
            )
            run_cli(package, "init", "--package-id", package.name)
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


class ExecutionRecordLedgerTest(unittest.TestCase):
    def _package(self, root: Path, composition: str = "tickets=false, dag=false") -> Path:
        repo = root / "repo"
        repo.mkdir()
        init_repo(repo)
        package = repo / "docs/implementations/260803-er"
        package.mkdir(parents=True)
        (package / "plan.md").write_text(
            "# Plan\n\n"
            "<!-- impl-package:projection revision-set begin -->\n"
            "决策修订（Decision Revision）：N/A\n"
            "规格修订（Spec Revision）：N/A\n"
            "计划修订（Plan Revision）：P1\n"
            "<!-- impl-package:projection revision-set end -->\n\n"
            f"执行组合（Composition）：{composition}\n",
            encoding="utf-8",
        )
        run_cli(package, "init", "--package-id", package.name)
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
        return package

    def test_er_add_is_idempotent_and_rebuilds_progress(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._package(Path(temp))
            payload = json.dumps(
                {
                    "purpose": "checkpoint",
                    "title": "ready seam",
                    "content": "The shared boundary is available.",
                    "nextAction": "run the downstream check",
                }
            )
            first = json.loads(run_cli(package, "er-add", input_text=payload).stdout)
            retry = json.loads(run_cli(package, "er-add", input_text=payload).stdout)
            self.assertEqual(first["recordId"], "initial-ER-001")
            self.assertTrue(retry["idempotent"])
            self.assertEqual(retry["recordId"], first["recordId"])
            self.assertIn("initial-ER-001", (package / "execution-records/index.md").read_text(encoding="utf-8"))
            progress = (package / "progress.md").read_text(encoding="utf-8")
            self.assertIn("Active Checkpoints", progress)
            self.assertIn("run the downstream check", progress)
            self.assertNotIn("## Execution Record", (package / "plan.md").read_text(encoding="utf-8"))
            run_cli(package, "validate", "--working-tree")

    def test_checkpoint_supersedes_by_subject_and_reusable_selection_is_validated(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._package(Path(temp))
            first = json.dumps(
                {
                    "purpose": "checkpoint",
                    "subject": "attempt",
                    "title": "recovery one",
                    "content": "first",
                    "nextAction": "continue",
                }
            )
            second = json.dumps(
                {
                    "purpose": "checkpoint",
                    "subject": "attempt",
                    "title": "recovery two",
                    "content": "second",
                    "nextAction": "continue",
                }
            )
            run_cli(package, "er-add", input_text=first)
            run_cli(package, "er-add", input_text=second)
            ledger = (package / "execution-records/initial.md").read_text(encoding="utf-8")
            self.assertIn("- Supersedes: initial-ER-001", ledger)
            invalid = run_cli(
                package,
                "er-add",
                check=False,
                input_text=json.dumps(
                    {
                        "purpose": "checkpoint",
                        "title": "bad reusable",
                        "content": "bad",
                        "nextAction": "stop",
                        "allowsDownstreamImplementation": True,
                        "downstream": ["task:T9"],
                    }
                ),
            )
            self.assertNotEqual(invalid.returncode, 0)
            self.assertIn("does not resolve", invalid.stderr)

    def test_sealed_record_tampering_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            package = self._package(Path(temp))
            run_cli(
                package,
                "er-add",
                input_text=json.dumps(
                    {
                        "purpose": "judgment",
                        "title": "observed failure",
                        "content": "provider returned a timeout",
                    }
                ),
            )
            ledger = package / "execution-records/initial.md"
            ledger.write_text(ledger.read_text(encoding="utf-8").replace("provider returned", "provider silently returned"), encoding="utf-8")
            failed = run_cli(package, "validate", "--working-tree", check=False)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("content hash mismatch", failed.stderr)


if __name__ == "__main__":
    unittest.main()
