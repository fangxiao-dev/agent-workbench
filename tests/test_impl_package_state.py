from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
FIXTURE = ROOT / "tests/fixtures/impl-package-ticket-first"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import engine  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class ImplPackageStateTests(unittest.TestCase):
    def make_repo(self) -> tuple[tempfile.TemporaryDirectory[str], Path, Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name)
        git(repo, "init")
        git(repo, "config", "user.email", "test@example.com")
        git(repo, "config", "user.name", "Ticket-first fixture")
        package = repo / "docs/implementations/20260813-example"
        (package / "tickets").mkdir(parents=True)
        shutil.copy2(FIXTURE / "ticket-only-plan.md", package / "plan.md")
        (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
        for source in (FIXTURE / "tickets").glob("*.md"):
            shutil.copy2(source, package / "tickets" / source.name)
        (repo / "evidence.md").write_text("fixture evidence\n", encoding="utf-8")
        git(repo, "add", ".")
        git(repo, "commit", "-m", "fixture")
        return temp, repo, package

    def cli(self, repo: Path, package: Path, *args: str, ok: bool = True, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        result = subprocess.run([sys.executable, str(CLI), "--package", str(package), *args], cwd=repo, input=input_text, text=True, capture_output=True, check=False)
        if ok and result.returncode:
            raise AssertionError(result.stderr or result.stdout)
        return result

    def init(self, repo: Path, package: Path) -> dict:
        return json.loads(self.cli(repo, package, "init", "--attempt", "initial", "--plan", "docs/implementations/20260813-example/plan.md").stdout)

    def state(self, package: Path) -> dict:
        return json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))

    def add_evidence(self, repo: Path, package: Path, *, revision: str | None = None, environment: str = "test") -> None:
        revision = revision or git(repo, "rev-parse", "HEAD")
        index = json.loads((FIXTURE / "evidence/index.json").read_text(encoding="utf-8"))
        for source in index["records"]:
            record = dict(source)
            record.update({"revision": revision, "environment": environment, "artifact": "evidence.md"})
            self.cli(repo, package, "evidence-add", input_text=json.dumps(record))

    def satisfy(self, repo: Path, package: Path, ticket: str, *, expect: str = "PENDING") -> None:
        self.cli(repo, package, "set-state", "ticket", ticket, "SATISFIED", "--expect", expect, "--revision", git(repo, "rev-parse", "HEAD"), "--environment", "test")

    def test_init_uses_exact_35_ticket_only_schema(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        result = self.init(repo, package)
        self.assertEqual(result["formatVersion"], "3.5")
        self.assertEqual(result["tasks"], 0)
        self.assertEqual(result["readyTickets"], ["TKT-01", "TKT-03", "TKT-04"])
        self.assertEqual(set(self.state(package)), {"formatVersion", "attempt", "attemptHistory", "tickets", "evidenceIndex", "activeCheckpoints"})
        self.assertNotIn("tasks", self.state(package))
        self.assertNotIn("resume", self.state(package))
        self.assertFalse((package / "dag.md").exists())
        self.assertFalse((package / "execution/initial/task-handoffs").exists())

    def test_satisfied_requires_all_claims_current_context_and_dependencies(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        missing_context = self.cli(repo, package, "set-state", "ticket", "TKT-01", "SATISFIED", "--expect", "PENDING", "--revision", git(repo, "rev-parse", "HEAD"), ok=False)
        self.assertIn("environment", missing_context.stderr)
        self.add_evidence(repo, package)
        blocked = self.cli(repo, package, "set-state", "ticket", "TKT-03", "SATISFIED", "--expect", "PENDING", "--revision", git(repo, "rev-parse", "HEAD"), "--environment", "test", ok=False)
        self.assertIn("dependencies", blocked.stderr)
        self.satisfy(repo, package, "TKT-01")
        accepted = self.state(package)["tickets"]["TKT-01"]
        self.assertEqual(accepted["state"], "SATISFIED")
        self.assertEqual(accepted["acceptance"]["revision"], git(repo, "rev-parse", "HEAD"))
        self.assertEqual(accepted["acceptance"]["environment"], "test")

    def test_contradictory_evidence_blocks_satisfied(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.add_evidence(repo, package)
        payload = {"ticket": "TKT-01", "claim": "AC-1", "timing": "early-falsification", "artifact": "evidence.md", "revision": git(repo, "rev-parse", "HEAD"), "environment": "test", "conclusion": "contradictory"}
        self.cli(repo, package, "evidence-add", input_text=json.dumps(payload))
        failed = self.cli(repo, package, "set-state", "ticket", "TKT-01", "SATISFIED", "--expect", "PENDING", "--revision", git(repo, "rev-parse", "HEAD"), "--environment", "test", ok=False)
        self.assertIn("contradictory", failed.stderr)

    def test_evidence_timing_is_bound_to_the_ticket_claim(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        payload = {"ticket": "TKT-01", "claim": "AC-2", "timing": "early-falsification", "artifact": "evidence.md", "revision": git(repo, "rev-parse", "HEAD"), "environment": "test", "conclusion": "supporting"}
        failed = self.cli(repo, package, "evidence-add", input_text=json.dumps(payload), ok=False)
        self.assertIn("timing", failed.stderr)

    def test_invalidating_satisfied_evidence_fails_before_writing_state(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.add_evidence(repo, package)
        self.satisfy(repo, package, "TKT-01")
        before = self.state(package)
        failed = self.cli(repo, package, "evidence-invalidate", "--ticket", "TKT-01", "--claim", "AC-1", "--artifact", "evidence.md", "--invalidated-by", "fixture", ok=False)
        self.assertIn("incomplete current evidence", failed.stderr)
        self.assertEqual(self.state(package), before)

    def test_missing_claim_timing_is_not_inherited_from_the_next_claim(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        ticket = package / "tickets" / "01-source.md"
        text = ticket.read_text(encoding="utf-8")
        text = text.replace("  - 证据时机：`early-falsification`\n", "", 1)
        ticket.write_text(text, encoding="utf-8")
        failed = self.cli(repo, package, "init", "--attempt", "initial", "--plan", "docs/implementations/20260813-example/plan.md", ok=False)
        self.assertIn("no evidence timing", failed.stderr)

    def test_checkpoint_overwrites_state_and_er_accepts_judgment_only(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        first = json.loads(self.cli(repo, package, "checkpoint", "--subject", "ticket:TKT-01", "--next", "run source test", "--evidence", "evidence.md").stdout)
        second = json.loads(self.cli(repo, package, "checkpoint", "--subject", "ticket:TKT-01", "--next", "read result", "--evidence", "evidence.md").stdout)
        self.assertEqual(first["subject"], "ticket:TKT-01")
        self.assertEqual(second["checkpoint"]["next"], "read result")
        state = self.state(package)
        self.assertEqual(set(state["activeCheckpoints"]), {"ticket:TKT-01"})
        er = (package / "execution/initial/execution-record.md").read_text(encoding="utf-8")
        self.assertNotIn("· checkpoint", er)
        bad = self.cli(repo, package, "er-add", input_text=json.dumps({"purpose": "checkpoint", "subject": "attempt", "title": "bad", "content": "bad", "nextAction": "no"}), ok=False)
        self.assertIn("judgment only", bad.stderr)
        good = self.cli(repo, package, "er-add", input_text=json.dumps({"purpose": "judgment", "subject": "attempt", "title": "Decision", "content": "Keep the narrow path."}))
        self.assertIn("recordId", json.loads(good.stdout))

    def test_cli_mutations_append_trail_rows_and_dedupe_repeated_checkpoint(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        checkpoint = self.cli(repo, package, "recovery", "checkpoint", "--subject", "attempt", "--next", "run source test", "--evidence", "evidence.md")
        repeated_checkpoint = self.cli(repo, package, "recovery", "checkpoint", "--subject", "attempt", "--next", "run source test", "--evidence", "evidence.md")
        self.assertEqual(checkpoint.returncode, 0)
        self.assertEqual(repeated_checkpoint.returncode, 0)
        self.assertEqual(set(json.loads(checkpoint.stdout)), {"subject", "checkpoint", "idempotent"})
        self.add_evidence(repo, package)
        satisfied = self.cli(
            repo,
            package,
            "ticket",
            "satisfy",
            "TKT-01",
            "--expect",
            "PENDING",
            "--revision",
            git(repo, "rev-parse", "HEAD"),
            "--environment",
            "test",
        )
        retired = self.cli(
            repo,
            package,
            "ticket",
            "retire",
            "TKT-02",
            "--expect",
            "PENDING",
            "--disposition",
            "waived",
            "--evidence",
            "evidence.md",
        )
        self.assertFalse(json.loads(satisfied.stdout)["idempotent"])
        self.assertEqual(satisfied.returncode, 0)
        self.assertEqual(set(json.loads(satisfied.stdout)), {"kind", "id", "state", "idempotent"})
        self.assertEqual(retired.returncode, 0)
        self.assertEqual(set(json.loads(retired.stdout)), {"kind", "id", "state", "idempotent"})

        rows = [json.loads(line) for line in (package / "execution/initial/trail.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0]["kind"], "checkpoint")
        self.assertEqual(rows[0]["subject"], "attempt")
        self.assertTrue(rows[0]["checkpoint"])
        self.assertEqual(rows[0]["next"], "run source test")
        self.assertEqual(rows[1]["kind"], "result")
        self.assertEqual(rows[1]["subject"], "ticket:TKT-01")
        self.assertEqual(rows[1]["transition"], "ticket-state")
        self.assertEqual(rows[1]["from"], "PENDING")
        self.assertEqual(rows[1]["to"], "SATISFIED")
        self.assertEqual(rows[1]["outcome"], "SATISFIED")
        self.assertEqual(rows[2]["subject"], "ticket:TKT-02")
        self.assertEqual(rows[2]["outcome"], "RETIRED")
        self.assertEqual(rows[2]["to"], "RETIRED")
        self.assertEqual([row["seq"] for row in rows], [1, 2, 3])

    def test_trail_append_failure_does_not_fail_ticket_mutation(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.add_evidence(repo, package)
        revision = git(repo, "rev-parse", "HEAD")
        stderr = StringIO()

        with patch.object(engine, "_append_trail", side_effect=OSError("disk full")), redirect_stderr(stderr):
            result = engine.command_set_state(
                package,
                "TKT-01",
                "SATISFIED",
                "PENDING",
                revision,
                "test",
                None,
                None,
                None,
                None,
                [],
                None,
            )

        self.assertFalse(result["idempotent"])
        self.assertEqual(self.state(package)["tickets"]["TKT-01"]["state"], "SATISFIED")
        self.assertIn("trail append failed", stderr.getvalue())

    def test_superseded_requires_successor_and_no_inbound_edges(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        bad = self.cli(repo, package, "set-state", "ticket", "TKT-01", "RETIRED", "--expect", "PENDING", "--disposition", "superseded", "--evidence", "evidence.md", ok=False)
        self.assertIn("successor", bad.stderr)
        failed = self.cli(repo, package, "set-state", "ticket", "TKT-01", "RETIRED", "--expect", "PENDING", "--disposition", "superseded", "--successor", "TKT-02", "--evidence", "evidence.md", ok=False)
        self.assertIn("inbound edges", failed.stderr)
        self.assertEqual(self.state(package)["tickets"]["TKT-01"], {"state": "PENDING"})

    def test_superseded_ticket_releases_only_after_successor_is_released(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        for name in ("02-transform.md", "03-verify.md", "04-publish.md"):
            ticket = package / "tickets" / name
            text = ticket.read_text(encoding="utf-8")
            text = text.replace("implementation: TKT-01", "implementation: TKT-02")
            text = text.replace("acceptance: TKT-01", "acceptance: TKT-02")
            text = text.replace("release: TKT-01", "release: TKT-02")
            if name == "02-transform.md":
                text = text.replace("- implementation: TKT-02", "- None")
            ticket.write_text(text, encoding="utf-8")
        self.init(repo, package)
        self.cli(repo, package, "set-state", "ticket", "TKT-01", "RETIRED", "--expect", "PENDING", "--disposition", "superseded", "--successor", "TKT-02", "--evidence", "evidence.md")
        self.add_evidence(repo, package)
        blocked = self.cli(repo, package, "set-state", "ticket", "TKT-03", "SATISFIED", "--expect", "PENDING", "--revision", git(repo, "rev-parse", "HEAD"), "--environment", "test", ok=False)
        self.assertIn("dependencies are not released", blocked.stderr)
        self.satisfy(repo, package, "TKT-02")
        self.satisfy(repo, package, "TKT-03")

    def test_retired_is_terminal_and_identical_retry_is_idempotent(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        retired = self.cli(repo, package, "ticket", "retire", "TKT-01", "--expect", "PENDING", "--disposition", "waived", "--evidence", "evidence.md")
        self.assertFalse(json.loads(retired.stdout)["idempotent"])
        repeated = self.cli(repo, package, "ticket", "retire", "TKT-01", "--expect", "RETIRED", "--disposition", "waived", "--evidence", "evidence.md")
        self.assertTrue(json.loads(repeated.stdout)["idempotent"])
        before = self.state(package)["tickets"]["TKT-01"]
        for target in ("PENDING", "BLOCKED"):
            args = ["set-state", "ticket", "TKT-01", target, "--expect", "RETIRED"]
            if target == "BLOCKED":
                args += ["--evidence", "evidence.md"]
            failed = self.cli(repo, package, *args, ok=False)
            self.assertIn("terminal", failed.stderr)
            self.assertEqual(self.state(package)["tickets"]["TKT-01"], before)

    def test_needs_revalidation_invalidates_selected_claims_only(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.add_evidence(repo, package)
        self.satisfy(repo, package, "TKT-01")
        transition = self.cli(
            repo, package, "ticket", "needs-revalidation", "TKT-01", "--expect", "SATISFIED",
            "--claim", "AC-1", "--invalidated-by", "spec-change",
        )
        result = json.loads(transition.stdout)
        self.assertEqual(result["claims"], ["AC-1"])
        self.assertGreater(result["invalidatedEvidence"], 0)
        evidence = self.state(package)["evidenceIndex"]["TKT-01"]
        self.assertTrue(all(row.get("invalidatedBy") == "spec-change" for row in evidence["AC-1"]))
        self.assertTrue(all(row.get("invalidatedBy") is None for row in evidence["AC-2"]))
        self.cli(repo, package, "ticket", "pending", "TKT-01", "--expect", "NEEDS-REVALIDATION", "--revalidation-plan", "docs/implementations/20260813-example/plan.md")
        old_only = self.cli(repo, package, "ticket", "satisfy", "TKT-01", "--expect", "PENDING", "--revision", git(repo, "rev-parse", "HEAD"), "--environment", "test", ok=False)
        self.assertIn("missing claims", old_only.stderr)
        self.add_evidence(repo, package)
        self.satisfy(repo, package, "TKT-01")

    def test_ticket_bytes_are_stable_after_runtime_updates(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        before = {path.name: path.read_bytes() for path in (package / "tickets").glob("*.md")}
        self.add_evidence(repo, package)
        self.satisfy(repo, package, "TKT-01")
        self.cli(repo, package, "checkpoint", "--subject", "ticket:TKT-01", "--next", "run verification", "--evidence", "evidence.md")
        self.cli(repo, package, "refresh-progress")
        self.satisfy(repo, package, "TKT-02")
        self.satisfy(repo, package, "TKT-03")
        self.satisfy(repo, package, "TKT-04")
        head = git(repo, "rev-parse", "HEAD")
        self.cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "stable ticket fixture", "--no-durable-delta-reason", "fixture", "--environment", "test")
        for path in (package / "tickets").glob("*.md"):
            self.assertEqual(path.read_bytes(), before[path.name])

    def test_blocked_retains_direct_evidence_and_does_not_enter_ready(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.cli(repo, package, "set-state", "ticket", "TKT-01", "BLOCKED", "--expect", "PENDING", "--evidence", "evidence.md")
        self.assertEqual(self.state(package)["tickets"]["TKT-01"], {"state": "BLOCKED", "evidence": "evidence.md"})
        status = json.loads(self.cli(repo, package, "validate").stdout)
        self.assertNotIn("TKT-01", status["readyTickets"])

    def test_gate_checks_release_edges_and_clears_active_checkpoints(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.add_evidence(repo, package)
        self.satisfy(repo, package, "TKT-01")
        self.satisfy(repo, package, "TKT-02")
        self.satisfy(repo, package, "TKT-03")
        self.satisfy(repo, package, "TKT-04")
        self.cli(repo, package, "checkpoint", "--next", "gate", "--evidence", "evidence.md")
        head = git(repo, "rev-parse", "HEAD")
        result = self.cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "fixture", "--no-durable-delta-reason", "fixture", "--environment", "test")
        self.assertEqual(json.loads(result.stdout)["verdict"], "pass")
        self.assertEqual(self.state(package)["activeCheckpoints"], {})
        self.assertEqual(self.state(package)["attemptHistory"][-1]["lifecycle"], "frozen")


if __name__ == "__main__":
    unittest.main()
