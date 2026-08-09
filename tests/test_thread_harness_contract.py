from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def text_block_after_heading(text: str, heading: str) -> str:
    section = text.split(heading, 1)[1]
    return re.search(r"```(?:text|json)\n(.*?)\n```", section, re.DOTALL).group(1)


def test_runtime_halt_examples_use_fresh_controller_session() -> None:
    command_source_paths = (
        "skills/thread-harness/goal-prompt.md",
        "skills/thread-harness/references/role-c.md",
        "skills/thread-harness/references/poll-contract.md",
    )
    halt_command = re.compile(
        r"(?:python\s+\S*ledger\.py|ledger\.py)\s+act\s+"
        r"--registry\s+\S+\s+--halt\s+--source-session\s+\S+\s+--reason"
    )

    runtime_root = ROOT / "skills/thread-harness"
    runtime_paths = tuple(
        path for path in runtime_root.rglob("*.md")
        if path.name != "design-notes.md"
    )
    for path in runtime_paths:
        assert "act --halt --reason" not in path.read_text(encoding="utf-8"), path

    for path in command_source_paths:
        text = read(path)
        assert halt_command.search(text), path

    skill = read("skills/thread-harness/SKILL.md")
    schema = read("skills/thread-harness/references/ledger-schema.md")
    assert "--source-session" in skill and "不提供可信调用者鉴权" in skill
    assert "--source-session" in schema and "不是可信鉴权" in schema


def test_standing_authority_has_stable_markers() -> None:
    goal = read("skills/thread-harness/goal-prompt.md")
    role_c = read("skills/thread-harness/references/role-c.md")
    broker = read("skills/thread-harness/sub-skills/owner-thread-broker/SUB-SKILL.md")

    for text in (goal, role_c, broker):
        assert "standing authority" in text.lower()

    assert "- contacting another child with a new instruction;" not in broker
    assert "授权边界未包含的本地文件或 Git mutation" in broker


def test_controller_goal_keeps_only_stable_runtime_contract() -> None:
    goal_doc = read("skills/thread-harness/goal-prompt.md")
    goal = text_block_after_heading(goal_doc, "## 主控 goal")

    assert "registry：<registry 的绝对路径 .json>" in goal
    assert "父包 entry：<绝对路径>" in goal
    assert "standing execution authority" in goal
    assert "远端 mutation：<允许的环境、对象和用途；没有则 N/A>" in goal
    assert "standing authority" in goal
    assert "退出码 2 = MUST_ACT" in goal
    assert "context compaction 时按 session-dispatch.md 处理" in goal

    repeated_runtime_detail = (
        "coordination_id：<id>",
        "stall-check 退出码 0 / 3 / 4 / 6",
        'wake.reason == "inactiveStatus"',
        "Role A catch-up；Role B",
        "seam 缺失是你的待办",
    )
    for detail in repeated_runtime_detail:
        assert detail not in goal


