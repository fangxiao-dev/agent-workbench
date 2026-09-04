from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
FIXTURE = ROOT / "tests/fixtures/impl-package-ticket-first"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import command_groups, engine  # noqa: E402


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

    def cli_with_situation(self, repo: Path, package: Path, *args: str, input_text: str | None = None) -> subprocess.CompletedProcess[str]:
        with patch.dict(os.environ, {"IMPL_PACKAGE_NO_SITUATION": "0"}):
            return self.cli(repo, package, *args, input_text=input_text)

    def assert_situation_footer(self, result: subprocess.CompletedProcess[str]) -> None:
        self.assertEqual(result.returncode, 0)
        self.assertRegex(result.stdout, r"\[处境\] digest=[0-9a-f]{12}")
        self.assertIn("协议:", result.stdout)

    def init(self, repo: Path, package: Path) -> dict:
        return json.loads(self.cli(repo, package, "init", "--attempt", "initial", "--plan", "docs/implementations/20260813-example/plan.md").stdout)

    def state(self, package: Path) -> dict:
        return json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))

    def write_situation_digest(
        self,
        package: Path,
        digest: str = "a1b2c3d4e5f6",
        *,
        state_sha256: str | None = None,
        ts: str = "2026-08-18T10:00:00Z",
    ) -> None:
        state_path = package / ".impl-package/state.json"
        credential = {
            "digest": digest,
            "ts": ts,
            "state_sha256": state_sha256 or hashlib.sha256(state_path.read_bytes()).hexdigest(),
        }
        path = package / "execution" / "initial" / "situation-digest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(credential), encoding="utf-8")

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
        self.assertIsNone(self.state(package)["predecessors"])
        self.assertEqual(set(self.state(package)), {"formatVersion", "attempt", "attemptHistory", "predecessors", "tickets", "evidenceIndex", "activeCheckpoints"})
        self.assertNotIn("tasks", self.state(package))
        self.assertNotIn("resume", self.state(package))
        self.assertFalse((package / "dag.md").exists())
        self.assertFalse((package / "execution/initial/task-handoffs").exists())

    def test_plan_must_explicitly_declare_predecessors(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        plan = package / "plan.md"
        plan.write_text(plan.read_text(encoding="utf-8").replace("- 前置包（Predecessors）：None\n", ""), encoding="utf-8")

        failed = self.cli(
            repo,
            package,
            "package",
            "init",
            "--attempt",
            "initial",
            "--plan",
            "docs/implementations/20260813-example/plan.md",
            ok=False,
        )

        self.assertIn("declare 前置包", failed.stderr)

    def test_predecessor_paths_are_recorded_and_searched_first(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        predecessor = repo / "docs/implementations/20260801-base"
        predecessor.mkdir(parents=True)
        second_predecessor = repo / "docs/implementations/20260802-policy"
        second_predecessor.mkdir(parents=True)
        (predecessor / "output.py").write_text(
            "def DatevPolicyWorkbenchDto():\n    pass\n",
            encoding="utf-8",
        )
        plan = package / "plan.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 前置包（Predecessors）：None",
                "- 前置包（Predecessors）：docs/implementations/20260801-base, docs/implementations/20260802-policy",
            ),
            encoding="utf-8",
        )
        ticket = package / "tickets" / "01-source.md"
        text = ticket.read_text(encoding="utf-8")
        ticket.write_text(
            text.replace(
                "\n## 安全不变量\n",
                "\n- 到达路径：entry → EXISTS: DatevPolicyWorkbenchDto → arrival\n\n## 安全不变量\n",
            ),
            encoding="utf-8",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "add predecessor output")

        self.init(repo, package)
        state = self.state(package)
        self.assertEqual(state["predecessors"], ["docs/implementations/20260801-base", "docs/implementations/20260802-policy"])
        payload = json.loads(self.cli(repo, package, "package", "validate").stdout)

        self.assertEqual(
            [item for item in payload["findings"] if item["code"] == "arrival-exists-symbol-not-found"],
            [],
        )

    def test_state_requires_predecessors_field(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        state_path = package / ".impl-package" / "state.json"
        state = self.state(package)
        del state["predecessors"]
        state_path.write_text(json.dumps(state), encoding="utf-8")

        failed = self.cli(repo, package, "package", "validate", ok=False)

        self.assertIn("predecessors", failed.stderr)

    def test_state_predecessors_must_match_plan(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        predecessor = repo / "docs/implementations/20260801-base"
        predecessor.mkdir(parents=True)
        plan = package / "plan.md"
        plan.write_text(
            plan.read_text(encoding="utf-8").replace(
                "- 前置包（Predecessors）：None",
                "- 前置包（Predecessors）：docs/implementations/20260801-base",
            ),
            encoding="utf-8",
        )
        self.init(repo, package)
        plan.write_text(plan.read_text(encoding="utf-8").replace("docs/implementations/20260801-base", "None"), encoding="utf-8")

        failed = self.cli(repo, package, "package", "validate", ok=False)

        self.assertIn("state predecessors do not match", failed.stderr)

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

    def test_one_acceptance_criterion_with_two_atomic_claims_requires_both(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        ticket = package / "tickets" / "01-source.md"
        ticket.write_text(
            ticket.read_text(encoding="utf-8").replace(
                "  - Stable claim ID：`AC-1`\n  - 证据时机：`early-falsification`",
                "  - Stable claim ID：`AC-1`\n  - 证据时机：`early-falsification`\n"
                "  - Stable claim ID：`AC-1-readback`\n  - 证据时机：`early-falsification`",
            ),
            encoding="utf-8",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "split acceptance atom")
        self.init(repo, package)
        self.add_evidence(repo, package)
        revision = git(repo, "rev-parse", "HEAD")

        missing = self.cli(
            repo,
            package,
            "ticket",
            "satisfy",
            "TKT-01",
            "--expect",
            "PENDING",
            "--revision",
            revision,
            "--environment",
            "test",
            ok=False,
        )
        self.assertIn("AC-1-readback", missing.stderr)

        self.cli(
            repo,
            package,
            "evidence",
            "add",
            input_text=json.dumps(
                {
                    "ticket": "TKT-01",
                    "claim": "AC-1-readback",
                    "timing": "early-falsification",
                    "artifact": "evidence.md",
                    "revision": revision,
                    "environment": "test",
                    "conclusion": "supporting",
                }
            ),
        )
        self.satisfy(repo, package, "TKT-01")
        self.assertEqual(self.state(package)["tickets"]["TKT-01"]["state"], "SATISFIED")

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

    def test_arrival_path_requires_exists_or_new_markers(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        ticket = package / "tickets" / "01-source.md"
        ticket.write_text(
            ticket.read_text(encoding="utf-8")
            + "\n- 到达路径：entry → TaxOfficeDelegatedAccessAdapter → arrival\n",
            encoding="utf-8",
        )

        failed = self.cli(
            repo,
            package,
            "package",
            "init",
            "--attempt",
            "initial",
            "--plan",
            "docs/implementations/20260813-example/plan.md",
            ok=False,
        )

        self.assertIn("unmarked segment", failed.stderr)

    def test_package_validate_reports_missing_exists_symbols_without_blocking(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        symbols = (
            "TaxOfficeDelegatedAccessAdapter",
            "DatevMandantPolicySnapshotMapper",
            "DatevPrivateSourceConfirmParticipant",
            "CreateDatevPolicyCandidateResponse",
        )
        route = "entry → " + " → ".join(f"EXISTS: {symbol}" for symbol in symbols) + " → arrival"
        ticket = package / "tickets" / "01-source.md"
        text = ticket.read_text(encoding="utf-8")
        ticket.write_text(text.replace("\n## 安全不变量\n", f"\n- 到达路径：{route}\n\n## 安全不变量\n"), encoding="utf-8")
        self.init(repo, package)

        result = self.cli(repo, package, "package", "validate")
        payload = json.loads(result.stdout)

        self.assertEqual(result.returncode, 0)
        self.assertEqual(payload["comparisonCommit"], git(repo, "rev-parse", "HEAD"))
        arrival_findings = [item for item in payload["findings"] if item["code"] == "arrival-exists-symbol-not-found"]
        self.assertEqual({item["symbol"] for item in arrival_findings}, set(symbols))
        self.assertTrue(all(item["code"] == "arrival-exists-symbol-not-found" for item in arrival_findings))

    def test_package_validate_checks_exists_at_comparison_commit_and_skips_new(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        ticket = package / "tickets" / "01-source.md"
        text = ticket.read_text(encoding="utf-8")
        ticket.write_text(
            text.replace(
                "\n## 安全不变量\n",
                "\n- 到达路径：entry → EXISTS: withTaxOfficeDelegatedFinanceScopeLease → NEW: CreateDatevPolicyCandidateResponse → arrival\n\n## 安全不变量\n",
            ),
            encoding="utf-8",
        )
        (repo / "src").mkdir()
        (repo / "src" / "finance.py").write_text(
            "def withTaxOfficeDelegatedFinanceScopeLease():\n    pass\n",
            encoding="utf-8",
        )
        git(repo, "add", ".")
        git(repo, "commit", "-m", "add existing arrival symbol")
        self.init(repo, package)

        payload = json.loads(self.cli(repo, package, "package", "validate").stdout)

        self.assertEqual(
            [item for item in payload["findings"] if item["code"] == "arrival-exists-symbol-not-found"],
            [],
        )

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

    def test_handoff_checkpoint_rotates_only_with_flag_and_records_handoff(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        ordinary = self.cli(
            repo,
            package,
            "recovery",
            "checkpoint",
            "--subject",
            "attempt",
            "--next",
            "ordinary recovery",
            "--evidence",
            "evidence.md",
        )
        self.assertEqual(set(json.loads(ordinary.stdout)), {"subject", "checkpoint", "idempotent"})
        trail_dir = package / "execution" / "initial"
        self.assertFalse((trail_dir / "trail.001.jsonl").exists())

        handoff = self.cli(
            repo,
            package,
            "recovery",
            "checkpoint",
            "--subject",
            "attempt",
            "--next",
            "handoff recovery",
            "--evidence",
            "evidence.md",
            "--handoff",
        )
        self.assertEqual(set(json.loads(handoff.stdout)), {"subject", "checkpoint", "idempotent"})
        archive = trail_dir / "trail.001.jsonl"
        current = trail_dir / "trail.jsonl"
        archived_rows = [json.loads(line) for line in archive.read_text(encoding="utf-8").splitlines()]
        current_rows = [json.loads(line) for line in current.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(archived_rows[-1]["kind"], "checkpoint")
        self.assertEqual(current_rows[0]["kind"], "handoff")
        self.assertTrue(current_rows[0]["checkpoint"])
        self.assertEqual(current_rows[0]["next"], "handoff recovery")
        self.assertEqual(self.state(package)["activeCheckpoints"]["attempt"]["next"], "handoff recovery")

    def test_handoff_rotation_failure_does_not_fail_checkpoint(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        stderr = StringIO()

        with patch.object(engine, "_rotate_trail", side_effect=OSError("disk full")), redirect_stderr(stderr):
            result = engine.command_checkpoint(package, "attempt", "continue after handoff", None, [], True)

        self.assertEqual(set(result), {"subject", "checkpoint", "idempotent"})
        self.assertEqual(self.state(package)["activeCheckpoints"]["attempt"]["next"], "continue after handoff")
        self.assertIn("trail rotation failed", stderr.getvalue())

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

    def test_trail_append_assigns_sequence_and_common_fields(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        fact = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "fact", "subject": "attempt", "key": "attempt.in_flight", "value": True}),
        )
        self.write_situation_digest(package)
        dispatch = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "dispatch", "subject": "attempt", "outcome": "RUNNING", "worker": "worker-01", "returned": False, "situation_digest": "a1b2c3d4e5f6"}),
        )
        self.assertEqual(json.loads(fact.stdout)["appended"], True)
        self.assertEqual(json.loads(dispatch.stdout)["appended"], True)
        rows = [json.loads(line) for line in (package / "execution/initial/trail.jsonl").read_text(encoding="utf-8").splitlines()]
        self.assertEqual([row["seq"] for row in rows], [1, 2])
        for row in rows:
            self.assertEqual(row["v"], 1)
            self.assertTrue(row["ts"].endswith("Z"))
            self.assertEqual(row["head"], git(repo, "rev-parse", "HEAD"))
        self.assertEqual(rows[1]["situation_digest"], "a1b2c3d4e5f6")

    def test_trail_append_named_flags_merge_into_event(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.write_situation_digest(package)

        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            "--situation-digest",
            "a1b2c3d4e5f6",
            "--review-phase",
            "initial",
            "--review-track",
            "Track A",
            "--review-recheck",
            input_text=json.dumps(
                {
                    "kind": "dispatch",
                    "subject": "attempt",
                    "outcome": "RUNNING",
                    "worker": "worker-01",
                    "returned": False,
                }
            ),
        )

        self.assertTrue(json.loads(result.stdout)["appended"])
        row = json.loads((package / "execution/initial/trail.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(row["situation_digest"], "a1b2c3d4e5f6")
        self.assertEqual(row["review_phase"], "initial")
        self.assertEqual(row["review_track"], "Track A")
        self.assertTrue(row["review_recheck"])

    def test_trail_append_named_flags_reject_invalid_values(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        payload = json.dumps({"kind": "fact", "subject": "attempt", "key": "attempt.in_flight", "value": True})

        invalid = (
            (("--situation-digest", "not-a-digest"), "12-character hex"),
            (("--review-phase", "terminal"), "invalid choice"),
            (("--review-track", "Track E"), "invalid choice"),
        )
        for (option, value), message in invalid:
            result = self.cli(repo, package, "trail", "append", option, value, input_text=payload, ok=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn(message, result.stderr)

    def test_trail_append_named_flags_reject_conflicting_stdin_values(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        base = {
            "kind": "dispatch",
            "subject": "attempt",
            "outcome": "RUNNING",
            "worker": "worker-01",
            "returned": False,
        }
        conflicts = (
            (("--situation-digest", "a1b2c3d4e5f6"), {"situation_digest": "deadbeefdead"}, "situation_digest"),
            (("--review-phase", "finding-closure"), {"review_phase": "initial", "review_track": "Track A"}, "review_phase"),
            (("--review-track", "Track B"), {"review_phase": "initial", "review_track": "Track A"}, "review_track"),
            (("--review-recheck", None), {"review_recheck": False}, "review_recheck"),
        )
        for (option, value), fields, field in conflicts:
            argv = ["trail", "append", option]
            if value is not None:
                argv.append(value)
            result = self.cli(repo, package, *argv, input_text=json.dumps({**base, **fields}), ok=False)
            self.assertIn("conflicts", result.stderr)
            self.assertIn(field, result.stderr)

    def test_trail_append_named_flags_accept_matching_stdin_values(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.write_situation_digest(package)
        payload = {
            "kind": "dispatch",
            "subject": "attempt",
            "outcome": "RUNNING",
            "worker": "worker-01",
            "returned": False,
            "situation_digest": "a1b2c3d4e5f6",
            "review_phase": "initial",
            "review_track": "Track A",
            "review_recheck": True,
        }

        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            "--situation-digest",
            "a1b2c3d4e5f6",
            "--review-phase",
            "initial",
            "--review-track",
            "Track A",
            "--review-recheck",
            input_text=json.dumps(payload),
        )
        self.assertTrue(json.loads(result.stdout)["appended"])

    def test_trail_append_stdin_named_fields_remain_compatible(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.write_situation_digest(package)
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps(
                {
                    "kind": "dispatch",
                    "subject": "attempt",
                    "outcome": "RUNNING",
                    "worker": "worker-01",
                    "returned": False,
                    "situation_digest": "a1b2c3d4e5f6",
                    "review_phase": "initial",
                    "review_track": "Track A",
                    "review_recheck": False,
                }
            ),
        )
        self.assertTrue(json.loads(result.stdout)["appended"])

    def test_review_dispatch_fields_use_closed_vocabulary_and_pairing(self) -> None:
        base = {
            "kind": "dispatch",
            "subject": "attempt",
            "outcome": "RUNNING",
            "worker": "worker-01",
            "returned": False,
            "situation_digest": "a1b2c3d4e5f6",
        }

        valid = engine._validate_trail_event(
            {**base, "review_phase": "terminal-final", "review_track": "Track D", "review_recheck": True}
        )
        self.assertEqual(valid["review_phase"], "terminal-final")
        self.assertEqual(valid["review_track"], "Track D")

        for invalid_phase in ("terminal", "final", 1):
            with self.assertRaisesRegex(engine.StateError, "initial.*finding-closure.*terminal-final"):
                engine._validate_trail_event(
                    {**base, "review_phase": invalid_phase, "review_track": "Track A"}
                )
        for invalid_track in ("Track C source recheck", "Track E", 1):
            with self.assertRaisesRegex(engine.StateError, "Track A.*Track B.*Track C.*Track D"):
                engine._validate_trail_event(
                    {**base, "review_phase": "initial", "review_track": invalid_track}
                )

        for partial in (
            {**base, "review_phase": "initial"},
            {**base, "review_track": "Track A"},
        ):
            with self.assertRaisesRegex(engine.StateError, "review_phase.*review_track"):
                engine._validate_trail_event(partial)

        self.assertEqual(engine._validate_trail_event(base), base)
        with self.assertRaisesRegex(engine.StateError, "review_recheck.*boolean"):
            engine._validate_trail_event(
                {**base, "review_phase": "initial", "review_track": "Track A", "review_recheck": "true"}
            )

    def test_trail_append_dispatch_requires_situation_digest(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "dispatch", "subject": "attempt", "outcome": "RUNNING", "worker": "worker-01", "returned": False}),
            ok=False,
        )
        self.assertIn("dispatch 需要当前处境的 digest", result.stderr)
        self.assertIn("事件缺少 situation_digest", result.stderr)
        self.assertFalse((package / "execution/initial/trail.jsonl").exists())

    def test_trail_append_dispatch_rejects_missing_situation_credential(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "dispatch", "subject": "attempt", "outcome": "RUNNING", "worker": "worker-01", "returned": False, "situation_digest": "a1b2c3d4e5f6"}),
            ok=False,
        )
        self.assertIn("dispatch 需要当前处境的 digest：先运行 situation.py render 取 digest，再重写这条 dispatch", result.stderr)
        self.assertIn("未找到 situation-digest.json 凭据文件", result.stderr)

    def test_trail_append_dispatch_rejects_situation_digest_mismatch(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.write_situation_digest(package, digest="deadbeefdead")
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "dispatch", "subject": "attempt", "outcome": "RUNNING", "worker": "worker-01", "returned": False, "situation_digest": "a1b2c3d4e5f6"}),
            ok=False,
        )
        self.assertIn("dispatch 需要当前处境的 digest：先运行 situation.py render 取 digest，再重写这条 dispatch", result.stderr)
        self.assertIn("digest 不匹配，凭据是 deadbeefdead", result.stderr)

    def test_trail_append_dispatch_rejects_stale_situation_credential(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        self.write_situation_digest(package)
        state_path = package / ".impl-package/state.json"
        state_path.write_bytes(state_path.read_bytes() + b"\n")
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "dispatch", "subject": "attempt", "outcome": "RUNNING", "worker": "worker-01", "returned": False, "situation_digest": "a1b2c3d4e5f6"}),
            ok=False,
        )
        self.assertIn("dispatch 需要当前处境的 digest：先运行 situation.py render 取 digest，再重写这条 dispatch", result.stderr)
        self.assertIn("处境已变，凭据渲染于 2026-08-18T10:00:00Z 之后 state.json 已更新", result.stderr)

    def test_trail_append_non_dispatch_kinds_do_not_require_situation_digest(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        for payload in (
            {"kind": "escape", "subject": "attempt", "deviation": "manual", "reason": "fixture"},
            {"kind": "fact", "subject": "attempt", "key": "attempt.in_flight", "value": True},
            {"kind": "worker-return", "subject": "attempt", "outcome": "DONE"},
        ):
            result = self.cli(repo, package, "trail", "append", input_text=json.dumps(payload))
            self.assertTrue(json.loads(result.stdout)["appended"])

    def test_trail_append_accepts_canonical_review_summary_fact(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        value = {
            "schemaVersion": 1,
            "reviewRunId": "review-01",
            "phase": "initial",
            "resolvedHead": git(repo, "rev-parse", "HEAD"),
            "findings": [],
        }
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps(
                {
                    "kind": "fact",
                    "subject": "review:review-01",
                    "key": "review.canonical_summary",
                    "value": value,
                }
            ),
        )

        self.assertTrue(json.loads(result.stdout)["appended"])
        row = json.loads((package / "execution/initial/trail.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(row["value"], value)

    def test_trail_append_rejects_unknown_fact_key_with_nearest_key(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "fact", "subject": "attempt", "key": "attempt.in_fligh", "value": True}),
            ok=False,
        )
        self.assertIn("attempt.in_flight", result.stderr)
        self.assertFalse((package / "execution/initial/trail.jsonl").exists())

    def test_trail_append_rejects_unsupported_kind(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        result = self.cli(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "checkpoint", "subject": "attempt"}),
            ok=False,
        )
        self.assertIn("invalid trail kind", result.stderr)
        self.assertIn("worker-return", result.stderr)

    def test_trail_append_failure_returns_nonzero(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        stderr = StringIO()
        stdout = StringIO()
        payload = json.dumps({"kind": "escape", "subject": "attempt", "deviation": "manual", "reason": "fixture"})
        with patch.object(engine, "_append_trail", side_effect=OSError("disk full")), patch.object(command_groups.sys, "stdin", StringIO(payload)), redirect_stderr(stderr), redirect_stdout(stdout):
            result = command_groups.main(package, "trail", ["append"])
        self.assertEqual(result, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertIn("disk full", stderr.getvalue())

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

    def test_situation_footer_covers_each_trigger_class(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        revision = git(repo, "rev-parse", "HEAD")

        ticket = self.cli_with_situation(
            repo, package, "ticket", "block", "TKT-01", "--expect", "PENDING", "--evidence", "evidence.md"
        )
        evidence = self.cli_with_situation(
            repo,
            package,
            "evidence",
            "add",
            input_text=json.dumps(
                {
                    "ticket": "TKT-01",
                    "claim": "AC-1",
                    "timing": "early-falsification",
                    "artifact": "evidence.md",
                    "revision": revision,
                    "environment": "test",
                    "conclusion": "supporting",
                }
            ),
        )
        recovery = self.cli_with_situation(
            repo, package, "recovery", "checkpoint", "--next", "continue with fixture", "--evidence", "evidence.md"
        )
        gate = self.cli_with_situation(
            repo, package, "gate", "blocked", "--comparison-commit", revision, "--reason", "footer fixture"
        )
        trail = self.cli_with_situation(
            repo,
            package,
            "trail",
            "append",
            input_text=json.dumps({"kind": "escape", "subject": "attempt", "deviation": "fixture", "reason": "footer"}),
        )
        validate = self.cli_with_situation(repo, package, "package", "validate")

        for result in (ticket, evidence, recovery, gate, trail, validate):
            self.assert_situation_footer(result)

    def test_situation_credential_hashes_state_after_mutation(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        result = self.cli_with_situation(
            repo, package, "recovery", "checkpoint", "--next", "verify after mutation", "--evidence", "evidence.md"
        )
        self.assert_situation_footer(result)
        credential = json.loads((package / "execution/initial/situation-digest.json").read_text(encoding="utf-8"))
        state_sha256 = hashlib.sha256((package / ".impl-package/state.json").read_bytes()).hexdigest()
        self.assertEqual(credential["state_sha256"], state_sha256)

    def test_render_failure_does_not_change_success_or_stdout(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        stdout = StringIO()
        stderr = StringIO()

        with patch.dict(os.environ, {"IMPL_PACKAGE_NO_SITUATION": "0"}), patch.object(
            command_groups.situation, "main", side_effect=RuntimeError("render boom")
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            code = command_groups.main(
                package,
                "recovery",
                ["checkpoint", "--next", "render failure path", "--evidence", "evidence.md"],
            )

        self.assertEqual(code, 0)
        self.assertEqual(stderr.getvalue(), "")
        self.assertNotIn("[处境]", stdout.getvalue())
        self.assertEqual(json.loads(stdout.getvalue())["subject"], "attempt")

    def test_package_validate_appends_footer_on_nonzero_exit(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)
        stdout = StringIO()
        stderr = StringIO()

        with patch.dict(os.environ, {"IMPL_PACKAGE_NO_SITUATION": "0"}), patch.object(
            engine, "command_validate", side_effect=engine.StateError("validate fixture failure")
        ), redirect_stdout(stdout), redirect_stderr(stderr):
            code = command_groups.main(package, "package", ["validate"])

        self.assertEqual(code, 1)
        self.assertIn("validate fixture failure", stderr.getvalue())
        self.assertRegex(stdout.getvalue(), r"\[处境\] digest=[0-9a-f]{12}")

    def test_no_situation_flag_and_environment_switch_each_disable_footer(self) -> None:
        temp, repo, package = self.make_repo()
        self.addCleanup(temp.cleanup)
        self.init(repo, package)

        with patch.dict(os.environ, {"IMPL_PACKAGE_NO_SITUATION": "0"}):
            flag = self.cli(
                repo,
                package,
                "--no-situation",
                "recovery",
                "checkpoint",
                "--next",
                "flag disabled",
                "--evidence",
                "evidence.md",
            )
        with patch.dict(os.environ, {"IMPL_PACKAGE_NO_SITUATION": "1"}):
            env = self.cli(
                repo,
                package,
                "recovery",
                "checkpoint",
                "--next",
                "environment disabled",
                "--evidence",
                "evidence.md",
            )

        for result in (flag, env):
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("[处境]", result.stdout)
            self.assertIsInstance(json.loads(result.stdout), dict)


if __name__ == "__main__":
    unittest.main()
