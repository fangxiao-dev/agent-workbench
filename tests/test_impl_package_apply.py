from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
APPLY_SCRIPT = ROOT / "skills" / "impl-package" / "scripts" / "impl_package_apply.py"
STATE_SCRIPT = ROOT / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
REVIEW_SCRIPT = ROOT / "skills" / "plan-review" / "scripts" / "review_ledger.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


APPLY = load_module("impl_package_apply_test", APPLY_SCRIPT)
STATE = load_module("impl_package_state_test", STATE_SCRIPT)
REVIEW = load_module("plan_review_ledger_test", REVIEW_SCRIPT)


def run_cli(script: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), *args],
        text=True,
        check=check,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def git_status_paths(root: Path) -> set[str]:
    output = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        text=True,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout
    return {line[3:] for line in output.splitlines()}


def init_repo(root: Path) -> None:
    git(root, "init")
    git(root, "config", "user.email", "test@example.com")
    git(root, "config", "user.name", "Test User")


def write_package(repo: Path, *, dag: bool = True) -> Path:
    package = repo / "docs" / "implementations" / "2026-08-01-plan-apply"
    package.mkdir(parents=True)
    (package / "decision.md").write_text(
        "# Decision D1\n\n"
        "<!-- impl-package:projection revision-set begin -->\n"
        "决策修订（Decision Revision）：D1\n"
        "<!-- impl-package:projection revision-set end -->\n",
        encoding="utf-8",
    )
    (package / "spec.md").write_text(
        "# Spec S1\n\n"
        "<!-- impl-package:projection revision-set begin -->\n"
        "决策修订（Decision Revision）：D1\n"
        "规格修订（Spec Revision）：S1\n"
        "<!-- impl-package:projection revision-set end -->\n",
        encoding="utf-8",
    )
    (package / "plan.md").write_text(
        "# Plan P1\n\n"
        "执行尝试 ID（Attempt ID）：initial\n"
        "<!-- impl-package:projection revision-set begin -->\n"
        "决策修订（Decision Revision）：D1\n"
        "规格修订（Spec Revision）：S1\n"
        "计划修订（Plan Revision）：P1\n"
        "<!-- impl-package:projection revision-set end -->\n"
        f"执行组合（Composition）：tickets=true, dag={'true' if dag else 'false'}\n\n"
        "## Execution Record\n\n",
        encoding="utf-8",
    )
    tickets = package / "tickets"
    tickets.mkdir()
    (tickets / "01-first.md").write_text(ticket_text("TK-1", "None"), encoding="utf-8")
    (tickets / "02-second.md").write_text(ticket_text("TK-2", "- implementation: TK-1"), encoding="utf-8")
    if dag:
        (package / "dag.md").write_text(
            "# Task DAG\n\n"
            "执行尝试 ID（Attempt ID）：initial\n"
            "- 修订集合（Revision set）：D1 / S1 / P1\n\n"
            "## Task graph\n\n"
            "| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |\n"
            "| --- | --- | --- | --- | --- |\n"
            "| T1 | owner | none | TK-1 | none |\n"
            "| T2 | owner | T1 | TK-2 | none |\n\n"
            "<!-- impl-package:projection runtime-state begin -->\n"
            "| 任务 | 状态 | 证据 |\n"
            "| --- | --- | --- |\n"
            "| T1 | PENDING | dag.md#T1 |\n"
            "| T2 | PENDING | dag.md#T2 |\n"
            "<!-- impl-package:projection runtime-state end -->\n",
            encoding="utf-8",
        )
    run_state(package, "init", "--package-id", package.name)
    git(repo, "add", ".")
    git(repo, "commit", "-m", "baseline planning package")
    return package


def ticket_text(ticket_id: str, dependencies: str) -> str:
    return (
        f"# {ticket_id}\n\n"
        f"**Ticket ID：** {ticket_id}\n"
        "**发布状态（Publication Status）：** Draft\n"
        "**执行尝试 ID（Attempt ID）：** initial\n"
        "**规格修订（Spec Revision）：** S1\n"
        "**计划修订（Plan Revision）：** P1\n\n"
        "## 建设内容\n\nA bounded planning slice.\n\n"
        "## 验收标准\n\n"
        "- **AC-1：** Observable result\n"
        "  - 证据：plan.md#AC-1\n\n"
        "## 阻塞依赖\n\n"
        f"{dependencies}\n\n"
        "## 运行时验收状态（Runtime Acceptance Status）\n\n"
        "<!-- impl-package:projection runtime-state begin -->\n"
        "- 值：[unrecorded]\n"
        "- 直接证据：[unrecorded]\n"
        "<!-- impl-package:projection runtime-state end -->\n"
    )


