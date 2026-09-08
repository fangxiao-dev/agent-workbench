from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace" / "plugins" / "impl-package"
SDD = PLUGIN / "skills" / "subagent-driven-development"
DISPATCHER = ROOT / "skills" / "dispatcher"


def test_retired_sdd_directory_is_absent() -> None:
    assert not SDD.exists()


def test_sdd_method_material_moved_to_dispatcher() -> None:
    skill = (DISPATCHER / "SKILL.md").read_text(encoding="utf-8")
    delegation = (DISPATCHER / "references" / "delegation.md").read_text(encoding="utf-8")
    resources = (DISPATCHER / "references" / "resource-isolation.md").read_text(encoding="utf-8")
    text = "\n".join((skill, delegation, resources))

    for marker in (
        "investigate",
        "implement",
        "fix",
        "verify",
        "DONE | BLOCKED | INCOMPLETE",
        "EVIDENCE_SUFFICIENT | EVIDENCE_GAP",
        "PENDING_REVIEW | PASSED",
        "foundation",
        "acceptance",
        "resource",
        "authorization",
        "当前动作 recovery",
    ):
        assert marker in text


def test_material_review_requirement_moved_to_business_owner() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")
    for marker in ("shared seam", "安全", "数据完整性", "并发", "migration", "权限", "不可逆外部副作用"):
        assert marker in dev
    assert "formal review requirement" in dev
    assert "do-review" in dev


def test_dev_uses_business_focus_and_candidate_scope() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")
    loop = dev.split("## 业务控制循环", 1)[1].split("## Owner 边界", 1)[0]

    for marker in ("刷新业务事实", "确定重点和候选范围", "应用 `$dispatcher`", "消费并记录", "判断继续或收口"):
        assert marker in loop
    assert "唯一业务下一动作" not in dev
    assert "/impl-package:subagent-driven-development" not in dev


def test_active_callers_route_execution_collaboration_to_dispatcher() -> None:
    callers = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills" / "impl-package" / "SKILL.md",
        PLUGIN / "skills" / "impl-planning" / "SKILL.md",
        PLUGIN / "skills" / "execution-boundaries" / "SKILL.md",
        PLUGIN / "skills" / "do-review" / "SKILL.md",
        ROOT / "skills" / "handoff" / "references" / "task-execution.md",
        ROOT / "skills" / "handoff-to-new-session" / "SKILL.md",
        ROOT / "skills" / "thread-harness" / "references" / "role-a.md",
        ROOT / "skills" / "thread-harness" / "references" / "role-b.md",
    )
    for path in callers:
        text = path.read_text(encoding="utf-8")
        assert "$dispatcher" in text, path
        assert "impl-package:subagent-driven-development" not in text, path
        assert "impl-subagent-driven-development" not in text, path

def test_active_markdown_has_no_sdd_route_outside_explicit_boundaries() -> None:
    roots = (ROOT / "AGENTS.md", ROOT / "skills", PLUGIN / "references", PLUGIN / "skills")
    files = [path for root in roots if root.is_file() for path in (root,)]
    files.extend(path for root in roots if root.is_dir() for path in root.rglob("*.md"))
    excluded = {
        ROOT / "skills" / "dispatcher" / "rubric.md",
        PLUGIN / "skills" / "dev-with-track" / "rubric.md",
    }
    for path in files:
        if path in excluded or SDD in path.parents or ROOT / "skills" / "dispatcher-workspace" in path.parents:
            continue
        text = path.read_text(encoding="utf-8")
        assert "impl-package:subagent-driven-development" not in text, path
        assert "impl-subagent-driven-development" not in text, path
