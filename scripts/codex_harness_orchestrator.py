#!/usr/bin/env python3
"""Thin Codex Crew orchestration control plane.

This module is deliberately smaller than the legacy parent controller.  It
owns one run snapshot and the hard boundaries around that snapshot; the
Orchestrator agent remains free to choose decomposition, assurance mode,
profiles, topology and Worker-local subagents.  The module never writes
business files on behalf of the Orchestrator.

The existing ``codex_harness_dispatch`` module remains the Worker/worktree
primitive. This module projects assignments onto that primitive and records
only the facts needed to route and accept a run; it does not create a second
child scheduler.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    from codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from codex_harness_controller import git_status, walk_items, walk_root_agent_messages
    from codex_harness_dispatch import assignment_task, continue_assignment, ensure_worktree, run_worker, write_json_atomic
    from codex_harness_policy import load_orchestrator_policy
    from codex_harness_profiles import ExecutionProfileError, load_execution_profiles, resolve_execution_profile, worker_profile_for_mode
    from codex_harness_runtime import LedgerIntegrityError, ResourceLedger
    from codex_harness_topology import TopologyError, serial_handoff_evidence, validate_serial_reuse
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from scripts.codex_harness_controller import git_status, walk_items, walk_root_agent_messages
    from scripts.codex_harness_dispatch import assignment_task, continue_assignment, ensure_worktree, run_worker, write_json_atomic
    from scripts.codex_harness_policy import load_orchestrator_policy
    from scripts.codex_harness_profiles import ExecutionProfileError, load_execution_profiles, resolve_execution_profile, worker_profile_for_mode
    from scripts.codex_harness_runtime import LedgerIntegrityError, ResourceLedger
    from scripts.codex_harness_topology import TopologyError, serial_handoff_evidence, validate_serial_reuse


CONTROL_SCHEMA_VERSION = "codex-crew.control.v0.1"
ORCHESTRATOR_TURN_SCHEMA_VERSION = "codex-crew.orchestrator-turn.v0"
WORKER_RESULT_SCHEMA_VERSION = "codex-crew.worker-result.v0"
ACCEPTANCE_SCHEMA_VERSION = "codex-crew.acceptance.v0"
DEFAULT_MAX_ACTIONS = 32
TOPOLOGIES = {"orchestrator_read_only", "worker_serial", "worker_parallel"}
RUN_STATUSES = {"running", "awaiting_owner", "verifying", "blocked", "succeeded", "failed", "cancelling", "cancelled"}
ASSIGNMENT_KINDS = {"delivery", "verification"}
ASSIGNMENT_STATUSES = {"planned", "ready", "running", "awaiting_orchestrator", "awaiting_owner", "submitted", "verifying", "accepted", "rejected", "failed", "cancelled"}
WORKER_STATUSES = {"succeeded", "needs_orchestrator", "needs_owner", "failed"}
OWNER_CATEGORIES = {"scope_change", "authority_expansion", "irreversible_external_side_effect", "acceptance_ambiguity"}
ACTIONS = {"dispatch", "control", "ask_owner", "finish"}
CONTROL_OPERATIONS = {"continue", "accept", "cancel"}


class OrchestratorError(RuntimeError):
    """Base error for a malformed run or an unsafe control-plane operation."""


class ControllerBusy(OrchestratorError):
    """Another process currently owns the run controller lock."""


class FullVerificationRequired(OrchestratorError):
    """A Full assignment cannot be accepted without an independent verifier."""


def _now() -> float:
    return time.time()


def _event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    state.setdefault("events", []).append({"at": _now(), "kind": kind, **fields})


def _active_workspace_paths(state: dict[str, Any], assignment_id: str | None = None) -> list[str]:
    paths = []
    for assignment in state.get("assignments", []):
        if assignment_id is not None and assignment.get("assignment_id") != assignment_id:
            continue
        workspace = assignment.get("workspace")
        if isinstance(workspace, dict) and isinstance(workspace.get("path"), str) and workspace["path"].strip():
            paths.append(str(Path(workspace["path"]).resolve()))
    return sorted(set(paths))


def _ledger_event(state: dict[str, Any], resource_type: str, resource_id: str, operation: str, evidence: str, **fields: Any) -> None:
    """Append resource evidence through the existing runtime ledger seam."""

    try:
        ledger = ResourceLedger(Path(state["artifact_root"]) / "resource-ledger.jsonl", state["run_id"])
        ledger.append(resource_type, resource_id, operation, evidence, **fields)
    except (LedgerIntegrityError, OSError, ValueError) as error:
        state["status"] = "blocked"
        state["quarantine"] = {"reason": "resource_ledger_integrity", "detail": str(error), "at": _now()}
        raise OrchestratorError(f"resource ledger rejected an event: {error}") from error


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def _git(root: Path, *args: str, check: bool = True) -> str:
    completed = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if check and completed.returncode:
        raise OrchestratorError(completed.stderr.strip() or f"git {' '.join(args)} failed")
    return completed.stdout.strip()


def _normal_path(value: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise OrchestratorError("path must be a string")
    candidate = value.replace("\\", "/").strip()
    if not candidate:
        if allow_empty:
            return ""
        raise OrchestratorError("path must not be empty")
    path = Path(candidate)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise OrchestratorError(f"path must be a normalized repository-relative path: {value!r}")
    return "/".join(path.parts)


def _path_owned(path: str, allowed: list[str]) -> bool:
    normalized = _normal_path(path)
    return any(normalized == root or normalized.startswith(root + "/") for root in allowed)


def git_changed_paths(worktree: Path) -> list[str]:
    """Return staged, unstaged and untracked paths as normalized relative names."""

    raw = _git(worktree, "status", "--porcelain=v1")
    paths: list[str] = []
    for line in raw.splitlines():
        if not line:
            continue
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        try:
            paths.append(_normal_path(value))
        except OrchestratorError:
            paths.append(value.replace("\\", "/"))
    return sorted(set(paths))


def git_committed_paths(worktree: Path, base_ref: str) -> list[str]:
    """Return paths changed by committed Worker work since ``base_ref``."""

    raw = _git(worktree, "diff", "--name-only", f"{base_ref}...HEAD")
    values: list[str] = []
    for line in raw.splitlines():
        if line.strip():
            values.append(_normal_path(line.strip()))
    return sorted(set(values))


def validate_worker_diff(assignment: dict[str, Any], changed_paths: list[str]) -> list[str]:
    """Reject any Worker change outside the assignment's declared ownership."""

    allowed = [_normal_path(item) for item in assignment.get("allowed_paths", [])]
    if assignment.get("kind") == "delivery" and not allowed:
        raise OrchestratorError("delivery assignments must declare at least one allowed path")
    normalized = []
    for path in changed_paths:
        normalized_path = _normal_path(path)
        normalized.append(normalized_path)
        if not _path_owned(normalized_path, allowed):
            raise OrchestratorError(f"worker changed a path outside assignment ownership: {path}")
    return sorted(set(normalized))


class ControllerLock:
    """Small process-level single-writer lock for one run snapshot.

    A stale lock is never silently reclaimed.  The explicit ``recover`` path
    is the only operation allowed to quarantine a lock after an owner checks
    that the old controller is no longer active.
    """

    def __init__(self, path: Path, run_id: str) -> None:
        self.path = path
        self.run_id = run_id
        self.token = uuid.uuid4().hex
        self.acquired = False

    def acquire(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"schema_version": "codex-crew.controller-lock.v0", "run_id": self.run_id, "pid": os.getpid(), "token": self.token, "acquired_at": _now()}
        try:
            with self.path.open("x", encoding="utf-8", newline="\n") as stream:
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
        except FileExistsError as error:
            raise ControllerBusy(f"controller lock already exists: {self.path}") from error
        self.acquired = True
        return payload

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            current = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            self.acquired = False
            return
        if isinstance(current, dict) and current.get("token") == self.token:
            self.path.unlink(missing_ok=True)
        self.acquired = False

    def __enter__(self) -> "ControllerLock":
        self.acquire()
        return self

    def __exit__(self, _exc_type: object, _exc_value: object, _traceback: object) -> None:
        self.release()


@contextmanager
def controller_lock(state: dict[str, Any]) -> Iterator[ControllerLock]:
    path = Path(state["controller"]["lock_path"])
    lock = ControllerLock(path, state["run_id"])
    with lock:
        yield lock


def _profile_for_assignment(state: dict[str, Any], assignment: dict[str, Any]) -> dict[str, str]:
    try:
        bundle = load_execution_profiles(Path(__file__).resolve().parents[1])
        profile = resolve_execution_profile(bundle, assignment["execution_profile"], "worker")
    except (ExecutionProfileError, KeyError) as error:
        raise OrchestratorError(f"assignment execution profile is invalid: {error}") from error
    expected = worker_profile_for_mode(bundle, assignment["assurance_mode"])
    if profile["id"] != expected["id"]:
        raise OrchestratorError(f"{assignment['assurance_mode']} assignment must use canonical profile {expected['id']}")
    return profile


def _empty_execution() -> dict[str, Any]:
    return {"topology": "orchestrator_read_only", "max_active_write_worktrees": 0, "workspace_reuse_policy": "none", "parallelism_rationale": None}


