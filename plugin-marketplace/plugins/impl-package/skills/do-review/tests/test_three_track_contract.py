from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


DO_REVIEW_DIR = Path(__file__).resolve().parents[1]
ROOT = DO_REVIEW_DIR.parents[1]
REGISTRY_PATH = DO_REVIEW_DIR / "references" / "reviewer-registry.json"
SKILL_PATH = DO_REVIEW_DIR / "SKILL.md"
BRIEFS_PATH = DO_REVIEW_DIR / "references" / "subagent-briefs.md"
TEMPLATES_PATH = DO_REVIEW_DIR / "references" / "output-templates.md"
TOPOLOGY_PATH = DO_REVIEW_DIR / "references" / "review-topology.md"
RUBRIC_PATH = DO_REVIEW_DIR / "rubric.md"
SCRIPT_PATH = DO_REVIEW_DIR / "scripts" / "verify-reviewer-skills.py"


def load_preflight_module():
    spec = importlib.util.spec_from_file_location("verify_reviewer_skills", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def markdown_section(text: str, heading: str) -> str:
    match = re.search(rf"(?ms)^## {re.escape(heading)}\s*$\n(.*?)(?=^## |\Z)", text)
    if not match:
        raise AssertionError(f"missing Markdown section: {heading}")
    return match.group(1)


class ThreeTrackContractTests(unittest.TestCase):
    def test_registry_defines_default_three_tracks_and_conditional_safety(self) -> None:
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
            set(registry["reviewers"]),
            {"review-code", "review-code-by-standards", "review-code-by-spec", "safety-review"},
        )
        for name, record in registry["reviewers"].items():
            self.assertEqual(record["canonical_skill_path"], f"skills/{name}/SKILL.md")
        self.assertNotIn("safety-review", [track["skill"] for track in registry["default_tracks"]])

    def test_reviewer_verifier_uses_registry_defaults_and_rejects_escaping_custom_path(self) -> None:
        module = load_preflight_module()
        registry = module.load_registry()
        self.assertEqual(
            module.registry_default_skill_names(registry),
            [track["skill"] for track in registry["default_tracks"]],
        )
        self.assertEqual(
            module.selected_registry_names(
                registry, None, ["custom-review=skills/custom-review/SKILL.md"]
            ),
            [],
        )
        with TemporaryDirectory() as temp_dir:
            outside_skill = Path(temp_dir) / "SKILL.md"
            outside_skill.write_text("---\nname: outside-review\n---\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "escapes plugin root"):
                module.verify_custom_skill(ROOT, f"outside-review={outside_skill}")

    def test_main_skill_is_a_compact_path_with_existing_conditional_references(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        self.assertLessEqual(len(skill.splitlines()), 120)
        references = set(re.findall(r"\]\((references/[^)]+)\)", skill))
        self.assertEqual(
            references,
            {
                "references/reviewer-registry.json",
                "references/review-topology.md",
                "references/subagent-briefs.md",
                "references/output-templates.md",
            },
        )
        for reference in references:
            self.assertTrue((DO_REVIEW_DIR / reference).is_file())
        self.assertNotIn("review_scope_preflight.py", skill)
        self.assertRegex(skill, r"review_ledger\.py create .*--repo-root .*--base .*--head")

    def test_leaf_brief_enforces_same_round_isolation_and_immutable_contract_reads(self) -> None:
        briefs = BRIEFS_PATH.read_text(encoding="utf-8")
        leaf = markdown_section(briefs, "Generic Leaf Reviewer Brief").lower()
        for prohibited in (
            "do not invoke do-review",
            "do not dispatch subagents",
            "do not re-evaluate reviewer topology or capacity",
            "other tracks in the current round",
        ):
            self.assertIn(prohibited, leaf)
        self.assertIn("git show <resolved-head>:<path>", leaf)
        self.assertIn("working tree", leaf)
        self.assertIn("do not recompute its hash", leaf)
        self.assertIn("fresh leaf-worker session", leaf)
        self.assertIn("later round", leaf)

    def test_safety_topology_is_conditional_and_explicit_selection_stays_exact(self) -> None:
        topology = TOPOLOGY_PATH.read_text(encoding="utf-8")
        safety = markdown_section(topology, "Safety admission")
        for boundary in (
            "authentication",
            "authorization",
            "data integrity",
            "concurrency",
            "migration",
            "external side effects",
        ):
            self.assertIn(boundary, safety)
        self.assertRegex(safety, r"(?s)no explicit reviewer list.*append `safety-review`")
        self.assertRegex(safety, r"(?s)explicit selections for full reviews.*exactly as stated")
        self.assertIn("omitted applicable Safety risk", safety)

    def test_finding_closure_is_incremental_but_terminal_final_rechecks_final_head(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        topology = TOPOLOGY_PATH.read_text(encoding="utf-8")
        phases = markdown_section(topology, "Review phase")
        self.assertRegex(phases, r"(?s)`finding-closure`.*one fresh independent `reviewer` leaf.*named findings")
        self.assertRegex(phases, r"(?s)`terminal-final`.*final implementation `HEAD`.*complete applicable topology")
        self.assertIn("cannot stand in for the terminal-final review", phases)
        self.assertRegex(skill, r"(?s)`finding-closure` has one fresh independent `reviewer` invocation.*worker Skill owns its model")
        self.assertIn("$grok-worker --no-subagents", skill)
        self.assertIn("one fresh fallback to the applicable current default reviewer", skill)
        self.assertIn("current host defaults for the caller-supplied target class", skill)

    def test_finding_closure_uses_one_independent_reviewer_without_track_split(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        topology = TOPOLOGY_PATH.read_text(encoding="utf-8")
        briefs = BRIEFS_PATH.read_text(encoding="utf-8")
        closure = markdown_section(topology, "Review phase")
        self.assertIn("one fresh independent `reviewer` leaf", closure)
        self.assertIn("do not split the closure into source, standards, spec, or Safety tracks", closure)
        self.assertIn("one fresh independent reviewer for the whole named-finding set", briefs)
        self.assertIn("finding-closure` has one fresh independent `reviewer` invocation", skill)

    def test_accepted_track_c_finding_gets_one_scoped_source_recheck(self) -> None:
        skill = SKILL_PATH.read_text(encoding="utf-8")
        topology = TOPOLOGY_PATH.read_text(encoding="utf-8")
        briefs = BRIEFS_PATH.read_text(encoding="utf-8")
        templates = TEMPLATES_PATH.read_text(encoding="utf-8")

        self.assertIn("accepts and classifies a finding as Track C / Spec fidelity", skill)
        self.assertIn("regardless of which leaf first surfaced it", skill)
        self.assertIn("blocks the implementation handoff", skill)
        self.assertIn("do not dispatch a second recheck", skill)
        self.assertIn("untouched legacy package is not by itself a contract gap", skill)
        self.assertIn("not a new review phase or lifecycle state", skill)
        self.assertIn("Accepted Track C Source Recheck Brief", briefs)
        self.assertIn("do not inspect the implementation broadly", briefs.lower())
        self.assertIn("absence alone is not a gap", briefs)
        self.assertIn("Design-source recheck:", templates)
        self.assertNotIn("source recheck", markdown_section(topology, "Review phase").lower())

    def test_loop_lifecycle_requires_two_clean_rounds_and_preserves_reactivation(self) -> None:
        topology = TOPOLOGY_PATH.read_text(encoding="utf-8")
        lifecycle = markdown_section(topology, "Loop track lifecycle")
        self.assertIn("first clean round", lifecycle)
        self.assertIn("second consecutive clean round", lifecycle)
        self.assertIn("reactivates a dormant track", lifecycle)
        self.assertRegex(lifecycle, r"(?s)Convergence requires.*no distinct new accepted blocker/follow-up.*every selected track dormant")

    def test_output_structure_preserves_per_track_fail_closed_and_terminal_coverage(self) -> None:
        templates = TEMPLATES_PATH.read_text(encoding="utf-8")
        report = templates.split("## Normal Review Report", 1)[1].split(
            "## Closure Verification Report", 1
        )[0]
        self.assertIn("## Track Verdicts", report)
        self.assertIn("| Track | Verdict | Coverage / note |", report)
        self.assertRegex(
            report,
            r"(?s)custom full-review selection.*selected Track label/skill pairs.*one verdict row per selected reviewer",
        )
        self.assertIn("| Audit record | retained internally |", report)
        self.assertNotIn("Canonical ledger artifact", report)
        self.assertIn("Independent closure reviewer", templates)
        self.assertIn("INCOMPLETE", templates)

    def test_rubric_records_atomic_review_run_without_stale_round_scope(self) -> None:
        rubric = RUBRIC_PATH.read_text(encoding="utf-8")
        self.assertIn("ReviewRun", rubric)
        self.assertIn("Git blob", rubric)
        self.assertNotIn("本轮只调整 Ownership 与拓扑", rubric)


if __name__ == "__main__":
    unittest.main()
