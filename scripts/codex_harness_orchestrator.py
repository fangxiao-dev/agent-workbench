#!/usr/bin/env python3
"""Thin Codex Crew orchestration control plane.

This module owns the Crew control plane separately from the Package stage runner. It
owns one run snapshot and the hard boundaries around that snapshot; the
Orchestrator agent remains free to choose decomposition, assurance mode,
profiles, explicit Worker cohorts, workspace layout and Worker-local subagents.  The module never writes
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
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

try:
    from codex_harness_agent import run_role_turn
    from codex_harness_control import cancel_commit_guard, clear_cancel_request, read_cancel_request, write_cancel_request
    from codex_harness_controller import git_status, walk_items, walk_root_agent_messages
    from codex_harness_dispatch import assignment_task, continue_assignment, ensure_worktree, run_worker, write_json_atomic
    from codex_harness_policy import load_orchestrator_policy
    from codex_harness_profiles import ExecutionProfileError, fetch_model_catalog, load_execution_profiles, resolve_execution_profile, select_available_verifier_profile, select_available_worker_profile, worker_profile_candidates_for_mode
    from codex_harness_runtime import LedgerIntegrityError, ResourceLedger
    from codex_harness_workspace import WorkspaceError, serial_handoff_evidence, validate_serial_reuse, worker_git_writable_roots
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_agent import run_role_turn
    from scripts.codex_harness_control import cancel_commit_guard, clear_cancel_request, read_cancel_request, write_cancel_request
    from scripts.codex_harness_controller import git_status, walk_items, walk_root_agent_messages
    from scripts.codex_harness_dispatch import assignment_task, continue_assignment, ensure_worktree, run_worker, write_json_atomic
    from scripts.codex_harness_policy import load_orchestrator_policy
    from scripts.codex_harness_profiles import ExecutionProfileError, fetch_model_catalog, load_execution_profiles, resolve_execution_profile, select_available_verifier_profile, select_available_worker_profile, worker_profile_candidates_for_mode
    from scripts.codex_harness_runtime import LedgerIntegrityError, ResourceLedger
    from scripts.codex_harness_workspace import WorkspaceError, serial_handoff_evidence, validate_serial_reuse, worker_git_writable_roots


CONTROL_SCHEMA_VERSION = "codex-crew.control.v0.5"
ORCHESTRATOR_TURN_SCHEMA_VERSION = "codex-crew.orchestrator-turn.v0.3"
WORKER_RESULT_SCHEMA_VERSION = "codex-crew.worker-result.v0.1"
VERIFIER_RESULT_SCHEMA_VERSION = "codex-crew.verifier-result.v0.1"
ACCEPTANCE_SCHEMA_VERSION = "codex-crew.acceptance.v0.1"
DEFAULT_OBSERVATION_INTERVAL_SECONDS = 180
MAX_ACTIVE_WORKERS = 4
RUN_STATUSES = {"running", "awaiting_owner", "blocked", "cancelling", "cancelled", "finished"}
ASSIGNMENT_KINDS = {"delivery"}
ACCESS_MODES = {"repository_read_only", "workspace_write"}
ASSIGNMENT_STATUSES = {"planned", "ready", "running", "awaiting_orchestrator", "awaiting_owner", "submitted", "verifying", "accepted", "rejected", "failed", "cancelled"}
WORKER_STATUSES = {"succeeded", "needs_orchestrator", "needs_owner", "failed"}
OWNER_CATEGORIES = {"scope_change", "authority_expansion", "irreversible_external_side_effect", "acceptance_ambiguity"}
ACTIONS = {"dispatch", "control", "ask_owner", "finish"}
CONTROL_OPERATIONS = {"start_workers", "continue_worker", "run_verifier", "accept", "cancel_assignment"}
TERMINAL_DISPOSITIONS = {"succeeded", "partial", "blocked", "needs_owner", "failed"}
CREW_INTENT_SHAPES = {"orchestrator_read_only", "single_writer", "multi_writer"}


class OrchestratorError(RuntimeError):
    """Base error for a malformed run or an unsafe control-plane operation."""


class ControllerBusy(OrchestratorError):
    """Another process currently owns the run controller lock."""


class FullVerificationRequired(OrchestratorError):
    """A Full assignment cannot be accepted without an independent verifier."""


def _now() -> float:
    return time.time()


def _event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    state.setdefault("events", []).append({"event_id": uuid.uuid4().hex, "at": _now(), "kind": kind, "data": fields})


def _open_owner_requests(state: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in state.get("owner_requests", []) if isinstance(item, dict) and item.get("status") == "open"]


def _assignment_has_owner_gate(state: dict[str, Any], assignment_id: str) -> bool:
    return any(item.get("scope") == "run" or item.get("assignment_id") == assignment_id for item in _open_owner_requests(state))


def _ready_assignment_ids_unchecked(state: dict[str, Any]) -> list[str]:
    by_id = {item["assignment_id"]: item for item in state.get("assignments", []) if isinstance(item, dict) and isinstance(item.get("assignment_id"), str)}
    ready: list[str] = []
    for assignment in state.get("assignments", []):
        if assignment.get("status") not in {"planned", "ready", "awaiting_orchestrator", "rejected"}:
            continue
        assignment_id = assignment["assignment_id"]
        if _assignment_has_owner_gate(state, assignment_id):
            continue
        if all(by_id.get(dependency, {}).get("status") == "accepted" for dependency in assignment.get("depends_on", [])):
            ready.append(assignment_id)
    return ready


def _refresh_crew_projection(state: dict[str, Any]) -> None:
    """Derive the observable Crew panorama without making it a scheduler."""

    crew = state["crew"]
    assignments = state.get("assignments", [])
    active = [item["assignment_id"] for item in assignments if item.get("worker", {}).get("status") == "running"]
    verifier = [item["assignment_id"] for item in assignments if item.get("verifier", {}).get("status") in {"pending", "running", "passed", "failed", "blocked"} and item.get("assurance_mode") == "full"]
    waiting = sorted({item.get("assignment_id") for item in _open_owner_requests(state) if isinstance(item.get("assignment_id"), str)})
    active_leases = [
        {"assignment_id": item["assignment_id"], "path": item["workspace"]["path"], "branch": item["workspace"]["branch"]}
        for item in assignments
        if isinstance(item.get("workspace"), dict) and item["workspace"].get("lease", {}).get("status") == "active" and isinstance(item["workspace"].get("path"), str)
    ]
    observed_at = _now()
    active_writers = [item for item in assignments if item.get("worker", {}).get("status") == "running" and item.get("access_mode") == "workspace_write"]
    crew["observed"] = {
        "active_worker_ids": sorted(active),
        "ready_assignment_ids": _ready_assignment_ids_unchecked(state),
        "awaiting_owner_assignment_ids": waiting,
        "verifier_assignment_ids": sorted(verifier),
        "active_write_leases": active_leases,
        "actual_shape": "multi_writer" if len(active_writers) > 1 else ("single_writer" if active_writers else "orchestrator_read_only"),
        "updated_at": observed_at,
    }
    if state.get("status") in {"running", "awaiting_owner"}:
        executable = crew["observed"]["ready_assignment_ids"] or active
        state["status"] = "awaiting_owner" if _open_owner_requests(state) and not executable else "running"


def _append_broker_notification(state: dict[str, Any], kind: str, summary: str, assignment_ids: list[str] | None = None) -> dict[str, Any]:
    known = {item["assignment_id"] for item in state.get("assignments", [])}
    allowed_kinds = {"crew_intent_changed", "assignment_defined", "worker_started", "worker_result", "verifier_result", "owner_request", "workspace_changed", "material_plan_change", "terminal"}
    related = list(assignment_ids or [])
    if kind not in allowed_kinds or not isinstance(summary, str) or not summary.strip() or len(related) != len(set(related)) or set(related) - known:
        raise OrchestratorError("Broker notification is malformed or references an unknown assignment")
    notification = {"notification_id": uuid.uuid4().hex, "kind": kind, "summary": summary.strip(), "assignment_ids": related, "created_at": _now()}
    state["broker_notifications"].append(notification)
    return notification


def _run_workspace_root(state: dict[str, Any]) -> Path:
    return (Path(state["repository_root"]).resolve().parent / ".codex-crew-worktrees" / state["run_id"]).resolve()


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
    if assignment.get("access_mode") == "workspace_write" and not allowed:
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
    candidates = worker_profile_candidates_for_mode(bundle, assignment["assurance_mode"])
    if profile not in candidates:
        raise OrchestratorError(f"{assignment['assurance_mode']} assignment must use a canonical candidate profile")
    selection = assignment.get("execution_profile_selection")
    if selection is None:
        if profile != candidates[0]:
            raise OrchestratorError(f"{assignment['assurance_mode']} assignment must begin with canonical primary profile {candidates[0]['id']}")
    elif not isinstance(selection, dict) or set(selection) != {"requested_candidates", "selected_profile", "catalog_digest", "observed_at", "reason"} or selection["requested_candidates"] != candidates or selection["selected_profile"] != profile or not isinstance(selection["catalog_digest"], str) or len(selection["catalog_digest"]) != 64 or any(character not in "0123456789abcdef" for character in selection["catalog_digest"]) or not isinstance(selection["observed_at"], (int, float)) or isinstance(selection["observed_at"], bool) or selection["reason"] not in {"first_available_candidate", "fallback_after_unavailable_prior_candidates"}:
        raise OrchestratorError("assignment Worker profile selection evidence is malformed")
    return profile


def _select_assignment_worker_profile(state: dict[str, Any], assignment: dict[str, Any], catalog: dict[str, Any] | None = None) -> dict[str, str]:
    """Resolve one Worker profile from App Server ``model/list`` before writing a workspace."""

    if assignment.get("execution_profile_selection") is not None:
        return _profile_for_assignment(state, assignment)
    try:
        bundle = load_execution_profiles(Path(__file__).resolve().parents[1])
        selection = select_available_worker_profile(bundle, assignment["assurance_mode"], catalog if catalog is not None else fetch_model_catalog())
    except ExecutionProfileError as error:
        raise OrchestratorError(f"Worker profile preflight failed before workspace materialization: {error}") from error
    assignment["execution_profile"] = selection["selected_profile"]["id"]
    assignment["execution_profile_selection"] = selection
    _event(state, "worker_profile_selected", assignment_id=assignment["assignment_id"], selected_profile=selection["selected_profile"]["id"], catalog_digest=selection["catalog_digest"], reason=selection["reason"])
    return _profile_for_assignment(state, assignment)

def _empty_turn_observation() -> dict[str, Any]:
    return {
        "turn_id": None,
        "started_at": None,
        "phase": "not_started",
        "completion": {"status": "not_started", "source": "none", "observed_at": None, "valid_envelope": False},
        "terminal": {"observed": False, "status": "not_observed", "observed_at": None, "source": "none", "valid_envelope": False},
        "interrupt": {"attempted": False, "acknowledged": False, "requested_at": None, "acknowledged_at": None, "error": None},
        "notification_summary": {"observed_count": 0, "methods": []},
        "observation": {"observed_at": None, "process_alive": None, "last_notification_at": None, "last_notification_method": None},
    }


def _empty_git_boundary() -> dict[str, Any]:
    return {"observed_at": None, "availability": "unavailable", "head": None, "is_clean": None, "porcelain": None, "error": None}


def _git_boundary(repository_root: Path) -> dict[str, Any]:
    try:
        head = _git(repository_root, "rev-parse", "HEAD")
        porcelain = git_status(repository_root)
    except BaseException as error:
        return {"observed_at": _now(), "availability": "unavailable", "head": None, "is_clean": None, "porcelain": None, "error": str(error)}
    return {"observed_at": _now(), "availability": "observed", "head": head, "is_clean": not bool(porcelain), "porcelain": porcelain, "error": None}


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


def _record_notifications(state: dict[str, Any], notifications: list[dict[str, Any]]) -> None:
    state["orchestrator"]["turn"]["notification_summary"] = _notification_summary(notifications)


def _record_observation(state: dict[str, Any], observation: dict[str, Any]) -> None:
    required = {"observed_at", "process_alive", "last_notification_at", "last_notification_method"}
    if set(observation) != required or not isinstance(observation["observed_at"], (int, float)) or not isinstance(observation["process_alive"], bool) or (observation["last_notification_at"] is not None and not isinstance(observation["last_notification_at"], (int, float))) or (observation["last_notification_method"] is not None and not isinstance(observation["last_notification_method"], str)):
        raise OrchestratorError("App Server observation is malformed")
    state["orchestrator"]["turn"]["observation"] = dict(observation)


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


@contextmanager
def _controller_commit_boundary(
    state: dict[str, Any],
    *,
    role: str,
    thread_id: str | None = None,
    turn_id: str | None = None,
) -> Iterator[None]:
    """Keep one short state/workspace commit linearizable with explicit cancel."""

    state_path = Path(state["state_path"])
    with cancel_commit_guard(state_path, state["run_id"]) as pending:
        if pending is not None:
            outcome = _completed_role_cancel_outcome(pending, thread_id=thread_id, turn_id=turn_id)
            _apply_role_cancel_outcome(state, state_path, outcome, role)
            raise OrchestratorError(f"run cancelled before {role} result/control application")
        yield


def _thin_policy_identity() -> dict[str, Any]:
    try:
        return load_orchestrator_policy(Path(__file__).resolve().parents[1])["identity"]
    except Exception as error:
        raise OrchestratorError(f"thin-control runtime policy is unavailable: {error}") from error


def new_snapshot(repository_root: Path, issue: str, state_path: Path, *, run_id: str | None = None, orchestrator_profile: str = "parent-sol-high", artifact_root: Path | None = None) -> dict[str, Any]:
    root = repository_root.resolve()
    if not issue or not issue.strip():
        raise OrchestratorError("issue must not be empty")
    resolved_run = run_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    if any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in resolved_run):
        raise OrchestratorError("run_id may contain only letters, digits, dash, underscore and dot")
    artifacts = (artifact_root or Path(tempfile.gettempdir()) / "codex-harness-runs" / "crew-orchestrator" / resolved_run).resolve()
    try:
        policy = load_orchestrator_policy(Path(__file__).resolve().parents[1])
    except Exception as error:
        raise OrchestratorError(f"thin-control runtime policy validation failed: {error}") from error
    configured_max_workers = policy["policy"]["crew_control"]["max_active_workers"]
    snapshot = {
        "$schema": "./codex-crew.control.v0.5.schema.json",
        "schema_version": CONTROL_SCHEMA_VERSION,
        "run_id": resolved_run,
        "repository_root": str(root),
        "artifact_root": str(artifacts),
        "workspace_root": str((root.parent / ".codex-crew-worktrees" / resolved_run).resolve()),
        "state_path": str(state_path.resolve()),
        "issue": issue.strip(),
        "status": "running",
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
        "crew": {
            "capabilities": {
                "max_active_workers": configured_max_workers,
                "roles": ["worker", "verifier"],
                "assurance_modes": ["lite", "full"],
                "worker_access_modes": ["repository_read_only", "workspace_write"],
                "workspace_strategies": list(policy["policy"]["workspace"]["allowed_strategies"]),
                "runtime": {"cohort_parallelism_available": configured_max_workers > 1, "observed_at": None, "evidence": "canonical_runtime_policy"},
            },
            "intent": {"shape": "orchestrator_read_only", "rationale": "No Worker capability has been invoked.", "updated_at": _now()},
            "observed": {"active_worker_ids": [], "ready_assignment_ids": [], "awaiting_owner_assignment_ids": [], "verifier_assignment_ids": [], "active_write_leases": [], "actual_shape": "orchestrator_read_only", "updated_at": _now()},
        },
        "broker_notifications": [],
        "terminal": None,
        "assignments": [],
        "owner_requests": [],
        "messages": [],
        "acceptances": [],
        "events": [{"event_id": uuid.uuid4().hex, "at": _now(), "kind": "run_initialized", "data": {}}],
        "last_message": "",
        "quarantine": None,
        "cancellation": {"phase": "none", "request_id": None, "requested_at": None, "handled_at": None, "reason": None, "provenance": None},
        "controller": {"lock_path": str(state_path.resolve().with_suffix(".controller.lock"))},
    }
    _refresh_crew_projection(snapshot)
    validate_snapshot(snapshot)
    return snapshot


def _validate_assignment(assignment: dict[str, Any], repository_root: Path) -> None:
    required = {"run_id", "assignment_id", "kind", "revision", "goal", "non_goals", "acceptance_criteria", "assurance_mode", "execution_profile", "execution_profile_selection", "access_mode", "allowed_paths", "external_resources", "verification_commands", "depends_on", "context", "status", "workspace", "boundary_evidence", "worker", "result", "verifier", "acceptance"}
    if not isinstance(assignment, dict) or required - set(assignment):
        raise OrchestratorError("assignment is missing required fields")
    if not isinstance(assignment["run_id"], str) or not assignment["run_id"].strip() or assignment["kind"] not in ASSIGNMENT_KINDS or not isinstance(assignment["assignment_id"], str) or not assignment["assignment_id"].strip() or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in assignment["assignment_id"]) or not isinstance(assignment["revision"], int) or isinstance(assignment["revision"], bool) or assignment["revision"] < 1:
        raise OrchestratorError("assignment identity or kind is malformed")
    if not isinstance(assignment["goal"], str) or not assignment["goal"].strip() or not isinstance(assignment["non_goals"], list) or any(not isinstance(item, str) for item in assignment["non_goals"]):
        raise OrchestratorError("assignment goal/non_goals are malformed")
    if not isinstance(assignment["acceptance_criteria"], list) or not assignment["acceptance_criteria"] or any(not isinstance(item, str) or not item.strip() for item in assignment["acceptance_criteria"]):
        raise OrchestratorError("assignment acceptance_criteria must contain non-empty natural-language criteria")
    if assignment["assurance_mode"] not in {"lite", "full"} or not isinstance(assignment["execution_profile"], str) or not assignment["execution_profile"].strip():
        raise OrchestratorError("assignment assurance/profile is malformed")
    if assignment["access_mode"] not in ACCESS_MODES:
        raise OrchestratorError("assignment access_mode is malformed")
    allowed = assignment["allowed_paths"]
    if not isinstance(allowed, list) or any(not isinstance(item, str) for item in allowed):
        raise OrchestratorError("assignment allowed_paths are malformed")
    normalized_allowed = [_normal_path(item) for item in allowed]
    if assignment["access_mode"] == "workspace_write" and not normalized_allowed:
        raise OrchestratorError("delivery assignments must declare at least one allowed path")
    if assignment["access_mode"] == "repository_read_only" and normalized_allowed:
        raise OrchestratorError("read-only assignments cannot declare write ownership")
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
    if assignment["access_mode"] == "repository_read_only":
        if workspace is not None:
            raise OrchestratorError("read-only assignments cannot bind a write workspace")
    elif not isinstance(workspace, dict) or set(workspace) != {"strategy", "handoff_from", "path", "branch", "base_ref", "materialized", "lease"} or workspace["strategy"] not in {"new", "reuse"}:
        raise OrchestratorError("write assignment workspace is malformed")
    boundary_evidence = assignment["boundary_evidence"]
    if not isinstance(boundary_evidence, dict) or set(boundary_evidence) != {"source_revision", "pre_git", "post_git"} or (boundary_evidence["source_revision"] is not None and (not isinstance(boundary_evidence["source_revision"], str) or not boundary_evidence["source_revision"].strip())):
        raise OrchestratorError("assignment repository boundary evidence is malformed")
    for boundary in (boundary_evidence["pre_git"], boundary_evidence["post_git"]):
        if not isinstance(boundary, dict) or set(boundary) != {"observed_at", "availability", "head", "is_clean", "porcelain", "error"} or boundary["availability"] not in {"observed", "unavailable"} or (boundary["observed_at"] is not None and not isinstance(boundary["observed_at"], (int, float))) or (boundary["head"] is not None and not isinstance(boundary["head"], str)) or (boundary["is_clean"] is not None and not isinstance(boundary["is_clean"], bool)) or (boundary["porcelain"] is not None and not isinstance(boundary["porcelain"], str)) or (boundary["error"] is not None and not isinstance(boundary["error"], str)):
            raise OrchestratorError("assignment Git boundary evidence is malformed")
    if workspace is not None:
        if not isinstance(workspace["materialized"], bool) or not isinstance(workspace["lease"], dict) or set(workspace["lease"]) != {"status", "acquired_at", "released_at"} or workspace["lease"]["status"] not in {"inactive", "active", "released"} or any(value is not None and not isinstance(value, (int, float)) for value in (workspace["lease"]["acquired_at"], workspace["lease"]["released_at"])):
            raise OrchestratorError("assignment workspace materialization or lease evidence is malformed")
        if workspace["strategy"] == "new" and workspace["handoff_from"] is not None:
            raise OrchestratorError("new workspace cannot declare handoff_from")
        if workspace["strategy"] == "reuse" and (not isinstance(workspace["handoff_from"], str) or not workspace["handoff_from"].strip()):
            raise OrchestratorError("reused workspace requires an explicit handoff_from assignment")
        resolved_fields = [workspace[key] for key in ("path", "branch", "base_ref")]
        if any(value is not None and (not isinstance(value, str) or not value.strip()) for value in resolved_fields) or any(value is None for value in resolved_fields) and any(value is not None for value in resolved_fields):
            raise OrchestratorError("workspace path, branch and base_ref must be resolved together")
        if workspace["path"] is not None:
            resolved_workspace = Path(workspace["path"]).resolve()
            run_root = (repository_root.resolve().parent / ".codex-crew-worktrees" / assignment["run_id"]).resolve()
            if workspace["strategy"] == "new" and resolved_workspace != run_root and run_root not in resolved_workspace.parents:
                raise OrchestratorError("new Worker worktree must remain inside the run-owned workspace root")
            if workspace["strategy"] == "new" and not workspace["branch"].startswith(f"codex/crew/{assignment['run_id']}/{assignment['assignment_id']}/"):
                raise OrchestratorError("new Worker branch must use the assignment-scoped run-owned prefix")
    worker = assignment["worker"]
    if not isinstance(worker, dict) or set(worker) != {"thread_id", "turn_id", "status", "interrupt"} or any(value is not None and (not isinstance(value, str) or not value.strip()) for value in (worker["thread_id"], worker["turn_id"])) or worker["status"] not in {"pending", "running", "stopped"}:
        raise OrchestratorError("assignment worker binding is malformed")
    worker_interrupt = worker["interrupt"]
    if not isinstance(worker_interrupt, dict) or set(worker_interrupt) != {"attempted", "acknowledged", "requested_at", "acknowledged_at", "error"} or not isinstance(worker_interrupt["attempted"], bool) or not isinstance(worker_interrupt["acknowledged"], bool) or any(value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool)) for value in (worker_interrupt["requested_at"], worker_interrupt["acknowledged_at"])) or (worker_interrupt["error"] is not None and not isinstance(worker_interrupt["error"], str)):
        raise OrchestratorError("assignment worker interrupt evidence is malformed")
    if assignment["result"] is not None and not isinstance(assignment["result"], dict):
        raise OrchestratorError("assignment result must be null or an object")
    verifier = assignment["verifier"]
    if not isinstance(verifier, dict) or set(verifier) != {"status", "attempts"} or verifier["status"] not in {"not_required", "pending", "running", "passed", "failed", "blocked"} or not isinstance(verifier["attempts"], list) or any(not isinstance(item, dict) for item in verifier["attempts"]):
        raise OrchestratorError("assignment verifier state is malformed")
    attempt_fields = {"schema_version", "run_id", "assignment_id", "revision", "base_commit", "head_commit", "worker_result_digest", "profile", "thread_id", "turn_id", "status", "independent", "recursive", "summary", "findings", "verification", "observed_at"}
    for attempt in verifier["attempts"]:
        if set(attempt) != attempt_fields or attempt.get("schema_version") != VERIFIER_RESULT_SCHEMA_VERSION or attempt.get("run_id") != assignment["run_id"] or attempt.get("assignment_id") != assignment["assignment_id"] or attempt.get("revision") != assignment["revision"] or any(not isinstance(attempt.get(key), str) or not attempt[key].strip() for key in ("base_commit", "head_commit", "worker_result_digest", "thread_id", "turn_id", "summary")) or attempt.get("profile") != "verifier-sol-high" or attempt.get("status") not in {"passed", "failed", "blocked"} or attempt.get("independent") is not True or attempt.get("recursive") is not False or not isinstance(attempt.get("findings"), list) or not isinstance(attempt.get("verification"), list) or not isinstance(attempt.get("observed_at"), (int, float)) or isinstance(attempt.get("observed_at"), bool):
            raise OrchestratorError("assignment verifier attempt is malformed")
    if assignment["assurance_mode"] == "lite" and verifier != {"status": "not_required", "attempts": []}:
        raise OrchestratorError("Lite assignments cannot carry independent verifier state")
    if assignment["acceptance"] is not None and not isinstance(assignment["acceptance"], dict):
        raise OrchestratorError("assignment acceptance must be null or an object")
    _profile_for_assignment({"repository_root": str(repository_root)}, assignment)


def validate_snapshot(state: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "repository_root", "artifact_root", "workspace_root", "state_path", "issue", "status", "policy_identity", "orchestrator", "crew", "broker_notifications", "terminal", "assignments", "owner_requests", "messages", "acceptances", "events", "last_message", "quarantine", "cancellation", "controller"}
    if not isinstance(state, dict) or state.get("schema_version") != CONTROL_SCHEMA_VERSION or required - set(state):
        raise OrchestratorError("unsupported or incomplete Orchestrator snapshot")
    if any(not isinstance(state.get(key), str) or not state[key].strip() for key in ("run_id", "repository_root", "artifact_root", "workspace_root", "state_path", "issue")) or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for character in state["run_id"]) or state["status"] not in RUN_STATUSES or Path(state["workspace_root"]).resolve() != _run_workspace_root(state):
        raise OrchestratorError("snapshot identity or status is malformed")
    policy_identity = state["policy_identity"]
    if not isinstance(policy_identity, dict) or policy_identity.get("schema_version") != "codex-harness.runtime-policy.v1.3" or any(not isinstance(policy_identity.get(key), str) or not policy_identity[key].strip() for key in ("policy_path", "schema_path", "policy_sha256", "schema_sha256", "maturity")):
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
    if not isinstance(turn, dict) or set(turn) != {"turn_id", "started_at", "phase", "completion", "terminal", "interrupt", "notification_summary", "observation"} or (turn["turn_id"] is not None and not isinstance(turn["turn_id"], str)) or (turn["started_at"] is not None and not isinstance(turn["started_at"], (int, float))) or turn["phase"] not in {"not_started", "started", "collecting_completion", "terminal_observed"}:
        raise OrchestratorError("Orchestrator turn observation is malformed")
    completion = turn["completion"]
    if not isinstance(completion, dict) or set(completion) != {"status", "source", "observed_at", "valid_envelope"} or completion["status"] not in {"not_started", "awaiting_terminal", "completed"} or completion["source"] not in {"none", "turn_start_notifications", "notification_collection", "thread_history"} or (completion["observed_at"] is not None and not isinstance(completion["observed_at"], (int, float))) or not isinstance(completion["valid_envelope"], bool):
        raise OrchestratorError("Orchestrator completion evidence is malformed")
    terminal = turn["terminal"]
    if not isinstance(terminal, dict) or set(terminal) != {"observed", "status", "observed_at", "source", "valid_envelope"} or not isinstance(terminal["observed"], bool) or terminal["status"] not in {"not_observed", "completed", "failed", "interrupted", "cancelled"} or terminal["source"] not in {"none", "turn_start_notifications", "notification_collection", "thread_history"} or (terminal["observed_at"] is not None and not isinstance(terminal["observed_at"], (int, float))) or not isinstance(terminal["valid_envelope"], bool) or (terminal["observed"] is False and (terminal["status"] != "not_observed" or terminal["source"] != "none")):
        raise OrchestratorError("Orchestrator terminal evidence is malformed")
    interrupt = turn["interrupt"]
    if not isinstance(interrupt, dict) or set(interrupt) != {"attempted", "acknowledged", "requested_at", "acknowledged_at", "error"} or not isinstance(interrupt["attempted"], bool) or not isinstance(interrupt["acknowledged"], bool) or (interrupt["requested_at"] is not None and not isinstance(interrupt["requested_at"], (int, float))) or (interrupt["acknowledged_at"] is not None and not isinstance(interrupt["acknowledged_at"], (int, float))) or (interrupt["error"] is not None and not isinstance(interrupt["error"], str)):
        raise OrchestratorError("Orchestrator interrupt evidence is malformed")
    notification_summary = turn["notification_summary"]
    if not isinstance(notification_summary, dict) or set(notification_summary) != {"observed_count", "methods"} or not isinstance(notification_summary["observed_count"], int) or isinstance(notification_summary["observed_count"], bool) or notification_summary["observed_count"] < 0 or not isinstance(notification_summary["methods"], list) or any(not isinstance(item, dict) or set(item) != {"method", "count"} or not isinstance(item["method"], str) or not item["method"] or not isinstance(item["count"], int) or isinstance(item["count"], bool) or item["count"] < 1 for item in notification_summary["methods"]):
        raise OrchestratorError("Orchestrator notification summary is malformed")
    observation = turn["observation"]
    if not isinstance(observation, dict) or set(observation) != {"observed_at", "process_alive", "last_notification_at", "last_notification_method"} or (observation["observed_at"] is not None and not isinstance(observation["observed_at"], (int, float))) or (observation["process_alive"] is not None and not isinstance(observation["process_alive"], bool)) or (observation["last_notification_at"] is not None and not isinstance(observation["last_notification_at"], (int, float))) or (observation["last_notification_method"] is not None and not isinstance(observation["last_notification_method"], str)):
        raise OrchestratorError("Orchestrator current observation is malformed")
    boundary_evidence = orchestrator["boundary_evidence"]
    if not isinstance(boundary_evidence, dict) or set(boundary_evidence) != {"pre_git", "post_git"}:
        raise OrchestratorError("Orchestrator boundary evidence is malformed")
    for boundary in boundary_evidence.values():
        if not isinstance(boundary, dict) or set(boundary) != {"observed_at", "availability", "head", "is_clean", "porcelain", "error"} or boundary["availability"] not in {"observed", "unavailable"} or (boundary["observed_at"] is not None and not isinstance(boundary["observed_at"], (int, float))) or (boundary["head"] is not None and not isinstance(boundary["head"], str)) or (boundary["is_clean"] is not None and not isinstance(boundary["is_clean"], bool)) or (boundary["porcelain"] is not None and not isinstance(boundary["porcelain"], str)) or (boundary["error"] is not None and not isinstance(boundary["error"], str)):
            raise OrchestratorError("Orchestrator git boundary evidence is malformed")
    crew = state["crew"]
    if not isinstance(crew, dict) or set(crew) != {"capabilities", "intent", "observed"}:
        raise OrchestratorError("snapshot Crew panorama is malformed")
    capabilities = crew["capabilities"]
    if not isinstance(capabilities, dict) or set(capabilities) != {"max_active_workers", "roles", "assurance_modes", "worker_access_modes", "workspace_strategies", "runtime"} or capabilities["max_active_workers"] != MAX_ACTIVE_WORKERS or capabilities["roles"] != ["worker", "verifier"] or capabilities["assurance_modes"] != ["lite", "full"] or capabilities["worker_access_modes"] != ["repository_read_only", "workspace_write"] or capabilities["workspace_strategies"] != ["new", "reuse"]:
        raise OrchestratorError("snapshot Crew capabilities do not match the canonical runtime policy")
    runtime_capability = capabilities["runtime"]
    if not isinstance(runtime_capability, dict) or set(runtime_capability) != {"cohort_parallelism_available", "observed_at", "evidence"} or not isinstance(runtime_capability["cohort_parallelism_available"], bool) or (runtime_capability["observed_at"] is not None and not isinstance(runtime_capability["observed_at"], (int, float))) or not isinstance(runtime_capability["evidence"], str):
        raise OrchestratorError("snapshot Crew runtime capability evidence is malformed")
    intent = crew["intent"]
    if not isinstance(intent, dict) or set(intent) != {"shape", "rationale", "updated_at"} or intent["shape"] not in CREW_INTENT_SHAPES or not isinstance(intent["rationale"], str) or not intent["rationale"].strip() or not isinstance(intent["updated_at"], (int, float)):
        raise OrchestratorError("snapshot Crew intent is malformed")
    observed = crew["observed"]
    observed_fields = {"active_worker_ids", "ready_assignment_ids", "awaiting_owner_assignment_ids", "verifier_assignment_ids", "active_write_leases", "actual_shape", "updated_at"}
    if not isinstance(observed, dict) or set(observed) != observed_fields or observed["actual_shape"] not in CREW_INTENT_SHAPES or not isinstance(observed["updated_at"], (int, float)) or any(not isinstance(observed[key], list) for key in observed_fields - {"actual_shape", "updated_at"}):
        raise OrchestratorError("snapshot Crew observed projection is malformed")
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
    for request in state["owner_requests"]:
        required_request = {"request_id", "scope", "assignment_id", "category", "detail", "status", "requested_at", "resolved_at", "decision"}
        if not isinstance(request, dict) or set(request) != required_request or not isinstance(request["request_id"], str) or request["scope"] not in {"run", "assignment"} or request["category"] not in OWNER_CATEGORIES or not isinstance(request["detail"], str) or not request["detail"].strip() or request["status"] not in {"open", "resolved", "cancelled"} or not isinstance(request["requested_at"], (int, float)) or (request["resolved_at"] is not None and not isinstance(request["resolved_at"], (int, float))):
            raise OrchestratorError("Owner request is malformed")
        if request["scope"] == "assignment" and request["assignment_id"] not in known:
            raise OrchestratorError("assignment-scoped Owner request references an unknown assignment")
        if request["scope"] == "run" and request["assignment_id"] is not None:
            raise OrchestratorError("run-scoped Owner request cannot bind an assignment")
        if request["status"] == "open" and (request["decision"] is not None or request["resolved_at"] is not None):
            raise OrchestratorError("open Owner request cannot carry a decision")
        if request["status"] == "resolved" and (not isinstance(request["decision"], dict) or set(request["decision"]) != {"disposition", "detail", "provenance", "decided_at"} or request["decision"]["disposition"] not in {"approved", "rejected"}):
            raise OrchestratorError("decided Owner request lacks bound provenance")
    if not isinstance(state["broker_notifications"], list):
        raise OrchestratorError("Broker notifications must be an array")
    for notification in state["broker_notifications"]:
        if not isinstance(notification, dict) or set(notification) != {"notification_id", "kind", "summary", "assignment_ids", "created_at"} or not isinstance(notification["notification_id"], str) or not isinstance(notification["kind"], str) or not isinstance(notification["summary"], str) or not notification["summary"].strip() or not isinstance(notification["assignment_ids"], list) or set(notification["assignment_ids"]) - known or not isinstance(notification["created_at"], (int, float)):
            raise OrchestratorError("Broker notification is malformed")
    terminal = state["terminal"]
    if terminal is not None:
        if not isinstance(terminal, dict) or set(terminal) != {"disposition", "summary", "fact_refs", "incomplete_facts", "finished_at"} or terminal["disposition"] not in TERMINAL_DISPOSITIONS or not isinstance(terminal["summary"], str) or not terminal["summary"].strip() or not isinstance(terminal["fact_refs"], list) or any(not isinstance(item, str) for item in terminal["fact_refs"]) or not isinstance(terminal["incomplete_facts"], list) or any(not isinstance(item, str) or not item.strip() for item in terminal["incomplete_facts"]) or not isinstance(terminal["finished_at"], (int, float)):
            raise OrchestratorError("run terminal disposition is malformed")
        if state["status"] != "finished":
            raise OrchestratorError("terminal disposition requires finished run status")
    cancellation = state["cancellation"]
    if not isinstance(cancellation, dict) or set(cancellation) != {"phase", "request_id", "requested_at", "handled_at", "reason", "provenance"} or cancellation["phase"] not in {"none", "requested", "cancelling", "cancelled", "quarantined"}:
        raise OrchestratorError("snapshot cancellation state is malformed")
    if cancellation["phase"] == "none" and any(cancellation[key] is not None for key in ("request_id", "requested_at", "handled_at", "reason", "provenance")):
        raise OrchestratorError("empty cancellation state cannot carry request evidence")
    if cancellation["phase"] != "none" and (not isinstance(cancellation["request_id"], str) or not cancellation["request_id"].strip() or not isinstance(cancellation["reason"], str) or not cancellation["reason"].strip() or not isinstance(cancellation["provenance"], str) or not cancellation["provenance"].strip() or not isinstance(cancellation["requested_at"], (int, float)) or isinstance(cancellation["requested_at"], bool)):
        raise OrchestratorError("active cancellation state lacks trusted request evidence")
    controller = state["controller"]
    if not isinstance(controller, dict) or set(controller) != {"lock_path"} or not isinstance(controller["lock_path"], str) or not controller["lock_path"].strip():
        raise OrchestratorError("controller lock projection is malformed")


def make_assignment(assignment_id: str, goal: str, *, run_id: str | None = None, assurance_mode: str = "lite", kind: str = "delivery", access_mode: str = "workspace_write", execution_profile: str | None = None, allowed_paths: list[str] | None = None, non_goals: list[str] | None = None, acceptance_criteria: list[str] | None = None, verification_commands: list[str] | None = None, depends_on: list[str] | None = None, external_resources: list[str] | None = None, revision: int = 1, fresh_context: bool = True, workspace_strategy: str = "new", handoff_from: str | None = None, workspace_path: str | None = None, workspace_branch: str | None = None, workspace_base_ref: str | None = None) -> dict[str, Any]:
    if assurance_mode not in {"lite", "full"} or kind not in ASSIGNMENT_KINDS or access_mode not in ACCESS_MODES:
        raise OrchestratorError("unsupported assignment mode or kind")
    if access_mode == "repository_read_only" and any(value is not None for value in (handoff_from, workspace_path, workspace_branch, workspace_base_ref)):
        raise OrchestratorError("read-only assignments cannot declare workspace intent")
    profile = execution_profile or ("worker-full-terra-high" if assurance_mode == "full" else "worker-lite-luna-max")
    assignment = {
        "run_id": run_id or "unbound",
        "assignment_id": assignment_id,
        "kind": kind,
        "revision": revision,
        "goal": goal,
        "non_goals": list(non_goals or []),
        "acceptance_criteria": list(acceptance_criteria or ["The assignment goal is satisfied and all declared verification commands pass."]),
        "assurance_mode": assurance_mode,
        "execution_profile": profile,
        "execution_profile_selection": None,
        "access_mode": access_mode,
        "allowed_paths": list(allowed_paths or []),
        "external_resources": list(external_resources or []),
        "verification_commands": list(verification_commands or []),
        "depends_on": list(depends_on or []),
        "context": {"fresh": fresh_context, "continuation_allowed": True},
        "status": "planned",
        "workspace": None if access_mode == "repository_read_only" else {"strategy": workspace_strategy, "handoff_from": handoff_from, "path": workspace_path, "branch": workspace_branch, "base_ref": workspace_base_ref, "materialized": False, "lease": {"status": "inactive", "acquired_at": None, "released_at": None}},
        "boundary_evidence": {"source_revision": None, "pre_git": _empty_git_boundary(), "post_git": _empty_git_boundary()},
        "worker": {"thread_id": None, "turn_id": None, "status": "pending", "interrupt": {"attempted": False, "acknowledged": False, "requested_at": None, "acknowledged_at": None, "error": None}},
        "result": None,
        "verifier": {"status": "pending" if assurance_mode == "full" else "not_required", "attempts": []},
        "acceptance": None,
    }
    if run_id is None:
        assignment.pop("run_id")
    return assignment


def ready_assignment_ids(state: dict[str, Any]) -> list[str]:
    validate_snapshot(state)
    return _ready_assignment_ids_unchecked(state)


def _ownership_disjoint(assignments: list[dict[str, Any]]) -> bool:
    paths: list[str] = []
    resources: set[str] = set()
    for assignment in assignments:
        if assignment.get("access_mode") == "repository_read_only":
            continue
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


def materialize_workspaces(state: dict[str, Any], assignment_ids: list[str] | None = None, *, catalog: dict[str, Any] | None = None) -> list[dict[str, str]]:
    """Materialize only an explicitly selected, already preflighted Worker cohort."""

    validate_snapshot(state)
    selected = list(assignment_ids or [])
    ready = set(ready_assignment_ids(state))
    if not selected or len(selected) > state["crew"]["capabilities"]["max_active_workers"] or len(selected) != len(set(selected)) or set(selected) - ready:
        raise OrchestratorError("workspace materialization requires an explicit eligible Worker cohort within the resource bound")
    selected_assignments = [next(item for item in state["assignments"] if item["assignment_id"] == assignment_id) for assignment_id in selected]
    root = Path(state["repository_root"])
    specs: list[tuple[dict[str, Any], dict[str, str], bool]] = []
    for assignment in selected_assignments:
        _select_assignment_worker_profile(state, assignment, catalog)
        workspace = assignment["workspace"]
        reuse = workspace["strategy"] == "reuse"
        if reuse:
            previous = next((item for item in state["assignments"] if item["assignment_id"] == workspace["handoff_from"]), None)
            if previous is None or previous["run_id"] != state["run_id"] or previous["status"] != "accepted" or not isinstance(previous.get("acceptance"), dict) or not isinstance(previous["acceptance"].get("handoff"), dict):
                raise OrchestratorError("workspace reuse requires a same-run accepted handoff")
            source = previous["workspace"]
            if not source.get("materialized") or any(source.get(key) is None for key in ("path", "branch", "base_ref")):
                raise OrchestratorError("workspace reuse source is not materialized")
            if workspace["path"] is not None and (workspace["path"] != source["path"] or workspace["branch"] != source["branch"]):
                raise OrchestratorError("workspace reuse intent must match the accepted source workspace")
            workspace.update({"path": source["path"], "branch": source["branch"], "base_ref": previous["acceptance"]["commit"]})
            try:
                validate_serial_reuse(Path(workspace["path"]), previous["acceptance"]["handoff"], state["run_id"])
            except WorkspaceError as error:
                raise OrchestratorError(f"workspace reuse gate failed: {error}") from error
        elif any(workspace.get(key) is None for key in ("path", "branch", "base_ref")):
            raise OrchestratorError("new workspace requires explicit Orchestrator path, branch and base_ref intent")
        _validate_assignment(assignment, root)
        specs.append((assignment, {key: workspace[key] for key in ("path", "branch", "base_ref")}, reuse))
    results: list[dict[str, str]] = []
    for assignment, worktree_spec, reuse in specs:
        workspace = assignment["workspace"]
        with _controller_commit_boundary(state, role="orchestrator", thread_id=state["orchestrator"].get("thread_id"), turn_id=state["orchestrator"]["turn"].get("turn_id")):
            pass
        ready_result = ensure_worktree(root, worktree_spec)
        with _controller_commit_boundary(state, role="orchestrator", thread_id=state["orchestrator"].get("thread_id"), turn_id=state["orchestrator"]["turn"].get("turn_id")):
            workspace["path"] = ready_result["path"]
            workspace["materialized"] = True
            if not reuse:
                workspace["base_ref"] = _git(Path(workspace["path"]), "rev-parse", "HEAD")
            assignment["status"] = "ready"
            _event(state, "workspace_ready", assignment_id=assignment["assignment_id"], reused=reuse, **ready_result)
            _ledger_event(state, "worktree", assignment["assignment_id"], "acquire", "explicit Worker workspace", path=workspace["path"])
            results.append({"assignment_id": assignment["assignment_id"], **ready_result})
    _refresh_crew_projection(state)
    validate_snapshot(state)
    return results


def dispatch_worker(state: dict[str, Any], assignment_id: str, *, worker_runner: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None, state_mutex: threading.RLock | None = None, continuation_message: str | None = None) -> dict[str, Any]:
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
    _select_assignment_worker_profile(state, assignment)
    workspace = assignment["workspace"]
    if assignment["access_mode"] == "workspace_write" and (not isinstance(workspace, dict) or not workspace["materialized"] or workspace["path"] is None):
        raise OrchestratorError("write Worker dispatch requires an explicitly materialized workspace")
    if assignment["access_mode"] == "repository_read_only" and assignment["boundary_evidence"]["source_revision"] is None:
        raise OrchestratorError("read-only Worker dispatch requires a fixed repository revision")
    execution = _profile_for_assignment(state, assignment)
    task = assignment_task(assignment, execution, repository_root=Path(state["repository_root"]))
    if assignment["access_mode"] == "workspace_write":
        assert isinstance(workspace, dict)
        task["writable_roots"] = worker_git_writable_roots(Path(workspace["path"]), workspace["branch"], state["run_id"], assignment_id)
    state_path = Path(state["state_path"])

    mutex = state_mutex or threading.RLock()

    def persist_worker_thread(thread_id: str) -> None:
        with mutex:
            assignment["worker"]["thread_id"] = thread_id
            assignment["worker"]["status"] = "running"
            _event(state, "worker_thread_started", assignment_id=assignment_id, thread_id=thread_id)
            _refresh_crew_projection(state)
            write_json_atomic(state_path, state)

    def persist_worker_turn(thread_id: str, turn_id: str) -> None:
        with mutex:
            assignment["worker"]["thread_id"] = thread_id
            assignment["worker"]["turn_id"] = turn_id
            assignment["worker"]["status"] = "running"
            _event(state, "worker_turn_started", assignment_id=assignment_id, thread_id=thread_id, turn_id=turn_id)
            _refresh_crew_projection(state)
            write_json_atomic(state_path, state)

    def persist_worker_cancelling(request: dict[str, Any]) -> None:
        with mutex:
            state["status"] = "cancelling"
            state["cancellation"] = {"phase": "cancelling", "request_id": request["request_id"], "requested_at": request["requested_at"], "handled_at": None, "reason": request["reason"], "provenance": request["provenance"]}
            write_json_atomic(state_path, state)

    task["control"] = {"run_id": state["run_id"], "state_path": state["state_path"], "artifact_root": state["artifact_root"], "callbacks": {"on_thread_started": persist_worker_thread, "on_turn_started": persist_worker_turn, "on_cancelling": persist_worker_cancelling}}
    with _controller_commit_boundary(
        state,
        role="orchestrator",
        thread_id=state["orchestrator"].get("thread_id"),
        turn_id=state["orchestrator"]["turn"].get("turn_id"),
    ):
        with mutex:
            assignment["status"] = "running"
            assignment["worker"]["status"] = "running"
            if isinstance(assignment["workspace"], dict):
                assignment["workspace"]["lease"] = {"status": "active", "acquired_at": _now(), "released_at": None}
            _refresh_crew_projection(state)
            write_json_atomic(state_path, state)
    runner = worker_runner
    try:
        if runner is not None:
            raw_result = runner(assignment_id, task)
        elif assignment["worker"].get("thread_id"):
            raw_result = continue_assignment(
                task,
                assignment["worker"]["thread_id"],
                continuation_message or "Continue this same assignment after the Orchestrator update. Preserve the existing scope, ownership and acceptance contract, then return the structured Worker result.",
            )
        else:
            raw_result = run_worker(assignment_id, task)
    except BaseException as error:
        raw_result = {"status": "failed", "summary": "Worker dispatch failed before a structured result", "error": str(error), "changed_paths": []}
    if not isinstance(raw_result, dict):
        raw_result = {"status": "failed", "summary": "Worker dispatch returned a non-object result", "changed_paths": []}
    control_outcome = raw_result.get("_control_outcome")
    if not isinstance(control_outcome, dict):
        pending_cancel = read_cancel_request(state_path, state["run_id"])
        if pending_cancel is not None:
            control_outcome = _completed_role_cancel_outcome(
                pending_cancel,
                thread_id=assignment["worker"].get("thread_id") or raw_result.get("worker_thread_id"),
                turn_id=assignment["worker"].get("turn_id") or raw_result.get("worker_turn_id"),
            )
    if isinstance(control_outcome, dict):
        assignment["worker"]["interrupt"]["attempted"] = bool(control_outcome.get("interrupt", {}).get("attempted"))
        assignment["worker"]["interrupt"]["requested_at"] = _now() if assignment["worker"]["interrupt"]["attempted"] else None
        assignment["worker"]["interrupt"]["acknowledged"] = bool(control_outcome.get("interrupt", {}).get("acknowledged"))
        assignment["worker"]["interrupt"]["acknowledged_at"] = _now() if assignment["worker"]["interrupt"]["acknowledged"] else None
        assignment["worker"]["interrupt"]["error"] = control_outcome.get("interrupt", {}).get("error")
        _apply_role_cancel_outcome(state, state_path, control_outcome, "worker")
        raise OrchestratorError(f"Worker turn ended as {control_outcome['status']}")
    if assignment["access_mode"] == "repository_read_only":
        after = _git_boundary(Path(state["repository_root"]))
        with mutex:
            assignment["boundary_evidence"]["post_git"] = after
            before = assignment["boundary_evidence"]["pre_git"]
            if after["availability"] != "observed" or before["head"] != after["head"] or before["porcelain"] != after["porcelain"]:
                _mark_blocked(state, "read_only_worker_boundary_changed", f"repository boundary changed while read-only Worker {assignment_id} was active")
                write_json_atomic(state_path, state)
                raise OrchestratorError("read-only Worker repository boundary changed during execution")
        if raw_result.get("commit") is None:
            raw_result["commit"] = assignment["boundary_evidence"]["source_revision"]
        raw_result.setdefault("changed_paths", [])
    elif isinstance(workspace, dict) and raw_result.get("commit") is None and Path(workspace["path"]).is_dir():
        raw_result["commit"] = _git(Path(workspace["path"]), "rev-parse", "HEAD")
    with mutex:
        return record_worker_result(state, assignment_id, raw_result)


def start_worker_cohort(state: dict[str, Any], assignment_ids: list[str], *, worker_runner: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None, continuation_messages: dict[str, str] | None = None) -> list[dict[str, Any]]:
    """Preflight and run exactly the Worker cohort selected by the Orchestrator."""

    validate_snapshot(state)
    selected = list(assignment_ids)
    maximum = state["crew"]["capabilities"]["max_active_workers"]
    if not selected or len(selected) > maximum or len(selected) != len(set(selected)):
        raise OrchestratorError(f"start_workers requires one to {maximum} unique assignment ids")
    if state["crew"]["observed"]["active_worker_ids"]:
        raise OrchestratorError("a new Worker cohort cannot start while another Worker is active")
    ready = set(ready_assignment_ids(state))
    if set(selected) - ready:
        raise OrchestratorError("start_workers may name only currently eligible assignments")
    assignments = [next(item for item in state["assignments"] if item["assignment_id"] == assignment_id) for assignment_id in selected]
    if not _ownership_disjoint(assignments):
        raise OrchestratorError("selected Worker cohort has overlapping write ownership or external resources")
    for assignment in assignments:
        if assignment["kind"] != "delivery" or assignment["worker"]["status"] == "running":
            raise OrchestratorError("selected assignment cannot start a delivery Worker")
        _validate_assignment(assignment, Path(state["repository_root"]))
    try:
        catalog = fetch_model_catalog()
        for assignment in assignments:
            _select_assignment_worker_profile(state, assignment, catalog)
    except (ExecutionProfileError, OrchestratorError) as error:
        raise OrchestratorError(f"Worker cohort profile preflight failed before workspace materialization: {error}") from error
    state["crew"]["capabilities"]["runtime"] = {"cohort_parallelism_available": maximum > 1, "observed_at": _now(), "evidence": "model_catalog_and_runtime_policy"}
    read_only_assignments = [assignment for assignment in assignments if assignment["access_mode"] == "repository_read_only"]
    if read_only_assignments:
        boundary = _git_boundary(Path(state["repository_root"]))
        if boundary["availability"] != "observed" or not boundary["head"]:
            raise OrchestratorError("read-only Worker cohort requires an observable repository revision")
        for assignment in read_only_assignments:
            existing = assignment["boundary_evidence"]
            if existing["source_revision"] is None:
                assignment["boundary_evidence"] = {"source_revision": boundary["head"], "pre_git": dict(boundary), "post_git": _empty_git_boundary()}
            elif existing["source_revision"] != boundary["head"] or existing["pre_git"]["porcelain"] != boundary["porcelain"]:
                raise OrchestratorError("read-only Worker continuation requires the original fixed repository boundary")
            else:
                assignment["boundary_evidence"]["post_git"] = _empty_git_boundary()
    write_assignments = [assignment["assignment_id"] for assignment in assignments if assignment["access_mode"] == "workspace_write"]
    if write_assignments:
        materialize_workspaces(state, write_assignments, catalog=catalog)
    state_mutex = threading.RLock()
    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=len(selected), thread_name_prefix=f"crew-{state['run_id']}") as pool:
        futures = {
            pool.submit(
                dispatch_worker,
                state,
                assignment_id,
                worker_runner=worker_runner,
                state_mutex=state_mutex,
                continuation_message=(continuation_messages or {}).get(assignment_id),
            ): assignment_id
            for assignment_id in selected
        }
        for future in as_completed(futures):
            assignment_id = futures[future]
            try:
                results[assignment_id] = future.result()
            except BaseException as error:
                results[assignment_id] = {"assignment_id": assignment_id, "status": "failed", "summary": f"Worker capability failed: {error}"}
    with state_mutex:
        _refresh_crew_projection(state)
        write_json_atomic(Path(state["state_path"]), state)
    return [results[assignment_id] for assignment_id in selected]


def _normalize_worker_result(raw: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    status = raw.get("status")
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
        "worker_turn_id": raw.get("worker_turn_id") or raw.get("turn_id"),
    }


def record_worker_result(state: dict[str, Any], assignment_id: str, raw_result: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None:
        raise OrchestratorError(f"unknown assignment: {assignment_id}")
    if raw_result.get("assignment_id") not in {None, assignment_id} or raw_result.get("revision") not in {None, assignment["revision"]}:
        raise OrchestratorError("Worker result is bound to a different assignment revision")
    enriched_result = dict(raw_result)
    if "changed_paths" not in enriched_result and isinstance(assignment.get("workspace"), dict) and isinstance(assignment["workspace"].get("path"), str):
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
    with _controller_commit_boundary(
        state,
        role="worker",
        thread_id=assignment["worker"].get("thread_id") or result.get("worker_thread_id"),
        turn_id=assignment["worker"].get("turn_id") or result.get("worker_turn_id"),
    ):
        assignment["result"] = result
        if assignment["assurance_mode"] == "full":
            assignment["verifier"]["status"] = "pending"
        assignment["worker"]["thread_id"] = result.get("worker_thread_id") or assignment["worker"].get("thread_id")
        assignment["worker"]["turn_id"] = result.get("worker_turn_id") or assignment["worker"].get("turn_id")
        # A structured result is a terminal envelope for the current Worker turn.
        # The thread remains resumable, but it no longer owns an active write lease.
        assignment["worker"]["status"] = "stopped"
        if isinstance(assignment["workspace"], dict):
            assignment["workspace"]["lease"] = {"status": "released", "acquired_at": assignment["workspace"]["lease"].get("acquired_at"), "released_at": _now()}
        assignment["status"] = {"succeeded": "submitted", "needs_orchestrator": "awaiting_orchestrator", "needs_owner": "awaiting_owner", "failed": "failed"}[result["status"]]
        if result["status"] == "needs_owner":
            state["owner_requests"].append({"request_id": uuid.uuid4().hex, "scope": "assignment", "assignment_id": assignment_id, "category": result["owner_request"]["category"], "detail": result["owner_request"]["detail"], "status": "open", "requested_at": _now(), "resolved_at": None, "decision": None})
        _event(state, "worker_result_recorded", assignment_id=assignment_id, worker_status=result["status"])
        _ledger_event(state, "assignment", assignment_id, "result_recorded", "structured Worker result accepted by control plane", worker_status=result["status"])
        _refresh_crew_projection(state)
        validate_snapshot(state)
    return result


def _verification_passed(values: list[dict[str, Any]]) -> bool:
    return bool(values) and all(isinstance(item, dict) and item.get("exit_code") == 0 for item in values)


def _verifier_binding(state: dict[str, Any], assignment: dict[str, Any]) -> dict[str, Any]:
    result = assignment.get("result")
    if not isinstance(result, dict) or result.get("status") != "succeeded":
        raise OrchestratorError("Full verifier requires a successful submitted Worker result")
    if not _verification_passed(result.get("verification", [])):
        raise OrchestratorError("Full verifier requires successful structured Worker verification evidence")
    workspace = assignment["workspace"]
    if not isinstance(result.get("commit"), str):
        raise OrchestratorError("Full verifier requires a fixed Worker revision")
    if assignment["access_mode"] == "repository_read_only":
        boundary = _git_boundary(Path(state["repository_root"]))
        expected = assignment["boundary_evidence"]
        if boundary["availability"] != "observed" or boundary["head"] != expected["source_revision"] or boundary["porcelain"] != expected["pre_git"]["porcelain"] or result["commit"] != expected["source_revision"]:
            raise OrchestratorError("Full read-only verifier requires the unchanged repository boundary observed by the Worker")
        worktree = Path(state["repository_root"])
        base_commit = head_commit = expected["source_revision"]
    else:
        if not isinstance(workspace, dict) or not isinstance(workspace.get("path"), str):
            raise OrchestratorError("Full delivery verifier requires a materialized workspace")
        worktree = Path(workspace["path"])
        head_commit = _git(worktree, "rev-parse", "HEAD")
        if head_commit != result["commit"] or git_status(worktree):
            raise OrchestratorError("Full verifier requires a clean workspace at the reported Worker commit")
        base_commit = _git(worktree, "rev-parse", workspace["base_ref"])
    return {
        "run_id": state["run_id"],
        "assignment_id": assignment["assignment_id"],
        "revision": assignment["revision"],
        "base_commit": base_commit,
        "head_commit": head_commit,
        "worker_result_digest": _digest(result),
        "workspace_path": str(worktree.resolve()),
        "goal": assignment["goal"],
        "non_goals": assignment["non_goals"],
        "acceptance_criteria": assignment["acceptance_criteria"],
        "verification_commands": assignment["verification_commands"],
    }


def _apply_role_cancel_outcome(state: dict[str, Any], state_path: Path, outcome: dict[str, Any], role: str) -> None:
    request = outcome.get("cancel_request")
    if not isinstance(request, dict):
        raise OrchestratorError("role cancellation outcome is missing its durable request")
    state["cancellation"] = {
        "phase": "cancelled" if outcome["status"] == "cancelled" else "quarantined",
        "request_id": request["request_id"],
        "requested_at": request["requested_at"],
        "handled_at": _now(),
        "reason": request["reason"],
        "provenance": request["provenance"],
    }
    if outcome["status"] == "cancelled":
        state["status"] = "cancelled"
        for assignment in state["assignments"]:
            if assignment["status"] not in {"accepted", "cancelled"}:
                assignment["status"] = "cancelled"
                assignment["worker"]["status"] = "stopped"
                if isinstance(assignment["workspace"], dict):
                    assignment["workspace"]["lease"] = {"status": "released", "acquired_at": assignment["workspace"]["lease"].get("acquired_at"), "released_at": _now()}
        _refresh_crew_projection(state)
        _event(state, "run_cancelled", request_id=request["request_id"], role=role)
    else:
        _mark_blocked(state, "turn_stop_unconfirmed", f"{role} turn stop could not be confirmed")
    write_json_atomic(state_path, state)
    # Canonical terminal state must become durable before the owner request is
    # acknowledged by removing its sidecar.  A residual idempotent request is
    # safer than losing the only durable cancel intent after a state write fault.
    clear_cancel_request(state_path, request["request_id"])


def _completed_role_cancel_outcome(
    request: dict[str, Any],
    *,
    thread_id: str | None,
    turn_id: str | None,
    terminal_status: str = "completed",
) -> dict[str, Any]:
    """Bind a late explicit cancel to an already terminal role turn."""

    return {
        "status": "cancelled",
        "thread_id": thread_id,
        "turn_id": turn_id,
        "cancel_request": request,
        "interrupt": {"attempted": False, "acknowledged": False, "error": None},
        "terminal": {"observed": True, "status": terminal_status, "source": "turn/completed"},
        "notifications": [],
        "history": None,
    }


def _default_full_verifier_runner(state: dict[str, Any], assignment: dict[str, Any], request: dict[str, Any]) -> dict[str, Any]:
    state_path = Path(state["state_path"])
    artifact_root = Path(state["artifact_root"])

    def on_thread_started(thread_id: str) -> None:
        _event(state, "verifier_thread_started", assignment_id=assignment["assignment_id"], thread_id=thread_id)
        write_json_atomic(state_path, state)

    def on_turn_started(thread_id: str, turn_id: str) -> None:
        _event(state, "verifier_turn_started", assignment_id=assignment["assignment_id"], thread_id=thread_id, turn_id=turn_id)
        write_json_atomic(state_path, state)

    def on_cancelling(cancel_request: dict[str, Any]) -> None:
        state["status"] = "cancelling"
        state["cancellation"] = {"phase": "cancelling", "request_id": cancel_request["request_id"], "requested_at": cancel_request["requested_at"], "handled_at": None, "reason": cancel_request["reason"], "provenance": cancel_request["provenance"]}
        write_json_atomic(state_path, state)

    prompt = (
        "You are a fresh independent Codex Crew Verifier. Review only the fixed comparison point below. "
        "You are read-only, cannot create subagents, and must not change the workspace. Return exactly one JSON object with status passed|failed|blocked, summary, findings, and verification. "
        f"Binding={json.dumps(request, ensure_ascii=False)}"
    )
    outcome = run_role_turn(
        state_path=state_path,
        run_id=state["run_id"],
        role="verifier",
        cwd=Path(request["workspace_path"]),
        prompt=prompt,
        execution=request["profile"],
        stderr_path=artifact_root / f"verifier-{assignment['assignment_id']}.stderr.log",
        sandbox="read-only",
        thread_id=None,
        approval_policy="never",
        enable_multi_agent=False,
        ephemeral=True,
        on_thread_started=on_thread_started,
        on_turn_started=on_turn_started,
        on_cancelling=on_cancelling,
    )
    if outcome["status"] in {"cancelled", "quarantined"}:
        _apply_role_cancel_outcome(state, state_path, outcome, "verifier")
        raise OrchestratorError(f"Verifier turn ended as {outcome['status']}")
    if _terminal_status(outcome["status"]) != "completed":
        return {"status": "blocked", "summary": f"Verifier terminal status was {outcome['status']}", "findings": [], "verification": [], "_controller_evidence": {"thread_id": outcome["thread_id"], "turn_id": outcome["turn_id"]}}
    evidence = outcome["notifications"] + [outcome["history"]]
    if walk_items(evidence):
        return {"status": "blocked", "summary": "Verifier attempted recursive agent delegation", "findings": [], "verification": [], "_controller_evidence": {"thread_id": outcome["thread_id"], "turn_id": outcome["turn_id"]}}
    messages = walk_root_agent_messages(evidence, outcome["thread_id"])
    parsed = _parse_json_message(messages[-1]) if messages else None
    if not isinstance(parsed, dict):
        parsed = {"status": "blocked", "summary": "Verifier did not return valid structured evidence", "findings": [], "verification": []}
    parsed["_controller_evidence"] = {"thread_id": outcome["thread_id"], "turn_id": outcome["turn_id"]}
    return parsed


def run_full_verifier(state: dict[str, Any], assignment_id: str, verifier_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Run and persist one fresh, read-only, non-recursive Full verifier attempt.

    Agent-supplied provenance is ignored.  The controller binds the verdict to
    the exact Worker result and comparison point before it can be consumed by
    ``accept_assignment``.
    """

    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None:
        raise OrchestratorError(f"unknown assignment: {assignment_id}")
    if assignment["assurance_mode"] != "full":
        raise OrchestratorError("independent verifier is only required for Full assignments")
    binding = _verifier_binding(state, assignment)
    try:
        profiles = load_execution_profiles(Path(__file__).resolve().parents[1])
        selection = select_available_verifier_profile(profiles, "full", fetch_model_catalog())
    except ExecutionProfileError as error:
        assignment["verifier"]["status"] = "blocked"
        assignment["status"] = "verifying"
        _refresh_crew_projection(state)
        raise OrchestratorError(f"Full verifier profile preflight failed: {error}") from error
    request = {**binding, "profile": selection["selected_profile"], "fresh_context": True, "sandbox": "read-only", "network_access": False, "recursive": False}
    assignment["verifier"]["status"] = "running"
    _event(state, "verifier_started", assignment_id=assignment_id, worker_result_digest=binding["worker_result_digest"])
    state_path = Path(state["state_path"])
    write_json_atomic(state_path, state)
    pending_cancel = read_cancel_request(state_path, state["run_id"])
    if pending_cancel is not None:
        outcome = {"status": "cancelled", "cancel_request": pending_cancel}
        _apply_role_cancel_outcome(state, state_path, outcome, "verifier")
        raise OrchestratorError("run cancelled before Full verifier start")
    if verifier_runner is None:
        raw = _default_full_verifier_runner(state, assignment, request)
    else:
        raw = verifier_runner(json.loads(json.dumps(request, ensure_ascii=False)))
    if not isinstance(raw, dict):
        raw = {"status": "blocked", "summary": "Verifier returned a non-object result", "findings": [], "verification": []}
    pending_cancel = read_cancel_request(state_path, state["run_id"])
    if pending_cancel is not None:
        controller_evidence = raw.get("_controller_evidence") if isinstance(raw.get("_controller_evidence"), dict) else {}
        outcome = _completed_role_cancel_outcome(
            pending_cancel,
            thread_id=controller_evidence.get("thread_id"),
            turn_id=controller_evidence.get("turn_id"),
        )
        _apply_role_cancel_outcome(state, state_path, outcome, "verifier")
        raise OrchestratorError("run cancelled after Full verifier turn and before verdict application")
    status = raw.get("status") if raw.get("status") in {"passed", "failed", "blocked"} else "blocked"
    controller_evidence = raw.get("_controller_evidence") if isinstance(raw.get("_controller_evidence"), dict) else {}
    if any(not isinstance(controller_evidence.get(key), str) or not controller_evidence[key].strip() for key in ("thread_id", "turn_id")):
        assignment["verifier"]["status"] = "blocked"
        assignment["status"] = "verifying"
        _refresh_crew_projection(state)
        raise OrchestratorError("Full verifier provenance is missing; synthetic independence evidence is forbidden")
    attempt = {
        "schema_version": VERIFIER_RESULT_SCHEMA_VERSION,
        **{key: binding[key] for key in ("run_id", "assignment_id", "revision", "base_commit", "head_commit", "worker_result_digest")},
        "profile": selection["selected_profile"]["id"],
        "thread_id": controller_evidence["thread_id"],
        "turn_id": controller_evidence["turn_id"],
        "status": status,
        "independent": True,
        "recursive": False,
        "summary": raw.get("summary") if isinstance(raw.get("summary"), str) and raw["summary"].strip() else "Verifier returned no summary",
        "findings": raw.get("findings") if isinstance(raw.get("findings"), list) else [],
        "verification": raw.get("verification") if isinstance(raw.get("verification"), list) else [],
        "observed_at": _now(),
    }
    with _controller_commit_boundary(
        state,
        role="verifier",
        thread_id=controller_evidence["thread_id"],
        turn_id=controller_evidence["turn_id"],
    ):
        worktree = Path(binding["workspace_path"])
        if _git(worktree, "rev-parse", "HEAD") != binding["head_commit"] or git_status(worktree):
            attempt["status"] = "blocked"
            attempt["summary"] = "Workspace changed while the independent verifier was running"
        assignment["verifier"]["attempts"].append(attempt)
        assignment["verifier"]["status"] = attempt["status"]
        if attempt["status"] == "passed":
            assignment["status"] = "submitted"
        elif attempt["status"] == "failed":
            assignment["status"] = "rejected"
        else:
            assignment["status"] = "verifying"
        _event(state, "verifier_completed", assignment_id=assignment_id, verifier_status=attempt["status"])
        _refresh_crew_projection(state)
        validate_snapshot(state)
    return attempt


