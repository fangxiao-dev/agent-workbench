from __future__ import annotations

import json
import subprocess
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from jsonschema import Draft202012Validator, ValidationError

from scripts.codex_harness_orchestrator import (
    CONTROL_SCHEMA_VERSION,
    ORCHESTRATOR_TURN_SCHEMA_VERSION,
    FullVerificationRequired,
    OrchestratorError,
    accept_assignment,
    apply_orchestrator_turn,
    make_assignment,
    new_snapshot,
    ready_assignment_ids,
    record_broker_message,
    record_worker_result,
    run_full_verifier,
    run_orchestrator_turn,
    start_worker_cohort,
    validate_snapshot,
    worker_git_writable_roots,
)


ROOT = Path(__file__).resolve().parents[1]
CATALOG = {
    "data": [
        {"id": "gpt-5.6-luna", "supportedReasoningEfforts": [{"reasoningEffort": "max"}]},
        {"id": "gpt-5.6-terra", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]},
        {"id": "gpt-5.6-sol", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]},
    ]
}


def snapshot(root: Path = ROOT, *, run_id: str | None = None) -> dict:
    state_root = Path(tempfile.gettempdir()) / "codex-harness-tests"
    state_root.mkdir(parents=True, exist_ok=True)
    state_path = state_root / f"orchestrator-{uuid.uuid4().hex}.json"
    return new_snapshot(root, "capability host test", state_path, run_id=run_id or f"test-{uuid.uuid4().hex[:8]}")


def definition(state: dict, assignment_id: str, path: str, *, revision: int = 1, assurance: str = "lite", depends_on: list[str] | None = None, allowed_paths: list[str] | None = None, access_mode: str = "workspace_write") -> dict:
    return {
        "assignment_id": assignment_id,
        "kind": "delivery",
        "revision": revision,
        "goal": f"deliver {assignment_id}",
        "non_goals": [],
        "acceptance_criteria": [f"{assignment_id} is complete"],
        "assurance_mode": assurance,
        "execution_profile": "worker-full-terra-high" if assurance == "full" else "worker-lite-luna-max",
        "access_mode": access_mode,
        "allowed_paths": [] if access_mode == "repository_read_only" else (allowed_paths or [path]),
        "external_resources": [],
        "verification_commands": ["check"],
        "depends_on": depends_on or [],
        "context": {"fresh": True, "continuation_allowed": True},
        "workspace": None if access_mode == "repository_read_only" else {
            "strategy": "new",
            "handoff_from": None,
            "path": str((Path(state["workspace_root"]) / assignment_id).resolve()),
            "branch": f"codex/crew/{state['run_id']}/{assignment_id}/work",
            "base_ref": "HEAD",
        },
    }


def turn(state: dict, action: str, **fields: object) -> dict:
    return {"schema_version": ORCHESTRATOR_TURN_SCHEMA_VERSION, "run_id": state["run_id"], "action": action, "summary": f"{action} action", **fields}


def terminal_role(envelope: dict) -> dict:
    thread_id = "orchestrator-thread"
    return {
        "status": "completed",
        "thread_id": thread_id,
        "turn_id": "orchestrator-turn",
        "cancel_request": None,
        "interrupt": {"attempted": False, "acknowledged": False, "error": None},
        "terminal": {"observed": True, "status": "completed", "source": "turn/completed"},
        "notifications": [{"method": "turn/completed", "params": {"threadId": thread_id, "turn": {"status": "completed"}}}],
        "history": {"items": [{"type": "agentMessage", "threadId": thread_id, "text": json.dumps(envelope)}]},
    }


