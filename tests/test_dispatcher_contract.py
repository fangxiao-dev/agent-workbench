from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "skills" / "dispatcher"
SKILL = DISPATCHER / "SKILL.md"
DELEGATION = DISPATCHER / "references" / "delegation.md"
RESOURCES = DISPATCHER / "references" / "resource-isolation.md"
EVALS = DISPATCHER / "evals" / "evals.json"


def test_dispatcher_is_model_invoked_single_execution_entry() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    frontmatter = skill.split("---", 2)[1]

    assert "description:" in frontmatter
    assert "disable-model-invocation" not in frontmatter
    for marker in ("subagent", "异步", "并行", "worker 返回"):
        assert marker in frontmatter
    assert "subagent-driven-development" not in skill


def test_dispatcher_uses_the_approved_five_step_loop() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    loop = skill.split("## 执行循环", 1)[1].split("完成标准", 1)[0]

    assert sum(line.startswith(tuple(f"{n}." for n in range(1, 6))) for line in loop.splitlines()) == 5
    for marker in (
        "明确交付范围",
        "主动发现可推进工作",
        "形成具体执行合同",
        "核实返回并及时审查",
        "限定阻塞范围并继续安排",
    ):
        assert marker in loop


def test_dispatcher_discloses_only_two_execution_references() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "references/delegation.md" in skill
    assert "references/resource-isolation.md" in skill
    assert DELEGATION.is_file()
    assert RESOURCES.is_file()


def test_delegation_keeps_worker_contract_and_lifecycle() -> None:
    text = DELEGATION.read_text(encoding="utf-8")
    for marker in (
        "investigate",
        "implement",
        "fix",
        "verify",
        "DONE | BLOCKED | INCOMPLETE",
        "EVIDENCE_SUFFICIENT | EVIDENCE_GAP",
        "write ownership",
        "focused verification",
        "cleanup",
        "reviewer 与 implementer 保持独立",
    ):
        assert marker in text


def test_resource_reference_classifies_local_dependencies_and_real_resources() -> None:
    text = RESOURCES.read_text(encoding="utf-8")
    for marker in ("`foundation`", "`acceptance`", "`resource`", "`authorization`"):
        assert marker in text
    for marker in ("DB", "端口", "测试数据", "输出目录", "外部记录", "resource_keys"):
        assert marker in text
    assert "局部 barrier 不升级为全局 blocking" in text
    assert "独立 worktree 只隔离文件" in text


def test_dispatcher_correlates_receipt_return_and_delta_review() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    for marker in (
        "宿主 receipt 明确成功",
        "dispatch_id",
        "return_id",
        "code_delta",
        "consumption_id",
        "待派审事实",
        "待派审欠项",
        "后续扫描继续处理",
    ):
        assert marker in skill


def test_dispatcher_uses_context_signals_instead_of_numeric_fallbacks() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "固定等待时间" in skill
    assert "`INCOMPLETE` 次数" in skill
    assert "15 分钟" not in skill
    assert "30 分钟" not in skill
    assert "连续两次 `INCOMPLETE`" not in skill
    assert "新 Topic 使用 fresh worker" not in skill


def test_dispatcher_evals_cover_consolidated_behavior() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    assert [case["id"] for case in evals] == list(range(1, 16))
    prompts = "\n".join(case["prompt"] for case in evals)
    expected = "\n".join(case["expected_output"] for case in evals)
    for marker in ("同一 Ticket", "agent 槽位", "acceptance edge", "第一次 INCOMPLETE", "review 在途"):
        assert marker in prompts
    for marker in ("待派审事实", "不按次数换人", "不能宣称整体完成"):
        assert marker in expected
    for case in evals:
        assert case["expectations"]
        assert "只读模拟" in case["prompt"]
        assert "禁止实际修改" in case["prompt"]
