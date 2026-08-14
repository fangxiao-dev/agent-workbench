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
    for marker in (
        "一个 package 绑定一个主 thread 和一个 standing bookkeeper",
        "impl-package-composition-contract.md",
        "impl-package-current-state.md",
        "req-align",
        "impl-planning",
        "plan-review",
        "to-tickets",
        "dev-with-track",
        "依赖：是",
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
    assert "package 记录通过 bookkeeper 落盘" in callers["dev-with-track"]
