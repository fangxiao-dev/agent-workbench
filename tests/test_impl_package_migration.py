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
    def make_candidate(self) -> tuple[tempfile.TemporaryDirectory[str], Path]:
        temp = tempfile.TemporaryDirectory()
        repo = Path(temp.name) / "repo"
        repo.mkdir()
        package = repo / "packages" / "topic"
        (package / ".impl-package").mkdir(parents=True)
        (package / "execution/initial").mkdir(parents=True)
        (package / "migration/archive/task-handoffs").mkdir(parents=True)
        (package / "evidence").mkdir()
        (package / "tickets").mkdir()
        (package / "tickets/01.md").write_text("**Ticket ID：** TKT-01\n**Attempt ID：** initial\n\n## 验收标准\n- Stable claim ID：`AC-1`\n  - 证据时机：`early-falsification`\n", encoding="utf-8")
        (package / "plan.md").write_text("# Plan\n\nAttempt ID：initial\nComposition：tickets=true, dag=false\n", encoding="utf-8")
        (package / "evidence/source-output.md").write_text("verified source\n", encoding="utf-8")
        subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
        subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
        subprocess.run(["git", "config", "user.name", "Migration Test"], cwd=repo, check=True)
        subprocess.run(["git", "add", "."], cwd=repo, check=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=repo, check=True, capture_output=True)
        (package / "migration/legacy-state.json").write_text(json.dumps({"formatVersion": "3.4"}), encoding="utf-8")
        (package / "execution/initial/execution-record.md").write_text("# Execution Record · initial\n- Attempt: initial\n- Lifecycle: active\n- Gate: open\n", encoding="utf-8")
        state = {
            "formatVersion": "3.5",
            "attempt": {"id": "initial", "plan": "packages/topic/plan.md"},
            "attemptHistory": [{"id": "initial", "plan": "packages/topic/plan.md", "lifecycle": "active", "gate": None, "executionRecord": "execution/initial/execution-record.md"}],
            "tickets": {"TKT-01": {"state": "PENDING"}},
            "evidenceIndex": {"TKT-01": {"AC-1": [{"timing": "early-falsification", "artifact": "packages/topic/evidence/source-output.md", "revision": git(repo, "rev-parse", "HEAD"), "environment": "test", "conclusion": "supporting"}]}},
            "activeCheckpoints": {"attempt": {"next": "continue", "blocker": None, "evidence": ["packages/topic/evidence/source-output.md"]}},
        }
        (package / ".impl-package/state.json").write_text(json.dumps(state), encoding="utf-8")
        return temp, package

    def test_validator_accepts_candidate_and_reports_anchor(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        pre_anchor = git(package, "rev-parse", "HEAD")
        result = validate_migration(package, pre_anchor=pre_anchor)
        self.assertTrue(result["valid"])
        self.assertEqual(result["formatVersion"], "3.5")
        self.assertEqual(result["preMigrationAnchor"], pre_anchor)

    def test_validator_rejects_handoff_as_evidence_or_active_handoff_tree(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        state_path = package / ".impl-package/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["evidenceIndex"]["TKT-01"]["AC-1"][0]["artifact"] = "execution/initial/task-handoffs/T1-handoff.md"
        (package / "execution/initial/task-handoffs").mkdir()
        (package / "execution/initial/task-handoffs/T1-handoff.md").write_text("handoff", encoding="utf-8")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package)

    def test_validator_binds_anchor_history_and_checkpoint_paths(self) -> None:
        temp, package = self.make_candidate()
        self.addCleanup(temp.cleanup)
        with self.assertRaises(MigrationError):
            validate_migration(package, pre_anchor="deadbeef")

        state_path = package / ".impl-package/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["attemptHistory"][0].pop("executionRecord")
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package)

        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["attemptHistory"] = [{"id": "initial", "plan": "packages/topic/plan.md", "lifecycle": "active", "gate": None, "executionRecord": "execution/initial/execution-record.md"}]
        state["activeCheckpoints"]["attempt"]["evidence"] = ["missing.md"]
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
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
        state_path = package2 / ".impl-package/state.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        revision = git(package2, "rev-parse", "HEAD")
        state["tickets"]["TKT-01"] = {"state": "SATISFIED", "acceptance": {"revision": revision, "environment": "test"}}
        state_path.write_text(json.dumps(state), encoding="utf-8")
        index_path = package2 / "evidence/source-output.md"
        index_path.write_text("contradictory source\n", encoding="utf-8")
        state["evidenceIndex"]["TKT-01"]["AC-1"][0]["conclusion"] = "contradictory"
        state_path.write_text(json.dumps(state), encoding="utf-8")
        with self.assertRaises(MigrationError):
            validate_migration(package2)



if __name__ == "__main__":
    unittest.main()
