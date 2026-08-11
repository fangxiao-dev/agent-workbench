from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_handoff_owns_two_stage_delivery_and_default_configuration() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert "`model=gpt-5.6-sol` and `thinking=high`" in skill
    assert "reports anchor PASS and stops" in skill
    assert "`anchor FAIL: source worktree setup mismatch`" in skill
    assert "Only after both the title and anchor PASS are confirmed" in skill
    assert "send the filled second-stage continuation prompt" in skill
    assert "A timeout is not PASS" in skill
    assert "target.environment = { type: \"local\" }" in skill


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


def test_incomplete_creation_or_naming_never_reaches_continuation() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert "If a `clientThreadId` is returned, do not poll it" in skill
    assert "Only after both the title and anchor PASS are confirmed" in skill
    assert "local creation, renaming, anchor PASS, and continuation delivery all succeed" in skill


def test_downstream_protocol_can_supply_stateless_continuation_authority() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")

    assert "stateless child that has no package recovery authority" in skill
    assert "no context entry is treated as recovery authority" in skill
    assert "generic continuation card is replaced by the downstream continuation" in skill
    assert "Role B 无持久恢复权威" in dispatch
    assert "仅作验证锚点" in dispatch
