#!/usr/bin/env python3
"""Coordination state, progress classification and action summaries."""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path

import ledger_runtime as rt
from ledger_runtime import *
from broker_contract import BUDGET_STAGES, budget_stage, node_kind
from rollout_compaction import RolloutCompactionError, observe_rollout
from ledger_poll import *
from ledger_registry import *

def update_compaction_observers(state: dict, nodes: list[dict]) -> None:
    """更新 controller 与 active child current session 的增量 rollout 观测状态。"""
    sessions_root = Path(
        os.environ.get(SESSIONS_ROOT_ENV) or (Path.home() / ".codex" / "sessions")
    )
    observers = state.get("compaction_observers")
    if not isinstance(observers, dict):
        observers = {}
    for node in nodes:
        if node["role"] == "child" and (
            not node.get("active", True) or node.get("node_type") != "task"
        ):
            continue
        session_id = node["session_id"]
        previous = observers.get(session_id)
        try:
            observers[session_id] = observe_rollout(
                session_id,
                previous if isinstance(previous, dict) else None,
                sessions_root,
            )
        except (OSError, RolloutCompactionError):
            continue
    state["compaction_observers"] = observers

def update_budget_states(state: dict, registry: dict, config: dict) -> None:
    """根据当前 session 的 token observer 机械计算并持久化预算阶段。"""
    observers = state.get("compaction_observers")
    if not isinstance(observers, dict):
        observers = {}
    budget_states = state.get("budget_states")
    if not isinstance(budget_states, dict):
        budget_states = {}

    for node in registry_nodes(registry):
        if node["role"] == "child" and (
            not node.get("active", True) or node.get("node_type") != "task"
        ):
            continue
        session_id = node.get("session_id")
        if not session_id:
            continue
        observer = observers.get(session_id)
        previous = budget_states.get(session_id)
        previous_stage = previous.get("stage") if isinstance(previous, dict) else None
        compaction_count = observer.get("observed_count") if isinstance(observer, dict) else None
        stage, source = budget_stage(
            observer,
            config,
            previous_stage=previous_stage,
            compaction_count=compaction_count,
        )
        budget_states[session_id] = {
            "stage": stage,
            "source": source,
            "handoff_at": config["budget"]["handoff_at"],
            "last_input_tokens": (
                observer.get("last_token_usage", {}).get("input_tokens")
                if isinstance(observer, dict) and isinstance(observer.get("last_token_usage"), dict)
                else None
            ),
        }
    state["budget_states"] = budget_states

def budget_stage_text(registry: dict, state: dict) -> str:
    budget_states = state.get("budget_states")
    if not isinstance(budget_states, dict):
        budget_states = {}
    parts = []
    for entry in route_registry_entries(registry):
        if entry["role"] == "child" and (
            not entry["active"] or node_kind(entry["node"]) != "task"
        ):
            continue
        session_id = node_session_id(entry["node"])
        current = budget_states.get(session_id) if session_id else None
        stage = current.get("stage") if isinstance(current, dict) else "tracking"
        if stage not in BUDGET_STAGES:
            stage = "tracking"
        parts.append(f"{entry['name']}={stage}")
    return ", ".join(parts) or "-"

def handoff_required_text(registry: dict, state: dict) -> str:
    budget_states = state.get("budget_states")
    if not isinstance(budget_states, dict):
        budget_states = {}
    names = []
    for entry in route_registry_entries(registry):
        if entry["role"] == "child" and (
            not entry["active"] or node_kind(entry["node"]) != "task"
        ):
            continue
        session_id = node_session_id(entry["node"])
        current = budget_states.get(session_id) if session_id else None
        if isinstance(current, dict) and current.get("stage") == "handoff_due":
            names.append(entry["name"])
    return ", ".join(names) or "-"

def compaction_count_text(registry: dict, state: dict) -> str:
    """按 controller 与 active child current session 输出基线后的 compaction 次数。"""
    observers = state.get("compaction_observers")
    if not isinstance(observers, dict):
        observers = {}
    counts = []
    for entry in route_registry_entries(registry):
        if entry["role"] == "child" and (
            not entry["active"] or node_kind(entry["node"]) != "task"
        ):
            continue
        session_id = node_session_id(entry["node"])
        observer = observers.get(session_id) if session_id else None
        count = observer.get("observed_count") if isinstance(observer, dict) else None
        counts.append((entry["name"], count if type(count) is int and count >= 0 else None))
    return ", ".join(
        f"{name}={count}" if count is not None else f"{name}=?"
        for name, count in counts
    ) or "-"

