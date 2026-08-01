#!/usr/bin/env python3
"""Append-only coordination ledger for thread-harness."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path


STATE_VALUES = {"working", "awaiting_seam", "awaiting_owner", "done"}
SEAM_STATUS_VALUES = {"assigned", "delivered"}
SESSIONS_ROOT_ENV = "THREAD_HARNESS_SESSIONS_ROOT"
BROKER_ROOT_ENV = "THREAD_HARNESS_BROKER_ROOT"


def broker_dir() -> Path:
    """运行时根目录。测试必须用 THREAD_HARNESS_BROKER_ROOT 指到别处——
    默认目录是生产运行时，跑测试时往里写会和在跑的 harness 抢同一棵目录树。"""
    override = os.environ.get(BROKER_ROOT_ENV)
    return Path(override) if override else Path(tempfile.gettempdir()) / "codex-thread-broker"


class LedgerError(Exception):
    pass


def now_local() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def to_local_iso(value):
    if not value:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, timezone.utc).astimezone().isoformat(timespec="seconds")
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        return datetime.fromisoformat(text).astimezone().isoformat(timespec="seconds")
    except ValueError:
        return value


def runtime_dir(coordination_id: str) -> Path:
    return broker_dir() / coordination_id


def registry_path(coordination_id: str) -> Path:
    return broker_dir() / f"{coordination_id}.json"


def jsonl_path(coordination_id: str, name: str) -> Path:
    return runtime_dir(coordination_id) / name


def ensure_runtime(coordination_id: str) -> Path:
    root = runtime_dir(coordination_id)
    root.mkdir(parents=True, exist_ok=True)
    for name in ("progress.jsonl", "seams.jsonl", "decisions.jsonl"):
        jsonl_path(coordination_id, name).touch(exist_ok=True)
    return root


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict):
                rows.append(value)
    return rows


def load_state(coordination_id: str) -> dict:
    path = runtime_dir(coordination_id) / "sync-state.json"
    if not path.exists():
        return {"invalid_rounds": 0}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"invalid_rounds": 0}


def save_state(coordination_id: str, state: dict) -> None:
    path = runtime_dir(coordination_id) / "sync-state.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_registry(coordination_id: str) -> dict:
    path = registry_path(coordination_id)
    if not path.exists():
        raise LedgerError(f"registry not found: {path}")
    try:
        registry = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LedgerError(f"registry is not valid JSON: {path} ({exc})") from exc
    if not isinstance(registry, dict):
        raise LedgerError(f"registry root must be an object: {path}")
    return registry


def node_session_id(node: dict) -> str | None:
    for key in ("current_session_id", "session_id", "thread_id", "threadId"):
        value = node.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def registry_nodes(registry: dict) -> list[dict]:
    nodes: list[dict] = []

    def add(name: str, value: dict, role: str) -> None:
        session_id = node_session_id(value)
        if session_id:
            nodes.append(
                {
                    "name": name,
                    "session_id": session_id,
                    "role": role,
                    "worktree": value.get("worktree") if isinstance(value.get("worktree"), str) else None,
                }
            )

    controller = registry.get("controller")
    if isinstance(controller, dict):
        add(controller.get("name") or "controller", controller, "controller")

    children = registry.get("children") or registry.get("nodes") or []
    if isinstance(children, dict):
        for name, value in children.items():
            if isinstance(value, dict):
                add(value.get("name") or str(name), value, "child")
    elif isinstance(children, list):
        for index, value in enumerate(children):
            if isinstance(value, dict):
                add(value.get("name") or value.get("node") or f"child_{index}", value, "child")

    if not nodes:
        raise LedgerError("registry has no controller/children with current_session_id")
    return nodes


def find_rollout(session_id: str) -> Path:
    root = Path(os.environ.get(SESSIONS_ROOT_ENV) or (Path.home() / ".codex" / "sessions"))
    if not root.exists():
        raise LedgerError(f"sessions root not found: {root}")
    matches = []
    for current_root, dirs, files in os.walk(root):
        dirs[:] = [name for name in dirs if name not in {".git", "__pycache__"}]
        for filename in files:
            if filename.startswith("rollout-") and filename.endswith(".jsonl") and session_id in filename:
                matches.append(Path(current_root) / filename)
    if not matches:
        raise LedgerError(
            f"rollout not found for session id {session_id} under {root}; "
            "controller may be running in ephemeral mode, which does not persist rollout"
        )
    matches.sort(key=lambda path: str(path))
    return matches[-1]


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
            arguments = payload.get("arguments") if "arguments" in payload else item.get("arguments")
            text = stringify(arguments)
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
    needles = ("codex_app__send_message_to_thread", "codex_app__create_thread")
    for obj in events:
        item = response_item(obj)
        if not item:
            continue
        payload = payload_of(item)
        item_type = item.get("type") or payload.get("type")
        if item_type != "custom_tool_call":
            continue
        text = stringify(payload.get("arguments") if "arguments" in payload else item.get("arguments"))
        name = stringify(payload.get("name") or item.get("name") or "")
        if any(needle in text or needle in name for needle in needles):
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
        return "timeoutMs missing < 180000", []
    timeout_ms = int(timeout_match.group(1))
    if timeout_ms < 180000:
        return f"timeoutMs {timeout_ms} < 180000", []

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


def validate_projection(payload: dict | None, actual_targets: int) -> str | None:
    if not isinstance(payload, dict) or payload.get("v") != 1:
        return "projection missing or wrong version"
    for key in ("n", "polls"):
        if key not in payload:
            return f"projection shape altered (missing {key})"
    n = payload.get("n")
    if n != actual_targets:
        return f"projection n={n} != actual targets {actual_targets}"
    polls = payload.get("polls")
    if not isinstance(polls, list):
        return "poll entry shape altered"
    for poll in polls:
        if not isinstance(poll, dict) or any(key not in poll for key in ("id", "status", "turn", "turnStatus", "txt")):
            return "poll entry shape altered"
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
        return "done"
    if "owner" in text:
        return "awaiting_owner"
    if "seam" in text or waiting_on:
        return "awaiting_seam"
    return "working"


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


def classify_and_rows(payload: dict, nodes: list[dict], round_no: int, previous: dict) -> tuple[list[dict], dict]:
    ts = now_local()
    by_session = {node["session_id"]: node for node in nodes}
    by_name = {node["name"]: node for node in nodes}
    rows_by_name = {}
    polls = payload.get("polls") if isinstance(payload.get("polls"), list) else []
    heads = {node["name"]: git_head(node.get("worktree")) for node in nodes}

    for poll in polls:
        if not isinstance(poll, dict):
            continue
        session_id = field(poll, "id")
        name = field(poll, "node", "name")
        node = by_session.get(session_id) or by_name.get(name)
        if not node:
            continue
        status = field(poll, "status")
        note = field(poll, "txt")
        rows_by_name[node["name"]] = {
            "ts": ts,
            "src": "poll",
            "round": round_no,
            "node": node["name"],
            "head": heads.get(node["name"]),
            "turn": field(poll, "turn"),
            "status": status,
            "turn_status": field(poll, "turnStatus"),
            "state": normalize_state(status),
            "note": str(note or status or "")[:500],
        }

    for node in nodes:
        if node["name"] not in rows_by_name:
            prev = previous.get(node["name"], {})
            rows_by_name[node["name"]] = {
                "ts": ts,
                "src": "poll",
                "round": round_no,
                "node": node["name"],
                "head": heads.get(node["name"]),
                "turn": prev.get("turn"),
                "status": prev.get("status"),
                "turn_status": prev.get("turn_status"),
                "state": prev.get("state") if prev.get("state") in STATE_VALUES else "working",
                "note": "no poll payload for node",
            }

    wake = payload.get("wake") if isinstance(payload.get("wake"), dict) else {}
    wake_reason = wake.get("reason")
    idle_sessions = wake_thread_ids(wake) if wake_reason == "inactiveStatus" else set()
    idle_nodes = {by_session[sid]["name"] for sid in idle_sessions if sid in by_session}
    if wake_reason == "inactiveStatus" and not idle_nodes:
        for poll in polls:
            if not isinstance(poll, dict):
                continue
            status_text = str(field(poll, "status") or "").lower()
            session_id = field(poll, "id")
            if "inactive" in status_text or "notloaded" in status_text or "not_loaded" in status_text:
                node = by_session.get(session_id)
                if node:
                    idle_nodes.add(node["name"])

    changed_nodes = []
    unchanged = []
    head_changed = False
    for node in nodes:
        name = node["name"]
        row = rows_by_name[name]
        old_head = previous.get(name, {}).get("head")
        new_head = row.get("head")
        if new_head and old_head and new_head != old_head:
            head_changed = True
            if name in idle_nodes:
                continue
            changed_nodes.append((name, new_head, old_head))
        elif new_head and not old_head:
            head_changed = True
            if name in idle_nodes:
                continue
            changed_nodes.append((name, new_head, None))
        else:
            if name in idle_nodes:
                continue
            unchanged.append(name)

    return list(rows_by_name.values()), {
        "wake_reason": wake_reason,
        "idle_nodes": sorted(idle_nodes),
        "changed_nodes": changed_nodes,
        "unchanged": unchanged,
        "head_changed": head_changed,
        "head_unavailable": sorted(name for name, head in heads.items() if head is None),
    }


def latest_progress_parts(coordination_id: str) -> tuple[dict, dict]:
    latest_poll = {}
    latest_report = {}
    for row in read_jsonl(jsonl_path(coordination_id, "progress.jsonl")):
        node = row.get("node")
        if not node:
            continue
        if row.get("src") == "report":
            latest_report[node] = row
        elif row.get("src") == "poll":
            latest_poll[node] = row
        else:
            latest_report[node] = row
    return latest_poll, latest_report


def latest_progress(coordination_id: str) -> dict:
    latest_poll, latest_report = latest_progress_parts(coordination_id)
    names = set(latest_poll) | set(latest_report)
    latest = {}
    for name in names:
        poll = latest_poll.get(name, {})
        report = latest_report.get(name, {})
        row = dict(poll or report)
        if report:
            row["state"] = report.get("state")
            row["waiting_on"] = report.get("waiting_on") if isinstance(report.get("waiting_on"), list) else []
            row["last_report_ts"] = report.get("last_report_ts") or report.get("ts")
        else:
            row["state"] = poll.get("state") if poll.get("state") in STATE_VALUES else "working"
            row["waiting_on"] = []
            row["last_report_ts"] = None
        if poll:
            row["head"] = poll.get("head")
            row["turn"] = poll.get("turn")
            row["status"] = poll.get("status")
            row["turn_status"] = poll.get("turn_status")
        latest[name] = row
    return latest


def pending_decisions(coordination_id: str) -> list[dict]:
    status_by_id = {}
    for row in read_jsonl(jsonl_path(coordination_id, "decisions.jsonl")):
        decision_id = row.get("decision_id")
        if decision_id:
            status_by_id[decision_id] = row
    return [row for row in status_by_id.values() if row.get("status") == "pending"]


def seam_producers(coordination_id: str) -> dict:
    producers = {}
    for row in read_jsonl(jsonl_path(coordination_id, "seams.jsonl")):
        seam_id = row.get("seam_id")
        producer = row.get("producer")
        if seam_id and producer:
            producers[seam_id] = producer
    return producers


def latest_by_round(coordination_id: str) -> list[tuple[int, dict]]:
    rounds = {}
    for row in read_jsonl(jsonl_path(coordination_id, "progress.jsonl")):
        if row.get("src") != "poll":
            continue
        round_no = row.get("round")
        node = row.get("node")
        if isinstance(round_no, int) and node:
            rounds.setdefault(round_no, {})[node] = row.get("head")
    return sorted(rounds.items(), key=lambda item: item[0])


def stall_streak(coordination_id: str) -> int:
    """连续多少轮没有任何 node 的 git HEAD 推进。

    head 取不到（worktree 缺失/不是 git 仓库）时**沿用该 node 上次已知值**，
    即"无证据表明有推进"，而不是重置计数。

    这里必须 fail-closed：曾经的实现是"任一 head 为 None 就把 streak 清零"，
    后果是一条线的 worktree 路径写错就永久关掉整组的停滞检测，而且完全无声——
    正是本 harness 要消灭的那种失效。误报一次 MUST_ACT 的代价远低于永不报警。
    取不到这件事本身由摘要的 head_unavailable 单独暴露。
    """
    rounds = latest_by_round(coordination_id)
    streak = 0
    previous = None
    carried: dict = {}
    for _, heads in rounds:
        effective = {}
        for node, head in heads.items():
            if head is None:
                effective[node] = carried.get(node)
            else:
                effective[node] = head
                carried[node] = head
        if previous is not None and effective == previous:
            streak += 1
        else:
            streak = 0
        previous = effective
    return streak


def seams_unowned_count(coordination_id: str) -> int:
    producers = seam_producers(coordination_id)
    latest = latest_progress(coordination_id)
    missing = set()
    for row in latest.values():
        waiting_on = row.get("waiting_on")
        if not isinstance(waiting_on, list):
            continue
        for item in waiting_on:
            if isinstance(item, str) and item.startswith("seam:"):
                seam_id = item.split(":", 1)[1]
                if seam_id and seam_id not in producers:
                    missing.add(seam_id)
    return len(missing)


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


def format_summary(round_no: int, valid: bool, offset: int, classification: dict, coordination_id: str, streak_limit: int) -> str:
    changed = classification["changed_nodes"]
    pending = pending_decisions(coordination_id)
    changed_text = ", ".join(
        f"{name}({new} <- {old})" if old else f"{name}({new} <- none)"
        for name, new, old in changed
    ) or "-"
    pending_text = f"{len(pending)}"
    if pending:
        first = pending[0]
        pending_text += f"  ({first.get('decision_id')}, raised_by={first.get('raised_by')}, blocks={len(first.get('blocks') or [])})"
    return "\n".join(
        [
            f"ROUND {round_no}  valid={'yes' if valid else 'no'}  offset={offset}",
            f"idle_nodes:      {', '.join(classification['idle_nodes']) or '-'}",
            f"changed_nodes:   {changed_text}",
            f"unchanged:       {', '.join(classification['unchanged']) or '-'}",
            f"head_unavailable: {', '.join(classification.get('head_unavailable') or []) or '-'}",
            f"never_reported:  {', '.join(classification.get('never_reported') or []) or '-'}",
            f"pending_decisions: {pending_text}",
            f"stall_streak:    {stall_streak(coordination_id)}/{streak_limit}",
            f"seams_unowned:   {seams_unowned_count(coordination_id)}",
            f"dispatches_since_progress: {load_state(coordination_id).get('dispatches_since_progress', 0)}",
        ]
    )


def cmd_init(args) -> int:
    ensure_runtime(args.coordination_id)
    print(f"initialized {runtime_dir(args.coordination_id)}")
    return 0


def cmd_sync(args) -> int:
    ensure_runtime(args.coordination_id)
    registry = load_registry(args.coordination_id)
    nodes = registry_nodes(registry)
    controller = next((node for node in nodes if node["role"] == "controller"), nodes[0])
    rollout = find_rollout(controller["session_id"])
    state = load_state(args.coordination_id)
    if state.get("rollout_path") != str(rollout):
        state["rollout_path"] = str(rollout)
        state["offset"] = 0
    offset = int(state.get("offset") or 0)

    call = output = None
    events = []
    new_offset = offset
    scanned_lines = 0
    for attempt in range(20):
        rollout.stat()
        events, new_offset, scanned_lines = read_rollout_events(rollout, offset)
        call, output = latest_wait_round(events)
        if call and output:
            break
        if attempt < 19:
            time.sleep(0.1)

    if not call or not output:
        print(format_sync_stale(rollout, scanned_lines))
        return 1

    dispatches = count_dispatch_calls(events)
    state["dispatches_since_progress"] = int(state.get("dispatches_since_progress") or 0) + dispatches

    # 轮询目标是全部 children，不含 controller 自己——主控轮询自身没有意义。
    poll_targets = [node for node in nodes if node["role"] != "controller"]
    reason, actual_ids = validate_call(call["arguments"], [node["session_id"] for node in poll_targets])
    if reason:
        state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
        state["offset"] = new_offset
        save_state(args.coordination_id, state)
        print(f"ROUND INVALID: poll snippet altered ({reason})")
        return 1

    payload = extract_projection(output["output"])
    reason = validate_projection(payload, len(actual_ids))
    if reason:
        state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
        state["offset"] = new_offset
        save_state(args.coordination_id, state)
        print(f"ROUND INVALID: poll snippet altered ({reason})")
        return 1

    latest_poll, latest_report = latest_progress_parts(args.coordination_id)
    rows, classification = classify_and_rows(payload, poll_targets, args.round, latest_progress(args.coordination_id))
    classification["never_reported"] = sorted(node["name"] for node in poll_targets if node["name"] not in latest_report)
    for row in rows:
        append_jsonl(jsonl_path(args.coordination_id, "progress.jsonl"), row)
    if classification["head_changed"]:
        state["dispatches_since_progress"] = 0
    state["offset"] = new_offset
    save_state(args.coordination_id, state)
    print(format_summary(args.round, True, new_offset, classification, args.coordination_id, args.streak))
    return 0


def cmd_report(args) -> int:
    ensure_runtime(args.coordination_id)
    if args.state not in STATE_VALUES:
        raise LedgerError(f"invalid state {args.state}; expected one of {', '.join(sorted(STATE_VALUES))}")
    append_jsonl(
        jsonl_path(args.coordination_id, "progress.jsonl"),
        {
            "ts": now_local(),
            "src": "report",
            "round": args.round,
            "node": args.node,
            "head": args.head,
            "state": args.state,
            "waiting_on": args.waiting_on or [],
            "last_report_ts": now_local(),
            "note": args.note or "",
        },
    )
    print(f"reported {args.node} state={args.state}")
    return 0


def cmd_seam(args) -> int:
    ensure_runtime(args.coordination_id)
    registry = load_registry(args.coordination_id)
    known_nodes = {node["name"] for node in registry_nodes(registry)}
    if args.producer not in known_nodes:
        raise LedgerError(f"unknown producer node: {args.producer}")
    for consumer in args.consumers or []:
        if consumer not in known_nodes:
            raise LedgerError(f"unknown consumer node: {consumer}")
    status = "delivered" if args.deliver else "assigned"
    append_jsonl(
        jsonl_path(args.coordination_id, "seams.jsonl"),
        {
            "ts": now_local(),
            "seam_id": args.seam_id,
            "producer": args.producer,
            "consumers": args.consumers or [],
            "status": status,
            "artifact": args.deliver,
        },
    )
    print(f"seam {args.seam_id} status={status}")
    return 0


def cmd_decide(args) -> int:
    ensure_runtime(args.coordination_id)
    if args.raise_id:
        append_jsonl(
            jsonl_path(args.coordination_id, "decisions.jsonl"),
            {
                "ts": now_local(),
                "decision_id": args.raise_id,
                "raised_by": args.by,
                "blocks": args.blocks or [],
                "question": args.question,
                "status": "pending",
                "answer": None,
            },
        )
        print(f"decision {args.raise_id} status=pending")
        return 0
    if args.answer:
        append_jsonl(
            jsonl_path(args.coordination_id, "decisions.jsonl"),
            {
                "ts": now_local(),
                "decision_id": args.answer,
                "raised_by": None,
                "blocks": [],
                "question": None,
                "status": "answered",
                "answer": args.text,
            },
        )
        print(f"decision {args.answer} status=answered")
        return 0
    raise LedgerError("decide requires --raise or --answer")


def cmd_stall_check(args) -> int:
    ensure_runtime(args.coordination_id)
    dispatches = int(load_state(args.coordination_id).get("dispatches_since_progress") or 0)
    pending = pending_decisions(args.coordination_id)
    if pending:
        items = ", ".join(f"{row.get('decision_id')} raised_by={row.get('raised_by')}" for row in pending)
        print(f"MUST_ESCALATE pending_decisions: {items} dispatches_since_progress={dispatches}")
        return 3
    streak = stall_streak(args.coordination_id)
    if streak >= args.streak:
        print(f"MUST_ACT stall_streak={streak}/{args.streak} dispatches_since_progress={dispatches}")
        return 2
    print(f"OK stall_streak={streak}/{args.streak} dispatches_since_progress={dispatches}")
    return 0


class UsageErrorParser(argparse.ArgumentParser):
    """用法错误退出 64（EX_USAGE），不用 argparse 默认的 2。

    2 是 stall-check 的 MUST_ACT。若用法错误也退 2，broker 会把一次拼错的命令
    读成"必须行动"，或者反过来把真正的 MUST_ACT 当成拼写问题忽略掉。退出码
    必须在语义上唯一。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"ERROR: {message}", file=sys.stderr)
        raise SystemExit(64)


