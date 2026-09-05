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


def test_spec_template_has_current_design_scope_and_required_subordinate_contract() -> None:
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
    assert "Disposition: detailed | not-required" in detail
    assert "not-required" in spec
    assert "Reason:" in detail


def test_spec_gate_and_planning_backstop_enforce_contract_completion() -> None:
    gate = read("skills/req-align/references/spec-gate.md")
    planning = read("skills/impl-planning/SKILL.md")

    assert "Spec Design Preflight" in gate
    assert "两个独立实施者" in gate
    assert "正式阶段迁移以该 bundle 记录为依据" in gate
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
        assert "Disposition: detailed" in text
        assert "Disposition: not-required" in text


def test_touched_spec_requires_contract_design_but_untouched_legacy_is_not_migrated() -> None:
    router = read("skills/req-align/SKILL.md")
    lifecycle = read("skills/req-align/references/package-lifecycle.md")
    subskill = read("skills/req-align/sub-skills/spec/SUB-SKILL.md")

    for text in (lifecycle, subskill):
        assert "未触及的 legacy Spec" in text
    # router 用等价表述承载同一二分：新建/修订当场补齐，legacy 留到下次。
    assert "每个新建或修订的 Spec 都有从属 contract-design" in router
    assert "legacy Spec 在下次 req-align 时补齐" in router
    assert "本次创建或修订 Spec 时补齐从属文件" in subskill
