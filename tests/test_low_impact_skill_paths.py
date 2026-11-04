from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_skill(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_brainstorming_fast_path_skips_design_artifacts_for_bounded_work() -> None:
    skill = read_skill("skills", "brainstorming", "SKILL.md")
    assert "Trivial / Local / Reversible Fast Path" in skill
    assert "no public-contract, security, data-migration, cross-host, or irreversible effect" in skill
    assert "Do not require alternatives, a design document, a planning artifact, or design approval." in skill


def test_skill_creator_defaults_local_nonsemantic_edits_to_focused_validation() -> None:
    skill = read_skill(
        "skills",
        "write-skill-smartly",
        "sub-skills",
        "skill-creator",
        "SUB-SKILL.md",
    )
    assert "## Validation Scope" in skill
    assert "Default to focused validation for wording edits, rule clarifications, reference fixes, and local non-semantic corrections." in skill
    assert "changing a workflow or output contract" in skill
    assert "do not create a workspace, baseline runs, grading, benchmark, or viewer for this path" in skill