def build_parser() -> argparse.ArgumentParser:
    parser = UsageErrorParser(description="thread-harness append-only ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    init = sub.add_parser("init")
    init.add_argument("--coordination-id", required=True)
    init.set_defaults(func=cmd_init)

    sync = sub.add_parser("sync")
    sync.add_argument("--coordination-id", required=True)
    sync.add_argument("--round", required=True, type=int)
    sync.add_argument("--streak", type=int, default=3)
    sync.set_defaults(func=cmd_sync)

    report = sub.add_parser("report")
    report.add_argument("--coordination-id", required=True)
    report.add_argument("--node", required=True)
    report.add_argument("--state", required=True)
    report.add_argument("--round", type=int, default=0)
    report.add_argument("--head")
    report.add_argument("--waiting-on", action="extend", nargs="+", default=[])
    report.add_argument("--note")
    report.set_defaults(func=cmd_report)

    seam = sub.add_parser("seam")
    seam.add_argument("--coordination-id", required=True)
    seam.add_argument("--seam-id", required=True)
    seam.add_argument("--producer", required=True)
    seam.add_argument("--consumers", action="extend", nargs="+", default=[])
    seam.add_argument("--deliver")
    seam.set_defaults(func=cmd_seam)

    decide = sub.add_parser("decide")
    decide.add_argument("--coordination-id", required=True)
    decide.add_argument("--raise", dest="raise_id")
    decide.add_argument("--by")
    decide.add_argument("--blocks", action="extend", nargs="+", default=[])
    decide.add_argument("--question")
    decide.add_argument("--answer")
    decide.add_argument("--text")
    decide.set_defaults(func=cmd_decide)

    stall = sub.add_parser("stall-check")
    stall.add_argument("--coordination-id", required=True)
    stall.add_argument("--streak", type=int, default=3)
    stall.set_defaults(func=cmd_stall_check)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
