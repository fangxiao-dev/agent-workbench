from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_generic_skill_owns_modes_and_routes_behavior() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")

    assert "始终默认 `default-long`" in skill
    assert "任务较聚焦时可以选择 `ordinary`" in skill
    assert "不定义“聚焦”的机械判据" in skill
    assert "impl-package:investigate-before-implement" in skill
    assert "active skill catalog 中存在 `reviewer`" in skill
    assert "$reviewer" not in skill
    assert "gpt-" not in skill.lower()
    assert "reasoning" not in skill.lower()


def test_mode_consumers_reference_the_generic_owner_without_a_cycle() -> None:
    investigate = read("plugin-marketplace/plugins/impl-package/skills/investigate-before-implement/SKILL.md")
    preflight = read("plugin-marketplace/plugins/impl-package/skills/execution-preflight/SKILL.md")
    authorization = read(
        "plugin-marketplace/plugins/impl-package/skills/execution-preflight/references/authorization-contract.md"
    )
    handoff = read("skills/handoff-to-new-session/SKILL.md")
    bounded_task = read("plugin-marketplace/plugins/impl-package/skills/dispatch-bounded-task/SKILL.md")

    for text in (preflight, authorization, handoff, bounded_task):
        assert "impl-package:subagent-driven-development" in text

    assert "impl-package:subagent-driven-development" not in investigate
    assert "active skill catalog 中存在 `call-grok`" in investigate
    assert "$call-grok" not in investigate
    assert "references/parallel-work-admission.md" in investigate
    assert "$dispatching-parallel-agents" not in investigate
    assert "### Subagent modes" not in preflight
    assert "| `default-long`（默认/长任务）" not in preflight
