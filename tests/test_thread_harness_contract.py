from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


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
    broker = read("skills/thread-harness/owner-thread-broker/SKILL.md")

    for text in (goal, role_c, broker):
        assert "standing authority" in text.lower()

    assert "- contacting another child with a new instruction;" not in broker
    assert "授权边界未包含的本地文件或 Git mutation" in broker


def test_role_b_compaction_is_new_assignment_not_recovery() -> None:
    role_b = read("skills/thread-harness/references/role-b.md")
    dispatch = read("skills/thread-harness/references/session-dispatch.md")
    runtime = role_b + dispatch

    assert "Role B 没有持久恢复权威" in role_b
    assert "发生 compaction 后不走 catch-up" in role_b
    assert "### Role A catch-up" in dispatch
    assert "Role B 不用这个模板" in dispatch
    assert "supersedes previous card" not in runtime

    obsolete_promises = (
        "assignment card 就是你的恢复权威",
        "Role B 是主控写的 assignment card",
        "Role B=下方 card",
        "Role B 是这张卡本身",
        "card 是 Platform 的**唯一**恢复权威",
    )
    for promise in obsolete_promises:
        assert promise not in runtime


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