def test_role_b_compaction_is_new_assignment_not_recovery() -> None:
    role_b = read("skills/thread-harness/references/role-b.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    runtime = role_b + dispatch

    assert "Role B 没有持久恢复权威" in role_b
    assert "发生 compaction 后不走 catch-up" in role_b
    assert "新的最小 assignment card" in role_b
    assert "当前动作需要新增权限时" in role_b
    assert "standing authority 内给予明确的一次性授权" in role_b
    assert "### Role A catch-up" in dispatch
    assert "Role B 不用这个模板" in dispatch
    assert "supersedes previous card" not in runtime
    assert "完整 card" not in runtime + read("skills/thread-harness/references/run-procedure.md")

    obsolete_promises = (
        "assignment card 就是你的恢复权威",
        "Role B 是主控写的 assignment card",
        "Role B=下方 card",
        "Role B 是这张卡本身",
        "card 是 Platform 的**唯一**恢复权威",
    )
    for promise in obsolete_promises:
        assert promise not in runtime


def test_role_a_and_b_carry_default_long_into_handoff() -> None:
    role_a = read("skills/thread-harness/references/role-a.md")
    role_b = read("skills/thread-harness/references/role-b.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")

    marker = "子线调度模式：按 `/impl-package:subagent-driven-development`，默认使用 `default-long`。"
    assert marker in role_a
    assert marker in role_b
    assert marker not in dispatch


def test_second_stage_dispatch_is_role_specific_and_minimal() -> None:
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    role_a = text_block_after_heading(dispatch, "#### Role A prompt")
    role_b = text_block_after_heading(dispatch, "#### Role B prompt")
    role_c = text_block_after_heading(dispatch, "### Role C 特有顺序")

    assert len([line for line in role_a.splitlines() if line.strip()]) <= 20
    assert len([line for line in role_b.splitlines() if line.strip()]) <= 20
    assert len([line for line in role_c.splitlines() if line.strip()]) <= 20
    assert "不得超过 20 个非空逻辑行" in dispatch
    assert "Role A 从 package entry 恢复并继续" in dispatch
    assert "current Next Action" in role_a
    assert "state=working" in role_a

    fields = ("- seam / 任务：", "- next action：", "- inputs：", "- done when：")
    role_b_lines = [line for line in role_b.splitlines() if line.strip()]
    assert tuple(line.split("<", 1)[0] for line in role_b_lines if line.startswith("- ")) == fields

    obsolete_fields = (
        "- registry：",
        "- exact inputs：",
        "- already earned：",
        "- still required：",
        "- authorization：",
        "- exclusions：",
    )
    for field in obsolete_fields:
        assert field not in role_a + role_b

    repeated_workflow = (
        "impl-package:investigate-before-implement",
        "impl-package:do-review",
        "impl-package:subagent-driven-development",
        "impl-package:verification-before-completion",
    )
    for marker in repeated_workflow:
        assert marker not in dispatch

    role_c_order = "核对 registry 已指向自己 → `status` → Owner goal → `preflight` → 首轮固定 poll → `sync`"
    assert role_c_order in dispatch
    assert "每个 child 的 node 名 → session_id" not in dispatch
    assert "当前在途的 assignment（谁在造哪个 seam）" not in dispatch
    assert "各 child 不可触碰的 dirty / Owner WIP" not in dispatch


def test_child_h1_and_dispatch_do_not_expose_registry_or_self_routing() -> None:
    skill = read("skills/thread-harness/SKILL.md")
    schema = read("skills/thread-harness/references/ledger-schema.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    broker = read("skills/thread-harness/sub-skills/owner-thread-broker/SUB-SKILL.md")

    h1_skill = re.search(r"```json\n(.*?)\n```", skill, re.DOTALL).group(1)
    h1_schema = text_block_after_heading(schema, "### H1 JSON payload")
    for payload in (h1_skill, h1_schema):
        for routing_field in ('"registry"', '"coordination_id"', '"node"', '"session_id"'):
            assert routing_field not in payload

    role_a = text_block_after_heading(dispatch, "#### Role A prompt")
    role_b = text_block_after_heading(dispatch, "#### Role B prompt")
    for prompt in (role_a, role_b):
        assert "controller=<current_controller_session_id>" in prompt
        assert "registry=" not in prompt
        assert "coordination_id=" not in prompt
        assert "node=" not in prompt
        assert "session=" not in prompt

    assert "controller 持有该 coordination 的绝对 registry JSON 路径" in broker


def test_active_assignment_completion_requires_reassignment() -> None:
    skill = read("skills/thread-harness/SKILL.md")
    role_c = read("skills/thread-harness/references/role-c.md")
    poll = read("skills/thread-harness/references/poll-contract.md")
    schema = read("skills/thread-harness/references/ledger-schema.md")
    broker = read("skills/thread-harness/sub-skills/owner-thread-broker/SUB-SKILL.md")
    ledger = read("skills/thread-harness/scripts/ledger.py")
    selftest = read("skills/thread-harness/scripts/selftest.py")

    assert "H5 active node 无静默终态" in skill
    assert "只有 `active=false` 表示 node 已退出 coordination" in skill
    assert "进入下一轮 poll 前必须三选一" in role_c
    assert "reassignment_required" in poll
    assert "历史 `done` 仅兼容读取" in schema
    assert "ready_for_assignment` 或历史 `done`" in broker
    assert 'REASSIGNMENT_STATES = {"ready_for_assignment", "done"}' in ledger
    assert "legacy done 对 active node 兼容映射为 reassignment signal" in selftest


def test_run_procedure_uses_split_template_sources() -> None:
    procedure = read("skills/thread-harness/references/run-procedure.md")
    design_notes = read("skills/thread-harness/references/design-notes.md")
    normalized = " ".join(procedure.split())

    assert "Owner 要粘贴的启动文本、goal 与 `create_thread` 授权来自 [goal-prompt.md](../goal-prompt.md)" in normalized
    assert "controller 发给 child 的 registration、assignment card、接手与交接文本来自 [session-dispatch.md](session-dispatch.md)" in normalized
    assert "全部可粘贴文本" not in procedure
    assert "如果模型忘了这条，系统会安静地失效" not in procedure
    assert "不是运行规范" in design_notes.split("---", 1)[0]


def test_create_thread_authorization_covers_role_b_replacement() -> None:
    goal = read("skills/thread-harness/goal-prompt.md")

    assert goal.count("Role B 由 controller 创建继任者") == 2


def test_compaction_observer_is_imported_and_runtime_docs_use_it() -> None:
    utility = read("skills/thread-harness/scripts/rollout_compaction.py")
    ledger = read("skills/thread-harness/scripts/ledger.py")
    role_c = read("skills/thread-harness/references/role-c.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    poll = read("skills/thread-harness/references/poll-contract.md")
    schema = read("skills/thread-harness/references/ledger-schema.md")

    assert "from rollout_compaction import" in ledger
    assert "os.walk" not in utility
    assert ".rglob(" not in utility
    assert "compaction_count" in role_c
    assert "compaction_count" in dispatch
    assert "compaction_count: <node>=<n>" in poll
    assert "observer" not in poll
    assert "rollout EOF" not in poll
    assert "context_compacted" not in poll
    assert "compaction_observers" in schema
    assert "poll-contract.md#compaction_count" in role_c
    assert "poll-contract.md#compaction_count" in dispatch
    assert "Role A 不自行估算或查找次数" in dispatch
    assert "先尽快完成手头任务，写好可恢复 checkpoint" in dispatch
    assert "不要领取新的工作" in dispatch

    runtime_root = ROOT / "skills/thread-harness"
    runtime_docs = tuple(
        path for path in runtime_root.rglob("*.md")
        if path.name != "design-notes.md"
    )
    for path in runtime_docs:
        assert "session_age_h" not in path.read_text(encoding="utf-8"), path


def test_runtime_docs_exclude_design_and_test_process_without_losing_stall_rules() -> None:
    skill = read("skills/thread-harness/SKILL.md")
    goal = read("skills/thread-harness/goal-prompt.md")
    role_c = read("skills/thread-harness/references/role-c.md")
    poll = read("skills/thread-harness/references/poll-contract.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    schema = read("skills/thread-harness/references/ledger-schema.md")
    design_notes = read("skills/thread-harness/references/design-notes.md")

    assert "连续 5 轮" in skill
    assert "`3/5` 或 `4/5`" in role_c
    assert "CHECK_HEARTBEAT" in role_c
    assert "默认阈值为 `5/5`" in poll
    assert "从 `3/5` 起" in poll

    assert "## 回归自检" not in poll
    assert "## 已知限制" not in poll
    assert "## 实测记录" not in schema
    assert "实测占比依次为" not in dispatch
    assert "### 复用 `$handoff-to-new-session`，不要重造" not in dispatch

    assert "### 三条准入判据" not in goal
    assert "### 维护边界" in goal
    assert "### 4.6 goal 的准入判据" in design_notes
    assert "动态进展从 registry、ledger 与任务包读取" in design_notes
