from __future__ import annotations

import sys
import copy
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "grill-me-smartly" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def test_grill_ledger_records_questions_answers_and_convergence(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    init = ledger.init_ledger(
        root=tmp_path,
        topic="docs/plans/example.md",
        slug="example",
        initiator="Codex",
    )

    assert "initialized Q ledger" in init.message

    q1 = ledger.add_question(
        root=tmp_path,
        slug="example",
        author="Questioner",
        branch="恢复能力",
        question="克隆后是否能恢复完整 dashboard?",
        why_now="这决定哪些 Obsidian 配置要纳入 Git。",
        recommended_default="跟踪 dashboard 必需配置,忽略机器本地状态。",
    )
    q2 = ledger.add_question(
        root=tmp_path,
        slug="example",
        author="Questioner",
        branch="来源建模",
        question="是否需要区分 repo 文档和 vault source note?",
        why_now="这决定来源路径的语义是否会混淆。",
        recommended_default="加入来源类型。",
    )

    assert q1.question_id == "Q1"
    assert q2.question_id == "Q2"

    ledger.record_answer(
        root=tmp_path,
        slug="example",
        question="Q1",
        author="Answerer",
        answer="当前计划不够完整。",
        evidence="`.obsidian/community-plugins.json` 启用 good-bases。",
        uncertainty="没有启动 Obsidian 做运行验证。",
        needs_user=False,
    )
    ledger.converge_question(
        root=tmp_path,
        slug="example",
        question="Q1",
        line="跟踪 dashboard 必需配置,本地路径写入 ignored local config。",
        rationale="这样 clone 后能恢复 dashboard,又不会提交机器私有路径。",
        impact="修改计划中的 Git track/ignore 策略。",
    )
    ledger.record_answer(
        root=tmp_path,
        slug="example",
        question="Q2",
        author="Answerer",
        answer="需要用户确认 source note 是否是一等来源。",
        evidence="现有任务同时引用 repo docs 和 TaskManager source notes。",
        uncertainty="source note 的产品语义不是纯本地事实。",
        needs_user=True,
    )
    ledger.need_user(
        root=tmp_path,
        slug="example",
        question="Q2",
        line="请裁决 vault source note 是否和 repo doc 一样作为一等来源。",
    )

    status = ledger.get_status(root=tmp_path, slug="example")
    assert status.frontmatter["status"] == ledger.STATUS_NEEDS_USER
    assert status.questions["Q1"]["status"] == ledger.Q_STATUS_CONVERGED
    assert status.questions["Q2"]["status"] == ledger.Q_STATUS_NEEDS_USER

    markdown = ledger.read_markdown(root=tmp_path, slug="example")
    assert "## 已收敛决策摘要" in markdown
    assert "跟踪 dashboard 必需配置" in markdown
    assert "## 待用户裁决" in markdown
    assert "vault source note" in markdown
    assert "| Q1 | 恢复能力 | 克隆后是否能恢复完整 dashboard? | 已收敛 | Answerer |" in markdown
    assert "## 停止证明" in markdown


def test_grill_ledger_end_turn_statuses(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="status", initiator="Codex")
    ledger.add_question(
        root=tmp_path,
        slug="status",
        author="Questioner",
        branch="验证",
        question="是否需要新增测试?",
        why_now="这决定实现完成标准。",
        recommended_default="新增最小行为测试。",
    )

    open_result = ledger.end_turn(root=tmp_path, slug="status")
    assert "status = 进行中" in open_result.message

    ledger.record_answer(
        root=tmp_path,
        slug="status",
        question="Q1",
        author="Answerer",
        answer="需要。",
        evidence="仓库已有 pytest 测试风格。",
        uncertainty="无。",
        needs_user=False,
    )
    ledger.converge_question(
        root=tmp_path,
        slug="status",
        question="Q1",
        line="新增 pytest 覆盖 ledger 行为。",
        rationale="和现有 discuss-ledger core 测试保持一致。",
        impact="增加一个聚焦测试文件。",
    )

    final_result = ledger.end_turn(root=tmp_path, slug="status")
    assert "status = 进行中" in final_result.message
    assert ledger.get_status(root=tmp_path, slug="status").frontmatter["status"] == ledger.STATUS_OPEN
    assert not ledger.review_path(tmp_path, "status").exists()

    stop_result = ledger.stop_review(
        root=tmp_path,
        slug="status",
        proof="Questioner 确认所有 material branches 已覆盖,没有待用户裁决项。",
    )
    assert "status = 已收敛" in stop_result.message
    assert ledger.get_status(root=tmp_path, slug="status").frontmatter["status"] == ledger.STATUS_CONVERGED

    review = ledger.read_review(root=tmp_path, slug="status")
    assert "# Grill Review：Plan" in review
    assert "## 最终结论" in review
    assert "新增 pytest 覆盖 ledger 行为。" in review
    assert "和现有 discuss-ledger core 测试保持一致。" in review
    assert "仓库已有 pytest 测试风格。" in review
    assert "## 停止依据" in review
    assert "Questioner 确认所有 material branches 已覆盖" in review
    assert "## 完整记录" not in review
    assert "## 问题与回答总览" not in review
    assert "<!-- grill-ledger-state" not in review
    assert "是否需要新增测试?" not in review


def test_stop_with_user_decision_writes_review_without_process_log(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="pending", initiator="Codex")
    ledger.add_question(
        root=tmp_path,
        slug="pending",
        author="Questioner",
        branch="风险偏好",
        question="是否接受破坏兼容?",
        why_now="这决定迁移策略。",
        recommended_default="默认不破坏兼容。",
    )
    ledger.record_answer(
        root=tmp_path,
        slug="pending",
        question="Q1",
        author="Answerer",
        answer="需要用户裁决。",
        evidence="本地没有风险偏好记录。",
        uncertainty="用户意图未知。",
        needs_user=True,
    )
    ledger.need_user(
        root=tmp_path,
        slug="pending",
        question="Q1",
        line="请裁决是否接受破坏兼容。",
    )

    ledger.stop_review(
        root=tmp_path,
        slug="pending",
        proof="剩余问题仅依赖真实用户裁决。",
    )

    review = ledger.read_review(root=tmp_path, slug="pending")
    assert "status: \"待用户裁决\"" in review
    assert "## 待用户裁决" in review
    assert "请裁决是否接受破坏兼容。" in review
    assert "为什么现在问" not in review
    assert "需要用户裁决。" not in review


def test_existing_legacy_ledger_remains_readable_and_writable(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Legacy", slug="legacy", initiator="Codex")
    new_path = ledger.ledger_path(tmp_path, "legacy")
    legacy_path = tmp_path / ledger.DEFAULT_DIR / "grill-legacy.md"
    new_path.rename(legacy_path)

    ledger.add_question(
        root=tmp_path,
        slug="legacy",
        author="Questioner",
        branch="兼容",
        question="旧 ledger 能否继续?",
        why_now="避免中断现有审阅。",
        recommended_default="继续读取旧文件。",
    )

    assert "旧 ledger 能否继续?" in legacy_path.read_text(encoding="utf-8")
    assert not new_path.exists()

    try:
        ledger.init_ledger(root=tmp_path, topic="Replacement", slug="legacy", initiator="Codex")
    except FileExistsError as exc:
        assert str(legacy_path) in str(exc)
    else:
        raise AssertionError("init_ledger should not overwrite an existing legacy ledger")


def test_grill_ledger_init_refuses_to_overwrite_existing_ledger(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="same", initiator="Codex")

    try:
        ledger.init_ledger(root=tmp_path, topic="Other", slug="same", initiator="Codex")
    except FileExistsError as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("init_ledger should not overwrite an existing ledger")

    markdown = ledger.read_markdown(root=tmp_path, slug="same")
    assert "Plan" in markdown
    assert "Other" not in markdown


def test_needs_user_answer_does_not_populate_empty_user_summary(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="intent", initiator="Codex")
    ledger.add_question(
        root=tmp_path,
        slug="intent",
        author="Questioner",
        branch="产品意图",
        question="是否接受破坏兼容?",
        why_now="这决定迁移策略。",
        recommended_default="默认不破坏兼容。",
    )
    ledger.record_answer(
        root=tmp_path,
        slug="intent",
        question="Q1",
        author="Answerer",
        answer="这取决于用户风险偏好。",
        evidence="本地文件没有记录风险偏好。",
        uncertainty="需要用户裁决。",
        needs_user=True,
    )

    status = ledger.get_status(root=tmp_path, slug="intent")
    assert status.frontmatter["status"] == ledger.STATUS_OPEN
    assert status.questions["Q1"]["status"] == ledger.Q_STATUS_ANSWERED
    assert status.state["needs_user"] == []

    ledger.need_user(
        root=tmp_path,
        slug="intent",
        question="Q1",
        line="请裁决是否接受破坏兼容。",
    )
    status = ledger.get_status(root=tmp_path, slug="intent")
    assert status.frontmatter["status"] == ledger.STATUS_NEEDS_USER
    assert status.questions["Q1"]["status"] == ledger.Q_STATUS_NEEDS_USER


def round_example() -> dict:
    reference = SRC.parent / "references" / "round-record.md"
    return json.loads(reference.read_text(encoding="utf-8").split("```json\n", 1)[1].split("```", 1)[0])


def test_import_round_cli_preserves_dialogue_and_owner_boundary(tmp_path: Path, capsys) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="rounds", initiator="Codex")
    batch = round_example()
    batch["items"][0]["discussion"] += " 代码示例：<!-- comment -->"
    owner = copy.deepcopy(batch["items"][0])
    owner.update(id="R1-Q2", question="是否改为异步删除？", needs_user=True)
    unresolved = copy.deepcopy(batch["items"][0])
    unresolved.update(id="R1-Q3", questioner_review="证据不足，继续查证。")
    unresolved.pop("proposal")
    batch["items"].extend([owner, unresolved])
    source = tmp_path / "round.json"
    source.write_text(json.dumps(batch, ensure_ascii=False), encoding="utf-8")
    args = ["--root", str(tmp_path), "import-round", "--slug", "rounds", "--file", str(source), "--accept", "R1-Q1"]

    assert ledger.main(args) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["ids"] == {"R1-Q1": "Q1", "R1-Q2": "Q2", "R1-Q3": "Q3"}
    status = ledger.get_status(root=tmp_path, slug="rounds")
    assert [q["status"] for q in status.questions.values()] == [
        ledger.Q_STATUS_CONVERGED, ledger.Q_STATUS_NEEDS_USER, ledger.Q_STATUS_ANSWERED,
    ]
    assert status.frontmatter["status"] == ledger.STATUS_NEEDS_USER
    assert len(status.state["convergences"]) == 1
    assert status.state["needs_user"][0]["line"] == owner["question"]
    markdown = ledger.read_markdown(root=tmp_path, slug="rounds")
    assert batch["items"][0]["discussion"] in markdown
    assert unresolved["questioner_review"] in markdown
    assert not ledger.review_path(tmp_path, "rounds").exists()

    assert ledger.main(args) == 0
    assert json.loads(capsys.readouterr().out)["replayed"] is True
    assert ledger.read_markdown(root=tmp_path, slug="rounds") == markdown
    # Post-processing still uses the existing Q IDs and records the real Owner answer.
    ledger.record_answer(root=tmp_path, slug="rounds", question="Q2", author="Owner",
                         answer="采纳异步删除", evidence="Owner 本轮回复", uncertainty="", needs_user=False)
    ledger.converge_question(root=tmp_path, slug="rounds", question="Q2",
                             line="改为异步删除", rationale="Owner 已裁决", impact="调整响应合同")
    assert ledger.get_status(root=tmp_path, slug="rounds").state["needs_user"] == []


@pytest.mark.parametrize("case", ["invalid_tail", "duplicate", "boolean", "owner_accept", "unknown_accept", "missing_proposal"])
def test_import_round_rejects_invalid_batch_without_partial_write(tmp_path: Path, case: str) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="invalid", initiator="Codex")
    before = ledger.read_markdown(root=tmp_path, slug="invalid")
    batch = round_example()
    accept = []
    if case == "invalid_tail":
        batch["items"].append({"id": "bad"})
    elif case == "duplicate":
        batch["items"].append(copy.deepcopy(batch["items"][0]))
    elif case == "boolean":
        batch["items"][0]["needs_user"] = "false"
    elif case == "owner_accept":
        batch["items"][0]["needs_user"] = True
        accept = ["R1-Q1"]
    elif case == "unknown_accept":
        accept = ["missing"]
    else:
        batch["items"][0].pop("proposal")
        accept = ["R1-Q1"]
    source = tmp_path / "round.json"
    source.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError):
        ledger.import_round(root=tmp_path, slug="invalid", file=source, accept=accept)
    assert ledger.read_markdown(root=tmp_path, slug="invalid") == before


