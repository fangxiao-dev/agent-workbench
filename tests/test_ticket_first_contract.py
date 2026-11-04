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
FIXTURE = ROOT / "tests" / "fixtures" / "impl-package-state"
PLUGIN = ROOT / "plugin-marketplace" / "plugins" / "impl-package"
CLI = PLUGIN / "scripts" / "impl_package_state.py"


def run(command: list[str], cwd: Path, *, ok: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, input=input_text, capture_output=True, text=True, check=False)
    if ok and result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo).stdout.strip()


class TicketFirstContractTests(unittest.TestCase):
    def test_grouped_router_help_and_flat_aliases_removed(self) -> None:
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

    def test_grouped_package_init_and_ticket_satisfy_reject_flat_spelling(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first grouped fixture")
        package = repo / "docs" / "implementations" / "260813-grouped"
        (package / "tickets").mkdir(parents=True)
        shutil.copy2(FIXTURE / "plan.md", package / "plan.md")
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        shutil.copy2(FIXTURE / "spec.md", package / "spec.md")
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
        self.assertEqual(initialized["formatVersion"], "3.6")
        revision = git(repo, "rev-parse", "HEAD")

        grouped = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "ticket", "satisfy", "TKT-04", "--expect", "PENDING", "--revision", revision, "--environment", "grouped"],
                repo,
            ).stdout
        )
        flat = run(
            [sys.executable, str(CLI), "--package", str(package), "set-state", "ticket", "TKT-03", "SATISFIED", "--expect", "PENDING", "--revision", revision, "--environment", "grouped"],
            repo,
            ok=False,
        )
        self.assertIn("unknown command group", flat.stderr)
        self.assertEqual(grouped["state"], "SATISFIED")
        state = json.loads((package / ".impl-package" / "state.json").read_text(encoding="utf-8"))
        self.assertEqual(state["tickets"]["TKT-04"]["state"], "SATISFIED")
        self.assertEqual(state["tickets"]["TKT-03"]["state"], "PENDING")

    def test_fixture_declares_ticket_only_edges_and_journey_coverage(self) -> None:
        plan = (FIXTURE / "plan.md").read_text(encoding="utf-8")
        self.assertIn("Composition：tickets=true, dag=false", plan)
        self.assertIn("Acceptance: journey", plan)
        self.assertNotIn("dag.md", plan)

        typed_edges: set[str] = set()
        ticket_ids: set[str] = set()
        for path in sorted((FIXTURE / "tickets").glob("*.md")):
            text = path.read_text(encoding="utf-8")
            identifier = re.search(r"\*\*Ticket ID：\*\*\s*(\S+)", text)
            self.assertIsNotNone(identifier, path)
            ticket_ids.add(identifier.group(1))
            self.assertNotIn("Stable claim ID", text, path)
            for label in ("Journey steps", "Suites", "Required review"):
                self.assertRegex(text, rf"(?m)^- {label}: \S+", path)
            for edge in re.findall(r"^- (implementation|acceptance|release):\s*(\S+)$", text, re.MULTILINE):
                typed_edges.add(edge[0])
                self.assertIn(edge[1], {"TKT-01", "TKT-02", "TKT-03", "TKT-04"})

        self.assertEqual(ticket_ids, {"TKT-01", "TKT-02", "TKT-03", "TKT-04"})
        self.assertEqual(typed_edges, {"implementation", "acceptance", "release"})

    def test_journey_coverage_is_owned_across_planning_review_and_execution(self) -> None:
        composition = (PLUGIN / "references/impl-package-composition-contract.md").read_text(encoding="utf-8")
        planning = (PLUGIN / "skills/impl-planning/SKILL.md").read_text(encoding="utf-8")
        review = (PLUGIN / "skills/plan-review/SKILL.md").read_text(encoding="utf-8")
        execution = (PLUGIN / "skills/dev-with-track/SKILL.md").read_text(encoding="utf-8")

        self.assertNotIn("stable claim", composition.lower())
        self.assertIn("Journey step 与套件归属写进 Ticket 的 Coverage", planning)
        self.assertIn("被某张 Ticket 的 Coverage 认领", review)
        self.assertIn("../../references/impl-package-composition-contract.md", review)
        self.assertIn("逐条核对 claim 与 evidence", execution)

    def test_v36_journey_coverage_and_walking_skeleton_contract_is_present(self) -> None:
        composition = (PLUGIN / "references/impl-package-composition-contract.md").read_text(encoding="utf-8")
        ticket = (PLUGIN / "skills/impl-planning/assets/templates/ticket.md").read_text(encoding="utf-8")
        planning = (PLUGIN / "skills/impl-planning/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("## 7. 3.6 Journey 验收合同", composition)
        self.assertIn("## Coverage", ticket)
        self.assertIn("walking skeleton", planning)
        self.assertIn("没有既无 step 也无套件的 Ticket", planning)

    def test_ticket_only_runtime_keeps_strict_ready_barrier_without_task_surface(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first fixture")

        package = repo / "docs" / "implementations" / "260813-ticket-first"
        (package / "tickets").mkdir(parents=True)
        (package / "plan.md").write_text((FIXTURE / "plan.md").read_text(encoding="utf-8"), encoding="utf-8")
        for source in (FIXTURE / "tickets").glob("*.md"):
            shutil.copy2(source, package / "tickets" / source.name)
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        shutil.copy2(FIXTURE / "spec.md", package / "spec.md")
        (repo / "evidence.md").write_text("verified artifact\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")

        relative_plan = (package / "plan.md").relative_to(repo).as_posix()
        result = json.loads(
            run(
                [sys.executable, str(CLI), "--package", str(package), "package", "init", "--attempt", "initial", "--plan", relative_plan],
                repo,
            ).stdout
        )
        self.assertEqual(result["tasks"], 0)
        self.assertEqual(result["tickets"], 4)
        self.assertEqual(result["readyTickets"], ["TKT-01", "TKT-03", "TKT-04"])
        self.assertFalse((package / "dag.md").exists())
        self.assertFalse((package / "execution" / "initial" / "task-handoffs").exists())

        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("## Ticket Status", progress)
        self.assertNotIn("## Task Execution", progress)

        fixture_revision = git(repo, "rev-parse", "HEAD")
        satisfy = [sys.executable, str(CLI), "--package", str(package), "ticket", "satisfy"]
        blocked = run(
            [*satisfy, "TKT-03", "--expect", "PENDING", "--revision", fixture_revision],
            repo,
            ok=False,
        )
        self.assertIn("dependencies are not released", blocked.stderr)

        release = run([*satisfy, "TKT-04", "--expect", "PENDING", "--revision", fixture_revision], repo)
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
        self.assertIn("Required Ticket TKT-01", gate.stderr)
        self.assertIn("release 入边 TKT-01 未释放", gate.stderr)

    def test_stage_a_docs_mark_legacy_task_and_checkpoint_boundaries(self) -> None:
        composition = (ROOT / "plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md").read_text(encoding="utf-8")
        planning = (ROOT / "plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md").read_text(encoding="utf-8")
        dag = (ROOT / "plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md").read_text(encoding="utf-8")
        handoff = (ROOT / "skills/handoff/references/impl-package.md").read_text(encoding="utf-8")

        self.assertNotIn("dag=false", composition)
        self.assertIn("RETIRED", composition)
        self.assertIn("`formatVersion` 不是 3.6 的旧 package 不再支持", dag)
        self.assertIn("/impl-package:dev-with-track", handoff)
        self.assertIn("不复制 Ticket 状态", handoff)
        self.assertNotIn("dag=", planning)

    def make_validate_package(
        self,
        *,
        decision: str = "# Decision\n",
        spec: str | None = None,
        contract: str = "# Contract design\n",
        plan_suffix: str = "",
        ticket_edits: dict[str, list[tuple[str, str]]] | None = None,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Validate findings fixture")
        package = repo / "docs" / "implementations" / "260813-validate-findings"
        (package / "tickets").mkdir(parents=True)
        plan = (FIXTURE / "plan.md").read_text(encoding="utf-8") + plan_suffix
        (package / "plan.md").write_text(plan, encoding="utf-8")
        (package / "decision.md").write_text(decision, encoding="utf-8")
        (package / "spec.md").write_text(spec if spec is not None else (FIXTURE / "spec.md").read_text(encoding="utf-8"), encoding="utf-8")
        (package / "contract-design.md").write_text(contract, encoding="utf-8")
        for source in (FIXTURE / "tickets").glob("*.md"):
            text = source.read_text(encoding="utf-8")
            for old, new in (ticket_edits or {}).get(source.name, []):
                text = text.replace(old, new)
            (package / "tickets" / source.name).write_text(text, encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "validate findings fixture")
        relative_plan = (package / "plan.md").relative_to(repo).as_posix()
        run(
            [
                sys.executable,
                str(CLI),
                "--package",
                str(package),
                "package",
                "init",
                "--attempt",
                "initial",
                "--plan",
                relative_plan,
            ],
            repo,
        )
        return temp, repo, package

    def validate_findings(self, repo: Path, package: Path) -> list[dict]:
        result = run([sys.executable, str(CLI), "--package", str(package), "package", "validate"], repo)
        return json.loads(result.stdout)["findings"]

    def test_validate_reports_ticket_names_in_contract_documents(self) -> None:
        temp, repo, package = self.make_validate_package(
            decision="# Decision\nTKT-01 TKT-02 TKT-01\n",
            spec=(FIXTURE / "spec.md").read_text(encoding="utf-8") + "\nTKT-03\n",
            contract="# Contract\nTKT-04 TKT-04\n",
        )
        self.addCleanup(temp.cleanup)

        findings = [item for item in self.validate_findings(repo, package) if item["code"] == "contract-doc-names-ticket"]

        self.assertEqual({item["path"] for item in findings}, {"decision.md", "spec.md", "contract-design.md"})
        by_path = {item["path"]: item for item in findings}
        self.assertEqual((by_path["decision.md"]["hitCount"], by_path["decision.md"]["ticketIds"]), (3, ["TKT-01", "TKT-02"]))
        self.assertEqual((by_path["spec.md"]["hitCount"], by_path["spec.md"]["ticketIds"]), (1, ["TKT-03"]))
        self.assertEqual((by_path["contract-design.md"]["hitCount"], by_path["contract-design.md"]["ticketIds"]), (2, ["TKT-04"]))

    def test_validate_omits_ticket_names_finding_without_published_ids(self) -> None:
        temp, repo, package = self.make_validate_package()
        self.addCleanup(temp.cleanup)

        findings = self.validate_findings(repo, package)

        self.assertNotIn("contract-doc-names-ticket", {item["code"] for item in findings})

    def test_validate_reports_prose_gate_only_for_acceptance_inbound_edges(self) -> None:
        temp, repo, package = self.make_validate_package(
            plan_suffix="\nB失败时不进入 TKT-04。\nA失败时不派发 TKT-01。\n",
            ticket_edits={"03-verify.md": [("- acceptance: TKT-01", "- acceptance: TKT-04")]},
        )
        self.addCleanup(temp.cleanup)

        findings = [item for item in self.validate_findings(repo, package) if item["code"] == "plan-prose-gates-acceptance-edge"]
        by_ticket = {item["ticket"]: item for item in findings}

        self.assertEqual(by_ticket["TKT-04"]["inboundTypes"], ["acceptance"])
        self.assertIn("不进入 TKT-04", by_ticket["TKT-04"]["detail"])
        self.assertNotIn("TKT-01", by_ticket)

    def test_validate_omits_prose_gate_finding_without_gate_wording(self) -> None:
        temp, repo, package = self.make_validate_package(
            plan_suffix="\nCheckpoint B 记录 TKT-04 的结果。\n",
            ticket_edits={"03-verify.md": [("- acceptance: TKT-01", "- acceptance: TKT-04")]},
        )
        self.addCleanup(temp.cleanup)

        findings = [item for item in self.validate_findings(repo, package) if item["code"] == "plan-prose-gates-acceptance-edge"]

        self.assertEqual(findings, [])

    def test_validate_reports_ticket_without_any_arrival_path(self) -> None:
        temp, repo, package = self.make_validate_package()
        self.addCleanup(temp.cleanup)

        findings = [item for item in self.validate_findings(repo, package) if item["code"] == "ticket-arrival-path-absent"]

        self.assertEqual({item["ticket"] for item in findings}, {"TKT-01", "TKT-02", "TKT-03", "TKT-04"})
        self.assertTrue(all(item["path"].startswith("tickets/") for item in findings))

    def test_validate_omits_arrival_finding_when_a_path_is_declared(self) -> None:
        temp, repo, package = self.make_validate_package(
            ticket_edits={"01-source.md": [("\n## Coverage\n", "\n- 到达路径：entry → NEW: FixtureEntry → arrival\n\n## Coverage\n")]},
        )
        self.addCleanup(temp.cleanup)

        findings = [item for item in self.validate_findings(repo, package) if item["code"] == "ticket-arrival-path-absent"]

        self.assertNotIn("TKT-01", {item["ticket"] for item in findings})
        self.assertEqual(len(findings), 3)


if __name__ == "__main__":
    unittest.main()
