from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DISPATCHER = ROOT / "skills" / "dispatcher"
SKILL = DISPATCHER / "SKILL.md"
EVALS = DISPATCHER / "evals" / "evals.json"


def test_dispatcher_is_a_lightweight_upstream_scheduler() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    for marker in (
        "面向上游主控",
        "Baby step 派发门槛",
        "不可约分检查",
        "当前批次",
        "fan out",
        "receipt",
        "worker return",
        "Topic 生命周期",
        "idle",
    ):
        assert marker in skill
    for queue_marker in (
        "task-queue.json",
        "depOn",
        "get-next-tasks",
        "阶段查询表",
        "CLI 用法",
        "`planned`",
        "`in-progress`",
    ):
        assert queue_marker not in skill


def test_dispatcher_confirms_receipt_before_consuming_worker_return() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "宿主 receipt" in skill
    assert "先消费" in skill and "worker return" in skill
    assert "同一 Topic" in skill and "新 Topic" in skill
    assert "fresh worker" in skill


def test_breadth_gate_splits_reducible_work_surfaces() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    gate = skill.split("## Baby step 派发门槛", 1)[1].split("## 调度循环", 1)[0]

    for marker in (
        "不可约分检查",
        "可观察子结果",
        "独立改变",
        "停止",
        "重新排序",
        "独立可消费结果",
    ):
        assert marker in gate
    assert "继续切分" in gate


def test_breadth_gate_does_not_use_search_scope_or_file_count_as_a_limit() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    gate = skill.split("## Baby step 派发门槛", 1)[1].split("## 调度循环", 1)[0]

    assert "检索范围宽" in gate
    assert "多个紧密相关文件" in gate and "跨文件" in gate
    assert "文件数量" in gate
    assert "没有任何一部分能先独立改变、停止或重新排序后续调度" in gate


def test_dispatcher_evals_cover_admission_batch_receipt_return_and_idle() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    assert [case["id"] for case in evals] == [1, 2, 3, 4, 5]
    luna = next(case for case in evals if "manifest、全部 Skills、scripts、protocols 和 tests" in case["prompt"])
    broad_search = next(case for case in evals if "整个仓库搜索" in case["prompt"])
    multi_file = next(case for case in evals if "多个紧密相关文件" in case["prompt"])
    batch = next(case for case in evals if "两个互不依赖" in case["prompt"])
    lifecycle = next(case for case in evals if "同一 Topic" in case["prompt"] and "新 Topic" in case["prompt"])

    assert "拆成可独立返回" in luna["expected_output"]
    assert "允许派发" in broad_search["expected_output"]
    assert "允许派发" in multi_file["expected_output"]
    assert "receipt" in batch["expected_output"] and "idle" in batch["expected_output"]
    assert "复用" in lifecycle["expected_output"] and "fresh" in lifecycle["expected_output"]


def test_evals_are_wellformed_read_only_scenarios() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    for case in evals:
        assert case["expectations"]
        assert "只读模拟" in case["prompt"]
        assert "禁止实际修改" in case["prompt"]
