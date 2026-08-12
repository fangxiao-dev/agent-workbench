from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_state.py"


def run(
    command: list[str],
    cwd: Path,
    *,
    ok: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(command, cwd=cwd, input=input_text, capture_output=True, text=True, check=False)
    if ok and result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result


def git(repo: Path, *args: str) -> str:
    return run(["git", *args], repo).stdout.strip()


class ImplPackageStateTests(unittest.TestCase):
    def make_repo(
        self,
        *,
        tickets: bool = False,
        dag: bool = False,
        second_task: bool = False,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Test")
        package = repo / "docs" / "implementations" / "260806-example"
        package.mkdir(parents=True)
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (package / "plan.md").write_text(
            "# Plan\n\nAttempt ID：initial\n"
            f"Composition：tickets={str(tickets).lower()}, dag={str(dag).lower()}\n",
            encoding="utf-8",
        )
        if tickets:
            directory = package / "tickets"
            directory.mkdir()
            self.write_ticket(directory / "01.md", "TKT-01")
        if dag:
            rows = ["| T1 | core | none | TKT-01 | none |"]
            if second_task:
                rows.append("| T2 | api | T1 | TKT-01 | seam |")
            (package / "dag.md").write_text(
                "# DAG\n\nAttempt ID：initial\n\n"
                "## Task graph\n\n| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |\n"
                "| --- | --- | --- | --- | --- |\n" + "\n".join(rows) + "\n",
                encoding="utf-8",
            )
        (repo / "evidence.md").write_text("proof\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return temp, repo, package

    def write_ticket(
        self,
        path: Path,
        identifier: str,
        *,
        attempt: str = "initial",
        dependency: str = "None",
    ) -> None:
        path.write_text(
            f"# Ticket\n\n**Ticket ID：** {identifier}\n"
            "**Publication Status：** Draft\n"
            f"**Attempt ID：** {attempt}\n"
            "\n"
            "## 验收标准\n\n- AC-1: works\n\n"
            f"## 阻塞依赖\n\n- {dependency}\n",
            encoding="utf-8",
        )

    def cli(
        self,
        repo: Path,
        package: Path,
        *args: str,
        ok: bool = True,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return run([sys.executable, str(CLI), "--package", str(package), *args], repo, ok=ok, input_text=input_text)

    def init(self, repo: Path, package: Path, *, attempt: str = "initial", plan: str = "plan.md") -> dict:
        relative = (package / plan).relative_to(repo).as_posix()
        return json.loads(self.cli(repo, package, "init", "--attempt", attempt, "--plan", relative).stdout)

    def state(self, package: Path) -> dict:
        return json.loads((package / ".impl-package" / "state.json").read_text(encoding="utf-8"))

    def set_state(
        self,
        repo: Path,
        package: Path,
        kind: str,
        identifier: str,
        state: str,
        expect: str,
        *,
        ok: bool = True,
    ) -> subprocess.CompletedProcess[str]:
        return self.cli(
            repo,
            package,
            "set-state",
            kind,
            identifier,
            state,
            "--expect",
            expect,
            "--evidence",
            "evidence.md",
            ok=ok,
        )

    def test_alignment_only_package_needs_no_state(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        result = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertEqual(result, {"active": False, "commit": None, "reason": "no-active-attempt"})

    def test_all_four_compositions_create_only_earned_surfaces(self) -> None:
        for tickets in (False, True):
            for dag in (False, True):
                with self.subTest(tickets=tickets, dag=dag):
                    temp, repo, package = self.make_repo(tickets=tickets, dag=dag)
                    try:
                        result = self.init(repo, package)
                        self.assertEqual(result["tickets"], 1 if tickets else 0)
                        self.assertEqual(result["tasks"], 1 if dag else 0)
                        self.assertEqual(set(self.state(package)), {"formatVersion", "attempt", "tasks", "tickets", "resume"})
                        self.assertEqual(self.state(package)["formatVersion"], "3.4")
                        self.assertTrue((package / "progress.md").is_file())
                        self.assertTrue((package / "execution/initial/execution-record.md").is_file())
                        self.assertFalse((package / "execution/index.md").exists())
                        progress = (package / "progress.md").read_text(encoding="utf-8")
                        self.assertEqual("## Ticket Acceptance" in progress, tickets)
                        self.assertEqual("## Task Execution" in progress, dag)
                    finally:
                        temp.cleanup()

    def test_init_filters_tickets_by_current_attempt_and_publishes_projection(self) -> None:
        temp, repo, package = self.make_repo(tickets=True)
        self.addCleanup(temp.cleanup)
        self.write_ticket(package / "tickets/old.md", "TKT-OLD", attempt="patch-old")
        self.init(repo, package)
        self.assertEqual(set(self.state(package)["tickets"]), {"TKT-01"})
        current = (package / "tickets/01.md").read_text(encoding="utf-8")
        old = (package / "tickets/old.md").read_text(encoding="utf-8")
        self.assertIn("**Publication Status：** Approved", current)
        self.assertNotIn("发布状态（Publication Status）", current)
        self.assertIn("Runtime Acceptance Status: PENDING", current)
        self.assertIn("**Publication Status：** Draft", old)

    def test_legacy_bilingual_labels_remain_readable(self) -> None:
        temp, repo, package = self.make_repo(tickets=True)
        self.addCleanup(temp.cleanup)
        replacements = {
            "Attempt ID": "执行尝试 ID（Attempt ID）",
            "Composition": "执行组合（Composition）",
            "Publication Status": "发布状态（Publication Status）",
        }
        for path in (
            package / "decision.md",
            package / "spec.md",
            package / "plan.md",
            package / "tickets/01.md",
        ):
            text = path.read_text(encoding="utf-8")
            for current, legacy in replacements.items():
                text = text.replace(current, legacy)
            path.write_text(text, encoding="utf-8")

        result = self.init(repo, package)
        self.assertEqual(result["tickets"], 1)
        current = (package / "tickets/01.md").read_text(encoding="utf-8")
        self.assertIn("**Publication Status：** Approved", current)
        self.assertNotIn("发布状态（Publication Status）", current)

    def test_revision_aliases_are_optional_and_nonbinding(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        status = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertEqual(status["revisions"], {"decision": None, "spec": None, "plan": None})
        plan = package / "plan.md"
        plan.write_text(plan.read_text(encoding="utf-8") + "\nclarification\n", encoding="utf-8")
        result = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertEqual(result["revisions"], {"decision": None, "spec": None, "plan": None})
        (package / "decision.md").write_text("# Decision\n\nDecision Revision：D9\n", encoding="utf-8")
        (package / "spec.md").write_text("# Spec\n\nDecision Revision：D8\nSpec Revision：S7\n", encoding="utf-8")
        plan.write_text(plan.read_text(encoding="utf-8") + "\nDecision Revision：D1\nSpec Revision：S1\nPlan Revision：P1\n", encoding="utf-8")
        self.cli(repo, package, "refresh-progress")
        result = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertEqual(result["revisions"], {"decision": "D1", "spec": "S1", "plan": "P1"})

    def test_active_attempt_still_requires_spec_document(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        (package / "spec.md").unlink()
        failed = self.cli(
            repo,
            package,
            "init",
            "--attempt",
            "initial",
            "--plan",
            (package / "plan.md").relative_to(repo).as_posix(),
            ok=False,
        )
        self.assertIn("spec.md is required", failed.stderr)

    def test_rejects_unsupported_format_and_non_date_package(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        path = package / ".impl-package/state.json"
        state = self.state(package)
        state["formatVersion"] = "3.3"
        path.write_text(json.dumps(state), encoding="utf-8")
        self.assertIn("expected '3.4'", self.cli(repo, package, "validate", ok=False).stderr)

        other = repo / "docs/implementations/no-date"
        other.mkdir()
        for name in ("decision.md", "spec.md", "plan.md"):
            (other / name).write_text((package / name).read_text(encoding="utf-8"), encoding="utf-8")
        relative = (other / "plan.md").relative_to(repo).as_posix()
        self.assertIn("date-prefixed", self.cli(repo, other, "init", "--attempt", "initial", "--plan", relative, ok=False).stderr)

    def test_cas_and_dependency_readiness(self) -> None:
        temp, repo, package = self.make_repo(dag=True, second_task=True)
        self.addCleanup(temp.cleanup)
        result = self.init(repo, package)
        self.assertEqual(result["readyTasks"], ["T1"])
        blocked = self.set_state(repo, package, "task", "T2", "READY", "PENDING", ok=False)
        self.assertIn("dependencies are not released", blocked.stderr)
        self.set_state(repo, package, "task", "T1", "DONE", "PENDING")
        self.set_state(repo, package, "task", "T2", "READY", "PENDING")
        stale = self.set_state(repo, package, "task", "T2", "RUNNING", "PENDING", ok=False)
        self.assertIn("expected PENDING, found READY", stale.stderr)

    def test_rejects_task_and_ticket_dependency_cycles(self) -> None:
        temp, repo, package = self.make_repo(dag=True, second_task=True)
        self.addCleanup(temp.cleanup)
        dag = package / "dag.md"
        dag.write_text(dag.read_text(encoding="utf-8").replace("| T1 | core | none |", "| T1 | core | T2 |"), encoding="utf-8")
        self.assertIn("contains a cycle", self.cli(repo, package, "init", "--attempt", "initial", "--plan", (package / "plan.md").relative_to(repo).as_posix(), ok=False).stderr)

        temp2, repo2, package2 = self.make_repo(tickets=True)
        self.addCleanup(temp2.cleanup)
        self.write_ticket(package2 / "tickets/02.md", "TKT-02", dependency="acceptance: TKT-01")
        first = package2 / "tickets/01.md"
        first.write_text(first.read_text(encoding="utf-8").replace("- None", "- acceptance: TKT-02"), encoding="utf-8")
        failed = self.cli(repo2, package2, "init", "--attempt", "initial", "--plan", (package2 / "plan.md").relative_to(repo2).as_posix(), ok=False)
        self.assertIn("contains a cycle", failed.stderr)

    def test_rejects_attempt_path_escape_and_missing_task_ownership(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        plan = package / "plan.md"
        plan.write_text(plan.read_text(encoding="utf-8").replace("initial", "../../escape"), encoding="utf-8")
        failed = self.cli(repo, package, "init", "--attempt", "../../escape", "--plan", plan.relative_to(repo).as_posix(), ok=False)
        self.assertIn("invalid Attempt ID", failed.stderr)
        self.assertFalse((repo.parent / "escape").exists())

        temp2, repo2, package2 = self.make_repo(dag=True)
        self.addCleanup(temp2.cleanup)
        dag = package2 / "dag.md"
        dag.write_text(dag.read_text(encoding="utf-8").replace("| T1 | core |", "| T1 |  |"), encoding="utf-8")
        failed = self.cli(repo2, package2, "init", "--attempt", "initial", "--plan", (package2 / "plan.md").relative_to(repo2).as_posix(), ok=False)
        self.assertIn("Primary ownership", failed.stderr)

    def test_task_done_does_not_accept_ticket_and_ticket_dependencies_are_enforced(self) -> None:
        temp, repo, package = self.make_repo(tickets=True, dag=True)
        self.addCleanup(temp.cleanup)
        self.write_ticket(package / "tickets/02.md", "TKT-02", dependency="acceptance: TKT-01")
        self.init(repo, package)
        self.set_state(repo, package, "task", "T1", "DONE", "PENDING")
        self.assertEqual(self.state(package)["tickets"]["TKT-01"]["state"], "PENDING")
        blocked = self.set_state(repo, package, "ticket", "TKT-02", "SATISFIED", "PENDING", ok=False)
        self.assertIn("dependencies are not released", blocked.stderr)
        self.set_state(repo, package, "ticket", "TKT-01", "SATISFIED", "PENDING")
        self.set_state(repo, package, "ticket", "TKT-02", "SATISFIED", "PENDING")

    def test_checkpoint_and_er_add_rebuild_progress_without_content_identity(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        first = json.loads(self.cli(repo, package, "checkpoint", "--next", "run focused test", "--blocker", "provider unavailable", "--evidence", "evidence.md").stdout)
        self.assertEqual(first["recordId"], "initial-ER-001")
        self.assertEqual(self.state(package)["resume"], {"blocker": "provider unavailable", "next": "run focused test", "evidence": "evidence.md"})
        payload = json.dumps({"purpose": "checkpoint", "subject": "attempt", "title": "Recovered", "content": "Provider is back.", "nextAction": "continue", "evidence": "evidence.md"})
        second = json.loads(self.cli(repo, package, "er-add", input_text=payload).stdout)
        retry = json.loads(self.cli(repo, package, "er-add", input_text=payload).stdout)
        self.assertEqual(second["recordId"], "initial-ER-002")
        self.assertTrue(retry["idempotent"])
        record = (package / "execution/initial/execution-record.md").read_text(encoding="utf-8")
        self.assertIn("- Supersedes: initial-ER-001", record)
        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("initial-ER-002", progress)
        self.assertIn("continue", progress)

    def test_judgment_does_not_change_resume(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.cli(repo, package, "checkpoint", "--next", "continue")
        before = self.state(package)["resume"]
        payload = json.dumps({"purpose": "judgment", "subject": "attempt", "title": "Boundary decision", "content": "Keep the adapter local."})
        self.cli(repo, package, "er-add", input_text=payload)
        self.assertEqual(self.state(package)["resume"], before)

    def test_refresh_progress_repairs_ticket_dag_progress_and_links_handoff(self) -> None:
        temp, repo, package = self.make_repo(tickets=True, dag=True)
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        handoff = package / "execution/initial/task-handoffs/T1-handoff.md"
        handoff.parent.mkdir(parents=True)
        handoff.write_text("# Task Handoff: T1\n", encoding="utf-8")
        (package / "progress.md").write_text("stale\n", encoding="utf-8")
        (package / "dag.md").write_text((package / "dag.md").read_text(encoding="utf-8").replace("| T1 | PENDING |", "| T1 | DONE |"), encoding="utf-8")
        self.cli(repo, package, "refresh-progress")
        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("execution/initial/task-handoffs/T1-handoff.md", progress)
        self.assertIn("| T1 | PENDING |", (package / "dag.md").read_text(encoding="utf-8"))
        self.cli(repo, package, "validate")

    def test_gate_requires_complete_state_and_explicit_stage7_result(self) -> None:
        temp, repo, package = self.make_repo(dag=True)
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        head = git(repo, "rev-parse", "HEAD")
        unfinished = self.cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "checks passed", "--no-durable-delta-reason", "no durable change", ok=False)
        self.assertIn("unfinished", unfinished.stderr)
        self.set_state(repo, package, "task", "T1", "DONE", "PENDING")
        missing_stage7 = self.cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "checks passed", ok=False)
        self.assertIn("no-durable-delta-reason", missing_stage7.stderr)
        result = json.loads(self.cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "checks passed", "--evidence", "evidence.md", "--no-durable-delta-reason", "no reusable delta").stdout)
        self.assertEqual(result["commit"], head)
        self.assertIn("- Lifecycle: frozen", (package / "execution/initial/execution-record.md").read_text(encoding="utf-8"))
        frozen = self.cli(repo, package, "checkpoint", "--next", "must fail", ok=False)
        self.assertIn("frozen", frozen.stderr)
        payload = json.dumps({"purpose": "judgment", "title": "Must fail", "content": "Frozen attempt."})
        self.assertIn("frozen", self.cli(repo, package, "er-add", input_text=payload, ok=False).stderr)
        self.assertIn("frozen", self.set_state(repo, package, "task", "T1", "WAIVED", "DONE", ok=False).stderr)
        (repo / "evidence.md").unlink()
        frozen_status = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertEqual(frozen_status["gate"]["verdict"], "pass")

    def test_terminal_gate_clears_resume_and_hides_historical_checkpoint(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.cli(repo, package, "checkpoint", "--next", "resume implementation", "--blocker", "waiting")
        head = git(repo, "rev-parse", "HEAD")

        self.cli(repo, package, "gate", "fail", "--comparison-commit", head, "--reason", "needs patch", "--no-durable-delta-reason", "implementation defect only")

        self.assertEqual(self.state(package)["resume"], {"blocker": None, "next": None, "evidence": None})
        record = (package / "execution/initial/execution-record.md").read_text(encoding="utf-8")
        self.assertIn("- Lifecycle: frozen", record)
        self.assertIn("initial-ER-001", record)
        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertNotIn("initial-ER-001", progress)
        self.assertIn("| none | attempt | none | none | none |", progress)
        self.assertIn("- Next action: none", progress)

    def test_idempotent_terminal_gate_repairs_legacy_resume_after_head_advances(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.cli(repo, package, "checkpoint", "--next", "resume implementation", "--blocker", "waiting")
        comparison = git(repo, "rev-parse", "HEAD")
        self.cli(repo, package, "gate", "fail", "--comparison-commit", comparison, "--reason", "needs patch", "--no-durable-delta-reason", "implementation defect only")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "record terminal runtime metadata")
        self.assertNotEqual(git(repo, "rev-parse", "HEAD"), comparison)

        state_path = package / ".impl-package/state.json"
        state = self.state(package)
        state["resume"] = {"blocker": "legacy blocker", "next": "legacy next", "evidence": "retired-evidence.md"}
        state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        progress_path = package / "progress.md"
        progress = progress_path.read_text(encoding="utf-8")
        progress = progress.replace("| none | attempt | none | none | none |", "| initial-ER-001 | attempt | active | resume implementation | none |")
        progress = progress.replace("- Blocker: none", "- Blocker: legacy blocker").replace("- Next action: none", "- Next action: legacy next")
        progress_path.write_text(progress, encoding="utf-8")

        result = json.loads(self.cli(repo, package, "gate", "fail", "--comparison-commit", comparison, "--reason", "retry", "--no-durable-delta-reason", "retry").stdout)
        self.assertTrue(result["idempotent"])
        self.assertEqual(self.state(package)["resume"], {"blocker": None, "next": None, "evidence": None})
        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("- Lifecycle: frozen", progress)
        self.assertIn("- Next action: none", progress)
        self.assertIn("| none | attempt | none | none | none |", progress)

    def test_terminal_gate_requires_current_head_but_blocked_accepts_older_commit(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        old_head = git(repo, "rev-parse", "HEAD")
        (repo / "later.md").write_text("later\n", encoding="utf-8")
        git(repo, "add", "later.md")
        git(repo, "commit", "-m", "advance head")
        current_head = git(repo, "rev-parse", "HEAD")

        rejected = self.cli(repo, package, "gate", "fail", "--comparison-commit", old_head, "--reason", "stale comparison", "--no-durable-delta-reason", "none", ok=False)
        self.assertIn("must equal current HEAD", rejected.stderr)
        blocked = json.loads(self.cli(repo, package, "gate", "blocked", "--comparison-commit", old_head, "--reason", "waiting").stdout)
        self.assertEqual(blocked["commit"], old_head)
        terminal = json.loads(self.cli(repo, package, "gate", "fail", "--comparison-commit", current_head, "--reason", "needs patch", "--no-durable-delta-reason", "none").stdout)
        self.assertEqual(terminal["commit"], current_head)

    def test_patch_attempt_keeps_light_attempt_history_in_progress(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        head = git(repo, "rev-parse", "HEAD")
        self.cli(repo, package, "gate", "fail", "--comparison-commit", head, "--reason", "needs patch", "--no-durable-delta-reason", "implementation defect only")
        (package / "patch-a.patch-plan.md").write_text(
            "# Patch Plan\n\nAttempt ID：patch-a\nDecision Revision：D1\nSpec Revision：S1\nPlan Revision：P2\nComposition：tickets=false, dag=false\n",
            encoding="utf-8",
        )
        result = self.init(repo, package, attempt="patch-a", plan="patch-a.patch-plan.md")
        self.assertIsNone(result["gate"])
        self.assertIsNone(json.loads(self.cli(repo, package, "status").stdout)["gate"])
        progress = (package / "progress.md").read_text(encoding="utf-8")
        self.assertIn("| initial | frozen | fail | execution/initial/execution-record.md |", progress)
        self.assertIn("| patch-a | active | open | execution/patch-a/execution-record.md |", progress)

    def test_patch_attempt_rollover_uses_frozen_plan_then_enforces_current_aliases(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        head = git(repo, "rev-parse", "HEAD")
        self.cli(repo, package, "gate", "fail", "--comparison-commit", head, "--reason", "requirements changed", "--no-durable-delta-reason", "superseded by patch")
        state_path = package / ".impl-package/state.json"
        legacy_state = self.state(package)
        legacy_state["resume"] = {"blocker": "legacy", "next": "start patch", "evidence": "retired-evidence.md"}
        state_path.write_text(json.dumps(legacy_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        decision = package / "decision.md"
        spec = package / "spec.md"
        decision.write_text(decision.read_text(encoding="utf-8") + "\nupdated direction\n", encoding="utf-8")
        spec.write_text(spec.read_text(encoding="utf-8") + "\nupdated contract\n", encoding="utf-8")
        frozen_retry = self.init(repo, package)
        self.assertEqual(frozen_retry["attempt"], "initial")
        self.assertEqual(frozen_retry["gate"]["verdict"], "fail")
        legacy_state = self.state(package)
        legacy_state["resume"] = {"blocker": "legacy", "next": "start patch", "evidence": "retired-evidence.md"}
        state_path.write_text(json.dumps(legacy_state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (package / "patch-a.patch-plan.md").write_text(
            "# Patch Plan\n\nAttempt ID：patch-a\nComposition：tickets=false, dag=false\n",
            encoding="utf-8",
        )

        result = self.init(repo, package, attempt="patch-a", plan="patch-a.patch-plan.md")
        self.assertEqual(result["attempt"], "patch-a")
        self.assertEqual(result["revisions"], {"decision": None, "spec": None, "plan": None})
        self.assertIn("- Lifecycle: frozen", (package / "execution/initial/execution-record.md").read_text(encoding="utf-8"))

        spec.write_text(spec.read_text(encoding="utf-8") + "\nfollow-up clarification\n", encoding="utf-8")
        self.cli(repo, package, "validate")

    def test_existing_execution_findings_must_be_routed_before_terminal_gate(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        (package / "execution-findings.md").write_text("# Findings\n", encoding="utf-8")
        head = git(repo, "rev-parse", "HEAD")
        failed = self.cli(repo, package, "gate", "defer", "--comparison-commit", head, "--reason", "owner deferred", "--no-durable-delta-reason", "none", ok=False)
        self.assertIn("execution-findings.md", failed.stderr)
        relative = (package / "execution-findings.md").relative_to(repo).as_posix()
        self.cli(repo, package, "gate", "defer", "--comparison-commit", head, "--reason", "owner deferred", "--evidence", relative, "--no-durable-delta-reason", "none")

    def test_rejects_absolute_parent_and_missing_evidence_paths(self) -> None:
        temp, repo, package = self.make_repo(dag=True)
        self.addCleanup(temp.cleanup)
        absolute = self.cli(repo, package, "init", "--attempt", "initial", "--plan", str(package / "plan.md"), ok=False)
        self.assertIn("repository-relative", absolute.stderr)
        self.init(repo, package)
        for value in ("../evidence.md", "missing.md"):
            failed = self.cli(repo, package, "set-state", "task", "T1", "DONE", "--expect", "PENDING", "--evidence", value, ok=False)
            self.assertNotEqual(failed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
