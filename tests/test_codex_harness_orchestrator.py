from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_orchestrator import (
    FullVerificationRequired,
    OrchestratorError,
    apply_topology,
    cancel_run,
    choose_topology,
    make_assignment,
    new_snapshot,
    ready_assignment_ids,
    record_broker_message,
    record_worker_result,
    recover_run,
    run_full_verifier,
    run_orchestrator_turn,
    validate_snapshot,
    validate_worker_diff,
)


ROOT = Path(__file__).resolve().parents[1]


def snapshot() -> dict:
    return new_snapshot(ROOT, "thin control test", ROOT / ".tmp-orchestrator-state.json", run_id="orchestrator-test")


class CodexHarnessOrchestratorTest(unittest.TestCase):
    def test_orchestrator_is_read_only_and_has_no_worker_worktree(self) -> None:
        state = snapshot()
        self.assertEqual(state["execution"]["topology"], "orchestrator_read_only")
        self.assertEqual(state["execution"]["max_active_write_worktrees"], 0)
        self.assertEqual(state["orchestrator"]["sandbox"], "read-only")
        self.assertEqual(state["orchestrator"]["turn"]["phase"], "not_started")
        self.assertEqual(state["orchestrator"]["requested_execution"]["model"], None)

    def test_default_artifact_root_is_outside_repository_and_override_is_preserved(self) -> None:
        state = snapshot()
        self.assertNotIn(ROOT.resolve(), Path(state["artifact_root"]).resolve().parents)
        override = ROOT.parent / "explicit-harness-artifacts"
        overridden = new_snapshot(ROOT, "override artifacts", ROOT / ".tmp-orchestrator-state.json", run_id="artifact-override", artifact_root=override)
        self.assertEqual(Path(overridden["artifact_root"]), override.resolve())

    def test_broker_message_persists_with_non_conflicting_event_metadata(self) -> None:
        state = snapshot()
        state["orchestrator"]["thread_id"] = "thread-existing"
        persisted = record_broker_message(state, "continue with the accepted scope")
        self.assertEqual(persisted["kind"], "ordinary_correction")
        self.assertEqual(state["messages"][-1]["body"], "continue with the accepted scope")
        self.assertEqual(state["events"][-1]["kind"], "broker_message_received")
        self.assertEqual(state["events"][-1]["message_kind"], "ordinary_correction")

    def test_worker_diff_outside_assignment_paths_is_rejected(self) -> None:
        assignment = make_assignment("a", "fix", allowed_paths=["src/api"])
        with self.assertRaises(OrchestratorError):
            validate_worker_diff(assignment, ["src/api/ok.py", "tests/other.py"])

    def test_stale_worker_result_revision_is_rejected(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("a", "fix", allowed_paths=["src"])]
        with self.assertRaises(OrchestratorError):
            record_worker_result(state, "a", {"assignment_id": "a", "revision": 2, "status": "succeeded", "summary": "stale", "changed_paths": [], "verification": []})

    def test_strict_serial_topology_allows_one_active_writer(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("a", "one", allowed_paths=["src/a"]), make_assignment("b", "two", allowed_paths=["src/b"])]
        validate_snapshot(state)
        apply_topology(state, "worker_serial")
        self.assertEqual(state["execution"]["max_active_write_worktrees"], 1)
        self.assertEqual(ready_assignment_ids(state), ["a", "b"])
        from scripts.codex_harness_orchestrator import materialize_workspaces

        with self.assertRaises(OrchestratorError):
            materialize_workspaces(state, ["a", "b"])

    def test_serial_reuse_requires_accepted_clean_handoff(self) -> None:
        from scripts.codex_harness_orchestrator import accept_assignment, materialize_workspaces

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            for args in (("init",), ("config", "user.email", "crew@example.test"), ("config", "user.name", "Crew Test")):
                subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state_path = Path(directory) / "state.json"
            state = new_snapshot(root, "serial handoff", state_path, run_id="serial-handoff-test", artifact_root=root / "artifacts")
            state["assignments"] = [make_assignment("one", "write one", allowed_paths=["README.md"], verification_commands=["check"]), make_assignment("two", "write two", allowed_paths=["README.md"], depends_on=["one"], verification_commands=["check"])]
            apply_topology(state, "worker_serial")
            materialize_workspaces(state, ["one"])
            workspace = Path(state["assignments"][0]["workspace"]["path"])
            (workspace / "README.md").write_text("one\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(workspace), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(workspace), "commit", "-m", "one"], check=True, capture_output=True)
            commit = subprocess.run(["git", "-C", str(workspace), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
            record_worker_result(state, "one", {"status": "succeeded", "summary": "one", "commit": commit, "changed_paths": ["README.md"], "verification": [{"command": "check", "exit_code": 0}]})
            accept_assignment(state, "one")
            materialize_workspaces(state, ["two"])
            self.assertEqual(state["assignments"][1]["workspace"]["path"], state["assignments"][0]["workspace"]["path"])

    def test_disjoint_frozen_assignments_allow_worker_parallel(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("dto", "map", allowed_paths=["src/dto"]), make_assignment("tests", "test", allowed_paths=["tests/dto"])]
        selected = choose_topology(state, "worker_parallel", rationale="DTO is frozen and write ownership is disjoint.")
        self.assertEqual(selected["topology"], "worker_parallel")
        state["assignments"][1]["allowed_paths"] = ["src/dto/contracts"]
        with self.assertRaises(OrchestratorError):
            choose_topology(state, "worker_parallel", rationale="overlap")

    def test_parallel_topology_requires_two_currently_ready_writers(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("owner", "blocked", allowed_paths=["src/a"]), make_assignment("ready", "ready", allowed_paths=["src/b"], depends_on=["owner"])]
        state["assignments"][0]["status"] = "awaiting_owner"
        with self.assertRaises(OrchestratorError):
            choose_topology(state, "worker_parallel", rationale="not currently ready")

    def test_assignment_dependency_cycle_is_rejected_before_dispatch(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("a", "a", allowed_paths=["src/a"], depends_on=["b"]), make_assignment("b", "b", allowed_paths=["src/b"], depends_on=["a"])]
        with self.assertRaises(OrchestratorError):
            validate_snapshot(state)

    def test_upstream_owner_request_blocks_dependent_downstream(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("upstream", "ask", allowed_paths=["src/a"]), make_assignment("downstream", "use", allowed_paths=["src/b"], depends_on=["upstream"])]
        validate_snapshot(state)
        result = record_worker_result(state, "upstream", {"status": "needs_owner", "summary": "need API decision", "owner_request": {"category": "scope_change", "detail": "Choose API shape."}, "changed_paths": []})
        self.assertEqual(result["status"], "needs_owner")
        self.assertEqual(ready_assignment_ids(state), [])

    def test_worker_dispatch_reuses_existing_dispatch_primitive_boundary(self) -> None:
        from scripts.codex_harness_orchestrator import dispatch_worker

        state = snapshot()
        assignment = make_assignment("worker", "bounded fix", allowed_paths=["src"])
        assignment["workspace"] = {"path": str(ROOT.parent / "fixture-worker"), "branch": "codex/fixture-worker", "base_ref": "HEAD"}
        state["assignments"] = [assignment]
        apply_topology(state, "worker_serial")
        seen = []

        def fake_runner(task_id: str, task: dict, timeout: int) -> dict:
            seen.append((task_id, task["worker_execution"]["id"], timeout))
            return {"status": "succeeded", "summary": "worker complete", "changed_paths": [], "verification": [{"command": "check", "exit_code": 0}]}

        result = dispatch_worker(state, "worker", timeout_seconds=17, worker_runner=fake_runner)
        self.assertEqual(result["status"], "succeeded")
        self.assertEqual(seen, [("worker", "worker-lite-luna-max", 17)])

    def test_full_verifier_is_one_shot_and_never_recurses(self) -> None:
        state = snapshot()
        state["assignments"] = [make_assignment("full", "review", assurance_mode="full", kind="verification", allowed_paths=[])]
        calls = []

        def verifier(current: dict, assignment: dict) -> dict:
            calls.append(assignment["assignment_id"])
            self.assertEqual(len(current["assignments"]), 1)
            return {"status": "passed", "independent": True, "summary": "verified", "verification": [{"exit_code": 0}]}

        verdict = run_full_verifier(state, "full", verifier)
        self.assertEqual(verdict["status"], "passed")
        self.assertEqual(calls, ["full"])
        with self.assertRaises(FullVerificationRequired):
            from scripts.codex_harness_orchestrator import accept_assignment

            state["assignments"][0]["result"] = {"status": "succeeded", "changed_paths": [], "verification": [{"exit_code": 0}], "commit": None}
            state["assignments"][0]["status"] = "submitted"
            accept_assignment(state, "full")

    def test_uncertain_cancel_is_blocked_and_quarantined(self) -> None:
        state = snapshot()
        state["orchestrator"]["thread_id"] = "thread-live"
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            state["state_path"] = str(state_path)
            state["controller"]["lock_path"] = str(state_path.with_suffix(".controller.lock"))
            result = cancel_run(state, state_path, "owner requested stop")
        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["quarantine"]["reason"], "cancellation_uncertain")

    def test_active_assignment_cancel_without_stop_proof_is_fail_closed(self) -> None:
        from scripts.codex_harness_orchestrator import apply_orchestrator_turn, ORCHESTRATOR_TURN_SCHEMA_VERSION

        state = snapshot()
        assignment = make_assignment("active", "active", allowed_paths=["src"])
        assignment["status"] = "running"
        assignment["worker"]["status"] = "running"
        state["assignments"] = [assignment]
        with self.assertRaises(OrchestratorError):
            apply_orchestrator_turn(state, {"schema_version": ORCHESTRATOR_TURN_SCHEMA_VERSION, "run_id": state["run_id"], "action": "control", "operation": "cancel", "assignment_id": "active", "summary": "stop"})
        self.assertEqual(state["status"], "blocked")

    def test_cancellation_uncertain_cannot_be_recovered_into_workspace_reuse(self) -> None:
        state = snapshot()
        state["status"] = "blocked"
        state["quarantine"] = {"reason": "cancellation_uncertain"}
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "state.json"
            with self.assertRaises(OrchestratorError):
                recover_run(state, state_path, force=True)

    def test_timeout_reconciles_history_without_interrupt_when_terminal_is_known(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state_path = Path(directory) / "state.json"
            state = new_snapshot(root, "history reconciliation", state_path, run_id="history-reconciliation", artifact_root=Path(directory) / "artifacts")
            calls: list[str] = []
            envelope = json.dumps({"schema_version": "codex-crew.orchestrator-turn.v0", "run_id": state["run_id"], "action": "finish", "summary": "read-only dry run complete"})

            class FakeSession:
                def __init__(self, *_args: object) -> None:
                    pass

                def __enter__(self) -> "FakeSession":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

                def request(self, _request_id: int, method: str, _params: dict, _timeout: int) -> tuple[dict, list[dict]]:
                    calls.append(method)
                    if method == "initialize":
                        return {}, []
                    if method == "thread/start":
                        return {"thread": {"id": "thread-history"}}, []
                    if method == "turn/start":
                        return {"turn": {"id": "turn-history"}}, []
                    if method == "thread/read":
                        return {"turns": [{"id": "turn-history", "status": "completed"}], "items": [{"type": "agentMessage", "threadId": "thread-history", "text": envelope}]}, []
                    raise AssertionError(method)

                def collect_until_turn_complete(self, *_args: object) -> list[dict]:
                    raise TimeoutError("no notification")

            with patch("scripts.codex_harness_orchestrator.JsonRpcSession", FakeSession), patch("scripts.codex_harness_orchestrator.app_server_command", return_value=["fake"]):
                result = run_orchestrator_turn(state, state_path, timeout_seconds=1, resume=False)
            self.assertEqual(result["action"], "finish")
            self.assertEqual(state["status"], "succeeded")
            self.assertNotIn("turn/interrupt", calls)
            self.assertEqual(state["orchestrator"]["turn"]["terminal"]["source"], "thread_history")
            self.assertTrue(state["orchestrator"]["turn"]["terminal"]["valid_envelope"])

    def test_timeout_unknown_is_interrupted_once_and_quarantined_without_worker_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state_path = Path(directory) / "state.json"
            state = new_snapshot(root, "timeout quarantine", state_path, run_id="timeout-quarantine", artifact_root=Path(directory) / "artifacts")
            calls: list[str] = []

            class FakeSession:
                def __init__(self, *_args: object) -> None:
                    pass

                def __enter__(self) -> "FakeSession":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

                def request(self, _request_id: int, method: str, _params: dict, _timeout: int) -> tuple[dict, list[dict]]:
                    calls.append(method)
                    if method == "initialize":
                        return {}, []
                    if method == "thread/start":
                        return {"thread": {"id": "thread-timeout"}}, []
                    if method == "turn/start":
                        return {"turn": {"id": "turn-timeout"}}, []
                    if method in {"thread/read", "turn/interrupt"}:
                        return {}, []
                    raise AssertionError(method)

                def collect_until_turn_complete(self, *_args: object) -> list[dict]:
                    raise TimeoutError("still no terminal")

            with patch("scripts.codex_harness_orchestrator.JsonRpcSession", FakeSession), patch("scripts.codex_harness_orchestrator.app_server_command", return_value=["fake"]):
                with self.assertRaises(OrchestratorError):
                    run_orchestrator_turn(state, state_path, timeout_seconds=1, resume=False)
            self.assertEqual(calls.count("turn/interrupt"), 1)
            self.assertEqual(state["status"], "blocked")
            self.assertEqual(state["quarantine"]["reason"], "turn_completion_unknown")
            self.assertEqual(state["orchestrator"]["turn"]["phase"], "completion_unknown")
            self.assertEqual(state["execution"]["max_active_write_worktrees"], 0)
            self.assertEqual(state["assignments"], [])
            self.assertEqual(state["orchestrator"]["boundary_evidence"]["post_git"]["availability"], "observed")
            persisted = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["quarantine"]["reason"], "turn_completion_unknown")
            with self.assertRaises(OrchestratorError):
                recover_run(state, state_path, force=True)

    def test_timeout_with_terminal_after_interrupt_remains_blocked_and_non_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state_path = Path(directory) / "state.json"
            state = new_snapshot(root, "interrupted terminal", state_path, run_id="interrupted-terminal", artifact_root=Path(directory) / "artifacts")
            calls: list[str] = []

            class FakeSession:
                def __init__(self, *_args: object) -> None:
                    self.collections = 0

                def __enter__(self) -> "FakeSession":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

                def request(self, _request_id: int, method: str, _params: dict, _timeout: int) -> tuple[dict, list[dict]]:
                    calls.append(method)
                    if method == "initialize":
                        return {}, []
                    if method == "thread/start":
                        return {"thread": {"id": "thread-interrupted"}}, []
                    if method == "turn/start":
                        return {"turn": {"id": "turn-interrupted"}}, []
                    if method == "thread/read":
                        return {}, []
                    if method == "turn/interrupt":
                        return {}, [{"method": "turn/completed", "params": {"threadId": "thread-interrupted", "turn": {"status": "interrupted"}}}]
                    raise AssertionError(method)

                def collect_until_turn_complete(self, *_args: object) -> list[dict]:
                    self.collections += 1
                    if self.collections == 1:
                        raise TimeoutError("initial timeout")
                    return []

            with patch("scripts.codex_harness_orchestrator.JsonRpcSession", FakeSession), patch("scripts.codex_harness_orchestrator.app_server_command", return_value=["fake"]):
                with self.assertRaises(OrchestratorError):
                    run_orchestrator_turn(state, state_path, timeout_seconds=1, resume=False)
            self.assertEqual(calls.count("turn/interrupt"), 1)
            self.assertEqual(state["quarantine"]["reason"], "orchestrator_turn_interrupted")
            self.assertEqual(state["orchestrator"]["turn"]["terminal"]["status"], "interrupted")
            self.assertEqual(state["orchestrator"]["turn"]["phase"], "terminal_observed")
            with self.assertRaises(OrchestratorError):
                recover_run(state, state_path, force=True)

    def test_post_turn_git_boundary_is_persisted_when_app_server_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "repo"
            root.mkdir()
            subprocess.run(["git", "-C", str(root), "init"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.email", "crew@example.test"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "config", "user.name", "Crew Test"], check=True, capture_output=True)
            (root / "README.md").write_text("base\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", "README.md"], check=True, capture_output=True)
            subprocess.run(["git", "-C", str(root), "commit", "-m", "base"], check=True, capture_output=True)
            state_path = Path(directory) / "state.json"
            state = new_snapshot(root, "boundary failure", state_path, run_id="boundary-failure", artifact_root=Path(directory) / "artifacts")

            class FakeSession:
                def __init__(self, *_args: object) -> None:
                    pass

                def __enter__(self) -> "FakeSession":
                    return self

                def __exit__(self, *_args: object) -> None:
                    return None

                def request(self, _request_id: int, method: str, _params: dict, _timeout: int) -> tuple[dict, list[dict]]:
                    if method == "initialize":
                        (root / "unexpected.txt").write_text("changed\n", encoding="utf-8")
                        raise RuntimeError("App Server failed")
                    raise AssertionError(method)

            with patch("scripts.codex_harness_orchestrator.JsonRpcSession", FakeSession), patch("scripts.codex_harness_orchestrator.app_server_command", return_value=["fake"]):
                with self.assertRaises(RuntimeError):
                    run_orchestrator_turn(state, state_path, timeout_seconds=1, resume=False)
            self.assertEqual(state["status"], "blocked")
            self.assertEqual(state["quarantine"]["reason"], "orchestrator_write_boundary")
            self.assertEqual(state["orchestrator"]["boundary_evidence"]["pre_git"]["availability"], "observed")
            self.assertEqual(state["orchestrator"]["boundary_evidence"]["post_git"]["availability"], "observed")
            self.assertFalse(state["orchestrator"]["boundary_evidence"]["post_git"]["is_clean"])

    def test_schema_asset_is_parseable_and_versioned(self) -> None:
        schema = json.loads((ROOT / "skills" / "codex-harness" / "assets" / "codex-crew.control.v0.1.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["$id"], "codex-crew.control.v0.1")
        self.assertTrue({"runSnapshot", "orchestratorTurn", "assignment", "workerResult", "acceptance", "turnEvidence", "boundaryEvidence"}.issubset(schema["$defs"]))


if __name__ == "__main__":
    unittest.main()
