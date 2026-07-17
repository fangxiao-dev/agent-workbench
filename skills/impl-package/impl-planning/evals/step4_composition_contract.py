from __future__ import annotations

from pathlib import Path
import re


SKILL_ROOT = Path(__file__).resolve().parents[1]
IMPL_ROOT = SKILL_ROOT.parent


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(content: str, needle: str, label: str) -> None:
    if needle not in content:
        raise AssertionError(f"Missing {label}: {needle}")


def assert_not_contains(content: str, needle: str, label: str) -> None:
    if needle in content:
        raise AssertionError(f"Unexpected {label}: {needle}")


def assert_unique_revision_projection(content: str, body: str, label: str) -> None:
    marker = "revision-set"
    expected = (
        f"<!-- impl-package:projection {marker} begin -->\n"
        f"{body}\n"
        f"<!-- impl-package:projection {marker} end -->"
    )
    assert_contains(content, expected, f"{label} revision-set projection")
    if content.count(f"<!-- impl-package:projection {marker} begin -->") != 1:
        raise AssertionError(f"{label} must contain exactly one revision-set begin marker")
    if content.count(f"<!-- impl-package:projection {marker} end -->") != 1:
        raise AssertionError(f"{label} must contain exactly one revision-set end marker")
    outside_marker = re.sub(
        rf"(?ms)<!-- impl-package:projection {marker} begin -->\n.*?<!-- impl-package:projection {marker} end -->",
        "",
        content,
    )
    if re.search(
        r"(?m)^\s*(?:决策修订（Decision Revision）|规格修订（Spec Revision）|计划修订（Plan Revision）|Decision Revision|Spec Revision|Plan Revision)[：:]",
        outside_marker,
    ):
        raise AssertionError(f"{label} duplicates a revision declaration outside its machine-owned projection")


