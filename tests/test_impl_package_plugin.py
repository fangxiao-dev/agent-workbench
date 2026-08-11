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
    assert codex["version"] == claude["version"] == "0.2.1"
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
        r"(?<![\w/])((?:\.\./)*(?:references|assets|scripts|evals)/[A-Za-z0-9_.\-/]+)"
    )
    plugin_root = PLUGIN.resolve()

    for skill_file in (PLUGIN / "skills").glob("*/SKILL.md"):
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


def test_parallel_admission_and_optional_capabilities_are_internalized() -> None:
    investigate = (PLUGIN / "skills" / "investigate-before-implement" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    subagent = (PLUGIN / "skills" / "subagent-driven-development" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "references/parallel-work-admission.md" in investigate
    assert "$dispatching-parallel-agents" not in investigate
    assert "$call-grok" not in investigate
    assert "$reviewer" not in subagent
    assert (PLUGIN / "skills" / "investigate-before-implement" / "references" / "parallel-work-admission.md").is_file()
