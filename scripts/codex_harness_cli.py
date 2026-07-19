#!/usr/bin/env python3
"""Low-level Codex CLI and App Server v2 JSON-RPC capabilities.

This module intentionally has no Harness policy, Impl-Package, Parent Result,
worktree, or verifier semantics. It can be imported by small standalone
callers that need to drive one App Server session per worktree/task.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Callable, Iterable


DEFAULT_DISABLED_MCP_SERVERS = (
    "openaiDeveloperDocs",
    "figma",
    "drawio",
    "playwright",
    "notion",
    "node_repl",
    "pencil",
)

__all__ = [
    "DEFAULT_DISABLED_MCP_SERVERS",
    "JsonRpcSession",
    "TurnControlRequested",
    "app_server_command",
    "codex_version",
    "find_codex_command",
    "initialize_params",
]


class TurnControlRequested(RuntimeError):
    """Yield an explicit caller-owned control request without closing the session."""

    def __init__(self, request: dict[str, Any]) -> None:
        super().__init__("an explicit turn control request is pending")
        self.request = request


def find_codex_command() -> list[str]:
    """Resolve the Codex executable, honoring ``CODEX_EXECUTABLE`` first."""

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


def app_server_command(
    *,
    enable_multi_agent: bool = True,
    approval_policy: str = "never",
    disabled_mcp_servers: Iterable[str] = DEFAULT_DISABLED_MCP_SERVERS,
    disable_vercel_plugin: bool = True,
) -> list[str]:
    """Build a Codex App Server stdio command without starting a process.

    The defaults preserve the POC's network-free behavior. Callers that need
    other MCP or approval settings must opt in explicitly at the command
    construction site.
    """

    command = find_codex_command() + ["app-server", "--stdio"]
    if enable_multi_agent:
        command.extend(["--enable", "multi_agent"])
    command.extend(["-c", f'approval_policy="{approval_policy}"'])
    if disable_vercel_plugin:
        command.extend(["-c", 'plugins."vercel-plugin@plugins-cli".enabled=false'])
    for server in disabled_mcp_servers:
        command.extend(["-c", f"mcp_servers.{server}.enabled=false"])
    return command


def codex_version(command: list[str] | None = None) -> str:
    """Return the version reported by a Codex executable."""

    completed = subprocess.run(command or find_codex_command() + ["--version"], capture_output=True, text=True, check=True)
    return completed.stdout.strip()


def initialize_params(client_name: str, client_version: str = "0.1", *, experimental_api: bool = True) -> dict[str, Any]:
    """Build the protocol-level ``initialize`` params used by App Server v2."""

    params: dict[str, Any] = {"clientInfo": {"name": client_name, "version": client_version}}
    if experimental_api:
        params["capabilities"] = {"experimentalApi": True}
    return params


class JsonRpcSession:
    """One App Server process with JSONL request/notification handling."""

    def __init__(self, command: list[str], stderr_path: Path) -> None:
        stderr_path.parent.mkdir(parents=True, exist_ok=True)
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

    def request(
        self,
        request_id: int,
        method: str,
        params: dict[str, Any],
        timeout: float,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        """Send one JSON-RPC request and return its result plus prior notifications."""

        assert self.process.stdin is not None
        self.process.stdin.write(json.dumps({"id": request_id, "method": method, "params": params}) + "\n")
        self.process.stdin.flush()
        deadline = time.monotonic() + timeout
        notifications: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            try:
                message = self.messages.get(timeout=min(1, deadline - time.monotonic()))
            except queue.Empty:
                if self.process.poll() is not None:
                    raise RuntimeError(f"App Server exited with code {self.process.returncode}")
                continue
            if message.get("id") == request_id:
                if "error" in message:
                    raise RuntimeError(f"{method} failed: {message['error']}")
                return message["result"], notifications
            notifications.append(message)
        raise TimeoutError(f"Timed out waiting for {method}")

    def collect_until_turn_complete(
        self,
        thread_id: str,
        timeout: float | None = None,
        *,
        expected_turn_id: str | None = None,
        observation_interval_seconds: float | None = None,
        on_observation: Callable[[dict[str, Any]], None] | None = None,
        control_poll_interval_seconds: float | None = None,
        on_control_poll: Callable[[], dict[str, Any] | None] | None = None,
    ) -> list[dict[str, Any]]:
        """Collect notifications through the terminal event for ``thread_id``.

        ``timeout=None`` means that an active turn has no elapsed-time
        cancellation path.  Clients may still supply a finite timeout for
        legacy probes, but that only raises ``TimeoutError``; this transport
        primitive never interrupts a turn.  Optional observations give a
        controller a compact liveness signal without adding another scheduler.
        """

        if timeout is not None and timeout <= 0:
            raise ValueError("timeout must be positive when supplied")
        if observation_interval_seconds is not None and observation_interval_seconds <= 0:
            raise ValueError("observation_interval_seconds must be positive when supplied")
        if control_poll_interval_seconds is not None and control_poll_interval_seconds <= 0:
            raise ValueError("control_poll_interval_seconds must be positive when supplied")
        if (control_poll_interval_seconds is None) != (on_control_poll is None):
            raise ValueError("control polling requires both an interval and callback")
        deadline = None if timeout is None else time.monotonic() + timeout
        next_observation = None if observation_interval_seconds is None else time.monotonic() + observation_interval_seconds
        next_control_poll = None if control_poll_interval_seconds is None else time.monotonic()
        notifications: list[dict[str, Any]] = []
        last_notification_at: float | None = None
        last_notification_method: str | None = None

        def observe(*, process_alive: bool) -> None:
            if on_observation is not None:
                on_observation(
                    {
                        "observed_at": time.time(),
                        "process_alive": process_alive,
                        "last_notification_at": last_notification_at,
                        "last_notification_method": last_notification_method,
                    }
                )

        while deadline is None or time.monotonic() < deadline:
            now = time.monotonic()
            if next_control_poll is not None and now >= next_control_poll:
                assert on_control_poll is not None
                request = on_control_poll()
                if request is not None:
                    raise TurnControlRequested(request)
                next_control_poll = now + control_poll_interval_seconds
            if next_observation is not None and now >= next_observation:
                alive = self.process.poll() is None
                observe(process_alive=alive)
                if not alive:
                    raise RuntimeError(f"App Server exited with code {self.process.returncode}")
                next_observation = now + observation_interval_seconds
            try:
                wakeups = [1.0]
                if deadline is not None:
                    wakeups.append(max(0.001, deadline - time.monotonic()))
                if next_observation is not None:
                    wakeups.append(max(0.001, next_observation - time.monotonic()))
                if next_control_poll is not None:
                    wakeups.append(max(0.001, next_control_poll - time.monotonic()))
                remaining = min(wakeups)
                message = self.messages.get(timeout=remaining)
            except queue.Empty:
                if self.process.poll() is not None:
                    observe(process_alive=False)
                    raise RuntimeError(f"App Server exited with code {self.process.returncode}")
                continue
            notifications.append(message)
            method = message.get("method")
            if isinstance(method, str) and method:
                last_notification_at = time.time()
                last_notification_method = method
            if message.get("method") == "turn/completed":
                params = message.get("params", {})
                nested_turn = params.get("turn") if isinstance(params, dict) else None
                completed_turn_id = params.get("turnId") if isinstance(params, dict) else None
                if completed_turn_id is None and isinstance(nested_turn, dict):
                    completed_turn_id = nested_turn.get("id") or nested_turn.get("turnId")
                if params.get("threadId") == thread_id and (expected_turn_id is None or completed_turn_id == expected_turn_id):
                    observe(process_alive=True)
                    return notifications
        raise TimeoutError("Timed out waiting for turn/completed")

    def close(self) -> None:
        """Terminate the process and join the reader; safe to call repeatedly."""

        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.reader.join(timeout=5)

    def __enter__(self) -> "JsonRpcSession":
        return self

    def __exit__(self, _exc_type: object, _exc_value: object, _traceback: object) -> None:
        self.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or build low-level Codex CLI/App Server capabilities.")
    parser.add_argument("--version", action="store_true", help="print the Codex CLI version")
    parser.add_argument("--print-app-server-command", action="store_true", help="print the default App Server command")
    args = parser.parse_args()
    if args.version:
        print(codex_version())
    elif args.print_app_server_command:
        print(json.dumps(app_server_command()))
    else:
        parser.error("choose --version or --print-app-server-command")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
