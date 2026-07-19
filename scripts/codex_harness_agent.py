"""Reusable App Server role-turn runner for Codex Crew agents."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

try:
    from codex_harness_cli import JsonRpcSession, TurnControlRequested, app_server_command, initialize_params
    from codex_harness_control import read_cancel_request
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, TurnControlRequested, app_server_command, initialize_params
    from scripts.codex_harness_control import read_cancel_request


class RoleTurnError(RuntimeError):
    """A role turn configuration cannot preserve the Crew control boundary."""


def _terminal_status(events: list[dict[str, Any]], thread_id: str, turn_id: str | None = None) -> str | None:
    for event in reversed(events):
        if event.get("method") != "turn/completed":
            continue
        params = event.get("params")
        if not isinstance(params, dict) or params.get("threadId") != thread_id:
            continue
        turn = params.get("turn")
        completed_turn_id = params.get("turnId")
        if completed_turn_id is None and isinstance(turn, dict):
            completed_turn_id = turn.get("id") or turn.get("turnId")
        if turn_id is not None and completed_turn_id != turn_id:
            continue
        candidate = params.get("status")
        if not isinstance(candidate, str) and isinstance(turn, dict):
            candidate = turn.get("status")
        return candidate.strip().lower() if isinstance(candidate, str) and candidate.strip() else "completed"
    return None


def _sandbox_policy(sandbox: str, writable_roots: list[Path] | None = None) -> dict[str, Any]:
    if sandbox == "read-only":
        if writable_roots:
            raise RoleTurnError("read-only role turns cannot declare writable roots")
        return {"type": "readOnly", "networkAccess": False}
    if sandbox == "workspace-write":
        roots = []
        for root in writable_roots or []:
            resolved = Path(root).resolve()
            if not resolved.is_absolute() or str(resolved) in roots:
                raise RoleTurnError("workspace-write roots must be unique absolute paths")
            roots.append(str(resolved))
        return {"type": "workspaceWrite", "writableRoots": roots, "networkAccess": False}
    raise RoleTurnError(f"unsupported role-turn sandbox: {sandbox}")


def _cancelled_before_start(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "cancelled",
        "thread_id": None,
        "turn_id": None,
        "cancel_request": request,
        "interrupt": {"attempted": False, "acknowledged": False, "error": None},
        "terminal": {"observed": True, "status": "not_started", "source": "pre_turn_cancel"},
        "notifications": [],
        "history": None,
    }


def _cancelled_after_terminal(
    request: dict[str, Any],
    *,
    thread_id: str,
    turn_id: str,
    terminal: str,
    notifications: list[dict[str, Any]],
    history: Any,
) -> dict[str, Any]:
    """Prefer an explicit cancel received before a terminal result is applied.

    The role turn is already proven terminal, so sending an interrupt would be
    both redundant and racy.  The controller must discard the business result
    while retaining the terminal evidence that makes cancellation conclusive.
    """

    return {
        "status": "cancelled",
        "thread_id": thread_id,
        "turn_id": turn_id,
        "cancel_request": request,
        "interrupt": {"attempted": False, "acknowledged": False, "error": None},
        "terminal": {"observed": True, "status": terminal, "source": "turn/completed"},
        "notifications": notifications,
        "history": history,
    }


def _finish_cancel(
    session: JsonRpcSession,
    *,
    request: dict[str, Any],
    thread_id: str,
    turn_id: str,
    notifications: list[dict[str, Any]],
    request_id: int,
    confirmation_seconds: float,
) -> dict[str, Any]:
    interrupt = {"attempted": True, "acknowledged": False, "error": None}
    try:
        _, interrupt_events = session.request(
            request_id,
            "turn/interrupt",
            {"threadId": thread_id, "turnId": turn_id},
            30,
        )
        interrupt["acknowledged"] = True
        notifications.extend(interrupt_events)
    except (RuntimeError, TimeoutError) as error:
        interrupt["error"] = str(error)
    terminal = _terminal_status(notifications, thread_id, turn_id)
    if terminal is None:
        try:
            notifications.extend(session.collect_until_turn_complete(thread_id, confirmation_seconds, expected_turn_id=turn_id))
        except (RuntimeError, TimeoutError) as error:
            if interrupt["error"] is None:
                interrupt["error"] = str(error)
        terminal = _terminal_status(notifications, thread_id, turn_id)
    if terminal is None:
        return {
            "status": "quarantined",
            "thread_id": thread_id,
            "turn_id": turn_id,
            "cancel_request": request,
            "interrupt": interrupt,
            "terminal": {"observed": False, "status": None, "source": None},
            "quarantine": {"reason": "turn_stop_unconfirmed", "observed_at": time.time()},
            "notifications": notifications,
            "history": None,
        }
    return {
        "status": "cancelled",
        "thread_id": thread_id,
        "turn_id": turn_id,
        "cancel_request": request,
        "interrupt": interrupt,
        "terminal": {"observed": True, "status": terminal, "source": "turn/completed"},
        "notifications": notifications,
        "history": None,
    }


def run_role_turn(
    *,
    state_path: Path,
    run_id: str,
    role: str,
    cwd: Path,
    prompt: str,
    execution: dict[str, str],
    stderr_path: Path,
    sandbox: str,
    writable_roots: list[Path] | None = None,
    thread_id: str | None = None,
    approval_policy: str = "never",
    enable_multi_agent: bool = True,
    ephemeral: bool = False,
    observation_interval_seconds: float | None = None,
    on_observation: Callable[[dict[str, Any]], None] | None = None,
    on_thread_started: Callable[[str], None] | None = None,
    on_turn_started: Callable[[str, str], None] | None = None,
    on_cancelling: Callable[[dict[str, Any]], None] | None = None,
    interrupt_confirmation_seconds: float = 30,
    session_factory: Callable[[list[str], Path], JsonRpcSession] = JsonRpcSession,
) -> dict[str, Any]:
    """Run one fresh or resumed role turn with explicit persisted cancellation.

    Normal turns have no duration-based interrupt.  The only interrupt path is
    a valid cancel sidecar bound to ``run_id``.  Callbacks are invoked at the
    identity boundary so the controller can durably record a thread, turn, or
    cancelling transition before the next App Server action.
    """

    state_path = Path(state_path)
    cwd = Path(cwd)
    stderr_path = Path(stderr_path)
    if not isinstance(run_id, str) or not run_id.strip() or not isinstance(role, str) or not role.strip():
        raise RoleTurnError("run_id and role are required")
    if not isinstance(prompt, str) or not prompt.strip():
        raise RoleTurnError("role-turn prompt is required")
    if not isinstance(execution, dict) or any(not isinstance(execution.get(field), str) or not execution[field].strip() for field in ("model", "reasoning_effort")):
        raise RoleTurnError("role-turn execution must bind model and reasoning_effort")
    if interrupt_confirmation_seconds <= 0:
        raise RoleTurnError("interrupt confirmation window must be positive")
    sandbox_policy = _sandbox_policy(sandbox, writable_roots)
    if role == "verifier" and (thread_id is not None or sandbox != "read-only" or enable_multi_agent):
        raise RoleTurnError("verifier turns must be fresh, read-only, and have multi-agent disabled")

    def poll_cancel() -> dict[str, Any] | None:
        return read_cancel_request(state_path, run_id)

    command = app_server_command(enable_multi_agent=enable_multi_agent, approval_policy=approval_policy)
    with session_factory(command, stderr_path) as session:
        session.request(1, "initialize", initialize_params(f"codex-crew-{role}"), 30)
        pending = poll_cancel()
        if pending is not None:
            if on_cancelling is not None:
                on_cancelling(pending)
            return _cancelled_before_start(pending)
        if thread_id is None:
            started, _ = session.request(
                2,
                "thread/start",
                {
                    "cwd": str(cwd),
                    "sandbox": sandbox,
                    "approvalPolicy": approval_policy,
                    "ephemeral": True if role == "verifier" else ephemeral,
                    "model": execution["model"],
                    "config": {"model_reasoning_effort": execution["reasoning_effort"]},
                },
                30,
            )
            started_thread_id = started.get("thread", {}).get("id")
            if not isinstance(started_thread_id, str) or not started_thread_id.strip():
                raise RoleTurnError("thread/start did not return a thread id")
            thread_id = started_thread_id
        else:
            session.request(
                2,
                "thread/resume",
                {
                    "threadId": thread_id,
                    "cwd": str(cwd),
                    "sandbox": sandbox,
                    "approvalPolicy": approval_policy,
                    "model": execution["model"],
                    "config": {"model_reasoning_effort": execution["reasoning_effort"]},
                },
                30,
            )
        if on_thread_started is not None:
            on_thread_started(thread_id)
        pending = poll_cancel()
        if pending is not None:
            if on_cancelling is not None:
                on_cancelling(pending)
            result = _cancelled_before_start(pending)
            result["thread_id"] = thread_id
            return result
        started_turn, start_events = session.request(
            3,
            "turn/start",
            {
                "threadId": thread_id,
                "input": [{"type": "text", "text": prompt}],
                "approvalPolicy": approval_policy,
                "sandboxPolicy": sandbox_policy,
            },
            30,
        )
        turn_id = started_turn.get("turn", {}).get("id")
        if not isinstance(turn_id, str) or not turn_id.strip():
            raise RoleTurnError("turn/start did not return a turn id")
        if on_turn_started is not None:
            on_turn_started(thread_id, turn_id)
        notifications = list(start_events)
        terminal = _terminal_status(notifications, thread_id, turn_id)
        if terminal is None:
            try:
                notifications.extend(
                    session.collect_until_turn_complete(
                        thread_id,
                        None,
                        expected_turn_id=turn_id,
                        observation_interval_seconds=observation_interval_seconds,
                        on_observation=on_observation,
                        control_poll_interval_seconds=1.0,
                        on_control_poll=poll_cancel,
                    )
                )
            except TurnControlRequested as control:
                if on_cancelling is not None:
                    on_cancelling(control.request)
                return _finish_cancel(
                    session,
                    request=control.request,
                    thread_id=thread_id,
                    turn_id=turn_id,
                    notifications=notifications,
                    request_id=4,
                    confirmation_seconds=interrupt_confirmation_seconds,
                )
            terminal = _terminal_status(notifications, thread_id, turn_id)
        if terminal is None:
            raise RoleTurnError("turn collection ended without terminal evidence")
        history_params = {"threadId": thread_id}
        if not (role == "verifier" or ephemeral):
            history_params["includeTurns"] = True
        history, history_events = session.request(4, "thread/read", history_params, 30)
        notifications.extend(history_events)
        pending = poll_cancel()
        if pending is not None:
            if on_cancelling is not None:
                on_cancelling(pending)
            return _cancelled_after_terminal(
                pending,
                thread_id=thread_id,
                turn_id=turn_id,
                terminal=terminal,
                notifications=notifications,
                history=history,
            )
        return {
            "status": terminal,
            "thread_id": thread_id,
            "turn_id": turn_id,
            "cancel_request": None,
            "interrupt": {"attempted": False, "acknowledged": False, "error": None},
            "terminal": {"observed": True, "status": terminal, "source": "turn/completed"},
            "notifications": notifications,
            "history": history,
        }
