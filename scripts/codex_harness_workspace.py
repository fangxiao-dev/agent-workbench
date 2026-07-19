"""Workspace handoff evidence shared by Crew and Impl-Package adapters."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


class WorkspaceError(RuntimeError):
    """A workspace handoff is malformed or unsafe to reuse."""


def _git(worktree: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(worktree), *args], capture_output=True, text=True)
    if completed.returncode:
        raise WorkspaceError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def worker_git_writable_roots(worktree: Path, branch: str, run_id: str, assignment_id: str) -> list[str]:
    """Return only the Git metadata roots required for one assignment branch commit."""

    expected_prefix = f"codex/crew/{run_id}/{assignment_id}/"
    if not branch.startswith(expected_prefix):
        raise WorkspaceError(f"Worker branch must remain in its assignment-scoped namespace: {expected_prefix}")
    root = worktree.resolve()
    if _git(root, "symbolic-ref", "HEAD") != f"refs/heads/{branch}":
        raise WorkspaceError("Worker worktree HEAD is not bound to the declared branch")
    git_dir = Path(_git(root, "rev-parse", "--absolute-git-dir")).resolve()
    common_dir = Path(_git(root, "rev-parse", "--git-common-dir")).resolve()
    objects = Path(_git(root, "rev-parse", "--git-path", "objects")).resolve()
    branch_ref = Path(_git(root, "rev-parse", "--git-path", f"refs/heads/{branch}")).resolve()
    branch_log = Path(_git(root, "rev-parse", "--git-path", f"logs/refs/heads/{branch}")).resolve()
    assignment_ref_root = (common_dir / "refs" / "heads" / "codex" / "crew" / run_id / assignment_id).resolve()
    assignment_log_root = (common_dir / "logs" / "refs" / "heads" / "codex" / "crew" / run_id / assignment_id).resolve()
    if assignment_ref_root not in branch_ref.parents or assignment_log_root not in branch_log.parents or common_dir not in git_dir.parents or objects != (common_dir / "objects").resolve():
        raise WorkspaceError("Worker Git metadata roots escaped the assignment boundary")
    assignment_ref_root.mkdir(parents=True, exist_ok=True)
    assignment_log_root.mkdir(parents=True, exist_ok=True)
    return [str(git_dir), str(objects), str(assignment_ref_root), str(assignment_log_root)]


def serial_handoff_evidence(worktree: Path, commit: str, verification: list[dict[str, Any]], delivery_program_id: str) -> dict[str, Any]:
    """Capture the facts required before a later assignment reuses a workspace."""

    root = worktree.resolve()
    resolved_commit = _git(root, "rev-parse", f"{commit}^{{commit}}")
    head = _git(root, "rev-parse", "HEAD")
    if head != resolved_commit:
        raise WorkspaceError("serial handoff commit must equal the clean worktree HEAD")
    if _git(root, "status", "--porcelain=v1"):
        raise WorkspaceError("serial handoff requires a clean worktree")
    if not verification or any(not isinstance(item, dict) or item.get("exit_code") != 0 for item in verification):
        raise WorkspaceError("serial handoff requires successful independent verification evidence")
    return {
        "schema_version": "codex-crew.serial-handoff.v0",
        "delivery_program_id": delivery_program_id,
        "worktree": str(root),
        "commit": resolved_commit,
        "verification": verification,
    }


def validate_serial_reuse(worktree: Path, handoff: dict[str, Any], delivery_program_id: str) -> dict[str, Any]:
    """Fail closed unless an accepted assignment can safely hand off its workspace."""

    required = {"schema_version", "delivery_program_id", "worktree", "commit", "verification"}
    if not isinstance(handoff, dict) or set(handoff) != required or handoff.get("schema_version") != "codex-crew.serial-handoff.v0":
        raise WorkspaceError("serial reuse handoff is malformed")
    root = worktree.resolve()
    if handoff["delivery_program_id"] != delivery_program_id or Path(handoff["worktree"]).resolve() != root:
        raise WorkspaceError("serial reuse handoff belongs to a different delivery program or worktree")
    if _git(root, "status", "--porcelain=v1"):
        raise WorkspaceError("serial reuse requires a clean worktree")
    previous = _git(root, "rev-parse", f"{handoff['commit']}^{{commit}}")
    _git(root, "merge-base", "--is-ancestor", previous, "HEAD")
    if not isinstance(handoff["verification"], list) or not handoff["verification"] or any(not isinstance(item, dict) or item.get("exit_code") != 0 for item in handoff["verification"]):
        raise WorkspaceError("serial reuse requires prior successful verification evidence")
    return json.loads(json.dumps(handoff))
