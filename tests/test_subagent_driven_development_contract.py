from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace" / "plugins" / "impl-package"
SDD = PLUGIN / "skills" / "subagent-driven-development"


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_method_first_skill_owns_topic_dependency_lane_and_lifecycle() -> None:
    skill = (SDD / "SKILL.md").read_text(encoding="utf-8")

    assert len(skill.splitlines()) <= 140
    for marker in (
        "Topic",
        "foundation dependency",
        "acceptance dependency",
        "resource dependency",
        "authorization dependency",
        "work lane",
        "review lane",
        "test lane",
        "investigate",
        "implement",
        "fix",
        "verify",
        "EVIDENCE_SUFFICIENT",
        "EVIDENCE_GAP",
        "DONE",
        "BLOCKED",
        "INCOMPLETE",
        "PENDING_REVIEW",
        "PASSED",
        "look-ahead",
        "主 session",
        "当前 worktree",
        "新隔离 worktree",
        "caller",
    ):
        assert marker in skill

    for retired in (
        "$grok-worker",
        "@luna-worker",
        "worker:",
        "fallback_from",
        "progress-file",
        "mode-contracts",
        "worker-resolver",
        "mode=review",
    ):
        assert retired not in skill


def test_dev_frontloads_the_business_control_loop() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")

    loop = dev.index("## 业务控制循环")
    assert loop < dev.index("## Owner 边界")
    assert loop < dev.index("## Restore")
    assert loop < dev.index("## Ticket 激活 preflight")
    for step in (
        "刷新事实",
        "选择动作",
        "裁决语义",
        "形成 Topic",
        "交给 Dispatcher",
        "执行 bounded worker",
        "消费结果",
    ):
        assert step in dev[loop : dev.index("## Owner 边界")]


def test_sdd_frontloads_caller_selected_worktree_isolation() -> None:
    sdd = (SDD / "SKILL.md").read_text(encoding="utf-8")
    early = sdd[: sdd.index("## Step 1")]

    for marker in ("当前 worktree", "新隔离 worktree", "caller", "文件 ownership"):
        assert marker in early
    assert "DB" in early and "端口" in early


def test_agent_facing_contracts_use_positive_ownership() -> None:
    paths = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        PLUGIN / "skills" / "dev-with-track" / "references" / "control-flow.md",
        PLUGIN / "skills" / "dev-with-track" / "rubric.md",
        SDD / "SKILL.md",
        SDD / "references" / "parallel-work-admission.md",
        SDD / "rubric.md",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    for sediment in (
        "The caller supplies the task-specific",
        "not its downstream route",
        "remain outside SDD",
        "不自行定义主控调度或下游 worker 方法",
        "本 Skill 不复制 worker、provider、batch、lane 或 lifecycle 规则",
        "不选择 provider、不维护主控队列",
        "不选择 executor，也不维护 queue",
        "不要求 worker 手工填固定 envelope 或固定版式",
        "互不产出对方的输入",
        "不建立 worker pool",
        "不拥有动态队列、provider 解析或原生派发教程",
        "不要求固定 envelope 或输出版式",
    ):
        assert sediment not in text

    design = read("docs/skill-design/subagent-driven-development-method-first-redesign-260825.md")
    assert "状态：已实施" in design
    assert "## 10. 非目标" not in design


