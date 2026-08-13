#!/usr/bin/env python3
"""Rollout, poll projection and Git observation helpers for thread-harness."""

from __future__ import annotations

import ast
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess

from rollout_compaction import RolloutCompactionError, rollout_path_for_thread
import ledger_runtime as rt
from ledger_runtime import *

def find_rollout(session_id: str) -> Path:
    root = Path(os.environ.get(SESSIONS_ROOT_ENV) or (Path.home() / ".codex" / "sessions"))
    try:
        return rollout_path_for_thread(session_id, root)
    except RolloutCompactionError as exc:
        raise LedgerError(
            f"rollout not found for session id {session_id} under {root}; "
            "controller may be running in ephemeral mode, which does not persist rollout"
        ) from exc

def response_item(obj: dict) -> dict | None:
    if obj.get("type") == "response_item":
        item = obj.get("payload") or obj.get("item") or obj.get("response_item")
        return item if isinstance(item, dict) else None
    if obj.get("type") in {"custom_tool_call", "custom_tool_call_output"}:
        return obj
    payload = obj.get("payload")
    if isinstance(payload, dict) and payload.get("type") in {"custom_tool_call", "custom_tool_call_output"}:
        return payload
    return None

def payload_of(item: dict) -> dict:
    payload = item.get("payload")
    return payload if isinstance(payload, dict) else item

def stringify(value) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))

def tool_call_source_text(payload: dict, item: dict) -> str:
    """Read only the real shell command from legacy or modern tool payloads."""
    def command_text(value) -> str:
        if isinstance(value, dict):
            command = value.get("command")
            return command if isinstance(command, str) else ""
        if not isinstance(value, str):
            return stringify(value)
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return value
        if isinstance(parsed, dict):
            command = parsed.get("command")
            return command if isinstance(command, str) else ""
        return parsed if isinstance(parsed, str) else value

    for container in (payload, item):
        if not isinstance(container, dict):
            continue
        for key in ("arguments", "input"):
            if key not in container:
                continue
            return command_text(container.get(key))
    return ""

def is_shell_exec_call(payload: dict, item: dict) -> bool:
    return (payload.get("name") or item.get("name")) == "exec"

def read_rollout_events(path: Path, offset: int) -> tuple[list[dict], int, int]:
    events = []
    scanned = 0
    with path.open("rb") as fh:
        fh.seek(offset)
        while True:
            raw = fh.readline()
            if not raw:
                break
            scanned += 1
            try:
                line = raw.decode("utf-8")
            except UnicodeDecodeError:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                events.append(value)
        return events, fh.tell(), scanned

def latest_wait_round(events: list[dict]) -> tuple[dict | None, dict | None]:
    calls: dict[str, dict] = {}
    outputs: dict[str, dict] = {}
    order: list[str] = []
    for obj in events:
        item = response_item(obj)
        if not item:
            continue
        payload = payload_of(item)
        item_type = item.get("type") or payload.get("type")
        call_id = item.get("call_id") or payload.get("call_id") or item.get("id") or payload.get("id")
        if not call_id:
            continue
        if item_type == "custom_tool_call":
            if not is_shell_exec_call(payload, item):
                continue
            text = tool_call_source_text(payload, item)
            if "codex_app__wait_threads" in text:
                calls[call_id] = {"call_id": call_id, "arguments": text}
                order.append(call_id)
        elif item_type == "custom_tool_call_output":
            outputs[call_id] = {"call_id": call_id, "output": payload.get("output", item.get("output"))}
    for call_id in reversed(order):
        if call_id in outputs:
            return calls[call_id], outputs[call_id]
    return (calls[order[-1]], None) if order else (None, None)

def count_dispatch_calls(events: list[dict]) -> int:
    count = 0
    needles = ("tools.codex_app__send_message_to_thread", "tools.codex_app__create_thread")
    outputs = set()
    calls = []
    for obj in events:
        item = response_item(obj)
        if not item:
            continue
        payload = payload_of(item)
        item_type = item.get("type") or payload.get("type")
        call_id = item.get("call_id") or payload.get("call_id") or item.get("id") or payload.get("id")
        if not call_id:
            continue
        if item_type == "custom_tool_call":
            if not is_shell_exec_call(payload, item):
                continue
            text = tool_call_source_text(payload, item)
            if any(needle in text for needle in needles):
                calls.append(call_id)
        elif item_type == "custom_tool_call_output":
            outputs.add(call_id)
    for call_id in calls:
        if call_id in outputs:
            count += 1
    return count

def text_candidates(output_value) -> list[str]:
    candidates = []
    if isinstance(output_value, list):
        for item in output_value:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                candidates.append(item["text"])
            elif isinstance(item, str):
                candidates.append(item)
    elif isinstance(output_value, str):
        candidates.append(output_value)
    return candidates

def extract_projection(output_value):
    for text in text_candidates(output_value):
        try:
            value = json.loads(text.strip())
            if isinstance(value, dict) and value.get("v") == 1:
                return value
        except json.JSONDecodeError:
            pass

        start = text.find("{")
        end = text.rfind("}")
        if start >= 0 and end > start:
            try:
                value = json.loads(text[start : end + 1])
                if isinstance(value, dict) and value.get("v") == 1:
                    return value
            except json.JSONDecodeError:
                continue
    return None

def parse_ids_array(arguments: str) -> list[str] | None:
    match = re.search(r"\bconst\s+ids\s*=\s*(\[[\s\S]*?\])\s*;", arguments)
    if not match:
        return None
    try:
        value = ast.literal_eval(match.group(1))
    except (SyntaxError, ValueError):
        return None
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        return None
    return value

