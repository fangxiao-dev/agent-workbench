from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TASK_QUEUE = ROOT / "skills" / "task-queue"
SKILL = TASK_QUEUE / "SKILL.md"
EVALS = TASK_QUEUE / "evals" / "evals.json"


def test_task_queue_is_explicit_and_depends_one_way_on_dispatcher() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    dispatcher = (ROOT / "skills" / "dispatcher" / "SKILL.md").read_text(encoding="utf-8")
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")

    assert "$dispatcher" in skill
    assert "../dispatcher/SKILL.md" in skill
    assert "$task-queue" in agents
    for cue in ("task-queue.json", "depOn", "get-next-tasks", "update-*", "delete"):
        assert cue in skill
    assert "task-queue" not in dispatcher
    assert "独立可返回性" not in skill


def test_queue_keeps_two_states_and_gains_no_task_manager_vocabulary() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "`status` 只有 `planned` 与 `in-progress`" in skill
    for retired_status in ("status=waiting", "status=parked", "status=cancelled", "status=completed"):
        assert retired_status not in skill


def test_in_progress_means_occupied_not_running() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "不承诺 worker 此刻仍在运行" in skill
    assert "不退回 `planned`" in skill


def test_phase_table_routes_blocked_and_continuing_worker_returns() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    table = skill.split("## 阶段查询表", 1)[1].split("## CLI 用法", 1)[0]

    for marker in ("BLOCKED", "planned + depOn", "外部/Owner", "保持 `in-progress`", "共享依赖"):
        assert marker in table
    assert "同一 Topic 仍需工作" in table


def test_delete_and_dependency_contract_remain_narrow() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for marker in (
        "fully completed",
        "cancelled",
        "superseded",
        "retire",
        "没有剩余工作",
        "下游已改依赖或退役",
        "另一个队列项的产出",
        "Acceptance Gate",
    ):
        assert marker in skill


def test_task_queue_evals_keep_the_original_queue_scenarios() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    assert [case["id"] for case in evals] == list(range(1, 12))
    for case in evals:
        assert case["expectations"]
        assert "只读模拟" in case["prompt"]
        assert "禁止实际修改" in case["prompt"]