def classify_and_rows(
    payload: dict,
    nodes: list[dict],
    round_no: int,
    seq: int,
    previous: dict,
    *,
    profile: str = "swarm",
) -> tuple[list[dict], dict]:
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
            "seq": seq,
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
                "seq": seq,
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

    def latest_state(name: str) -> str:
        previous_state = previous.get(name, {}).get("state")
        if previous_state in STATE_VALUES:
            return previous_state
        return rows_by_name[name].get("state") or "unknown"

    def may_be_idle(name: str) -> bool:
        return latest_state(name) == "working"

    reassignment_required = []
    if profile == "swarm":
        reassignment_required = sorted(
            node["name"]
            for node in nodes
            if node.get("active", True) and latest_state(node["name"]) in REASSIGNMENT_STATES
        )

    idle_sessions = wake_thread_ids(wake) if wake_reason == "inactiveStatus" else set()
    idle_nodes = {
        by_session[sid]["name"]
        for sid in idle_sessions
        if sid in by_session and by_session[sid].get("active", True) and may_be_idle(by_session[sid]["name"])
    }
    # Desktop may expose an idle thread through polls[].status even when wake.reason
    # is turnCompleted or absent.  Treat status as the primary per-node signal and
    # inactiveStatus only as an additional wake hint.
    for poll in polls:
        if not isinstance(poll, dict):
            continue
        status_text = str(field(poll, "status") or "").lower().replace("-", "_")
        session_id = field(poll, "id")
        node = by_session.get(session_id)
        if node and status_text in IDLE_STATUS_VALUES and node.get("active", True) and may_be_idle(node["name"]):
            idle_nodes.add(node["name"])

    changed_nodes = []
    advance_kinds = {}
    unchanged = []
    head_changed = False
    for node in nodes:
        name = node["name"]
        row = rows_by_name[name]
        old_head = previous.get(name, {}).get("head")
        new_head = row.get("head")
        if new_head and old_head and new_head != old_head:
            head_changed = True
            advance_kinds[name] = advance_kind(node.get("worktree"), new_head, old_head)
            changed_nodes.append((name, new_head, old_head))
        elif new_head and not old_head:
            head_changed = True
            advance_kinds[name] = advance_kind(node.get("worktree"), new_head)
            changed_nodes.append((name, new_head, None))
        else:
            if name in idle_nodes:
                continue
            unchanged.append(name)

    return list(rows_by_name.values()), {
        "wake_reason": wake_reason,
        "reassignment_required": reassignment_required,
        "idle_nodes": sorted(idle_nodes),
        "changed_nodes": changed_nodes,
        "advance_kinds": advance_kinds,
        "unchanged": unchanged,
        "head_changed": head_changed,
        "head_unavailable": sorted(name for name, head in heads.items() if head is None),
        "unknown_status": sorted(
            row["node"] for row in rows_by_name.values()
            if row.get("state") == "unknown" and row.get("note") != "no poll payload for node"
        ),
        "timed_out": bool(payload.get("timedOut")),
        "timed_out_no_change": bool(payload.get("timedOut")) and not polls,
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

def stale_report_nodes(coordination_id: str) -> set[str]:
    latest_report_index = {}
    rows = read_jsonl(jsonl_path(coordination_id, "progress.jsonl"))
    for index, row in enumerate(rows):
        if row.get("src") == "report" and row.get("node"):
            latest_report_index[row["node"]] = (index, row)

    stale = set()
    for node, (report_index, report) in latest_report_index.items():
        report_head = report.get("head")
        for row in rows[report_index + 1:]:
            if row.get("src") != "poll" or row.get("node") != node:
                continue
            poll_head = row.get("head")
            if poll_head and (not report_head or poll_head != report_head):
                stale.add(node)
                break
    return stale

def latest_progress(coordination_id: str) -> dict:
    latest_poll, latest_report = latest_progress_parts(coordination_id)
    stale_nodes = stale_report_nodes(coordination_id)
    names = set(latest_poll) | set(latest_report)
    latest = {}
    for name in names:
        poll = latest_poll.get(name, {})
        report = latest_report.get(name, {})
        row = dict(poll or report)
        if report:
            row["state"] = report.get("state")
            if name in stale_nodes:
                row["state"] = f"{row['state']}(stale)"
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

def runnable_watch_nodes(coordination_id: str, active_children: list[dict]) -> list[dict]:
    """Return the active children that still need a blocking wait.

    A report-backed seam/owner wait or completed node is already waiting on an
    explicit controller/Owner action.  It must remain in HEAD collection and
    progress projection, but it must not keep waking a fixed blocking wait.
    A dispatch recorded after the report makes that producer runnable again.
    """
    latest = latest_progress(coordination_id)
    _, latest_report = latest_progress_parts(coordination_id)
    stale_nodes = stale_report_nodes(coordination_id)
    dispatched_nodes = set()
    for act in read_jsonl(jsonl_path(coordination_id, "acts.jsonl")):
        producer = act.get("producer")
        if act.get("kind") != "dispatch" or not producer:
            continue
        report = latest_report.get(producer)
        if not report or ledger_event_after(act, report):
            dispatched_nodes.add(producer)
    runnable = []
    for node in active_children:
        name = node["name"]
        state = latest.get(name, {}).get("state")
        if (
            name not in latest_report
            or name in stale_nodes
            or name in dispatched_nodes
            or state not in NON_RUNNABLE_STATES
        ):
            runnable.append(node)
    return runnable

def pending_decisions(coordination_id: str) -> list[dict]:
    status_by_id = {}
    for row in read_jsonl(jsonl_path(coordination_id, "decisions.jsonl")):
        decision_id = row.get("decision_id")
        if decision_id:
            status_by_id[decision_id] = row
    return [row for row in status_by_id.values() if row.get("status") == "pending"]

def decision_ids(rows: list[dict]) -> list[str]:
    return [row.get("decision_id") for row in rows if row.get("decision_id")]

def format_id_list(ids: list) -> str:
    return ", ".join(str(item) for item in ids if item) or "-"

def pending_escalation_groups(coordination_id: str) -> tuple[list[dict], list[dict]]:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    unreported = []
    already_escalated = []
    for decision in pending_decisions(coordination_id):
        decision_id = decision.get("decision_id")
        decision_instance_id = decision.get("decision_instance_id")
        if isinstance(decision_instance_id, str) and decision_instance_id:
            escalated = any(
                row.get("kind") == "escalate"
                and row.get("decision_id") == decision_id
                and row.get("decision_instance_id") == decision_instance_id
                for row in acts
            )
        else:
            # Legacy rows have no instance id.  Keep the old timestamp fallback
            # only for legacy raise/escalate rows; a newer instance must not
            # accidentally mask a legacy pending record.
            raise_ts = decision.get("ts")
            escalated = any(
                row.get("kind") == "escalate"
                and row.get("decision_id") == decision_id
                and not row.get("decision_instance_id")
                and ts_not_earlier(row.get("ts"), raise_ts)
                for row in acts
            )
        if escalated:
            already_escalated.append(decision)
        else:
            unreported.append(decision)
    return unreported, already_escalated

def latest_act(coordination_id: str) -> dict | None:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    return acts[-1] if acts else None

def halted_act(coordination_id: str) -> dict | None:
    acts = read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))
    halt = next((row for row in reversed(acts) if row.get("kind") == "halt"), None)
    if not halt:
        return None
    halt_poll_seq = halt.get("halt_poll_seq")
    if not isinstance(halt_poll_seq, int):
        # 旧 halt 行没有 poll 序号。**不要拿 act seq 去比 poll seq**——它们是两个
        # 独立计数器（实测一次真实运行里 poll 已到 135 而 act 才 38），比较的结果
        # 是任何旧 halt 行都立刻失效。退回旧语义：只有当它仍是最后一条 act 时才
        # 算 halted，由后续 act 显式解除。
        return halt if acts and acts[-1] is halt else None
    current_poll_seq = int(load_state(coordination_id).get("next_poll_seq") or 0)
    if current_poll_seq > halt_poll_seq:
        return None
    return halt

