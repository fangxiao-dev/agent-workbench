from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
IMPL = ROOT / "skills/impl-package"


def files_under(root: Path):
    for current, directories, files in os.walk(root):
        directories[:] = [name for name in directories if name != "__pycache__" and "workspace" not in name]
        for name in files:
            yield Path(current) / name


def test_stage_evals_are_valid_and_nonempty() -> None:
    paths = [
        IMPL / "req-align/evals/evals.json",
        IMPL / "impl-planning/evals/evals.json",
        IMPL / "to-tickets/evals/evals.json",
        IMPL / "create-task-dag/evals/evals.json",
        IMPL / "dev-with-track/evals/evals.json",
        IMPL / "verification-before-completion/evals/evals.json",
    ]
    for path in paths:
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["skill_name"]
        assert payload["evals"]


def test_active_package_files_have_no_retired_state_mechanisms() -> None:
    retired = (
        "revision-bindings.json",
        "runtime-state.json",
        "contractVersion",
        "hash-object",
        "contentSha256",
        ".glob(",
        ".rglob(",
        "fnmatch",
    )
    for path in files_under(IMPL):
        if path.suffix.lower() not in {".md", ".py", ".json"}:
            continue
        text = path.read_text(encoding="utf-8")
        for token in retired:
            assert token not in text, f"{path.relative_to(ROOT)} contains {token}"


def test_core_templates_expose_only_current_contract() -> None:
    plan = (IMPL / "impl-planning/assets/templates/plan.md").read_text(encoding="utf-8")
    state = (IMPL / "references/impl-package-current-state.md").read_text(encoding="utf-8")
    gate = (IMPL / "dev-with-track/assets/templates/gate.md").read_text(encoding="utf-8")
    assert "tickets=<true|false>, dag=<true|false>" in plan
    assert '"formatVersion": "3.4"' in state
    assert all(field in state for field in ('"attempt"', '"tasks"', '"tickets"', '"resume"'))
    assert "execution/<attempt>/execution-record.md" in state
    assert "execution/<attempt>/task-handoffs/<task-id>-handoff.md" in state
    assert "set-state <task|ticket> <id> <state> --expect <state>" in state
    assert "Comparison commit" in gate


def test_complete_progress_and_workflow_surfaces_are_present() -> None:
    progress = (IMPL / "dev-with-track/assets/templates/progress.md").read_text(encoding="utf-8")
    planning = (IMPL / "impl-planning/assets/templates/plan.md").read_text(encoding="utf-8")
    review = (ROOT / "skills/plan-review/SKILL.md").read_text(encoding="utf-8")
    assert all(section in progress for section in ("Ticket Acceptance", "Task Execution", "Active Checkpoints", "Attempt History"))
    assert all(section in planning for section in ("Coverage & Change Map", "计划验证", "Bundle Review & Approval"))
    assert "fresh independent reviewer" in review
    for relative in (
        "assets/impl-package-intro.html",
        "references/evergreen-module-spec-and-backfill-design.md",
        "references/plan-apply-runbook.md",
        "dev-with-track/assets/templates/manual-acceptance-readiness.md",
    ):
        assert (IMPL / relative).is_file()


def test_deleted_audit_artifacts_stay_deleted() -> None:
    for relative in (
        "scripts/impl_package_apply.py",
        "assets/impl-package-state-config.json",
        "assets/templates/revision-bindings.json",
        "assets/templates/runtime-state.json",
    ):
        assert not (IMPL / relative).exists()