def run_state(package: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return run_cli(STATE_SCRIPT, "--package", str(package), *args, check=check)


def prepare_authorized_review(repo: Path, package: Path, temp_root: Path) -> tuple[Path, Path]:
    target_paths = [
        package / "plan.md",
        package / "tickets" / "01-first.md",
        package / "tickets" / "02-second.md",
    ]
    reference_paths = [package / "decision.md", package / "spec.md", package / "dag.md"]
    ledger = REVIEW.init_ledger(
        [str(path) for path in target_paths],
        [str(path) for path in reference_paths],
        repo_root=str(repo),
        temp_root=temp_root,
    )
    for dimension in REVIEW.DIMENSIONS:
        REVIEW.record_ledger(
            ledger,
            {
                "type": "materiality",
                "dimension": dimension,
                "status": "reviewed",
                "reason": "fixture review completed",
            },
        )
    REVIEW.record_ledger(ledger, {"type": "review_state", "outside_voice": "complete"})
    REVIEW.finalize_clearance(ledger)
    presented = REVIEW.present_candidate(ledger)
    source = {
        "actor": "owner",
        "channel": "test-chat",
        "reference": "apply-test",
        "action": "apply",
        "manifest_hash": presented["manifest_hash"],
        "statement": "owner approves the complete planning bundle",
    }
    REVIEW.authorize_ledger(ledger, presented["manifest_hash"], source)
    authorization = temp_root / "authorization.json"
    authorization.write_text(json.dumps(source), encoding="utf-8")
    return ledger, authorization


def apply_args(package: Path, ledger: Path, authorization: Path) -> list[str]:
    return [
        "publish-plan",
        "--package",
        str(package),
        "--decision",
        "D1",
        "--spec",
        "S1",
        "--plan",
        "P1",
        "--ledger",
        str(ledger),
        "--authorization",
        str(authorization),
    ]


class PublishPlanApplyTest(unittest.TestCase):
    def test_publish_plan_atomically_publishes_and_registers_earned_dag_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            ledger, authorization = prepare_authorized_review(repo, package, root / "review-runtime")

            result = run_cli(APPLY_SCRIPT, *apply_args(package, ledger, authorization), check=False)

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(result.stdout, "APPLIED\n")
            self.assertEqual(result.stderr, "")
            for path in sorted((package / "tickets").glob("*.md")):
                self.assertIn("Publication Status）：** Approved", path.read_text(encoding="utf-8"))
            revisions = json.loads((package / ".impl-package/revision-bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(revisions["current"]["decision"]["revision"], "D1")
            self.assertEqual(revisions["current"]["spec"]["revision"], "S1")
            self.assertEqual(revisions["current"]["attempt"]["revision"], "P1")
            runtime = json.loads((package / ".impl-package/runtime-state.json").read_text(encoding="utf-8"))
            self.assertEqual({row["id"] for row in runtime["tickets"]}, {"TK-1", "TK-2"})
            self.assertEqual({row["id"] for row in runtime["tasks"]}, {"T1", "T2"})
            self.assertFalse((package / ".impl-package/publish-plan-transaction.json").exists())
            self.assertFalse((package / ".impl-package/registration-transaction.json").exists())
            dirty_paths = git_status_paths(repo)
            self.assertEqual(
                dirty_paths,
                {
                    "docs/implementations/2026-08-01-plan-apply/.impl-package/revision-bindings.json",
                    "docs/implementations/2026-08-01-plan-apply/.impl-package/runtime-state.json",
                    "docs/implementations/2026-08-01-plan-apply/tickets/01-first.md",
                    "docs/implementations/2026-08-01-plan-apply/tickets/02-second.md",
                },
            )
            self.assertEqual(run_state(package, "validate", "--working-tree").returncode, 0)

    def test_publish_plan_rolls_back_ticket_and_sidecars_when_registration_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            ledger, authorization = prepare_authorized_review(repo, package, root / "review-runtime")
            parsed = APPLY._parser().parse_args(apply_args(package, ledger, authorization))

            with mock.patch.object(
                APPLY.STATE,
                "command_register_revisions",
                side_effect=APPLY.STATE.StateError("injected registration blocker"),
            ):
                with self.assertRaisesRegex(APPLY.ApplyError, "injected registration blocker"):
                    APPLY._publish_plan(parsed)

            for path in sorted((package / "tickets").glob("*.md")):
                self.assertIn("Publication Status）：** Draft", path.read_text(encoding="utf-8"))
            revisions = json.loads((package / ".impl-package/revision-bindings.json").read_text(encoding="utf-8"))
            self.assertEqual(revisions["current"], {})
            self.assertFalse((package / ".impl-package/publish-plan-transaction.json").exists())
            self.assertFalse((package / ".impl-package/registration-transaction.json").exists())

    def test_interrupted_transaction_is_recovered_before_new_apply(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            ledger, authorization = prepare_authorized_review(repo, package, root / "review-runtime")
            del ledger, authorization
            context = APPLY._build_context(package, {"decision": "D1", "spec": "S1", "plan": "P1"}, {"decision": None, "spec": None, "plan": None}, None)
            paths = APPLY._target_paths(package, context)
            snapshot = APPLY._snapshot(package, paths)
            APPLY._write_journal(package, APPLY._journal_payload(package, context, snapshot, "prepared"))
            ticket = package / "tickets" / "01-first.md"
            ticket.write_text(ticket.read_text(encoding="utf-8").replace("Draft", "Approved"), encoding="utf-8")

            APPLY._recover_pending(package)

            self.assertIn("Publication Status）：** Draft", ticket.read_text(encoding="utf-8"))
            self.assertFalse((package / ".impl-package/publish-plan-transaction.json").exists())
            self.assertEqual(git(repo, "status", "--porcelain"), "")

    def test_interrupted_transaction_stops_on_external_worktree_change(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            context = APPLY._build_context(package, {"decision": "D1", "spec": "S1", "plan": "P1"}, {"decision": None, "spec": None, "plan": None}, None)
            snapshot = APPLY._snapshot(package, APPLY._target_paths(package, context))
            APPLY._write_journal(package, APPLY._journal_payload(package, context, snapshot, "prepared"))
            unrelated = repo / "unrelated.md"
            unrelated.write_text("outside transaction\n", encoding="utf-8")

            with self.assertRaisesRegex(APPLY.ApplyError, "outside its transaction targets"):
                APPLY._recover_pending(package)

            self.assertTrue((package / ".impl-package/publish-plan-transaction.json").exists())
            unrelated.unlink()
            APPLY._recover_pending(package)
            self.assertFalse((package / ".impl-package/publish-plan-transaction.json").exists())

    def test_sync_working_unit_generates_summary_without_remote_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            ledger, authorization = prepare_authorized_review(repo, package, root / "review-runtime")
            applied = run_cli(APPLY_SCRIPT, *apply_args(package, ledger, authorization), check=False)
            self.assertEqual(applied.returncode, 0, applied.stderr)

            result = run_cli(
                APPLY_SCRIPT,
                "sync-working-unit",
                "--package",
                str(package),
                "--repo",
                "example/repo",
                "--pr",
                "180",
                "--issue",
                "179",
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("PR: #180", result.stdout)
            self.assertIn("Issue: #179", result.stdout)
            self.assertIn("D1 / S1 / P1", result.stdout)
            self.assertIn("No implementation, database, application-runtime, commit, push, or remote mutation", result.stdout)


class PublishPlanValidationTest(unittest.TestCase):
    def test_cycle_is_blocker_before_ticket_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = root / "repo"
            repo.mkdir()
            init_repo(repo)
            package = write_package(repo)
            first = package / "tickets" / "01-first.md"
            second = package / "tickets" / "02-second.md"
            first.write_text(ticket_text("TK-1", "- implementation: TK-2"), encoding="utf-8")
            second.write_text(ticket_text("TK-2", "- implementation: TK-1"), encoding="utf-8")

            with self.assertRaisesRegex(APPLY.ApplyError, "deterministic dependency-compatible order|cyclic"):
                APPLY._build_context(
                    package,
                    {"decision": "D1", "spec": "S1", "plan": "P1"},
                    {"decision": None, "spec": None, "plan": None},
                    None,
                )
            self.assertIn("Publication Status）：** Draft", first.read_text(encoding="utf-8"))
            self.assertIn("Publication Status）：** Draft", second.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
