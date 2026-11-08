#!/usr/bin/env python3
"""Run one Claude Code task through DeepSeek and stream a readable log."""

from __future__ import annotations

import argparse
import json
import os
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any


DEFAULT_MODEL = "deepseek-v4-flash"
DEFAULT_PERMISSION = "acceptEdits"
DEFAULT_CLIP_CHARS = 400
DEFAULT_IDLE_TIMEOUT_SEC = 900
DEFAULT_HEARTBEAT_SEC = 60
INHERITED_CLAUDE_ENV = re.compile(r"^(CLAUDE_(?:CODE|AGENT)_|CLAUDECODE$)")


def eprint(*values: object) -> None:
    print(*values, file=sys.stderr, flush=True)


def emit(*values: object) -> None:
    print(*values, flush=True)


def find_claude_executable() -> Path | str:
    override = os.environ.get("CLAUDE_EXE")
    if override:
        return Path(override)

    path_claude = shutil.which("claude")
    if path_claude and "volta" not in Path(path_claude).parts[-1].lower():
        return Path(path_claude)

    app_data = os.environ.get("APPDATA")
    if app_data:
        desktop_root = Path(app_data) / "Claude" / "claude-code"
        if desktop_root.is_dir():
            candidates = [
                path
                for path in desktop_root.rglob("claude.exe")
                if path.is_file()
            ]
            if candidates:
                return max(candidates, key=lambda path: path.stat().st_mtime)

    if path_claude:
        return Path(path_claude)
    raise RuntimeError("claude executable not found; set CLAUDE_EXE")


def read_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY")
    if key:
        return key

    key_file = Path.home() / ".claude" / "secrets" / "deepseek.key"
    try:
        key = key_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise RuntimeError("DEEPSEEK_API_KEY is not set and deepseek.key is unavailable") from exc
    if not key:
        raise RuntimeError(f"empty DeepSeek API key: {key_file}")
    return key


def build_child_environment(model: str, api_key: str) -> dict[str, str]:
    environment = os.environ.copy()
    for name in os.environ:
        if INHERITED_CLAUDE_ENV.search(name):
            environment.pop(name, None)

    environment.update(
        {
            "ANTHROPIC_BASE_URL": "https://api.deepseek.com/anthropic",
            "ANTHROPIC_AUTH_TOKEN": api_key,
            "ANTHROPIC_MODEL": model,
            "ANTHROPIC_SMALL_FAST_MODEL": model,
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": model,
            "ANTHROPIC_DEFAULT_SONNET_MODEL": model,
            "ANTHROPIC_DEFAULT_OPUS_MODEL": model,
            "CLAUDE_CODE_SUBAGENT_MODEL": model,
            "CLAUDE_CODE_MAX_CONTEXT_TOKENS": "1000000",
            "CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC": "1",
        }
    )
    environment.pop("ANTHROPIC_API_KEY", None)
    return environment


def clip(value: str, limit: int) -> str:
    compact = re.sub(r"\s+", " ", value)
    if len(compact) <= limit:
        return compact
    return f"{compact[:limit]}..."


def content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return str(content)
    return " ".join(
        item.get("text", str(item)) if isinstance(item, dict) else str(item)
        for item in content
    )


