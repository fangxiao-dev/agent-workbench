from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_handoff_owns_staged_delivery_and_current_task_configuration() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert "x-codex-turn-metadata" in skill
    assert 'nodeRepl.requestMeta["x-codex-turn-metadata"]' in skill
    assert "pass its `model` unchanged as `model`" in skill
    assert "its `reasoning_effort` unchanged as `thinking`" in skill
    assert "session configuration unavailable" in skill
    assert "plain prompt text" in skill
    assert "do not wrap either one in `<codex_delegation>`" in skill
    assert "reports anchor PASS and stops" in skill
    assert "`anchor FAIL: source worktree setup mismatch`" in skill
    assert "Only after both the title and anchor PASS are confirmed" in skill
    assert "send the filled second-stage continuation prompt" in skill
    assert "A timeout is not PASS" in skill
    assert '"type": "project"' in skill
    assert '"projectId": "<verified project id from list_projects>"' in skill
    assert '"environment": { "type": "local" }' in skill
    assert 'do not use `target.type = "worktree"`' in skill
    assert "make one `wait_threads` call" in skill
    assert "timeout no greater than 60 seconds" in skill
    assert "at most one corrective message with no acknowledgment wait or re-audit" in skill
    assert "a missing receipt gets one correction and makes delivery incomplete" in skill


def test_anchor_and_continuation_cards_keep_separate_responsibilities() -> None:
    template = read("skills/handoff-to-new-session/references/handoff-prompt-template.md")
    anchor, continuation = template.split("## Second-stage continuation prompt", maxsplit=1)

    assert "AUTHORITY_ANCHOR_BLOCK" in anchor
    assert "OPTIONAL_READ_ONLY_VALIDATION_ANCHORS_OR_N/A" in anchor
    assert "只报告 `anchor PASS`" in anchor
    assert "不要读取恢复记录或开始工作" in anchor
    assert "current attempt / binding" not in anchor
    assert "next action" not in anchor

    assert "current attempt / binding" in continuation
    assert "next action" in continuation
    assert "Send this only after the title and first-stage `anchor PASS` are confirmed" in continuation
    assert "目标与 next actions" in continuation
    assert "skill/方法及用途" in continuation
    assert "应完成后汇报、因具名 blocker 停止，还是按记录移交" in continuation
    assert "不是执行预演" in continuation
    assert "不等待批准。发出后立即" in continuation
    assert "mode=[MODE] / worker=[WORKER] / schedule=[SCHEDULE] / review=[REVIEW]" in continuation
    assert "SCHEDULING_DECISION_OR_N/A" not in continuation


def test_continuation_carries_current_worker_strategy_not_legacy_mode_only() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    assert "recorded strategy" in skill
    assert "mode / worker / schedule / review" in skill
    assert "recorded subagent mode in one line" not in skill
    assert "investigate-before-implement" not in skill
    assert "dispatch-bounded-task" not in skill
    assert "route=" not in skill


def test_incomplete_creation_or_naming_never_reaches_continuation() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert "If a `clientThreadId` is returned, do not poll it" in skill
    assert "Only after both the title and anchor PASS are confirmed" in skill
    assert "understanding audit has passed or issued its single correction" in skill


def test_downstream_protocol_can_supply_stateless_continuation_authority() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")

    assert "stateless child that has no package recovery authority" in skill
    assert "no context entry is treated as recovery authority" in skill
    assert "generic continuation card is replaced by the downstream continuation" in skill
    assert "The template's understanding receipt still applies" in skill
    assert "Role B 无持久恢复权威" in dispatch
    assert "额外只读验证锚点" in dispatch
