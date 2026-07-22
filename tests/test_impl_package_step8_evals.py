from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
IMPL_ROOT = ROOT / "skills" / "impl-package"
REVIEW_ROOT = ROOT / "skills" / "reviews"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def assert_contains(text: str, needle: str, message: str) -> None:
    if needle not in text:
        raise AssertionError(f"{message} Missing: {needle}")


def assert_not_contains(text: str, needle: str, message: str) -> None:
    if needle in text:
        raise AssertionError(f"{message} Unexpected: {needle}")


def find_eval(eval_file: dict[str, Any], eval_id: int) -> dict[str, Any]:
    matches = [item for item in eval_file["evals"] if int(item["id"]) == eval_id]
    if len(matches) != 1:
        raise AssertionError(f"Expected exactly one eval id {eval_id}")
    return matches[0]


def eval_text(eval_case: dict[str, Any]) -> str:
    return "\n".join(
        (
            eval_case["prompt"],
            eval_case["expected_output"],
            *eval_case.get("expectations", []),
        )
    )


def is_eval_workspace(path: Path) -> bool:
    return any(part.endswith("-workspace") for part in path.relative_to(IMPL_ROOT).parts)


class ImplPackageStep8EvalContractTest(unittest.TestCase):
    def test_impact_scoped_simplification_contract(self) -> None:
        composition = read(IMPL_ROOT / "references" / "impl-package-composition-contract.md")
        for signal in (
            "contract impact",
            "acceptance impact",
            "authority direction",
            "execution impact",
        ):
            assert_contains(composition, signal, "Shared impact routing signal")
        assert_contains(composition, "不是新的 stage、mode、持久 artifact 或必填 JSON schema", "Impact routing must stay lightweight")
        assert_contains(composition, "不表示正文必然失效", "Plan mismatch must not imply full invalidation")

        skill_expectations = {
            IMPL_ROOT / "SKILL.md": "不为了“进流程”调用 `req-align`",
            IMPL_ROOT / "req-align" / "SKILL.md": "## No-contract fast path",
            IMPL_ROOT / "impl-planning" / "SKILL.md": "计划拆解 bundle",
            IMPL_ROOT / "to-tickets" / "SKILL.md": "未受影响 ticket 可作为一个 batch",
            IMPL_ROOT / "create-task-dag" / "SKILL.md": "未受影响节点可以批量确认",
            IMPL_ROOT / "dev-with-track" / "SKILL.md": "bundle approval",
            IMPL_ROOT / "execution-preflight" / "SKILL.md": "plan-decomposition bundle is `approved`",
            IMPL_ROOT / "subagent-driven-development" / "SKILL.md": "委派成本高于收益",
            REVIEW_ROOT / "code-review" / "SKILL.md": "Docs/evidence/config-metadata-only changes use a focused profile",
            REVIEW_ROOT / "standards-review" / "SKILL.md": "Fowler code-smell baseline",
            REVIEW_ROOT / "spec-review" / "SKILL.md": "scope creep",
            REVIEW_ROOT / "safety-review" / "SKILL.md": "### 收缩型变化的 focused path",
            IMPL_ROOT / "verification-before-completion" / "SKILL.md": "不是 terminal completion claim",
        }
        for path, expected in skill_expectations.items():
            assert_contains(read(path), expected, f"Missing distributed simplification rule: {path}")
        assert_contains(read(IMPL_ROOT / "impl-planning" / "SKILL.md"), "不扩展 sidecar schema", "Impl-planning schema boundary")
        assert_contains(read(IMPL_ROOT / "dev-with-track" / "SKILL.md"), "采用 delta-first restore", "Dev restore strategy")
        assert_contains(read(IMPL_ROOT / "execution-preflight" / "SKILL.md"), "Merely citing a plan", "Preflight skip boundary")

    def test_lifecycle_eval_contract(self) -> None:
        eval_paths = {
            "req-align": IMPL_ROOT / "req-align" / "evals" / "evals.json",
            "to-tickets": IMPL_ROOT / "to-tickets" / "evals" / "evals.json",
            "impl-planning": IMPL_ROOT / "impl-planning" / "evals" / "evals.json",
            "create-task-dag": IMPL_ROOT / "create-task-dag" / "evals" / "evals.json",
            "dev-with-track": IMPL_ROOT / "dev-with-track" / "evals" / "evals.json",
            "standards-review": REVIEW_ROOT / "standards-review" / "evals" / "evals.json",
            "spec-review": REVIEW_ROOT / "spec-review" / "evals" / "evals.json",
            "safety-review": REVIEW_ROOT / "safety-review" / "evals" / "evals.json",
        }
        evals: dict[str, dict[str, Any]] = {}
        for skill, path in eval_paths.items():
            parsed = json.loads(read(path))
            if parsed.get("skill_name") != skill or len(parsed.get("evals", [])) < 1:
                raise AssertionError(f"Invalid eval file: {path}")
            evals[skill] = parsed

        req_drift = eval_text(find_eval(evals["req-align"], 4))
        assert_contains(req_drift, "implementation-only", "Req-align drift eval")
        assert_contains(req_drift, "Decision then Spec", "Req-align decision drift eval")
        focused_prd = eval_text(find_eval(evals["req-align"], 8))
        assert_contains(focused_prd, "focused PRD", "New capability must earn a Focused PRD decision")
        assert_contains(focused_prd, "lightweight Decision", "Small correction may stay lightweight")
        assert_contains(focused_prd, "does not create or expand decision.md", "Implementation-only fix must not grow decision")
        assert_contains(focused_prd, "plan.md alone owns", "Implementation planning boundary")

        simple_patch = eval_text(find_eval(evals["impl-planning"], 4))
        assert_contains(simple_patch, "tickets=false, dag=false", "Simple patch composition eval")
        assert_contains(simple_patch, "Planned Verification", "Simple patch planned verification eval")
        assert_contains(simple_patch, "Execution Record", "Simple patch execution record eval")
        assert_contains(simple_patch, "no task checklist", "Simple patch no-checklist eval")
        dag_patch = eval_text(find_eval(evals["impl-planning"], 5))
        assert_contains(dag_patch, "tickets=false, dag=true", "Patch DAG composition eval")
        assert_not_contains(dag_patch, "Patch execution topology", "Retired patch topology eval")

        ticket_draft = eval_text(find_eval(evals["to-tickets"], 1))
        assert_contains(ticket_draft, "current attempt plan", "To-tickets plan composition source")
        assert_contains(ticket_draft, "bundle", "To-tickets joint decomposition bundle")
        ticket_mismatch = eval_text(find_eval(evals["to-tickets"], 5))
        assert_contains(ticket_mismatch, "impl-planning", "To-tickets composition mismatch routing")
        assert_contains(
            ticket_mismatch,
            "without rerunning the Spec gate solely for Composition",
            "To-tickets must not re-gate composition-only changes",
        )
        assert_not_contains(
            ticket_mismatch,
            "Routes to req-align",
            "To-tickets composition-only mismatch must not route to req-align",
        )
        ticket_attempt_boundary = eval_text(find_eval(evals["to-tickets"], 6))
        assert_contains(
            ticket_attempt_boundary,
            "same Attempt ID",
            "To-tickets must reject historical-attempt blockers",
        )

        dag_input = eval_text(find_eval(evals["create-task-dag"], 1))
        assert_contains(dag_input, "current attempt plan", "Task-DAG current-attempt input")
        assert_contains(dag_input, "contributes-to", "Task-DAG AC traceability")
        assert_contains(dag_input, "Draft", "Task-DAG accepts Draft Tickets before joint review")
        dag_persistence = eval_text(find_eval(evals["create-task-dag"], 7))
        assert_contains(
            dag_persistence,
            "requires dag.md or a patch DAG",
            "Task-DAG persistence contract",
        )
        no_dag_route = eval_text(find_eval(evals["create-task-dag"], 14))
        assert_contains(no_dag_route, "tickets=false, dag=false", "Task-DAG no-DAG patch rejection")
        assert_contains(no_dag_route, "no task checklist", "Task-DAG no-checklist patch behavior")
        patch_dag_route = eval_text(find_eval(evals["create-task-dag"], 15))
        assert_contains(patch_dag_route, "tickets=false, dag=true", "Task-DAG patch DAG acceptance")

        blocked_pass = eval_text(find_eval(evals["dev-with-track"], 9))
        assert_contains(blocked_pass, "Supersedes", "Append-only blocked-to-pass gate eval")
        assert_contains(blocked_pass, "old entry", "Append-only old-entry preservation")
        revision_proof = eval_text(find_eval(evals["dev-with-track"], 10))
        assert_contains(revision_proof, "S1", "Gate revision binding source")
        assert_contains(revision_proof, "S2", "Gate revision binding target")
        policy_boundary = eval_text(find_eval(evals["dev-with-track"], 11))
        assert_contains(policy_boundary, "policy", "Verification policy reference eval")
        assert_contains(policy_boundary, "gate", "Gate summary boundary eval")

        spec_template = read(IMPL_ROOT / "req-align" / "assets" / "templates" / "spec.md")
        assert_contains(spec_template, "决策修订（Decision Revision）：D<n>", "Spec must resolve lightweight Decision revision.")
        assert_contains(spec_template, "规格修订（Spec Revision）：S<n>", "Spec revision header.")
        assert_not_contains(spec_template, "Composition:", "Spec must not own Composition.")
        assert_not_contains(
            spec_template,
            "Status: Draft | Spec Gate Passed | Spec Gate Blocked | Superseded",
            "Current spec SoT must not be superseded as a whole file.",
        )
        decision_template = read(IMPL_ROOT / "req-align" / "assets" / "templates" / "decision.md")
        assert_contains(decision_template, "聚焦需求定义 + 当前方案决策与理由", "Decision must own the focused need and current choice.")
        for focused_prd_field in (
            "目标用户 / 使用场景",
            "当前问题与触发条件",
            "期望结果与用户价值",
            "范围",
            "非目标",
            "核心体验或业务流程",
            "成功判断信号",
        ):
            assert_contains(decision_template, focused_prd_field, f"Focused PRD field: {focused_prd_field}")
        assert_contains(decision_template, "只属于 `spec.md`", "Decision/spec boundary.")
        assert_contains(decision_template, "只属于 `plan.md`", "Decision/plan boundary.")
        assert_not_contains(
            decision_template,
            "point-in-time research and decision record",
            "Decision must not retain event-only identity.",
        )

        plan_template = read(IMPL_ROOT / "impl-planning" / "assets" / "templates" / "plan.md")
        assert_contains(plan_template, "## 计划验证", "Plan verification selection.")
        assert_contains(plan_template, "## 执行记录", "Plan execution evidence.")
        assert_not_contains(plan_template, "Executable Checklist", "Plan must not contain task checklist.")

        gate_template = read(
            IMPL_ROOT / "dev-with-track" / "assets" / "templates" / "gate.md"
        )
        assert_contains(gate_template, "# 门禁账本（Gate Ledger）", "Single gate ledger.")
        assert_contains(gate_template, "取代（Supersedes）：", "Gate supersession chain.")
        assert_contains(gate_template, "证据（Evidence）：", "Gate execution-record link.")
        assert_contains(gate_template, "### 长期增量（Durable Deltas）", "Gate durable-delta capture.")
        assert_not_contains(
            gate_template,
            "Verification checklist",
            "Gate must not copy full verification checklist.",
        )
        progress_template = read(
            IMPL_ROOT / "dev-with-track" / "assets" / "templates" / "progress.md"
        )
        assert_contains(
            progress_template,
            "仅当该 Task 实际",
            "Progress must remain conditional on an earned Task event.",
        )
        assert_contains(
            progress_template,
            "不是 Ticket 验收或第二套状态源",
            "Progress must not become a second Ticket state source.",
        )

        dag_skill = read(IMPL_ROOT / "create-task-dag" / "SKILL.md")
        assert_contains(dag_skill, "DAG 必须持久化在当前 attempt", "Impl-Package DAG must be durable.")
        assert_not_contains(dag_skill, "持久化始终可选", "Impl-Package DAG persistence cannot be optional.")
        assert_contains(
            dag_skill,
            "Composition 不一致、plan/spec/AC 缺失或漂移：路由",
            "Composition mismatch route must be explicit.",
        )
        assert_contains(
            dag_skill,
            "`impl-planning` 或 `req-align`",
            "Composition mismatch must route upstream.",
        )

        safety_skill = read(REVIEW_ROOT / "safety-review" / "SKILL.md")
        assert_contains(
            safety_skill,
            "git rev-parse <comparison-ref>^{commit}",
            "Safety base ref must resolve to a commit SHA.",
        )
        assert_contains(
            safety_skill,
            "git diff <base-sha>...<head-sha>",
            "Safety diff must use immutable SHAs.",
        )
        pinned_safety = eval_text(find_eval(evals["safety-review"], 7))
        assert_contains(pinned_safety, "immutable commit SHAs", "Safety eval must pin movable refs.")

        standards_axis = eval_text(find_eval(evals["standards-review"], 2))
        assert_contains(standards_axis, "codebase-design", "Standards-review design baseline")
        assert_contains(standards_axis, "Keeps contract fidelity out", "Standards-review ownership boundary")
        spec_axis = eval_text(find_eval(evals["spec-review"], 2))
        assert_contains(spec_axis, "compatibility window", "Spec-review compatibility contract")
        assert_contains(spec_axis, "state machine", "Spec-review state-machine contract")
        safety_p0 = eval_text(find_eval(evals["safety-review"], 1))
        assert_contains(safety_p0, "idempotency", "Safety-review P0 guard")

        impl_entry = read(IMPL_ROOT / "SKILL.md")
        composition_contract = read(
            IMPL_ROOT / "references" / "impl-package-composition-contract.md"
        )
        system_design = read(IMPL_ROOT / "references" / "impl-package-system-design.md")
        backfill_design = read(
            IMPL_ROOT / "references" / "evergreen-module-spec-and-backfill-design.md"
        )
        dev_with_track = read(IMPL_ROOT / "dev-with-track" / "SKILL.md")
        intro_html = read(IMPL_ROOT / "assets" / "impl-package-intro.html")
        for surface in (
            impl_entry,
            composition_contract,
            system_design,
            backfill_design,
            dev_with_track,
            intro_html,
        ):
            assert_contains(
                surface,
                "不阻塞",
                "Backfill must be explicitly non-blocking across every current guidance surface.",
            )
        assert_contains(
            composition_contract,
            "editorial correction",
            "Exact-blob editorial corrections must rebind without re-gating.",
        )
        assert_contains(
            composition_contract,
            "不得把语义变化伪装为同 alias rebinding",
            "Semantic binding drift must still upgrade revisions.",
        )
        assert_contains(
            system_design,
            "风险驱动的 Grill",
            "System design must not retain automatic Grill routing.",
        )
        assert_not_contains(
            system_design,
            "Spec Gate 前自动质检",
            "System design must retire automatic Grill routing.",
        )
        assert_contains(
            composition_contract,
            "terminal gate entry 写入前必须完成 Stage 7 durable-delta capture",
            "Composition contract must keep capture inside the terminal gate.",
        )
        assert_contains(
            composition_contract,
        "提示本身不构成 audit/apply/verify 授权",
            "Composition contract must separate prompting from authorization.",
        )
        assert_contains(backfill_design, "## 当前稳态用法", "Backfill design must lead with current steady-state usage.")
        assert_contains(
            backfill_design,
            "不替 terminal gate 履行 Stage 7 capture",
            "Backfill cannot replace gate capture.",
        )
        assert_contains(
            dev_with_track,
            "另以非阻塞 follow-up 提示可选 backfill",
            "Execution owner must report optional backfill without reopening the gate.",
        )
        assert_contains(intro_html, "第二部分 · 6 步主流程", "Human intro must present a six-step main flow.")
        assert_contains(
            intro_html,
            "Gate 后可选维护:提示 Backfill,但不自动执行",
            "Human intro must place backfill outside the numbered flow.",
        )
        assert_not_contains(intro_html, "开发 6+1", "Human intro must not retain the obsolete 6+1 model.")
        assert_not_contains(intro_html, "+1 回刷交接", "Human intro must not present backfill as a seventh step.")
        assert_contains(
            backfill_design,
            "### 跨模块 journey 与引用纪律",
            "Evergreen design must define cross-module journey ownership.",
        )
        assert_contains(
            backfill_design,
            "journey anchor → module PRD contribution → primary module spec contract",
            "Cross-module journey must use a non-duplicating anchor chain.",
        )
        assert_contains(
            composition_contract,
            "Composition request",
            "Shorthand must be treated as an owner request, not artifact authorization.",
        )
        assert_contains(
            composition_contract,
            "不得静默改标签",
            "Shorthand conflicts must be surfaced before artifact changes.",
        )
        assert_contains(
            intro_html,
            "可以主动说“按 S / M / L / D 模式做”",
            "Human intro must explain active shorthand selection.",
        )
        assert_contains(
            intro_html,
            "单一验收 · 不切票 · 不排图",
            "Human shorthand cards must lead with decision meaning.",
        )
        assert_not_contains(
            intro_html,
            "tickets=T · dag=F",
            "Human shorthand cards must not lead with canonical booleans.",
        )

        impl_skill_files = sorted(
            path for path in IMPL_ROOT.rglob("SKILL.md") if not is_eval_workspace(path)
        )
        self.assertEqual(10, len(impl_skill_files))
        non_reporting_skills = {
            Path("skills/impl-package/subagent-driven-development/SKILL.md"),
            Path("skills/impl-package/verification-before-completion/SKILL.md"),
        }
        for skill_file in impl_skill_files:
            relative_path = skill_file.relative_to(ROOT)
            if relative_path in non_reporting_skills:
                continue
            assert_contains(
                read(skill_file),
                "talk-to-boss",
                f"Impl-Package skill must directly reuse talk-to-boss: {skill_file}",
            )
        assert_contains(
            impl_entry,
            "canonical handoff",
            "Impl-Package root must keep only its canonical handoff adaptation.",
        )
        assert_not_contains(
            impl_entry,
            "owner-facing-reporting.md",
            "Impl-Package must not duplicate talk-to-boss in a local reporting reference.",
        )

        active_roots = (
            IMPL_ROOT / "req-align",
            IMPL_ROOT / "to-tickets",
            IMPL_ROOT / "impl-planning",
            IMPL_ROOT / "create-task-dag",
            IMPL_ROOT / "dev-with-track",
            REVIEW_ROOT / "standards-review",
            REVIEW_ROOT / "spec-review",
            REVIEW_ROOT / "safety-review",
        )
        for active_root in active_roots:
            for path in active_root.rglob("*"):
                if path.is_file() and "to-issues" in path.read_text(
                    encoding="utf-8", errors="ignore"
                ):
                    raise AssertionError(f"Active Impl-Package skill retains to-issues: {path}")

    def test_module_review_routes_migrate_to_the_standards_spec_pair(self) -> None:
        registry = json.loads(
            read(ROOT / "skills" / "do-review" / "references" / "reviewer-registry.json")
        )
        self.assertEqual(
            [track["skill"] for track in registry["default_tracks"]],
            ["code-review", "standards-review", "spec-review"],
        )
        self.assertNotIn("module-review", registry["reviewers"])
        self.assertFalse(
            (REVIEW_ROOT / "module-review").exists(),
            "active reviews/module-review must be deleted; only the explicit deprecated archive may remain",
        )

        active_surfaces = (
            ROOT / "examples" / "datev-accounting-rules.pre-3.2-upgrade-fixture.toml",
            IMPL_ROOT / "SKILL.md",
            IMPL_ROOT / "dev-with-track" / "SKILL.md",
            IMPL_ROOT / "references" / "impl-package-system-design.md",
            IMPL_ROOT / "verification-before-completion" / "SKILL.md",
            IMPL_ROOT / "assets" / "impl-package-intro.html",
        )
        for surface in active_surfaces:
            text = read(surface)
            assert_not_contains(text, "module-review", f"Active module reviewer reference: {surface}")
            assert_not_contains(text, "reviews/module-review", f"Active module path: {surface}")
            assert_contains(text, "standards-review", f"Standards route missing: {surface}")
            assert_contains(text, "spec-review", f"Spec route missing: {surface}")

        routing = read(IMPL_ROOT / "dev-with-track" / "SKILL.md")
        assert_contains(routing, "`code-review` 是普通实现的默认选择", "Code review must remain the normal implementation default")
        assert_contains(
            routing,
            "涉及 interface、状态机、模块边界、跨模块行为或 seam 时，`standards-review` / `spec-review` 是强信号",
            "Standards and Spec must preserve their risk-driven paired route",
        )
        assert_contains(
            routing,
            "auth、permission、payment、webhook、migration、外部 mutation、数据完整性、并发安全",
            "Safety must keep its independent risk route",
        )

        fixture = read(ROOT / "examples" / "datev-accounting-rules.pre-3.2-upgrade-fixture.toml")
        assert_contains(
            fixture,
            'skills = ["impl-package", "impl-package/dev-with-track", "reviews/code-review", "reviews/standards-review", "reviews/spec-review", "reviews/safety-review"]',
            "Integration fixture must list the migrated reviewer pair",
        )

        harness = read(ROOT / "scripts" / "codex_harness_prepare.py")
        assert_contains(harness, "_default_reviewer_skill_paths", "Harness must read configured default reviewers")
        assert_contains(harness, "_reviewer_skill_paths(\"safety-review\")", "Harness must preserve conditional safety addition")


if __name__ == "__main__":
    unittest.main()
