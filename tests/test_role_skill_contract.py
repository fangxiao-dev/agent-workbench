from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLE = "reviewer"


def read_skill(name: str) -> str:
    return (ROOT / "skills" / name / "SKILL.md").read_text(encoding="utf-8")


def test_role_skills_have_model_visible_frontmatter() -> None:
    skill = read_skill(ROLE)
    assert skill.startswith(f"---\nname: {ROLE}\n")
    assert "description:" in skill.split("---", 2)[1]
    assert "disable-model-invocation" not in skill.split("---", 2)[1]


def test_reviewer_defaults_depend_on_target_class() -> None:
    reviewer = read_skill("reviewer")

    assert "Use a subagent directly" in reviewer
    assert "model `gpt-5.6-sol`, reasoning effort `high`" in reviewer
    assert "model `gpt-5.6-terra`, reasoning effort `high`" in reviewer
    assert "skill definitions, agent protocol or setup, workflow docs" in reviewer
    assert "`P0`, `P1`, `P2`" in reviewer


def test_role_skills_leave_task_prompt_to_the_caller() -> None:
    skill = read_skill(ROLE)
    assert "The caller prompt must supply every task-specific input" in skill
    assert "override" not in skill.lower()
    assert "unless the caller explicitly" not in skill.lower()


def test_global_entry_and_handoff_route_to_current_delegation_skills() -> None:
    global_instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    handoff = (ROOT / "skills" / "handoff" / "references" / "task-execution.md").read_text(
        encoding="utf-8"
    )

    for name in ("subagent-driven-development", "investigate-before-implement"):
        assert f"impl-package:{name}" in global_instructions
        assert f"impl-package:{name}" in handoff
        assert (ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / name / "SKILL.md").is_file()
    assert "dispatch a separate subagent" in global_instructions
    assert "if `reviewer` is available" in global_instructions
    assert "单独只读 subagent" in handoff
    assert "存在 `reviewer`" in handoff
    for removed in ("investigator", "implementer"):
        assert f"skills/{removed}/" not in global_instructions
        assert f"`${removed}`" not in global_instructions
        assert f"`${removed}`" not in handoff
        assert not (ROOT / "skills" / removed / "SKILL.md").exists()
    assert "workflow and role definitions do not supply business prompts" in global_instructions
    assert "不在 handoff 中重复" in handoff