def last_must_act_answered(coordination_id: str) -> bool:
    state = load_state(coordination_id)
    last_seq = state.get("last_must_act_seq")
    if not isinstance(last_seq, int):
        return False
    for row in read_jsonl(jsonl_path(coordination_id, "acts.jsonl")):
        seq = row.get("seq")
        if isinstance(seq, int) and seq > last_seq:
            return True
    return False

def canonical_seam_id(value: str) -> str:
    """Accept a bare ID or waiting_on-style seam:<id>, and return the bare ID."""
    seam_id = value.removeprefix("seam:")
    if not seam_id or seam_id.startswith("seam:"):
        raise UsageError("seam ID must be <id> or seam:<id>")
    return seam_id

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
        round_no = row.get("seq")
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
    reset_seq = load_state(coordination_id).get("stall_reset_seq")
    if isinstance(reset_seq, int):
        rounds = [(seq, heads) for seq, heads in rounds if seq >= reset_seq]
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

def seams_waiting_counts(coordination_id: str) -> tuple[int, int, int]:
    producers = seam_producers(coordination_id)
    latest = latest_progress(coordination_id)
    missing = set()
    malformed = 0
    stale_waiting_on = 0
    for row in latest.values():
        waiting_on = row.get("waiting_on")
        state = row.get("state")
        if state != "awaiting_seam":
            if state == "awaiting_seam(stale)" and isinstance(waiting_on, list):
                stale_waiting_on += len(waiting_on)
            elif state == "awaiting_seam(stale)" and waiting_on:
                stale_waiting_on += 1
            continue
        if not isinstance(waiting_on, list):
            if waiting_on:
                malformed += 1
            continue
        for item in waiting_on:
            if isinstance(item, str) and item.startswith("seam:"):
                seam_id = item.split(":", 1)[1]
                if seam_id and seam_id not in producers:
                    missing.add(seam_id)
                elif not seam_id:
                    malformed += 1
            elif item:
                malformed += 1
            else:
                malformed += 1
    return len(missing), malformed, stale_waiting_on

