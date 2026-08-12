from __future__ import annotations

import importlib.util
import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


DO_REVIEW_DIR = Path(__file__).resolve().parents[1]
ROOT = DO_REVIEW_DIR.parents[1]
REGISTRY_PATH = DO_REVIEW_DIR / "references" / "reviewer-registry.json"
SKILL_PATH = DO_REVIEW_DIR / "SKILL.md"
BRIEFS_PATH = DO_REVIEW_DIR / "references" / "subagent-briefs.md"
TEMPLATES_PATH = DO_REVIEW_DIR / "references" / "output-templates.md"
SCRIPT_PATH = DO_REVIEW_DIR / "scripts" / "verify-reviewer-skills.py"


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("verify_reviewer_skills", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ThreeTrackContractTests(unittest.TestCase):
    def test_registry_defines_the_default_three_leaf_tracks(self) -> None:
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        self.assertEqual(
            registry["default_tracks"],
            [
                {"label": "Track A", "skill": "review-code"},
                {"label": "Track B", "skill": "review-code-by-standards"},
                {"label": "Track C", "skill": "review-code-by-spec"},
            ],
        )
        self.assertEqual(
            registry["reviewers"]["review-code-by-standards"]["canonical_skill_path"],
            "skills/review-code-by-standards/SKILL.md",
        )
        self.assertEqual(
            registry["reviewers"]["review-code-by-spec"]["canonical_skill_path"],
            "skills/review-code-by-spec/SKILL.md",
        )
        for removed_name in ("code-review", "standards-review", "spec-review"):
            self.assertNotIn(removed_name, registry["reviewers"])
        self.assertNotIn("module-review", registry["reviewers"])

    def test_preflight_defaults_are_read_from_registry(self) -> None:
        module = load_preflight_module()
        registry = module.load_registry()
        self.assertEqual(
            module.registry_default_skill_names(registry),
            ["review-code", "review-code-by-standards", "review-code-by-spec"],
        )
        self.assertNotIn(
            '"review-code", "review-code-by-standards", "review-code-by-spec"',
            SCRIPT_PATH.read_text(encoding="utf-8"),
        )

    def test_preflight_rejects_custom_paths_outside_plugin(self) -> None:
        module = load_preflight_module()
        with TemporaryDirectory() as temp_dir:
            outside_skill = Path(temp_dir) / "SKILL.md"
            outside_skill.write_text("---\nname: outside-review\n---\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes plugin root"):
                module.verify_custom_skill(ROOT, f"outside-review={outside_skill}")

    def test_custom_only_preflight_does_not_select_default_tracks(self) -> None:
        module = load_preflight_module()
        self.assertEqual(
            [],
            module.selected_registry_names(
                module.load_registry(), None, ["custom-review=skills/custom-review/SKILL.md"]
            ),
        )

    def test_leaf_prompt_contract_preserves_same_round_isolation(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        briefs = BRIEFS_PATH.read_text(encoding="utf-8")
        for text in (skill, briefs):
            normalized = text.lower()
            self.assertIn("do not invoke do-review", normalized)
            self.assertIn("do not dispatch subagents", normalized)
            self.assertIn("do not re-evaluate reviewer topology or capacity", normalized)
            self.assertIn("other tracks in the current round", normalized)
        self.assertIn("prior round's canonical review context", skill)
        self.assertIn("phases", skill)

    def test_leaf_roles_use_primary_intent_and_parent_handoff(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        briefs = BRIEFS_PATH.read_text(encoding="utf-8")
        standards = (ROOT / "skills" / "review-code-by-standards" / "SKILL.md").read_text(encoding="utf-8")
        code = (ROOT / "skills" / "review-code" / "SKILL.md").read_text(encoding="utf-8")
        self.assertIn("primary review intent", skill)
        self.assertIn("cross-domain candidate", skill)
        self.assertIn("not an exclusive capability boundary", briefs)
        self.assertIn("首要深挖方向", standards)
        self.assertIn("审查偏重", code)

    def test_scope_contract_fails_fast_and_records_spec_discovery(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        self.assertIn("python <do-review-skill-dir>/scripts/review_ledger.py create", skill)
        self.assertNotIn("python scripts/review_ledger.py create", skill)
        self.assertIn("git rev-parse <base>^{commit}", skill)
        self.assertIn("git rev-parse <head>^{commit}", skill)
        self.assertIn("empty diff stops the review before any leaf dispatch", skill)
        self.assertIn("Spec evidence discovery", skill)
        self.assertIn("issue/PR references in the included commit messages", skill)
        self.assertIn("user-provided paths", skill)
        self.assertIn("matching PRD/spec material in `docs/`, `specs/`, or `.scratch/`", skill)
        self.assertIn("Spec source discovery record (searched sources and results):", skill)
        self.assertIn("still dispatch the default `review-code-by-spec` leaf", skill)

    def test_skill_has_fail_closed_default_three_track_verdicts(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        templates = TEMPLATES_PATH.read_text(encoding="utf-8")
        for label in (
            "Track A (review-code)",
            "Track B (review-code-by-standards)",
            "Track C (review-code-by-spec)",
        ):
            self.assertIn(label, skill)
            self.assertIn(label, templates)
        self.assertIn("Aggregate fail-closed", skill)
        self.assertIn("any required `FAIL` makes Overall `FAIL`", skill)

    def test_owner_report_keeps_ledger_internal_without_hiding_track_verdicts(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        templates = TEMPLATES_PATH.read_text(encoding="utf-8")
        self.assertIn("Ledger paths remain internal unless requested", skill)
        self.assertIn("Do not create, request, or infer owner approval", skill)
        self.assertIn("| Audit record | retained internally |", templates)
        self.assertNotIn("Canonical ledger artifact | `<absolute", templates)
        self.assertIn("## Track Verdicts", templates)


if __name__ == "__main__":
    unittest.main()
