"""Execution-topology validation and serial-worktree gates for Codex Crew."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


TOPOLOGY_SCHEMA_VERSION = "codex-crew.execution-topology.v0"
TOPOLOGIES = {"read_only", "parent_serial", "worker_parallel"}


class TopologyError(RuntimeError):
    """Raised when a topology declaration or serial handoff is unsafe."""


def _git(worktree: Path, *args: str) -> str:
    completed = subprocess.run(["git", "-C", str(worktree), *args], capture_output=True, text=True)
    if completed.returncode:
        raise TopologyError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def validate_execution_topology(value: dict[str, Any], contracts: dict[str, Any] | None = None) -> dict[str, Any]:
    """Validate the parent-declared topology without turning it into acceptance."""

    required = {
        "schema_version",
        "execution_topology",
        "dispatcher_required",
        "max_active_write_worktrees",
        "workspace_reuse_policy",
        "promotion_boundary",
        "selection_rationale",
        "not_parallel_rationale",
    }
    if not isinstance(value, dict) or set(value) != required:
        raise TopologyError("execution topology has unsupported or missing fields")
    if value["schema_version"] != TOPOLOGY_SCHEMA_VERSION:
        raise TopologyError("unsupported execution topology schema version")
    topology = value["execution_topology"]
    if topology not in TOPOLOGIES:
        raise TopologyError("unsupported execution topology")
    if not isinstance(value["dispatcher_required"], bool) or not isinstance(value["max_active_write_worktrees"], int) or isinstance(value["max_active_write_worktrees"], bool):
        raise TopologyError("dispatcher_required and max_active_write_worktrees are malformed")
    if any(not isinstance(value[key], str) or not value[key].strip() for key in ("workspace_reuse_policy", "promotion_boundary", "selection_rationale")):
        raise TopologyError("execution topology string fields must be non-empty")
    if value["not_parallel_rationale"] is not None and (not isinstance(value["not_parallel_rationale"], str) or not value["not_parallel_rationale"].strip()):
        raise TopologyError("not_parallel_rationale must be a non-empty string or null")
    expected = {
        "read_only": (False, 0, True),
        "parent_serial": (False, 1, True),
        "worker_parallel": (True, None, False),
    }[topology]
    configured = (contracts or {}).get(topology, {})
    configured_dispatcher = configured.get("dispatcher_required", expected[0])
    configured_maximum = configured.get("max_active_write_worktrees", expected[1])
    configured_minimum = configured.get("minimum_active_write_worktrees", 2 if topology == "worker_parallel" else None)
    if value["dispatcher_required"] is not configured_dispatcher:
        raise TopologyError(f"{topology} has an invalid dispatcher requirement")
    if configured_maximum is not None and value["max_active_write_worktrees"] != configured_maximum:
        raise TopologyError(f"{topology} has an invalid write-worktree bound")
    if topology == "worker_parallel" and value["max_active_write_worktrees"] < configured_minimum:
        raise TopologyError("worker_parallel requires at least two active write worktrees")
    for field in ("workspace_reuse_policy", "promotion_boundary"):
        if field in configured and value[field] != configured[field]:
            raise TopologyError(f"{topology} does not match the canonical {field}")
    if expected[2] and value["not_parallel_rationale"] is None:
        raise TopologyError(f"{topology} requires a not_parallel_rationale")
    if not expected[2] and value["not_parallel_rationale"] is not None:
        raise TopologyError("worker_parallel must not invent a non-parallel rationale")
    return dict(value)


def serial_worktree_spec(repository_root: Path, run_id: str) -> dict[str, str]:
    root = repository_root.resolve()
    return {
        "path": str(root.parent / ".codex-crew-worktrees" / run_id / "parent-serial"),
        "branch": f"codex/crew/{run_id}/serial",
        "base_ref": "HEAD",
    }


def ensure_serial_worktree(repository_root: Path, worktree: dict[str, str]) -> dict[str, str]:
    """Create or reopen the one parent-owned serial worktree for a run."""

    root = repository_root.resolve()
    target = Path(worktree["path"]).resolve()
    if target == root:
        raise TopologyError("parent_serial must not write the controller repository worktree")
    if target.exists():
        listed = _git(root, "worktree", "list", "--porcelain")
        if f"worktree {target}" not in listed:
            raise TopologyError("serial worktree path exists but is not registered")
        return {"path": str(target), "created": "false"}
    target.parent.mkdir(parents=True, exist_ok=True)
    _git(root, "worktree", "add", "-b", worktree["branch"], str(target), worktree["base_ref"])
    return {"path": str(target), "created": "true"}


def serial_handoff_evidence(worktree: Path, commit: str, verification: list[dict[str, Any]], delivery_program_id: str) -> dict[str, Any]:
    """Capture the local facts required before another fresh context reuses it."""

    root = worktree.resolve()
    resolved_commit = _git(root, "rev-parse", f"{commit}^{{commit}}")
    head = _git(root, "rev-parse", "HEAD")
    if head != resolved_commit:
        raise TopologyError("serial handoff commit must equal the clean worktree HEAD")
    if _git(root, "status", "--porcelain=v1"):
        raise TopologyError("serial handoff requires a clean worktree")
    if not verification or any(not isinstance(item, dict) or item.get("exit_code") != 0 for item in verification):
        raise TopologyError("serial handoff requires successful independent verification evidence")
    return {
        "schema_version": "codex-crew.serial-handoff.v0",
        "delivery_program_id": delivery_program_id,
        "worktree": str(root),
        "commit": resolved_commit,
        "verification": verification,
    }


def validate_serial_reuse(worktree: Path, handoff: dict[str, Any], delivery_program_id: str) -> dict[str, Any]:
    """Fail closed unless a new work package can safely reuse a serial tree."""

    required = {"schema_version", "delivery_program_id", "worktree", "commit", "verification"}
    if not isinstance(handoff, dict) or set(handoff) != required or handoff.get("schema_version") != "codex-crew.serial-handoff.v0":
        raise TopologyError("serial reuse handoff is malformed")
    root = worktree.resolve()
    if handoff["delivery_program_id"] != delivery_program_id or Path(handoff["worktree"]).resolve() != root:
        raise TopologyError("serial reuse handoff belongs to a different delivery program or worktree")
    if _git(root, "status", "--porcelain=v1"):
        raise TopologyError("serial reuse requires a clean worktree")
    previous = _git(root, "rev-parse", f"{handoff['commit']}^{{commit}}")
    _git(root, "merge-base", "--is-ancestor", previous, "HEAD")
    if not isinstance(handoff["verification"], list) or not handoff["verification"] or any(not isinstance(item, dict) or item.get("exit_code") != 0 for item in handoff["verification"]):
        raise TopologyError("serial reuse requires prior successful verification evidence")
    return json.loads(json.dumps(handoff))
