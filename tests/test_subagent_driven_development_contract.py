from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_generic_skill_owns_single_axis_scheduling_and_worker_lifecycle() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")

    contract = skill.split("```text", 1)[1].split("```", 1)[0]
    assert "Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED> · route=<route>" in contract
    assert "mode=" not in contract
    assert "default-long" not in skill
    assert "ordinary" not in skill
    assert "reason/blocker:" in contract
    assert "LOCAL 或 BLOCKED" in contract
    assert "resources:" in contract
    assert "reuse:" in contract
    assert "每个委派的 bounded unit 使用 fresh subagent" in skill
    assert "已发生 context compaction 时，从 canonical input 启动 fresh subagent" in skill
    assert "省略 `reuse` 表示使用 fresh subagent" in skill
    assert "Impl-Package 基于批准的 Plan、Ticket 或 DAG" in skill
    assert "独立 review → `reviewer`" in skill
    assert "$reviewer" not in skill
    assert "gpt-" not in skill.lower()
    assert "reasoning" not in skill.lower()


def test_scheduling_consumers_reference_the_owner_without_a_cycle() -> None:
    investigate = read("plugin-marketplace/plugins/impl-package/skills/investigate-before-implement/SKILL.md")
    preflight = read("plugin-marketplace/plugins/impl-package/skills/execution-preflight/SKILL.md")
    authorization = read(
        "plugin-marketplace/plugins/impl-package/skills/execution-preflight/references/authorization-contract.md"
    )
    handoff = read("skills/handoff-to-new-session/SKILL.md")
    bounded_task = read("plugin-marketplace/plugins/impl-package/skills/dispatch-bounded-task/SKILL.md")

    for text in (preflight, authorization, handoff):
        assert "impl-package:subagent-driven-development" in text

    assert "impl-package:subagent-driven-development" not in investigate
    assert "impl-package:subagent-driven-development" not in bounded_task
    assert "references/parallel-work-admission.md" not in investigate
    assert "$dispatching-parallel-agents" not in investigate
    assert "### Subagent modes" not in preflight
    assert "未输出 `reuse:` 时新建 subagent" in bounded_task


def test_explicit_standing_role_refreshes_after_context_compaction() -> None:
    grill = read("plugin-marketplace/plugins/impl-package/skills/grill-me-smartly/SKILL.md")

    assert "Standing Questioner 是显式 lifecycle 例外" in grill
    assert "发生 context compaction 后" in grill
    assert "启动 fresh Questioner" in grill


def test_verbose_read_only_verification_is_delegated_without_overrouting_small_checks() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")

    assert "预计长时间运行或高回显的既定只读测试" in skill
    assert "`SERIAL` verification unit" in skill
    assert "`/impl-package:dispatch-bounded-task`" in skill
    assert "由其选择 Verifier" in skill
    assert "单条、快速且输出有界的原子检查" in skill
    assert "可留在主 session" in skill
    assert "实现动作或有写副作用的命令不属于 Verifier" in skill
