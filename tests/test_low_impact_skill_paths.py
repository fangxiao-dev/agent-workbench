from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_skill(*parts: str) -> str:
    return (ROOT.joinpath(*parts)).read_text(encoding="utf-8")


def test_brainstorming_fast_path_skips_design_artifacts_for_bounded_work() -> None:
    skill = read_skill("skills", "brainstorming", "SKILL.md")
    assert "Trivial / Local / Reversible Fast Path" in skill
    assert "no public-contract, security, data-migration, cross-host, or irreversible effect" in skill
    assert "Do not require alternatives, a design document, a planning artifact, or design approval." in skill


def test_skill_creator_defaults_local_nonsemantic_edits_to_focused_validation() -> None:
    skill = read_skill("skills", "skill-creator", "SKILL.md")
    assert "## Validation Scope" in skill
    assert "Default to focused validation for wording edits, rule clarifications, reference fixes, and local non-semantic corrections." in skill
    assert "changing a workflow or output contract" in skill
    assert "do not create a workspace, baseline runs, grading, benchmark, or viewer for this path" in skill


def test_task_manager_routes_single_authorized_upserts_to_apply_and_retains_escalations() -> None:
    skill = read_skill("skills", "task-manager", "SKILL.md")
    evals = read_skill("skills", "task-manager", "evals", "evals.json")
    assert "## Apply Routing" in skill
    assert "Apply an upsert directly when the user has explicitly asked to create or update it" in skill
    assert "more than one artifact is written; the operation is bulk, import, overwrite, delete, init, migration, refresh, or baseline work" in skill
    assert "Default behavior is dry-run." not in skill
    assert "run upsert --apply with --project shop-web; do not add a dry-run or second confirmation" in evals
    assert '"id": "create-future-feature"' in evals
    assert "dry-run upsert with --project supplier-admin" in evals