def kill_process_tree(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
        return
    try:
        os.killpg(os.getpgid(process.pid), signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        process.kill()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--prompt", help="task text sent to Claude Code")
    source.add_argument("--prompt-file", type=Path, help="file containing the task text")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="working directory for the child")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--resume", help="session id from a previous [done] line")
    parser.add_argument("--cli-model", help="Claude CLI model alias, used to verify mapping")
    parser.add_argument("--permission", default=DEFAULT_PERMISSION)
    parser.add_argument("--tools", help="comma-separated Claude Code tools")
    parser.add_argument("--clip-chars", type=int, default=DEFAULT_CLIP_CHARS)
    parser.add_argument("--idle-timeout-sec", type=int, default=DEFAULT_IDLE_TIMEOUT_SEC)
    parser.add_argument("--heartbeat-sec", type=int, default=DEFAULT_HEARTBEAT_SEC)
    return parser.parse_args(argv)


def stream_process(args: argparse.Namespace, executable: Path | str) -> int:
    cli_args = [
        "--permission-mode",
        args.permission,
        "--strict-mcp-config",
        "--output-format",
        "stream-json",
        "--verbose",
    ]
    if args.tools:
        cli_args.append(f"--tools={args.tools}")
    if args.resume:
        cli_args.extend(["--resume", args.resume])
    if args.cli_model:
        cli_args.extend(["--model", args.cli_model])

    if not args.cwd.is_dir():
        raise RuntimeError(f"working directory does not exist: {args.cwd}")

    environment = build_child_environment(args.model, read_api_key())
    process = subprocess.Popen(
        [str(executable), "-p", *cli_args],
        cwd=args.cwd,
        env=environment,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        start_new_session=True,
    )

    lines: queue.Queue[tuple[str, str | None]] = queue.Queue()

    def read_stream(name: str, stream: Any) -> None:
        assert stream is not None
        for line in iter(stream.readline, ""):
            lines.put((name, line.rstrip("\r\n")))
        lines.put((name, None))

    stdout_reader = threading.Thread(target=read_stream, args=("stdout", process.stdout), daemon=True)
    stderr_reader = threading.Thread(target=read_stream, args=("stderr", process.stderr), daemon=True)
    stdout_reader.start()
    stderr_reader.start()

    assert process.stdin is not None
    try:
        process.stdin.write(args.prompt)
        process.stdin.close()
    except (BrokenPipeError, OSError):
        pass

    session_id: str | None = None
    got_result = False
    last_line = ""
    exit_code = 0
    started = time.monotonic()
    last_event = started
    last_heartbeat = 0.0
    events = 0
    open_streams = 2

    while open_streams:
        try:
            stream_name, line = lines.get(timeout=1)
        except queue.Empty:
            elapsed = time.monotonic() - started
            idle = time.monotonic() - last_event
            if args.idle_timeout_sec > 0 and idle >= args.idle_timeout_sec:
                emit(
                    f"[timeout] no output for {int(idle)}s; killing child. "
                    f"session={session_id} last={last_line}"
                )
                exit_code = 2
                break
            if (
                args.heartbeat_sec > 0
                and idle >= args.heartbeat_sec
                and int(idle) - int(last_heartbeat) >= args.heartbeat_sec
            ):
                last_heartbeat = idle
                emit(f"[hb] elapsed={int(elapsed)}s idle={int(idle)}s events={events}")
            continue

        if line is None:
            open_streams -= 1
            continue

        events += 1
        last_event = time.monotonic()
        if "claude.ai connectors are disabled" in line or "unrecognized_model" in line:
            continue
        if not line.lstrip().startswith("{"):
            emit(f"[cli] {line}")
            continue

        last_line = clip(line, args.clip_chars)
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            emit(f"[cli] {line}")
            continue

        if event.get("session_id"):
            session_id = event["session_id"]

        event_type = event.get("type")
        if event_type == "system" and event.get("subtype") == "init":
            emit(f"[init] model={event.get('model')} cwd={event.get('cwd')}")
        elif event_type == "assistant":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "text":
                    emit(f"[text] {block.get('text', '')}")
                elif block.get("type") == "tool_use":
                    tool_input = json.dumps(
                        block.get("input", {}),
                        ensure_ascii=False,
                        separators=(",", ":"),
                    )
                    emit(f"[tool] {block.get('name')} {clip(tool_input, args.clip_chars)}")
        elif event_type == "user":
            for block in event.get("message", {}).get("content", []):
                if block.get("type") == "tool_result":
                    emit(f"[result] {clip(content_text(block.get('content')), args.clip_chars)}")
        elif event_type == "result":
            got_result = True
            model_usage = ",".join(event.get("modelUsage", {}).keys())
            emit(
                f"[done] {event.get('duration_ms')}ms models={model_usage} "
                f"error={event.get('is_error')} session={event.get('session_id')}"
            )
            emit("---")
            emit(event.get("result", ""))

    if exit_code == 0:
        try:
            exit_code = process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            kill_process_tree(process)
            exit_code = process.wait()
    else:
        kill_process_tree(process)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            pass

    if not got_result:
        child_exit = process.returncode if process.returncode is not None else "killed"
        elapsed_ms = int((time.monotonic() - started) * 1000)
        emit(f"[done] {elapsed_ms}ms error=True no-result exit={child_exit} session={session_id}")
        if exit_code == 0:
            exit_code = 1
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.prompt_file is not None:
        try:
            prompt = args.prompt_file.read_text(encoding="utf-8")
        except OSError as exc:
            eprint(f"error: cannot read prompt file: {exc}")
            return 2
        args.prompt = prompt
    if not args.prompt:
        eprint("error: prompt is empty; use --prompt or a non-empty --prompt-file")
        return 2
    if min(args.clip_chars, args.idle_timeout_sec, args.heartbeat_sec) < 0:
        eprint("error: numeric limits must be non-negative")
        return 2

    try:
        executable = find_claude_executable()
        return stream_process(args, executable)
    except (RuntimeError, OSError) as exc:
        eprint(f"error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