def test_round_import_has_no_question_quota_and_rejects_changed_replay(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="large", initiator="Codex")
    batch = round_example()
    template = batch["items"][0]
    batch["items"] = [dict(template, id=f"R1-Q{i}") for i in range(1, 35)]
    source = tmp_path / "round.json"
    source.write_text(json.dumps(batch), encoding="utf-8")
    ledger.import_round(root=tmp_path, slug="large", file=source)
    before = ledger.read_markdown(root=tmp_path, slug="large")
    assert len(ledger.get_status(root=tmp_path, slug="large").questions) == 34
    with pytest.raises(ValueError, match="different content or acceptance"):
        ledger.import_round(root=tmp_path, slug="large", file=source, accept=["R1-Q1"])
    batch["items"][0]["answer"] = "changed"
    source.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match="different content or acceptance"):
        ledger.import_round(root=tmp_path, slug="large", file=source)
    assert ledger.read_markdown(root=tmp_path, slug="large") == before


def test_round_import_publish_failure_keeps_existing_ledger(tmp_path: Path, monkeypatch) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="atomic", initiator="Codex")
    before = ledger.read_markdown(root=tmp_path, slug="atomic")
    source = tmp_path / "round.json"
    source.write_text(json.dumps(round_example()), encoding="utf-8")

    def fail_replace(self, target):
        raise OSError("simulated publish failure")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated publish failure"):
        ledger.import_round(root=tmp_path, slug="atomic", file=source)
    assert ledger.read_markdown(root=tmp_path, slug="atomic") == before
    assert not list(ledger.ledger_path(tmp_path, "atomic").parent.glob(".grill-import-*"))


