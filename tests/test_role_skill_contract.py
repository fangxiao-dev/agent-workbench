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


def test_dispatcher_selects_reviewer_and_leaf_executes_finding_closure() -> None:
    reviewer = read_skill("reviewer")
    dispatcher = read_skill("dispatcher")

    assert "`finding-closure`" in reviewer
    assert "已经选定的独立只读 reviewer" in reviewer
    assert "直接执行收到的审查任务" in reviewer
    assert "## Default routing" not in reviewer
    assert "start one fresh" not in reviewer
    assert "默认使用 `luna-worker`" in dispatcher
    assert "由调用方选择并启动执行者" in dispatcher
    assert "model `grok-4.5`" not in reviewer
    assert "gpt-5.6-sol" not in reviewer
    assert "gpt-5.6-terra" not in reviewer
    assert "`P0`, `P1`, `P2`" in reviewer


def test_role_skills_leave_task_prompt_to_the_caller() -> None:
    skill = read_skill(ROLE)
    assert "调用方提供本次任务所需的目标" in skill
    assert "override" not in skill.lower()
    assert "unless the caller explicitly" not in skill.lower()


def test_acceptance_routes_recovery_and_evidence_to_role_entry_points() -> None:
    acceptance = read_skill("run-acceptance")
    role_dir = ROOT / "skills" / "run-acceptance" / "references"
    controller = (role_dir / "controller.md").read_text(encoding="utf-8")
    verifier = (role_dir / "verifier.md").read_text(encoding="utf-8")

    assert "## 按动作读取" in acceptance
    for role in (controller, verifier):
        assert "启动、会话续接或上下文压缩后" in role
        assert "[SKILL.md](../SKILL.md)" in role
    assert "本轮用户补充约束" in controller
    assert "已有工具输出可以精确定位时，直接引用" in controller
    assert "**证据配对**" in acceptance
    assert "先投影本次判定所需字段" in acceptance
    assert "原始工具调用定位" in acceptance
    assert "| 旅程／子场景、受验 HEAD |" in verifier


def test_global_entry_and_handoff_route_to_dispatcher() -> None:
    global_instructions = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    handoff = (ROOT / "skills" / "handoff" / "references" / "impl-package.md").read_text(
        encoding="utf-8"
    )

    for text in (global_instructions, handoff):
        assert "$dispatcher" in text
        assert "impl-package:subagent-driven-development" not in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text
    assert "independent read-only review" in global_instructions
    assert "thin `reviewer` contract" in global_instructions
    assert "不在交接中复制调度或审查流程" in handoff
    assert not (
        ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "investigate-before-implement" / "SKILL.md"
    ).exists()
    assert not (
        ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "dispatch-bounded-task" / "SKILL.md"
    ).exists()
    assert "candidate selection" in global_instructions
    assert "`do-review` owns review topology and finding closure" in global_instructions
    assert "The caller supplies the task-specific" not in global_instructions
