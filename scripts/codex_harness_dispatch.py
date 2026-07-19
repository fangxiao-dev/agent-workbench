"""Thin Worker/worktree adapter owned by the Codex Crew Orchestrator.

This module contains no scheduler, parent state, topology selection, manifest
protocol, or CLI.  It materializes one controller-approved worktree and runs
one bounded Worker assignment.  Canonical assignment lifecycle and acceptance
remain in ``codex_harness_orchestrator.py``.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any

try:
    from codex_harness_agent import run_role_turn
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_agent import run_role_turn


WORKER_RESULT_SCHEMA_VERSION = "codex-crew.worker-result.v0.1"
WORKER_STATUSES = {"succeeded", "needs_orchestrator", "needs_owner", "failed"}
OWNER_CATEGORIES = {"scope_change", "authority_expansion", "irreversible_external_side_effect", "acceptance_ambiguity"}


def write_json_atomic(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


def ensure_worktree(repository_root: Path, worktree: dict[str, str]) -> dict[str, str]:
    root = repository_root.resolve()
    target = Path(worktree["path"]).resolve()
    if target == root:
        raise ValueError("worktree target must not be the repository root")
    if target.exists():
        completed = subprocess.run(["git", "-C", str(root), "worktree", "list", "--porcelain"], capture_output=True, text=True, check=True)
        current_path: Path | None = None
        branches: dict[Path, str | None] = {}
        for line in completed.stdout.splitlines() + [""]:
            if line.startswith("worktree "):
                current_path = Path(line[9:]).resolve()
                branches[current_path] = None
            elif line.startswith("branch ") and current_path is not None:
                branches[current_path] = line[7:]
            elif not line:
                current_path = None
        if target not in branches:
            raise ValueError(f"worktree target exists but is not a registered worktree: {target}")
        expected_branch = f"refs/heads/{worktree['branch']}"
        if branches[target] not in {expected_branch, worktree["branch"]}:
            raise ValueError(f"worktree target is bound to a different branch: {target}")
        return {"path": str(target), "created": "false"}
    target.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "-C", str(root), "worktree", "add", "-b", worktree["branch"], str(target), worktree["base_ref"]], check=True, capture_output=True, text=True)
    return {"path": str(target), "created": "true"}


def _parse_worker_result(raw: str, assignment_id: str, revision: int) -> dict[str, Any] | None:
    candidate = raw.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    required = {"schema_version", "assignment_id", "revision", "status", "summary", "verification", "owner_request"}
    if not isinstance(result, dict) or required - set(result):
        return None
    if result.get("schema_version") != WORKER_RESULT_SCHEMA_VERSION or result.get("assignment_id") != assignment_id or result.get("revision") != revision:
        return None
    if result.get("status") not in WORKER_STATUSES or not isinstance(result.get("summary"), str) or not isinstance(result.get("verification"), list):
        return None
    request = result.get("owner_request")
    if request is not None and (not isinstance(request, dict) or set(request) != {"category", "detail"} or request.get("category") not in OWNER_CATEGORIES or not isinstance(request.get("detail"), str)):
        return None
    if result["status"] == "needs_owner" and request is None:
        return None
    return result


def _worker_prompt(assignment_id: str, revision: int, assignment_prompt: str, access_mode: str) -> str:
    access_boundary = (
        "Inspect the fixed repository revision in read-only mode. Do not modify files, Git refs, external systems, or environment state. "
        if access_mode == "repository_read_only"
        else "Work only inside this assignment worktree. "
    )
    return (
        f"You are the Worker owner for assignment_id={assignment_id!r}, revision={revision}. {assignment_prompt}\n\n"
        f"{access_boundary}Own the bounded assignment end to end, including analysis, design, review and evidence appropriate to its access mode. "
        "You may control your own Subagents, but do not contact the Owner, Broker, or sibling Workers. Return needs_orchestrator for in-contract coordination. "
        "Use needs_owner only for scope_change, authority_expansion, irreversible_external_side_effect, or acceptance_ambiguity. "
        "For succeeded, verification must be a non-empty array of objects with command (string), exit_code (integer), and claim (string). "
        "Return exactly one JSON object and nothing else: "
        f'{{"schema_version":"{WORKER_RESULT_SCHEMA_VERSION}","assignment_id":"{assignment_id}","revision":{revision},"status":"succeeded|needs_orchestrator|needs_owner|failed","summary":"...","commit":null,"changed_paths":[],"artifacts":[],"verification":[],"owner_request":null,"subagent_telemetry":{{"delegated":false,"active_count":0}}}}.'
    )


def assignment_task(assignment: dict[str, Any], worker_execution: dict[str, str], *, repository_root: Path | None = None) -> dict[str, Any]:
    required = {"assignment_id", "revision", "goal", "non_goals", "acceptance_criteria", "access_mode", "allowed_paths", "verification_commands", "workspace", "boundary_evidence"}
    if not isinstance(assignment, dict) or required - set(assignment):
        raise ValueError("assignment is missing Worker adapter fields")
    if not isinstance(worker_execution, dict) or any(not isinstance(worker_execution.get(key), str) or not worker_execution[key].strip() for key in ("id", "model", "reasoning_effort")):
        raise ValueError("worker execution binding is malformed")
    workspace = assignment["workspace"]
    access_mode = assignment["access_mode"]
    if access_mode not in {"repository_read_only", "workspace_write"}:
        raise ValueError("assignment access mode is malformed")
    if access_mode == "workspace_write" and (not isinstance(workspace, dict) or any(not isinstance(workspace.get(key), str) or not workspace[key].strip() for key in ("path", "branch", "base_ref"))):
        raise ValueError("write assignment workspace must contain materialized path, branch and base_ref")
    if access_mode == "repository_read_only" and (workspace is not None or repository_root is None or not assignment["boundary_evidence"].get("source_revision")):
        raise ValueError("read-only assignment requires a fixed repository revision and no workspace")
    if not isinstance(assignment["goal"], str) or not assignment["goal"].strip() or not isinstance(assignment["revision"], int) or isinstance(assignment["revision"], bool) or assignment["revision"] < 1:
        raise ValueError("assignment goal and revision are malformed")
    if not isinstance(assignment["non_goals"], list) or any(not isinstance(item, str) or not item.strip() for item in assignment["non_goals"]):
        raise ValueError("assignment non_goals must be strings")
    if not isinstance(assignment["acceptance_criteria"], list) or not assignment["acceptance_criteria"] or any(not isinstance(item, str) or not item.strip() for item in assignment["acceptance_criteria"]):
        raise ValueError("assignment acceptance_criteria must contain non-empty strings")
    if not isinstance(assignment["allowed_paths"], list) or any(not isinstance(item, str) or not item.strip() for item in assignment["allowed_paths"]):
        raise ValueError("assignment allowed_paths must be strings")
    if access_mode == "workspace_write" and not assignment["allowed_paths"]:
        raise ValueError("write assignment requires allowed_paths")
    if access_mode == "repository_read_only" and assignment["allowed_paths"]:
        raise ValueError("read-only assignment cannot declare write ownership")
    commands = assignment["verification_commands"]
    if not isinstance(commands, list) or any(not isinstance(command, str) or not command.strip() for command in commands):
        raise ValueError("assignment verification_commands must be strings")
    non_goals = "; ".join(assignment["non_goals"]) or "none"
    acceptance = "; ".join(assignment["acceptance_criteria"])
    if access_mode == "repository_read_only":
        prompt = f"Goal: {assignment['goal']} Non-goals: {non_goals}. Acceptance criteria: {acceptance}. Repository revision: {assignment['boundary_evidence']['source_revision']}. Produce analysis and evidence without mutation."
        worktree = {"path": str(Path(repository_root).resolve()), "branch": None, "base_ref": assignment["boundary_evidence"]["source_revision"]}
    else:
        paths = ", ".join(assignment["allowed_paths"])
        prompt = (
            f"Goal: {assignment['goal']} Non-goals: {non_goals}. Acceptance criteria: {acceptance}. "
            f"You may modify only these repository-relative paths: {paths}. "
            "Do not split package work, implementation, review loops, or internal T1-T5 style steps into top-level assignments unless authority, write ownership, delivery responsibility, or the acceptance boundary materially changes."
        )
        worktree = {key: workspace[key] for key in ("path", "branch", "base_ref")}
    return {
        "id": assignment["assignment_id"],
        "revision": assignment["revision"],
        "prompt": prompt,
        "access_mode": access_mode,
        "worktree": worktree,
        "verification_commands": list(commands),
        "worker_execution": dict(worker_execution),
        "ephemeral": False,
    }


def continue_assignment(task: dict[str, Any], thread_id: str, message: str) -> dict[str, Any]:
    if not isinstance(thread_id, str) or not thread_id.strip() or not isinstance(message, str) or not message.strip():
        raise ValueError("thread_id and continuation message are required")
    return _run_worker_role(task, _worker_prompt(task["id"], task["revision"], message, task["access_mode"]), thread_id=thread_id)


def _walk_agent_messages(value: Any, thread_id: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("agentThreadId") and value.get("agentThreadId") != thread_id:
            return found
        if value.get("threadId") and value.get("threadId") != thread_id:
            return found
        if value.get("type") in {"agentMessage", "agent_message"} and isinstance(value.get("text"), str):
            found.append(value["text"])
        for nested in value.values():
            found.extend(_walk_agent_messages(nested, thread_id))
    elif isinstance(value, list):
        for nested in value:
            found.extend(_walk_agent_messages(nested, thread_id))
    return found


def run_worker(_assignment_id: str, task: dict[str, Any]) -> dict[str, Any]:
    return _run_worker_role(task, _worker_prompt(task["id"], task["revision"], task["prompt"], task["access_mode"]), thread_id=None)


def _run_worker_role(task: dict[str, Any], prompt: str, *, thread_id: str | None) -> dict[str, Any]:
    assignment_id = task["id"]
    revision = task["revision"]
    worktree = Path(task["worktree"]["path"])
    control = task.get("control") if isinstance(task.get("control"), dict) else {}
    run_id = control.get("run_id") or f"worker-{assignment_id}"
    artifact_root = Path(control.get("artifact_root") or (Path(tempfile.gettempdir()) / "codex-harness-runs" / "workers" / run_id))
    execution = task["worker_execution"]
    state_path = Path(control.get("state_path") or (artifact_root / "control.json"))
    callbacks = control.get("callbacks") if isinstance(control.get("callbacks"), dict) else {}
    outcome = run_role_turn(
        state_path=state_path,
        run_id=run_id,
        role="worker",
        cwd=worktree,
        prompt=prompt,
        execution=execution,
        stderr_path=artifact_root / f"worker-{assignment_id}.stderr.log",
        sandbox="read-only" if task["access_mode"] == "repository_read_only" else "workspace-write",
        writable_roots=None if task["access_mode"] == "repository_read_only" else [Path(item) for item in task.get("writable_roots", [])],
        thread_id=thread_id,
        approval_policy="never",
        enable_multi_agent=True,
        ephemeral=bool(task.get("ephemeral", False)),
        on_thread_started=callbacks.get("on_thread_started"),
        on_turn_started=callbacks.get("on_turn_started"),
        on_cancelling=callbacks.get("on_cancelling"),
    )
    if outcome["status"] in {"cancelled", "quarantined"}:
        return {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "assignment_id": assignment_id, "revision": revision, "status": "failed", "summary": f"worker turn {outcome['status']}", "verification": [], "owner_request": None, "worker_thread_id": outcome["thread_id"], "worker_turn_id": outcome["turn_id"], "worker_execution": execution, "_control_outcome": outcome}
    messages = _walk_agent_messages(outcome["notifications"] + [outcome["history"]], outcome["thread_id"])
    raw = messages[-1] if messages else ""
    result = _parse_worker_result(raw, assignment_id, revision)
    if result is None:
        result = {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "assignment_id": assignment_id, "revision": revision, "status": "failed", "summary": "Worker did not return a valid structured result", "verification": [], "owner_request": None, "raw_result": raw}
    result["worker_thread_id"] = outcome["thread_id"]
    result["worker_turn_id"] = outcome["turn_id"]
    result["worker_execution"] = execution
    return result
