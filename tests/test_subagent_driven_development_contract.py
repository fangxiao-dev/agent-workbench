from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_unified_skill_owns_strategy_and_worker_lifecycle() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")
    resolver = read(
        "plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/worker-resolver.md"
    )

    assert len(skill.splitlines()) <= 180
    # Slim form keeps the mode/review/failure judgment heuristics (no strategy
    # yaml, no host-specific worker names — those moved to providers/presets).
    for marker in (
        "investigate",
        "EVIDENCE_SUFFICIENT",
        "implement",
        "fix",
        "review",
        "fresh invocation",
        "不重新裁决",
        "checkpoint|closure",
        "共享可变运行资源",
        "BLOCKED",
        "fallback",
        "主 session 始终负责",
    ):
        assert marker in skill
    assert "$grok-worker" not in skill
    assert "@luna-worker" not in skill
    assert "```yaml" not in skill
    assert "skills/call-grok/SKILL.md" in resolver
    assert "不传 model/effort" in resolver


def test_mode_contracts_cover_investigate_implement_fix_and_review() -> None:
    modes = read(
        "plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/mode-contracts.md"
    )
    for heading in ("## investigate", "## implement", "## fix", "## review"):
        assert heading in modes
    assert "EVIDENCE_SUFFICIENT | EVIDENCE_GAP" in modes
    assert "finding closure" in modes
    assert "无写副作用" in modes
    assert "reviewer" in modes


def test_scheduling_consumers_reference_only_the_unified_entry() -> None:
    callers = (
        read("AGENTS.md"),
        read("plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md"),
        read("plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md"),
        read("skills/handoff/references/task-execution.md"),
        read("skills/handoff-to-new-session/SKILL.md"),
    )
    for text in callers:
        # Cross-host routing form or the DSH native command form.
        assert "impl-package:subagent-driven-development" in text or "impl-subagent-driven-development" in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text


def test_parallel_admission_remains_a_conditional_reference() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")
    admission = read(
        "plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md"
    )
    # The parallel-work judgment core stays in the slim skill; the file remains
    # as the conditional reference for multiple-ready candidates.
    assert "共享可变运行资源" in skill
    assert "ownership" in admission
    assert "共享可变运行资源" in admission
    assert "worker" not in admission.lower() or "不选择 worker" in admission
