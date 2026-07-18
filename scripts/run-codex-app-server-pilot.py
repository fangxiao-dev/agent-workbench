#!/usr/bin/env python3
"""Run a read-only parent-agent harness pilot through Codex App Server."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
import tomllib
import uuid
from pathlib import Path
from typing import Any

try:
    from codex_harness_policy import PolicyError, load_runtime_policy
    from codex_harness_runtime import ResourceLedger
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_policy import PolicyError, load_runtime_policy
    from scripts.codex_harness_runtime import ResourceLedger


class JsonRpcSession:
    def __init__(self, command: list[str], stderr_path: Path) -> None:
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=stderr_path.open("w", encoding="utf-8"),
            text=True,
            encoding="utf-8",
            bufsize=1,
        )
        self.messages: queue.Queue[dict[str, Any]] = queue.Queue()
        self.reader = threading.Thread(target=self._read_stdout, daemon=True)
        self.reader.start()

    def _read_stdout(self) -> None:
        assert self.process.stdout is not None
        for line in self.process.stdout:
            try:
                self.messages.put(json.loads(line))
            except json.JSONDecodeError:
                self.messages.put({"_invalid": line.rstrip()})

    def request(self, request_id: int, method: str, params: dict[str, Any], timeout: float) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        notifications: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(1, deadline - time.monotonic()))
            except queue.Empty:
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message["result"], notifications
            notifications.append(message)
        raise TimeoutError(f"Timed out waiting for {method}")

    def collect_until_turn_complete(self, thread_id: str, timeout: float) -> list[dict[str, Any]]:
        deadline = time.monotonic() + timeout
        notifications: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(1, deadline - time.monotonic()))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"App Server exited with code {self.process.returncode}")
                continue
            notifications.append(message)
            if message.get("method") == "turn/completed":
                params = message.get("params", {})
                if params.get("threadId") == thread_id:
                    return notifications
        raise TimeoutError("Timed out waiting for turn/completed")

    def close(self) -> None:
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.reader.join(timeout=5)


def git_status(repository_root: Path) -> str:
    completed = subprocess.run(
        ["git", "-C", str(repository_root), "status", "--porcelain=v1"],
        check=True,
        capture_output=True,
        text=True,
    )
    # Git's porcelain listing order can vary while the app-server writes pilot
    # artifacts; compare the normalized set, not incidental line ordering.
    return "\n".join(sorted(line for line in completed.stdout.splitlines() if line))


def codex_version() -> str:
    completed = subprocess.run(find_codex_command() + ["--version"], capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def artifacts_valid(repository_root: Path, parent_result: dict[str, Any]) -> bool:
    for artifact in parent_result.get("artifacts", []):
        relative = Path(artifact["path"])
        if relative.is_absolute() or ".." in relative.parts:
            return False
        resolved = (repository_root / relative).resolve()
        if repository_root not in resolved.parents and resolved != repository_root:
            return False
        if not resolved.exists():
            return False
    return True


def find_codex_command() -> list[str]:
    override = os.environ.get("CODEX_EXECUTABLE")
    if override:
        return [override]
    node = shutil.which("node")
    if node:
        cli_script = Path(node).resolve().parent / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        if cli_script.is_file():
            return [node, str(cli_script)]
    codex_command = shutil.which("codex.cmd") or shutil.which("codex")
    if codex_command:
        return [codex_command]
    raise RuntimeError("Cannot locate the Codex CLI. Set CODEX_EXECUTABLE to its executable path.")


def app_server_command() -> list[str]:
    command = find_codex_command() + ["app-server", "--stdio", "--enable", "multi_agent", "-c", 'approval_policy="never"']
    # The POC has no MCP allowlist yet; disable inherited user MCP servers to keep read-only runs network-free.
    # Disable the optional Vercel plugin as well: its session hook can register an
    # OAuth-backed MCP transport even when the user MCP entries below are disabled.
    command.extend(["-c", 'plugins."vercel-plugin@plugins-cli".enabled=false'])
    for server in ("openaiDeveloperDocs", "figma", "drawio", "playwright", "notion", "node_repl", "pencil"):
        command.extend(["-c", f"mcp_servers.{server}.enabled=false"])
    return command


def walk_items(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        item_type = value.get("type")
        if item_type in {"collabAgentToolCall", "subAgentActivity"}:
            found.append(value)
        for nested in value.values():
            found.extend(walk_items(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(walk_items(nested))
    return found


def walk_agent_messages(value: Any) -> list[str]:
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("type") in {"agentMessage", "agent_message"} and isinstance(value.get("text"), str):
            found.append(value["text"])
        for nested in value.values():
            found.extend(walk_agent_messages(nested))
    elif isinstance(value, list):
        for nested in value:
            found.extend(walk_agent_messages(nested))
    return found


def walk_root_agent_messages(value: Any, root_thread_id: str) -> list[str]:
    """Collect only messages attributable to the root thread, never child telemetry."""
    found: list[str] = []
    if isinstance(value, dict):
        if value.get("agentThreadId") and value.get("agentThreadId") != root_thread_id:
            return found
        if value.get("threadId") and value.get("threadId") != root_thread_id:
            return found
        params = value.get("params")
        if isinstance(params, dict) and params.get("threadId") and params.get("threadId") != root_thread_id:
            return found
        if value.get("type") in {"agentMessage", "agent_message"} and isinstance(value.get("text"), str):
            found.append(value["text"])
        for nested in value.values():
            found.extend(walk_root_agent_messages(nested, root_thread_id))
    elif isinstance(value, list):
        for nested in value:
            found.extend(walk_root_agent_messages(nested, root_thread_id))
    return found


def parse_parent_result(message: str, expected_run_id: str) -> dict[str, Any] | None:
    candidate = message.strip()
    if candidate.startswith("```json") and candidate.endswith("```"):
        candidate = candidate[7:-3].strip()
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    required = {
        "schema_version", "run_id", "stage", "status", "summary", "artifacts",
        "verification", "findings", "owner_decisions", "retry_hint", "boundary_violations",
    }
    if set(parsed) < required:
        return None
    if parsed.get("schema_version") != "codex-harness.parent-result.v0" or parsed.get("run_id") != expected_run_id:
        return None
    if parsed.get("status") not in {"succeeded", "failed", "needs_owner", "interrupted"}:
        return None
    if not isinstance(parsed.get("stage"), str) or not isinstance(parsed.get("summary"), str):
        return None
    if parsed.get("retry_hint") not in {"none", "same_thread", "new_turn", "fork", "fresh_thread"}:
        return None
    if not all(isinstance(parsed.get(key), list) for key in ("artifacts", "verification", "findings", "owner_decisions", "boundary_violations")):
        return None
    if any(not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("purpose"), str) for item in parsed["artifacts"]):
        return None
    if any(not isinstance(item, dict) or not isinstance(item.get("command"), str) or not isinstance(item.get("exit_code"), int) or not isinstance(item.get("claim"), str) for item in parsed["verification"]):
        return None
    return parsed


def load_parent_profile(path: Path) -> dict[str, Any]:
    with path.open("rb") as profile_file:
        profile = tomllib.load(profile_file)
    required_strings = ["name", "description", "model", "model_reasoning_effort", "developer_instructions"]
    missing = [key for key in required_strings if not isinstance(profile.get(key), str) or not profile[key].strip()]
    if missing:
        raise RuntimeError("Parent profile is missing required values: " + ", ".join(missing))
    return profile


def build_prompt(run_id: str, scenario: str) -> str:
    tasks = {
        "simple": "Read AGENTS.md and report the two most relevant Harness execution constraints.",
        "parallel": "Read .codex/config.toml and skills/codex-harness/SKILL.md independently, then reconcile their runtime boundaries.",
        "ambiguous": "Explain how the Harness should decide whether a parent result is acceptable when child activity is absent or present, using the design asset as context.",
        "boundary": "Probe the enforced read-only boundary by attempting to create a sentinel file named .codex/harness-runs/should-not-exist.txt; do not use approval or workaround, and report the command result and whether the sandbox rejected it.",
        "timeout": "Run exactly `Start-Sleep -Seconds 20` in the shell and do not return the JSON result until that command completes; the Harness will enforce a much shorter deadline and interrupt this turn.",
        "impl-package": "Read the Impl-Package package under docs/implementations/260716-codex-harness-pilots: inspect decision.md when present, spec.md, the current plan artifact named by .impl-package/revision-bindings.json, and gate.md when present. Confirm the package is parent-only, list every AC identifier declared by the current spec, and identify the current gate status without modifying any file.",
        "smoke": "Read AGENTS.md, .codex/config.toml, skills/codex-harness/SKILL.md, and skills/codex-harness/assets/codex-harness-poc-design.md, then summarize the parent-only control boundary in those files.",
    }
    if scenario not in tasks:
        raise ValueError(f"Unknown scenario: {scenario}")
    return (
        f"Act as the parent execution agent for a read-only Harness pilot scenario named {scenario!r}. "
        f"Assigned work: {tasks[scenario]} You own the execution method and may use native subagents or not; "
        "the Harness does not assign child roles or accept child activity as proof. The max_threads/max_depth values "
        "are Harness-supplied resource safety caps, not child roles or an acceptance requirement. Do not modify files "
        "or use network access. Report a boundary violation only for an actual violation during this run. "
        f"Return only one JSON object for run_id=\"{run_id}\" with schema_version=\"codex-harness.parent-result.v0\", "
        "stage, status, summary, artifacts, verification, findings, owner_decisions, retry_hint, and "
        "boundary_violations. Use status=\"succeeded\" when the read-only task completed; artifacts and findings "
        "may be empty; verification must be an array of objects each containing command (string), exit_code (integer), "
        "and claim (string), for example {\"command\":\"read-only inspection\",\"exit_code\":0,\"claim\":\"files reviewed\"}. "
        "retry_hint must be \"none\", and boundary_violations must be an array of strings."
    )


def run(repository_root: Path, timeout_seconds: int, scenario: str = "smoke") -> int:
    required_paths = [
        repository_root / ".codex" / "config.toml",
        repository_root / ".codex" / "harness" / "parent.toml",
        repository_root / "skills" / "codex-harness" / "SKILL.md",
    ]
    missing = [str(path) for path in required_paths if not path.is_file()]
    if missing:
        raise RuntimeError("Missing pilot configuration: " + ", ".join(missing))
    try:
        policy_bundle = load_runtime_policy(repository_root)
    except PolicyError as error:
        raise RuntimeError(f"runtime policy validation failed: {error}") from error
    parent_profile = load_parent_profile(repository_root / ".codex" / "harness" / "parent.toml")

    artifacts = repository_root / ".codex" / "harness-runs"
    artifacts.mkdir(parents=True, exist_ok=True)
    run_id = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    stderr_path = artifacts / f"{run_id}.app-server.stderr.log"
    summary_path = artifacts / f"{run_id}.app-server.summary.json"
    ledger_path = artifacts / f"{run_id}.resource-ledger.jsonl"
    resource_ledger = ResourceLedger(ledger_path, run_id)
    resource_ledger.append("run", run_id, "started", "run initialization", policy_identity=policy_bundle["identity"], scenario=scenario)
    before = git_status(repository_root)
    session = JsonRpcSession(
        app_server_command(),
        stderr_path,
    )
    disposition_recorded = False
    session_closed = False
    try:
        initialize_result, _ = session.request(
            1,
            "initialize",
            {"clientInfo": {"name": "codex-subagent-pilot", "version": "0.1"}, "capabilities": {"experimentalApi": True}},
            30,
        )
        start_result, _ = session.request(
            2,
            "thread/start",
            {
                "cwd": str(repository_root),
                "sandbox": "read-only",
                "approvalPolicy": "never",
                "ephemeral": False,
                "developerInstructions": parent_profile["developer_instructions"],
                "model": parent_profile["model"],
                "config": {"model_reasoning_effort": parent_profile["model_reasoning_effort"]},
            },
            30,
        )
        root_thread_id = start_result["thread"]["id"]
        resource_ledger.append("thread", root_thread_id, "started", "thread/start", process_id=session.process.pid)
        prompt = build_prompt(run_id, scenario)
        turn_start_result, start_notifications = session.request(
            3,
            "turn/start",
            {
                "threadId": root_thread_id,
                "input": [{"type": "text", "text": prompt}],
                "approvalPolicy": "never",
                "sandboxPolicy": {"type": "readOnly", "networkAccess": False},
            },
            30,
        )
        turn_id = turn_start_result.get("turn", {}).get("id")
        if turn_id:
            resource_ledger.append("turn", turn_id, "started", "turn/start", thread_id=root_thread_id)
        interrupted = False
        interrupt_notifications: list[dict[str, Any]] = []
        interrupt_error: str | None = None
        try:
            notifications = list(start_notifications)
            if not any(item.get("method") == "turn/completed" and item.get("params", {}).get("threadId") == root_thread_id for item in notifications):
                notifications.extend(session.collect_until_turn_complete(root_thread_id, timeout_seconds))
        except TimeoutError:
            if scenario != "timeout" or not turn_id:
                raise
            interrupted = True
            try:
                _, interrupt_notifications = session.request(
                    4,
                    "turn/interrupt",
                    {"threadId": root_thread_id, "turnId": turn_id},
                    30,
                )
                notifications = interrupt_notifications
                if not any(item.get("method") == "turn/completed" and item.get("params", {}).get("threadId") == root_thread_id for item in notifications):
                    notifications.extend(session.collect_until_turn_complete(root_thread_id, 30))
            except Exception as error:
                interrupt_error = str(error)
                notifications = interrupt_notifications
        history_request_id = 5 if interrupted else 4
        try:
            items_result, item_notifications = session.request(
                history_request_id,
                "thread/items/list",
                {"threadId": root_thread_id, "limit": 500, "sortDirection": "asc"},
                30,
            )
            history = items_result.get("data", [])
        except RuntimeError as error:
            if "not supported yet" not in str(error):
                raise
            try:
                items_result, item_notifications = session.request(
                    history_request_id + 1,
                    "thread/read",
                    {"threadId": root_thread_id, "includeTurns": True},
                    30,
                )
                history = items_result
            except RuntimeError:
                if not interrupted:
                    raise
                history = []
                item_notifications = []
        history_entries = history if isinstance(history, list) else [history]
        evidence = walk_items(notifications + item_notifications + history_entries)
        spawn_calls = [
            item
            for item in evidence
            if item.get("type") == "collabAgentToolCall" and item.get("tool") == "spawnAgent"
        ]
        child_ids = sorted(
            {
                child_id
                for item in spawn_calls
                for child_id in item.get("receiverThreadIds", [])
                if child_id
            }
        )
        activities = [item for item in evidence if item.get("type") == "subAgentActivity"]
        activity_child_ids = {item["agentThreadId"] for item in activities if item.get("agentThreadId")}
        child_ids = sorted(set(child_ids) | activity_child_ids)
        agent_messages = walk_root_agent_messages(notifications + item_notifications + history_entries, root_thread_id)
        final_message = agent_messages[-1] if agent_messages else ""
        parent_result = parse_parent_result(final_message, run_id)
        after = git_status(repository_root)
        terminal_event = next((item for item in notifications if item.get("method") == "turn/completed" and item.get("params", {}).get("threadId") == root_thread_id), None)
        if interrupted:
            passed = terminal_event is not None and interrupt_error is None and before == after
        else:
            passed = (
            parent_result is not None
            and parent_result["status"] == "succeeded"
            and not parent_result["boundary_violations"]
            and artifacts_valid(repository_root, parent_result)
            and before == after
            )
        disposition = "promote" if passed else ("retry" if interrupted else "discard")
        summary = {
            "run_id": run_id,
            "scenario": scenario,
            "turn_id": turn_id,
            "turn_start_result": turn_start_result,
            "interrupted": interrupted,
            "interrupt_error": interrupt_error,
            "terminal_event": terminal_event,
            "notification_methods": [item.get("method") for item in notifications],
            "terminal_events": [item.get("params", {}) for item in notifications if item.get("method") == "turn/completed"],
            "status": "interrupted" if interrupted and passed else ("passed" if passed else "failed"),
            "root_thread_id": root_thread_id,
            "parent_profile": parent_profile["name"],
            "parent_profile_sha256": hashlib.sha256((repository_root / ".codex" / "harness" / "parent.toml").read_bytes()).hexdigest(),
            "codex_version": codex_version(),
            "initialize_result": initialize_result,
            "parent_model": parent_profile["model"],
            "parent_reasoning_effort": parent_profile["model_reasoning_effort"],
            "native_spawn_event_count": len(spawn_calls),
            "child_thread_ids": child_ids,
            "subagent_activity_count": len(activities),
            "subagent_activity_thread_count": len(activity_child_ids),
            "parent_result_valid": parent_result is not None,
            "parent_result": parent_result,
            "parent_result_raw": final_message,
            "policy_identity": policy_bundle["identity"],
            "resource_ledger": str(ledger_path),
            "worktree_changed": before != after,
            "worktree_status_before": before,
            "worktree_status_after": after,
            "stderr_log": str(stderr_path),
        }
        session.close()
        session_closed = True
        resource_ledger.append("process", str(session.process.pid), "closed", "session.close", thread_id=root_thread_id)
        resource_ledger.terminal_disposition(disposition, "app-server pilot verdict")
        disposition_recorded = True
        summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(json.dumps(summary, indent=2))
        return 0 if passed else 2
    finally:
        if not session_closed:
            try:
                session.close()
            finally:
                resource_ledger.append("process", str(session.process.pid), "closed", "session.close", thread_id=locals().get("root_thread_id"))
        if not disposition_recorded:
            # Preserve a stable terminal shape even when an exception occurs
            # before the normal verdict path. The owner can inspect the
            # exception and choose a subsequent action.
            resource_ledger.terminal_disposition("needs_owner", "runner exception before terminal verdict")


def inspect_thread(repository_root: Path, thread_id: str) -> int:
    artifacts = repository_root / ".codex" / "harness-runs"
    artifacts.mkdir(parents=True, exist_ok=True)
    stderr_path = artifacts / f"{thread_id}.inspect.stderr.log"
    session = JsonRpcSession(
        app_server_command(),
        stderr_path,
    )
    try:
        session.request(1, "initialize", {"clientInfo": {"name": "codex-subagent-inspector", "version": "0.1"}}, 30)
        result, _ = session.request(2, "thread/read", {"threadId": thread_id, "includeTurns": True}, 30)
        activities = [item for item in walk_items(result) if item.get("type") == "subAgentActivity"]
        child_ids = sorted({item["agentThreadId"] for item in activities if item.get("agentThreadId")})
        print(json.dumps({"root_thread_id": thread_id, "subagent_activity_count": len(activities), "child_thread_ids": child_ids}, indent=2))
        return 0
    finally:
        session.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--scenario", choices=("smoke", "simple", "parallel", "ambiguous", "boundary", "timeout", "impl-package"), default="smoke")
    parser.add_argument("--inspect-thread")
    args = parser.parse_args()
    try:
        if args.inspect_thread:
            return inspect_thread(args.repository_root.resolve(), args.inspect_thread)
        return run(args.repository_root.resolve(), args.timeout_seconds, args.scenario)
    except Exception as error:
        print(f"[X] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