def accept_assignment(state: dict[str, Any], assignment_id: str) -> dict[str, Any]:
    validate_snapshot(state)
    assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None)
    if assignment is None or assignment.get("result") is None or assignment["result"].get("status") != "succeeded":
        raise OrchestratorError("only a successful submitted assignment can be accepted")
    result = assignment["result"]
    changed = validate_worker_diff(assignment, result.get("changed_paths", []))
    if assignment["access_mode"] == "repository_read_only":
        boundary = _git_boundary(Path(state["repository_root"]))
        evidence = assignment["boundary_evidence"]
        if changed or result.get("commit") != evidence["source_revision"] or boundary["availability"] != "observed" or boundary["head"] != evidence["source_revision"] or boundary["porcelain"] != evidence["pre_git"]["porcelain"]:
            raise OrchestratorError("read-only acceptance requires an unchanged fixed repository boundary")
    elif assignment["kind"] == "delivery":
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
        attempts = assignment["verifier"]["attempts"]
        if not attempts:
            raise FullVerificationRequired("Full acceptance requires an independent one-shot verifier")
        verifier = attempts[-1]
        expected_binding = _verifier_binding(state, assignment)
        if verifier.get("status") != "passed" or verifier.get("independent") is not True or verifier.get("recursive") is not False or any(verifier.get(key) != expected_binding[key] for key in ("run_id", "assignment_id", "revision", "base_commit", "head_commit", "worker_result_digest")):
            raise FullVerificationRequired("Full acceptance requires the latest controller-owned verifier result for this Worker result")
    handoff = None
    if assignment["kind"] == "delivery" and assignment["access_mode"] == "workspace_write":
        try:
            handoff = serial_handoff_evidence(Path(assignment["workspace"]["path"]), result["commit"], verification, state["run_id"])
        except WorkspaceError as error:
            raise OrchestratorError(f"serial promotion boundary failed: {error}") from error
    acceptance = {"schema_version": ACCEPTANCE_SCHEMA_VERSION, "assignment_id": assignment_id, "revision": assignment["revision"], "worker_result_digest": _digest(result), "commit": result.get("commit"), "changed_paths": changed, "verification": verification, "verifier": verifier, "handoff": handoff, "disposition": "accepted", "accepted_at": _now()}
    assignment["acceptance"] = acceptance
    assignment["status"] = "accepted"
    state["acceptances"].append(acceptance)
    _event(state, "assignment_accepted", assignment_id=assignment_id, full=assignment["assurance_mode"] == "full")
    _refresh_crew_projection(state)
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
    common = {"schema_version", "run_id", "action", "summary", "crew_intent", "broker_notifications"}
    allowed = {
        "dispatch": common | {"assignments"},
        "control": common | {"operation", "assignment_ids", "assignment_id", "message", "reason"},
        "ask_owner": common | {"request"},
        "finish": common | {"disposition", "fact_refs", "incomplete_facts"},
    }[value["action"]]
    if set(value) - allowed:
        return None
    if not isinstance(value.get("summary", ""), str) or not value["summary"].strip():
        return None
    if value["action"] == "dispatch" and not isinstance(value.get("assignments"), list):
        return None
    if value["action"] == "control" and value.get("operation") not in CONTROL_OPERATIONS:
        return None
    if value["action"] == "control":
        operation = value["operation"]
        if operation == "start_workers" and (not isinstance(value.get("assignment_ids"), list) or not value["assignment_ids"] or any(key in value for key in ("assignment_id", "message", "reason"))):
            return None
        if operation == "continue_worker" and (not isinstance(value.get("assignment_id"), str) or not isinstance(value.get("message"), str) or any(key in value for key in ("assignment_ids", "reason"))):
            return None
        if operation in {"run_verifier", "accept"} and (not isinstance(value.get("assignment_id"), str) or any(key in value for key in ("assignment_ids", "message", "reason"))):
            return None
        if operation == "cancel_assignment" and (not isinstance(value.get("assignment_id"), str) or not isinstance(value.get("reason"), str) or any(key in value for key in ("assignment_ids", "message"))):
            return None
    if value["action"] == "ask_owner":
        request = value.get("request")
        if not isinstance(request, dict) or request.get("scope") not in {"assignment", "run"} or request.get("category") not in OWNER_CATEGORIES or not isinstance(request.get("detail"), str) or not request["detail"].strip():
            return None
    if value["action"] == "finish" and (value.get("disposition") not in TERMINAL_DISPOSITIONS or not isinstance(value.get("fact_refs"), list) or not value["fact_refs"] or not isinstance(value.get("incomplete_facts"), list)):
        return None
    return value


