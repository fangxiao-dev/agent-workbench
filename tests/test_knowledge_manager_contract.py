from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANAGER = ROOT / "skills" / "knowledge-manager"
SKILL = MANAGER / "SKILL.md"
EVALS = MANAGER / "evals" / "evals.json"
DESIGN = ROOT / "docs" / "skill-design" / "knowledge-manager-system-design-260913.md"
OLD_MANAGER = ROOT / "skills" / "project-knowledge-manager"
STANDALONE_RETRO = ROOT / "skills" / "retro"
OLD_DESIGN = ROOT / "docs" / "skill-design" / "retro-skill-design-260913.md"
BACKFILL = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "skills" / "backfill-stable-docs" / "SKILL.md"


def read_skill() -> str:
    assert SKILL.is_file(), f"missing Knowledge Manager skill: {SKILL}"
    return SKILL.read_text(encoding="utf-8")


def test_knowledge_manager_is_the_explicit_three_entry_manager() -> None:
    text = read_skill()
    frontmatter = text.split("---", 2)[1]

    assert "name: knowledge-manager" in frontmatter
    assert "disable-model-invocation: true" in frontmatter
    assert "name: project-knowledge-manager" not in frontmatter
    assert "name: retro" not in frontmatter
    assert "$knowledge-manager" in text
    assert "learn-lessons" in text
    assert "/impl-package:backfill-stable-docs" in text
    assert "environment lane" in text
    assert "不是独立 Skill" in text


def test_old_manager_and_standalone_retro_are_retired_without_aliases() -> None:
    assert not OLD_MANAGER.exists()
    assert not STANDALONE_RETRO.exists()
    assert not OLD_DESIGN.exists()


def test_environment_lane_keeps_all_seven_observation_categories() -> None:
    text = read_skill()
    categories = (
        ("Navigation",),
        ("Automated checks", "Checks"),
        ("Coding standards", "Standards"),
        ("Instruction placement",),
        ("Tool economy",),
        ("No-ops",),
        ("Information access",),
    )
    for alternatives in categories:
        assert any(marker in text for marker in alternatives)


def test_manager_dispatches_two_read_only_peer_audits() -> None:
    text = read_skill()

    for marker in (
        "$dispatcher",
        "learn-lessons",
        "/impl-package:backfill-stable-docs",
        "只读审计",
        "两个 worker",
    ):
        assert marker in text
    assert "宿主没有 subagent 能力时" in text
    assert "主线程顺序完成相同的只读审计" in text
    assert "不把 Manager 的 apply 授权传给 worker" in text


def test_peer_worker_cannot_inherit_manager_apply_authority() -> None:
    manager = read_skill()
    backfill = BACKFILL.read_text(encoding="utf-8")

    assert manager.count("只建立一次 `Source Snapshot`") == 1
    assert "两个 worker 与主线程共享这份快照" in manager
    assert "peer worker 只执行 `audit-only`" in backfill
    assert "不能继承或消费这份 apply 授权" in backfill
    assert "只有 Manager 主线程消费审计结果后可以据此 apply" in backfill


def test_manager_is_the_sole_writer() -> None:
    text = read_skill()

    for marker in (
        "唯一写者",
        "worker 不得写任何文件",
        "主线程消费",
    ):
        assert marker in text
    assert "environment 只生成报告" in text


def test_session_input_reuses_existing_references_and_falls_back_safely() -> None:
    text = read_skill()

    for marker in (
        "conversation/thread reference",
        "transcript",
        "file 或 link",
        "source-insufficient",
        "自定义 session ID",
    ):
        assert marker in text
    assert "继续可运行的知识 lane" in text


def test_owner_gap_is_separate_from_normal_recommendations() -> None:
    text = read_skill()

    for marker in (
        "owner-gap",
        "具体证据",
        "干预",
        "明确 owner",
    ):
        assert marker in text
    assert "不能混入 recommendation" in text


def test_audit_only_and_environment_report_only_are_explicit() -> None:
    text = read_skill()

    for marker in ("audit-only", "environment", "只生成报告"):
        assert marker in text
    assert "environment" in text and "不修改代码" in text
    assert "三个 lane 全部只读" in text
    assert "知识候选记为 `pending`" in text


def test_system_design_replaces_retro_design() -> None:
    assert DESIGN.is_file()
    text = DESIGN.read_text(encoding="utf-8")
    for marker in (
        "learn-lessons",
        "/impl-package:backfill-stable-docs",
        "knowledge-manager",
        "Source Snapshot",
        "environment lane",
        "owner-gap",
        "Matt Pocock",
        "audit-only",
    ):
        assert marker in text
    assert "不是 Skill、alias 或独立入口" in text


def test_manager_evals_cover_the_three_lane_contract() -> None:
    assert EVALS.is_file(), f"missing Knowledge Manager evals: {EVALS}"
    payload = json.loads(EVALS.read_text(encoding="utf-8"))

    assert payload["skill_name"] == "knowledge-manager"
    evals = payload["evals"]
    assert evals
    for case in evals:
        assert case["expectations"]
        assert case["prompt"]
        assert case["expected_output"]

    corpus = json.dumps(payload, ensure_ascii=False)
    assert any(marker in corpus for marker in ("learn-lessons", "Learn Lessons"))
    assert any(marker in corpus for marker in ("backfill-stable-docs", "Stable Docs"))
    for marker in (
        "environment",
        "owner-gap",
        "source-insufficient",
        "audit-only",
        "唯一写者",
        "去重",
        "冲突",
    ):
        assert marker in corpus