def test_focused_control_loop_and_worktree_scenarios_are_recorded() -> None:
    dev_evals = json.loads(
        (PLUGIN / "skills" / "dev-with-track" / "evals" / "evals.json").read_text(encoding="utf-8")
    )["evals"]
    sdd_evals = json.loads((SDD / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]

    dev_control = next(case for case in dev_evals if case["id"] == 8)
    file_isolation = next(case for case in sdd_evals if case["id"] == 9)
    runtime_isolation = next(case for case in sdd_evals if case["id"] == 10)

    assert "business control loop first" in dev_control["expectations"]
    assert "file overlap does not force blocked" in file_isolation["expectations"]
    assert "serialize unisolated DB and port" in runtime_isolation["expectations"]


def test_sdd_evals_keep_coherent_work_together_and_replan_thrashing() -> None:
    sdd_evals = json.loads((SDD / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]

    coherent = next(case for case in sdd_evals if case["id"] == 11)
    recovery = next(case for case in sdd_evals if case["id"] == 12)
    thrash = next(case for case in sdd_evals if case["id"] == 13)

    assert "mechanical cleanup stays in step" in coherent["expectations"]
    assert "same worker continues" in recovery["expectations"]
    assert "foundation investigation first" in thrash["expectations"]


def test_sdd_eval_requires_return_point_authorization_before_follow_up() -> None:
    sdd_evals = json.loads((SDD / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]

    stepwise = next(case for case in sdd_evals if "后端事务语义" in case["prompt"])

    assert "主控验收后再授权下一段" in stepwise["expected_output"]
    assert "独立 PostgreSQL/browser 验证单独派发" in stepwise["expected_output"]


def test_dispatcher_and_sdd_are_peer_guidance_for_upstream_and_downstream() -> None:
    dispatcher = read("skills/dispatcher/SKILL.md")
    sdd = (SDD / "SKILL.md").read_text(encoding="utf-8")
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")

    assert "面向上游主控" in dispatcher
    for marker in ("Topic-first", "baby step", "dispatch", "worker return", "idle"):
        assert marker in dispatcher
    assert "下游" in sdd and "bounded worker" in sdd
    assert "$dispatcher" in dev
    assert "/impl-package:subagent-driven-development" in dev
    assert "平级" in dev
    assert "mode / worker / schedule / review" not in dev
    assert "worker=<" not in dev

    control_flow = (PLUGIN / "skills" / "dev-with-track" / "references" / "control-flow.md").read_text(encoding="utf-8")
    runtime = (PLUGIN / "skills" / "dev-with-track" / "references" / "runtime-protocol.md").read_text(encoding="utf-8")
    assert "references/control-flow.md" in dev
    assert "references/runtime-protocol.md" in dev
    assert "$dispatcher" in control_flow and "subagent-driven-development" in control_flow
    assert "state.json" in runtime
    assert "固定 fallback" in runtime


def test_impl_package_active_tree_has_no_task_queue_semantics() -> None:
    active_paths = (
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        PLUGIN / "skills" / "dev-with-track" / "references" / "control-flow.md",
        PLUGIN / "skills" / "dev-with-track" / "references" / "runtime-protocol.md",
        PLUGIN / "skills" / "dev-with-track" / "rubric.md",
        PLUGIN / "skills" / "dev-with-track" / "evals" / "evals.json",
        SDD / "SKILL.md",
        SDD / "references" / "parallel-work-admission.md",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in active_paths)

    for retired in (
        "task-queue.json",
        "get-next-tasks",
        "depOn",
        "queue idle",
        "dynamic queue",
        "动态 queue",
        "queue/dispatch/return/idle",
    ):
        assert retired not in text


def test_retired_provider_and_fixed_output_references_are_removed() -> None:
    assert not (SDD / "references" / "worker-resolver.md").exists()
    assert not (SDD / "references" / "mode-contracts.md").exists()

    active_text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SDD / "SKILL.md",
            SDD / "references" / "parallel-work-admission.md",
            SDD / "references" / "review-gate.md",
            SDD / "evals" / "evals.json",
            SDD / "rubric.md",
        )
    )
    for retired in (
        "$grok-worker",
        "@luna-worker",
        "fresh invocation",
        "fallback_from",
        "Investigation / cause / blast radius",
        "progress-file.md",
    ):
        assert retired not in active_text


def test_method_and_review_owner_are_consistent_across_updated_direct_callers() -> None:
    protocols = json.loads((PLUGIN / "scripts" / "impl_package_runtime" / "protocols.json").read_text(encoding="utf-8"))
    protocol_text = "\n".join(protocols.values())

    assert "fresh fixer" not in protocol_text
    assert "同 Topic work lane" in protocol_text


def test_parallel_admission_classifies_dependency_and_resources() -> None:
    skill = (SDD / "SKILL.md").read_text(encoding="utf-8")
    admission = (SDD / "references" / "parallel-work-admission.md").read_text(encoding="utf-8")

    assert "references/parallel-work-admission.md" in skill
    for marker in ("foundation", "acceptance", "resource", "authorization", "look-ahead", "cleanup owner"):
        assert marker in admission
    assert "readyTickets 已明确" not in admission
    assert "不负责发现候选" not in admission


def test_scheduling_consumers_reference_the_peer_entries() -> None:
    callers = (
        read("AGENTS.md"),
        read("plugin-marketplace/plugins/impl-package/skills/impl-package/SKILL.md"),
        read("plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md"),
        read("skills/handoff/references/task-execution.md"),
        read("skills/handoff-to-new-session/SKILL.md"),
    )
    for text in callers:
        assert "impl-package:subagent-driven-development" in text or "impl-subagent-driven-development" in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text
    assert "$dispatcher" in callers[0]
    assert "$dispatcher" in callers[2]
