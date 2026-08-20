from __future__ import annotations

import json
import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "tests" / "fixtures" / "impl-package-ticket-first"
CLI = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_state.py"


def run(command: list[str], cwd: Path, *, ok: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, input=input_text, capture_output=True, text=True, check=False)
    if ok and result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo).stdout.strip()


class TicketFirstContractTests(unittest.TestCase):
    def test_grouped_router_help_and_legacy_alias_surface(self) -> None:
        runtime = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_runtime"
        self.assertTrue((runtime / "command_groups.py").is_file())
        for adapter in ("package_commands.py", "ticket_commands.py", "evidence_commands.py", "recovery_commands.py", "gate_commands.py", "cli_support.py"):
            self.assertFalse((runtime / adapter).exists(), adapter)

        root_help = run([sys.executable, str(CLI), "--package", "fixture", "--help"], ROOT).stdout
        for group in ("package", "ticket", "evidence", "recovery", "gate"):
            self.assertIn(group, root_help)
        for legacy in ("set-state", "evidence-add", "checkpoint", "er-add"):
            self.assertNotIn(legacy, root_help)

        ticket_help = run([sys.executable, str(CLI), "--package", "fixture", "ticket", "satisfy", "--help"], ROOT).stdout
        self.assertIn("--revision", ticket_help)
        self.assertIn("--environment", ticket_help)
        self.assertNotIn("--successor", ticket_help)

        package_help = run([sys.executable, str(CLI), "--package", "fixture", "package", "--help"], ROOT).stdout
        self.assertIn("init", package_help)
        self.assertIn("refresh-progress", package_help)
        evidence_help = run([sys.executable, str(CLI), "--package", "fixture", "evidence", "--help"], ROOT).stdout
        self.assertIn("add", evidence_help)
        self.assertIn("invalidate", evidence_help)
        recovery_help = run([sys.executable, str(CLI), "--package", "fixture", "recovery", "--help"], ROOT).stdout
        self.assertIn("checkpoint", recovery_help)
        self.assertIn("judgment", recovery_help)
        gate_help = run([sys.executable, str(CLI), "--package", "fixture", "gate", "--help"], ROOT).stdout
        self.assertIn("pass", gate_help)
        gate_pass_help = run([sys.executable, str(CLI), "--package", "fixture", "gate", "pass", "--help"], ROOT).stdout
        self.assertIn("--comparison-commit", gate_pass_help)
        legacy_gate_help = run(
            [sys.executable, str(CLI), "--package", "fixture", "gate", "--comparison-commit", "abc", "--reason", "r", "pass", "--help"],
            ROOT,
        )
        self.assertEqual(legacy_gate_help.returncode, 0)
        self.assertIn("--comparison-commit", legacy_gate_help.stdout)
        abbreviated_gate_help = run(
            [
                sys.executable,
                str(CLI),
                "--package",
                "fixture",
                "gate",
                "--reas",
                "r",
                "--comparison-commit",
                "abc",
                "pass",
                "--help",
            ],
            ROOT,
        )
        self.assertEqual(abbreviated_gate_help.returncode, 0)
        self.assertIn("--comparison-commit", abbreviated_gate_help.stdout)

        spec = importlib.util.spec_from_file_location("ticket_first_cli", CLI)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertIn("compositionPattern", module.CONFIG["documents"])

    def test_grouped_package_init_and_ticket_satisfy_match_legacy_engine(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first grouped fixture")
        package = repo / "docs" / "implementations" / "260813-grouped"
        (package / "tickets").mkdir(parents=True)
        shutil.copy2(FIXTURE / "ticket-only-plan.md", package / "plan.md")
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
        for source in (FIXTURE / "tickets").glob("*.md"):
            shutil.copy2(source, package / "tickets" / source.name)
        (repo / "evidence.md").write_text("grouped fixture evidence\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "grouped fixture")
        relative_plan = (package / "plan.md").relative_to(repo).as_posix()

        initialized = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "package", "init", "--attempt", "initial", "--plan", relative_plan],
                repo,
            ).stdout
        )
        self.assertEqual(initialized["formatVersion"], "3.5")
        revision = git(repo, "rev-parse", "HEAD")
        index = json.loads((FIXTURE / "evidence" / "index.json").read_text(encoding="utf-8"))
        for source in index["records"]:
            record = dict(source)
            record.update({"artifact": "evidence.md", "revision": revision, "environment": "grouped"})
            run([sys.executable, str(CLI), "--package", str(package), "evidence", "add"], repo, input_text=json.dumps(record))

        grouped = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "ticket", "satisfy", "TKT-01", "--expect", "PENDING", "--revision", revision, "--environment", "grouped"],
                repo,
            ).stdout
        )
        legacy = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "set-state", "ticket", "TKT-02", "SATISFIED", "--expect", "PENDING", "--revision", revision, "--environment", "grouped"],
                repo,
            ).stdout
        )
        self.assertEqual(grouped["state"], legacy["state"])
        state = json.loads((package / ".impl-package" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tickets"]["TKT-01"]["state"], "SATISFIED")
        self.assertEqual(state["tickets"]["TKT-02"]["state"], "SATISFIED")

    def test_fixture_declares_ticket_only_edges_claim_timing_and_safety(self) -> None:
        plan = (FIXTURE / "ticket-only-plan.md").read_text(encoding="utf-8")
        self.assertIn("Composition：tickets=true, dag=false", plan)
        self.assertNotIn("dag.md", plan)

        typed_edges: set[str] = set()
        ticket_ids: set[str] = set()
        claim_keys: set[tuple[str, str]] = set()
        timing_values: set[str] = set()
        for path in sorted((FIXTURE / "tickets").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            identifier = re.search(r"\*\*Ticket ID：\*\*\s*(\S+)", text)
            self.assertIsNotNone(identifier, path)
            ticket_id = identifier.group(1)
            ticket_ids.add(ticket_id)
            claims = re.findall(r"Stable claim ID：`([^`]+)`", text)
            self.assertTrue(claims, path)
            self.assertEqual(len(claims), len(set(claims)), path)
            claim_keys.update((ticket_id, claim) for claim in claims)
            timings = re.findall(r"证据时机：`([^`]+)`", text)
            self.assertTrue(timings, path)
            self.assertTrue(set(timings) <= {"early-falsification", "remaining-completion"}, path)
            timing_values.update(timings)
            for label in ("tenant", "RBAC / privacy", "幂等 / 数据完整性"):
                value = re.search(rf"^- {re.escape(label)}：(.+)$", text, re.MULTILINE)
                self.assertIsNotNone(value, path)
                self.assertTrue(value.group(1).strip() and not value.group(1).strip().startswith("<"), path)
            for edge in re.findall(r"^- (implementation|acceptance|release):\s*(\S+)$", text, re.MULTILINE):
                typed_edges.add(edge[0])
                self.assertIn(edge[1], {"TKT-01", "TKT-02", "TKT-03", "TKT-04"})

        self.assertEqual(ticket_ids, {"TKT-01", "TKT-02", "TKT-03", "TKT-04"})
        self.assertEqual(typed_edges, {"implementation", "acceptance", "release"})
        self.assertEqual(timing_values, {"early-falsification", "remaining-completion"})

        index = json.loads((FIXTURE / "evidence" / "index.json").read_text(encoding="utf-8"))
        records = index["records"]
        self.assertEqual(
            {(item["ticket"], item["claim"]) for item in records},
            claim_keys,
        )
        for item in records:
            self.assertEqual(item["revision"], index["revision"])
            self.assertEqual(item["environment"], index["environment"])
            for field in ("ticket", "claim", "revision", "environment", "timing", "artifact", "conclusion"):
                self.assertTrue(item.get(field), item)
            self.assertIn(item["timing"], {"early-falsification", "remaining-completion"})
            self.assertEqual(item["conclusion"], "supporting")
            artifact, _, anchor = item["artifact"].partition("#")
            artifact_path = FIXTURE / artifact
            self.assertTrue(artifact_path.is_file(), item)
            if anchor:
                self.assertIn(anchor.lower(), artifact_path.read_text(encoding="utf-8").lower(), item)

        incomplete = {**index, "records": records[:-1]}
        self.assertNotEqual({(item["ticket"], item["claim"]) for item in incomplete["records"]}, claim_keys)

    def test_ticket_only_runtime_keeps_strict_ready_barrier_without_task_surface(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first fixture")

        package = repo / "docs" / "implementations" / "260813-ticket-first"
        (package / "tickets").mkdir(parents=True)
        (package / "plan.md").write_text((FIXTURE / "ticket-only-plan.md").read_text(encoding="utf-8"), encoding="utf-8")
        for source in (FIXTURE / "tickets").glob("*.md"):
            shutil.copy2(source, package / "tickets" / source.name)
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (repo / "evidence.md").write_text("verified artifact\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")

        relative_plan = (package / "plan.md").relative_to(repo).as_posix()
        result = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "init", "--attempt", "initial", "--plan", relative_plan],
                repo,
            ).stdout
        )
        self.assertEqual(result["tasks"], 0)
        self.assertEqual(result["tickets"], 4)
        self.assertEqual(result["readyTickets"], ["TKT-01", "TKT-03", "TKT-04"])
        self.assertFalse((package / "dag.md").exists())
        self.assertFalse((package / "execution" / "initial" / "task-handoffs").exists())

        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("## Ticket Acceptance", progress)
        self.assertNotIn("## Task Execution", progress)

        evidence_index = json.loads((FIXTURE / "evidence" / "index.json").read_text(encoding="utf-8"))
        fixture_revision = git(repo, "rev-parse", "HEAD")
        for source in evidence_index["records"]:
            record = dict(source)
            record.update({"artifact": "evidence.md", "revision": fixture_revision, "environment": "ticket-first-contract-fixture"})
            run(
                [sys.executable, str(CLI), "--package", str(package), "evidence-add"],
                repo,
                input_text=json.dumps(record),
            )

        blocked = run(
            [
                sys.executable,
                str(CLI),
                "--package",
                str(package),
                "set-state",
                "ticket",
                "TKT-03",
                "SATISFIED",
                "--expect",
                "PENDING",
                "--revision",
                fixture_revision,
                "--environment",
                "ticket-first-contract-fixture",
            ],
            repo,
            ok=False,
        )
        self.assertIn("dependencies are not released", blocked.stderr)

        release = run(
            [
                sys.executable,
                str(CLI),
                "--package",
                str(package),
                "set-state",
                "ticket",
                "TKT-04",
                "SATISFIED",
                "--expect",
                "PENDING",
                "--revision",
                fixture_revision,
                "--environment",
                "ticket-first-contract-fixture",
            ],
            repo,
        )
        self.assertEqual(json.loads(release.stdout)["state"], "SATISFIED")
        gate = run(
            [
                sys.executable,
                str(CLI),
                "--package",
                str(package),
                "gate",
                "pass",
                "--comparison-commit",
                git(repo, "rev-parse", "HEAD"),
                "--reason",
                "release edge still has an unfinished upstream ticket",
                "--no-durable-delta-reason",
                "fixture only",
            ],
            repo,
            ok=False,
        )
        self.assertIn("unfinished", gate.stderr)

    def test_migration_fixture_rejects_handoff_as_proof_and_preserves_authority(self) -> None:
        legacy = json.loads((FIXTURE / "migration" / "legacy-state.json").read_text(encoding="utf-8"))
        candidate = json.loads((FIXTURE / "migration" / "expected-candidate.json").read_text(encoding="utf-8"))
        handoff = (FIXTURE / "migration" / "legacy-task-handoff.md").read_text(encoding="utf-8")
        execution_record = (FIXTURE / "migration" / "legacy-execution-record.md").read_text(encoding="utf-8")

        self.assertEqual(legacy["formatVersion"], "3.4")
        self.assertEqual(candidate["composition"], {"tickets": True, "dag": False})
        self.assertEqual(candidate["taskArtifacts"], [])
        self.assertEqual(candidate["legacyArchive"], "migration/archive/task-handoffs/T1-handoff.md")
        self.assertIn("evidence/source-output.md", candidate["evidenceSources"])
        self.assertIn("execution/initial/task-handoffs/T1-handoff.md", candidate["rejectedEvidence"])
        self.assertIn("not acceptance evidence", handoff)
        self.assertIn("evidence/source-output.md", execution_record)
        retired = candidate["retiredExamples"]
        self.assertEqual({item["disposition"] for item in retired}, {"waived", "superseded"})
        self.assertEqual(retired[0]["state"], "RETIRED")
        self.assertEqual(retired[1]["successor"], "TKT-02")
        self.assertEqual(
            {item["authority"] for item in candidate["interruptions"] if item["point"] != "after-switch"},
            {"pre-migration-anchor"},
        )
        self.assertEqual(candidate["interruptions"][-1]["authority"], "single-migration-commit")

    def test_migration_fixture_models_staging_interruptions_and_single_switch(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name) / "repo"
        repo.mkdir()
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first migration fixture")

        package = repo / "package"
        (package / ".impl-package").mkdir(parents=True)
        (package / "execution" / "initial" / "task-handoffs").mkdir(parents=True)
        (package / "evidence").mkdir()
        shutil.copy2(FIXTURE / "migration" / "legacy-state.json", package / ".impl-package" / "state.json")
        shutil.copy2(FIXTURE / "migration" / "legacy-task-handoff.md", package / "execution" / "initial" / "task-handoffs" / "T1-handoff.md")
        shutil.copy2(FIXTURE / "migration" / "legacy-execution-record.md", package / "execution" / "initial" / "execution-record.md")
        shutil.copy2(FIXTURE / "migration" / "evidence" / "source-output.md", package / "evidence" / "source-output.md")
        (repo / "README.md").write_text("legacy package\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "legacy package")
        pre_anchor = git(repo, "rev-parse", "HEAD")
        legacy_state = (package / ".impl-package" / "state.json").read_text(encoding="utf-8")

        candidate_state = json.loads((FIXTURE / "migration" / "candidate-state.json").read_text(encoding="utf-8"))

        stage_number = 0

        def stage_candidate(*, include_index: bool) -> Path:
            nonlocal stage_number
            stage_number += 1
            staging = Path(temp.name) / f"staging-{stage_number}-{include_index}"
            shutil.copytree(package, staging)
            (staging / ".impl-package" / "state.json").write_text(json.dumps(candidate_state, indent=2) + "\n", encoding="utf-8")
            if include_index:
                shutil.copy2(FIXTURE / "evidence" / "index.json", staging / "evidence" / "index.json")
                archive = staging / "migration" / "archive" / "task-handoffs"
                archive.mkdir(parents=True)
                shutil.copy2(
                    staging / "execution" / "initial" / "task-handoffs" / "T1-handoff.md",
                    archive / "T1-handoff.md",
                )
                shutil.rmtree(staging / "execution" / "initial" / "task-handoffs")
            return staging

        def validate_candidate(staging: Path) -> None:
            state = json.loads((staging / ".impl-package" / "state.json").read_text(encoding="utf-8"))
            self.assertEqual(state["composition"], {"tickets": True, "dag": False})
            self.assertEqual(state["tasks"], {})
            self.assertTrue((staging / state["evidenceIndex"]).is_file())
            self.assertTrue((staging / state["legacyArchive"]).is_file())
            self.assertFalse((staging / "execution" / "initial" / "task-handoffs").exists())
            index_text = (staging / state["evidenceIndex"]).read_text(encoding="utf-8")
            self.assertNotIn("task-handoffs/", index_text)

        # Before validation, during validation, and after validation-before-switch all
        # leave the package and Git authority at the pre-migration anchor.
        stage_candidate(include_index=True)
        self.assertEqual(git(repo, "rev-parse", "HEAD"), pre_anchor)
        self.assertEqual((package / ".impl-package" / "state.json").read_text(encoding="utf-8"), legacy_state)

        invalid = stage_candidate(include_index=False)
        with self.assertRaises(AssertionError):
            validate_candidate(invalid)
        self.assertEqual(git(repo, "rev-parse", "HEAD"), pre_anchor)
        self.assertEqual((package / ".impl-package" / "state.json").read_text(encoding="utf-8"), legacy_state)

        valid = stage_candidate(include_index=True)
        validate_candidate(valid)
        self.assertEqual(git(repo, "rev-parse", "HEAD"), pre_anchor)
        self.assertEqual((package / ".impl-package" / "state.json").read_text(encoding="utf-8"), legacy_state)

        shutil.rmtree(package)
        shutil.copytree(valid, package)
        git(repo, "add", ".")
        git(repo, "commit", "-m", "ticket-first migration")
        migration_commit = git(repo, "rev-parse", "HEAD")
        self.assertNotEqual(migration_commit, pre_anchor)
        self.assertEqual(git(repo, "rev-parse", "HEAD^"), pre_anchor)
        validate_candidate(package)

    def test_stage_a_docs_mark_legacy_task_and_checkpoint_boundaries(self) -> None:
        composition = (ROOT / "plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md").read_text(encoding="utf-8")
        planning = (ROOT / "plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md").read_text(encoding="utf-8")
        dag = (ROOT / "plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md").read_text(encoding="utf-8")
        handoff = (ROOT / "skills/handoff-to-new-session/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("dag=false", composition)
        self.assertIn("RETIRED", composition)
        self.assertIn("early falsification evidence", composition)
        self.assertIn("新 package 一律不创建 Task DAG", dag)
        self.assertIn("owner 明确授权恢复/迁移已有 3.4 package", dag)
        self.assertIn("不把 Task handoff 或 `DONE` 当 acceptance proof", dag)
        self.assertIn("active checkpoint", handoff)
        self.assertIn("context compaction is only an emergency fallback", handoff)
        self.assertIn("新 package 不调用 `create-task-dag`", planning)


if __name__ == "__main__":
    unittest.main()
