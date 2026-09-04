from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills-deprecated" / "dispatch-fix"
ARCHIVE_ROOT = ROOT / "skills-deprecated" / "dispatch-fix-thread"
SCRIPT = SKILL_ROOT / "scripts" / "group_bookkeeping.py"


def load_bookkeeping():
    spec = importlib.util.spec_from_file_location("dispatch_fix_group_bookkeeping", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def record_data() -> dict:
    return {
        "fix_id": "fix-123",
        "repository_root": "D:/repo",
        "fix_base": "a" * 40,
        "integration": {"branch": "feature", "worktree": "D:/repo"},
        "updated_at": "will-be-replaced",
        "groups": [
            {
                "id": "G1",
                "topic": "authentication",
                "findings": [
                    {
                        "id": "F1",
                        "summary": "reject expired token",
                        "acceptance_points": ["expired tokens are rejected"],
                    },
                    {
                        "id": "F2",
                        "summary": "preserve refresh token",
                        "acceptance_points": ["valid refresh token remains usable"],
                    },
                ],
                "write_scope": ["src/auth/"],
                "branch": "codex/fix-123-g1",
                "worktree": "D:/wt/fix-123-g1",
                "worker": "luna-g1",
                "source_commits": ["b" * 40],
                "integrated_commits": ["c" * 40],
                "focused_verification": ["pytest tests/auth -q: passed"],
                "result": "accepted",
                "conclusion": "F1 and F2 passed",
            },
            {
                "id": "G2",
                "topic": "billing",
                "findings": [
                    {
                        "id": "F3",
                        "summary": "round invoice total",
                        "acceptance_points": ["invoice uses currency precision"],
                    }
                ],
                "write_scope": ["src/billing/"],
                "branch": "codex/fix-123-g2",
                "worktree": "D:/wt/fix-123-g2",
                "worker": "luna-g2",
                "source_commits": ["d" * 40],
                "integrated_commits": ["e" * 40],
                "focused_verification": ["pytest tests/billing -q: passed"],
                "result": "accepted",
                "conclusion": "F3 passed",
            },
        ],
    }


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data), encoding="utf-8")


def test_dispatch_fix_is_deprecated_and_has_no_active_entry() -> None:
    root = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert not (ROOT / "skills" / "dispatch-fix" / "SKILL.md").exists()
    assert "name: dispatch-fix" in root
    assert "disable-model-invocation: true" in root
    assert "Deprecated historical archive. Do not invoke." in root
    assert "1–3 个 findings" in root
    assert "4 个及以上" in root
    assert "references/simple.md" in root
    assert "references/grouped.md" in root
    assert "parent-dispatch" not in root
    assert "parent-integrate" not in root
    assert "send_message_to_thread" not in root


def test_previous_skill_is_deprecated_and_has_no_active_entry() -> None:
    archived = (ARCHIVE_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert not (ROOT / "skills" / "dispatch-fix-thread" / "SKILL.md").exists()
    assert "deprecated: true" in archived
    assert "Deprecated historical archive. Do not invoke." in archived
    assert (ARCHIVE_ROOT / "scripts" / "bookkeeping.py").exists()
    assert (ARCHIVE_ROOT / "references" / "fixer.md").exists()
    assert (ARCHIVE_ROOT / "references" / "parent-dispatch.md").exists()
    assert (ARCHIVE_ROOT / "references" / "parent-integrate.md").exists()
    assert (ARCHIVE_ROOT / "evals" / "evals.json").exists()


def test_simple_mode_uses_one_worker_and_no_extra_coordination_artifacts() -> None:
    simple = (SKILL_ROOT / "references" / "simple.md").read_text(encoding="utf-8")

    assert "一个 Topic" in simple
    assert "$dispatcher" in simple
    assert "subagent-driven-development" in simple
    assert "work lane" in simple
    assert "@luna-worker" not in simple
    assert "让出整个 worktree 的写 ownership" in simple
    assert "不创建 ledger、branch 或额外 worktree" in simple
    assert "启动前已经存在的 dirty paths" in simple
    assert "简单模式不产生 group bookkeeping" in simple


def test_grouped_mode_uses_connected_grouping_and_independent_worktrees() -> None:
    grouped = (SKILL_ROOT / "references" / "grouped.md").read_text(encoding="utf-8")

    assert "topic 相同" in grouped
    assert "预计修改路径重叠" in grouped
    assert "共享可变资源" in grouped
    assert "每个 connected component 是一个 group" in grouped
    assert "每个 group 从 `fix_base` 创建唯一 branch/worktree" in grouped
    assert "每个 group 是独立 Topic" in grouped
    assert "$dispatcher" in grouped
    assert "work lane" in grouped
    assert "当前 worktree clean" in grouped
    assert "cherry-pick 回当前分支" in grouped
    assert "%TEMP%\\dispatch-fix\\<fix-id>\\groups.json" in grouped


def test_active_contract_has_no_task_handoff_protocol() -> None:
    active = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (
            SKILL_ROOT / "SKILL.md",
            SKILL_ROOT / "references" / "simple.md",
            SKILL_ROOT / "references" / "grouped.md",
        )
    )

    for stale_term in ("thread_id", "request.json", "state.json", "terminal projection"):
        assert stale_term not in active


def test_write_is_atomic_and_summary_counts_groups(tmp_path: Path) -> None:
    bookkeeping = load_bookkeeping()
    records = tmp_path / "records"
    input_path = tmp_path / "groups-input.json"
    write_json(input_path, record_data())

    written = bookkeeping.write_groups(records, input_path)
    result = bookkeeping.summary(records)

    assert written["updated_at"].endswith("Z")
    assert result == {
        "valid": True,
        "fix_id": "fix-123",
        "groups": 2,
        "accepted": 2,
        "blocked": 0,
        "working": 0,
    }
    assert list(records.glob(".groups.json.*.tmp")) == []


def test_record_rejects_extra_task_handoff_fields() -> None:
    bookkeeping = load_bookkeeping()
    data = record_data()
    data["thread_id"] = "legacy"

    with pytest.raises(bookkeeping.RecordError, match="unexpected fields: thread_id"):
        bookkeeping.validate_groups(data)


def test_group_worktrees_and_branches_must_be_unique() -> None:
    bookkeeping = load_bookkeeping()
    data = record_data()
    data["groups"][1]["worktree"] = data["groups"][0]["worktree"]

    with pytest.raises(bookkeeping.RecordError, match="group worktrees must be unique"):
        bookkeeping.validate_groups(data)


def test_accepted_group_requires_commit_mapping_and_focused_evidence() -> None:
    bookkeeping = load_bookkeeping()
    data = record_data()
    data["groups"][0]["integrated_commits"] = []

    with pytest.raises(bookkeeping.RecordError, match="correspond one-to-one"):
        bookkeeping.validate_groups(data)

    data = record_data()
    data["groups"][0]["focused_verification"] = []
    with pytest.raises(bookkeeping.RecordError, match="requires focused verification evidence"):
        bookkeeping.validate_groups(data)


def test_finding_can_belong_to_only_one_group() -> None:
    bookkeeping = load_bookkeeping()
    data = record_data()
    data["groups"][1]["findings"][0]["id"] = "F1"

    with pytest.raises(bookkeeping.RecordError, match="finding ids must be unique"):
        bookkeeping.validate_groups(data)
