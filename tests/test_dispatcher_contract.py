from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "skills" / "dispatcher"
SKILL = DISPATCHER / "SKILL.md"
EVALS = DISPATCHER / "evals" / "evals.json"


def test_queue_keeps_two_states_and_gains_no_task_manager_vocabulary() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "`status` 只有 `planned` 与 `in-progress`" in skill
    for retired_status in ("status=waiting", "status=parked", "status=cancelled", "status=completed"):
        assert retired_status not in skill


def test_in_progress_means_occupied_not_running() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "不承诺 worker 此刻仍在运行" in skill
    # An externally blocked task parks in in-progress rather than lying to get-next-tasks.
    assert "不退回 `planned`" in skill


def test_phase_table_routes_a_blocked_worker_return() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    table = skill.split("## 阶段查询表", 1)[1].split("## CLI 用法", 1)[0]

    assert "BLOCKED" in table
    for branch in ("update-deps --add", "in-progress", "共享依赖"):
        assert branch in table


def test_internal_blocker_returns_original_task_to_planned_with_dependency() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    table = skill.split("## 阶段查询表", 1)[1].split("## CLI 用法", 1)[0]

    assert "planned + depOn" in table
    assert "外部/Owner" in table and "保持 `in-progress`" in table


def test_delete_retires_only_items_with_no_remaining_work() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for marker in ("fully completed", "cancelled", "superseded", "retire", "没有剩余工作"):
        assert marker in skill
    assert "下游已改依赖或退役" in skill
    assert "唯一前置就是这条判断" not in skill


def test_dep_on_admission_is_restricted_to_other_queue_items() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "另一个队列项的产出" in skill
    assert "Acceptance Gate" in skill


def test_queue_item_granularity_is_one_baby_step_inside_topic() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "一个队列项只对应 Topic 内一个合格 baby step" in skill
    assert "结果可二元判定、前置依赖已回答且能独立验证" in skill
    assert "worker 返回后先消费结果，再决定下一步" in skill


def test_evals_are_wellformed_read_only_scenarios() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    assert len(evals) >= 9
    assert [case["id"] for case in evals] == list(range(1, len(evals) + 1))
    for case in evals:
        assert case["expectations"]
        assert "只读模拟" in case["prompt"]
        assert "禁止实际修改" in case["prompt"]
