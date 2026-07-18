from __future__ import annotations

import json
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_dispatch import (
    DISPATCH_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    WORKER_RESULT_SCHEMA_VERSION,
    initialise_state,
    ensure_worktrees,
    record_worker_result,
    ready_task_ids,
    validate_parent_binding,
    validate_manifest,
    run_worker,
)


ROOT = Path(__file__).resolve().parents[1]


def lite_manifest() -> dict:
    return {
        "schema_version": DISPATCH_SCHEMA_VERSION,
        "profile": "lite",
        "worker_profile": "worker-lite-luna-max",
        "repository_root": str(ROOT),
        "parent_run_id": "run-test",
        "parent_thread_id": "parent-thread-test",
        "tasks": [
            {
                "id": "fix-one",
                "prompt": "Fix the known bug without redesign.",
                "worktree": {"path": str(ROOT.parent / "crew-test-fix-one"), "branch": "codex/crew-test-fix-one", "base_ref": "HEAD"},
                "verification_commands": ["python -m unittest"],
            }
        ],
    }


def parallel_manifest() -> dict:
    return {
        "schema_version": "codex-crew.dispatch.v2",
        "execution_topology": "worker_parallel",
        "profile": "full",
        "worker_profile": "worker-full-terra-high",
        "repository_root": str(ROOT),
        "parent_run_id": "run-parallel",
        "parent_thread_id": "parent-thread-parallel",
        "max_active_write_worktrees": 2,
        "parallelism_rationale": "DTO is frozen and implementation/test paths are disjoint.",
        "tasks": [
            {"id": "dto-map", "prompt": "Implement frozen DTO mapping.", "depends_on": [], "write_ownership": {"paths": ["src/mapping"], "external_resources": []}, "worktree": {"path": str(ROOT.parent / "crew-test-dto-map"), "branch": "codex/crew-test-dto-map", "base_ref": "HEAD"}},
            {"id": "dto-tests", "prompt": "Add frozen DTO contract tests.", "depends_on": [], "write_ownership": {"paths": ["tests/dto"], "external_resources": []}, "worktree": {"path": str(ROOT.parent / "crew-test-dto-tests"), "branch": "codex/crew-test-dto-tests", "base_ref": "HEAD"}},
        ],
    }


