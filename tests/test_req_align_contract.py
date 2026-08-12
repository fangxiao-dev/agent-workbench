from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace/plugins/impl-package"
REQ_ALIGN = PLUGIN / "skills/req-align"


def read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_req_align_is_public_router_with_internal_decision_and_spec_subskills() -> None:
    router = read("skills/req-align/SKILL.md")
    assert all(route in router for route in ("full", "decision-only", "spec-only"))
    assert "sub-skills/decision/SUB-SKILL.md" in router
    assert "sub-skills/spec/SUB-SKILL.md" in router

    decision = REQ_ALIGN / "sub-skills/decision/SUB-SKILL.md"
    spec = REQ_ALIGN / "sub-skills/spec/SUB-SKILL.md"
    assert decision.is_file()
    assert spec.is_file()
    assert "Decision Gate" in decision.read_text(encoding="utf-8")
    assert "Spec Design Preflight" in spec.read_text(encoding="utf-8")


def test_spec_template_has_current_design_scope_and_optional_detail_contract() -> None:
    spec = read("skills/req-align/assets/templates/spec.md")
    detail = read("skills/req-align/assets/templates/contract-design.md")

    assert "## Spec 设计范围" in spec
    assert all(
        surface in spec
        for surface in (
            "API operations",
            "Persistence models",
            "Cross-module seams",
            "Public read models",
        )
    )
    assert "Spec Revision：S<n>" not in detail
    assert "没有独立 Status、revision、approval 或 Gate" in detail
    assert "状态（Status）：" not in detail


def test_spec_gate_and_planning_backstop_enforce_contract_completion() -> None:
    gate = read("skills/req-align/references/spec-gate.md")
    planning = read("skills/impl-planning/SKILL.md")

    assert "Spec Design Preflight" in gate
    assert "两个独立实施者" in gate
    assert "proposal 的内容通过判断不能冒充正式阶段迁移" in gate
    assert all(
        dimension in planning
        for dimension in (
            "可观察行为",
            "data identity",
            "permission",
            "concurrency",
            "recovery",
            "public shape",
        )
    )
    assert "不得创建或更新 Plan/state" in planning
    assert "不得在 Plan 中补第二套 DTO/schema" in planning


def test_contract_design_is_subordinate_to_one_spec_lifecycle() -> None:
    lifecycle = read("skills/req-align/references/package-lifecycle.md")
    composition = read("references/impl-package-composition-contract.md")

    for text in (lifecycle, composition):
        assert "contract-design.md" in text
        assert "没有独立 alias、revision、状态" in text
