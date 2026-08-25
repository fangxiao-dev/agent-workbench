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


def test_reviewer_uses_worker_skill_defaults_without_model_pin() -> None:
    reviewer = read_skill("reviewer")

    assert "`finding-closure`" in reviewer
    assert "$grok-worker" in reviewer
    assert "--no-subagents" in reviewer
    assert "worker Skill owns its model and effort defaults" in reviewer
    assert "model `grok-4.5`" not in reviewer
    assert "model `gpt-5.6-sol`, reasoning effort `high`" in reviewer
    assert "model `gpt-5.6-terra`, reasoning effort `high`" in reviewer
    assert "skill definitions, agent protocol or setup, workflow docs" in reviewer
    assert "`P0`, `P1`, `P2`" in reviewer


def test_role_skills_leave_task_prompt_to_the_caller() -> None:
    skill = read_skill(ROLE)
    assert "The caller prompt must supply every task-specific input" in skill
    assert "override" not in skill.lower()
    assert "unless the caller explicitly" not in skill.lower()


def test_global_entry_and_handoff_route_to_unified_delegation_skill() -> None:
    global_instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    handoff = (ROOT / "skills" / "handoff" / "references" / "task-execution.md").read_text(
        encoding="utf-8"
    )

    for text in (global_instructions, handoff):
        assert "impl-package:subagent-driven-development" in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text
    assert "independent read-only review" in global_instructions
    assert "thin `reviewer` contract" in global_instructions
    assert "单独只读 subagent" in handoff
    assert "存在 `reviewer`" in handoff
    assert not (
        ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "investigate-before-implement" / "SKILL.md"
    ).exists()
    assert not (
        ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "dispatch-bounded-task" / "SKILL.md"
    ).exists()
    assert "Dispatcher and SDD are peer guidance" in global_instructions
    assert "`do-review` owns review topology and finding closure" in global_instructions
    assert "The caller supplies the task-specific" not in global_instructions
    assert "不在 handoff 中重复" in handoff