class CodexCrewDispatchTest(unittest.TestCase):
    def test_lite_manifest_initialises_durable_state(self) -> None:
        manifest = lite_manifest()
        validate_manifest(manifest)
        state = initialise_state(manifest)
        self.assertEqual(state["schema_version"], STATE_SCHEMA_VERSION)
        self.assertEqual(state["status"], "running")
        self.assertEqual(state["tasks"]["fix-one"]["status"], "pending")

    def test_worker_question_routes_to_parent_without_ending_request(self) -> None:
        state = initialise_state(lite_manifest())
        result = {
            "schema_version": WORKER_RESULT_SCHEMA_VERSION,
            "task_id": "fix-one",
            "status": "needs_parent",
            "summary": "Fixture and implementation differ.",
            "verification": [],
            "owner_request": None,
        }
        action = record_worker_result(state, "fix-one", result)
        self.assertEqual(action["action"], "parent_attention")
        self.assertEqual(state["status"], "attention")
        self.assertEqual(state["tasks"]["fix-one"]["result"]["status"], "needs_parent")

    def test_owner_result_is_returned_to_parent_without_becoming_controller_state(self) -> None:
        state = initialise_state(lite_manifest())
        result = {
            "schema_version": WORKER_RESULT_SCHEMA_VERSION,
            "task_id": "fix-one",
            "status": "needs_owner",
            "summary": "External API version must change.",
            "verification": [],
            "owner_request": {"category": "scope_change", "detail": "Use the new public API."},
        }
        action = record_worker_result(state, "fix-one", result)
        self.assertEqual(action["action"], "parent_attention")
        self.assertEqual(state["status"], "attention")

    def test_worker_attention_is_preserved_for_parent(self) -> None:
        manifest = lite_manifest()
        manifest["tasks"].append(
            {
                "id": "fix-two",
                "prompt": "Fix another known bug.",
                "worktree": {"path": str(ROOT.parent / "crew-test-fix-two"), "branch": "codex/crew-test-fix-two", "base_ref": "HEAD"},
            }
        )
        state = initialise_state(manifest)
        record_worker_result(state, "fix-one", {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": "fix-one", "status": "needs_owner", "summary": "scope", "verification": [], "owner_request": {"category": "scope_change", "detail": "scope"}})
        record_worker_result(state, "fix-two", {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": "fix-two", "status": "failed", "summary": "failed", "verification": [], "owner_request": None})
        self.assertEqual(state["status"], "attention")

    def test_manifest_rejects_duplicate_worktree_or_branch_bindings(self) -> None:
        manifest = lite_manifest()
        manifest["tasks"].append({"id": "duplicate-path", "prompt": "Another bounded repair.", "worktree": {"path": manifest["tasks"][0]["worktree"]["path"], "branch": "codex/other", "base_ref": "HEAD"}})
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_manifest_rejects_worker_profile_that_does_not_match_mode_binding(self) -> None:
        manifest = lite_manifest()
        manifest["worker_profile"] = "worker-full-terra-high"
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_frozen_dto_with_disjoint_writes_allows_worker_parallel(self) -> None:
        manifest = parallel_manifest()
        validate_manifest(manifest)
        state = initialise_state(manifest)
        self.assertEqual(state["schema_version"], "codex-crew.state.v2")
        self.assertEqual(ready_task_ids(state), ["dto-map", "dto-tests"])

    def test_worker_parallel_rejects_overlapping_write_ownership(self) -> None:
        manifest = parallel_manifest()
        manifest["tasks"][1]["write_ownership"]["paths"] = ["src/mapping/contracts"]
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_owner_attention_blocks_strictly_dependent_downstream_worktree(self) -> None:
        manifest = parallel_manifest()
        manifest["tasks"][1]["depends_on"] = ["dto-map"]
        state = initialise_state(manifest)
        self.assertEqual(ready_task_ids(state), ["dto-map"])
        record_worker_result(state, "dto-map", {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": "dto-map", "status": "needs_owner", "summary": "Need API approval.", "verification": [], "owner_request": {"category": "scope_change", "detail": "DTO shape changes."}})
        self.assertEqual(state["status"], "attention")
        self.assertEqual(ready_task_ids(state), [])
        with patch("scripts.codex_harness_dispatch.ensure_worktree") as create_worktree:
            self.assertEqual(ensure_worktrees(state), [])
        create_worktree.assert_not_called()

    def test_worker_thread_receives_canonical_model_and_reasoning_effort(self) -> None:
        manifest = lite_manifest()
        state = initialise_state(manifest)
        task = state["tasks"]["fix-one"]

        class FakeSession:
            requests: list[tuple[int, str, dict]] = []

            def __init__(self, *_args, **_kwargs):
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def request(self, request_id, method, params, _timeout):
                self.requests.append((request_id, method, params))
                if method == "thread/start":
                    return {"thread": {"id": "worker-thread"}}, []
                if method == "turn/start":
                    return {"turn": {"id": "worker-turn"}}, []
                return {}, []

            def collect_until_turn_complete(self, _thread_id, _timeout):
                return []

        result = {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": "fix-one", "status": "succeeded", "summary": "ok", "verification": [], "owner_request": None}
        with patch("scripts.codex_harness_dispatch.JsonRpcSession", FakeSession), patch("scripts.codex_harness_dispatch.app_server_command", return_value=["codex"]), patch("scripts.codex_harness_dispatch.initialize_params", return_value={}), patch("scripts.codex_harness_dispatch.parse_worker_result", return_value=result):
            outcome = run_worker("fix-one", task, 30)
        start_request = next(item for item in FakeSession.requests if item[1] == "thread/start")
        self.assertEqual(start_request[2]["model"], "luna")
        self.assertEqual(start_request[2]["config"], {"model_reasoning_effort": "max"})
        self.assertEqual(outcome["worker_execution"]["id"], "worker-lite-luna-max")
        manifest = lite_manifest()
        manifest["tasks"].append({"id": "duplicate-branch", "prompt": "Another bounded repair.", "worktree": {"path": str(ROOT.parent / "crew-test-fix-two"), "branch": manifest["tasks"][0]["worktree"]["branch"], "base_ref": "HEAD"}})
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_parent_binding_rejects_wrong_profile_or_repository(self) -> None:
        manifest = lite_manifest()
        parent = {"schema_version": "codex-crew.parent-state.v1", "run_id": manifest["parent_run_id"], "repository_root": str(ROOT), "parent": {"thread_id": manifest["parent_thread_id"]}, "mode": {"confirmed": "lite"}}
        validate_parent_binding(manifest, parent)
        wrong_profile = dict(manifest, profile="full")
        with self.assertRaises(ValueError):
            validate_parent_binding(wrong_profile, parent)
        wrong_root = dict(manifest, repository_root=str(ROOT.parent))
        with self.assertRaises(ValueError):
            validate_parent_binding(wrong_root, parent)

    def test_invalid_worker_result_cannot_be_recorded(self) -> None:
        state = initialise_state(lite_manifest())
        with self.assertRaises(ValueError):
            record_worker_result(state, "fix-one", {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": "fix-one", "status": "succeeded", "summary": "missing verification"})

    def test_resources_and_evals_are_structured_for_both_skills(self) -> None:
        for skill_name in ("codex-crew-lite", "codex-crew"):
            self.assertTrue((ROOT / "skills" / "codex-harness" / skill_name / "SKILL.md").is_file())
            evaluation = json.loads((ROOT / "skills" / "codex-harness" / skill_name / "evals" / "evals.json").read_text(encoding="utf-8"))
            self.assertEqual(evaluation["skill_name"], skill_name)
            self.assertGreaterEqual(len(evaluation["cases"]), 3)


if __name__ == "__main__":
    unittest.main()
