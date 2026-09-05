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
    "dev-with-track",
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
    "execution-boundaries",
    "monitor-progress",
}

# Merged/renamed skill directories (slim refactor): the flat skill set above
# replaced these, except for the restored standalone grilling entry.
LEGACY_SKILL_DIRS = {
    "to-tickets",
    "execution-preflight",
    "standing-bookkeeper",
    "verification-before-completion",
    "create-task-dag",
}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_host_manifests_and_marketplaces_share_plugin_identity() -> None:
    codex = load_json(PLUGIN / ".codex-plugin" / "plugin.json")
    claude = load_json(PLUGIN / ".claude-plugin" / "plugin.json")
    agents_marketplace = load_json(MARKETPLACE / ".agents" / "plugins" / "marketplace.json")
    claude_marketplace = load_json(MARKETPLACE / ".claude-plugin" / "marketplace.json")

    assert codex["name"] == claude["name"] == "impl-package"
    assert codex["version"] == claude["version"] == "0.4.2"
    assert codex["skills"] == claude["skills"] == "./skills/"
    assert codex["hooks"] == "./hooks/codex-hooks.json"
    assert "hooks" not in claude
    assert (PLUGIN / "hooks" / "codex-hooks.json").is_file()
    assert (PLUGIN / "hooks" / "impl_package_hooks.py").is_file()
    assert "agents" not in codex
    assert claude["agents"] == [
        "./agents/review-track-code.md",
        "./agents/review-track-standards.md",
        "./agents/review-track-spec.md",
        "./agents/review-track-safety.md",
    ]
    assert agents_marketplace["plugins"][0]["source"]["path"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["source"] == "./plugins/impl-package"
    assert claude_marketplace["plugins"][0]["version"] == claude["version"]


def test_do_review_owns_the_judgment_heuristics() -> None:
    review = (PLUGIN / "skills" / "do-review" / "SKILL.md").read_text(encoding="utf-8")

    # Judgment heuristics stay in the slim do-review (mechanics moved to the
    # orchestrator / reviewer presets).
    for marker in (
        "Safety admission",
        "Closure ≠ terminal",
        "terminal-final",
        "finding-closure",
        "Loop clean & convergence",
        "Track C source recheck",
        "reviewer-registry.json",
        "review_ledger.py",
        "review_track_stats.py record",
        "review.canonical_summary",
        "native subagents",
        "owner approval",
    ):
        assert marker in review
    # Host-specific leaf mapping is gone from the skill (moved to presets).
    assert "review-track-code" not in review
    assert "spawn_subagent" not in review

    output_contract = (PLUGIN / "skills" / "do-review" / "references" / "output-templates.md").read_text(
        encoding="utf-8"
    )
    for marker in ("findingKey", "ticketIds", "tracks", "classification", "lifecycle"):
        assert marker in output_contract


def test_plugin_exposes_the_slimmed_flat_skill_set() -> None:
    skill_files = sorted((PLUGIN / "skills").glob("*/SKILL.md"))
    names = {
        re.search(r"^name:\s*([^\s]+)\s*$", path.read_text(encoding="utf-8"), re.MULTILINE).group(1)
        for path in skill_files
    }

    assert names == EXPECTED_SKILLS
    assert len(skill_files) == len(EXPECTED_SKILLS)
    for legacy in LEGACY_SKILL_DIRS:
        assert not (PLUGIN / "skills" / legacy / "SKILL.md").exists(), f"{legacy} should be merged away"
    assert not (PLUGIN / "skills" / "investigate-before-implement").exists()
    assert not (PLUGIN / "skills" / "dispatch-bounded-task").exists()

    router = (PLUGIN / "skills" / "impl-package" / "SKILL.md").read_text(encoding="utf-8")
    # The routing table is now a native-command index (`impl-<stage>`).
    for name in EXPECTED_SKILLS - {"impl-package", "execution-boundaries"}:
        assert f"impl-{name}" in router
    assert "/plugin:skill" in router


def test_monitor_progress_opens_dashboard_before_optional_automation() -> None:
    skill_dir = PLUGIN / "skills" / "monitor-progress"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    template = (skill_dir / "templates" / "automation-prompt.md").read_text(encoding="utf-8")

    assert "disable-model-invocation: true" in skill
    assert "CODEX_THREAD_ID" in skill
    assert skill.index("monitor_progress.py open") < skill.index("是否启用 automation 监控")
    assert "用户拒绝时返回页面 URL 并停止" in skill
    assert "monitor_progress.py" in skill
    for marker in (
        "read-cycle",
        "read-static",
        "STATIC_HASH",
        "items: []",
        "ownerInputs",
            "packageStatus",
            "ticketPresentation",
        "packageDiff",
        "targetUpdates",
        "nextRolloutCursors",
        "observationDiff",
        "lastSimulationCorrection",
        "按 observations 顺序分类",
        "confirmed 生效",
        "candidate 不授权",
        "kind=pattern",
        "one-time",
            "明确实例/一次决策=one-time",
            "steer前看上下文，idle≠block，讨论不发",
        "语义变化",
        "progress=事实/必修问题",
        "improvements=不影响收口的可选建议",
        "不造字段",
    ):
        assert marker in template
    for command in ("read-cycle", "read-static", "write-cycle"):
        assert command in template
    assert "{{MONITOR_CLI_PATH_JSON}}" in template
    assert len(template) < 1000
    assert "工具调试不入 sidecar" in template
    assert "Grok" not in template
    assert "antecedent、主体、动作和范围" in skill
    assert "kind/增改删" in template
    assert "模拟纠偏" in template
    assert "否则写“无”" in template
    assert "dry-run" in template
    rendered = (
        template.replace("{{AUTOMATION_ID}}", "impl-package-2026-08-31-bank-reconciliation-nm-settlement-groups")
        .replace(
            "{{WORKSPACE_ROOT_JSON}}",
            r"D:\\CodeSpace\\kaispan-dev\\.worktrees\\260824-finance-assistant-mvp-implementation",
        )
        .replace(
            "{{MONITOR_CLI_PATH_JSON}}",
            r"C:\\Users\\Xiao\\.codex\\plugins\\cache\\agent-workbench\\impl-package\\0.4.2\\scripts\\monitor_progress.py",
        )
        .replace("{{STATIC_HASH}}", "f" * 64)
    )
    assert len(rendered) < 1000
    for obsolete in (
        "{{MONITOR_THREAD_ID}}",
        "{{TARGET_THREAD_ID}}",
        "TARGET_BASELINE_JSON",
        "MONITOR_STATE",
        "OWNER_FALLBACK_OVERRIDE",
        "automation_update",
        "真实测试 PDF",
        "non-terminal idle/blocked",
        "policySnapshot.fallback",
        "targetBaseline",
        "policySnapshot",
        "runtimeState",
        '"statement"',
        '"supersedes"',
        "ledgerFingerprint",
    ):
        assert obsolete not in template


def test_migration_validator_is_standalone_and_not_a_runtime_entrypoint() -> None:
    migration_validator = PLUGIN / "scripts" / "validate_ticket_first_migration.py"
    assert migration_validator.is_file()
    assert not (PLUGIN / "skills" / "validate_ticket_first_migration").exists()

    for manifest_path in (PLUGIN / ".codex-plugin" / "plugin.json", PLUGIN / ".claude-plugin" / "plugin.json"):
        manifest = load_json(manifest_path)
        assert manifest["skills"] == "./skills/"
        assert "validate_ticket_first_migration.py" not in json.dumps(manifest)

    runtime_sources = (
        PLUGIN / "scripts" / "impl_package_state.py",
        PLUGIN / "scripts" / "impl_package_runtime" / "command_groups.py",
        PLUGIN / "scripts" / "impl_package_runtime" / "engine.py",
    )
    for source in runtime_sources:
        text = source.read_text(encoding="utf-8")
        assert "validate_ticket_first_migration" not in text
        assert "validate_migration(" not in text

    preflight = (PLUGIN / "skills" / "execution-boundaries" / "SKILL.md").read_text(encoding="utf-8")
    assert "validate_ticket_first_migration" not in preflight
    linker = (ROOT / "scripts" / "link_skill.py").read_text(encoding="utf-8")
    assert "validate_ticket_first_migration" not in linker

    runbook = (PLUGIN / "references" / "ticket-first-migration-runbook.md").read_text(encoding="utf-8")
    assert "scripts/validate_ticket_first_migration.py" in runbook
    assert "普通 3.5 runtime 不会主动调用它" in runbook


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


def test_unified_entry_owns_method_and_review_requirement_judgment() -> None:
    skill_dir = PLUGIN / "skills" / "subagent-driven-development"
    skill = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    review = (skill_dir / "references" / "review-gate.md").read_text(encoding="utf-8")

    assert len(skill.splitlines()) <= 140
    for marker in (
        "Topic",
        "foundation dependency",
        "acceptance dependency",
        "work lane",
        "review lane",
        "test lane",
        "investigate",
        "EVIDENCE_SUFFICIENT",
        "verify",
        "不重新裁决",
        "BLOCKED",
        "始终拥有最终集成",
    ):
        assert marker in skill
    assert "$grok-worker" not in skill
    assert "@luna-worker" not in skill
    assert "```yaml" not in skill
    assert "PENDING_REVIEW" in review
    assert "do-review" in review
    assert not (skill_dir / "references" / "worker-resolver.md").exists()
    assert not (skill_dir / "references" / "mode-contracts.md").exists()


def test_active_callers_reference_the_unified_entry() -> None:
    callers = (
        ROOT / "AGENTS.md",
        PLUGIN / "skills" / "impl-package" / "SKILL.md",
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        ROOT / "skills" / "handoff" / "references" / "task-execution.md",
        ROOT / "skills" / "thread-harness" / "references" / "role-b.md",
    )
    for caller in callers:
        text = caller.read_text(encoding="utf-8")
        # Cross-host routing form (`/impl-package:subagent-driven-development`) or the
        # DSH native command form (`impl-subagent-driven-development`).
        assert "impl-package:subagent-driven-development" in text or "impl-subagent-driven-development" in text
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
    review = (PLUGIN / "skills" / "do-review" / "SKILL.md").read_text(encoding="utf-8")
    # do-review owns the review topology/fail-closed contract (slim form keeps the judgment).
    assert "terminal-final" in review
    assert "Closure ≠ terminal" in review
    assert "finding-closure" in review
    assert "INCOMPLETE" in review
    # dev-with-track keeps the execution/Gate judgment; review dispatch is injected via
    # the situation protocol, not repeated here.
    assert "Escape" in dev or "escape" in dev
    assert "terminal Gate" in dev
    assert "Stage 7" in dev
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


def test_resume_capsule_supplies_facts_while_runtime_reference_keeps_the_fallback() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")
    runtime = (PLUGIN / "skills" / "dev-with-track" / "references" / "runtime-protocol.md").read_text(
        encoding="utf-8"
    )
    boundaries = (PLUGIN / "skills" / "execution-boundaries" / "SKILL.md").read_text(encoding="utf-8")

    restore = dev.split("## Restore", 1)[1].split("## Ticket 激活 preflight", 1)[0]
    assert "Impl-Package Resume Capsule v1" in dev
    assert "references/runtime-protocol.md" in restore
    assert "activate --package <package>" in restore
    assert "deactivate" in restore
    assert "progress.md" not in restore
    assert dev.count("唯一 writer") == 1

    assert "## Codex Resume Capsule" in runtime
    assert "## 恢复顺序" in runtime
    for marker in ("package validate", "progress.md", "situation.py render"):
        assert marker in runtime
    assert "task-queue.json" not in runtime
    assert "Impl-Package Resume Capsule v1" in boundaries