def test_round_import_rejects_reusing_stable_id_in_another_batch(tmp_path: Path) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="ids", initiator="Codex")
    batch = round_example()
    source = tmp_path / "round.json"
    source.write_text(json.dumps(batch), encoding="utf-8")
    ledger.import_round(root=tmp_path, slug="ids", file=source)
    before = ledger.read_markdown(root=tmp_path, slug="ids")
    batch["batch_id"] = "R1-B2"
    source.write_text(json.dumps(batch), encoding="utf-8")
    with pytest.raises(ValueError, match="item ids already imported"):
        ledger.import_round(root=tmp_path, slug="ids", file=source)
    assert ledger.read_markdown(root=tmp_path, slug="ids") == before


@pytest.mark.parametrize("include_owner", [False, True])
def test_stop_refuses_unresolved_import_even_when_other_items_need_owner(tmp_path: Path, include_owner: bool) -> None:
    from grill_ledger_core import ledger

    ledger.init_ledger(root=tmp_path, topic="Plan", slug="stop", initiator="Codex")
    batch = round_example()
    batch["items"][0].pop("proposal")
    batch["items"][0]["questioner_review"] = "证据不足，继续查证。"
    if include_owner:
        batch["items"].append(dict(batch["items"][0], id="R1-Q2", needs_user=True))
    source = tmp_path / "round.json"
    source.write_text(json.dumps(batch), encoding="utf-8")
    ledger.import_round(root=tmp_path, slug="stop", file=source)
    before = ledger.read_markdown(root=tmp_path, slug="stop")
    with pytest.raises(ValueError, match="cannot stop with unresolved questions: Q1"):
        ledger.stop_review(root=tmp_path, slug="stop", proof="未查清事实不能被此声明覆盖。")
    assert ledger.read_markdown(root=tmp_path, slug="stop") == before
    assert not ledger.review_path(tmp_path, "stop").exists()
