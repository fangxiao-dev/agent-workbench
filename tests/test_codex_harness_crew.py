from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_crew import (
    PARENT_ROUTE_SCHEMA_VERSION,
    PARENT_STATE_SCHEMA_VERSION,
    PARENT_STATUS_SCHEMA_VERSION,
    _apply_control,
    confirm_mode,
    continue_parent,
    register_dispatch,
    new_state,
    parse_route,
    parse_status,
    validate_state,
)
from scripts.codex_harness_dispatch import initialise_state, write_json_atomic


ROOT = Path(__file__).resolve().parents[1]


def route_message(run_id: str, mode: str = "lite") -> str:
    return json.dumps({"schema_version": PARENT_ROUTE_SCHEMA_VERSION, "run_id": run_id, "status": "awaiting_mode_confirmation", "recommended_mode": mode, "rationale": "bounded repair", "required_inputs": []})


def status_message(run_id: str, status: str = "running", **fields: object) -> str:
    return json.dumps({"schema_version": PARENT_STATUS_SCHEMA_VERSION, "run_id": run_id, "status": status, "summary": "parent update", **fields})


class CodexHarnessCrewTest(unittest.TestCase):
    def test_route_and_status_are_structured_and_run_bound(self) -> None:
        state = new_state(ROOT, "Fix the issue", ROOT / ".codex" / "harness" / "crew-parent.toml")
        self.assertEqual(state["schema_version"], PARENT_STATE_SCHEMA_VERSION)
        route = parse_route(route_message(state["run_id"]), state["run_id"])
        self.assertEqual(route["recommended_mode"], "lite")
        self.assertIsNone(parse_route(route_message("other"), state["run_id"]))
        status = parse_status(status_message(state["run_id"], "running"), state["run_id"])
        self.assertEqual(status["status"], "running")
        validate_state(state)

    def test_main_confirms_lite_on_same_parent_thread(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "parent.state.json"
            state = new_state(ROOT, "Fix the issue", ROOT / ".codex" / "harness" / "crew-parent.toml", run_id="run-lite")
            state["parent"]["thread_id"] = "parent-thread-1"
            state["mode"] = {"status": "awaiting_confirmation", "proposed": "lite", "confirmed": None, "rationale": "bounded"}
            state["status"] = "awaiting_mode_confirmation"
            with patch("scripts.codex_harness_crew._run_turn", return_value={"thread_id": "parent-thread-1", "turn_id": "turn-2", "message": status_message("run-lite")}):
                result = confirm_mode(state_path, state, "lite", 30)
        self.assertEqual(result["thread_id"], "parent-thread-1")
        self.assertEqual(state["mode"]["confirmed"], "lite")
        self.assertEqual(state["status"], "running")

    def test_owner_request_round_trips_through_same_parent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "parent-owner.state.json"
            state = new_state(ROOT, "Fix the issue", ROOT / ".codex" / "harness" / "crew-parent.toml", run_id="run-owner")
            state["parent"]["thread_id"] = "parent-thread-2"
            state["mode"] = {"status": "confirmed", "proposed": "lite", "confirmed": "lite", "rationale": "bounded"}
            state["status"] = "awaiting_owner"
            with patch("scripts.codex_harness_crew._run_turn", return_value={"thread_id": "parent-thread-2", "turn_id": "turn-3", "message": status_message("run-owner", "completed")}):
                result = continue_parent(state_path, state, "Owner decision: approved the API change.", 30)
        self.assertEqual(result["thread_id"], "parent-thread-2")
        self.assertEqual(state["status"], "completed")
        self.assertTrue(any(event["kind"] == "owner_decision_forwarded" for event in state["events"]))
        self.assertIsNone(_apply_control(state, status_message("other")))

    def test_lite_to_full_requires_proposal_and_loads_policy_before_resume(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "parent-upgrade.state.json"
            state = new_state(ROOT, "Issue expanded", ROOT / ".codex" / "harness" / "crew-parent.toml", run_id="run-upgrade")
            state["parent"]["thread_id"] = "parent-thread-3"
            state["mode"] = {"status": "awaiting_confirmation", "proposed": "full", "confirmed": "lite", "rationale": "scope expanded"}
            state["status"] = "awaiting_mode_confirmation"
            with patch("scripts.codex_harness_crew._load_full_policy", return_value=(None, None)) as load_policy, patch("scripts.codex_harness_crew._run_turn", return_value={"thread_id": "parent-thread-3", "turn_id": "turn-4", "message": status_message("run-upgrade")}):
                result = confirm_mode(state_path, state, "full", 30)
            self.assertEqual(result["thread_id"], "parent-thread-3")
            self.assertEqual(state["mode"]["confirmed"], "full")
            self.assertEqual(state["parent"]["sandbox"], "workspace-write")
            load_policy.assert_called_once()

    def test_continuation_requires_confirmed_mode(self) -> None:
        state = new_state(ROOT, "Fix the issue", ROOT / ".codex" / "harness" / "crew-parent.toml", run_id="run-unconfirmed")
        state["parent"]["thread_id"] = "parent-thread-unconfirmed"
        state["status"] = "failed"
        validate_state(state)
        state["status"] = "running"
        with self.assertRaises(ValueError):
            validate_state(state)

    def test_dispatch_registration_binds_artifact_and_parent_state(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            state_path = Path(directory) / "parent.state.json"
            state = new_state(ROOT, "Fix the issue", ROOT / ".codex" / "harness" / "crew-parent.toml", run_id="run-dispatch")
            state["state_path"] = str(state_path)
            state["parent"]["thread_id"] = "parent-thread-dispatch"
            state["mode"] = {"status": "confirmed", "proposed": "lite", "confirmed": "lite", "rationale": "bounded"}
            state["status"] = "running"
            dispatch = {
                "schema_version": "codex-crew.dispatch.v0",
                "profile": "lite",
                "repository_root": str(ROOT),
                "parent_run_id": "run-dispatch",
                "parent_thread_id": "parent-thread-dispatch",
                "tasks": [{"id": "fix-one", "prompt": "Fix it.", "worktree": {"path": str(ROOT.parent / "crew-test-register"), "branch": "codex/crew-test-register", "base_ref": "HEAD"}}],
            }
            dispatch_path = Path(state["artifact_root"]) / "dispatch.state.json"
            write_json_atomic(dispatch_path, initialise_state(dispatch))
            write_json_atomic(state_path, state)
            reference = register_dispatch(state_path, state, dispatch_path)
            self.assertEqual(reference["profile"], "lite")
            self.assertEqual(state["dispatch_refs"][0]["path"], str(dispatch_path.resolve()))
            validate_state(state)


if __name__ == "__main__":
    unittest.main()
