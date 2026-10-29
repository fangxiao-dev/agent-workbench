from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/handoff"


def read(name):
    return (SKILL / name).read_text(encoding="utf-8")


def test_router_loads_only_the_relevant_existing_reference():
    text = read("SKILL.md")
    assert "尚未初始化运行状态" in text
    assert "读取一份参考" in text
    assert "disable-model-invocation: true" not in text
    for target in re.findall(r"\]\(([^)]+)\)", text):
        assert (SKILL / target).is_file(), target


def test_content_only_delivery_and_shared_lessons():
    text = read("SKILL.md")
    assert "默认输出可复制的交接文本" in text
    assert "用户需要文件时才" in text
    assert "本 session 尚未沉淀的经验" in text
    assert "没有内容写“无”" in text
    assert "已有长青覆盖直接引用" in text
    assert "用户行为要求、已有授权" in text
    combined = text + read("references/ordinary-task.md") + read("references/impl-package.md")
    for removed in ("create_thread", "wait_threads", "requestMeta", "compact_anchor", "anchor PASS", "continuation"):
        assert removed not in combined


def test_package_recovery_is_owned_by_harness():
    text = read("references/impl-package.md")
    assert "/impl-package:dev-with-track" in text
    assert "不复制 Ticket 状态" in text
    assert "均可省略" in text
    assert "先识别相关diff与归属" in text
    assert "不创建另一套状态协议" in text


def test_ordinary_task_has_no_runtime_precondition():
    text = read("references/ordinary-task.md")
    assert "尚未初始化运行状态" in text
    assert "首个判断和产出" in text
    assert "没有checkpoint或package state不妨碍交接" in text
    assert "不要求固定章节齐全" in text


def test_retired_protocol_is_not_an_active_dependency():
    assert not (ROOT / "skills/handoff-to-new-session/SKILL.md").exists()
    assert not (SKILL / "scripts/compact_anchor.py").exists()
    for folder in (ROOT / "skills", ROOT / "plugin-marketplace/plugins/impl-package/skills"):
        for path in folder.rglob("*"):
            if path.suffix not in (".md", ".yaml"):
                continue
            text = path.read_text(encoding="utf-8")
            assert "$handoff-to-new-session" not in text, path
            assert "references/task-execution.md" not in text, path


def test_session_delivery_signals_are_retired_from_the_situation_table():
    text = (ROOT / "plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml").read_text(encoding="utf-8")
    assert "attempt.record.handoff-recovery-needed" not in text
    assert "attempt.record.handoff-target-corrected" not in text
    assert "attempt.record.anchor-mismatch" in text
    assert "dev-with-track Restore" in text
