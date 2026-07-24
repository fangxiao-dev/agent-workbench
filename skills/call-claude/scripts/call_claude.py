#!/usr/bin/env python3
"""Run one short-lived Claude CLI request and emit a stable JSON envelope."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
from typing import Any

SCRIPT_ROOT = Path(__file__).resolve().parents[3] / "scripts"
if str(SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPT_ROOT))

from executor_env import load_executor_env

load_executor_env(SCRIPT_ROOT.parent)


DEFAULT_TIMEOUT_S = 900


class ExecutorError(RuntimeError):
    def __init__(self, code: str, message: str, exit_code: int | None = None):
        super().__init__(f"{code}: {message}")
        self.code = code
        self.message = message
        self.exit_code = exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one short-lived Claude CLI request.")
    parser.add_argument("--cwd", required=True, type=Path, help="Working directory for the Claude process.")
    prompt_group = parser.add_mutually_exclusive_group(required=True)
    prompt_group.add_argument("--prompt", help="Prompt sent to Claude through stdin.")
    prompt_group.add_argument("--prompt-file", type=Path, help="UTF-8 file containing the prompt.")
    parser.add_argument("--timeout-s", "--timeout", dest="timeout_s", type=int, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--executable", help="Claude executable path or command; otherwise use discovery")
    parser.add_argument("--model", help="Claude model identifier.")
    parser.add_argument("--effort", help="Claude reasoning effort.")
    parser.add_argument("--tools", help="Claude tools setting, including an explicit empty string.")
    parser.add_argument("--system-prompt", help="System prompt supplied by the caller.")
    parser.add_argument("--json-schema", help="Inline JSON schema supplied by the caller.")
    parser.add_argument(
        "--disable-slash-commands",
        action="store_true",
        help="Pass Claude's disable-slash-commands flag for this invocation.",
    )
    parser.add_argument(
        "--no-session-persistence",
        action="store_true",
        help="Pass Claude's no-session-persistence flag for this invocation.",
    )
    return parser


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    try:
        return args.prompt_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutorError("INPUT_ERROR", f"could not read prompt file: {exc}") from exc


def build_command(
    args: argparse.Namespace,
    *,
    executable: str = "claude",
    include_json_schema: bool = True,
) -> list[str]:
    command = [executable, "-p", "--output-format", "json"]
    if args.no_session_persistence:
        command.append("--no-session-persistence")
    if args.disable_slash_commands:
        command.append("--disable-slash-commands")
    if args.model is not None:
        command.extend(["--model", args.model])
    if args.effort is not None:
        command.extend(["--effort", args.effort])
    if args.tools is not None:
        command.extend(["--tools", args.tools])
    if args.system_prompt is not None:
        command.extend(["--system-prompt", args.system_prompt])
    if include_json_schema and args.json_schema is not None:
        command.extend(["--json-schema", args.json_schema])
    return command


def terminate_process_tree(process: subprocess.Popen[str]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            capture_output=True,
            check=False,
        )
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except OSError:
        try:
            process.terminate()
        except OSError:
            pass


def resolve_volta_claude_executable(resolved: str) -> str | None:
    """Bypass Volta's batch shim when JSON arguments must remain intact."""

    if os.name != "nt" or Path(resolved).name.lower() != "claude.cmd":
        return None
    volta = shutil.which("volta")
    if volta is None:
        return None
    completed = subprocess.run([volta, "which", "claude"], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        return None
    shim = Path(completed.stdout.strip())
    executable = shim.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    return str(executable) if executable.is_file() else None


def resolve_claude_executable(explicit: str | None) -> str:
    if explicit:
        return explicit
    override = os.environ.get("CLAUDE_EXECUTABLE")
    if override:
        return override
    found = shutil.which("claude.cmd") or shutil.which("claude")
    if found:
        return found
    raise ExecutorError("BINARY_NOT_FOUND", "could not find a Claude CLI; set --executable or CLAUDE_EXECUTABLE")


def run_process(command: list[str], *, prompt: str, cwd: Path, timeout_s: int) -> subprocess.CompletedProcess[str]:
    executable = command[0]
    resolved = shutil.which(executable)
    actual_command = command
    volta_executable = resolve_volta_claude_executable(resolved) if resolved else None
    if volta_executable:
        actual_command = [volta_executable, *command[1:]]
    elif resolved and resolved.lower().endswith((".cmd", ".bat")):
        actual_command = ["cmd", "/c", resolved, *command[1:]]
    popen_kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": str(cwd),
    }
    if os.name != "nt":
        popen_kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(actual_command, **popen_kwargs)
    except FileNotFoundError as exc:
        raise ExecutorError("BINARY_NOT_FOUND", "claude was not found on PATH") from exc
    except PermissionError as exc:
        raise ExecutorError("PERMISSION", str(exc)) from exc

    try:
        stdout, stderr = process.communicate(input=prompt, timeout=timeout_s)
    except subprocess.TimeoutExpired as exc:
        terminate_process_tree(process)
        process.communicate()
        raise ExecutorError("TIMEOUT", f"claude timed out after {timeout_s}s") from exc
    return subprocess.CompletedProcess(actual_command, process.returncode, stdout, stderr)