def _apply_turn_annotations(state: dict[str, Any], turn: dict[str, Any]) -> None:
    intent = turn.get("crew_intent")
    if intent is not None:
        if not isinstance(intent, dict) or set(intent) != {"shape", "rationale"} or intent.get("shape") not in CREW_INTENT_SHAPES or not isinstance(intent.get("rationale"), str) or not intent["rationale"].strip():
            raise OrchestratorError("Crew intent update is malformed")
        state["crew"]["intent"] = {"shape": intent["shape"], "rationale": intent["rationale"].strip(), "updated_at": _now()}
    notification_kind_map = {"crew_intent_changed": "crew_intent_changed", "material_plan_change": "material_plan_change", "workspace_decision_changed": "workspace_changed", "delivery_risk": "material_plan_change", "owner_attention": "owner_request"}
    for notification in turn.get("broker_notifications", []):
        if not isinstance(notification, dict) or notification.get("kind") not in notification_kind_map:
            raise OrchestratorError("Broker notification input is malformed")
        _append_broker_notification(state, notification_kind_map[notification["kind"]], notification.get("summary"), notification.get("assignment_ids"))


def _assignment_from_definition(state: dict[str, Any], proposed: dict[str, Any]) -> dict[str, Any]:
    required = {"assignment_id", "kind", "revision", "goal", "non_goals", "acceptance_criteria", "assurance_mode", "execution_profile", "access_mode", "allowed_paths", "external_resources", "verification_commands", "depends_on", "context", "workspace"}
    if not isinstance(proposed, dict) or set(proposed) != required or proposed.get("kind") != "delivery" or not isinstance(proposed.get("context"), dict) or set(proposed["context"]) != {"fresh", "continuation_allowed"}:
        raise OrchestratorError("dispatch assignment definition is malformed")
    workspace = proposed["workspace"]
    if proposed["access_mode"] == "repository_read_only" and workspace is not None:
        raise OrchestratorError("read-only assignment dispatch must use workspace=null")
    if proposed["access_mode"] == "workspace_write" and (not isinstance(workspace, dict) or set(workspace) != {"strategy", "handoff_from", "path", "branch", "base_ref"}):
        raise OrchestratorError("dispatch workspace intent is malformed")
    return make_assignment(
        proposed["assignment_id"],
        proposed["goal"],
        run_id=state["run_id"],
        assurance_mode=proposed["assurance_mode"],
        access_mode=proposed["access_mode"],
        execution_profile=proposed["execution_profile"],
        allowed_paths=proposed["allowed_paths"],
        non_goals=proposed["non_goals"],
        acceptance_criteria=proposed["acceptance_criteria"],
        verification_commands=proposed["verification_commands"],
        depends_on=proposed["depends_on"],
        external_resources=proposed["external_resources"],
        revision=proposed["revision"],
        fresh_context=proposed["context"]["fresh"],
        workspace_strategy=workspace["strategy"] if isinstance(workspace, dict) else "new",
        handoff_from=workspace["handoff_from"] if isinstance(workspace, dict) else None,
        workspace_path=workspace["path"] if isinstance(workspace, dict) else None,
        workspace_branch=workspace["branch"] if isinstance(workspace, dict) else None,
        workspace_base_ref=workspace["base_ref"] if isinstance(workspace, dict) else None,
    )


