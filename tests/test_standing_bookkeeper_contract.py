from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace/plugins/impl-package"
SKILL = PLUGIN / "skills/standing-bookkeeper"
MERGED_SKILL = PLUGIN / "skills/execution-boundaries"


def read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_standing_bookkeeper_entry_and_role_are_complete() -> None:
    entry = MERGED_SKILL / "SKILL.md"
    role = MERGED_SKILL / "references/role.md"
    evals = SKILL / "evals/evals.json"

    assert entry.is_file()
    assert role.is_file()
    assert evals.is_file()
    assert "name: execution-boundaries" in entry.read_text(encoding="utf-8")
    assert "references/role.md" in entry.read_text(encoding="utf-8")

    role_text = role.read_text(encoding="utf-8")
    for marker in (
        "slow path",
        "impl-package-composition-contract.md",
        "impl-package-current-state.md",
        "证据矛盾",
        "部分写入补齐",
        "跨 stage 对账",
        "结构化修复",
        "state.json",
        "回执",
        "focused validation",
    ):
        assert marker in entry.read_text(encoding="utf-8") + role_text

    payload = json.loads(evals.read_text(encoding="utf-8"))
    entries = payload["evals"]
    assert len(entries) == 8
    assert [entry["id"] for entry in entries] == list(range(1, 9))
    assert all(entry["prompt"] and entry["expected_output"] for entry in entries)
    assert all(entry["expectations"] for entry in entries)

    eval_text = json.dumps(entries, ensure_ascii=False)
    for marker in (
        "依赖：否",
        "correction",
        "恢复",
        "state CLI",
        "focused validation",
    ):
        assert marker in eval_text


def test_package_writers_delegate_physical_mutation_without_moving_semantic_ownership() -> None:
    callers = {
        "req-align": read("skills/req-align/SKILL.md"),
        "decision": read("skills/req-align/sub-skills/decision/SUB-SKILL.md"),
        "spec": read("skills/req-align/sub-skills/spec/SUB-SKILL.md"),
        "impl-planning": read("skills/impl-planning/SKILL.md"),
        "ticket-split": read("skills/impl-planning/SKILL.md"),
        "plan-review": read("skills/plan-review/SKILL.md"),
        "dev-with-track": read("skills/dev-with-track/SKILL.md"),
    }

    for name, text in callers.items():
        assert "/impl-package:execution-boundaries" in text

    assert "主 thread 保留 contract 语义、Gate 和最终采信权" in callers["req-align"]
    assert "主 thread 直接写入并验证 Plan/Ticket" in callers["impl-planning"]
    assert "主 thread 直接写入 Ticket 正文" in callers["ticket-split"]
    assert "业务文档由 owning-stage 主 thread 直接更新" in callers["plan-review"]
    assert "slow path" in callers["dev-with-track"]
    assert "记账 subagent 串行执行语义 CLI" in callers["dev-with-track"]
    role = read("skills/execution-boundaries/references/role.md")
    assert "同一 package 保持一个记账 writer" in role
    assert "异步执行" in role and "依赖：是" in role
    assert "不修改业务代码或 Decision/Spec/Plan/Ticket 正文" in role
