#!/usr/bin/env python3
"""Run one short-lived Codex CLI task and emit a stable JSON envelope."""
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


class ExecutorError(RuntimeError):
    def __init__(self, code: str, message: str, *, exit_code: int | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.exit_code = exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one short-lived Codex CLI task")
    parser.add_argument("--cwd", required=True, help="working directory passed to Codex")
    prompt = parser.add_mutually_exclusive_group(required=True)
    prompt.add_argument("--prompt", help="task prompt")
    prompt.add_argument("--prompt-file", type=Path, help="UTF-8 task prompt file")
    parser.add_argument("--timeout-s", type=int, default=900, help="process timeout in seconds")
    parser.add_argument("--executable", help="Codex executable path or command; otherwise use discovery")
    parser.add_argument("--model", help="Codex model")
    parser.add_argument("--config", action="append", default=[], help="repeatable Codex -c configuration")
    parser.add_argument("--sandbox", help="Codex sandbox policy supplied by the caller")
    parser.add_argument("--ephemeral", action="store_true", help="request an ephemeral Codex session")
    parser.add_argument("--output-schema", type=Path, help="caller-supplied Codex output schema")
    return parser


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt is not None:
        return args.prompt
    try:
        return args.prompt_file.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutorError("PROMPT_FILE", f"could not read prompt file: {exc}") from exc


def build_command(
    args: argparse.Namespace,
    *,
    executable: str = "codex",
    ignore_user_config: bool = False,
) -> list[str]:
    command = [executable, "exec"]
    if ignore_user_config:
        command.append("--ignore-user-config")
    command.append("--json")
    if args.model:
        command.extend(["-m", args.model])
    for config in args.config:
        command.extend(["-c", config])
    if args.sandbox:
        command.extend(["--sandbox", args.sandbox])
    if args.ephemeral:
        command.append("--ephemeral")
    if args.output_schema:
        command.extend(["--output-schema", str(args.output_schema)])
    command.extend(["--cd", str(Path(args.cwd).resolve()), "-"])
    return command


def terminate_process_tree(pid: int) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True, check=False)
        return
    try:
        os.killpg(pid, signal.SIGTERM)
    except (AttributeError, OSError):
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            pass


def resolve_codex_executable(explicit: str | None) -> str:
    """Find a usable CLI without selecting the WindowsApps package resource."""

    if explicit:
        return explicit
    override = os.environ.get("CODEX_EXECUTABLE")
    if override:
        return override
    path_command = shutil.which("codex.cmd") or shutil.which("codex")
    if path_command and "\\windowsapps\\" not in path_command.lower().replace("/", "\\"):
        return path_command
    local_app_data = os.environ.get("LOCALAPPDATA")
    if local_app_data:
        desktop_bin = Path(local_app_data) / "OpenAI" / "Codex" / "bin"
        desktop_candidates = [desktop_bin / "codex.exe", *desktop_bin.glob("*/codex.exe")]
        usable_candidates = [candidate for candidate in desktop_candidates if candidate.is_file()]
        if usable_candidates:
            return str(max(usable_candidates, key=lambda candidate: candidate.stat().st_mtime))
    raise ExecutorError("BINARY_NOT_FOUND", "could not find a usable Codex CLI; set --executable or CODEX_EXECUTABLE")


def run_process(command: list[str], *, stdin: str, timeout_s: int, cwd: Path) -> subprocess.CompletedProcess[str]:
    executable = command[0]
    resolved = shutil.which(executable)
    if resolved is None:
        raise ExecutorError("BINARY_NOT_FOUND", f"{executable} was not found on PATH")
    actual_command = [resolved, *command[1:]]
    if resolved.lower().endswith(".ps1"):
        actual_command = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", resolved, *command[1:]]
    elif resolved.lower().endswith((".cmd", ".bat")):
        actual_command = ["cmd", "/c", resolved, *command[1:]]
    kwargs: dict[str, Any] = {
        "stdin": subprocess.PIPE,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "cwd": str(cwd),
    }
    if os.name != "nt":
        kwargs["start_new_session"] = True
    try:
        process = subprocess.Popen(actual_command, **kwargs)
        try:
            stdout, stderr = process.communicate(input=stdin, timeout=timeout_s)
        except subprocess.TimeoutExpired as exc:
            terminate_process_tree(process.pid)
            process.communicate()
            raise ExecutorError("TIMEOUT", f"codex timed out after {timeout_s}s") from exc
        return subprocess.CompletedProcess(actual_command, process.returncode, stdout, stderr)
    except PermissionError as exc:
        raise ExecutorError("PERMISSION", str(exc)) from exc
    except FileNotFoundError as exc:
        raise ExecutorError("BINARY_NOT_FOUND", f"{executable} was not found on PATH") from exc