def _empty_turn_observation() -> dict[str, Any]:
    return {
        "turn_id": None,
        "started_at": None,
        "phase": "not_started",
        "completion": {"status": "not_started", "source": "none", "observed_at": None, "valid_envelope": False},
        "terminal": {"observed": False, "status": "not_observed", "observed_at": None, "source": "none", "valid_envelope": False},
        "interrupt": {"attempted": False, "acknowledged": False, "requested_at": None, "acknowledged_at": None, "error": None},
        "notification_summary": {"observed_count": 0, "methods": []},
    }


def _empty_git_boundary() -> dict[str, Any]:
    return {"observed_at": None, "availability": "unavailable", "is_clean": None, "porcelain": None, "error": None}


def _git_boundary(repository_root: Path) -> dict[str, Any]:
    try:
        porcelain = git_status(repository_root)
    except BaseException as error:
        return {"observed_at": _now(), "availability": "unavailable", "is_clean": None, "porcelain": None, "error": str(error)}
    return {"observed_at": _now(), "availability": "observed", "is_clean": not bool(porcelain), "porcelain": porcelain, "error": None}


def _notification_summary(notifications: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for item in notifications:
        method = item.get("method")
        if isinstance(method, str) and method:
            counts[method] = counts.get(method, 0) + 1
    return {"observed_count": len(notifications), "methods": [{"method": method, "count": count} for method, count in sorted(counts.items())]}


def _terminal_status(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip().lower()
    if candidate in {"completed", "succeeded", "success"}:
        return "completed"
    if candidate in {"failed", "error"}:
        return "failed"
    if candidate in {"interrupted", "interrupt"}:
        return "interrupted"
    if candidate in {"cancelled", "canceled"}:
        return "cancelled"
    return None


def _terminal_from_notifications(notifications: list[dict[str, Any]], thread_id: str) -> str | None:
    for item in reversed(notifications):
        if item.get("method") != "turn/completed":
            continue
        params = item.get("params")
        if not isinstance(params, dict) or params.get("threadId") != thread_id:
            continue
        nested = params.get("turn")
        status = _terminal_status(params.get("status")) or (_terminal_status(nested.get("status")) if isinstance(nested, dict) else None)
        return status or "completed"
    return None


def _terminal_from_history(history: Any, turn_id: str | None) -> str | None:
    if not turn_id:
        return None
    if isinstance(history, dict):
        identifiers = {history.get("id"), history.get("turnId")}
        nested_turn = history.get("turn")
        if isinstance(nested_turn, dict):
            identifiers.update({nested_turn.get("id"), nested_turn.get("turnId")})
        if turn_id in identifiers:
            status = _terminal_status(history.get("status"))
            if status is None and isinstance(nested_turn, dict):
                status = _terminal_status(nested_turn.get("status"))
            if status is not None:
                return status
        for nested in history.values():
            status = _terminal_from_history(nested, turn_id)
            if status is not None:
                return status
    elif isinstance(history, list):
        for nested in history:
            status = _terminal_from_history(nested, turn_id)
            if status is not None:
                return status
    return None


def _record_notifications(state: dict[str, Any], notifications: list[dict[str, Any]]) -> None:
    state["orchestrator"]["turn"]["notification_summary"] = _notification_summary(notifications)


def _record_terminal(state: dict[str, Any], status: str, source: str) -> None:
    turn = state["orchestrator"]["turn"]
    observed_at = _now()
    turn["terminal"] = {"observed": True, "status": status, "observed_at": observed_at, "source": source, "valid_envelope": False}
    turn["completion"] = {"status": "completed", "source": source, "observed_at": observed_at, "valid_envelope": False}
    turn["phase"] = "terminal_observed"


def _record_boundary(state: dict[str, Any], key: str, boundary: dict[str, Any]) -> None:
    state["orchestrator"]["boundary_evidence"][key] = boundary


def _mark_blocked(state: dict[str, Any], reason: str, detail: str) -> None:
    state["status"] = "blocked"
    state["quarantine"] = {"reason": reason, "detail": detail, "at": _now(), "workspaces": _active_workspace_paths(state)}
    _event(state, "orchestrator_turn_blocked", reason=reason)


def _thin_policy_identity() -> dict[str, Any]:
    try:
        return load_orchestrator_policy(Path(__file__).resolve().parents[1])["identity"]
    except Exception as error:
        raise OrchestratorError(f"thin-control runtime policy is unavailable: {error}") from error


def new_snapshot(repository_root: Path, issue: str, state_path: Path, *, run_id: str | None = None, orchestrator_profile: str = "parent-sol-high", artifact_root: Path | None = None, max_actions: int = DEFAULT_MAX_ACTIONS) -> dict[str, Any]:
    root = repository_root.resolve()
    if not issue or not issue.strip():
        raise OrchestratorError("issue must not be empty")
    if max_actions < 1:
        raise OrchestratorError("max_actions must be positive")
    resolved_run = run_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in resolved_run):
        raise OrchestratorError("run_id may contain only letters, digits, dash, underscore and dot")
    artifacts = (artifact_root or Path(tempfile.gettempdir()) / "codex-harness-runs" / "crew-orchestrator" / resolved_run).resolve()
    try:
        policy = load_orchestrator_policy(Path(__file__).resolve().parents[1])
    except Exception as error:
        raise OrchestratorError(f"thin-control runtime policy validation failed: {error}") from error
    configured_max_actions = policy["policy"]["actions"]["max_actions_per_run"]
    if max_actions == DEFAULT_MAX_ACTIONS:
        max_actions = configured_max_actions
    if max_actions > configured_max_actions:
        raise OrchestratorError("max_actions cannot exceed the canonical thin-control policy bound")
    snapshot = {
        "$schema": "./codex-crew.control.v0.1.schema.json",
        "schema_version": CONTROL_SCHEMA_VERSION,
        "run_id": resolved_run,
        "repository_root": str(root),
        "artifact_root": str(artifacts),
        "state_path": str(state_path.resolve()),
        "issue": issue.strip(),
        "status": "running",
        "action_count": 0,
        "max_actions": max_actions,
        "policy_identity": policy["identity"],
        "orchestrator": {
            "thread_id": None,
            "sandbox": "read-only",
            "approval_policy": "never",
            "context_fresh": True,
            "requested_execution": {"profile": orchestrator_profile, "model": None, "reasoning_effort": None, "sandbox": "read-only", "approval_policy": "never", "network_access": False},
            "turn": _empty_turn_observation(),
            "boundary_evidence": {"pre_git": _empty_git_boundary(), "post_git": _empty_git_boundary()},
        },
        "execution": _empty_execution(),
        "assignments": [],
        "owner_requests": [],
        "messages": [],
        "acceptances": [],
        "events": [{"at": _now(), "kind": "run_initialized"}],
        "last_message": "",
        "quarantine": None,
        "controller": {"lock_path": str(state_path.resolve().with_suffix(".controller.lock"))},
    }
    validate_snapshot(snapshot)
    return snapshot


def _validate_assignment(assignment: dict[str, Any], repository_root: Path) -> None:
    required = {"run_id", "assignment_id", "kind", "revision", "goal", "non_goals", "assurance_mode", "execution_profile", "allowed_paths", "external_resources", "verification_commands", "depends_on", "context", "status", "workspace", "worker", "result", "acceptance"}
    if not isinstance(assignment, dict) or required - set(assignment):
        raise OrchestratorError("assignment is missing required fields")
    if not isinstance(assignment["run_id"], str) or not assignment["run_id"].strip() or assignment["kind"] not in ASSIGNMENT_KINDS or not isinstance(assignment["assignment_id"], str) or not assignment["assignment_id"].strip() or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in assignment["assignment_id"]) or not isinstance(assignment["revision"], int) or isinstance(assignment["revision"], bool) or assignment["revision"] < 1:
        raise OrchestratorError("assignment identity or kind is malformed")
    if not isinstance(assignment["goal"], str) or not assignment["goal"].strip() or not isinstance(assignment["non_goals"], list) or any(not isinstance(item, str) for item in assignment["non_goals"]):
        raise OrchestratorError("assignment goal/non_goals are malformed")
    if assignment["assurance_mode"] not in {"lite", "full"} or not isinstance(assignment["execution_profile"], str) or not assignment["execution_profile"].strip():
        raise OrchestratorError("assignment assurance/profile is malformed")
    allowed = assignment["allowed_paths"]
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise OrchestratorError("assignment allowed_paths are malformed")
    normalized_allowed = [_normal_path(item) for item in allowed]
    if assignment["kind"] == "delivery" and not normalized_allowed:
        raise OrchestratorError("delivery assignments must declare at least one allowed path")
    if len(normalized_allowed) != len(set(normalized_allowed)):
        raise OrchestratorError("assignment allowed_paths must be unique")
    resources = assignment["external_resources"]
    if not isinstance(resources, list) or any(not isinstance(item, str) or not item.strip() for item in resources):
        raise OrchestratorError("assignment external_resources are malformed")
    commands = assignment["verification_commands"]
    if not isinstance(commands, list) or any(not isinstance(item, str) or not item.strip() for item in commands):
        raise OrchestratorError("assignment verification_commands are malformed")
    dependencies = assignment["depends_on"]
    if not isinstance(dependencies, list) or any(not isinstance(item, str) or not item.strip() for item in dependencies) or assignment["assignment_id"] in dependencies:
        raise OrchestratorError("assignment dependencies are malformed")
    context = assignment["context"]
    if not isinstance(context, dict) or set(context) != {"fresh", "continuation_allowed"} or not isinstance(context["fresh"], bool) or not isinstance(context["continuation_allowed"], bool):
        raise OrchestratorError("assignment context policy is malformed")
    if assignment["status"] not in ASSIGNMENT_STATUSES:
        raise OrchestratorError("unsupported assignment status")
    workspace = assignment["workspace"]
    if workspace is not None:
        if not isinstance(workspace, dict) or set(workspace) not in ({"path", "branch", "base_ref"}, {"path", "branch", "base_ref", "handoff"}) or any(not isinstance(workspace.get(key), str) or not workspace[key].strip() for key in ("path", "branch", "base_ref")):
            raise OrchestratorError("assignment workspace is malformed")
        resolved_workspace = Path(workspace["path"]).resolve()
        if resolved_workspace == repository_root.resolve() or repository_root.parent.resolve() not in resolved_workspace.parents:
            raise OrchestratorError("worker worktree must be a sibling/descendant of the controller repository")
    worker = assignment["worker"]
    if not isinstance(worker, dict) or set(worker) != {"thread_id", "status"} or (worker["thread_id"] is not None and (not isinstance(worker["thread_id"], str) or not worker["thread_id"].strip())) or worker["status"] not in {"pending", "running", "stopped"}:
        raise OrchestratorError("assignment worker binding is malformed")
    if assignment["result"] is not None and not isinstance(assignment["result"], dict):
        raise OrchestratorError("assignment result must be null or an object")
    if assignment["acceptance"] is not None and not isinstance(assignment["acceptance"], dict):
        raise OrchestratorError("assignment acceptance must be null or an object")
    _profile_for_assignment({"repository_root": str(repository_root)}, assignment)


