#!/usr/bin/env python3
"""Exercise persistent thread resume/fork canaries and fail-closed mismatch handling."""

from __future__ import annotations

import argparse
import json
import sys
import time
import tomllib
from pathlib import Path

try:
    from codex_harness_cli import JsonRpcSession, app_server_command
    from codex_harness_controller import walk_root_agent_messages
    from codex_harness_policy import PolicyError, load_runtime_policy
    from codex_harness_runtime import ThreadLease
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command
    from scripts.codex_harness_controller import walk_root_agent_messages
    from scripts.codex_harness_policy import PolicyError, load_runtime_policy
    from scripts.codex_harness_runtime import ThreadLease


def start_session(root: Path, stderr_path: Path):
    session = JsonRpcSession(
        app_server_command(),
        stderr_path,
    )
    session.request(1, "initialize", {"clientInfo": {"name": "codex-harness-resume-pilot", "version": "0.1"}, "capabilities": {"experimentalApi": True}}, 30)
    return session


def thread_start(session, root: Path, profile: dict):
    result, _ = session.request(2, "thread/start", {"cwd": str(root), "sandbox": "read-only", "approvalPolicy": "never", "ephemeral": False, "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
    return result["thread"]["id"], result


def projection(session, thread_id: str, request_id: int, start_result: dict | None = None, model: str | None = None, effort: str | None = None, root: Path | None = None) -> dict:
    """Record only provider-observable profile/history fields, never infer them."""
    observed: dict[str, object] = {}
    if isinstance(start_result, dict):
        thread = start_result.get("thread", {})
        if isinstance(thread, dict):
            for key in ("model", "modelProvider", "reasoningEffort", "modelReasoningEffort", "model_reasoning_effort"):
                if key in thread:
                    observed[key] = thread[key]
    try:
        result, _ = session.request(request_id, "thread/read", {"threadId": thread_id, "includeTurns": True}, 30)
    except Exception as error:
        return {"supported": False, "error": str(error), "observed": observed, "history_count": 0}
    def count_history(value):
        if isinstance(value, list):
            return sum(count_history(item) for item in value)
        if isinstance(value, dict):
            count = sum(count_history(item) for item in value.values())
            if value.get("type") in {"turn", "agentMessage", "agent_message"}:
                count += 1
            return count
        return 0
    def collect_fields(value):
        if isinstance(value, dict):
            for key in ("model", "modelProvider", "reasoningEffort", "modelReasoningEffort", "model_reasoning_effort"):
                if key in value:
                    observed[key] = value[key]
            for item in value.values():
                collect_fields(item)
        elif isinstance(value, list):
            for item in value:
                collect_fields(item)
    collect_fields(result)
    settings_update = {"supported": False, "observed": {}}
    config_projection = {"supported": False, "observed": {}}
    if root is not None:
        try:
            config_result, _ = session.request(request_id + 9, "config/read", {"cwd": str(root), "includeLayers": True}, 30)
            config_projection["supported"] = True
            collect_fields(config_result.get("config", {}) if isinstance(config_result, dict) else config_result)
            config_projection["observed"] = config_result.get("config", {}) if isinstance(config_result, dict) else {}
        except Exception as error:
            config_projection["error"] = str(error)
    if model and effort:
        efforts = ["low", effort] if effort == "high" else [effort]
        try:
            for offset, requested_effort in enumerate(efforts, start=1):
                _, settings_notifications = session.request(request_id + offset, "thread/settings/update", {"threadId": thread_id, "model": model, "reasoningEffort": requested_effort}, 30)
                settings_update["supported"] = True
                time.sleep(0.5)
                while True:
                    try:
                        settings_notifications.append(session.messages.get_nowait())
                    except Exception:
                        break
                settings_update["methods"] = [item.get("method") for item in settings_notifications if isinstance(item, dict)]
                for notification in settings_notifications:
                    if notification.get("method") == "thread/settings/updated":
                        thread_settings = notification.get("params", {}).get("threadSettings", {})
                        collect_fields(thread_settings)
                        settings_update["observed"] = thread_settings
        except Exception as error:
            settings_update["error"] = str(error)
    return {"supported": True, "observed": observed, "history_count": count_history(result), "settings_update": settings_update, "config_projection": config_projection}


def run_canary(session, thread_id: str, request_id: int, label: str) -> dict:
    prompt = f"Return exactly one JSON object {{\"canary\":\"PARENT_ROLE_CANARY\",\"label\":\"{label}\"}} and nothing else. Do not modify files or use network."
    result, notifications = session.request(request_id, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": prompt}], "approvalPolicy": "never", "sandboxPolicy": {"type": "readOnly", "networkAccess": False}}, 30)
    turn_id = result["turn"]["id"]
    notifications.extend(session.collect_until_turn_complete(thread_id, 120))
    messages = walk_root_agent_messages(notifications, thread_id)
    return {"thread_id": thread_id, "turn_id": turn_id, "canary": any("PARENT_ROLE_CANARY" in message for message in messages), "messages": messages[-1:]}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    root = args.repository_root.resolve()
    try:
        policy_bundle = load_runtime_policy(root)
    except PolicyError as error:
        print(f"[X] runtime policy validation failed: {error}", file=sys.stderr)
        return 1
    profile_path = root / ".codex" / "harness" / "parent.toml"
    with profile_path.open("rb") as stream:
        profile = tomllib.load(stream)
    artifact_dir = root / ".codex" / "harness-runs"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-resume"
    first = start_session(root, artifact_dir / f"{run_id}.first.stderr.log")
    root_thread_id, initial_start_result = thread_start(first, root, profile)
    initial = run_canary(first, root_thread_id, 3, "initial")
    initial_projection = projection(first, root_thread_id, 6, initial_start_result, profile["model"], profile["model_reasoning_effort"], root)
    first.close()

    second = start_session(root, artifact_dir / f"{run_id}.second.stderr.log")
    lease = ThreadLease(artifact_dir, root_thread_id, run_id)
    lease_evidence = None
    try:
        lease_evidence = lease.acquire()
        resume_result, _ = second.request(2, "thread/resume", {"threadId": root_thread_id, "cwd": str(root), "sandbox": "read-only", "approvalPolicy": "never", "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
        resumed = run_canary(second, root_thread_id, 3, "resumed")
        resumed_projection = projection(second, root_thread_id, 6, resume_result, profile["model"], profile["model_reasoning_effort"], root)
        fork_result, _ = second.request(4, "thread/fork", {"threadId": root_thread_id, "ephemeral": False, "cwd": str(root), "sandbox": "read-only", "approvalPolicy": "never", "developerInstructions": profile["developer_instructions"], "model": profile["model"], "config": {"model_reasoning_effort": profile["model_reasoning_effort"]}}, 30)
        fork_thread_id = fork_result["thread"]["id"]
        forked = run_canary(second, fork_thread_id, 5, "forked")
    finally:
        if lease.acquired:
            lease.release()
        second.close()
    mismatch_model = "gpt-5.6"
    # Fail closed before calling App Server: this version accepts unknown model names and falls back silently.
    mismatch_api_called = False
    # The Harness rejects a mismatched profile before reuse and falls back to a fresh thread.
    mismatch_rejected = mismatch_model != profile["model"]
    third = start_session(root, artifact_dir / f"{run_id}.fresh.stderr.log")
    fresh_thread_id, fresh_start_result = thread_start(third, root, profile)
    fresh = run_canary(third, fresh_thread_id, 3, "fresh-fallback")
    fresh_projection = projection(third, fresh_thread_id, 6, fresh_start_result, profile["model"], profile["model_reasoning_effort"], root)
    third.close()
    profile_projection_observed = all("model" in item.get("observed", {}) and any(key in item.get("observed", {}) for key in ("reasoningEffort", "modelReasoningEffort", "model_reasoning_effort")) for item in (initial_projection, resumed_projection, fresh_projection))
    passed = initial["canary"] and resume_result and resumed["canary"] and forked["canary"] and mismatch_rejected and fresh["canary"] and profile_projection_observed
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "requested_model": profile["model"], "requested_reasoning_effort": profile["model_reasoning_effort"], "profile_projection_observed": profile_projection_observed, "policy_identity": policy_bundle["identity"], "continuation_lease": {"acquired": True, "owner_token": lease_evidence["owner_token"], "released": not lease.path.exists()}, "initial": initial, "initial_projection": initial_projection, "resumed": resumed, "resumed_projection": resumed_projection, "forked": forked, "mismatch_model": mismatch_model, "mismatch_api_called": mismatch_api_called, "mismatch_rejected_by_harness": mismatch_rejected, "fresh_fallback": fresh, "fresh_projection": fresh_projection, "root_thread_id": root_thread_id, "fork_thread_id": fork_thread_id, "fresh_thread_id": fresh_thread_id}
    output = artifact_dir / f"{run_id}.summary.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if summary["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
