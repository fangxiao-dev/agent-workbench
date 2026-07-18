#!/usr/bin/env python3
"""Main-session controller for one persistent Codex Crew parent thread.

The interactive/main session calls this controller as a broker. The parent
thread performs all issue analysis, mode-specific orchestration, worktree and
worker dispatch, and result aggregation. This module owns the parent state and
continuation protocol; ``codex_harness_dispatch.py`` remains the lower-level
worker/worktree primitive used by the parent.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

try:
    from codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from codex_harness_controller import git_status, walk_root_agent_messages
    from codex_harness_dispatch import read_json, validate_state as validate_dispatch_state, write_json_atomic
    from codex_harness_policy import PolicyError, load_runtime_policy
    from codex_harness_runtime import LedgerIntegrityError, ResourceLedger, ThreadLease
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from scripts.codex_harness_controller import git_status, walk_root_agent_messages
    from scripts.codex_harness_dispatch import read_json, validate_state as validate_dispatch_state, write_json_atomic
    from scripts.codex_harness_policy import PolicyError, load_runtime_policy
    from scripts.codex_harness_runtime import LedgerIntegrityError, ResourceLedger, ThreadLease


PARENT_STATE_SCHEMA_VERSION = "codex-crew.parent-state.v0"
PARENT_ROUTE_SCHEMA_VERSION = "codex-crew.parent-route.v0"
PARENT_STATUS_SCHEMA_VERSION = "codex-crew.parent-status.v0"
MODES = {"lite", "full"}
STATUSES = {"starting", "awaiting_mode_confirmation", "running", "awaiting_owner", "completed", "failed"}
OWNER_CATEGORIES = {"scope_change", "authority_expansion", "irreversible_external_side_effect", "acceptance_ambiguity"}


def _read_profile(path: Path) -> dict[str, str]:
    with path.open("rb") as stream:
        profile = tomllib.load(stream)
    required = ("name", "description", "model", "model_reasoning_effort", "developer_instructions")
    if any(not isinstance(profile.get(key), str) or not profile[key].strip() for key in required):
        raise ValueError(f"parent profile is missing required values: {path}")
    return {key: profile[key] for key in required}


def _event(state: dict[str, Any], kind: str, **fields: Any) -> None:
    state["events"].append({"at": time.time(), "kind": kind, **fields})


def new_state(repository_root: Path, issue: str, profile_path: Path, run_id: str | None = None, harness_root: Path | None = None) -> dict[str, Any]:
    resolved_harness_root = (harness_root or Path(__file__).resolve().parents[1]).resolve()
    resolved_run_id = run_id or time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    artifact_root = resolved_harness_root / ".codex" / "harness-runs" / "crew" / resolved_run_id
    return {
        "schema_version": PARENT_STATE_SCHEMA_VERSION,
        "run_id": resolved_run_id,
        "repository_root": str(repository_root.resolve()),
        "harness_root": str(resolved_harness_root),
        "artifact_root": str(artifact_root),
        "issue": issue,
        "parent": {
            "thread_id": None,
            "profile_path": str(profile_path.resolve()),
            "sandbox": "read-only",
            "approval_policy": "never",
        },
        "mode": {"status": "routing", "proposed": None, "confirmed": None, "rationale": ""},
        "status": "starting",
        "policy_identity": None,
        "decision_requests": [],
        "dispatch_refs": [],
        "last_message": "",
        "worktree_status_baseline": git_status(repository_root.resolve()),
        "events": [{"at": time.time(), "kind": "parent_run_initialized"}],
    }


def validate_state(state: dict[str, Any]) -> None:
    required = {"schema_version", "run_id", "repository_root", "harness_root", "artifact_root", "issue", "parent", "mode", "status", "policy_identity", "decision_requests", "dispatch_refs", "last_message", "worktree_status_baseline", "events"}
    if state.get("schema_version") != PARENT_STATE_SCHEMA_VERSION or required - set(state):
        raise ValueError("unsupported or incomplete parent state")
    if any(not isinstance(state.get(field), str) or not state[field].strip() for field in ("run_id", "repository_root", "harness_root", "artifact_root", "issue")):
        raise ValueError("parent state identity or path fields are malformed")
    if state["status"] not in STATUSES:
        raise ValueError(f"unsupported parent state status: {state['status']}")
    if "state_path" in state and (not isinstance(state["state_path"], str) or not state["state_path"].strip()):
        raise ValueError("state_path must be a non-empty string when present")
    parent = state["parent"]
    if not isinstance(parent, dict) or set(parent) != {"thread_id", "profile_path", "sandbox", "approval_policy"}:
        raise ValueError("parent state has malformed parent projection")
    if parent["thread_id"] is not None and (not isinstance(parent["thread_id"], str) or not parent["thread_id"].strip()):
        raise ValueError("parent.thread_id must be null or a non-empty string")
    mode = state["mode"]
    if not isinstance(mode, dict) or set(mode) != {"status", "proposed", "confirmed", "rationale"}:
        raise ValueError("parent state has malformed mode projection")
    if mode["proposed"] is not None and mode["proposed"] not in MODES:
        raise ValueError("mode.proposed is invalid")
    if mode["confirmed"] is not None and mode["confirmed"] not in MODES:
        raise ValueError("mode.confirmed is invalid")
    if mode["status"] not in {"routing", "awaiting_confirmation", "confirmed"}:
        raise ValueError("mode.status is invalid")
    if not isinstance(state["decision_requests"], list) or not isinstance(state["dispatch_refs"], list) or not isinstance(state["events"], list):
        raise ValueError("parent state event/request collections are malformed")
    expected_artifact_root = Path(state["harness_root"]).resolve() / ".codex" / "harness-runs" / "crew" / state["run_id"]
    if Path(state["artifact_root"]).resolve() != expected_artifact_root:
        raise ValueError("parent artifact_root is not the harness-owned run directory")
    seen_dispatch_paths: set[str] = set()
    for reference in state["dispatch_refs"]:
        if not isinstance(reference, dict) or set(reference) != {"path", "sha256", "profile", "status"}:
            raise ValueError("parent dispatch reference is malformed")
        if not isinstance(reference["path"], str) or not reference["path"].strip() or not isinstance(reference["sha256"], str) or len(reference["sha256"]) != 64 or any(character not in "0123456789abcdef" for character in reference["sha256"]):
            raise ValueError("parent dispatch reference path or digest is malformed")
        if reference["profile"] not in MODES or reference["status"] not in {"running", "attention", "completed", "failed"}:
            raise ValueError("parent dispatch reference profile or status is invalid")
        resolved = str(Path(reference["path"]).resolve())
        if expected_artifact_root not in Path(resolved).parents or resolved in seen_dispatch_paths:
            raise ValueError("parent dispatch references must be unique files under artifact_root")
        seen_dispatch_paths.add(resolved)
    if state["status"] != "starting" and not state["parent"]["thread_id"]:
        raise ValueError("non-starting parent state requires a thread id")
    if state["status"] in {"running", "awaiting_owner", "completed"} and mode["confirmed"] not in MODES:
        raise ValueError("active parent state requires a confirmed profile")


def artifact_root(state: dict[str, Any]) -> Path:
    validate_state(state)
    path = Path(state["artifact_root"])
    path.mkdir(parents=True, exist_ok=True)
    return path


def _dispatch_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def register_dispatch(parent_state_path: Path, parent_state: dict[str, Any], dispatch_state_path: Path) -> dict[str, Any]:
    validate_state(parent_state)
    dispatch = read_json(dispatch_state_path)
    validate_dispatch_state(dispatch)
    required = {"schema_version", "profile", "repository_root", "parent_run_id", "parent_thread_id", "status", "tasks"}
    if required - set(dispatch) or dispatch.get("schema_version") != "codex-crew.state.v0":
        raise ValueError("dispatch state is not a current Crew dispatch state")
    if parent_state["mode"]["confirmed"] not in MODES:
        raise ValueError("dispatch registration requires a confirmed parent profile")
    if dispatch["profile"] != parent_state["mode"]["confirmed"] or Path(dispatch["repository_root"]).resolve() != Path(parent_state["repository_root"]).resolve() or dispatch["parent_run_id"] != parent_state["run_id"] or dispatch["parent_thread_id"] != parent_state["parent"]["thread_id"]:
        raise ValueError("dispatch state is not bound to the current parent run/thread/profile")
    resolved = dispatch_state_path.resolve()
    if artifact_root(parent_state) not in resolved.parents:
        raise ValueError("dispatch state must remain under the harness-owned run artifact root")
    ref = {"path": str(resolved), "sha256": _dispatch_digest(resolved), "profile": dispatch["profile"], "status": dispatch["status"]}
    parent_state["dispatch_refs"] = [item for item in parent_state["dispatch_refs"] if item.get("path") != str(resolved)]
    parent_state["dispatch_refs"].append(ref)
    _event(parent_state, "dispatch_registered", **ref)
    write_json_atomic(parent_state_path, parent_state)
    return ref


def _strip_json_block(message: str) -> str:
    candidate = message.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        return candidate[7:-3].strip()
    return candidate


def parse_route(message: str, expected_run_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(_strip_json_block(message))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    required = {"schema_version", "run_id", "status", "recommended_mode", "rationale", "required_inputs"}
    if required - set(value) or value.get("schema_version") != PARENT_ROUTE_SCHEMA_VERSION or value.get("run_id") != expected_run_id:
        return None
    if value.get("status") != "awaiting_mode_confirmation" or value.get("recommended_mode") not in MODES or not isinstance(value.get("rationale"), str) or not isinstance(value.get("required_inputs"), list):
        return None
    return value


def parse_status(message: str, expected_run_id: str) -> dict[str, Any] | None:
    try:
        value = json.loads(_strip_json_block(message))
    except json.JSONDecodeError:
        return None
    if not isinstance(value, dict):
        return None
    required = {"schema_version", "run_id", "status", "summary"}
    if required - set(value) or value.get("schema_version") != PARENT_STATUS_SCHEMA_VERSION or value.get("run_id") != expected_run_id:
        return None
    if value.get("status") not in {"running", "awaiting_owner", "awaiting_mode_confirmation", "completed", "failed"} or not isinstance(value.get("summary"), str) or not value["summary"].strip():
        return None
    owner_request = value.get("owner_request")
    if "owner_request" in value and (not isinstance(owner_request, dict) or set(owner_request) != {"category", "detail", "question"} or owner_request.get("category") not in OWNER_CATEGORIES or any(not isinstance(owner_request.get(key), str) or not owner_request[key].strip() for key in ("detail", "question"))):
        return None
    if value.get("status") == "awaiting_owner" and owner_request is None:
        return None
    mode_request = value.get("mode_request")
    if "mode_request" in value and (not isinstance(mode_request, dict) or mode_request.get("recommended_mode") not in MODES or not isinstance(mode_request.get("rationale"), str) or not mode_request["rationale"].strip()):
        return None
    if value.get("status") == "awaiting_mode_confirmation" and mode_request is None:
        return None
    return value


def _parent_prompt(state: dict[str, Any], phase: str, message: str = "") -> str:
    common = (
        "You are the single persistent Codex Crew parent for this user request. "
        "The interactive main session is a user-facing broker: it forwards the issue, mode confirmation, ordinary corrections, and owner decisions. "
        "Do all execution orchestration here. Do not ask the main session to create worktrees, start workers, collect worker results, or perform implementation actions. "
        f"Use {Path(__file__).resolve().as_posix()} for worker/worktree primitives. Every independent worker gets a fresh thread and a distinct worktree. Do not edit the controller repository root; only update the parent/dispatch state, harness artifacts, and isolated worker worktrees. "
    )
    if phase == "route":
        return common + (
            "This is a read-only routing turn. Inspect the issue, do not modify files, do not create worktrees, and do not dispatch workers. "
            f"Return exactly one JSON object with schema_version={PARENT_ROUTE_SCHEMA_VERSION!r}, run_id={state['run_id']!r}, "
            'status="awaiting_mode_confirmation", recommended_mode="lite|full", rationale, and required_inputs (array). '
            f"Issue:\n{state['issue']}"
        )
    mode = state["mode"]["confirmed"]
    mode_rules = (
        "Use the Lite profile: the issue must remain bounded and non-redesign; use the dispatcher for worktrees, fresh workers, structured worker results, and basic diff/test evidence. Do not load or invent full Harness policy."
        if mode == "lite"
        else
        "Use the Full profile: load the canonical codex-harness runtime policy, preserve its design_baseline maturity, and use the existing Harness/Impl-Package/verifier seams when applicable. Do not execute an unapproved package or expand authority. Record policy identity and use the dispatcher only for disjoint worker units."
    )
    contract = (
        f"Return exactly one JSON object with schema_version={PARENT_STATUS_SCHEMA_VERSION!r}, run_id={state['run_id']!r}, "
        'status="running|awaiting_owner|awaiting_mode_confirmation|completed|failed", summary, and optional owner_request '
        '(category/detail/question) or mode_request (recommended_mode/rationale). needs_owner and mode changes pause only this continuation; '
        "they do not terminate the overall request."
    )
    binding = (
        f"Parent run_id={state['run_id']}, parent_thread_id={state['parent']['thread_id']}, parent_state={state.get('state_path', '')}, artifact_root={state['artifact_root']}. "
        "Every dispatch manifest must include the exact parent_run_id, parent_thread_id, confirmed profile, and repository_root. "
        f"Initialize a parent-bound dispatch state with `{Path(__file__).resolve().parent.joinpath('codex_harness_dispatch.py').as_posix()} init-state --manifest <manifest> --parent-state {state.get('state_path', '<parent-state>')} --state {state['artifact_root']}/<dispatch>.state.json`, keep it under artifact_root, and register it with `{Path(__file__).resolve().as_posix()} register-dispatch --state {state.get('state_path', '<parent-state>')} --dispatch-state <dispatch-state>` so the main session can inspect task outcomes. "
    )
    return common + mode_rules + "\n" + binding + contract + "\nMain-session update:\n" + message


def _load_full_policy(state: dict[str, Any], state_path: Path) -> tuple[dict[str, Any], ResourceLedger]:
    root = Path(state["harness_root"])
    try:
        bundle = load_runtime_policy(root)
    except PolicyError as error:
        raise RuntimeError(f"full mode runtime policy validation failed: {error}") from error
    state["policy_identity"] = bundle["identity"]
    ledger = ResourceLedger(artifact_root(state) / "resource-ledger.jsonl", state["run_id"])
    return bundle, ledger


def _run_turn(state: dict[str, Any], state_path: Path, prompt: str, *, resume: bool, timeout_seconds: int) -> dict[str, Any]:
    validate_state(state)
    parent = state["parent"]
    profile = _read_profile(Path(parent["profile_path"]))
    mode = state["mode"]["confirmed"]
    if resume and mode not in MODES:
        raise ValueError("parent cannot resume before the main session confirms Lite or Full")
    lease: ThreadLease | None = None
    ledger: ResourceLedger | None = None
    if resume:
        if mode == "full":
            _bundle, ledger = _load_full_policy(state, state_path)
        lease = ThreadLease(artifact_root(state), parent["thread_id"], state["run_id"])
        lease.acquire()
        if ledger is not None:
            ledger.append("thread", parent["thread_id"], "continuation_started", "crew parent controller", mode=mode)
    stderr_path = artifact_root(state) / "parent.stderr.log"
    before = git_status(Path(state["repository_root"]))
    session: JsonRpcSession | None = None
    try:
        session = JsonRpcSession(app_server_command(approval_policy=parent["approval_policy"]), stderr_path)
        session.request(1, "initialize", initialize_params("codex-crew-parent"), 30)
        if resume:
            session.request(2, "thread/resume", {"threadId": parent["thread_id"], "cwd": state["repository_root"], "sandbox": parent["sandbox"], "approvalPolicy": parent["approval_policy"], "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
        else:
            started, _ = session.request(2, "thread/start", {"cwd": state["repository_root"], "sandbox": parent["sandbox"], "approvalPolicy": parent["approval_policy"], "ephemeral": False, "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
            parent["thread_id"] = started["thread"]["id"]
        started_turn, notifications = session.request(3, "turn/start", {"threadId": parent["thread_id"], "input": [{"type": "text", "text": prompt}], "approvalPolicy": parent["approval_policy"], "sandboxPolicy": {"type": "readOnly" if parent["sandbox"] == "read-only" else "workspaceWrite", "networkAccess": False}}, 30)
        if not any(item.get("method") == "turn/completed" and item.get("params", {}).get("threadId") == parent["thread_id"] for item in notifications):
            notifications.extend(session.collect_until_turn_complete(parent["thread_id"], timeout_seconds))
        try:
            history, history_notifications = session.request(4, "thread/read", {"threadId": parent["thread_id"], "includeTurns": True}, 30)
        except RuntimeError:
            history, history_notifications = {}, []
        messages = walk_root_agent_messages(notifications + history_notifications + [history], parent["thread_id"])
        message = messages[-1] if messages else ""
        after = git_status(Path(state["repository_root"]))
        if before != after:
            raise RuntimeError("parent modified the controller repository worktree; worker mutations must stay in isolated worktrees")
        return {"thread_id": parent["thread_id"], "turn_id": started_turn.get("turn", {}).get("id"), "message": message}
    finally:
        if session is not None:
            session.close()
        try:
            if ledger is not None:
                ledger.append("thread", parent["thread_id"], "continuation_closed", "crew parent controller", mode=mode)
        finally:
            if lease is not None and lease.acquired:
                lease.release()


def _apply_control(state: dict[str, Any], message: str) -> dict[str, Any] | None:
    route = parse_route(message, state["run_id"])
    if route is not None:
        state["mode"] = {"status": "awaiting_confirmation", "proposed": route["recommended_mode"], "confirmed": None, "rationale": route["rationale"]}
        state["status"] = "awaiting_mode_confirmation"
        _event(state, "mode_proposed", recommended_mode=route["recommended_mode"], required_inputs=route["required_inputs"])
        return route
    status = parse_status(message, state["run_id"])
    if status is None:
        state["status"] = "failed"
        _event(state, "parent_protocol_invalid", message_digest=hashlib.sha256(message.encode("utf-8")).hexdigest())
        return None
    if status["status"] == "awaiting_owner":
        state["status"] = "awaiting_owner"
        if status.get("owner_request"):
            state["decision_requests"].append(status["owner_request"])
        _event(state, "owner_decision_requested", request=status.get("owner_request"))
    elif status["status"] == "awaiting_mode_confirmation":
        request = status.get("mode_request") or {}
        state["mode"]["status"] = "awaiting_confirmation"
        state["mode"]["proposed"] = request.get("recommended_mode")
        state["mode"]["rationale"] = request.get("rationale", status["summary"])
        state["status"] = "awaiting_mode_confirmation"
        _event(state, "mode_change_requested", request=request)
    else:
        state["status"] = status["status"]
    return status


def start_parent(state_path: Path, state: dict[str, Any], timeout_seconds: int) -> dict[str, Any]:
    result = _run_turn(state, state_path, _parent_prompt(state, "route"), resume=False, timeout_seconds=timeout_seconds)
    state["last_message"] = result["message"]
    _event(state, "parent_started", thread_id=result["thread_id"], turn_id=result["turn_id"])
    control = _apply_control(state, result["message"])
    write_json_atomic(state_path, state)
    return {"state": state, "control": control, **result}


def confirm_mode(state_path: Path, state: dict[str, Any], mode: str, timeout_seconds: int) -> dict[str, Any]:
    validate_state(state)
    if mode not in MODES:
        raise ValueError("mode must be lite or full")
    if state["status"] != "awaiting_mode_confirmation":
        raise ValueError("mode confirmation requires awaiting_mode_confirmation state")
    proposed = state["mode"]["proposed"]
    current = state["mode"]["confirmed"]
    if proposed != mode and not (current == "lite" and mode == "full"):
        raise ValueError(f"mode {mode!r} is not the current parent proposal")
    if current == "full" and mode == "lite":
        raise ValueError("full mode cannot be downgraded within a parent run")
    if mode == "full":
        _load_full_policy(state, state_path)
        state["parent"]["sandbox"] = "workspace-write"
    else:
        state["parent"]["sandbox"] = "workspace-write"
    state["mode"] = {"status": "confirmed", "proposed": mode, "confirmed": mode, "rationale": state["mode"]["rationale"]}
    state["status"] = "running"
    _event(state, "mode_confirmed", mode=mode)
    try:
        result = _run_turn(state, state_path, _parent_prompt(state, "execute", f"Main session confirmed mode={mode}. Continue the issue now."), resume=True, timeout_seconds=timeout_seconds)
    except BaseException as error:
        state["status"] = "failed"
        _event(state, "parent_continuation_failed", mode=mode, error=str(error))
        write_json_atomic(state_path, state)
        raise
    state["last_message"] = result["message"]
    _event(state, "parent_continued", thread_id=result["thread_id"], turn_id=result["turn_id"], mode=mode)
    control = _apply_control(state, result["message"])
    write_json_atomic(state_path, state)
    return {"state": state, "control": control, **result}


def continue_parent(state_path: Path, state: dict[str, Any], message: str, timeout_seconds: int) -> dict[str, Any]:
    validate_state(state)
    if state["status"] not in {"running", "awaiting_owner"}:
        raise ValueError("parent continuation requires running or awaiting_owner state")
    if state["status"] == "awaiting_owner":
        _event(state, "owner_decision_forwarded", detail=message)
    try:
        result = _run_turn(state, state_path, _parent_prompt(state, "execute", message), resume=True, timeout_seconds=timeout_seconds)
    except BaseException as error:
        state["status"] = "failed"
        _event(state, "parent_continuation_failed", mode=state["mode"]["confirmed"], error=str(error))
        write_json_atomic(state_path, state)
        raise
    state["last_message"] = result["message"]
    _event(state, "parent_continued", thread_id=result["thread_id"], turn_id=result["turn_id"], mode=state["mode"]["confirmed"])
    control = _apply_control(state, result["message"])
    write_json_atomic(state_path, state)
    return {"state": state, "control": control, **result}


def _issue_from_args(args: argparse.Namespace) -> str:
    if args.issue is not None:
        return args.issue.strip()
    return args.issue_file.read_text(encoding="utf-8").strip()


def main() -> int:
    parser = argparse.ArgumentParser(description="Control one persistent Codex Crew parent thread.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    start = subparsers.add_parser("start")
    start.add_argument("--repository-root", type=Path, required=True)
    issue_group = start.add_mutually_exclusive_group(required=True)
    issue_group.add_argument("--issue")
    issue_group.add_argument("--issue-file", type=Path)
    start.add_argument("--state", type=Path, required=True)
    start.add_argument("--parent-profile", type=Path)
    start.add_argument("--harness-root", type=Path)
    start.add_argument("--run-id")
    start.add_argument("--timeout-seconds", type=int, default=900)
    confirm = subparsers.add_parser("confirm-mode")
    confirm.add_argument("--state", type=Path, required=True)
    confirm.add_argument("--mode", choices=sorted(MODES), required=True)
    confirm.add_argument("--timeout-seconds", type=int, default=900)
    cont = subparsers.add_parser("continue")
    cont.add_argument("--state", type=Path, required=True)
    message_group = cont.add_mutually_exclusive_group(required=True)
    message_group.add_argument("--message")
    message_group.add_argument("--message-file", type=Path)
    cont.add_argument("--timeout-seconds", type=int, default=900)
    status = subparsers.add_parser("status")
    status.add_argument("--state", type=Path, required=True)
    register = subparsers.add_parser("register-dispatch")
    register.add_argument("--state", type=Path, required=True)
    register.add_argument("--dispatch-state", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "start":
        root = args.repository_root.resolve()
        profile_path = (args.parent_profile or root / ".codex" / "harness" / "crew-parent.toml").resolve()
        issue = _issue_from_args(args)
        if not issue:
            raise ValueError("issue must not be empty")
        state = new_state(root, issue, profile_path, args.run_id, args.harness_root)
        state["state_path"] = str(args.state.resolve())
        write_json_atomic(args.state, state)
        try:
            result = start_parent(args.state, state, args.timeout_seconds)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 1 if result["state"]["status"] == "failed" else 0
        except BaseException:
            state["status"] = "failed"
            _event(state, "parent_start_failed")
            write_json_atomic(args.state, state)
            raise
    state = read_json(args.state)
    validate_state(state)
    if args.command == "confirm-mode":
        result = confirm_mode(args.state, state, args.mode, args.timeout_seconds)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["state"]["status"] == "failed" else 0
    if args.command == "continue":
        message = args.message if args.message is not None else args.message_file.read_text(encoding="utf-8")
        result = continue_parent(args.state, state, message, args.timeout_seconds)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result["state"]["status"] == "failed" else 0
    if args.command == "status":
        print(json.dumps(state, ensure_ascii=False, indent=2))
        return 0
    if args.command == "register-dispatch":
        print(json.dumps(register_dispatch(args.state, state, args.dispatch_state), ensure_ascii=False, indent=2))
        return 0
    raise AssertionError("unreachable")


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, PolicyError, LedgerIntegrityError, RuntimeError, TimeoutError) as error:
        print(f"[X] {error}", file=sys.stderr)
        raise SystemExit(1)