def validate_snapshot(state: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "repository_root", "artifact_root", "state_path", "issue", "status", "action_count", "max_actions", "policy_identity", "orchestrator", "execution", "assignments", "owner_requests", "messages", "acceptances", "events", "last_message", "quarantine", "controller"}
    if not isinstance(state, dict) or state.get("schema_version") != CONTROL_SCHEMA_VERSION or required - set(state):
        raise OrchestratorError("unsupported or incomplete Orchestrator snapshot")
    if any(not isinstance(state.get(key), str) or not state[key].strip() for key in ("run_id", "repository_root", "artifact_root", "state_path", "issue")) or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in state["run_id"]) or state["status"] not in RUN_STATUSES:
        raise OrchestratorError("snapshot identity or status is malformed")
    if not isinstance(state["action_count"], int) or isinstance(state["action_count"], bool) or not isinstance(state["max_actions"], int) or isinstance(state["max_actions"], bool) or state["action_count"] < 0 or state["action_count"] > state["max_actions"]:
        raise OrchestratorError("snapshot action budget is malformed")
    policy_identity = state["policy_identity"]
    if not isinstance(policy_identity, dict) or policy_identity.get("schema_version") != "codex-harness.runtime-policy.v1" or any(not isinstance(policy_identity.get(key), str) or not policy_identity[key].strip() for key in ("policy_path", "schema_path", "policy_sha256", "schema_sha256", "maturity")):
        raise OrchestratorError("snapshot is missing the canonical thin-control policy identity")
    if policy_identity != _thin_policy_identity():
        raise OrchestratorError("snapshot policy identity does not match the current canonical thin-control policy")
    orchestrator = state["orchestrator"]
    required_orchestrator = {"thread_id", "sandbox", "approval_policy", "context_fresh", "requested_execution", "turn", "boundary_evidence"}
    if not isinstance(orchestrator, dict) or set(orchestrator) != required_orchestrator or (orchestrator["thread_id"] is not None and not isinstance(orchestrator["thread_id"], str)) or orchestrator["sandbox"] != "read-only" or orchestrator["approval_policy"] != "never" or orchestrator["context_fresh"] is not True:
        raise OrchestratorError("Orchestrator must be an explicit read-only controller")
    requested_execution = orchestrator["requested_execution"]
    if not isinstance(requested_execution, dict) or set(requested_execution) != {"profile", "model", "reasoning_effort", "sandbox", "approval_policy", "network_access"} or not isinstance(requested_execution["profile"], str) or not requested_execution["profile"].strip() or requested_execution["sandbox"] != "read-only" or requested_execution["approval_policy"] != "never" or requested_execution["network_access"] is not False or any(value is not None and not isinstance(value, str) for value in (requested_execution["model"], requested_execution["reasoning_effort"])):
        raise OrchestratorError("Orchestrator requested execution evidence is malformed")
    turn = orchestrator["turn"]
    if not isinstance(turn, dict) or set(turn) != {"turn_id", "started_at", "phase", "completion", "terminal", "interrupt", "notification_summary"} or (turn["turn_id"] is not None and not isinstance(turn["turn_id"], str)) or (turn["started_at"] is not None and not isinstance(turn["started_at"], (int, float))) or turn["phase"] not in {"not_started", "started", "collecting_completion", "reconciling_history", "interrupt_requested", "interrupt_confirmed", "terminal_observed", "completion_unknown"}:
        raise OrchestratorError("Orchestrator turn observation is malformed")
    completion = turn["completion"]
    if not isinstance(completion, dict) or set(completion) != {"status", "source", "observed_at", "valid_envelope"} or completion["status"] not in {"not_started", "awaiting_terminal", "completed", "timed_out", "unknown_timeout"} or completion["source"] not in {"none", "turn_start_notifications", "notification_collection", "thread_history", "post_interrupt_reconciliation"} or (completion["observed_at"] is not None and not isinstance(completion["observed_at"], (int, float))) or not isinstance(completion["valid_envelope"], bool):
        raise OrchestratorError("Orchestrator completion evidence is malformed")
    terminal = turn["terminal"]
    if not isinstance(terminal, dict) or set(terminal) != {"observed", "status", "observed_at", "source", "valid_envelope"} or not isinstance(terminal["observed"], bool) or terminal["status"] not in {"not_observed", "completed", "failed", "interrupted", "cancelled"} or terminal["source"] not in {"none", "turn_start_notifications", "notification_collection", "thread_history", "post_interrupt_reconciliation"} or (terminal["observed_at"] is not None and not isinstance(terminal["observed_at"], (int, float))) or not isinstance(terminal["valid_envelope"], bool) or (terminal["observed"] is False and (terminal["status"] != "not_observed" or terminal["source"] != "none")):
        raise OrchestratorError("Orchestrator terminal evidence is malformed")
    interrupt = turn["interrupt"]
    if not isinstance(interrupt, dict) or set(interrupt) != {"attempted", "acknowledged", "requested_at", "acknowledged_at", "error"} or not isinstance(interrupt["attempted"], bool) or not isinstance(interrupt["acknowledged"], bool) or (interrupt["requested_at"] is not None and not isinstance(interrupt["requested_at"], (int, float))) or (interrupt["acknowledged_at"] is not None and not isinstance(interrupt["acknowledged_at"], (int, float))) or (interrupt["error"] is not None and not isinstance(interrupt["error"], str)):
        raise OrchestratorError("Orchestrator interrupt evidence is malformed")
    notification_summary = turn["notification_summary"]
    if not isinstance(notification_summary, dict) or set(notification_summary) != {"observed_count", "methods"} or not isinstance(notification_summary["observed_count"], int) or isinstance(notification_summary["observed_count"], bool) or notification_summary["observed_count"] < 0 or not isinstance(notification_summary["methods"], list) or any(not isinstance(item, dict) or set(item) != {"method", "count"} or not isinstance(item["method"], str) or not item["method"] or not isinstance(item["count"], int) or isinstance(item["count"], bool) or item["count"] < 1 for item in notification_summary["methods"]):
        raise OrchestratorError("Orchestrator notification summary is malformed")
    boundary_evidence = orchestrator["boundary_evidence"]
    if not isinstance(boundary_evidence, dict) or set(boundary_evidence) != {"pre_git", "post_git"}:
        raise OrchestratorError("Orchestrator boundary evidence is malformed")
    for boundary in boundary_evidence.values():
        if not isinstance(boundary, dict) or set(boundary) != {"observed_at", "availability", "is_clean", "porcelain", "error"} or boundary["availability"] not in {"observed", "unavailable"} or (boundary["observed_at"] is not None and not isinstance(boundary["observed_at"], (int, float))) or (boundary["is_clean"] is not None and not isinstance(boundary["is_clean"], bool)) or (boundary["porcelain"] is not None and not isinstance(boundary["porcelain"], str)) or (boundary["error"] is not None and not isinstance(boundary["error"], str)):
            raise OrchestratorError("Orchestrator git boundary evidence is malformed")
    execution = state["execution"]
    if not isinstance(execution, dict) or set(execution) != {"topology", "max_active_write_worktrees", "workspace_reuse_policy", "parallelism_rationale"} or execution["topology"] not in TOPOLOGIES or not isinstance(execution["max_active_write_worktrees"], int) or isinstance(execution["max_active_write_worktrees"], bool) or execution["max_active_write_worktrees"] < 0:
        raise OrchestratorError("snapshot execution topology is malformed")
    if not isinstance(execution["workspace_reuse_policy"], str) or not execution["workspace_reuse_policy"].strip() or (execution["parallelism_rationale"] is not None and (not isinstance(execution["parallelism_rationale"], str) or not execution["parallelism_rationale"].strip())):
        raise OrchestratorError("snapshot execution rationale is malformed")
    expected_max = {"orchestrator_read_only": 0, "worker_serial": 1, "worker_parallel": None}[execution["topology"]]
    if expected_max is not None and execution["max_active_write_worktrees"] != expected_max:
        raise OrchestratorError(f"{execution['topology']} has an invalid active write-worktree bound")
    if execution["topology"] == "worker_parallel" and execution["max_active_write_worktrees"] < 2:
        raise OrchestratorError("worker_parallel requires at least two active write worktrees")
    assignments = state["assignments"]
    if not isinstance(assignments, list):
        raise OrchestratorError("snapshot assignments must be an array")
    known = {item.get("assignment_id") for item in assignments if isinstance(item, dict)}
    if len(known) != len(assignments):
        raise OrchestratorError("assignment ids must be unique")
    root = Path(state["repository_root"]).resolve()
    for assignment in assignments:
        # Assignment builders may be used before a run is known.  Binding is
        # completed exactly once at the run boundary; after that, a mismatch
        # is rejected rather than silently moved between runs.
        if "run_id" not in assignment:
            assignment["run_id"] = state["run_id"]
        if assignment.get("run_id") != state["run_id"]:
            raise OrchestratorError(f"assignment {assignment.get('assignment_id')} is bound to a different run")
        _validate_assignment(assignment, root)
        if set(assignment["depends_on"]) - known:
            raise OrchestratorError(f"assignment {assignment['assignment_id']} references an unknown dependency")
    visiting: set[str] = set()
    visited: set[str] = set()
    by_id = {item["assignment_id"]: item for item in assignments}

    def visit(assignment_id: str) -> None:
        if assignment_id in visiting:
            raise OrchestratorError("assignment dependency graph contains a cycle")
        if assignment_id in visited:
            return
        visiting.add(assignment_id)
        for dependency in by_id[assignment_id]["depends_on"]:
            visit(dependency)
        visiting.remove(assignment_id)
        visited.add(assignment_id)

    for assignment_id in by_id:
        visit(assignment_id)
    for field in ("owner_requests", "messages", "acceptances", "events"):
        if not isinstance(state[field], list):
            raise OrchestratorError(f"snapshot {field} must be an array")
    controller = state["controller"]
    if not isinstance(controller, dict) or set(controller) != {"lock_path"} or not isinstance(controller["lock_path"], str) or not controller["lock_path"].strip():
        raise OrchestratorError("controller lock projection is malformed")