def main() -> None:
    skill = read(SKILL_ROOT / "SKILL.md")
    template = read(SKILL_ROOT / "assets" / "templates" / "plan.md")
    decision_template = read(IMPL_ROOT / "req-align" / "assets" / "templates" / "decision.md")
    spec_template = read(IMPL_ROOT / "req-align" / "assets" / "templates" / "spec.md")
    patching = read(SKILL_ROOT / "patching.md")
    rubric = read(SKILL_ROOT / "rubric.md")
    shared = read(IMPL_ROOT / "references" / "impl-package-composition-contract.md")
    gate_template = read(
        IMPL_ROOT / "dev-with-track" / "assets" / "templates" / "gate.md"
    )
    binding_template = read(
        IMPL_ROOT / "assets" / "templates" / "revision-bindings.json"
    )
    readiness_template = read(
        IMPL_ROOT
        / "dev-with-track"
        / "assets"
        / "templates"
        / "manual-acceptance-readiness.md"
    )
    ticket_template = read(
        IMPL_ROOT / "to-tickets" / "assets" / "templates" / "ticket.md"
    )
    dag_template = read(
        IMPL_ROOT / "dev-with-track" / "assets" / "templates" / "dag.md"
    )
    dev_with_track = read(IMPL_ROOT / "dev-with-track" / "SKILL.md")
    dev_evals = read(IMPL_ROOT / "dev-with-track" / "evals" / "evals.json")
    req_align = read(IMPL_ROOT / "req-align" / "SKILL.md")

    required = (
        (skill, "Attempt ID", "attempt identity"),
        (skill, "Composition 是当前 plan 的事实", "plan-owned composition"),
        (skill, "Planned Verification", "planned verification"),
        (skill, "Execution Record", "execution record"),
        (skill, "不在 plan 保存 task checklist", "no task checklist rule"),
        (skill, "terminal gate verdict 后 plan 冻结", "terminal freeze"),
        (template, "决策修订（Decision Revision）：D<n>", "decision revision"),
        (template, "规格修订（Spec Revision）：S<n>", "spec revision"),
        (template, "计划修订（Plan Revision）：P<n>", "plan revision"),
        (
            template,
            "执行组合（Composition）：tickets=<true|false>, dag=<true|false>",
            "composition declaration",
        ),
        (template, "## 计划验证", "planned verification section"),
        (template, "## 执行记录", "execution record section"),
        (template, "### ER-<n>", "stable execution-record anchor"),
        (template, "## 计划修订历史", "revision history"),
        (patching, "plan 独立声明 P1 与 Composition", "patch-owned composition"),
        (
            patching,
            "不建立 executable task checklist",
            "no-DAG patch checklist prohibition",
        ),
        (patching, "不创建 patch-gate 文件", "single gate ledger"),
        (
            shared,
            "Composition 的唯一事实源是当前 attempt plan",
            "shared composition source",
        ),
        (shared, "Append-only Gate Ledger", "shared gate lifecycle"),
        (shared, "Revision-blob binding", "revision-blob binding section"),
        (
            shared,
            "git rev-parse HEAD:<package-relative-path>",
            "git blob resolution command",
        ),
        (shared, "NEEDS-REVALIDATION", "ticket/DAG plan-revision drift rule"),
        (shared, "Module Knowledge Watermark", "module knowledge watermark mechanism"),
        (shared, "不只 pass", "terminal-entry findings block covers fail/defer"),
        (template, "Module Knowledge Watermark", "plan-side watermark field"),
        (
            template,
            "发布时绑定校验（Binding Validation at Publication）：Pending | Passed",
            "human-readable plan publication conclusion",
        ),
        (
            gate_template,
            "修订集合（Revision set）：D<n> / S<n> / P<n>",
            "human-readable gate revision set",
        ),
        (
            gate_template,
            "绑定校验（Binding validation）：<passed | failed>",
            "human-readable gate binding conclusion",
        ),
        (binding_template, '"current"', "binding registry current selection"),
        (
            binding_template,
            '"purpose": "internal-machine-sidecar"',
            "binding sidecar internal purpose",
        ),
        (binding_template, '"ownerFacing": false', "binding sidecar non-delivery marker"),
        (binding_template, '"blob"', "binding registry blob field"),
        (binding_template, '"mode": "exact-blob"', "exact artifact binding mode"),
        (
            binding_template,
            '"mode": "plan-contract-v1"',
            "plan contract projection mode",
        ),
        (shared, "Integrated, gate open", "derived integration qualifier"),
        (readiness_template, "### 必须", "manual readiness required fields"),
        (readiness_template, "### 可选项（Optional", "manual readiness optional fields"),
        (ticket_template, "Plan Revision", "ticket plan-revision field"),
        (dag_template, "NEEDS-REVALIDATION", "dag plan-revision drift note"),
        (
            dev_with_track,
            "terminal entry（pass/fail/defer",
            "findings block covers all terminal verdicts",
        ),
        (
            dev_with_track,
            "git rev-parse HEAD:<package-relative-path>",
            "restore recomputes artifact blob",
        ),
        (
            dev_with_track,
            "plan-contract-v1",
            "restore permits append-only execution evidence without P drift",
        ),
        (
            dev_with_track,
            "manual-acceptance-readiness.md",
            "lightweight manual readiness handoff",
        ),
        (
            dev_evals,
            "Does not invent a new owner approval gate after lifecycle is already Active",
            "active lifecycle approval eval",
        ),
        (skill, "正文不得要求 owner 打开 JSON", "planning handoff stays Markdown-first"),
        (
            dev_with_track,
            "正文不得要求 owner 打开 JSON",
            "execution handoff stays Markdown-first",
        ),
        (
            req_align,
            "正文不得要求 owner 打开 JSON",
            "alignment handoff stays Markdown-first",
        ),
    )
    for content, needle, label in required:
        assert_contains(content, needle, label)

    assert_unique_revision_projection(
        decision_template,
        "决策修订（Decision Revision）：D<n>",
        "decision template",
    )
    assert_unique_revision_projection(
        spec_template,
        "决策修订（Decision Revision）：D<n>\n规格修订（Spec Revision）：S<n>",
        "spec template",
    )
    assert_unique_revision_projection(
        template,
        "决策修订（Decision Revision）：D<n>\n规格修订（Spec Revision）：S<n>\n计划修订（Plan Revision）：P<n>",
        "plan template",
    )

    for needle in (
        "Patch execution topology",
        "## When tickets=false: Executable Checklist",
        "## When Patch topology=no-DAG: Patch Execution Checklist",
        "## Package Engineering Contract",
    ):
        assert_not_contains(template, needle, "retired plan shape")

    forbidden = (
        (skill, "Composition 由 spec", "spec-owned composition"),
        (patching, "原 package 的 `Composition:`", "inherited patch composition"),
        (template, "Status: Draft | Active | Frozen", "manually maintained plan lifecycle"),
        (template, "(commit <sha>)", "self-referential plan commit binding"),
        (gate_template, "(commit <sha>)", "legacy gate commit binding"),
        (
            template,
            "Revision Bindings: [revision-bindings.json]",
            "owner-facing JSON link in plan",
        ),
        (
            gate_template,
            "- Revision bindings: revision-bindings.json",
            "owner-facing JSON field in gate",
        ),
        (
            gate_template,
            "机器审计元数据：",
            "redundant gate machine metadata",
        ),
    )
    for content, needle, label in forbidden:
        assert_not_contains(content, needle, label)

    assert_contains(rubric, "每次 attempt 独立决定 Composition", "rubric composition preference")
    assert_contains(
        rubric,
        "简单 no-DAG attempt 不建立 task checklist",
        "rubric no-checklist preference",
    )
    assert_contains(
        rubric,
        "gate 只保存 newest-first append-only 判决摘要",
        "rubric gate summary preference",
    )

    print("Step 4 attempt-lifecycle contract checks passed.")


if __name__ == "__main__":
    main()