def apply_orchestrator_turn(state: dict[str, Any], turn: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    if turn.get("schema_version") != ORCHESTRATOR_TURN_SCHEMA_VERSION or turn.get("run_id") != state["run_id"]:
        raise OrchestratorError("Orchestrator turn is not bound to this run")
    action = turn["action"]
    state["last_message"] = turn.get("summary", "")
    if action == "dispatch":
        additions = turn.get("assignments", [])
        if not additions:
            raise OrchestratorError("dispatch requires at least one assignment")
        candidate = json.loads(json.dumps(state, ensure_ascii=False))
        existing = {item["assignment_id"]: item for item in candidate["assignments"]}
        for proposed in additions:
            assignment = _assignment_from_definition(candidate, proposed)
            previous = existing.get(assignment["assignment_id"])
            if previous is None:
                if assignment["revision"] != 1:
                    raise OrchestratorError("new assignment revision must begin at 1")
                candidate["assignments"].append(assignment)
            else:
                if previous["status"] in {"running", "verifying", "accepted", "cancelled"} or previous["worker"]["status"] == "running" or assignment["revision"] != previous["revision"] + 1:
                    raise OrchestratorError("assignment revision requires an inactive, unaccepted predecessor and revision + 1")
                index = next(index for index, item in enumerate(candidate["assignments"]) if item["assignment_id"] == assignment["assignment_id"])
                candidate["assignments"][index] = assignment
            existing[assignment["assignment_id"]] = assignment
        _refresh_crew_projection(candidate)
        validate_snapshot(candidate)
        state.clear()
        state.update(candidate)
        _event(state, "assignments_defined", assignment_ids=[item["assignment_id"] for item in additions])
        for assignment_id in [item["assignment_id"] for item in additions]:
            _append_broker_notification(state, "assignment_defined", f"Assignment {assignment_id} was defined or revised by the Orchestrator.", [assignment_id])
    elif action == "ask_owner":
        request = turn["request"]
        if request["scope"] == "assignment" and request["assignment_id"] not in {item["assignment_id"] for item in state["assignments"]}:
            raise OrchestratorError("assignment-scoped Owner request references an unknown assignment")
        state["owner_requests"].append({"request_id": uuid.uuid4().hex, **request, "status": "open", "requested_at": _now(), "resolved_at": None, "decision": None})
        _event(state, "owner_requested", category=request["category"])
    elif action == "control":
        operation = turn["operation"]
        assignment_id = turn.get("assignment_id")
        assignment = next((item for item in state["assignments"] if item["assignment_id"] == assignment_id), None) if assignment_id else None
        if operation != "start_workers" and assignment is None:
            raise OrchestratorError("control operation requires an assignment_id")
        if operation == "continue_worker":
            if assignment["status"] not in {"awaiting_orchestrator", "rejected", "ready", "planned"} or not assignment["worker"].get("thread_id"):
                raise OrchestratorError("assignment cannot be continued from its current status")
            assignment["status"] = "ready"
        elif operation == "cancel_assignment":
            if assignment["worker"]["status"] == "running" or assignment["status"] == "running":
                raise OrchestratorError("active assignment cancellation must use the run cancel channel")
            assignment["status"] = "cancelled"
            assignment["worker"]["status"] = "stopped"
            if isinstance(assignment["workspace"], dict):
                assignment["workspace"]["lease"] = {"status": "released", "acquired_at": assignment["workspace"]["lease"].get("acquired_at"), "released_at": _now()}
            for request in state["owner_requests"]:
                if request["status"] == "open" and request["assignment_id"] == assignment_id:
                    request["status"] = "cancelled"
                    request["resolved_at"] = _now()
        elif operation == "accept":
            if "verifier_result" in turn:
                raise OrchestratorError("Orchestrator cannot supply verifier evidence")
            accept_assignment(state, assignment_id)
    elif action == "finish":
        if any(item["worker"]["status"] == "running" or item["verifier"]["status"] == "running" for item in state["assignments"]):
            raise OrchestratorError("Orchestrator cannot finish while Worker or Verifier capability is active")
        if turn["disposition"] == "succeeded" and any(item["status"] not in {"accepted", "cancelled"} for item in state["assignments"]):
            raise OrchestratorError("succeeded finish requires every non-cancelled assignment to be accepted")
        if turn["disposition"] != "succeeded" and not turn["incomplete_facts"]:
            raise OrchestratorError("non-succeeded finish requires explicit incomplete facts")
        state["terminal"] = {"disposition": turn["disposition"], "summary": turn["summary"], "fact_refs": list(turn["fact_refs"]), "incomplete_facts": list(turn["incomplete_facts"]), "finished_at": _now()}
        state["status"] = "finished"
        _event(state, "run_finished", disposition=turn["disposition"])
    _apply_turn_annotations(state, turn)
    _refresh_crew_projection(state)
    _event(state, "orchestrator_action", action=action)
    validate_snapshot(state)
    return state


def record_broker_message(state: dict[str, Any], message: str, *, kind: str = "ordinary_correction", provenance: str = "broker", request_id: str | None = None, decision: dict[str, str] | None = None) -> dict[str, Any]:
    validate_snapshot(state)
    if not isinstance(message, str) or not message.strip() or not isinstance(provenance, str) or not provenance.strip():
        raise OrchestratorError("broker message must not be empty")
    if kind not in {"ordinary_correction", "owner_decision"}:
        raise OrchestratorError("unsupported broker message kind")
    normalized_decision = None
    if kind == "ordinary_correction":
        if request_id is not None or decision is not None:
            raise OrchestratorError("ordinary Broker correction cannot carry Owner decision fields")
    else:
        if not isinstance(request_id, str) or not request_id.strip() or not isinstance(decision, dict) or set(decision) != {"disposition", "detail"} or decision["disposition"] not in {"approved", "rejected"} or not isinstance(decision["detail"], str) or not decision["detail"].strip():
            raise OrchestratorError("Owner decision must bind request_id, disposition and detail")
        request = next((item for item in state["owner_requests"] if item["request_id"] == request_id and item["status"] == "open"), None)
        if request is None:
            raise OrchestratorError("Owner decision references no open request")
        decided_at = _now()
        normalized_decision = dict(decision)
        request["status"] = "resolved"
        request["resolved_at"] = decided_at
        request["decision"] = {**normalized_decision, "provenance": provenance, "decided_at": decided_at}
        if request["scope"] == "assignment":
            assignment = next(item for item in state["assignments"] if item["assignment_id"] == request["assignment_id"])
            if assignment["status"] == "awaiting_owner":
                assignment["status"] = "awaiting_orchestrator"
    state["messages"].append({"message_id": uuid.uuid4().hex, "kind": kind, "provenance": provenance, "body": message, "request_id": request_id, "decision": normalized_decision, "at": _now()})
    _refresh_crew_projection(state)
    _event(state, "broker_message_received", message_kind=kind)
    validate_snapshot(state)
    return state["messages"][-1]


def _orchestrator_snapshot_view(state: dict[str, Any]) -> dict[str, Any]:
    """Project decision facts without making the prompt a second state store."""

    assignments = []
    for assignment in state["assignments"]:
        if assignment["status"] in {"accepted", "cancelled"}:
            continue
        result = assignment.get("result") if isinstance(assignment.get("result"), dict) else None
        workspace = assignment["workspace"]
        assignments.append(
            {
                "assignment_id": assignment["assignment_id"],
                "revision": assignment["revision"],
                "status": assignment["status"],
                "goal": assignment["goal"],
                "depends_on": assignment["depends_on"],
                "assurance_mode": assignment["assurance_mode"],
                "access_mode": assignment["access_mode"],
                "workspace": None if workspace is None else {"strategy": workspace["strategy"], "handoff_from": workspace["handoff_from"], "path": workspace["path"], "branch": workspace["branch"], "base_ref": workspace["base_ref"], "materialized": workspace["materialized"], "lease": workspace["lease"]},
                "boundary_evidence": assignment["boundary_evidence"],
                "worker": {"thread_id": assignment["worker"]["thread_id"], "status": assignment["worker"]["status"]},
                "latest_result": None if result is None else {"status": result.get("status"), "summary": result.get("summary"), "commit": result.get("commit")},
                "verifier": {"status": assignment["verifier"]["status"], "attempt_count": len(assignment["verifier"]["attempts"])},
            }
        )
    return {
        "run_id": state["run_id"],
        "status": state["status"],
        "crew": state["crew"],
        "assignments": assignments,
        "recent_acceptances": state["acceptances"][-5:],
        "owner_requests": _open_owner_requests(state),
        "recent_broker_messages": state["messages"][-10:],
        "broker_notifications": state["broker_notifications"][-10:],
        "terminal": state["terminal"],
        "quarantine": state["quarantine"],
        "cancellation": state["cancellation"],
    }


def _orchestrator_prompt(state: dict[str, Any], incoming: str = "") -> str:
    view = _orchestrator_snapshot_view(state)
    return (
        "You are the single Codex Crew Orchestrator. You may inspect the repository and state but must not modify business files. "
        "Only your structured actions are canonical scheduling decisions; Broker suggestions are non-canonical input. "
        "You control assignment routing and Worker acceptance; each Worker owns one cohesive delivery including package, implementation, review loop, and internal T1-T5 steps unless authority, write ownership, delivery responsibility, or acceptance boundary materially changes. "
        "One run may span multiple Issues, branches, worktrees, and PRs. You explicitly define assignments, choose repository_read_only or workspace_write access, choose workspace intent only for writers, start selected Worker cohorts, run Full verifiers, accept deliveries, and finish the run. Defining an assignment never starts it, and Worker success never starts a Verifier. "
        "Maintain Crew intent and notify the Broker of material changes; ordinary implementation choices do not require Owner approval. Fresh context, Worker use, assurance, branch, worktree, and active writer count are independent facts. "
        f"Run issue={state['issue']}. Decision view={json.dumps(view, ensure_ascii=False)}. The full canonical snapshot remains at {state['state_path']!r}.\n"
        f"Incoming broker message={incoming!r}. Return exactly one JSON object conforming to codex-crew.orchestrator-turn.v0.3 with action dispatch/control/ask_owner/finish."
    )


def run_orchestrator_turn(state: dict[str, Any], state_path: Path, *, message: str = "", observation_interval_seconds: int = DEFAULT_OBSERVATION_INTERVAL_SECONDS, resume: bool = True, worker_runner: Callable[[str, dict[str, Any]], dict[str, Any]] | None = None, verifier_runner: Callable[[dict[str, Any]], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Drive one read-only Orchestrator turn through the App Server."""

    validate_snapshot(state)
    if state["status"] not in {"running", "awaiting_owner"}:
        raise OrchestratorError(f"Orchestrator turn cannot start while run status is {state['status']}")
    if observation_interval_seconds < 1:
        raise OrchestratorError("observation_interval_seconds must be positive")
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
    raw = ""
    try:
        state["orchestrator"]["turn"] = _empty_turn_observation()

        def persist_thread(thread_id: str) -> None:
            state["orchestrator"]["thread_id"] = thread_id
            write_json_atomic(state_path, state)

        def persist_turn(thread_id: str, turn_id: str) -> None:
            state["orchestrator"]["thread_id"] = thread_id
            state["orchestrator"]["turn"]["turn_id"] = turn_id
            state["orchestrator"]["turn"]["started_at"] = _now()
            state["orchestrator"]["turn"]["phase"] = "collecting_completion"
            state["orchestrator"]["turn"]["completion"] = {"status": "awaiting_terminal", "source": "none", "observed_at": None, "valid_envelope": False}
            write_json_atomic(state_path, state)

        def observe(observation: dict[str, Any]) -> None:
            _record_observation(state, observation)
            write_json_atomic(state_path, state)

        def persist_cancelling(request: dict[str, Any]) -> None:
            state["status"] = "cancelling"
            state["cancellation"] = {"phase": "cancelling", "request_id": request["request_id"], "requested_at": request["requested_at"], "handled_at": None, "reason": request["reason"], "provenance": request["provenance"]}
            _event(state, "cancel_request_observed", request_id=request["request_id"], role="orchestrator")
            write_json_atomic(state_path, state)

        outcome = run_role_turn(
            state_path=state_path,
            run_id=state["run_id"],
            role="orchestrator",
            cwd=repository_root,
            prompt=_orchestrator_prompt(state, message),
            execution=execution,
            stderr_path=artifact_root / "orchestrator.stderr.log",
            sandbox="read-only",
            thread_id=state["orchestrator"]["thread_id"] if resume else None,
            approval_policy="never",
            enable_multi_agent=False,
            ephemeral=False,
            observation_interval_seconds=observation_interval_seconds,
            on_observation=observe,
            on_thread_started=persist_thread,
            on_turn_started=persist_turn,
            on_cancelling=persist_cancelling,
        )
        pending_cancel = read_cancel_request(state_path, state["run_id"])
        if pending_cancel is not None and outcome["status"] not in {"cancelled", "quarantined"}:
            terminal = outcome.get("terminal") if isinstance(outcome.get("terminal"), dict) else {}
            outcome = _completed_role_cancel_outcome(
                pending_cancel,
                thread_id=outcome.get("thread_id"),
                turn_id=outcome.get("turn_id"),
                terminal_status=terminal.get("status") if isinstance(terminal.get("status"), str) else "completed",
            )
        notifications = outcome["notifications"]
        history = outcome["history"] or {}
        _record_notifications(state, notifications)
        if outcome["status"] in {"cancelled", "quarantined"}:
            interrupt = outcome.get("interrupt", {})
            state["orchestrator"]["turn"]["interrupt"] = {
                "attempted": bool(interrupt.get("attempted")),
                "acknowledged": bool(interrupt.get("acknowledged")),
                "requested_at": _now() if interrupt.get("attempted") else None,
                "acknowledged_at": _now() if interrupt.get("acknowledged") else None,
                "error": interrupt.get("error") if isinstance(interrupt.get("error"), str) else None,
            }
            if outcome["status"] == "cancelled" and outcome["turn_id"]:
                _record_terminal(state, outcome["terminal"]["status"], "notification_collection")
            _apply_role_cancel_outcome(state, state_path, outcome, "orchestrator")
            return {"thread_id": outcome["thread_id"], "turn_id": outcome["turn_id"], "message": "", "action": "cancel", "worker_results": [], "state": state}
        terminal_status = _terminal_status(outcome["status"])
        if terminal_status is None:
            _mark_blocked(state, "turn_completion_unknown", "turn completed without durable terminal evidence")
            raise OrchestratorError("turn terminal evidence is missing")
        _record_terminal(state, terminal_status, "notification_collection")
        if terminal_status != "completed":
            _mark_blocked(state, "orchestrator_turn_terminal_noncompleted", f"turn terminal status was {terminal_status}")
            raise OrchestratorError(f"Orchestrator turn ended with terminal status {terminal_status}")
        thread_id = outcome["thread_id"]
        evidence = notifications + [history]
        if walk_items(evidence):
            _mark_blocked(state, "orchestrator_subagent_control_forbidden", "Orchestrator attempted to control a Subagent")
            raise OrchestratorError("Orchestrator attempted to control a Subagent; Subagents belong to Workers")
        messages = walk_root_agent_messages(evidence, thread_id)
        raw = messages[-1] if messages else ""
    except BaseException as error:
        if state["status"] not in {"blocked", "cancelled", "finished"}:
            _mark_blocked(state, "orchestrator_turn_failed", str(error))
        raise
    finally:
        after = _git_boundary(repository_root)
        _record_boundary(state, "post_git", after)
        if after["availability"] != "observed":
            _mark_blocked(state, "post_turn_git_unknown", str(after["error"] or "could not inspect repository after turn"))
        elif before["head"] != after["head"] or before["porcelain"] != after["porcelain"]:
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
        with _controller_commit_boundary(
            state,
            role="orchestrator",
            thread_id=state["orchestrator"].get("thread_id"),
            turn_id=state["orchestrator"]["turn"].get("turn_id"),
        ):
            apply_orchestrator_turn(state, turn)
    except OrchestratorError:
        write_json_atomic(state_path, state)
        raise
    worker_results: list[dict[str, Any]] = []
    verifier_result: dict[str, Any] | None = None
    if turn["action"] == "control" and state["status"] in {"running", "awaiting_owner"}:
        operation = turn["operation"]
        if operation == "start_workers":
            selected = turn.get("assignment_ids", [])
            worker_results = start_worker_cohort(state, selected, worker_runner=worker_runner)
            _append_broker_notification(state, "worker_result", f"Selected Worker cohort completed: {', '.join(selected)}.", selected)
        elif operation == "continue_worker":
            assignment_id = turn["assignment_id"]
            worker_results = start_worker_cohort(state, [assignment_id], worker_runner=worker_runner, continuation_messages={assignment_id: turn["message"]})
            _append_broker_notification(state, "worker_result", f"Worker continuation completed for {assignment_id}.", [assignment_id])
        elif operation == "run_verifier":
            assignment_id = turn["assignment_id"]
            verifier_result = run_full_verifier(state, assignment_id, verifier_runner)
            _append_broker_notification(state, "verifier_result", f"Verifier completed for {assignment_id} with {verifier_result['status']}.", [assignment_id])
    _refresh_crew_projection(state)
    write_json_atomic(state_path, state)
    return {"thread_id": state["orchestrator"]["thread_id"], "turn_id": state["orchestrator"]["turn"]["turn_id"], "message": raw, "action": turn["action"], "worker_results": worker_results, "verifier_result": verifier_result, "state": state}


def request_cancel(state_path: Path, reason: str, *, provenance: str = "owner", wait_seconds: float = 45, poll_interval_seconds: float = 1) -> dict[str, Any]:
    """Persist an out-of-band cancel request without taking controller ownership."""

    if wait_seconds < 0 or poll_interval_seconds <= 0:
        raise OrchestratorError("cancel wait settings are invalid")
    state_path = Path(state_path)
    state = json.loads(state_path.read_text(encoding="utf-8"))
    validate_snapshot(state)
    if state["status"] in {"cancelled", "finished"}:
        return {"status": state["status"], "pending": False, "request": None, "state": state}
    started_at = time.monotonic()
    request = write_cancel_request(state_path, state["run_id"], reason, provenance, lock_timeout_seconds=wait_seconds)
    deadline = started_at + wait_seconds
    while True:
        current = json.loads(state_path.read_text(encoding="utf-8"))
        validate_snapshot(current)
        cancellation = current["cancellation"]
        if cancellation["request_id"] == request["request_id"] and cancellation["phase"] in {"cancelled", "quarantined"}:
            return {"status": current["status"], "pending": False, "request": request, "state": current}
        if current["status"] in {"cancelled", "finished"}:
            clear_cancel_request(state_path, request["request_id"])
            return {"status": current["status"], "pending": False, "request": request, "state": current}
        if time.monotonic() >= deadline:
            return {"status": "cancel_pending", "pending": True, "request": request, "state": current}
        time.sleep(min(poll_interval_seconds, max(0.0, deadline - time.monotonic())))


def recover_run(state: dict[str, Any], state_path: Path, *, force: bool = False) -> dict[str, Any]:
    validate_snapshot(state)
    non_reusable_reasons = {"cancellation_uncertain", "turn_stop_unconfirmed", "turn_completion_unknown", "orchestrator_turn_interrupted"}
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
def start(state_path: Path, state: dict[str, Any], *, observation_interval_seconds: int = DEFAULT_OBSERVATION_INTERVAL_SECONDS) -> dict[str, Any]:
    return start_run(state_path, state, observation_interval_seconds=observation_interval_seconds)


def message(state: dict[str, Any], body: str, *, kind: str = "ordinary_correction", provenance: str = "broker", request_id: str | None = None, decision: dict[str, str] | None = None) -> dict[str, Any]:
    return record_broker_message(state, body, kind=kind, provenance=provenance, request_id=request_id, decision=decision)


def advance(state: dict[str, Any], state_path: Path, *, body: str = "", observation_interval_seconds: int = DEFAULT_OBSERVATION_INTERVAL_SECONDS, resume: bool = True) -> dict[str, Any]:
    with controller_lock(state):
        try:
            return run_orchestrator_turn(state, state_path, message=body, observation_interval_seconds=observation_interval_seconds, resume=resume)
        except BaseException as error:
            if state["status"] not in {"blocked", "cancelled", "finished"}:
                state["status"] = "blocked"
                state["quarantine"] = {"reason": "orchestrator_turn_failed", "detail": str(error), "at": _now()}
            write_json_atomic(state_path, state)
            raise


def status(state: dict[str, Any]) -> dict[str, Any]:
    validate_snapshot(state)
    return state


def cancel(state: dict[str, Any], state_path: Path, reason: str) -> dict[str, Any]:
    return request_cancel(state_path, reason)


def recover(state: dict[str, Any], state_path: Path, *, force: bool = False) -> dict[str, Any]:
    return recover_run(state, state_path, force=force)


def start_run(state_path: Path, state: dict[str, Any], *, observation_interval_seconds: int = DEFAULT_OBSERVATION_INTERVAL_SECONDS) -> dict[str, Any]:
    validate_snapshot(state)
    with controller_lock(state):
        write_json_atomic(state_path, state)
        try:
            return run_orchestrator_turn(state, state_path, observation_interval_seconds=observation_interval_seconds, resume=False)
        except BaseException as error:
            if state["status"] not in {"blocked", "cancelled", "finished"}:
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
    start.add_argument("--observation-interval-seconds", type=int, default=DEFAULT_OBSERVATION_INTERVAL_SECONDS)
    message = sub.add_parser("message")
    message.add_argument("--state", type=Path, required=True)
    message.add_argument("--message", required=True)
    message.add_argument("--kind", default="ordinary_correction", choices=["ordinary_correction", "owner_decision"])
    message.add_argument("--request-id")
    message.add_argument("--decision", choices=["approved", "rejected"])
    message.add_argument("--provenance", default="broker")
    message.add_argument("--observation-interval-seconds", type=int, default=DEFAULT_OBSERVATION_INTERVAL_SECONDS)
    advance = sub.add_parser("advance")
    advance.add_argument("--state", type=Path, required=True)
    advance.add_argument("--observation-interval-seconds", type=int, default=DEFAULT_OBSERVATION_INTERVAL_SECONDS)
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
        print(json.dumps(start_run(args.state, state, observation_interval_seconds=args.observation_interval_seconds), ensure_ascii=False, indent=2))
        return 0
    state = json.loads(args.state.read_text(encoding="utf-8"))
    validate_snapshot(state)
    if args.command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.command == "recover":
        print(json.dumps(recover_run(state, args.state, force=args.force), ensure_ascii=False, indent=2))
        return 0
    if args.command == "cancel":
        result = request_cancel(args.state, args.reason)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result["pending"] else (0 if result["status"] == "cancelled" else 1)
    lock_acquired = False
    try:
        with controller_lock(state):
            lock_acquired = True
            if args.command == "message":
                decision = {"disposition": args.decision, "detail": args.message} if args.kind == "owner_decision" and args.decision else None
                record_broker_message(state, args.message, kind=args.kind, provenance=args.provenance, request_id=args.request_id, decision=decision)
                write_json_atomic(args.state, state)
                result = run_orchestrator_turn(state, args.state, message=args.message, observation_interval_seconds=args.observation_interval_seconds)
            elif args.command == "advance":
                result = run_orchestrator_turn(state, args.state, observation_interval_seconds=args.observation_interval_seconds, resume=True)
            else:
                raise AssertionError("unreachable")
    except BaseException as error:
        if lock_acquired and state["status"] not in {"blocked", "cancelled", "finished"}:
            state["status"] = "blocked"
            state["quarantine"] = {"reason": "orchestrator_turn_failed", "detail": str(error), "at": _now()}
        write_json_atomic(args.state, state)
        raise
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OrchestratorError, WorkspaceError, ValueError, RuntimeError, TimeoutError) as error:
        print(f"[X] {error}", file=sys.stderr)
        raise SystemExit(1)