def make_assignment(assignment_id: str, goal: str, *, run_id: str | None = None, assurance_mode: str = "lite", kind: str = "delivery", execution_profile: str | None = None, allowed_paths: list[str] | None = None, non_goals: list[str] | None = None, verification_commands: list[str] | None = None, depends_on: list[str] | None = None, external_resources: list[str] | None = None, revision: int = 1, fresh_context: bool = True) -> dict[str, Any]:
    if assurance_mode not in {"lite", "full"} or kind not in ASSIGNMENT_KINDS:
        raise OrchestratorError("unsupported assignment mode or kind")
    profile = execution_profile or ("worker-full-terra-high" if assurance_mode == "full" else "worker-lite-luna-max")
    assignment = {
        "run_id": run_id or "unbound",
        "assignment_id": assignment_id,
        "kind": kind,
        "revision": revision,
        "goal": goal,
        "non_goals": list(non_goals or []),
        "assurance_mode": assurance_mode,
        "execution_profile": profile,
        "allowed_paths": list(allowed_paths or []),
        "external_resources": list(external_resources or []),
        "verification_commands": list(verification_commands or []),
        "depends_on": list(depends_on or []),
        "context": {"fresh": fresh_context, "continuation_allowed": True},
        "status": "planned",
        "workspace": None,
        "worker": {"thread_id": None, "status": "pending"},
        "result": None,
        "acceptance": None,
    }
    if run_id is None:
        assignment.pop("run_id")
    return assignment


def ready_assignment_ids(state: dict[str, Any]) -> list[str]:
    validate_snapshot(state)
    by_id = {item["assignment_id"]: item for item in state["assignments"]}
    return [item["assignment_id"] for item in state["assignments"] if item["status"] in {"planned", "ready"} and all(by_id[dependency]["status"] == "accepted" for dependency in item["depends_on"])]


def _ownership_disjoint(assignments: list[dict[str, Any]]) -> bool:
    paths: list[str] = []
    resources: set[str] = set()
    for assignment in assignments:
        for path in assignment["allowed_paths"]:
            normalized = _normal_path(path)
            if any(normalized == existing or normalized.startswith(existing + "/") or existing.startswith(normalized + "/") for existing in paths):
                return False
            paths.append(normalized)
        overlap = resources & set(assignment["external_resources"])
        if overlap:
            return False
        resources.update(assignment["external_resources"])
    return True


def choose_topology(state: dict[str, Any], requested: str | None = None, *, rationale: str | None = None) -> dict[str, Any]:
    validate_snapshot(state)
    write_assignments = [item for item in state["assignments"] if item["kind"] == "delivery"]
    if requested == "orchestrator_read_only" or (requested is None and not write_assignments):
        if write_assignments:
            raise OrchestratorError("orchestrator_read_only cannot carry delivery assignments")
        return {"topology": "orchestrator_read_only", "max_active_write_worktrees": 0, "workspace_reuse_policy": "none", "parallelism_rationale": None}
    if requested == "worker_parallel":
        ready_ids = set(ready_assignment_ids(state))
        ready_writers = [item for item in write_assignments if item["assignment_id"] in ready_ids]
        if len(ready_writers) < 2 or not _ownership_disjoint(ready_writers) or not rationale or not rationale.strip():
            raise OrchestratorError("worker_parallel requires at least two ready, disjoint delivery assignments and an explicit rationale")
        return {"topology": "worker_parallel", "max_active_write_worktrees": len(ready_writers), "workspace_reuse_policy": "distinct_disjoint_worktrees", "parallelism_rationale": rationale.strip()}
    if requested not in {None, "worker_serial"}:
        raise OrchestratorError(f"unsupported execution topology: {requested}")
    return {"topology": "worker_serial", "max_active_write_worktrees": 1, "workspace_reuse_policy": "same_run_serial_reuse_after_acceptance", "parallelism_rationale": None}


def apply_topology(state: dict[str, Any], requested: str | None = None, *, rationale: str | None = None) -> dict[str, Any]:
    selected = choose_topology(state, requested, rationale=rationale)
    state["execution"] = selected
    _event(state, "topology_selected", **selected)
    return selected


def materialize_workspaces(state: dict[str, Any], assignment_ids: list[str] | None = None) -> list[dict[str, str]]:
    """Create worktrees only for currently ready assignments."""

    validate_snapshot(state)
    topology = state["execution"]["topology"]
    if topology == "orchestrator_read_only":
        raise OrchestratorError("read-only runs cannot materialize Worker worktrees")
    ready = ready_assignment_ids(state)
    selected = assignment_ids or ready
    if len(set(selected)) != len(selected) or any(item not in ready for item in selected):
        raise OrchestratorError("only ready assignments may receive a worktree")
    if topology == "worker_serial" and len(selected) > 1:
        raise OrchestratorError("worker_serial permits one active write assignment")
    selected_assignments = [next(item for item in state["assignments"] if item["assignment_id"] == assignment_id) for assignment_id in selected]
    if any(item["kind"] != "delivery" for item in selected_assignments):
        raise OrchestratorError("verification assignments do not receive write worktrees")
    if topology == "worker_parallel" and (not selected_assignments or len(selected_assignments) > state["execution"]["max_active_write_worktrees"] or not _ownership_disjoint(selected_assignments)):
        raise OrchestratorError("worker_parallel selection violates active worktree or ownership bounds")
    root = Path(state["repository_root"])
    results: list[dict[str, str]] = []
    for assignment in selected_assignments:
        serial_reuse = False
        if assignment["workspace"] is None:
            base = root.parent / ".codex-crew-worktrees" / state["run_id"]
            suffix = "serial" if topology == "worker_serial" else assignment["assignment_id"]
            assignment["workspace"] = {"path": str((base / suffix).resolve()), "branch": f"codex/crew/{state['run_id']}/{suffix}", "base_ref": "HEAD"}
        workspace = assignment["workspace"]
        assert workspace is not None
        if topology == "worker_serial" and Path(workspace["path"]).exists():
            previous = [item for item in state["assignments"] if item["assignment_id"] != assignment["assignment_id"] and item["status"] == "accepted" and item.get("acceptance", {}).get("handoff", {}).get("worktree") == str(Path(workspace["path"]).resolve())]
            if not previous:
                raise OrchestratorError("serial worktree exists without an accepted handoff from this run")
            handoff = previous[-1]["acceptance"].get("handoff")
            try:
                validate_serial_reuse(Path(workspace["path"]), handoff, state["run_id"])
            except TopologyError as error:
                raise OrchestratorError(f"serial worktree reuse gate failed: {error}") from error
            serial_reuse = True
        ready_result = ensure_worktree(root, workspace)
        workspace["path"] = ready_result["path"]
        workspace["base_ref"] = _git(Path(workspace["path"]), "rev-parse", "HEAD")
        assignment["status"] = "ready"
        _event(state, "workspace_ready", assignment_id=assignment["assignment_id"], serial_reuse=serial_reuse, **ready_result)
        _ledger_event(state, "worktree", assignment["assignment_id"], "acquire", "ready assignment workspace", path=workspace["path"], topology=topology)
        results.append({"assignment_id": assignment["assignment_id"], **ready_result})
    validate_snapshot(state)
    return results