class CodexHarnessOrchestratorTest(unittest.TestCase):
    def test_snapshot_is_capability_panorama_without_topology_or_action_budget(self) -> None:
        state = snapshot()
        self.assertEqual(state["schema_version"], CONTROL_SCHEMA_VERSION)
        self.assertEqual(state["crew"]["intent"]["shape"], "orchestrator_read_only")
        self.assertEqual(state["crew"]["observed"]["active_worker_ids"], [])
        self.assertNotIn("execution", state)
        self.assertNotIn("action_count", state)
        self.assertNotIn("max_actions", state)

    def test_control_schema_accepts_snapshot_and_rejects_retired_fields(self) -> None:
        schema = json.loads((ROOT / "skills/codex-harness/assets/codex-crew.control.v0.5.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        state = snapshot()
        Draft202012Validator(schema).validate(state)
        state["action_count"] = 1
        with self.assertRaises(ValidationError):
            Draft202012Validator(schema).validate(state)

    def test_orchestrator_turn_schema_accepts_read_and_write_assignments(self) -> None:
        schema = json.loads((ROOT / "skills/codex-harness/assets/codex-crew.orchestrator-turn.v0.3.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        state = snapshot()
        envelope = turn(state, "dispatch", assignments=[definition(state, "audit", "", access_mode="repository_read_only"), definition(state, "delivery", "src/delivery")])
        Draft202012Validator(schema).validate(envelope)

    def test_dispatch_defines_assignment_without_worker_or_worktree(self) -> None:
        state = snapshot()
        proposal = definition(state, "delivery", "src/delivery")
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[proposal]))
        assignment = state["assignments"][0]
        self.assertEqual(assignment["status"], "planned")
        self.assertFalse(assignment["workspace"]["materialized"])
        self.assertEqual(assignment["worker"]["status"], "pending")
        self.assertEqual(state["crew"]["observed"]["ready_assignment_ids"], ["delivery"])

    def test_dispatch_revision_requires_inactive_unaccepted_revision_plus_one(self) -> None:
        state = snapshot()
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "delivery", "src/delivery")]))
        revised = definition(state, "delivery", "src/delivery", revision=2)
        revised["goal"] = "revised cohesive delivery"
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[revised]))
        self.assertEqual(state["assignments"][0]["revision"], 2)
        with self.assertRaisesRegex(OrchestratorError, "revision"):
            apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "delivery", "src/delivery", revision=4)]))

    def test_more_than_32_valid_actions_are_not_mechanically_stopped(self) -> None:
        state = snapshot()
        for revision in range(1, 41):
            apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "delivery", "src/delivery", revision=revision)]))
        self.assertEqual(state["assignments"][0]["revision"], 40)
        self.assertEqual(state["status"], "running")

    def test_start_workers_runs_only_selected_assignment(self) -> None:
        state = snapshot()
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "a", "src/a"), definition(state, "b", "src/b")]))
        seen: list[str] = []

        def runner(assignment_id: str, _task: dict) -> dict:
            seen.append(assignment_id)
            return {"status": "needs_orchestrator", "summary": "pause", "changed_paths": [], "verification": [], "worker_thread_id": f"thread-{assignment_id}", "turn_id": f"turn-{assignment_id}"}

        with patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG), patch("scripts.codex_harness_orchestrator.ensure_worktree", side_effect=lambda _root, workspace: {"path": workspace["path"], "branch": workspace["branch"], "created": True}), patch("scripts.codex_harness_orchestrator._git", return_value="base"), patch("scripts.codex_harness_orchestrator.worker_git_writable_roots", return_value=[str(ROOT)]):
            results = start_worker_cohort(state, ["a"], worker_runner=runner)
        self.assertEqual(seen, ["a"])
        self.assertEqual(results[0]["status"], "needs_orchestrator")
        self.assertEqual(state["assignments"][1]["status"], "planned")
        self.assertFalse(state["assignments"][1]["workspace"]["materialized"])

    def test_disjoint_workers_actually_overlap_in_one_explicit_cohort(self) -> None:
        state = snapshot()
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "a", "src/a"), definition(state, "b", "src/b")]))
        barrier = threading.Barrier(2)
        intervals: dict[str, tuple[float, float]] = {}

        def runner(assignment_id: str, _task: dict) -> dict:
            started = time.monotonic()
            barrier.wait(timeout=2)
            time.sleep(0.05)
            intervals[assignment_id] = (started, time.monotonic())
            return {"status": "needs_orchestrator", "summary": "pause", "changed_paths": [], "verification": [], "worker_thread_id": f"thread-{assignment_id}", "turn_id": f"turn-{assignment_id}"}

        with patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG), patch("scripts.codex_harness_orchestrator.ensure_worktree", side_effect=lambda _root, workspace: {"path": workspace["path"], "branch": workspace["branch"], "created": True}), patch("scripts.codex_harness_orchestrator._git", return_value="base"), patch("scripts.codex_harness_orchestrator.worker_git_writable_roots", return_value=[str(ROOT)]):
            start_worker_cohort(state, ["a", "b"], worker_runner=runner)
        self.assertLess(max(value[0] for value in intervals.values()), min(value[1] for value in intervals.values()))
        self.assertEqual(state["crew"]["observed"]["active_worker_ids"], [])

    def test_read_only_cohort_runs_without_branch_worktree_or_write_lease(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (repo / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-m", "base"], check=True, capture_output=True)
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            state = snapshot(repo, run_id="read-only-cohort")
            apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "audit-a", "", access_mode="repository_read_only"), definition(state, "audit-b", "", access_mode="repository_read_only")]))
            barrier = threading.Barrier(2)

            def runner(assignment_id: str, task: dict) -> dict:
                self.assertEqual(task["access_mode"], "repository_read_only")
                self.assertEqual(Path(task["worktree"]["path"]).resolve(), repo.resolve())
                self.assertNotIn("writable_roots", task)
                barrier.wait(timeout=2)
                return {"status": "succeeded", "summary": f"audited {assignment_id}", "changed_paths": [], "verification": [{"command": "inspect", "exit_code": 0, "claim": "observed"}], "worker_thread_id": f"thread-{assignment_id}", "turn_id": f"turn-{assignment_id}"}

            with patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG), patch("scripts.codex_harness_orchestrator.ensure_worktree", side_effect=AssertionError("read-only cohort must not create a worktree")):
                results = start_worker_cohort(state, ["audit-a", "audit-b"], worker_runner=runner)
        self.assertEqual([item["status"] for item in results], ["succeeded", "succeeded"])
        self.assertTrue(all(item["workspace"] is None for item in state["assignments"]))
        self.assertTrue(all(item["boundary_evidence"]["source_revision"] == head for item in state["assignments"]))
        self.assertTrue(all(item["boundary_evidence"]["pre_git"]["porcelain"] == item["boundary_evidence"]["post_git"]["porcelain"] for item in state["assignments"]))
        self.assertEqual(state["crew"]["observed"]["active_write_leases"], [])

    def test_read_only_worker_repository_drift_blocks_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "base"], check=True, capture_output=True)
            state = snapshot(repo, run_id="read-only-drift")
            apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "audit", "", access_mode="repository_read_only")]))

            def runner(_assignment_id: str, _task: dict) -> dict:
                (repo / "unexpected.txt").write_text("mutation\n", encoding="utf-8")
                return {"status": "succeeded", "summary": "invalid", "changed_paths": [], "verification": [{"command": "inspect", "exit_code": 0, "claim": "observed"}]}

            with patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG), patch("scripts.codex_harness_orchestrator.ensure_worktree", side_effect=AssertionError("read-only assignment must not create a worktree")):
                results = start_worker_cohort(state, ["audit"], worker_runner=runner)
        self.assertEqual(results[0]["status"], "failed")
        self.assertEqual(state["status"], "blocked")
        self.assertEqual(state["quarantine"]["reason"], "read_only_worker_boundary_changed")
        schema = json.loads((ROOT / "skills/codex-harness/assets/codex-crew.control.v0.5.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(state)

    def test_full_read_only_assignment_uses_explicit_verifier_and_acceptance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "base"], check=True, capture_output=True)
            head = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            state = snapshot(repo, run_id="full-read-only")
            apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "audit", "", assurance="full", access_mode="repository_read_only")]))

            def worker(_assignment_id: str, _task: dict) -> dict:
                return {"status": "succeeded", "summary": "audited", "changed_paths": [], "verification": [{"command": "inspect", "exit_code": 0, "claim": "observed"}], "worker_thread_id": "worker-thread", "turn_id": "worker-turn"}

            def verifier(_request: dict) -> dict:
                return {"status": "passed", "summary": "verified", "findings": [], "verification": [{"command": "inspect", "exit_code": 0}], "_controller_evidence": {"thread_id": "verifier-thread", "turn_id": "verifier-turn"}}

            with patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG):
                start_worker_cohort(state, ["audit"], worker_runner=worker)
                result = run_full_verifier(state, "audit", verifier)
                acceptance = accept_assignment(state, "audit")
        self.assertEqual(result["status"], "passed")
        self.assertEqual(acceptance["commit"], head)
        self.assertIsNone(acceptance["handoff"])

    def test_cohort_preflight_rejects_overlap_and_fifth_worker_before_materialization(self) -> None:
        state = snapshot()
        proposals = [definition(state, f"a{index}", "src/shared" if index < 2 else f"src/a{index}") for index in range(5)]
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=proposals))
        with patch("scripts.codex_harness_orchestrator.ensure_worktree") as ensure:
            with self.assertRaisesRegex(OrchestratorError, "overlapping"):
                start_worker_cohort(state, ["a0", "a1"])
            with self.assertRaisesRegex(OrchestratorError, "one to 4"):
                start_worker_cohort(state, [f"a{index}" for index in range(5)])
        ensure.assert_not_called()

    def test_worker_git_roots_are_limited_to_linked_metadata_objects_and_assignment_ref(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory) / "repo"
            repo.mkdir()
            subprocess.run(["git", "-C", str(repo), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(repo), "commit", "--allow-empty", "-m", "base"], check=True, capture_output=True)
            worktree = Path(directory) / "worker"
            branch = "codex/crew/git-roots/assignment/work"
            subprocess.run(["git", "-C", str(repo), "worktree", "add", "-b", branch, str(worktree), "HEAD"], check=True, capture_output=True)
            roots = [Path(item) for item in worker_git_writable_roots(worktree, branch, "git-roots", "assignment")]
            common = Path(subprocess.run(["git", "-C", str(worktree), "rev-parse", "--git-common-dir"], check=True, capture_output=True, text=True).stdout.strip()).resolve()
        self.assertEqual(len(roots), 4)
        self.assertNotIn(common, roots)
        self.assertIn((common / "objects").resolve(), roots)
        self.assertIn((common / "refs/heads/codex/crew/git-roots/assignment").resolve(), roots)

    def test_local_owner_gate_does_not_block_unrelated_assignment(self) -> None:
        state = snapshot()
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "blocked", "src/blocked"), definition(state, "free", "src/free")]))
        apply_orchestrator_turn(state, turn(state, "ask_owner", request={"scope": "assignment", "assignment_id": "blocked", "category": "scope_change", "detail": "Choose the bounded scope."}))
        self.assertEqual(ready_assignment_ids(state), ["free"])
        self.assertEqual(state["status"], "running")

    def test_owner_decision_binds_one_request_and_does_not_start_worker(self) -> None:
        state = snapshot()
        apply_orchestrator_turn(state, turn(state, "dispatch", assignments=[definition(state, "blocked", "src/blocked")]))
        apply_orchestrator_turn(state, turn(state, "ask_owner", request={"scope": "assignment", "assignment_id": "blocked", "category": "scope_change", "detail": "Choose the bounded scope."}))
        request_id = state["owner_requests"][0]["request_id"]
        record_broker_message(state, "approved within current scope", kind="owner_decision", request_id=request_id, decision={"disposition": "approved", "detail": "Proceed."})
        self.assertEqual(state["owner_requests"][0]["status"], "resolved")
        self.assertEqual(state["assignments"][0]["status"], "planned")
        self.assertEqual(state["assignments"][0]["worker"]["status"], "pending")
        with self.assertRaisesRegex(OrchestratorError, "open request"):
            record_broker_message(state, "duplicate", kind="owner_decision", request_id=request_id, decision={"disposition": "approved", "detail": "Again."})

    def test_worker_success_does_not_auto_run_verifier_or_finish(self) -> None:
        state = snapshot()
        assignment = make_assignment("full", "full delivery", run_id=state["run_id"], assurance_mode="full", allowed_paths=["src"], verification_commands=["check"], workspace_path=str(Path(state["workspace_root"]) / "full"), workspace_branch=f"codex/crew/{state['run_id']}/full/work", workspace_base_ref="HEAD")
        assignment["workspace"]["materialized"] = True
        assignment["status"] = "running"
        assignment["worker"]["status"] = "running"
        assignment["workspace"]["lease"] = {"status": "active", "acquired_at": time.time(), "released_at": None}
        state["assignments"] = [assignment]
        record_worker_result(state, "full", {"status": "succeeded", "summary": "submitted", "commit": "abc", "changed_paths": [], "verification": [{"command": "check", "exit_code": 0}], "worker_thread_id": "worker-thread", "turn_id": "worker-turn"})
        self.assertEqual(assignment["status"], "submitted")
        self.assertEqual(assignment["verifier"]["status"], "pending")
        self.assertEqual(state["status"], "running")
        self.assertIsNone(state["terminal"])
        with patch("scripts.codex_harness_orchestrator._git", return_value="abc"), patch("scripts.codex_harness_orchestrator.git_status", return_value=[]):
            with self.assertRaises(FullVerificationRequired):
                accept_assignment(state, "full")

    def test_full_verifier_accept_and_finish_are_three_explicit_steps(self) -> None:
        state = snapshot()
        assignment = make_assignment("full", "full delivery", run_id=state["run_id"], assurance_mode="full", allowed_paths=["src"], verification_commands=["check"], workspace_path=str(Path(state["workspace_root"]) / "full"), workspace_branch=f"codex/crew/{state['run_id']}/full/work", workspace_base_ref="base")
        assignment["workspace"]["materialized"] = True
        assignment["status"] = "submitted"
        assignment["result"] = {"schema_version": "codex-crew.worker-result.v0.1", "assignment_id": "full", "revision": 1, "status": "succeeded", "summary": "done", "commit": "head", "artifacts": [], "verification": [{"command": "check", "exit_code": 0}], "changed_paths": [], "owner_request": None, "subagent_telemetry": {"delegated": False, "active_count": 0}, "worker_thread_id": "worker-thread", "worker_turn_id": "worker-turn"}
        state["assignments"] = [assignment]
        binding = {"run_id": state["run_id"], "assignment_id": "full", "revision": 1, "base_commit": "base", "head_commit": "head", "worker_result_digest": "digest", "workspace_path": assignment["workspace"]["path"], "goal": assignment["goal"], "non_goals": [], "acceptance_criteria": assignment["acceptance_criteria"], "verification_commands": ["check"]}

        def verifier(_request: dict) -> dict:
            return {"status": "passed", "summary": "verified", "findings": [], "verification": [{"command": "check", "exit_code": 0}], "_controller_evidence": {"thread_id": "verifier-thread", "turn_id": "verifier-turn"}}

        handoff = {"schema_version": "codex-crew.serial-handoff.v0", "delivery_program_id": state["run_id"], "worktree": assignment["workspace"]["path"], "commit": "head", "verification": assignment["result"]["verification"]}
        with patch("scripts.codex_harness_orchestrator._verifier_binding", return_value=binding), patch("scripts.codex_harness_orchestrator.fetch_model_catalog", return_value=CATALOG), patch("scripts.codex_harness_orchestrator._git", return_value="head"), patch("scripts.codex_harness_orchestrator.git_status", return_value=[]), patch("scripts.codex_harness_orchestrator.serial_handoff_evidence", return_value=handoff):
            verdict = run_full_verifier(state, "full", verifier)
            self.assertEqual(verdict["status"], "passed")
            self.assertEqual(state["status"], "running")
            acceptance = accept_assignment(state, "full")
        self.assertEqual(acceptance["disposition"], "accepted")
        self.assertEqual(state["status"], "running")
        apply_orchestrator_turn(state, turn(state, "finish", disposition="succeeded", fact_refs=["acceptance:full"], incomplete_facts=[]))
        self.assertEqual(state["status"], "finished")
        self.assertEqual(state["terminal"]["disposition"], "succeeded")
        schema = json.loads((ROOT / "skills/codex-harness/assets/codex-crew.control.v0.5.schema.json").read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(state)

    def test_run_orchestrator_dispatch_turn_does_not_call_worker_runner(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state = snapshot(root, run_id="dispatch-only")
            envelope = turn(state, "dispatch", assignments=[definition(state, "delivery", "README.md")])

            def fake_role(**kwargs: object) -> dict:
                kwargs["on_thread_started"]("orchestrator-thread")
                kwargs["on_turn_started"]("orchestrator-thread", "orchestrator-turn")
                return terminal_role(envelope)

            def forbidden_worker(_assignment_id: str, _task: dict) -> dict:
                raise AssertionError("dispatch must not start a Worker")

            with patch("scripts.codex_harness_orchestrator.run_role_turn", side_effect=fake_role):
                result = run_orchestrator_turn(state, Path(state["state_path"]), resume=False, worker_runner=forbidden_worker)
        self.assertEqual(result["worker_results"], [])
        self.assertEqual(state["assignments"][0]["status"], "planned")


if __name__ == "__main__":
    unittest.main()
