from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_handoff_owns_local_creation_and_two_stage_delivery() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert 'nodeRepl.requestMeta["x-codex-turn-metadata"]' in skill
    assert "session configuration unavailable" in skill
    assert "thinking=reasoning_effort" in skill
    assert '{ type: "project", projectId, environment: { type: "local" } }' in skill
    assert "fork_thread" in skill
    assert "clientThreadId" in skill
    assert "只有标题已确认且 child 明确 anchor PASS" in skill
    assert "timeout 不是 PASS" in skill
    assert "每次" in skill and "wait_threads" in skill and "不超过 60 秒" in skill
    assert '::created-thread{threadId="' in skill


def test_prompt_cards_separate_anchor_from_continuation() -> None:
    template = read("skills/handoff-to-new-session/references/handoff-prompt-template.md")
    anchor, continuation = template.split("## Second-stage continuation prompt", maxsplit=1)

    assert "ABSOLUTE_WORKTREE_PATH" in anchor
    assert "FULL_GIT_HEAD" in anchor
    assert "AUTHORITY_AND_ENTRY_POINT" in anchor
    assert "只报告" in anchor and "anchor PASS" in anchor
    assert "不要读取恢复记录或开始工作" in anchor
    assert "ready work" not in anchor
    assert "OPTIONAL_HANDOFF_NOTES_OR_OMIT" not in anchor

    assert "ACTIVE_CHECKPOINT" in continuation
    assert "CURRENT_STATUS_AND_CANONICAL_READY_TICKETS_OR_RECORDED_ACTION" in continuation
    assert "AUTHORIZATION_AND_NAMED_BLOCKERS" in continuation
    assert "## Handoff Notes" in continuation
    assert "OPTIONAL_HANDOFF_NOTES_OR_OMIT" in continuation
    assert "/impl-package:dev-with-track" in continuation
    assert "$dispatcher" in continuation
    assert "/impl-package:subagent-driven-development" in continuation
    assert "这是理解回报，不是执行预演" in continuation
    assert "不等待批准" in continuation


def test_optional_handoff_notes_are_bounded_and_omittable() -> None:
    template = read("skills/handoff-to-new-session/references/handoff-prompt-template.md")
    _, continuation = template.split("## Second-stage continuation prompt", maxsplit=1)

    assert "1–3 条" in continuation
    assert "每条一行" in continuation
    assert "没有时删除整个 `## Handoff Notes` 章节" in continuation
    assert "用户或当前 agent 提供" in continuation
    for excluded in ("plan", "Ticket AC", "调度规则", "测试命令", "凭证", "受控数据"):
        assert excluded in continuation


def test_execution_semantics_are_delegated_not_reimplemented() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    template = read("skills/handoff-to-new-session/references/handoff-prompt-template.md")

    for pointer in (
        "/impl-package:dev-with-track",
        "$dispatcher",
        "/impl-package:subagent-driven-development",
    ):
        assert pointer in skill
        assert pointer in template

    duplicated_execution_terms = (
        "run foundation admission for every ready Ticket",
        "resource-safe current batch",
        "After each Ticket state mutation",
        "Ticket satisfaction is not a session boundary",
        "schema、service/job、generated contracts、PostgreSQL",
    )
    for term in duplicated_execution_terms:
        assert term not in skill
        assert term not in template


def test_ready_tickets_are_complete_but_checkpoint_does_not_own_scheduling() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    template = read("skills/handoff-to-new-session/references/handoff-prompt-template.md")

    assert "完整" in skill and "readyTickets" in skill
    assert "checkpoint 文案不能收窄" in skill
    assert "handoff 只传递 canonical" in skill
    assert "不复述这些流程" in skill
    assert "持续执行 owning workflow" in template
    assert "TKT-03" not in skill
    assert "TKT-05" not in skill
    assert "TKT-03" not in template
    assert "TKT-05" not in template


def test_recoverable_delivery_variance_keeps_progressing_without_masking_real_mismatch() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")

    assert "自动修正 prompt path、Windows 路径格式" in skill
    assert "每轮必须使用新证据并产生进展" in skill
    assert "不重复相同失败动作" in skill
    assert "真实 worktree/HEAD/authority/config/authorization 不匹配" in skill
    assert "重新发送 anchor-only prompt" in skill


def test_multi_ticket_evals_expect_routing_instead_of_copied_execution_rules() -> None:
    payload = json.loads(read("skills/handoff-to-new-session/evals/evals.json"))
    evals = {item["id"]: item for item in payload["evals"]}

    assert "readyTickets=[TKT-03,TKT-05]" in evals[10]["prompt"]
    assert "routes execution to the owning skills" in evals[10]["expected_output"]
    assert "does not restate" in evals[10]["expectations"][1]
    assert "one ready Ticket" in evals[11]["prompt"]
    assert "routes all execution decisions" in evals[11]["expected_output"]
    assert "terminal package" in evals[11]["prompt"]


def test_downstream_protocol_supplies_only_its_delta() -> None:
    skill = read("skills/handoff-to-new-session/SKILL.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")

    assert "downstream protocol 可以提供自己的 validation anchors 与 continuation" in skill
    assert "本 Skill 仍只负责通用创建和交付 gate" in skill
    assert "Role B 无持久恢复权威" in dispatch
    assert "额外只读验证锚点" in dispatch
