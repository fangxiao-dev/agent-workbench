from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MARKETPLACE = ROOT / "plugin-marketplace"
PLUGIN = MARKETPLACE / "plugins" / "impl-package"
EXPECTED_SKILLS = {
    "impl-package",
    "backfill-stable-docs",
    "create-task-dag",
    "dev-with-track",
    "dispatch-bounded-task",
    "execution-preflight",
    "impl-planning",
    "investigate-before-implement",
    "subagent-driven-development",
    "grill-me-smartly",
    "grilling",
    "plan-review",
    "do-review",
    "code-review",
    "standards-review",
    "spec-review",
    "safety-review",
    "req-align",
    "to-tickets",
    "verification-before-completion",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_host_manifests_and_marketplaces_share_plugin_identity() -> None:
    codex = load_json(PLUGIN / ".codex-plugin" / "plugin.json")
    claude = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    codex_marketplace = load_json(MARKETPLACE / ".agents" / "plugins" / "marketplace.json")
    claude_marketplace = load_json(MARKETPLACE / ".claude-plugin" / "marketplace.json")

    assert codex["name"] == claude["name"] == "impl-package"
    assert codex["version"] == claude["version"] == "0.2.4"
    assert codex["skills"] == claude["skills"] == "./skills/"
    assert codex_marketplace["name"] == claude_marketplace["name"] == "agent-workbench"
    assert codex_marketplace["plugins"][0]["source"]["path"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["version"] == claude["version"]


def test_plugin_exposes_twenty_flat_namespaced_skills() -> None:
    skill_files = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    names = {
        re.search(r"^name:\s*([^\s]+)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE).group(1)
        for path in skill_files
    }

    assert names == EXPECTED_SKILLS
    assert len(skill_files) == 20
    codex_names = {f"impl-package:{name}" for name in names}
    assert codex_names == {f"impl-package:{name}" for name in EXPECTED_SKILLS}

    router = (PLUGIN / "skills" / "impl-package" / "SKILL.md").read_text(encoding="utf-8")
    for name in EXPECTED_SKILLS - {"impl-package"}:
        assert f"`/impl-package:{name}`" in router


def test_skill_resource_paths_stay_inside_plugin() -> None:
    relative_resource = re.compile(
        r"(?<![\w/])((?:\.\./)*(?:references|assets|scripts|evals|sub-skills)/[A-Za-z0-9_.\-/]+)"
    )
    plugin_root = PLUGIN.resolve()

    skill_files = list((PLUGIN / "skills").glob("*/SKILL.md"))
    skill_files.extend((PLUGIN / "skills").glob("*/sub-skills/*/SUB-SKILL.md"))
    for skill_file in skill_files:
        for match in relative_resource.finditer(skill_file.read_text(encoding="utf-8")):
            target = (skill_file.parent / match.group(1)).resolve()
            assert target.is_relative_to(plugin_root), f"path escapes plugin: {skill_file}: {match.group(1)}"
            assert target.exists(), f"missing resource: {skill_file}: {match.group(1)}"


def test_old_impl_package_source_is_absent() -> None:
    assert not (ROOT / "skills" / "impl-package" / "SKILL.md").exists()
    assert not list((ROOT / "skills" / "impl-package").glob("*/SKILL.md"))
    assert not (ROOT / "plugins" / "impl-package").exists()

    moved_sources = (
        "investigate-before-implement",
        "subagent-driven-development",
        "grill-me-smartly",
        "grilling",
        "plan-review",
        "do-review",
    )
    for name in moved_sources:
        assert not (ROOT / "skills" / name / "SKILL.md").exists()
    for name in ("code-review", "standards-review", "spec-review", "safety-review"):
        assert not (ROOT / "skills" / "reviews" / name / "SKILL.md").exists()
    assert not (ROOT / "skills" / "dispatching-parallel-agents" / "SKILL.md").exists()


def test_delegation_layers_are_orthogonal_and_resources_are_internalized() -> None:
    investigate = (PLUGIN / "skills" / "investigate-before-implement" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    subagent = (PLUGIN / "skills" / "subagent-driven-development" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    dispatch = (PLUGIN / "skills" / "dispatch-bounded-task" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    task_templates = (
        PLUGIN / "skills" / "dispatch-bounded-task" / "references" / "task-templates.md"
    ).read_text(encoding="utf-8")

    assert "references/parallel-work-admission.md" not in investigate
    assert "luna-worker" not in investigate
    assert "dispatch-bounded-task" not in investigate
    assert "EVIDENCE_SUFFICIENT | EVIDENCE_GAP" in investigate
    assert "references/parallel-work-admission.md" in subagent
    assert "Plan、Ticket 或 DAG" in subagent
    assert "不要求 DAG Task artifact" in subagent
    assert "实施依据不足 →" not in subagent
    assert "原因、影响面与必要前置事实已经建立" in subagent
    assert "investigate-before-implement" not in subagent
    assert "Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED>" in subagent
    assert "batches/order:" not in subagent
    assert "resource keys:" not in subagent
    assert "task-templates.md" not in subagent
    assert "luna-worker" not in subagent
    assert "luna-worker" in dispatch
    assert "references/task-templates.md" in dispatch
    assert "/impl-package:subagent-driven-development" not in dispatch
    assert "batch/order" not in dispatch
    assert "resource keys" not in dispatch
    assert "cleanup owner" not in dispatch
    assert "batch/order" not in task_templates
    assert "resource/cleanup" not in task_templates
    assert "mode=<" not in task_templates
    assert "DONE" not in task_templates
    assert "BLOCKED" not in task_templates
    assert "$dispatching-parallel-agents" not in investigate
    assert "$call-grok" not in investigate
    assert "$reviewer" not in subagent
    assert not (
        PLUGIN
        / "skills"
        / "investigate-before-implement"
        / "references"
        / "parallel-work-admission.md"
    ).exists()
    assert (
        PLUGIN
        / "skills"
        / "subagent-driven-development"
        / "references"
        / "parallel-work-admission.md"
    ).is_file()

    routing_consumers = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        ROOT / "skills" / "thread-harness" / "SKILL.md",
        ROOT / "skills" / "handoff" / "references" / "task-execution.md",
    )
    for consumer in routing_consumers:
        text = consumer.read_text(encoding="utf-8")
        assert "/impl-package:dispatch-bounded-task" not in text
        assert "Plan、Ticket 或 DAG" not in text
