from __future__ import annotations

import json
import re
import unittest
from pathlib import Path
from typing import Any, Iterator

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
HARNESS_ROOT = ROOT / "skills" / "codex-harness"
SCHEMA_PATH = HARNESS_ROOT / "assets" / "codex-harness-eval.v0.6.schema.json"
ENTRY_SKILL_PATH = HARNESS_ROOT / "SKILL.md"
EVAL_PATHS = (
    HARNESS_ROOT / "codex-crew" / "evals" / "evals.json",
    HARNESS_ROOT / "codex-crew-lite" / "evals" / "evals.json",
)
FIXTURE_PATH = HARNESS_ROOT / "codex-crew" / "evals" / "fixtures" / "production-serial-handoff.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _walk_values(value: Any) -> Iterator[Any]:
    yield value
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_values(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_values(child)


class CodexHarnessEvalAssetsTest(unittest.TestCase):
    def test_schema_is_draft_2020_12_and_eval_documents_validate(self) -> None:
        schema = _read_json(SCHEMA_PATH)
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(schema["$id"].rsplit("/", 1)[-1], SCHEMA_PATH.name)
        Draft202012Validator.check_schema(schema)
        validator = Draft202012Validator(schema)
        for eval_path in EVAL_PATHS:
            document = _read_json(eval_path)
            with self.subTest(eval_path=str(eval_path)):
                validator.validate(document)
                self.assertEqual(document["schema_version"], "codex-harness.eval.v0.6")

    def test_case_ids_are_unique_within_and_across_eval_documents(self) -> None:
        seen: set[str] = set()
        for eval_path in EVAL_PATHS:
            document = _read_json(eval_path)
            ids = [case["id"] for case in document["cases"]]
            self.assertEqual(len(ids), len(set(ids)), f"duplicate case id in {eval_path}")
            duplicate = seen.intersection(ids)
            self.assertFalse(duplicate, f"case ids reused across eval documents: {sorted(duplicate)}")
            seen.update(ids)

    def test_three_assertion_classes_and_evidence_are_complete(self) -> None:
        required_classes = ("hard_invariants", "forbidden_actions", "advisory_quality")
        for eval_path in EVAL_PATHS:
            document = _read_json(eval_path)
            for case in document["cases"]:
                with self.subTest(eval_path=str(eval_path), case=case["id"]):
                    self.assertTrue(case["skill_behaviors"])
                    self.assertTrue(all(isinstance(item, str) and item.strip() for item in case["skill_behaviors"]))
                    self.assertTrue(case["expected_output"])
                    for assertion_class in required_classes:
                        assertions = case[assertion_class]
                        self.assertIsInstance(assertions, list)
                        self.assertTrue(assertions, f"{assertion_class} cannot be empty")
                        self.assertTrue(all(isinstance(item, str) and item.strip() for item in assertions))
                    self.assertTrue(case["evidence"])
                    self.assertTrue(all(item.get("kind") and item.get("description") for item in case["evidence"]))

    def test_worker_count_is_not_a_hard_invariant(self) -> None:
        worker_count = re.compile(r"(?:worker[_ ]count|workers?\s+(?:count|number|数量|数)|workers?\s*(?:>=|>|minimum|at\s+least))", re.IGNORECASE)
        for eval_path in EVAL_PATHS:
            document = _read_json(eval_path)
            for case in document["cases"]:
                for invariant in case["hard_invariants"]:
                    with self.subTest(eval_path=str(eval_path), case=case["id"], invariant=invariant):
                        self.assertIsNone(worker_count.search(invariant), "Worker quantity/topology cannot be a hard acceptance gate")

    def test_fixture_path_exists_and_is_the_sanitized_serial_handoff_case(self) -> None:
        full_document = _read_json(EVAL_PATHS[0])
        fixture_cases = [case for case in full_document["cases"] if "fixture_path" in case]
        self.assertEqual([case["fixture_path"] for case in fixture_cases], ["fixtures/production-serial-handoff.json"])
        resolved = (EVAL_PATHS[0].parent / fixture_cases[0]["fixture_path"]).resolve()
        self.assertEqual(resolved, FIXTURE_PATH.resolve())
        self.assertTrue(resolved.is_file())

    def test_entry_skill_exposes_the_eval_contract(self) -> None:
        skill = ENTRY_SKILL_PATH.read_text(encoding="utf-8")
        for marker in ("hard_invariants", "forbidden_actions", "advisory_quality", "crew.capabilities", "Owner gate", "有效结构化 `finish`", "没有基于时长的自动 interrupt", "人工/operator evidence", "notification 不等于 Owner approval"):
            with self.subTest(marker=marker):
                self.assertIn(marker, skill)

    def test_v0_6_contains_the_capability_host_regression_cases(self) -> None:
        full_document = _read_json(EVAL_PATHS[0])
        cases = {case["id"]: case for case in full_document["cases"]}
        expected = {
            "nonterminal-observation-no-interrupt",
            "broker-correction-continuation",
            "code-handoff-and-owner-gate-separated",
            "parallel-complete-write-ownership",
            "broker-does-not-replan",
            "cohesive-worker-delivery-boundary",
            "same-run-multi-branch-serial",
            "full-verifier-controller-owned",
            "explicit-live-cancel-sidecar",
            "dispatch-defines-without-executing",
            "selected-worker-cohort-only",
            "crew-panorama-and-broker-notification",
            "orchestrator-workspace-decision",
            "local-owner-gate-allows-unrelated-work",
            "explicit-verifier-accept-and-finish",
            "canonical-read-only-worker-cohort",
            "long-run-without-fixed-action-budget",
        }
        self.assertTrue(expected.issubset(cases), "Eval v0.6 must cover every capability-host regression")
        self.assertEqual(cases["nonterminal-observation-no-interrupt"]["terminal_state"], "running")
        self.assertEqual(cases["code-handoff-and-owner-gate-separated"]["terminal_state"], "awaiting_owner")
        self.assertTrue(any("finish" in item.lower() for item in cases["nonterminal-observation-no-interrupt"]["hard_invariants"]))
        self.assertTrue(any("cannot interrupt" in item.lower() for item in cases["nonterminal-observation-no-interrupt"]["hard_invariants"]))
        self.assertTrue(any("explicitly depend" in item.lower() for item in cases["code-handoff-and-owner-gate-separated"]["hard_invariants"]))
        self.assertTrue(any("完整" in item or "Every concurrently writable" in item for item in cases["parallel-complete-write-ownership"]["hard_invariants"]))
        self.assertTrue(any("cannot materialize" in item for item in cases["dispatch-defines-without-executing"]["hard_invariants"]))
        self.assertTrue(any("Unselected ready" in item for item in cases["selected-worker-cohort-only"]["hard_invariants"]))
        self.assertTrue(any("not Owner approval" in item for item in cases["crew-panorama-and-broker-notification"]["hard_invariants"]))
        self.assertTrue(any("one run" in item.lower() or "run identity" in item.lower() for item in cases["orchestrator-workspace-decision"]["forbidden_actions"] + cases["orchestrator-workspace-decision"]["hard_invariants"]))
        self.assertTrue(any("cannot globally suspend" in item for item in cases["local-owner-gate-allows-unrelated-work"]["hard_invariants"]))
        self.assertTrue(any("Do not auto-finish" in item for item in cases["explicit-verifier-accept-and-finish"]["forbidden_actions"]))
        self.assertTrue(any("cannot materialize" in item for item in cases["canonical-read-only-worker-cohort"]["hard_invariants"]))
        self.assertTrue(any("fixed action count" in item.lower() for item in cases["long-run-without-fixed-action-budget"]["hard_invariants"]))

    def test_eval_v0_5_is_replaced_without_a_compatibility_asset(self) -> None:
        self.assertFalse((HARNESS_ROOT / "assets" / "codex-harness-eval.v0.1.schema.json").exists())
        self.assertFalse((HARNESS_ROOT / "assets" / "codex-harness-eval.v0.2.schema.json").exists())
        self.assertFalse((HARNESS_ROOT / "assets" / "codex-harness-eval.v0.3.schema.json").exists())
        self.assertFalse((HARNESS_ROOT / "assets" / "codex-harness-eval.v0.4.schema.json").exists())
        self.assertFalse((HARNESS_ROOT / "assets" / "codex-harness-eval.v0.5.schema.json").exists())
        for eval_path in EVAL_PATHS:
            document = _read_json(eval_path)
            self.assertTrue(document["$schema"].endswith("codex-harness-eval.v0.6.schema.json"))

    def test_fixture_has_no_real_credentials_endpoint_or_external_mutation(self) -> None:
        fixture = _read_json(FIXTURE_PATH)
        self.assertTrue(fixture["sanitized"])
        mutation = fixture["external_mutation"]
        self.assertFalse(mutation["allowed"])
        self.assertFalse(mutation["observed"])
        self.assertEqual(mutation["resources"], [])

        serialized = json.dumps(fixture, ensure_ascii=False)
        forbidden_value_patterns = (
            r"https?://",
            r"(?:postgres|mysql|redis|grpc|ssh)://",
            r"\b(?:api[_-]?key|access[_-]?key|secret|password|token|bearer|private[_-]?key|credential)\b",
        )
        for pattern in forbidden_value_patterns:
            with self.subTest(pattern=pattern):
                self.assertIsNone(re.search(pattern, serialized, re.IGNORECASE))

        forbidden_keys = re.compile(r"(?:endpoint|url|host|api[_-]?key|access[_-]?key|secret|password|token|credential)", re.IGNORECASE)
        for value in _walk_values(fixture):
            if isinstance(value, str):
                self.assertIsNone(forbidden_keys.fullmatch(value), f"fixture contains a sensitive key/value: {value}")
            elif isinstance(value, dict):
                for key in value:
                    self.assertIsNone(forbidden_keys.fullmatch(str(key)), f"fixture contains a sensitive field: {key}")

    def test_fixture_models_verified_serial_workspace_reuse(self) -> None:
        fixture = _read_json(FIXTURE_PATH)
        self.assertEqual(fixture["fixture_version"], "codex-harness.fixture.v0.3")
        self.assertEqual(fixture["problem_lines"]["issue_count"], 5)
        self.assertEqual(len(fixture["problem_lines"]["code_delivery_lines"]), 4)
        self.assertEqual(len(fixture["problem_lines"]["read_only_lines"]), 1)
        self.assertEqual(fixture["run"]["crew_intent"]["shape"], "single_writer")
        self.assertEqual(fixture["run"]["observed_active_write_leases"], 1)
        assignments = fixture["assignments"]
        self.assertEqual(len(assignments), 5)
        deliveries = [assignment for assignment in assignments if assignment["kind"] == "delivery"]
        read_only = [assignment for assignment in assignments if assignment["kind"] == "read_only"]
        self.assertEqual(len(deliveries), 4)
        self.assertEqual(len(read_only), 1)
        self.assertTrue(all(assignment["worker"]["context_fresh"] for assignment in deliveries))
        self.assertEqual([assignment["depends_on"] for assignment in deliveries], [[], ["order-safety"], ["delivery-note-schema"], ["invoice-ready-email"]])
        self.assertEqual({assignment["workspace"]["id"] for assignment in deliveries}, {"serial-workspace"})
        self.assertEqual({assignment["workspace"]["path"] for assignment in deliveries}, {"<fixture-root>/serial-worktree"})
        self.assertEqual([assignment["workspace"]["strategy"] for assignment in deliveries], ["new", "reuse", "reuse", "reuse"])
        self.assertEqual([assignment["workspace"]["handoff_from"] for assignment in deliveries], [None, "order-safety", "delivery-note-schema", "invoice-ready-email"])
        self.assertEqual(len(fixture["handoffs"]), 3)
        self.assertTrue(all(all(handoff["gates"].values()) for handoff in fixture["handoffs"]))
        self.assertIsNone(read_only[0]["workspace"])
        self.assertIsNone(read_only[0]["result"]["commit"])


if __name__ == "__main__":
    unittest.main()