def validate_call(arguments: str, expected_session_ids: list[str]) -> tuple[str | None, list[str]]:
    timeout_match = re.search(r'"?timeoutMs"?\s*[:=]\s*(\d+)', arguments)
    if not timeout_match:
        return "timeoutMs missing (expected 120000)", []
    timeout_ms = int(timeout_match.group(1))
    if timeout_ms != 120000:
        return f"timeoutMs {timeout_ms} != 120000", []

    actual_ids = parse_ids_array(arguments)
    if actual_ids is None:
        return "cannot parse ids array from call", []
    actual = set(actual_ids)
    expected = set(expected_session_ids)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        return f"targets mismatch (missing={missing}, unexpected={unexpected})", actual_ids
    if len(actual_ids) != len(actual):
        duplicates = sorted({item for item in actual_ids if actual_ids.count(item) > 1})
        return f"targets mismatch (missing=[], unexpected=duplicate:{duplicates})", actual_ids
    return None, actual_ids

def validate_projection(payload: dict | None, actual_targets: int, expected_poll_ids: set[str]) -> str | None:
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return "projection missing or wrong version"
    for key in ("n", "polls", "timedOut"):
        if key not in payload:
            return f"projection shape altered (missing {key})"
    n = payload.get("n")
    if n != actual_targets:
        return f"projection n={n} != actual targets {actual_targets}"
    polls = payload.get("polls")
    if not isinstance(polls, list):
        return "poll entry shape altered"
    seen_ids = set()
    for poll in polls:
        if not isinstance(poll, dict) or any(key not in poll for key in ("id", "status", "turn", "turnStatus", "txt")):
            return "poll entry shape altered"
        poll_id = poll.get("id")
        if poll_id not in expected_poll_ids:
            return f"poll id not in registry ({poll_id})"
        if poll_id in seen_ids:
            return f"duplicate poll id ({poll_id})"
        seen_ids.add(poll_id)
    return None

def field(obj: dict, *names):
    for name in names:
        if name in obj:
            return obj[name]
    return None

def extract_head(value):
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        for key in ("head", "id", "turn_id", "turnId", "message_id", "messageId"):
            candidate = value.get(key)
            if isinstance(candidate, str):
                return candidate
    return None

def normalize_state(raw, waiting_on=None) -> str:
    text = str(raw or "").lower()
    if text in STATE_VALUES:
        return text
    if text in {"completed", "complete", "closed"}:
        return "ready_for_assignment"
    if "owner" in text:
        return "awaiting_owner"
    if "seam" in text or waiting_on:
        return "awaiting_seam"
    if text in KNOWN_WORKING_STATUSES:
        return "working"
    return "unknown"

def git_head(worktree: str | None) -> str | None:
    if not worktree:
        return None
    path = Path(worktree)
    if not path.exists():
        return None
    try:
        result = subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = (result.stdout or "").strip()
    if result.returncode != 0 or not re.fullmatch(r"[0-9a-fA-F]{40}", head):
        return None
    return head.lower()

def git_is_ancestor(worktree: str | None, ancestor: str, descendant: str) -> bool:
    if not worktree or not ancestor or not descendant:
        return False
    try:
        result = subprocess.run(
            ["git", "-C", str(Path(worktree)), "merge-base", "--is-ancestor", ancestor, descendant],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return result.returncode == 0

def git_commit_paths(worktree: str | None, head: str | None, old_head: str | None = None) -> list[str] | None:
    if not worktree or not head:
        return None
    if old_head:
        try:
            result = subprocess.run(
                ["git", "-C", str(Path(worktree)), "merge-base", "--is-ancestor", old_head, head],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if result.returncode != 0:
            return None
        command = ["git", "-C", str(Path(worktree)), "log", "--name-only", "--pretty=format:", f"{old_head}..{head}"]
    else:
        command = ["git", "-C", str(Path(worktree)), "show", "--name-only", "--pretty=format:", head]
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if result.returncode != 0:
        return None
    return [line.strip().replace("\\", "/") for line in (result.stdout or "").splitlines() if line.strip()]

def advance_kind(worktree: str | None, head: str | None, old_head: str | None = None) -> str:
    paths = git_commit_paths(worktree, head, old_head)
    if paths is None or not paths:
        return "unknown"
    for path in paths:
        if not (path.endswith(".md") or path.startswith("docs/")):
            return "code"
    return "docs"

def wake_thread_ids(wake: dict) -> set[str]:
    ids = set()
    for key in ("threadId", "thread_id", "target", "session_id", "sessionId"):
        value = wake.get(key)
        if isinstance(value, str):
            ids.add(value)
    for key in ("targets", "threadIds", "thread_ids"):
        value = wake.get(key)
        if isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    ids.add(item)
                elif isinstance(item, dict):
                    tid = field(item, "threadId", "thread_id", "session_id", "sessionId")
                    if isinstance(tid, str):
                        ids.add(tid)
    return ids

def rollout_stats(path: Path) -> tuple[str, int | None, str | None]:
    absolute = str(path.resolve())
    try:
        stat = path.stat()
    except OSError:
        return absolute, None, None
    return absolute, stat.st_size, to_local_iso(stat.st_mtime)

def format_sync_stale(path: Path, scanned_lines: int) -> str:
    absolute, size, mtime = rollout_stats(path)
    return (
        "SYNC STALE: rollout not flushed "
        f"(path={absolute}, bytes={size}, mtime={mtime}, scanned_lines={scanned_lines})"
    )

__all__ = [name for name in globals() if not name.startswith("_")]
