#!/usr/bin/env python3
"""Thin Grok CLI runner for short-task agents (review / explore / implement).

Stdout: one JSON result object.
Stderr: heartbeats and diagnostics.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_MAX_RUN = 120
DEFAULT_STALL_TIMEOUT_SEC = 180
DEFAULT_OVERALL_TIMEOUT_SEC = 2400
DEFAULT_HEARTBEAT_SEC = 15

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_MAX_TURNS = 2
EXIT_STALLED = 3
EXIT_TIMEOUT = 4

ROLE_ENVELOPES = {
    "explore": (
        "You are a read-only explorer. Investigate the request using only the "
        "allowed tools. Do not edit, create, or delete files. Do not run shell "
        "commands that change state. Return concise findings with concrete file "
        "paths and residual unknowns."
    ),
    "reviewer": (
        "You are a defect-first reviewer. Read and inspect only. Do not implement "
        "fixes unless the prompt explicitly asks for patch suggestions in text. "
        "Report actionable findings first (severity, location, evidence, impact). "
        "If nothing material is wrong, say so briefly."
    ),
    "implement": (
        "You are a plan-bounded implementer for a short task. Make the minimal "
        "diff needed to satisfy the request/plan. Do not expand scope. Prefer "
        "existing patterns. After changes, report: files changed, what you did, "
        "how to verify, and residual risk. Do not push, force-push, open PRs, or "
        "mutate production systems unless the prompt explicitly authorizes that."
    ),
}


def eprint(*args: Any, **kwargs: Any) -> None:
    print(*args, file=sys.stderr, **kwargs)


def resolve_grok_bin() -> Optional[str]:
    env = os.environ.get("GROK_BIN")
    if env and Path(env).exists():
        return env
    found = shutil.which("grok")
    if found:
        return found
    home = Path(os.environ.get("GROK_HOME") or (Path.home() / ".grok"))
    for name in ("grok.exe", "grok"):
        candidate = home / "bin" / name
        if candidate.exists():
            return str(candidate)
    return None


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME") or (Path.home() / ".grok"))


def auth_present() -> bool:
    if os.environ.get("XAI_API_KEY"):
        return True
    return (grok_home() / "auth.json").is_file()


def preflight(grok_bin: str, check_auth: bool) -> Tuple[bool, str, Dict[str, Any]]:
    info: Dict[str, Any] = {"grok_bin": grok_bin, "auth_present": auth_present()}
    try:
        proc = subprocess.run(
            [grok_bin, "version"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return False, f"failed to run grok version: {exc}", info

    version_text = (proc.stdout or proc.stderr or "").strip()
    info["version"] = version_text
    info["version_exit"] = proc.returncode
    if proc.returncode != 0:
        return False, f"grok version exited {proc.returncode}: {version_text}", info

    if check_auth and not info["auth_present"]:
        return (
            False,
            "auth missing: set XAI_API_KEY or run `grok login` (no auth.json)",
            info,
        )
    return True, "ok", info


def read_prompt(args: argparse.Namespace) -> str:
    if args.prompt_file:
        return Path(args.prompt_file).read_text(encoding="utf-8")
    if args.prompt is None:
        raise SystemExit("either --prompt or --prompt-file is required")
    return args.prompt


def build_prompt(role: str, user_prompt: str, plan_file: Optional[str], rules: Optional[str]) -> str:
    parts = [ROLE_ENVELOPES[role], "", "---", "", user_prompt.strip()]
    if plan_file:
        plan_path = Path(plan_file)
        parts.extend(["", "---", "", f"Plan file path: {plan_path.resolve()}"])
        try:
            content = plan_path.read_text(encoding="utf-8")
            # Cap plan injection so the wrapper stays usable for large plans.
            if len(content) > 120_000:
                content = content[:120_000] + "\n\n[truncated plan content]\n"
            parts.extend(["", "Plan file content:", content])
        except OSError as exc:
            parts.extend(["", f"(Could not read plan file: {exc})"])
    if rules:
        parts.extend(["", "---", "", "Additional rules:", rules.strip()])
    return "\n".join(parts).strip() + "\n"


def build_cmd(
    grok_bin: str,
    role: str,
    prompt: str,
    args: argparse.Namespace,
) -> List[str]:
    cmd: List[str] = [
        grok_bin,
        "-p",
        prompt,
        "--max-turns",
        str(args.max_run),
        "--output-format",
        "streaming-json",
    ]

    if args.cwd:
        cmd.extend(["--cwd", args.cwd])
    if args.model:
        cmd.extend(["-m", args.model])
    if args.effort:
        cmd.extend(["--effort", args.effort])
    if args.resume:
        cmd.extend(["--resume", args.resume])
    if args.worktree is not None:
        # argparse nargs='?' yields None when flag absent; '' or name when present.
        if args.worktree == "":
            cmd.append("--worktree")
        else:
            cmd.extend(["--worktree", args.worktree])

    if not args.allow_subagents:
        cmd.append("--no-subagents")
        cmd.extend(["--disallowed-tools", "Agent"])

    if role == "explore":
        tools = "read_file,grep,list_dir,web_search,web_fetch"
        cmd.extend(["--tools", tools])
    elif role == "reviewer":
        if args.allow_git_shell:
            # Keep shell available for git inspection; still no always-approve.
            tools = "read_file,grep,list_dir,run_terminal_cmd"
            cmd.extend(["--tools", tools])
            cmd.extend(["--allow", "Bash(git *)"])
            cmd.extend(["--deny", "Bash(git push*)", "--deny", "Bash(git push *)"])
        else:
            cmd.extend(["--tools", "read_file,grep,list_dir"])
    elif role == "implement":
        cmd.append("--always-approve")

    if args.rules and role == "implement":
        # rules already folded into prompt; also pass as CLI rules for extra weight
        cmd.extend(["--rules", args.rules])

    return cmd


def kill_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    pid = proc.pid
    if sys.platform == "win32":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                check=False,
            )
        except Exception:  # noqa: BLE001
            try:
                proc.kill()
            except Exception:  # noqa: BLE001
                pass
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:  # noqa: BLE001
            try:
                proc.terminate()
            except Exception:  # noqa: BLE001
                pass
        deadline = time.time() + 5
        while proc.poll() is None and time.time() < deadline:
            time.sleep(0.1)
        if proc.poll() is None:
            try:
                os.killpg(os.getpgid(pid), signal.SIGKILL)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass


def run_with_liveness(
    cmd: List[str],
    stall_timeout_sec: float,
    overall_timeout_sec: float,
    heartbeat_sec: float,
) -> Dict[str, Any]:
    started = time.time()
    last_event_at = started
    last_event_type = "none"
    heartbeats = 0
    text_parts: List[str] = []
    session_id: Optional[str] = None
    stop_reason: Optional[str] = None
    num_turns: Optional[int] = None
    usage: Any = None
    model_usage: Any = None
    raw_end: Optional[Dict[str, Any]] = None
    max_turns_seen = False
    error_message: Optional[str] = None
    status = "completed"
    terminal_lock = threading.Lock()
    stop_watchdog = threading.Event()

    popen_kwargs: Dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "bufsize": 1,
    }
    if sys.platform != "win32":
        popen_kwargs["start_new_session"] = True
    else:
        # CREATE_NEW_PROCESS_GROUP helps taskkill /T
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

    proc = subprocess.Popen(cmd, **popen_kwargs)

    def on_event(event: Dict[str, Any]) -> None:
        nonlocal last_event_at, last_event_type, session_id, stop_reason
        nonlocal num_turns, usage, model_usage, raw_end, max_turns_seen, error_message, status
        etype = event.get("type") or event.get("sessionUpdate") or "unknown"
        last_event_at = time.time()
        last_event_type = str(etype)

        if etype == "text":
            data = event.get("data")
            if data is None and isinstance(event.get("content"), dict):
                data = event["content"].get("text")
            if data:
                text_parts.append(str(data))
        elif etype == "thought":
            pass
        elif etype == "end":
            raw_end = event
            session_id = event.get("sessionId") or session_id
            stop_reason = event.get("stopReason")
            if "num_turns" in event:
                num_turns = event.get("num_turns")
            usage = event.get("usage", usage)
            model_usage = event.get("modelUsage", model_usage)
            if str(stop_reason or "").lower() in {"maxturns", "max_turns", "max_turns_reached"}:
                max_turns_seen = True
                status = "max_turns"
        elif etype == "max_turns_reached":
            max_turns_seen = True
            status = "max_turns"
            session_id = event.get("sessionId") or session_id
        elif etype == "error":
            error_message = event.get("message") or event.get("data") or json.dumps(event)
            status = "error"
            session_id = event.get("sessionId") or session_id
            if "num_turns" in event:
                num_turns = event.get("num_turns")
            usage = event.get("usage", usage)
        else:
            # Unknown event types still count as liveness.
            if "sessionId" in event:
                session_id = event.get("sessionId") or session_id
            data = event.get("data")
            if isinstance(data, str) and etype.endswith("text"):
                text_parts.append(data)

    def read_stdout() -> None:
        nonlocal last_event_at, last_event_type
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                # Non-JSON line: treat as progress text so we do not false-stall.
                with terminal_lock:
                    last_event_at = time.time()
                    last_event_type = "raw"
                    text_parts.append(line + "\n")
                continue
            if isinstance(event, dict):
                with terminal_lock:
                    on_event(event)

    def read_stderr() -> None:
        assert proc.stderr is not None
        for line in proc.stderr:
            # Forward child stderr for diagnostics; do not pollute stdout JSON.
            eprint(f"[grok-stderr] {line.rstrip()}")

    def watchdog() -> None:
        nonlocal status, heartbeats
        while not stop_watchdog.wait(0.5):
            now = time.time()
            with terminal_lock:
                age = now - last_event_at
                et = last_event_type
            wall = now - started
            if wall >= overall_timeout_sec:
                with terminal_lock:
                    status = "timeout"
                eprint(
                    f"[liveness] overall timeout after {wall:.1f}s "
                    f"(limit={overall_timeout_sec}s); killing grok"
                )
                kill_process_tree(proc)
                return
            if age >= stall_timeout_sec:
                with terminal_lock:
                    status = "stalled"
                eprint(
                    f"[liveness] stalled: no events for {age:.1f}s "
                    f"(limit={stall_timeout_sec}s, last={et}); killing grok"
                )
                kill_process_tree(proc)
                return
            # heartbeat cadence
            if heartbeat_sec > 0 and int(wall // heartbeat_sec) > heartbeats:
                heartbeats = int(wall // heartbeat_sec)
                eprint(
                    f"[heartbeat] t={wall:.0f}s age={age:.1f}s last={et} "
                    f"turns≈{num_turns if num_turns is not None else '?'}"
                )

    t_out = threading.Thread(target=read_stdout, name="grok-stdout", daemon=True)
    t_err = threading.Thread(target=read_stderr, name="grok-stderr", daemon=True)
    t_wd = threading.Thread(target=watchdog, name="grok-watchdog", daemon=True)
    t_out.start()
    t_err.start()
    t_wd.start()

    exit_code = proc.wait()
    stop_watchdog.set()
    t_out.join(timeout=2)
    t_err.join(timeout=2)
    t_wd.join(timeout=2)

    with terminal_lock:
        age = time.time() - last_event_at
        final_status = status
        if final_status == "completed":
            if max_turns_seen:
                final_status = "max_turns"
            elif exit_code not in (0, None) and not text_parts and error_message:
                final_status = "error"
            elif exit_code not in (0, None) and not text_parts and not raw_end:
                final_status = "error"
                error_message = error_message or f"grok exited with code {exit_code}"

        result = {
            "status": final_status,
            "sessionId": session_id,
            "num_turns": num_turns,
            "text": "".join(text_parts),
            "stopReason": stop_reason,
            "usage": usage,
            "modelUsage": model_usage,
            "error_message": error_message,
            "raw_end": raw_end,
            "process_exit_code": exit_code,
            "liveness": {
                "last_event_type": last_event_type,
                "last_event_age_sec": round(age, 3),
                "heartbeats": heartbeats,
                "stall_timeout_sec": stall_timeout_sec,
                "overall_timeout_sec": overall_timeout_sec,
                "elapsed_sec": round(time.time() - started, 3),
            },
        }
    return result


def status_to_exit(status: str) -> int:
    return {
        "completed": EXIT_OK,
        "max_turns": EXIT_MAX_TURNS,
        "stalled": EXIT_STALLED,
        "timeout": EXIT_TIMEOUT,
        "error": EXIT_ERROR,
        "preflight_failed": EXIT_ERROR,
    }.get(status, EXIT_ERROR)


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Run a short Grok CLI task with role presets and liveness checks.",
    )
    p.add_argument(
        "--role",
        required=True,
        choices=sorted(ROLE_ENVELOPES.keys()),
        help="Task role: explore | reviewer | implement",
    )
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt", help="Prompt text")
    g.add_argument("--prompt-file", help="Path to prompt file")

    p.add_argument("--cwd", help="Working directory for grok")
    p.add_argument(
        "--max-run",
        type=int,
        default=DEFAULT_MAX_RUN,
        help=f"Maps to grok --max-turns (default {DEFAULT_MAX_RUN})",
    )
    p.add_argument("--model", help="Model id")
    p.add_argument("--effort", help="Reasoning effort")
    p.add_argument("--plan-file", help="Plan file to inject into the prompt")
    p.add_argument("--rules", help="Extra rules text")
    p.add_argument("--resume", help="Resume grok session id")
    p.add_argument(
        "--worktree",
        nargs="?",
        const="",
        default=None,
        help="Pass --worktree to grok (optional name)",
    )
    p.add_argument(
        "--stall-timeout-sec",
        type=float,
        default=DEFAULT_STALL_TIMEOUT_SEC,
        help=f"No stream event for this many seconds => stalled (default {DEFAULT_STALL_TIMEOUT_SEC})",
    )
    p.add_argument(
        "--overall-timeout-sec",
        type=float,
        default=DEFAULT_OVERALL_TIMEOUT_SEC,
        help=f"Hard wall-clock timeout (default {DEFAULT_OVERALL_TIMEOUT_SEC})",
    )
    p.add_argument(
        "--heartbeat-sec",
        type=float,
        default=DEFAULT_HEARTBEAT_SEC,
        help=f"Stderr heartbeat interval (default {DEFAULT_HEARTBEAT_SEC})",
    )
    p.add_argument(
        "--allow-git-shell",
        action="store_true",
        help="Reviewer only: allow git shell commands for inspection",
    )
    p.add_argument(
        "--allow-subagents",
        action="store_true",
        help="Allow Grok to spawn subagents (off by default for short tasks)",
    )
    p.add_argument(
        "--preflight",
        action="store_true",
        help="Also require auth.json or XAI_API_KEY before running",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the would-be command as JSON and exit 0",
    )
    p.add_argument(
        "--raw-json",
        action="store_true",
        help="Include raw end event object under raw_end (always present when available)",
    )
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)
    if args.max_run < 1:
        eprint("--max-run must be >= 1")
        return EXIT_ERROR

    grok_bin = resolve_grok_bin()
    if not grok_bin:
        result = {
            "ok": False,
            "status": "preflight_failed",
            "role": args.role,
            "max_run": args.max_run,
            "text": "",
            "error_message": "grok binary not found (set GROK_BIN or install grok on PATH)",
            "exit_code": EXIT_ERROR,
            "cmd": [],
        }
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_ERROR

    ok, msg, pf = preflight(grok_bin, check_auth=args.preflight)
    if not ok:
        result = {
            "ok": False,
            "status": "preflight_failed",
            "role": args.role,
            "max_run": args.max_run,
            "text": "",
            "error_message": msg,
            "preflight": pf,
            "exit_code": EXIT_ERROR,
            "cmd": [],
        }
        print(json.dumps(result, ensure_ascii=False))
        return EXIT_ERROR

    user_prompt = read_prompt(args)
    prompt = build_prompt(args.role, user_prompt, args.plan_file, args.rules)
    cmd = build_cmd(grok_bin, args.role, prompt, args)

    if args.dry_run:
        # Avoid dumping huge plan bodies in dry-run command display.
        display_cmd = list(cmd)
        if len(display_cmd) >= 3 and display_cmd[1] == "-p":
            display_cmd[2] = f"<prompt {len(prompt)} chars>"
        result = {
            "ok": True,
            "status": "dry_run",
            "role": args.role,
            "max_run": args.max_run,
            "text": "",
            "preflight": pf,
            "cmd": display_cmd,
            "prompt_chars": len(prompt),
            "exit_code": EXIT_OK,
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return EXIT_OK

    eprint(
        f"[call-grok] role={args.role} max_run={args.max_run} "
        f"stall={args.stall_timeout_sec}s overall={args.overall_timeout_sec}s"
    )
    run = run_with_liveness(
        cmd=cmd,
        stall_timeout_sec=args.stall_timeout_sec,
        overall_timeout_sec=args.overall_timeout_sec,
        heartbeat_sec=args.heartbeat_sec,
    )

    status = run["status"]
    exit_code = status_to_exit(status)
    ok = status == "completed"

    # Redact full prompt from cmd in result; keep structure.
    display_cmd = list(cmd)
    if len(display_cmd) >= 3 and display_cmd[1] == "-p":
        display_cmd[2] = f"<prompt {len(prompt)} chars>"

    result: Dict[str, Any] = {
        "ok": ok,
        "status": status,
        "role": args.role,
        "sessionId": run.get("sessionId"),
        "num_turns": run.get("num_turns"),
        "max_run": args.max_run,
        "text": run.get("text") or "",
        "stopReason": run.get("stopReason"),
        "liveness": run.get("liveness"),
        "usage": run.get("usage"),
        "modelUsage": run.get("modelUsage"),
        "error_message": run.get("error_message"),
        "process_exit_code": run.get("process_exit_code"),
        "preflight": pf,
        "exit_code": exit_code,
        "cmd": display_cmd,
    }
    if args.raw_json and run.get("raw_end") is not None:
        result["raw_end"] = run.get("raw_end")

    print(json.dumps(result, ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
