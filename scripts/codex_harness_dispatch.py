#!/usr/bin/env python3
"""Reusable worker/worktree dispatch primitives for Codex Crew.

This module is intentionally below the parent controller. It creates isolated
worktrees, gives every worker a fresh App Server thread, and records structured
worker outcomes. It does not own a parent thread, select a mode, ask an owner
for a decision, or resume a parent. The parent agent calls these primitives;
the full controller composes policy, lease, ledger, package, and gate controls
above them.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    from codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from codex_harness_profiles import ExecutionProfileError, load_execution_profiles, worker_profile_for_mode
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from scripts.codex_harness_profiles import ExecutionProfileError, load_execution_profiles, worker_profile_for_mode


DISPATCH_SCHEMA_VERSION = "codex-crew.dispatch.v1"
STATE_SCHEMA_VERSION = "codex-crew.state.v1"
WORKER_RESULT_SCHEMA_VERSION = "codex-crew.worker-result.v0"
OWNER_CATEGORIES = {"scope_change", "authority_expansion", "irreversible_external_side_effect", "acceptance_ambiguity"}
WORKER_STATUSES = {"succeeded", "needs_parent", "needs_owner", "failed"}
DISPATCH_STATUSES = {"running", "attention", "completed", "failed"}


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON object: {path}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


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


def validate_manifest(manifest: dict[str, Any]) -> None:
    required = {"schema_version", "profile", "worker_profile", "repository_root", "parent_run_id", "parent_thread_id", "tasks"}
    if set(manifest) - {"$schema", *required} or required - set(manifest):
        raise ValueError("dispatch manifest has unsupported or missing fields")
    if manifest["schema_version"] != DISPATCH_SCHEMA_VERSION or manifest["profile"] not in {"lite", "full"}:
        raise ValueError("unsupported dispatch manifest version or profile")
    if not isinstance(manifest["worker_profile"], str) or not manifest["worker_profile"].strip():
        raise ValueError("worker_profile must be a non-empty string")
    try:
        profiles = load_execution_profiles(Path(__file__).resolve().parents[1])
        expected_worker = worker_profile_for_mode(profiles, manifest["profile"])
    except ExecutionProfileError as exc:
        raise ValueError(f"worker execution profile configuration is invalid: {exc}") from exc
    if manifest["worker_profile"] != expected_worker["id"]:
        raise ValueError(f"worker_profile must use the canonical {manifest['profile']} binding: {expected_worker['id']}")
    if not isinstance(manifest["repository_root"], str) or not manifest["repository_root"].strip():
        raise ValueError("repository_root must be a non-empty string")
    if any(not isinstance(manifest.get(key), str) or not manifest[key].strip() for key in ("parent_run_id", "parent_thread_id")):
        raise ValueError("parent_run_id and parent_thread_id must be non-empty strings")
    tasks = manifest["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty array")
    task_ids: set[str] = set()
    worktree_paths: set[str] = set()
    branches: set[str] = set()
    for task in tasks:
        if not isinstance(task, dict) or set(task) - {"id", "prompt", "worktree", "verification_commands"} or {"id", "prompt", "worktree"} - set(task):
            raise ValueError("task has unsupported or missing fields")
        task_id = task["id"]
        if not isinstance(task_id, str) or not task_id or task_id in task_ids:
            raise ValueError("every task requires a unique non-empty id")
        task_ids.add(task_id)
        if not isinstance(task["prompt"], str) or not task["prompt"].strip():
            raise ValueError(f"task {task_id} requires a prompt")
        worktree = task["worktree"]
        if not isinstance(worktree, dict) or set(worktree) != {"path", "branch", "base_ref"} or any(not isinstance(worktree.get(key), str) or not worktree[key].strip() for key in worktree):
            raise ValueError(f"task {task_id} requires worktree path, branch and base_ref")
        worktree_path = str(Path(worktree["path"]).expanduser().resolve()).casefold()
        if worktree_path in worktree_paths:
            raise ValueError(f"tasks must not share a worktree path: {worktree['path']}")
        if worktree["branch"] in branches:
            raise ValueError(f"tasks must not share a branch: {worktree['branch']}")
        worktree_paths.add(worktree_path)
        branches.add(worktree["branch"])
        commands = task.get("verification_commands", [])
        if not isinstance(commands, list) or any(not isinstance(command, str) or not command.strip() for command in commands):
            raise ValueError(f"task {task_id} verification_commands must be strings")


def validate_parent_binding(manifest: dict[str, Any], parent_state: dict[str, Any]) -> None:
    """Ensure a dispatch manifest belongs to the confirmed parent run.

    The dispatcher remains deliberately small, but a parent-bound invocation
    must not be able to silently dispatch work for another run, repository, or
    profile. The parent controller owns the richer state machine; this check
    only validates the cross-layer binding.
    """

    if parent_state.get("schema_version") != "codex-crew.parent-state.v1":
        raise ValueError("parent state is not a current Crew parent state")
    parent = parent_state.get("parent")
    mode = parent_state.get("mode")
    if not isinstance(parent, dict) or not isinstance(mode, dict):
        raise ValueError("parent state binding projection is malformed")
    confirmed = mode.get("confirmed")
    thread_id = parent.get("thread_id")
    if confirmed not in {"lite", "full"} or not isinstance(thread_id, str) or not thread_id.strip():
        raise ValueError("parent must have a confirmed profile and thread before dispatch")
    if manifest.get("profile") != confirmed:
        raise ValueError("dispatch profile does not match the confirmed parent profile")
    if manifest.get("parent_run_id") != parent_state.get("run_id") or manifest.get("parent_thread_id") != thread_id:
        raise ValueError("dispatch parent run/thread does not match the parent state")
    try:
        manifest_root = Path(manifest["repository_root"]).expanduser().resolve()
        parent_root = Path(parent_state["repository_root"]).expanduser().resolve()
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError("repository_root is malformed in parent binding") from error
    if manifest_root != parent_root:
        raise ValueError("dispatch repository_root does not match the parent state")


def initialise_state(manifest: dict[str, Any]) -> dict[str, Any]:
    validate_manifest(manifest)
    profiles = load_execution_profiles(Path(__file__).resolve().parents[1])
    worker = worker_profile_for_mode(profiles, manifest["profile"])
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "profile": manifest["profile"],
        "worker_profile": worker["id"],
        "worker_execution": worker,
        "repository_root": manifest["repository_root"],
        "parent_run_id": manifest["parent_run_id"],
        "parent_thread_id": manifest["parent_thread_id"],
        "status": "running",
        "tasks": {task["id"]: {"worktree": task["worktree"], "prompt": task["prompt"], "verification_commands": task.get("verification_commands", []), "worker_execution": worker, "status": "pending"} for task in manifest["tasks"]},
        "events": [{"at": time.time(), "kind": "state_initialized"}],
    }


def validate_state(state: dict[str, Any]) -> None:
    required = {"schema_version", "profile", "worker_profile", "worker_execution", "repository_root", "parent_run_id", "parent_thread_id", "status", "tasks", "events"}
    if required - set(state) or state.get("schema_version") != STATE_SCHEMA_VERSION:
        raise ValueError("unsupported or incomplete crew state")
    if state["status"] not in DISPATCH_STATUSES:
        raise ValueError("unsupported crew state status")
    if state.get("profile") not in {"lite", "full"} or not isinstance(state.get("repository_root"), str) or not state["repository_root"].strip():
        raise ValueError("crew state profile or repository_root is malformed")
    if not isinstance(state.get("worker_profile"), str) or not state["worker_profile"].strip() or not isinstance(state.get("worker_execution"), dict):
        raise ValueError("crew state worker execution binding is malformed")
    try:
        profiles = load_execution_profiles(Path(__file__).resolve().parents[1])
        expected_worker = worker_profile_for_mode(profiles, state["profile"])
    except ExecutionProfileError as exc:
        raise ValueError(f"worker execution profile configuration is invalid: {exc}") from exc
    if state["worker_profile"] != expected_worker["id"] or state["worker_execution"] != expected_worker:
        raise ValueError("crew state worker execution binding does not match the canonical profile")
    if any(not isinstance(state.get(key), str) or not state[key].strip() for key in ("parent_run_id", "parent_thread_id")):
        raise ValueError("dispatch state parent binding is malformed")
    if not isinstance(state["tasks"], dict) or not state["tasks"] or not isinstance(state["events"], list):
        raise ValueError("crew state tasks/events are malformed")
    for task_id, task in state["tasks"].items():
        if not isinstance(task, dict) or task.get("worker_execution") != expected_worker:
            raise ValueError(f"task {task_id} worker execution binding does not match the state profile")


def _event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    state["events"].append({"at": time.time(), "kind": kind, **fields})


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


def ensure_worktrees(state: dict[str, Any]) -> list[dict[str, str]]:
    validate_state(state)
    root = Path(state["repository_root"])
    probe = subprocess.run(["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"], capture_output=True, text=True)
    if probe.returncode or probe.stdout.strip() != "true":
        raise ValueError(f"repository_root is not a git worktree: {root}")
    results: list[dict[str, str]] = []
    for task_id, task in state["tasks"].items():
        result = ensure_worktree(root, task["worktree"])
        task["worktree"]["path"] = result["path"]
        _event(state, "worktree_ready", task_id=task_id, **result)
        results.append({"task_id": task_id, **result})
    return results


def parse_worker_result(raw: str, task_id: str) -> dict[str, Any] | None:
    candidate = raw.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    try:
        result = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    required = {"schema_version", "task_id", "status", "summary", "verification", "owner_request"}
    if not isinstance(result, dict) or required - set(result) or result.get("schema_version") != WORKER_RESULT_SCHEMA_VERSION or result.get("task_id") != task_id:
        return None
    if result.get("status") not in WORKER_STATUSES or not isinstance(result.get("summary"), str) or not isinstance(result.get("verification"), list):
        return None
    request = result.get("owner_request")
    if request is not None and (not isinstance(request, dict) or set(request) != {"category", "detail"} or request.get("category") not in OWNER_CATEGORIES or not isinstance(request.get("detail"), str)):
        return None
    if result["status"] == "needs_owner" and request is None:
        return None
    return result


def worker_prompt(task_id: str, task_prompt: str) -> str:
    return (
        f"You are an isolated worker for task_id={task_id!r} in this worktree. {task_prompt}\n\n"
        "Work only inside this worktree. Do not broaden the issue into redesign. If the task needs parent judgment, return status needs_parent. "
        "Use needs_owner only for scope_change, authority_expansion, irreversible_external_side_effect, or acceptance_ambiguity. "
        "Return exactly one JSON object and nothing else: "
        f'{{"schema_version":"{WORKER_RESULT_SCHEMA_VERSION}","task_id":"{task_id}","status":"succeeded|needs_parent|needs_owner|failed","summary":"...","verification":[],"owner_request":null}}.'
    )


def walk_agent_messages(value: Any, thread_id: str) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("agentThreadId") and value.get("agentThreadId") != thread_id:
            return found
        if value.get("threadId") and value.get("threadId") != thread_id:
            return found
        if value.get("type") in {"agentMessage", "agent_message"} and isinstance(value.get("text"), str):
            found.append(value["text"])
        for nested in value.values():
            found.extend(walk_agent_messages(nested, thread_id))
    elif isinstance(value, list):
        for nested in value:
            found.extend(walk_agent_messages(nested, thread_id))
    return found


def run_worker(task_id: str, task: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    worktree = Path(task["worktree"]["path"])
    stderr_path = worktree / ".codex-crew-worker.stderr.log"
    with JsonRpcSession(app_server_command(approval_policy="never"), stderr_path) as session:
        session.request(1, "initialize", initialize_params("codex-crew-worker"), 30)
        execution = task["worker_execution"]
        started, _ = session.request(2, "thread/start", {"cwd": str(worktree), "sandbox": "workspace-write", "approvalPolicy": "never", "ephemeral": True, "model": execution["model"], "config": {"model_reasoning_effort": execution["reasoning_effort"]}}, 30)
        thread_id = started["thread"]["id"]
        started_turn, start_events = session.request(3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": worker_prompt(task_id, task["prompt"])}], "approvalPolicy": "never", "sandboxPolicy": {"type": "workspaceWrite", "networkAccess": False}}, 30)
        events = list(start_events)
        events.extend(session.collect_until_turn_complete(thread_id, timeout_seconds))
        history, history_events = session.request(4, "thread/read", {"threadId": thread_id, "includeTurns": True}, 30)
        messages = walk_agent_messages(events + history_events + [history], thread_id)
        raw = messages[-1] if messages else ""
        result = parse_worker_result(raw, task_id)
        if result is None:
            result = {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": task_id, "status": "failed", "summary": "worker did not return a valid structured result", "verification": [], "owner_request": None, "raw_result": raw}
        result["worker_thread_id"] = thread_id
        result["turn_id"] = started_turn.get("turn", {}).get("id")
        result["worker_execution"] = execution
        return result


def record_worker_result(state: dict[str, Any], task_id: str, result: dict[str, Any]) -> dict[str, Any]:
    validate_state(state)
    if task_id not in state["tasks"]:
        raise ValueError(f"unknown task: {task_id}")
    parsed = parse_worker_result(json.dumps(result, ensure_ascii=False), task_id)
    if parsed is None:
        raise ValueError("worker result does not satisfy the structured worker-result contract")
    result = parsed
    task = state["tasks"][task_id]
    result["worker_execution"] = task["worker_execution"]
    task["result"] = result
    task["status"] = result["status"]
    if result["status"] in {"needs_owner", "needs_parent", "failed"}:
        state["status"] = "attention"
        _event(state, "worker_attention", task_id=task_id, worker_status=result["status"], owner_request=result.get("owner_request"))
        return {"action": "parent_attention", "state": state["status"], "worker_status": result["status"], "owner_request": result.get("owner_request")}
    _event(state, "worker_succeeded", task_id=task_id)
    if all(item.get("status") == "succeeded" for item in state["tasks"].values()):
        state["status"] = "completed"
        return {"action": "collect_results", "state": state["status"]}
    return {"action": "dispatch_next", "state": state["status"]}


def main() -> int:
    parser = argparse.ArgumentParser(description="Codex Crew reusable worktree dispatch primitives.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    init = subparsers.add_parser("init-state")
    init.add_argument("--manifest", type=Path, required=True)
    init.add_argument("--parent-state", type=Path)
    init.add_argument("--state", type=Path, required=True)
    worktrees = subparsers.add_parser("ensure-worktrees")
    worktrees.add_argument("--state", type=Path, required=True)
    record = subparsers.add_parser("record-worker-result")
    record.add_argument("--state", type=Path, required=True)
    record.add_argument("--task-id", required=True)
    record.add_argument("--result", type=Path, required=True)
    workers = subparsers.add_parser("start-workers")
    workers.add_argument("--state", type=Path, required=True)
    workers.add_argument("--task-id", action="append")
    workers.add_argument("--parallelism", type=int, default=1)
    workers.add_argument("--timeout-seconds", type=int, default=900)
    args = parser.parse_args()
    if args.command == "init-state":
        manifest = read_json(args.manifest)
        validate_manifest(manifest)
        if args.parent_state is not None:
            validate_parent_binding(manifest, read_json(args.parent_state))
        state = initialise_state(manifest)
        write_json_atomic(args.state, state)
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    state = read_json(args.state)
    validate_state(state)
    if args.command == "ensure-worktrees":
        result = ensure_worktrees(state)
        write_json_atomic(args.state, state)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    if args.command == "record-worker-result":
        result = read_json(args.result)
        action = record_worker_result(state, args.task_id, result)
        write_json_atomic(args.state, state)
        print(json.dumps(action, ensure_ascii=False, indent=2))
        return 0
    if args.command == "start-workers":
        task_ids = args.task_id or list(state["tasks"])
        if args.parallelism < 1 or args.timeout_seconds < 1 or len(set(task_ids)) != len(task_ids) or any(task_id not in state["tasks"] for task_id in task_ids):
            raise ValueError("invalid worker selection, parallelism, or timeout")
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.parallelism) as executor:
            futures = {executor.submit(run_worker, task_id, state["tasks"][task_id], args.timeout_seconds): task_id for task_id in task_ids}
            completed = []
            for future in concurrent.futures.as_completed(futures):
                task_id = futures[future]
                try:
                    result = future.result()
                except BaseException as error:
                    result = {"schema_version": WORKER_RESULT_SCHEMA_VERSION, "task_id": task_id, "status": "failed", "summary": "worker process failed before returning a structured result", "verification": [], "owner_request": None, "error": str(error)}
                completed.append((task_id, result))
        actions = []
        for task_id, result in sorted(completed):
            actions.append({"task_id": task_id, **record_worker_result(state, task_id, result)})
        write_json_atomic(args.state, state)
        print(json.dumps(actions, ensure_ascii=False, indent=2))
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, subprocess.CalledProcessError, TimeoutError, RuntimeError) as error:
        print(f"[X] {error}", file=sys.stderr)
        raise SystemExit(1)
