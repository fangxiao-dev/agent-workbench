from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_dispatch import WORKER_RESULT_SCHEMA_VERSION, assignment_task, continue_assignment, ensure_worktree, run_worker


ROOT = Path(__file__).resolve().parents[1]


def assignment(workspace: Path) -> dict:
    return {
        "assignment_id": "delivery",
        "revision": 2,
        "goal": "deliver the bounded change",
        "non_goals": ["redesign"],
        "acceptance_criteria": ["focused check passes"],
        "access_mode": "workspace_write",
        "allowed_paths": ["README.md"],
        "verification_commands": ["check"],
        "workspace": {"path": str(workspace), "branch": "codex/delivery", "base_ref": "HEAD"},
        "boundary_evidence": {"source_revision": None, "pre_git": {}, "post_git": {}},
    }


def read_only_assignment(repository: Path) -> dict:
    return {
        "assignment_id": "audit",
        "revision": 1,
        "goal": "audit the fixed revision",
        "non_goals": ["mutation"],
        "acceptance_criteria": ["report cites repository evidence"],
        "access_mode": "repository_read_only",
        "allowed_paths": [],
        "verification_commands": ["inspect"],
        "workspace": None,
        "boundary_evidence": {"source_revision": "abc123", "pre_git": {}, "post_git": {}},
    }


class CodexHarnessDispatchTest(unittest.TestCase):
    def test_assignment_projection_is_cohesive_and_contains_no_scheduler_state(self) -> None:
        task = assignment_task(assignment(ROOT.parent / "delivery-worktree"), {"id": "worker-full-terra-high", "model": "gpt-5.6-terra", "reasoning_effort": "high"})
        self.assertEqual(task["id"], "delivery")
        self.assertEqual(task["revision"], 2)
        self.assertIn("Do not split package work", task["prompt"])
        self.assertNotIn("depends_on", task)
        self.assertNotIn("topology", task)

    def test_existing_worktree_must_match_registered_branch(self) -> None:
        target = ROOT.parent / "delivery-worktree"
        listing = f"worktree {target}\nbranch refs/heads/codex/delivery\n\n"
        with patch("scripts.codex_harness_dispatch.subprocess.run", return_value=type("Completed", (), {"stdout": listing})()):
            with patch.object(Path, "exists", return_value=True):
                result = ensure_worktree(ROOT, {"path": str(target), "branch": "codex/delivery", "base_ref": "HEAD"})
        self.assertEqual(result["created"], "false")

    def test_fresh_worker_uses_current_assignment_result_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            task = assignment_task(assignment(Path(temporary)), {"id": "worker-full-terra-high", "model": "gpt-5.6-terra", "reasoning_effort": "high"})
            envelope = json.dumps({"schema_version": WORKER_RESULT_SCHEMA_VERSION, "assignment_id": "delivery", "revision": 2, "status": "succeeded", "summary": "done", "commit": "abc", "changed_paths": ["README.md"], "artifacts": [], "verification": [{"command": "check", "exit_code": 0, "claim": "passed"}], "owner_request": None, "subagent_telemetry": {"delegated": False, "active_count": 0}})

            def role_turn(**kwargs: object) -> dict:
                self.assertIsNone(kwargs["thread_id"])
                self.assertTrue(kwargs["enable_multi_agent"])
                return {"status": "completed", "thread_id": "worker-thread", "turn_id": "worker-turn", "notifications": [], "history": {"type": "agentMessage", "text": envelope}}

            with patch("scripts.codex_harness_dispatch.run_role_turn", side_effect=role_turn):
                result = run_worker("delivery", task)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(result["worker_thread_id"], "worker-thread")
        self.assertEqual(result["worker_turn_id"], "worker-turn")

    def test_continuation_reuses_same_worker_thread(self) -> None:
        task = assignment_task(assignment(ROOT.parent / "delivery-worktree"), {"id": "worker-lite-terra-high", "model": "gpt-5.6-terra", "reasoning_effort": "high"})
        envelope = json.dumps({"schema_version": WORKER_RESULT_SCHEMA_VERSION, "assignment_id": "delivery", "revision": 2, "status": "needs_orchestrator", "summary": "need guidance", "verification": [], "owner_request": None})

        def role_turn(**kwargs: object) -> dict:
            self.assertEqual(kwargs["thread_id"], "worker-thread")
            return {"status": "completed", "thread_id": "worker-thread", "turn_id": "worker-turn-2", "notifications": [], "history": {"type": "agentMessage", "text": envelope}}

        with patch("scripts.codex_harness_dispatch.run_role_turn", side_effect=role_turn):
            result = continue_assignment(task, "worker-thread", "continue inside the same contract")
        self.assertEqual(result["status"], "needs_orchestrator")

    def test_read_only_worker_reuses_role_turn_without_writable_roots(self) -> None:
        task = assignment_task(read_only_assignment(ROOT), {"id": "worker-lite-terra-high", "model": "gpt-5.6-terra", "reasoning_effort": "high"}, repository_root=ROOT)
        envelope = json.dumps({"schema_version": WORKER_RESULT_SCHEMA_VERSION, "assignment_id": "audit", "revision": 1, "status": "succeeded", "summary": "audited", "commit": "abc123", "changed_paths": [], "artifacts": [], "verification": [{"command": "inspect", "exit_code": 0, "claim": "observed"}], "owner_request": None, "subagent_telemetry": {"delegated": False, "active_count": 0}})

        def role_turn(**kwargs: object) -> dict:
            self.assertEqual(kwargs["sandbox"], "read-only")
            self.assertIsNone(kwargs["writable_roots"])
            self.assertEqual(Path(kwargs["cwd"]).resolve(), ROOT.resolve())
            self.assertTrue(kwargs["enable_multi_agent"])
            return {"status": "completed", "thread_id": "audit-thread", "turn_id": "audit-turn", "notifications": [], "history": {"type": "agentMessage", "text": envelope}}

        with patch("scripts.codex_harness_dispatch.run_role_turn", side_effect=role_turn):
            result = run_worker("audit", task)
        self.assertEqual(result["status"], "succeeded")


if __name__ == "__main__":
    unittest.main()
