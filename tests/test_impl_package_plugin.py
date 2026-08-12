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
    codex_marketplace = load_json(MARKETPLACE / ".agents" / "plugins" / "marketplace.json")
    claude_marketplace = load_json(MARKETPLACE / ".claude-plugin" / "marketplace.json")

    assert codex["name"] == claude["name"] == "impl-package"
    assert codex["version"] == claude["version"] == "0.2.8"
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
    scheduling_contract = subagent.split("```text", 1)[1].split("```", 1)[0]
    assert "Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED> · route=<route>" in scheduling_contract
    assert "mode=" not in scheduling_contract
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
    assert task_templates.count("Outcome: DONE | BLOCKED | INCOMPLETE") == 1
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


def test_dispatch_bounded_task_defines_fixer_profiles_and_template() -> None:
    dispatch = (
        PLUGIN / "skills" / "dispatch-bounded-task" / "SKILL.md"
    ).read_text(encoding="utf-8")
    task_templates = (
        PLUGIN / "skills" / "dispatch-bounded-task" / "references" / "task-templates.md"
    ).read_text(encoding="utf-8")
    failure_recovery = (
        PLUGIN / "skills" / "dispatch-bounded-task" / "references" / "worker-failure-recovery.md"
    ).read_text(encoding="utf-8")

    assert "| Implementer | `call-grok`：`grok-4.5`、`effort=high` | `luna-worker` | `gpt-5.6-terra`、`reasoning_effort=xhigh` |" in dispatch
    assert "| Fixer | `call-grok`：`grok-4.5`、`effort=high` | `luna-worker` | default subagent |" in dispatch
    assert "--no-subagents" not in dispatch
    assert "| Verifier | 调用者指定或当前宿主适配的验证 worker" in dispatch
    assert "存在 `reuse:` 时只沿用其中指定的同一 source unit 和 agent，不启动 `call-grok`" in dispatch
    assert "references/worker-failure-recovery.md" in dispatch
    assert dispatch.count("Outcome: DONE | BLOCKED | INCOMPLETE") == 1
    for native_status in ("timeout", "disconnect", "PARTIAL", "status != completed"):
        assert native_status not in dispatch
    assert "最多一次" in failure_recovery
    assert "进程已退出或被清理" in failure_recovery
    assert "实际 worktree diff" in failure_recovery
    assert "Outcome: INCOMPLETE" in failure_recovery
    assert "正常 `DONE` 与业务 `BLOCKED` 不进入本分支" in failure_recovery
    assert "不得换模型绕过" in failure_recovery

    assert "## Fixer" in task_templates
    assert "finding ID/ledger/reviewer" in task_templates
    assert "review target revision/comparison point" in task_templates
    assert "broken invariant/failure evidence" in task_templates
    assert "finding disposition/owner acceptance" in task_templates
    assert "不重新裁决 finding、不扩大范围、不宣称 closure" in task_templates
    assert "不以未证实的替代解释撤销既有修复" in task_templates
    assert task_templates.count("Outcome: DONE | BLOCKED | INCOMPLETE") == 1
    assert "quiet 选项" in task_templates
    assert "invocation-unique 临时日志" in task_templates
    assert "完整 stdout 留在 worker 或临时日志，不写入最终回复" in task_templates
    for evidence_field in (
        "command/procedure",
        "exit status",
        "pass/skip/failure count",
        "首个 actionable failure",
        "cleanup/residue",
        "artifact pointer",
    ):
        assert evidence_field in task_templates
    assert "成功日志无需沉淀" in task_templates
    assert "失败日志仅在其临时路径会改变下一步时" in task_templates


def test_terminal_pass_requires_applicable_safety_and_final_topology() -> None:
    dev = (PLUGIN / "skills" / "dev-with-track" / "SKILL.md").read_text(encoding="utf-8")

    assert "/impl-package:do-review" in dev
    assert "terminal-final coverage 完整" in dev
    for duplicated_owner in ("review-code-by-standards", "review-code-by-spec", "safety-review"):
        assert duplicated_owner not in dev


def test_hot_path_skills_stay_within_instruction_budget() -> None:
    paths = (
        PLUGIN / "skills" / "dev-with-track" / "SKILL.md",
        PLUGIN / "skills" / "dispatch-bounded-task" / "SKILL.md",
        PLUGIN / "skills" / "do-review" / "SKILL.md",
        PLUGIN / "skills" / "review-code" / "SKILL.md",
        PLUGIN / "skills" / "subagent-driven-development" / "SKILL.md",
    )
    counts = {path.parent.name: len(path.read_text(encoding="utf-8").splitlines()) for path in paths}

    assert sum(counts.values()) <= 350, counts
    assert counts["do-review"] <= 120
    assert counts["review-code"] <= 120
    checklist = PLUGIN / "skills" / "review-code" / "references" / "review-checklist.md"
    assert checklist.is_file()
    assert "references/review-checklist.md" in paths[3].read_text(encoding="utf-8")
    assert {"## Security review", "## Performance review", "## Testing review"} <= {
        line for line in checklist.read_text(encoding="utf-8").splitlines()
    }