def dispatch_worker(state: dict[str, Any], assignment_id: str, *, timeout_seconds: int = 900, worker_runner: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run one ready Worker through the existing dispatch primitive.

    The Orchestrator selects the assignment and topology; ``run_worker`` still
    owns the App Server/Worker thread primitive.  Tests and alternate callers
    can inject a runner with the same small signature.
    """

    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None:
        raise OrchestratorError(f"unknown assignment: {assignment_id}")
    if assignment["status"] in {"accepted", "cancelled"}:
        raise OrchestratorError("terminal assignment cannot accept a late Worker result")
    if assignment_id not in ready_assignment_ids(state):
        raise OrchestratorError("only a ready assignment may be dispatched")
    if assignment["kind"] != "delivery":
        raise OrchestratorError("verification assignments use the one-shot verifier interface")
    active = [item for item in state["assignments"] if item["status"] == "running"]
    if state["execution"]["topology"] == "worker_serial" and active:
        raise OrchestratorError("worker_serial already has an active Worker")
    if len(active) >= state["execution"]["max_active_write_worktrees"]:
        raise OrchestratorError("active Worker count exceeds the selected topology bound")
    if assignment["workspace"] is None:
        materialize_workspaces(state, [assignment_id])
    workspace = assignment["workspace"]
    if workspace is None:
        raise OrchestratorError("Worker dispatch requires a materialized workspace")
    execution = _profile_for_assignment(state, assignment)
    task = assignment_task(assignment, execution)
    assignment["status"] = "running"
    assignment["worker"]["status"] = "running"
    runner = worker_runner
    try:
        if runner is not None:
            raw_result = runner(assignment_id, task, timeout_seconds)
        elif assignment["worker"].get("thread_id"):
            raw_result = continue_assignment(
                task,
                assignment["worker"]["thread_id"],
                "Continue this same assignment after the Orchestrator update. Preserve the existing scope, ownership and acceptance contract, then return the structured Worker result.",
                timeout_seconds,
            )
        else:
            raw_result = run_worker(assignment_id, task, timeout_seconds)
    except BaseException as error:
        raw_result = {"status": "failed", "summary": "Worker dispatch failed before a structured result", "error": str(error), "changed_paths": []}
    if not isinstance(raw_result, dict):
        raw_result = {"status": "failed", "summary": "Worker dispatch returned a non-object result", "changed_paths": []}
    if raw_result.get("commit") is None and Path(workspace["path"]).is_dir():
        raw_result["commit"] = _git(Path(workspace["path"]), "rev-parse", "HEAD")
    return record_worker_result(state, assignment_id, raw_result)


def dispatch_ready_workers(state: dict[str, Any], *, timeout_seconds: int = 900, worker_runner: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Materialize and run only the currently ready delivery assignments.

    The Orchestrator chooses the cohort; this helper merely applies the
    selected topology.  It never creates workspaces for blocked downstream
    assignments and does not invent a worker task for read-only or serial
    parent execution.
    """

    validate_snapshot(state)
    if state["execution"]["topology"] == "orchestrator_read_only":
        return []
    ready = [item for item in ready_assignment_ids(state) if next(assignment for assignment in state["assignments"] if assignment["assignment_id"] == item)["kind"] == "delivery"]
    if not ready:
        return []
    if state["execution"]["topology"] == "worker_serial":
        selected = ready[:1]
    else:
        selected = ready[: state["execution"]["max_active_write_worktrees"]]
    materialize_workspaces(state, selected)
    # The thin controller does not become a child scheduler.  It materializes
    # the ready cohort and invokes the reusable primitive in a deterministic
    # order; callers that need true concurrent turns can use the dispatcher
    # primitive directly under its declared ownership bound.
    return [dispatch_worker(state, assignment_id, timeout_seconds=timeout_seconds, worker_runner=worker_runner) for assignment_id in selected]


def _normalize_worker_result(raw: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    status = raw.get("status")
    if status == "needs_parent":
        status = "needs_orchestrator"
    if status not in WORKER_STATUSES:
        status = "failed"
    verification = raw.get("verification", [])
    if not isinstance(verification, list):
        verification = []
    changed = raw.get("changed_paths", [])
    if not isinstance(changed, list):
        changed = []
    return {
        "schema_version": WORKER_RESULT_SCHEMA_VERSION,
        "assignment_id": assignment["assignment_id"],
        "revision": assignment["revision"],
        "status": status,
        "summary": raw.get("summary") if isinstance(raw.get("summary"), str) else "Worker returned no summary",
        "commit": raw.get("commit") if isinstance(raw.get("commit"), str) else None,
        "artifacts": raw.get("artifacts") if isinstance(raw.get("artifacts"), list) else [],
        "verification": verification,
        "changed_paths": changed,
        "owner_request": raw.get("owner_request"),
        "subagent_telemetry": raw.get("subagent_telemetry") if isinstance(raw.get("subagent_telemetry"), dict) else {"delegated": False, "active_count": 0},
        "worker_thread_id": raw.get("worker_thread_id"),
    }


def record_worker_result(state: dict[str, Any], assignment_id: str, raw_result: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None:
        raise OrchestratorError(f"unknown assignment: {assignment_id}")
    if raw_result.get("assignment_id") not in {None, assignment_id} or raw_result.get("revision") not in {None, assignment["revision"]}:
        raise OrchestratorError("Worker result is bound to a different assignment revision")
    enriched_result = dict(raw_result)
    if "changed_paths" not in enriched_result and assignment.get("workspace") is not None:
        workspace = assignment["workspace"]
        assert workspace is not None
        try:
            enriched_result["changed_paths"] = git_committed_paths(Path(workspace["path"]), workspace["base_ref"])
        except OrchestratorError:
            enriched_result["changed_paths"] = git_changed_paths(Path(workspace["path"]))
    result = _normalize_worker_result(enriched_result, assignment)
    if result["status"] == "needs_owner":
        request = result.get("owner_request")
        if not isinstance(request, dict) or request.get("category") not in OWNER_CATEGORIES or not isinstance(request.get("detail"), str) or not request["detail"].strip():
            raise OrchestratorError("needs_owner requires a structured owner request")
    changed = validate_worker_diff(assignment, result["changed_paths"])
    result["changed_paths"] = changed
    assignment["result"] = result
    assignment["worker"]["thread_id"] = result.get("worker_thread_id") or assignment["worker"].get("thread_id")
    assignment["worker"]["status"] = "stopped" if result["status"] in {"succeeded", "failed"} else "running"
    assignment["status"] = {"succeeded": "submitted", "needs_orchestrator": "awaiting_orchestrator", "needs_owner": "awaiting_owner", "failed": "failed"}[result["status"]]
    state["status"] = "awaiting_owner" if result["status"] == "needs_owner" else ("blocked" if result["status"] == "failed" else "verifying")
    if result["status"] == "needs_owner":
        state["owner_requests"].append({"assignment_id": assignment_id, **result["owner_request"]})
    _event(state, "worker_result_recorded", assignment_id=assignment_id, worker_status=result["status"])
    _ledger_event(state, "assignment", assignment_id, "result_recorded", "structured Worker result accepted by control plane", worker_status=result["status"])
    validate_snapshot(state)
    return result


def _verification_passed(values: list[dict[str, Any]]) -> bool:
    return bool(values) and all(isinstance(item, dict) and item.get("exit_code") == 0 for item in values)


def run_full_verifier(state: dict[str, Any], assignment_id: str, verifier: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run a one-shot, non-recursive verifier abstraction.

    Production wiring may supply a read-only verifier callback.  The callback
    receives the current snapshot and assignment and may only return a verdict;
    it cannot append assignments or mutate canonical state.  Without a
    callback we fail closed instead of claiming Worker self-checks are
    independent.
    """

    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None:
        raise OrchestratorError(f"unknown assignment: {assignment_id}")
    if assignment["assurance_mode"] != "full":
        raise OrchestratorError("independent verifier is only required for Full assignments")
    before_digest = _digest(state)
    if verifier is None:
        return {"schema_version": "codex-crew.verifier-result.v0", "status": "needs_verifier", "independent": False, "summary": "no independent verifier callback was supplied", "verification": []}
    verifier_view = json.loads(json.dumps(state, ensure_ascii=False))
    verifier_assignment = next(item for item in verifier_view["assignments"] if item["assignment_id"] == assignment_id)
    verdict = verifier(verifier_view, verifier_assignment)
    if not isinstance(verdict, dict) or _digest(state) != before_digest:
        raise OrchestratorError("full verifier must return a verdict and must not mutate canonical state")
    if verdict.get("status") not in {"passed", "failed"} or verdict.get("independent") is not True:
        raise OrchestratorError("full verifier verdict must be independent and passed/failed")
    return verdict


def accept_assignment(state: dict[str, Any], assignment_id: str, *, verifier_result: dict[str, Any] | None = None) -> dict[str, Any]:
    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None or assignment.get("result") is None or assignment["result"].get("status") != "succeeded":
        raise OrchestratorError("only a successful submitted assignment can be accepted")
    result = assignment["result"]
    changed = validate_worker_diff(assignment, result.get("changed_paths", []))
    if assignment["kind"] == "delivery":
        if not result.get("commit"):
            raise OrchestratorError("delivery acceptance requires a commit")
        if assignment["workspace"] is None:
            raise OrchestratorError("delivery acceptance requires a Worker workspace")
        workspace = Path(assignment["workspace"]["path"])
        if _git(workspace, "rev-parse", "HEAD") != result["commit"] or git_status(workspace):
            raise OrchestratorError("delivery acceptance requires clean HEAD at the reported commit")
    verification = result.get("verification", [])
    if not _verification_passed(verification):
        raise OrchestratorError("acceptance requires successful verification evidence")
    verifier = None
    if assignment["assurance_mode"] == "full":
        if not isinstance(verifier_result, dict) or verifier_result.get("status") != "passed" or verifier_result.get("independent") is not True:
            raise FullVerificationRequired("Full acceptance requires an independent one-shot verifier")
        verifier = verifier_result
    handoff = None
    if state["execution"]["topology"] == "worker_serial" and assignment["kind"] == "delivery":
        try:
            handoff = serial_handoff_evidence(Path(assignment["workspace"]["path"]), result["commit"], verification, state["run_id"])
        except TopologyError as error:
            raise OrchestratorError(f"serial promotion boundary failed: {error}") from error
    acceptance = {"schema_version": ACCEPTANCE_SCHEMA_VERSION, "assignment_id": assignment_id, "revision": assignment["revision"], "worker_result_digest": _digest(result), "commit": result.get("commit"), "changed_paths": changed, "verification": verification, "verifier": verifier, "handoff": handoff, "disposition": "accepted", "accepted_at": _now()}
    assignment["acceptance"] = acceptance
    assignment["status"] = "accepted"
    state["acceptances"].append(acceptance)
    state["status"] = "succeeded" if state["assignments"] and all(item["status"] == "accepted" for item in state["assignments"]) else "running"
    _event(state, "assignment_accepted", assignment_id=assignment_id, full=assignment["assurance_mode"] == "full")
    validate_snapshot(state)
    return acceptance


def _parse_json_message(message: str) -> dict[str, Any] | None:
    candidate = message.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def parse_orchestrator_turn(message: str, run_id: str) -> dict[str, Any] | None:
    value = _parse_json_message(message)
    if value is None or value.get("schema_version") != ORCHESTRATOR_TURN_SCHEMA_VERSION or value.get("run_id") != run_id or value.get("action") not in ACTIONS:
        return None
    if not isinstance(value.get("summary", ""), str):
        return None
    if value["action"] == "dispatch" and not isinstance(value.get("assignments"), list):
        return None
    if value["action"] == "control" and value.get("operation") not in CONTROL_OPERATIONS:
        return None
    if value["action"] == "ask_owner":
        request = value.get("owner_request")
        if not isinstance(request, dict) or request.get("category") not in OWNER_CATEGORIES or not isinstance(request.get("detail"), str) or not request["detail"].strip():
            return None
    return value


def apply_orchestrator_turn(state: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    if turn.get("schema_version") != ORCHESTRATOR_TURN_SCHEMA_VERSION or turn.get("run_id") != state["run_id"]:
        raise OrchestratorError("Orchestrator turn is not bound to this run")
    if state["action_count"] >= state["max_actions"]:
        state["status"] = "blocked"
        state["quarantine"] = {"reason": "action_limit_exceeded", "at": _now()}
        try:
            write_json_atomic(Path(state["state_path"]), state)
        except OSError:
            pass
        raise OrchestratorError("Orchestrator action limit exceeded")
    action = turn["action"]
    state["action_count"] += 1
    state["last_message"] = turn.get("summary", "")
    if action == "dispatch":
        additions = turn.get("assignments", [])
        if not additions:
            raise OrchestratorError("dispatch requires at least one assignment")
        had_assignments = bool(state["assignments"])
        existing = {item["assignment_id"] for item in state["assignments"]}
        for assignment in additions:
            if not isinstance(assignment, dict):
                raise OrchestratorError("dispatch assignment must be an object")
            if "schema_version" in assignment:
                assignment = dict(assignment)
                assignment.pop("schema_version", None)
            if assignment.get("assignment_id") in existing:
                raise OrchestratorError("dispatch cannot silently replace an existing assignment")
            assignment.setdefault("run_id", state["run_id"])
            _validate_assignment(assignment, Path(state["repository_root"]))
            state["assignments"].append(assignment)
            existing.add(assignment["assignment_id"])
        requested_topology = turn.get("execution_topology")
        if requested_topology is None and had_assignments:
            requested_topology = state["execution"]["topology"]
        apply_topology(state, requested_topology, rationale=turn.get("parallelism_rationale") or state["execution"].get("parallelism_rationale"))
        for assignment in state["assignments"]:
            if assignment["status"] == "planned" and assignment["assignment_id"] in ready_assignment_ids(state):
                assignment["status"] = "ready"
        if state["quarantine"] is None:
            state["status"] = "running"
        _event(state, "assignments_dispatched", assignment_ids=[item["assignment_id"] for item in additions])
    elif action == "ask_owner":
        request = turn["owner_request"]
        state["owner_requests"].append({"request_id": uuid.uuid4().hex, **request})
        state["status"] = "awaiting_owner"
        _event(state, "owner_requested", category=request["category"])
    elif action == "control":
        operation = turn["operation"]
        assignment_id = turn.get("assignment_id")
        assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None) if assignment_id else None
        if operation in {"continue", "cancel"} and assignment is None:
            raise OrchestratorError("control operation requires an assignment_id")
        if operation == "continue":
            if assignment["status"] not in {"awaiting_orchestrator", "awaiting_owner", "rejected", "ready"}:
                raise OrchestratorError("assignment cannot be continued from its current status")
            assignment["status"] = "ready"
            state["status"] = "running"
        elif operation == "cancel":
            if assignment["worker"]["status"] == "running" or assignment["status"] == "running":
                state["status"] = "blocked"
                state["quarantine"] = {"reason": "cancellation_uncertain", "assignment_id": assignment_id, "workspaces": _active_workspace_paths(state, assignment_id), "at": _now()}
                raise OrchestratorError("assignment cancellation requires a proven Worker stop")
            assignment["status"] = "cancelled"
            assignment["worker"]["status"] = "stopped"
            state["status"] = "cancelled" if all(item["status"] in {"accepted", "cancelled"} for item in state["assignments"]) else "running"
        else:
            if assignment is None:
                raise OrchestratorError("accept control operation requires an assignment_id")
            accept_assignment(state, assignment_id, verifier_result=turn.get("verifier_result"))
    elif action == "finish":
        if state["assignments"] and not all(item["status"] == "accepted" for item in state["assignments"]):
            raise OrchestratorError("Orchestrator cannot finish before every assignment is accepted")
        state["status"] = "succeeded"
        _event(state, "run_finished")
    _event(state, "orchestrator_action", action=action)
    validate_snapshot(state)
    return state


def record_broker_message(state: dict[str, Any], message: str, *, kind: str = "ordinary_correction", provenance: str = "broker") -> dict[str, Any]:
    validate_snapshot(state)
    if not isinstance(message, str) or not message.strip() or not isinstance(provenance, str) or not provenance.strip():
        raise OrchestratorError("broker message must not be empty")
    if kind not in {"ordinary_correction", "owner_decision", "cancel_request"}:
        raise OrchestratorError("unsupported broker message kind")
    state["messages"].append({"message_id": uuid.uuid4().hex, "kind": kind, "provenance": provenance, "body": message, "at": _now()})
    if kind == "owner_decision" and state["status"] == "awaiting_owner":
        state["status"] = "running"
    _event(state, "broker_message_received", message_kind=kind)
    validate_snapshot(state)
    return state["messages"][-1]


def _orchestrator_prompt(state: dict[str, Any], incoming: str = "") -> str:
    return (
        "You are the single Codex Crew Orchestrator. You may inspect the repository and state but must not modify business files. "
        "You control assignment routing and Worker acceptance; Workers own implementation and their own subagents. Choose the minimum topology. "
        f"Run id={state['run_id']}. Issue={state['issue']}. Existing snapshot={json.dumps(state, ensure_ascii=False)}.\n"
        f"Incoming broker message={incoming!r}. Return exactly one JSON object with schema_version={ORCHESTRATOR_TURN_SCHEMA_VERSION!r}, run_id, action(dispatch/control/ask_owner/finish), summary, and action-specific fields."
    )


def _read_orchestrator_history(session: JsonRpcSession, request_id: int, thread_id: str) -> tuple[Any, list[dict[str, Any]], str | None]:
    try:
        history, notifications = session.request(request_id, "thread/read", {"threadId": thread_id, "includeTurns": True}, 30)
    except (RuntimeError, TimeoutError) as error:
        return {}, [], str(error)
    return history, notifications, None


def run_orchestrator_turn(state: dict[str, Any], state_path: Path, *, message: str = "", timeout_seconds: int = 900, resume: bool = True, worker_runner: Callable[[str, dict[str, Any], int], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Drive one read-only Orchestrator turn through the App Server."""

    validate_snapshot(state)
    if timeout_seconds < 1:
        raise OrchestratorError("timeout_seconds must be positive")
    artifact_root = Path(state["artifact_root"])
    artifact_root.mkdir(parents=True, exist_ok=True)
    repository_root = Path(state["repository_root"])
    before = _git_boundary(repository_root)
    _record_boundary(state, "pre_git", before)
    if before["availability"] != "observed":
        _record_boundary(state, "post_git", _git_boundary(repository_root))
        _mark_blocked(state, "pre_turn_git_unknown", str(before["error"] or "could not inspect repository before turn"))
        write_json_atomic(state_path, state)
        raise OrchestratorError("cannot prove the Orchestrator repository boundary before turn start")
    requested = state["orchestrator"]["requested_execution"]
    try:
        profiles = load_execution_profiles(Path(__file__).resolve().parents[1])
        execution = resolve_execution_profile(profiles, requested["profile"], "parent")
    except (ExecutionProfileError, KeyError) as error:
        _record_boundary(state, "post_git", _git_boundary(repository_root))
        _mark_blocked(state, "orchestrator_profile_invalid", str(error))
        write_json_atomic(state_path, state)
        raise OrchestratorError(f"Orchestrator profile is invalid: {error}") from error
    requested["model"] = execution["model"]
    requested["reasoning_effort"] = execution["reasoning_effort"]
    write_json_atomic(state_path, state)
    notifications: list[dict[str, Any]] = []
    history: Any = {}
    history_notifications: list[dict[str, Any]] = []
    raw = ""
    started_turn: dict[str, Any] = {}
    try:
        with JsonRpcSession(app_server_command(approval_policy="never"), artifact_root / "orchestrator.stderr.log") as session:
            session.request(1, "initialize", initialize_params("codex-crew-orchestrator"), 30)
            if resume and state["orchestrator"]["thread_id"]:
                session.request(2, "thread/resume", {"threadId": state["orchestrator"]["thread_id"], "cwd": str(repository_root), "sandbox": "read-only", "approvalPolicy": "never", "model": execution["model"], "config": {"model_reasoning_effort": execution["reasoning_effort"]}}, 30)
            else:
                started, _ = session.request(2, "thread/start", {"cwd": str(repository_root), "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": False, "model": execution["model"], "config": {"model_reasoning_effort": execution["reasoning_effort"]}}, 30)
                state["orchestrator"]["thread_id"] = started["thread"]["id"]
            thread_id = state["orchestrator"]["thread_id"]
            started_turn, start_notifications = session.request(3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": _orchestrator_prompt(state, message)}], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly", "networkAccess": False}}, 30)
            turn_id = started_turn.get("turn", {}).get("id")
            if not isinstance(turn_id, str) or not turn_id:
                _mark_blocked(state, "orchestrator_turn_id_missing", "turn/start did not return a turn id")
                raise OrchestratorError("turn/start did not return a turn id")
            state["orchestrator"]["turn"]["turn_id"] = turn_id
            state["orchestrator"]["turn"]["started_at"] = _now()
            state["orchestrator"]["turn"]["phase"] = "started"
            state["orchestrator"]["turn"]["completion"] = {"status": "awaiting_terminal", "source": "none", "observed_at": None, "valid_envelope": False}
            notifications = list(start_notifications)
            _record_notifications(state, notifications)
            write_json_atomic(state_path, state)
            terminal_status = _terminal_from_notifications(notifications, thread_id)
            terminal_source = "turn_start_notifications" if terminal_status is not None else None
            if terminal_status is None:
                state["orchestrator"]["turn"]["phase"] = "collecting_completion"
                write_json_atomic(state_path, state)
                try:
                    notifications.extend(session.collect_until_turn_complete(thread_id, timeout_seconds))
                except TimeoutError:
                    state["orchestrator"]["turn"]["phase"] = "reconciling_history"
                    state["orchestrator"]["turn"]["completion"] = {"status": "timed_out", "source": "notification_collection", "observed_at": _now(), "valid_envelope": False}
                    _record_notifications(state, notifications)
                    history, history_notifications, history_error = _read_orchestrator_history(session, 4, thread_id)
                    notifications.extend(history_notifications)
                    _record_notifications(state, notifications)
                    terminal_status = _terminal_from_notifications(notifications, thread_id)
                    terminal_source = "notification_collection" if terminal_status is not None else None
                    if terminal_status is None:
                        terminal_status = _terminal_from_history(history, turn_id)
                        terminal_source = "thread_history" if terminal_status is not None else None
                    if terminal_status is None:
                        interrupt = state["orchestrator"]["turn"]["interrupt"]
                        interrupt["attempted"] = True
                        interrupt["requested_at"] = _now()
                        state["orchestrator"]["turn"]["phase"] = "interrupt_requested"
                        write_json_atomic(state_path, state)
                        try:
                            _, interrupt_notifications = session.request(5, "turn/interrupt", {"threadId": thread_id, "turnId": turn_id}, 30)
                            notifications.extend(interrupt_notifications)
                            interrupt["acknowledged"] = True
                            interrupt["acknowledged_at"] = _now()
                            state["orchestrator"]["turn"]["phase"] = "interrupt_confirmed"
                            try:
                                notifications.extend(session.collect_until_turn_complete(thread_id, 30))
                            except TimeoutError:
                                pass
                        except (RuntimeError, TimeoutError) as error:
                            interrupt["error"] = str(error)
                        history, history_notifications, post_interrupt_history_error = _read_orchestrator_history(session, 6, thread_id)
                        notifications.extend(history_notifications)
                        _record_notifications(state, notifications)
                        terminal_status = _terminal_from_notifications(notifications, thread_id)
                        terminal_source = "post_interrupt_reconciliation" if terminal_status is not None else None
                        if terminal_status is None:
                            terminal_status = _terminal_from_history(history, turn_id)
                            terminal_source = "post_interrupt_reconciliation" if terminal_status is not None else None
                        if terminal_status is None:
                            state["orchestrator"]["turn"]["phase"] = "completion_unknown"
                            state["orchestrator"]["turn"]["completion"] = {"status": "unknown_timeout", "source": "post_interrupt_reconciliation", "observed_at": _now(), "valid_envelope": False}
                            detail = "; ".join(item for item in (history_error, post_interrupt_history_error, interrupt["error"]) if item) or "turn/completed was not observed after timeout and interrupt"
                            _mark_blocked(state, "turn_completion_unknown", detail)
                            raise OrchestratorError("turn completion remains unknown after timeout reconciliation")
                        _record_terminal(state, terminal_status, terminal_source or "post_interrupt_reconciliation")
                        _mark_blocked(state, "orchestrator_turn_interrupted", "turn exceeded the completion timeout and required interrupt; start a new run")
                        raise OrchestratorError("Orchestrator turn required interrupt after completion timeout")
                terminal_status = _terminal_from_notifications(notifications, thread_id)
                terminal_source = "notification_collection" if terminal_status is not None else terminal_source
            if terminal_status is None:
                terminal_status = _terminal_from_history(history, turn_id)
                terminal_source = "thread_history" if terminal_status is not None else terminal_source
            if terminal_status is None:
                _mark_blocked(state, "turn_completion_unknown", "turn completed without durable terminal evidence")
                raise OrchestratorError("turn terminal evidence is missing")
            _record_terminal(state, terminal_status, terminal_source or "notification_collection")
            if terminal_status != "completed":
                _mark_blocked(state, "orchestrator_turn_terminal_noncompleted", f"turn terminal status was {terminal_status}")
                raise OrchestratorError(f"Orchestrator turn ended with terminal status {terminal_status}")
            if not history:
                history, history_notifications, _ = _read_orchestrator_history(session, 4, thread_id)
                notifications.extend(history_notifications)
                _record_notifications(state, notifications)
            evidence = notifications + history_notifications + [history]
            if walk_items(evidence):
                _mark_blocked(state, "orchestrator_subagent_control_forbidden", "Orchestrator attempted to control a Subagent")
                raise OrchestratorError("Orchestrator attempted to control a Subagent; Subagents belong to Workers")
            messages = walk_root_agent_messages(evidence, thread_id)
            raw = messages[-1] if messages else ""
    except BaseException as error:
        if state["status"] not in {"blocked", "cancelled", "succeeded"}:
            _mark_blocked(state, "orchestrator_turn_failed", str(error))
        raise
    finally:
        after = _git_boundary(repository_root)
        _record_boundary(state, "post_git", after)
        if after["availability"] != "observed":
            _mark_blocked(state, "post_turn_git_unknown", str(after["error"] or "could not inspect repository after turn"))
        elif before["porcelain"] != after["porcelain"]:
            _mark_blocked(state, "orchestrator_write_boundary", "controller repository worktree changed during Orchestrator turn")
        write_json_atomic(state_path, state)
    if state["status"] == "blocked":
        raise OrchestratorError(str((state.get("quarantine") or {}).get("detail") or "Orchestrator run is blocked"))
    turn = parse_orchestrator_turn(raw, state["run_id"])
    if turn is None:
        _mark_blocked(state, "invalid_orchestrator_turn", "Orchestrator did not return a valid structured turn")
        write_json_atomic(state_path, state)
        raise OrchestratorError("Orchestrator did not return a valid structured turn")
    state["orchestrator"]["turn"]["completion"]["valid_envelope"] = True
    state["orchestrator"]["turn"]["terminal"]["valid_envelope"] = True
    try:
        apply_orchestrator_turn(state, turn)
    except OrchestratorError:
        write_json_atomic(state_path, state)
        raise
    worker_results: list[dict[str, Any]] = []
    if turn["action"] in {"dispatch", "control"} and state["status"] == "running":
        worker_results = dispatch_ready_workers(state, timeout_seconds=timeout_seconds, worker_runner=worker_runner)
        if worker_results:
            _event(state, "ready_workers_dispatched", assignment_ids=[item.get("assignment_id") for item in worker_results])
    write_json_atomic(state_path, state)
    return {"thread_id": state["orchestrator"]["thread_id"], "turn_id": state["orchestrator"]["turn"]["turn_id"], "message": raw, "action": turn["action"], "worker_results": worker_results, "state": state}


def cancel_run(state: dict[str, Any], state_path: Path, reason: str, *, interrupt: Callable[[str], bool] | None = None) -> dict[str, Any]:
    validate_snapshot(state)
    if not reason or not reason.strip():
        raise OrchestratorError("cancel reason must not be empty")
    state["status"] = "cancelling"
    _event(state, "cancel_requested", reason=reason)
    thread_id = state["orchestrator"]["thread_id"]
    try:
        stopped = (thread_id is None and not any(item["status"] in {"running", "submitted", "verifying", "awaiting_orchestrator", "awaiting_owner"} for item in state["assignments"])) if interrupt is None else bool(interrupt(thread_id))
    except BaseException as error:
        stopped = False
        _event(state, "cancel_interrupt_failed", error=str(error))
    if stopped:
        for assignment in state["assignments"]:
            if assignment["status"] not in {"accepted", "cancelled"}:
                assignment["status"] = "cancelled"
                assignment["worker"]["status"] = "stopped"
        state["status"] = "cancelled"
        _event(state, "cancelled", reason=reason)
        _ledger_event(state, "run", state["run_id"], "cancel", "worker and orchestrator stop proven", reason=reason)
    else:
        state["status"] = "blocked"
        state["quarantine"] = {"reason": "cancellation_uncertain", "workspaces": _active_workspace_paths(state), "at": _now(), "detail": "thread/process stop could not be proven"}
        _event(state, "cancellation_uncertain")
    write_json_atomic(state_path, state)
    return state


def recover_run(state: dict[str, Any], state_path: Path, *, force: bool = False) -> dict[str, Any]:
    validate_snapshot(state)
    non_reusable_reasons = {"cancellation_uncertain", "turn_completion_unknown", "orchestrator_turn_interrupted"}
    if (state.get("quarantine") or {}).get("reason") in non_reusable_reasons:
        raise OrchestratorError("quarantined runs without a trustworthy terminal turn remain non-reusable; start a new run after manual reconciliation")
    active = [item["assignment_id"] for item in state["assignments"] if item["status"] in {"running", "submitted", "verifying", "awaiting_orchestrator", "awaiting_owner"} or item["worker"].get("status") == "running"]
    if active:
        raise OrchestratorError(f"cannot recover while Worker activity is unresolved: {', '.join(active)}")
    lock_path = Path(state["controller"]["lock_path"])
    if lock_path.exists():
        if not force:
            raise ControllerBusy("recovery requires explicit force after checking the previous controller")
        try:
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise OrchestratorError("controller lock is unreadable; cannot recover safely") from error
        pid = lock.get("pid") if isinstance(lock, dict) else None
        if isinstance(pid, int) and pid != os.getpid():
            try:
                os.kill(pid, 0)
            except OSError:
                lock_path.unlink(missing_ok=True)
            else:
                raise ControllerBusy(f"controller process {pid} is still alive")
        elif pid == os.getpid():
            raise ControllerBusy("current process owns the controller lock")
        else:
            raise OrchestratorError("controller lock has no trustworthy owner")
    state["quarantine"] = None
    if state["status"] == "blocked":
        state["status"] = "running"
    _event(state, "run_recovered", force=force)
    write_json_atomic(state_path, state)
    return state


# Public lifecycle names mirror the CLI verbs.  Keeping these as small
# wrappers makes the module useful to lightweight callers without forcing them
# through argparse or the App Server path.
def start(state_path: Path, state: dict[str, Any], *, timeout_seconds: int = 900) -> dict[str, Any]:
    return start_run(state_path, state, timeout_seconds=timeout_seconds)


def message(state: dict[str, Any], body: str, *, kind: str = "ordinary_correction", provenance: str = "broker") -> dict[str, Any]:
    return record_broker_message(state, body, kind=kind, provenance=provenance)


def advance(state: dict[str, Any], state_path: Path, *, body: str = "", timeout_seconds: int = 900, resume: bool = True) -> dict[str, Any]:
    with controller_lock(state):
        try:
            return run_orchestrator_turn(state, state_path, message=body, timeout_seconds=timeout_seconds, resume=resume)
        except BaseException as error:
            if state["status"] not in {"blocked", "cancelled", "succeeded"}:
                state["status"] = "blocked"
                state["quarantine"] = {"reason": "orchestrator_turn_failed", "detail": str(error), "at": _now()}
            write_json_atomic(state_path, state)
            raise


def status(state: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    return state


def cancel(state: dict[str, Any], state_path: Path, reason: str, *, interrupt: Callable[[str], bool] | None = None) -> dict[str, Any]:
    with controller_lock(state):
        return cancel_run(state, state_path, reason, interrupt=interrupt)


def recover(state: dict[str, Any], state_path: Path, *, force: bool = False) -> dict[str, Any]:
    return recover_run(state, state_path, force=force)


def start_run(state_path: Path, state: dict[str, Any], *, timeout_seconds: int = 900) -> dict[str, Any]:
    validate_snapshot(state)
    with controller_lock(state):
        write_json_atomic(state_path, state)
        try:
            return run_orchestrator_turn(state, state_path, timeout_seconds=timeout_seconds, resume=False)
        except BaseException as error:
            if state["status"] not in {"blocked", "cancelled", "succeeded"}:
                state["status"] = "blocked"
                state["quarantine"] = {"reason": "orchestrator_turn_failed", "detail": str(error), "at": _now()}
            write_json_atomic(state_path, state)
            raise


def main() -> int:
    parser = argparse.ArgumentParser(description="Thin Codex Crew Orchestrator control plane.")
    sub = parser.add_subparsers(dest="command", required=True)
    start = sub.add_parser("start")
    start.add_argument("--repository-root", type=Path, required=True)
    issue = start.add_mutually_exclusive_group(required=True)
    issue.add_argument("--issue")
    issue.add_argument("--issue-file", type=Path)
    start.add_argument("--state", type=Path, required=True)
    start.add_argument("--artifact-root", type=Path, help="explicit directory for Harness run evidence; defaults to the system Temp area")
    start.add_argument("--run-id")
    start.add_argument("--orchestrator-profile", default="parent-sol-high")
    start.add_argument("--timeout-seconds", type=int, default=900)
    message = sub.add_parser("message")
    message.add_argument("--state", type=Path, required=True)
    message.add_argument("--message", required=True)
    message.add_argument("--kind", default="ordinary_correction", choices=["ordinary_correction", "owner_decision", "cancel_request"])
    message.add_argument("--timeout-seconds", type=int, default=900)
    advance = sub.add_parser("advance")
    advance.add_argument("--state", type=Path, required=True)
    advance.add_argument("--timeout-seconds", type=int, default=900)
    status = sub.add_parser("status")
    status.add_argument("--state", type=Path, required=True)
    cancel = sub.add_parser("cancel")
    cancel.add_argument("--state", type=Path, required=True)
    cancel.add_argument("--reason", required=True)
    recover = sub.add_parser("recover")
    recover.add_argument("--state", type=Path, required=True)
    recover.add_argument("--force", action="store_true")
    args = parser.parse_args()
    if args.command == "start":
        issue_value = args.issue if args.issue is not None else args.issue_file.read_text(encoding="utf-8")
        state = new_snapshot(args.repository_root, issue_value, args.state, run_id=args.run_id, orchestrator_profile=args.orchestrator_profile, artifact_root=args.artifact_root)
        print(json.dumps(start_run(args.state, state, timeout_seconds=args.timeout_seconds), ensure_ascii=False, indent=2))
        return 0
    state = json.loads(args.state.read_text(encoding="utf-8"))
    validate_snapshot(state)
    if args.command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.command == "recover":
        print(json.dumps(recover_run(state, args.state, force=args.force), ensure_ascii=False, indent=2))
        return 0
    lock_acquired = False
    try:
        with controller_lock(state):
            lock_acquired = True
            if args.command == "message":
                record_broker_message(state, args.message, kind=args.kind)
                write_json_atomic(args.state, state)
                result = run_orchestrator_turn(state, args.state, message=args.message, timeout_seconds=args.timeout_seconds)
            elif args.command == "advance":
                result = run_orchestrator_turn(state, args.state, timeout_seconds=args.timeout_seconds, resume=True)
            elif args.command == "cancel":
                result = cancel_run(state, args.state, args.reason)
            else:
                raise AssertionError("unreachable")
    except BaseException as error:
        if lock_acquired and state["status"] not in {"blocked", "cancelled", "succeeded"}:
            state["status"] = "blocked"
            state["quarantine"] = {"reason": "orchestrator_turn_failed", "detail": str(error), "at": _now()}
        write_json_atomic(args.state, state)
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OrchestratorError, TopologyError, ValueError, RuntimeError, TimeoutError) as error:
        print(f"[X] {error}", file=sys.stderr)
        raise SystemExit(1)
