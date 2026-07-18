from __future__ import annotations

import json
import unittest
from pathlib import Path

from scripts.codex_harness_dispatch import (
    STATE_SCHEMA_VERSION,
    WORKER_RESULT_SCHEMA_VERSION,
    initialise_state,
    record_worker_result,
    validate_parent_binding,
    validate_manifest,
)


ROOT = Path(__file__).resolve().parents[1]


def lite_manifest() -> dict:
    return {
        "schema_version": "codex-crew.dispatch.v0",
        "profile": "lite",
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
        manifest = lite_manifest()
        manifest["tasks"].append({"id": "duplicate-branch", "prompt": "Another bounded repair.", "worktree": {"path": str(ROOT.parent / "crew-test-fix-two"), "branch": manifest["tasks"][0]["worktree"]["branch"], "base_ref": "HEAD"}})
        with self.assertRaises(ValueError):
            validate_manifest(manifest)

    def test_parent_binding_rejects_wrong_profile_or_repository(self) -> None:
        manifest = lite_manifest()
        parent = {"schema_version": "codex-crew.parent-state.v0", "run_id": manifest["parent_run_id"], "repository_root": str(ROOT), "parent": {"thread_id": manifest["parent_thread_id"]}, "mode": {"confirmed": "lite"}}
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
