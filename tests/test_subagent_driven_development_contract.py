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
    for field in ("mode:", "worker:", "schedule:", "review:"):
        assert field in skill
    assert "route" not in skill.lower()
    assert "默认是 `$grok-worker`" in skill
    assert "同一逻辑 worker" in skill
    assert "fresh invocation" in skill
    assert "context compaction" in skill
    assert "Outcome: DONE | BLOCKED | INCOMPLETE" in skill
    assert "review_state: PENDING_REVIEW" in skill
    assert "一次 fresh `@luna-worker` fallback" in skill
    assert "业务 `BLOCKED` 不 fallback" in skill
    assert "skills/call-grok/SKILL.md" in resolver
    assert "不传 model/effort" in resolver


def test_mode_contracts_cover_investigate_implement_fix_and_verify() -> None:
    modes = read(
        "plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/mode-contracts.md"
    )
    for heading in ("## investigate", "## implement", "## fix", "## verify"):
        assert heading in modes
    assert "EVIDENCE_SUFFICIENT | EVIDENCE_GAP" in modes
    assert "finding closure" in modes
    assert "无写副作用" in modes


def test_scheduling_consumers_reference_only_the_unified_entry() -> None:
    callers = (
        read("AGENTS.md"),
        read("plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md"),
        read("plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md"),
        read("plugin-marketplace/plugins/impl-package/skills/execution-preflight/SKILL.md"),
        read("plugin-marketplace/plugins/impl-package/skills/execution-preflight/references/authorization-contract.md"),
        read("skills/handoff/references/task-execution.md"),
        read("skills/handoff-to-new-session/SKILL.md"),
    )
    for text in callers:
        assert "impl-package:subagent-driven-development" in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text


def test_parallel_admission_remains_a_conditional_reference() -> None:
    skill = read("plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md")
    admission = read(
        "plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md"
    )
    assert "Parallel Work Admission" in skill
    assert "ownership" in admission
    assert "共享可变运行资源" in admission
    assert "worker" not in admission.lower() or "不选择 worker" in admission
