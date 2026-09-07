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
        "Topic-first 派发门槛",
        "机械附属不单独派发",
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


def test_topic_first_gate_splits_only_decision_changing_results() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    gate = skill.split("## Topic-first 派发门槛", 1)[1].split("## 调度循环", 1)[0]

    for marker in (
        "实现方向",
        "write ownership",
        "authorization",
        "资源 admission",
        "释放另一条可并行 Topic",
    ):
        assert marker in gate
    assert "继续切分" in gate


def test_topic_first_gate_allows_difficulty_based_adjacent_step_merge() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    gate = skill.split("## Topic-first 派发门槛", 1)[1].split("## 调度循环", 1)[0]

    for marker in ("无需新的主控裁决", "不损失并行机会", "不妨碍及时复核", "由 Astra 根据任务难度决定"):
        assert marker in gate
    assert "后段只是机械接线" not in gate


def test_breadth_gate_does_not_use_search_scope_or_file_count_as_a_limit() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    gate = skill.split("## Topic-first 派发门槛", 1)[1].split("## 调度循环", 1)[0]

    assert "检索整个仓库" in gate
    assert "多个紧密相关文件" in gate and "coherent outcome" in gate
    assert "文件数量" in gate
    assert "知识来源能分别阅读或返回，不等于必须分别派发" in gate


def test_dispatcher_refills_after_return_and_stops_thrashing() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "每次消费 return 后检查受影响候选" in skill
    assert "不等待无关 worker" in skill
    assert "当前批次全部结束或准备进入 idle 时再全局扫描" in skill
    assert "连续两次 `INCOMPLETE`" in skill
    assert "broad check 新发现一类 caller/producer" in skill
    assert "foundation investigation" in skill


def test_dispatcher_evals_cover_admission_batch_receipt_return_and_idle() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    assert [case["id"] for case in evals] == list(range(1, 11))
    source_inventory = next(case for case in evals if "shared runtime seam" in case["prompt"])
    broad_search = next(case for case in evals if "整个仓库搜索" in case["prompt"])
    multi_file = next(case for case in evals if "多个紧密相关文件" in case["prompt"])
    batch = next(case for case in evals if "两个互不依赖" in case["prompt"])
    lifecycle = next(case for case in evals if "同一 Topic" in case["prompt"] and "新 Topic" in case["prompt"])
    anti_thrash = next(case for case in evals if "连续两次返回 INCOMPLETE" in case["prompt"])
    future_conflict = next(case for case in evals if "未来都会修改同一个 controller" in case["prompt"])
    merge = next(case for case in evals if "不损失并行机会" in case["prompt"])
    value = next(case for case in evals if "预期产出很小" in case["prompt"])
    review = next(case for case in evals if "新的代码 diff" in case["prompt"])

    assert "保持一个 Topic" in source_inventory["expected_output"]
    assert "允许派发" in broad_search["expected_output"]
    assert "保持一个 baby step" in multi_file["expected_output"]
    assert "receipt" in batch["expected_output"] and "idle" in batch["expected_output"]
    assert "复用" in lifecycle["expected_output"] and "fresh" in lifecycle["expected_output"]
    assert "foundation investigation" in anti_thrash["expected_output"]
    assert "当前两个 baby step" in future_conflict["expected_output"] and "`PARALLEL`" in future_conflict["expected_output"]
    assert "冲突步骤到达" in future_conflict["expected_output"] and "`SERIAL`" in future_conflict["expected_output"]
    assert "按任务难度" in merge["expected_output"] and "合并" in merge["expected_output"]
    assert "暂缓" in value["expected_output"] and "dependency blocked" in value["expected_output"]
    assert "独立 review lane" in review["expected_output"] and "不机械派代码审查" in review["expected_output"]


def test_dispatcher_uses_value_based_release_and_conditional_delta_review() -> None:
    skill = SKILL.read_text(encoding="utf-8")

    assert "有实际收益" in skill
    assert "预期收益不足" in skill
    assert "没有新增代码改动时，不机械派代码审查" in skill
    assert "及时派轻量 delta review" in skill


def test_evals_are_wellformed_read_only_scenarios() -> None:
    evals = json.loads(EVALS.read_text(encoding="utf-8"))["evals"]

    for case in evals:
        assert case["expectations"]
        assert "只读模拟" in case["prompt"]
        assert "禁止实际修改" in case["prompt"]