def seams_unowned_count(coordination_id: str) -> int:
    return seams_waiting_counts(coordination_id)[0]

def format_summary(
    round_no: int,
    valid: bool,
    offset: int,
    classification: dict,
    coordination_id: str,
    registry: dict | None = None,
) -> str:
    changed = classification["changed_nodes"]
    pending = pending_decisions(coordination_id)
    unowned, malformed, stale_waiting_on = seams_waiting_counts(coordination_id)
    state = load_state(coordination_id)
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
            f"poll_targets:    {', '.join(classification.get('watch_nodes') or []) or '-'}",
            f"reassignment_required: {', '.join(classification.get('reassignment_required') or []) or '-'}",
            f"idle_nodes:      {', '.join(classification['idle_nodes']) or '-'}",
            f"changed_nodes:   {changed_text}",
            f"advance_kinds:   {', '.join(f'{name}={kind}' for name, kind in sorted((classification.get('advance_kinds') or {}).items())) or '-'}",
            f"unchanged:       {', '.join(classification['unchanged']) or '-'}",
            f"session_age_h:   {session_age_text(registry or {})}",
            f"compaction_count: {compaction_count_text(registry or {}, state)}",
            f"budget_stage:    {budget_stage_text(registry or {}, state)}",
            f"handoff_required: {handoff_required_text(registry or {}, state)}",
            f"timedOut:        {str(bool(classification.get('timed_out'))).lower()}"
            + (" (timeout, no change)" if classification.get("timed_out_no_change") else ""),
            f"head_unavailable: {', '.join(classification.get('head_unavailable') or []) or '-'}",
            f"never_reported:  {', '.join(classification.get('never_reported') or []) or '-'}",
            f"stale_reports:   {', '.join(sorted(stale_report_nodes(coordination_id))) or '-'}",
            f"unknown_status:  {', '.join(classification.get('unknown_status') or []) or '-'}",
            f"pending_decisions: {pending_text}",
            f"stall_streak:    {stall_streak(coordination_id)}/{STALL_LIMIT}",
            f"seams_unowned:   {unowned}",
            f"stale_waiting_on: {stale_waiting_on}",
            f"malformed_waiting_on: {malformed}",
            f"dispatches_since_progress: {state.get('dispatches_since_progress', 0)}",
            f"docs_only_advances: {state.get('docs_only_advances', 0)}",
            f"corrupt_ledger_lines: {corrupt_ledger_lines(coordination_id)}",
        ]
    )

__all__ = [name for name in globals() if not name.startswith("_")]