def is_user_config_error(stdout: str, stderr: str) -> bool:
    combined = f"{stdout}\n{stderr}".lower()
    return "error loading config.toml" in combined and "service_tier" in combined and "unknown variant" in combined


def classify_process_error(returncode: int, stdout: str, stderr: str) -> ExecutorError:
    combined = f"{stdout}\n{stderr}".lower()
    if "permission denied" in combined or "not allowed" in combined:
        return ExecutorError("PERMISSION", "codex could not access the requested project or files", exit_code=returncode)
    if "not authenticated" in combined or "authentication" in combined or "login" in combined:
        return ExecutorError("AUTH", "codex requires CLI login/authentication", exit_code=returncode)
    detail = stderr.strip() or stdout.strip() or "no diagnostic output"
    return ExecutorError("AGENT_FAILED", f"codex exited with code {returncode}: {detail}", exit_code=returncode)


def _text_from_value(value: Any) -> str | None:
    if isinstance(value, str) and value.strip():
        return value
    if isinstance(value, list):
        pieces = [_text_from_value(item) for item in value]
        rendered = "".join(piece for piece in pieces if piece)
        return rendered or None
    if isinstance(value, dict):
        for key in ("text", "content", "message", "output", "result"):
            text = _text_from_value(value.get(key))
            if text:
                return text
    return None


def parse_codex_jsonl(output: str) -> tuple[str, dict[str, Any] | None]:
    final_text: str | None = None
    usage: dict[str, Any] | None = None
    decoded_any = False
    for line in output.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        decoded_any = True
        if not isinstance(event, dict):
            continue
        item = event.get("item")
        candidate: str | None = None
        if isinstance(item, dict) and item.get("type") in {"agent_message", "message"}:
            candidate = _text_from_value(item)
        if candidate is None:
            candidate = _text_from_value(event.get("result"))
        if candidate is None:
            candidate = _text_from_value(event.get("payload"))
        if candidate:
            final_text = candidate
        event_usage = event.get("usage")
        if isinstance(event_usage, dict):
            usage = event_usage
    if final_text is None:
        try:
            value = json.loads(output.strip())
        except json.JSONDecodeError:
            value = None
        final_text = _text_from_value(value)
        if isinstance(value, dict) and isinstance(value.get("usage"), dict):
            usage = value["usage"]
    if not decoded_any or not final_text:
        raise ExecutorError("INVALID_OUTPUT", "codex did not emit a final text response")
    return final_text, usage


def run(args: argparse.Namespace) -> dict[str, Any]:
    cwd = Path(args.cwd).resolve()
    try:
        prompt = read_prompt(args)
        executable = resolve_codex_executable(args.executable)
        completed = run_process(build_command(args, executable=executable), stdin=prompt, timeout_s=args.timeout_s, cwd=cwd)
        if completed.returncode != 0 and is_user_config_error(completed.stdout, completed.stderr):
            print("WARN: codex user config failed to load; retried with --ignore-user-config.", file=sys.stderr)
            completed = run_process(
                build_command(args, executable=executable, ignore_user_config=True),
                stdin=prompt,
                timeout_s=args.timeout_s,
                cwd=cwd,
            )
        if completed.returncode != 0:
            raise classify_process_error(completed.returncode, completed.stdout, completed.stderr)
        text, usage = parse_codex_jsonl(completed.stdout)
        return {"ok": True, "status": "completed", "text": text, "usage": usage, "exit_code": 0, "error": None}
    except ExecutorError as exc:
        return {
            "ok": False,
            "status": exc.code.lower(),
            "text": None,
            "usage": None,
            "exit_code": exc.exit_code,
            "error": {"code": exc.code, "message": exc.message},
        }


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    print(json.dumps(run(args), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
