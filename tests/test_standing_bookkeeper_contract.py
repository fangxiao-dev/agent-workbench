from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace/plugins/impl-package"
SKILL = PLUGIN / "skills/standing-bookkeeper"


def read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_standing_bookkeeper_entry_and_role_are_complete() -> None:
    entry = SKILL / "SKILL.md"
    role = SKILL / "references/role.md"
    evals = SKILL / "evals/evals.json"

    assert entry.is_file()
    assert role.is_file()
    assert evals.is_file()
    assert "name: standing-bookkeeper" in entry.read_text(encoding="utf-8")
    assert "references/role.md" in entry.read_text(encoding="utf-8")

    role_text = role.read_text(encoding="utf-8")
    # 降级为异常 slow path 后的不变量：只在异常场景触发、不写 state.json、
    # 返回结构化修复输入由主 thread 执行。依据见
    # docs/skill-design/impl-package-situation-table-260815/bookkeeper-practicality.md
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
    assert payload["skill_name"] == "standing-bookkeeper"
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
        "to-tickets": read("skills/to-tickets/SKILL.md"),
        "plan-review": read("skills/plan-review/SKILL.md"),
        "dev-with-track": read("skills/dev-with-track/SKILL.md"),
    }

    for name, text in callers.items():
        assert "/impl-package:standing-bookkeeper" in text or name in {"decision", "spec"}

    assert "主 thread 保留 contract 语义、Gate 和最终采信权" in callers["req-align"]
    assert "主 thread 不直接编辑当前 package 的 Plan 或 runtime state" in callers["impl-planning"]
    assert "Ticket 文件的物理写入与运行时 state 更新" in callers["to-tickets"]
    assert "approved package edits are physically applied" in callers["plan-review"]
    # bookkeeper 已降级为异常 slow path：日常结构化写入由主 session 直接调 CLI，
    # bookkeeper 不再写 state.json。依据见
    # docs/skill-design/impl-package-situation-table-260815/bookkeeper-practicality.md
    assert "slow path" in callers["dev-with-track"]
    assert "不成为第二个 state writer" in callers["dev-with-track"]
