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
    "execution-preflight",
    "impl-planning",
    "subagent-driven-development",
    "grill-me-smartly",
    "grilling",
    "plan-review",
    "do-review",
    "review-code",
    "review-code-by-standards",
    "review-code-by-spec",
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
    agents_marketplace = load_json(MARKETPLACE / ".agents" / "plugins" / "marketplace.json")
    claude_marketplace = load_json(MARKETPLACE / ".claude-plugin" / "marketplace.json")

    assert codex["name"] == claude["name"] == "impl-package"
    assert codex["version"] == claude["version"] == "0.3.0"
    assert codex["skills"] == claude["skills"] == "./skills/"
    assert agents_marketplace["plugins"][0]["source"]["path"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["version"] == claude["version"]


def test_plugin_exposes_the_migrated_flat_skill_set() -> None:
    skill_files = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    names = {
        re.search(r"^name:\s*([^\s]+)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE).group(1)
        for path in skill_files
    }

    assert names == EXPECTED_SKILLS
    assert len(skill_files) == len(EXPECTED_SKILLS)
    assert not (PLUGIN / "skills" / "investigate-before-implement").exists()
    assert not (PLUGIN / "skills" / "dispatch-bounded-task").exists()

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


def test_unified_entry_owns_strategy_resolver_and_review_state() -> None:
    skill_dir = PLUGIN / "skills" / "subagent-driven-development"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    resolver = (skill_dir / "references" / "worker-resolver.md").read_text(encoding="utf-8")
    review = (skill_dir / "references" / "review-gate.md").read_text(encoding="utf-8")
    modes = (skill_dir / "references" / "mode-contracts.md").read_text(encoding="utf-8")

    assert len(skill.splitlines()) <= 180
    assert "mode:" in skill and "worker:" in skill and "review:" in skill
    strategy = skill.split("```yaml", 1)[1].split("```", 1)[0]
    assert "schedule:" not in strategy
    assert "route" not in skill.lower()
    assert '"$grok-worker"' in skill and '"@luna-worker"' in skill
    assert "skills/call-grok/SKILL.md" in resolver
    assert "@luna-worker" in resolver
    assert "不传 model/effort" in resolver
    assert "Outcome: BLOCKED" in resolver
    assert "fallback_from" in resolver
    assert "review_state: NOT_REQUIRED | PENDING_REVIEW | PASSED | FINDING | BLOCKED" in resolver
    assert "PENDING_REVIEW" in review
    assert "complexity" in review or "复杂度" in review
    assert all(marker in modes for marker in ("## investigate", "## implement", "## fix", "## review"))


def test_active_callers_use_only_the_unified_entry() -> None:
    callers = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills" / "impl-package" / "SKILL.md",
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        ROOT / "skills" / "handoff" / "references" / "task-execution.md",
        ROOT / "skills" / "thread-harness" / "references" / "role-b.md",
    )
    for caller in callers:
        text = caller.read_text(encoding="utf-8")
        assert "impl-package:subagent-driven-development" in text
        assert "impl-package:investigate-before-implement" not in text
        assert "impl-package:dispatch-bounded-task" not in text


def test_active_workflow_tree_has_no_legacy_entry_reference() -> None:
    roots = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills",
        ROOT / "skills" / "handoff",
        ROOT / "skills" / "handoff-to-new-session",
        ROOT / "skills" / "thread-harness",
    )
    legacy = (
        "impl-package:investigate-before-implement",
        "impl-package:dispatch-bounded-task",
        "/impl-package:investigate-before-implement",
        "/impl-package:dispatch-bounded-task",
        "route=dispatch-bounded-task",
    )
    files = [path for root in roots if root.is_file() for path in (root,)]
    files.extend(path for root in roots if root.is_dir() for path in root.rglob("*.md"))
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert not any(marker in text for marker in legacy), path


def test_terminal_review_contract_remains_owned_by_do_review() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")
    assert "/impl-package:do-review" in dev
    assert "terminal-final coverage 完整" in dev
    assert "已接受并归类 Track C / Spec fidelity finding" in dev
    assert "references/runtime-protocol.md" in dev
    assert "不创建 Ticket/Attempt 状态" in dev
    assert "不重复调度 reviewer" in dev
    assert "dispatch-fix" not in dev
    for duplicated_owner in ("review-code-by-standards", "review-code-by-spec", "safety-review"):
        assert duplicated_owner not in dev


def test_hot_path_skills_stay_within_instruction_budget() -> None:
    paths = (
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        PLUGIN / "skills" / "do-review" / "SKILL.md",
        PLUGIN / "skills" / "review-code" / "SKILL.md",
        PLUGIN / "skills" / "subagent-driven-development" / "SKILL.md",
    )
    counts = {path.parent.name: len(path.read_text(encoding="utf-8").splitlines()) for path in paths}

    assert counts["subagent-driven-development"] <= 180
    assert counts["do-review"] <= 120
    assert counts["review-code"] <= 120
    checklist = PLUGIN / "skills" / "review-code" / "references" / "review-checklist.md"
    assert checklist.is_file()
    assert "references/review-checklist.md" in paths[2].read_text(encoding="utf-8")
