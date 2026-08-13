from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_ROOT = ROOT / "plugin-marketplace/plugins/impl-package/scripts"
sys.path.insert(0, str(SCRIPT_ROOT))
from validate_ticket_first_migration import MigrationError, validate_migration  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    if result.returncode:
        raise AssertionError(result.stderr or result.stdout)
    return result.stdout.strip()


class TicketFirstMigrationTests(unittest.TestCase):
    def make_candidate(
        self,
        *,
        include_spec: bool = True,
        publication: str | None = "Approved",
        baseline_execution_record: str | None = None,
        include_execution_baseline: bool = True,
    ) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name) / "repo"
        repo.mkdir()
        package = repo / "packages" / "topic"
        (package / ".impl-package").mkdir(parents=True)
        (package / "execution/initial").mkdir(parents=True)
        (package / "migration/archive/task-handoffs").mkdir(parents=True)
        (package / "evidence").mkdir()
        (package / "tickets").mkdir()
        if include_spec:
            (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
        (package / "tickets/01.md").write_text(
            "**Ticket ID：** TKT-01\n"
            + (f"**Publication Status：** {publication}\n" if publication is not None else "")
            + "**Attempt ID：** initial\n\n"
            "## 验收标准\n"
            "- Stable claim ID：`AC-1`\n"
            "  - 证据时机：`early-falsification`\n",
            encoding="utf-8",
        )
        (package / "plan.md").write_text(
            "# Plan\n\nAttempt ID：initial\nComposition：tickets=true, dag=false\n",
            encoding="utf-8",
        )
        (package / "evidence/source-output.md").write_text("verified source\n", encoding="utf-8")
        execution_record = (
            "# Execution Record · initial\n\n"
            "- Attempt: initial\n"
            "- Lifecycle: active\n"
            "- Gate: open\n\n"
            "## initial-ER-001 · judgment\n\n"
            "- Subject: attempt\n"
            "- Title: Source output exists\n"
            "- Next action: none\n\n"
            "### Evidence\n\n"
            "- packages/topic/evidence/source-output.md\n\n"
            "### Content\n\n"
            "The source output is retained as migration evidence.\n"
        )
        execution_path = package / "execution/initial/execution-record.md"
        if include_execution_baseline:
            execution_path.write_text(
                baseline_execution_record if baseline_execution_record is not None else execution_record,
                encoding="utf-8",
            )
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Migration Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
        if not include_execution_baseline:
            execution_path.write_text(execution_record, encoding="utf-8")
        (package / "migration/legacy-state.json").write_text(json.dumps({"formatVersion": "3.4"}), encoding="utf-8")
        revision = git(repo, "rev-parse", "HEAD")
        state = {
            "formatVersion": "3.5",
            "attempt": {"id": "initial", "plan": "packages/topic/plan.md"},
            "attemptHistory": [{
                "id": "initial",
                "plan": "packages/topic/plan.md",
                "lifecycle": "active",
                "gate": None,
                "executionRecord": "execution/initial/execution-record.md",
            }],
            "tickets": {"TKT-01": {"state": "PENDING"}},
            "evidenceIndex": {
                "TKT-01": {
                    "AC-1": [{
                        "timing": "early-falsification",
                        "artifact": "packages/topic/evidence/source-output.md",
                        "revision": revision,
                        "environment": "test",
                        "conclusion": "supporting",
                    }]
                }
            },
            "activeCheckpoints": {
                "attempt": {
                    "next": "continue",
                    "blocker": None,
                    "evidence": ["packages/topic/evidence/source-output.md"],
                }
            },
        }
        (package / ".impl-package/state.json").write_text(json.dumps(state), encoding="utf-8")
        (package / "progress.md").write_text(
            "# Attempt Progress · initial\n\n"
            "> machine-owned projection；使用 `refresh-progress` 重建，不直接编辑。\n\n"
            "- Attempt: initial\n"
            "- Contract aliases: none (Git commit is the history anchor)\n"
            "- Composition: tickets=true, dag=false\n"
            "- Lifecycle: active\n"
            "- Latest gate: open\n"
            "- Blockers: none\n\n"
            "## Ticket Acceptance\n\n"
            "| Ticket | State | Evidence |\n"
            "| --- | --- | --- |\n"
            "| TKT-01 | PENDING | AC-1 |\n\n"
            "## Active Checkpoints\n\n"
            "| Subject | Status | Next action | Evidence |\n"
            "| --- | --- | --- | --- |\n"
            "| attempt | active | continue | packages/topic/evidence/source-output.md |\n\n"
            "## Attempt History\n\n"
            "| Attempt | Lifecycle | Gate | Execution Record |\n"
            "| --- | --- | --- | --- |\n"
            "| initial | active | open | execution/initial/execution-record.md |\n",
            encoding="utf-8",
        )
        return temp, package

    def state(self, package: Path) -> tuple[Path, dict]:
        path = package / ".impl-package/state.json"
        return path, json.loads(path.read_text(encoding="utf-8"))

    def test_validator_accepts_candidate_and_reports_anchor(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        pre_anchor = git(package, "rev-parse", "HEAD")
        result = validate_migration(package, pre_anchor=pre_anchor)
        self.assertTrue(result["valid"])
        self.assertEqual(result["formatVersion"], "3.5")
        self.assertEqual(result["preMigrationAnchor"], pre_anchor)
        self.assertEqual(result["warnings"], [])

    def test_validator_rejects_missing_spec_and_publication_admission(self) -> None:
        for kwargs in ({"include_spec": False}, {"publication": None}, {"publication": "Draft"}):
            temp, package = self.make_candidate(**kwargs)
            self.addCleanup(temp.cleanup)
            with self.assertRaises(MigrationError):
                validate_migration(package)

    def test_validator_rejects_handoff_as_evidence_or_active_handoff_tree(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        state_path, state = self.state(package)
        state["evidenceIndex"]["TKT-01"]["AC-1"][0]["artifact"] = "execution/initial/task-handoffs/T1-handoff.md"
        (package / "execution/initial/task-handoffs").mkdir()
        (package / "execution/initial/task-handoffs/T1-handoff.md").write_text("handoff", encoding="utf-8")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package)

    def test_validator_requires_progress_projection_and_rejects_runtime_marker(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        (package / "progress.md").unlink()
        with self.assertRaises(MigrationError):
            validate_migration(package)

        temp2, package2 = self.make_candidate()
        self.addCleanup(temp2.cleanup)
        progress = package2 / "progress.md"
        progress.write_text(progress.read_text(encoding="utf-8").replace("| TKT-01 | PENDING | AC-1 |", "| TKT-01 | BLOCKED | AC-1 |"), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package2)

        temp3, package3 = self.make_candidate()
        self.addCleanup(temp3.cleanup)
        ticket = package3 / "tickets/01.md"
        ticket.write_text(ticket.read_text(encoding="utf-8") + "\n<!-- impl-package:projection runtime-acceptance begin -->\n", encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package3)

    def test_validator_reuses_runtime_gate_parity_without_writing(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        gate = package / "gate.md"
        gate.write_text("# Gate\n\n- Verdict: pass\n", encoding="utf-8")
        with self.assertRaisesRegex(MigrationError, "runtime validate"):
            validate_migration(package)
        self.assertEqual(gate.read_text(encoding="utf-8"), "# Gate\n\n- Verdict: pass\n")

        temp2, package2 = self.make_candidate()
        self.addCleanup(temp2.cleanup)
        revision = git(package2, "rev-parse", "HEAD")
        gate2 = package2 / "gate.md"
        gate2.write_text(
            "# Gate\n\n"
            "- Verdict: pass\n"
            "- Attempt: initial\n"
            f"- Comparison commit: {revision}\n"
            "- Reason: fixture\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(MigrationError, "runtime validate"):
            validate_migration(package2)
        self.assertIn("- Verdict: pass", gate2.read_text(encoding="utf-8"))

    def test_validator_binds_anchor_history_and_checkpoint_paths(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        with self.assertRaises(MigrationError):
            validate_migration(package, pre_anchor="deadbeef")

        state_path, state = self.state(package)
        state["attemptHistory"][0].pop("executionRecord")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package)

        temp2, package2 = self.make_candidate()
        self.addCleanup(temp2.cleanup)
        state_path2, state2 = self.state(package2)
        state2["attemptHistory"][0]["executionRecord"] = "execution/other/execution-record.md"
        (package2 / "execution/other").mkdir()
        (package2 / "execution/other/execution-record.md").write_text(
            (package2 / "execution/initial/execution-record.md").read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        state_path2.write_text(json.dumps(state2), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package2)

        temp3, package3 = self.make_candidate()
        self.addCleanup(temp3.cleanup)
        state_path3, state3 = self.state(package3)
        state3["activeCheckpoints"]["attempt"]["evidence"] = ["missing.md"]
        state_path3.write_text(json.dumps(state3), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package3)

    def test_validator_rejects_execution_record_header_empty_and_bad_entry(self) -> None:
        cases = {
            "header": lambda text: text.replace("- Lifecycle: active", "- Lifecycle: frozen"),
            "empty": lambda text: text.replace("The source output is retained as migration evidence.", ""),
            "bad-entry": lambda text: text.replace("- Subject: attempt", "- Subject:"),
            "bad-sequence": lambda text: text.replace("initial-ER-001", "initial-ER-002"),
        }
        for name, mutate in cases.items():
            temp, package = self.make_candidate()
            self.addCleanup(temp.cleanup)
            path = package / "execution/initial/execution-record.md"
            path.write_text(mutate(path.read_text(encoding="utf-8")), encoding="utf-8")
            with self.assertRaises(MigrationError, msg=name):
                validate_migration(package)

    def test_validator_rejects_missing_timing_and_bad_satisfied_coverage(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        ticket = package / "tickets/01.md"
        ticket.write_text(ticket.read_text(encoding="utf-8").replace("  - 证据时机：`early-falsification`\n", ""), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package)

        temp2, package2 = self.make_candidate()
        self.addCleanup(temp2.cleanup)
        state_path, state = self.state(package2)
        revision = git(package2, "rev-parse", "HEAD")
        state["tickets"]["TKT-01"] = {"state": "SATISFIED", "acceptance": {"revision": revision, "environment": "test"}}
        state["evidenceIndex"]["TKT-01"]["AC-1"][0]["conclusion"] = "contradictory"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package2)

    def test_validator_returns_warning_when_source_baseline_is_unavailable(self) -> None:
        temp, package = self.make_candidate(include_execution_baseline=False)
        self.addCleanup(temp.cleanup)
        pre_anchor = git(package, "rev-parse", "HEAD")
        result = validate_migration(package, pre_anchor=pre_anchor)
        self.assertTrue(result["valid"])
        self.assertTrue(any(item["code"] == "source-execution-record-unavailable" for item in result["warnings"]))

    def test_validator_returns_warning_for_unparseable_source_baseline(self) -> None:
        old = "# legacy execution record\nnot machine readable\n"
        temp, package = self.make_candidate(baseline_execution_record=old)
        self.addCleanup(temp.cleanup)
        # The candidate is the normalized ER; the pre-anchor contains legacy text.
        path = package / "execution/initial/execution-record.md"
        path.write_text(
            "# Execution Record · initial\n\n- Attempt: initial\n- Lifecycle: active\n- Gate: open\n\n"
            "## initial-ER-001 · judgment\n\n- Subject: attempt\n- Title: Source output exists\n\n"
            "### Evidence\n\n- packages/topic/evidence/source-output.md\n\n"
            "### Content\n\nNormalized candidate judgment.\n",
            encoding="utf-8",
        )
        pre_anchor = git(package, "rev-parse", "HEAD")
        result = validate_migration(package, pre_anchor=pre_anchor)
        self.assertTrue(result["valid"])
        self.assertTrue(any(item["code"] == "source-execution-record-unparseable" for item in result["warnings"]))

    def test_validator_rejects_readable_source_judgment_content_diff(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        pre_anchor = git(package, "rev-parse", "HEAD")
        path = package / "execution/initial/execution-record.md"
        path.write_text(
            path.read_text(encoding="utf-8").replace(
                "The source output is retained as migration evidence.",
                "Candidate deliberately records a clarified judgment.",
            ),
            encoding="utf-8",
        )
        with self.assertRaises(MigrationError):
            validate_migration(package, pre_anchor=pre_anchor)

    def test_validator_rejects_missing_readable_source_judgment(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        pre_anchor = git(package, "rev-parse", "HEAD")
        path = package / "execution/initial/execution-record.md"
        path.write_text(
            "# Execution Record · initial\n\n"
            "- Attempt: initial\n"
            "- Lifecycle: active\n"
            "- Gate: open\n",
            encoding="utf-8",
        )
        with self.assertRaises(MigrationError):
            validate_migration(package, pre_anchor=pre_anchor)


if __name__ == "__main__":
    unittest.main()