def classify_process_error(returncode: int, stdout: str, stderr: str) -> ExecutorError:
    combined = f"{stdout}\n{stderr}".lower()
    if "permission denied" in combined or "not allowed" in combined:
        return ExecutorError("PERMISSION", "claude could not access the requested project or files", returncode)
    if "not authenticated" in combined or "authentication" in combined or "login" in combined:
        return ExecutorError("AUTH", "claude requires CLI login/authentication", returncode)
    detail = stderr.strip() or stdout.strip() or "no diagnostic output"
    return ExecutorError("AGENT_FAILED", f"claude exited with code {returncode}: {detail}", returncode)


def is_structured_output_retry_error(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    return (
        "error_max_structured_output_retries" in combined
        or "failed to provide valid structured output" in combined
    )


def parse_claude_output(output: str) -> tuple[str, dict[str, Any]]:
    try:
        parsed = json.loads(output.strip())
    except json.JSONDecodeError as exc:
        raise ExecutorError("INVALID_OUTPUT", "claude did not return a JSON result wrapper") from exc
    if not isinstance(parsed, dict):
        raise ExecutorError("INVALID_OUTPUT", "claude result wrapper must be a JSON object")
    text = parsed.get("result")
    if not isinstance(text, str) or not text.strip():
        raise ExecutorError("INVALID_OUTPUT", "claude result wrapper has no non-empty result text")
    usage = parsed.get("usage")
    return text, usage if isinstance(usage, dict) else {}


def success_envelope(text: str, usage: dict[str, Any], exit_code: int) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "completed",
        "text": text,
        "usage": usage,
        "exit_code": exit_code,
        "error": None,
    }


def error_envelope(error: ExecutorError) -> dict[str, Any]:
    return {
        "ok": False,
        "status": "failed",
        "text": "",
        "usage": {},
        "exit_code": error.exit_code,
        "error": {"code": error.code, "message": error.message},
    }


def execute(args: argparse.Namespace) -> dict[str, Any]:
    if args.timeout_s <= 0:
        return error_envelope(ExecutorError("INVALID_ARGUMENT", "--timeout-s must be greater than zero"))
    if not args.cwd.is_dir():
        return error_envelope(ExecutorError("INPUT_ERROR", f"--cwd is not a directory: {args.cwd}"))
    try:
        prompt = read_prompt(args)
        executable = resolve_claude_executable(args.executable)
        completed = run_process(build_command(args, executable=executable), prompt=prompt, cwd=args.cwd, timeout_s=args.timeout_s)
        if completed.stderr:
            print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
        if (
            completed.returncode != 0
            and args.json_schema is not None
            and is_structured_output_retry_error(completed.stdout, completed.stderr)
        ):
            completed = run_process(
                build_command(args, executable=executable, include_json_schema=False),
                prompt=prompt,
                cwd=args.cwd,
                timeout_s=args.timeout_s,
            )
            if completed.stderr:
                print(completed.stderr, file=sys.stderr, end="" if completed.stderr.endswith("\n") else "\n")
        if completed.returncode != 0:
            return error_envelope(classify_process_error(completed.returncode, completed.stdout, completed.stderr))
        text, usage = parse_claude_output(completed.stdout)
        return success_envelope(text, usage, completed.returncode)
    except ExecutorError as exc:
        return error_envelope(exc)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    envelope = execute(args)
    print(json.dumps(envelope, ensure_ascii=False, separators=(",", ":")))
    return 0 if envelope["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
