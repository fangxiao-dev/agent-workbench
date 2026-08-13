#!/usr/bin/env python3
"""Command handlers for the thread-harness coordination broker."""

from __future__ import annotations

import json
import os
import re
import tempfile
import uuid
from pathlib import Path

from ledger_runtime import *
from ledger_registry import *
from ledger_poll import *
from ledger_coordination import *

def cmd_preflight(args) -> int:
    issues: list[tuple[str, str]] = []
    warnings: list[tuple[str, str]] = []
    path = registry_path(args.coordination_id)
    registry = None

    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        issues.append(("registry_missing", str(path)))
    except (OSError, UnicodeError) as exc:
        issues.append(("registry_unreadable", f"{path} ({exc})"))
    else:
        try:
            registry = json.loads(raw)
        except (json.JSONDecodeError, UnicodeError) as exc:
            issues.append(("registry_unparseable", f"{path} ({exc})"))
        if registry is not None and not isinstance(registry, dict):
            issues.append(("registry_unparseable", "registry root must be an object"))
            registry = None

    nodes: list[dict] = []
    children_count = 0
    if registry is not None:
        config, broker_issues = validate_broker_config(registry)
        issues.extend(broker_issues)
        nodes, children_count = preflight_registry_nodes(registry, issues)
        if children_count > PREFLIGHT_CHILD_LIMIT:
            issues.append(("children_limit", f"children={children_count} max={PREFLIGHT_CHILD_LIMIT}"))
        preflight_field_issues(nodes, issues)
        preflight_broker_and_packages(registry, config, nodes, issues, warnings)
        issues.extend(preflight_duplicate_issues(nodes, "session_id", "duplicate_session_id"))
        issues.extend(preflight_duplicate_issues(nodes, "branch", "duplicate_branch"))
        issues.extend(
            preflight_duplicate_issues(nodes, "worktree", "shared_worktree", normalized_worktree)
        )

        for node in nodes:
            worktree = node.get("worktree")
            if not isinstance(worktree, str) or not worktree.strip():
                continue
            info = preflight_git_info(worktree)
            if info["kind"] == "missing":
                issues.append(("worktree_missing", f"{node['name']} -> {worktree}"))
                continue
            if info["kind"] == "not_git":
                issues.append(("not_git_repository", f"{node['name']} -> {worktree}"))
                continue
            if info["kind"] == "head_unavailable":
                issues.append(("head_unavailable", f"{node['name']} -> {worktree}"))

            registry_branch = node.get("branch")
            if isinstance(registry_branch, str) and registry_branch.strip():
                if info.get("branch") != registry_branch:
                    issues.append(
                        (
                            "branch_mismatch",
                            f"{node['name']} registry={registry_branch} actual={info.get('branch') or '<unknown>'}",
                        )
                    )

            dirty_count = info.get("dirty_count")
            if isinstance(dirty_count, int) and dirty_count:
                warnings.append(("dirty_worktree", f"{node['name']} ({dirty_count} files)"))

        for node in nodes:
            session_id = node.get("session_id")
            if not isinstance(session_id, str) or not session_id:
                continue
            try:
                find_rollout(session_id)
            except (LedgerError, OSError):
                if node["role"] == "controller":
                    issues.append(("controller_rollout_missing", session_id))
                else:
                    warnings.append(("child_rollout_missing", node["name"]))

    runtime_missing = []
    for name in PREFLIGHT_RUNTIME_FILES:
        runtime_path = jsonl_path(args.coordination_id, name)
        try:
            present = runtime_path.is_file()
        except OSError:
            present = False
        if not present:
            runtime_missing.append(name)
    if runtime_missing:
        issues.append(("runtime_uninitialized", f"missing={', '.join(runtime_missing)}; run init first"))

    if issues:
        print("PREFLIGHT FAILED")
        for tag, detail in issues:
            print(f"  {tag:<24} {detail}")
    else:
        print(
            f"PREFLIGHT OK  profile={config['profile']} nodes={len(nodes)} children={children_count} "
            f"handoff_at={config['budget']['handoff_at']}"
        )
    if warnings:
        print("warnings:")
        for tag, detail in sorted(warnings, key=lambda item: (item[0], item[1])):
            print(f"  {tag:<24} {detail}")
    return 5 if issues else 0

def cmd_init(args) -> int:
    ensure_runtime(args.coordination_id)
    print(f"initialized {runtime_dir(args.coordination_id)}")
    return 0

def cmd_sync(args) -> int:
    ensure_runtime(args.coordination_id)
    registry = load_registry(args.coordination_id)
    config = require_broker_config(registry)
    nodes = registry_nodes(registry)
    controller = next((node for node in nodes if node["role"] == "controller"), nodes[0])
    rollout = find_rollout(controller["session_id"])
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
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

        # HEAD 采集覆盖全部 active children；阻塞 wait 优先覆盖 runnable
        # watch-set，空集合时回退到原来的全 active poll。
        active_children = [
            node for node in nodes
            if node["role"] != "controller" and node.get("active", True)
        ]
        poll_targets = runnable_watch_nodes(args.coordination_id, active_children) or active_children
        reason, actual_ids = validate_call(call["arguments"], [node["session_id"] for node in poll_targets])
        if reason:
            state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
            state["offset"] = new_offset
            save_state(args.coordination_id, state)
            print(f"ROUND INVALID: poll snippet altered ({reason})")
            return 1

        payload = extract_projection(output["output"])
        expected_poll_ids = {node["session_id"] for node in poll_targets}
        reason = validate_projection(payload, len(actual_ids), expected_poll_ids)
        if reason:
            state["invalid_rounds"] = int(state.get("invalid_rounds") or 0) + 1
            state["offset"] = new_offset
            save_state(args.coordination_id, state)
            if reason.startswith("poll id not in registry"):
                print(f"ROUND INVALID: {reason}")
            elif reason.startswith("duplicate poll id"):
                print(f"ROUND INVALID: {reason}")
            else:
                print(f"ROUND INVALID: poll snippet altered ({reason})")
            return 1

        update_compaction_observers(state, nodes)
        update_budget_states(state, registry, config)
        latest_poll, latest_report = latest_progress_parts(args.coordination_id)
        poll_seq = next_seq(state, "next_poll_seq")
        rows, classification = classify_and_rows(
            payload,
            active_children,
            args.round,
            poll_seq,
            latest_progress(args.coordination_id),
            profile=config["profile"],
        )
        ledger_seq = next_ledger_seq(args.coordination_id, state)
        for row in rows:
            row["ledger_seq"] = ledger_seq
        classification["watch_nodes"] = [node["name"] for node in poll_targets]
        classification["never_reported"] = sorted(
            node["name"] for node in active_children if node["name"] not in latest_report
        )
        for row in rows:
            append_jsonl(jsonl_path(args.coordination_id, "progress.jsonl"), row)
        if classification["head_changed"]:
            kinds = classification.get("advance_kinds") or {}
            has_code = any(kind != "docs" for kind in kinds.values())
            docs_count = sum(1 for kind in kinds.values() if kind == "docs")
            if has_code:
                state["dispatches_since_progress"] = 0
                state["docs_only_advances"] = 0
            elif docs_count:
                state["docs_only_advances"] = int(state.get("docs_only_advances") or 0) + docs_count
        state["offset"] = new_offset
        save_state(args.coordination_id, state)
        print(
            format_summary(
                args.round,
                True,
                new_offset,
                classification,
                args.coordination_id,
                registry,
            )
        )
        return 0

def cmd_route(args) -> int:
    path = registry_path(args.coordination_id)
    try:
        original_bytes = path.read_bytes()
        registry = json.loads(original_bytes.decode("utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"registry not found: {path}") from exc
    except (OSError, UnicodeError) as exc:
        raise LedgerError(f"registry unreadable: {path} ({exc})") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"registry is not valid JSON: {path} ({exc})") from exc
    if not isinstance(registry, dict):
        raise LedgerError(f"registry root must be an object: {path}")
    require_broker_config(registry)

    target = route_entry_by_name(registry, args.node)
    node = target["node"]
    old_session = node.get("current_session_id")
    if not isinstance(old_session, str) or not old_session:
        raise UsageError(f"node {args.node} has no current_session_id")
    if args.expect_current is not None and args.expect_current != old_session:
        raise UsageError(
            f"current session mismatch for {args.node}: "
            f"registry={old_session} expected={args.expect_current}"
        )
    new_session = args.new_session
    if not new_session.strip():
        raise UsageError("--new-session must be non-empty")
    if any(entry["node"].get("current_session_id") == new_session for entry in route_registry_entries(registry)):
        raise UsageError(f"new session is already current: {new_session}")

    previous = node.get("previous_session_ids")
    if previous is None:
        previous = []
    if not isinstance(previous, list):
        raise UsageError(f"node {args.node} previous_session_ids must be a list")

    masked_before = route_masked_serialization(registry, target)
    if old_session not in previous:
        previous.append(old_session)
    node["previous_session_ids"] = previous
    node["current_session_id"] = new_session
    node["updated_at"] = now_local()

    try:
        replace_file_bytes(path, route_registry_bytes(registry, original_bytes))
        reread_bytes = path.read_bytes()
        reread = json.loads(reread_bytes.decode("utf-8"))
        if not isinstance(reread, dict):
            raise ValueError("registry root is no longer an object")
        reread_target = route_entry_by_label(reread, target["label"])
        if not reread_target or reread_target["node"].get("current_session_id") != new_session:
            raise ValueError("target current_session_id verification failed")
        if route_masked_serialization(reread, reread_target) != masked_before:
            raise ValueError("non-target registry content changed")
    except Exception as exc:
        try:
            replace_file_bytes(path, original_bytes)
        except OSError as restore_exc:
            raise LedgerError(
                f"route verification failed: {exc}; registry restore failed: {restore_exc}"
            ) from exc
        raise LedgerError(f"route verification failed: {exc}") from exc

    print(f"ROUTED {args.node} {old_session} -> {new_session}")
    return 0

def validate_report_source(coordination_id: str, node_name: str, source_session: str, head: str, registry: dict) -> dict:
    node = registry_node_by_name(registry, node_name)
    if not node:
        raise UsageError(f"unknown node: {node_name}")
    if node["role"] == "controller":
        raise UsageError("H1 source must be a child node")
    if not node.get("active", True):
        raise UsageError(f"inactive node cannot submit H1: {node_name}")
    if source_session != node["session_id"]:
        raise UsageError(
            f"H1 source session mismatch for {node_name}: "
            f"registry={node['session_id']} source={source_session}"
        )
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head or ""):
        raise UsageError("H1 head must be a full 40-character git SHA")

    baseline = latest_progress(coordination_id).get(node_name, {}).get("head")
    if baseline and baseline != head and not git_is_ancestor(node.get("worktree"), baseline, head):
        raise UsageError(
            f"H1 head is not a descendant of latest ledger HEAD for {node_name}: "
            f"baseline={baseline} source={head}"
        )
    current_head = git_head(node.get("worktree"))
    if not current_head:
        raise UsageError(f"H1 worktree HEAD unavailable for {node_name}")
    if current_head != head and not git_is_ancestor(node.get("worktree"), head, current_head):
        raise UsageError(
            f"H1 head is not on current worktree history for {node_name}: "
            f"source={head} worktree={current_head}"
        )
    return node

def cmd_report(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        if args.state not in STATE_VALUES:
            raise UsageError(f"invalid state {args.state}; expected one of {', '.join(sorted(STATE_VALUES))}")
        waiting_on = args.waiting_on or []
        if args.state == "awaiting_seam":
            valid_seams = [
                item for item in waiting_on
                if isinstance(item, str) and item.startswith("seam:") and item.split(":", 1)[1]
            ]
            if not valid_seams:
                raise UsageError("state awaiting_seam requires --waiting-on seam:<id>")

        registry = load_registry(args.coordination_id)
        config = require_broker_config(registry)
        if config["profile"] == "solo" and args.state == "awaiting_seam":
            raise UsageError("solo profile does not support awaiting_seam")
        node = registry_node_by_name(registry, args.node)
        if not node:
            raise UsageError(f"unknown node: {args.node}")
        if args.registry and node["role"] != "controller" and not args.source_session:
            raise UsageError("explicit --registry report requires --source-session")

        # head 缺省时自己从 registry 的 worktree 读，不要依赖子线记得传 --head。
        # 依据 design-notes §2.1：报告没带 head 会被判成 stale，其 waiting_on 就不计入
        # seams_unowned——那样读数 5 会不管实际情况一律接近 0。head 是有客观来源的事实，
        # 不该退回账本纪律。
        head = args.head
        head_source = "arg"
        if not head:
            head = git_head(node.get("worktree"))
            head_source = "worktree" if head else "unavailable"

        if args.source_session:
            node = validate_report_source(args.coordination_id, args.node, args.source_session, head, registry)

        row = {
            "ts": now_local(),
            "src": "report",
            "round": args.round,
            "node": args.node,
            "head": head,
            "head_source": head_source,
            "state": args.state,
            "waiting_on": waiting_on,
            "last_report_ts": now_local(),
            "note": args.note or "",
        }
        if args.source_session:
            row["source_session_id"] = args.source_session
            row["source_registry"] = str(registry_path(args.coordination_id).resolve())
        state = load_state(args.coordination_id)
        row["ledger_seq"] = next_ledger_seq(args.coordination_id, state)
        append_jsonl(jsonl_path(args.coordination_id, "progress.jsonl"), row)
        save_state(args.coordination_id, state)
        suffix = ""
        if args.state in {"working", "ready_for_assignment", "done"} and waiting_on:
            suffix = " (note: waiting_on is ignored for working/ready_for_assignment/done state summaries)"
        if head_source == "unavailable":
            suffix += " (warning: head unavailable, report will be treated as stale once HEAD advances)"
        print(f"reported {args.node} state={args.state} head={head or 'none'}({head_source}){suffix}")
        return 0

def cmd_seam(args) -> int:
    ensure_runtime(args.coordination_id)
    seam_id = canonical_seam_id(args.seam_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        config = require_broker_config(registry)
        if config["profile"] == "solo":
            raise UsageError("solo profile does not support seams")
        known_nodes = {node["name"] for node in registry_nodes(registry)}
        if args.producer not in known_nodes:
            raise UsageError(f"unknown producer node: {args.producer}")
        for consumer in args.consumers or []:
            if consumer not in known_nodes:
                raise UsageError(f"unknown consumer node: {consumer}")
        status = "delivered" if args.deliver else "assigned"
        state = load_state(args.coordination_id)
        ledger_seq = next_ledger_seq(args.coordination_id, state)
        append_jsonl(
            jsonl_path(args.coordination_id, "seams.jsonl"),
            {
                "ts": now_local(),
                "ledger_seq": ledger_seq,
                "seam_id": seam_id,
                "producer": args.producer,
                "consumers": args.consumers or [],
                "status": status,
                "artifact": args.deliver,
            },
        )
        save_state(args.coordination_id, state)
        print(f"seam {seam_id} status={status}")
        return 0

def cmd_decide(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        require_broker_config(load_registry(args.coordination_id))
        if args.raise_id:
            decision_instance_id = str(uuid.uuid4())
            state = load_state(args.coordination_id)
            ledger_seq = next_ledger_seq(args.coordination_id, state)
            append_jsonl(
                jsonl_path(args.coordination_id, "decisions.jsonl"),
                {
                    "ts": now_local(),
                    "ledger_seq": ledger_seq,
                    "decision_id": args.raise_id,
                    "decision_instance_id": decision_instance_id,
                    "raised_by": args.by,
                    "blocks": args.blocks or [],
                    "question": args.question,
                    "status": "pending",
                    "answer": None,
                },
            )
            save_state(args.coordination_id, state)
            print(f"decision {args.raise_id} status=pending instance={decision_instance_id}")
            return 0
        if args.answer:
            pending = {
                row.get("decision_id"): row
                for row in pending_decisions(args.coordination_id)
                if row.get("decision_id")
            }
            decision = pending.get(args.answer)
            if decision is None:
                raise UsageError(f"decision is not pending: {args.answer}")
            state = load_state(args.coordination_id)
            ledger_seq = next_ledger_seq(args.coordination_id, state)
            row = {
                "ts": now_local(),
                "ledger_seq": ledger_seq,
                "decision_id": args.answer,
                "raised_by": None,
                "blocks": [],
                "question": None,
                "status": "answered",
                "answer": args.text,
            }
            instance = decision.get("decision_instance_id")
            if isinstance(instance, str) and instance:
                row["decision_instance_id"] = instance
            append_jsonl(jsonl_path(args.coordination_id, "decisions.jsonl"), row)
            save_state(args.coordination_id, state)
            print(f"decision {args.answer} status=answered")
            return 0
        raise UsageError("decide requires --raise or --answer")

def latest_handoff_action(coordination_id: str, node_name: str, session_id: str) -> dict | None:
    for row in reversed(read_jsonl(jsonl_path(coordination_id, "acts.jsonl"))):
        if (
            row.get("kind") == "handoff"
            and row.get("node") == node_name
            and row.get("node_session_id") == session_id
        ):
            return row
    return None

def cmd_handoff_action(args, registry: dict, config: dict) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        config = require_broker_config(registry)
        controller = registry.get("controller")
        controller_session = controller.get("current_session_id") if isinstance(controller, dict) else None
        if not args.source_session:
            raise UsageError("act --handoff requires --source-session")
        if args.source_session != controller_session:
            raise UsageError("act --handoff source session must match controller current_session_id")
        if not args.node:
            raise UsageError("act --handoff requires --node")
        node = registry_node_by_name(registry, args.node)
        if not node:
            raise UsageError(f"unknown node: {args.node}")
        if node["role"] == "child" and not node.get("active", True):
            raise UsageError(f"inactive node cannot be handed off: {args.node}")
        node_session = node.get("session_id")
        if not node_session:
            raise UsageError(f"node {args.node} has no current session")
        reason = (args.reason or "").strip()
        if not reason:
            raise UsageError("act --handoff requires --reason")

        state = load_state(args.coordination_id)
        update_compaction_observers(state, registry_nodes(registry))
        update_budget_states(state, registry, config)
        current_budget = (state.get("budget_states") or {}).get(node_session)
        if not isinstance(current_budget, dict) or current_budget.get("stage") != "handoff_due":
            raise UsageError(f"node {args.node} is not handoff_due; run sync first")
        existing = latest_handoff_action(args.coordination_id, args.node, node_session)
        if existing:
            print(f"handoff already requested node={args.node} seq={existing.get('seq')}")
            return 0

        seq = next_seq(state, "next_act_seq")
        ledger_seq = next_ledger_seq(args.coordination_id, state)
        row = {
            "ts": now_local(),
            "seq": seq,
            "ledger_seq": ledger_seq,
            "kind": "handoff",
            "node": args.node,
            "node_session_id": node_session,
            "source_session": args.source_session,
            "seam_id": None,
            "producer": None,
            "deliverable": None,
            "decision_id": None,
            "reason": reason,
            "budget_stage": "handoff_due",
            "handoff_requested": True,
        }
        append_jsonl(jsonl_path(args.coordination_id, "acts.jsonl"), row)
        save_state(args.coordination_id, state)
        print(f"act handoff seq={seq} node={args.node}")
        return 0

def cmd_act(args) -> int:
    registry = load_registry(args.coordination_id)
    config = require_broker_config(registry)
    if args.handoff:
        return cmd_handoff_action(args, registry, config)
    if args.dispatch and config["profile"] == "solo":
        raise UsageError("solo profile does not support act --dispatch")
    if args.halt:
        controller = registry.get("controller")
        controller_session = controller.get("current_session_id") if isinstance(controller, dict) else None
        if not args.source_session:
            raise UsageError("act --halt requires --source-session")
        if args.source_session != controller_session:
            raise UsageError("act --halt source session must match controller current_session_id")
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        config = require_broker_config(registry)
        if args.dispatch and config["profile"] == "solo":
            raise UsageError("solo profile does not support act --dispatch")
        state = load_state(args.coordination_id)
        seq = next_seq(state, "next_act_seq")
        ledger_seq = next_ledger_seq(args.coordination_id, state)
        row = {"ts": now_local(), "seq": seq, "ledger_seq": ledger_seq}
        if args.dispatch:
            seam_id = canonical_seam_id(args.seam_id) if args.seam_id else None
            missing = [
                name for name, value in (
                    ("--seam-id", seam_id),
                    ("--producer", args.producer),
                    ("--deliverable", args.deliverable),
                )
                if not value
            ]
            if missing:
                raise UsageError(f"act --dispatch requires {', '.join(missing)}")
            known_nodes = {node["name"] for node in registry_nodes(registry)}
            if args.producer not in known_nodes:
                raise UsageError(f"unknown producer node: {args.producer}")
            current_producer = seam_producers(args.coordination_id).get(seam_id)
            if current_producer and current_producer != args.producer:
                print(
                    f"producer changed for seam {seam_id}: "
                    f"{current_producer} -> {args.producer}; appending new assignment"
                )
            row.update(
                {
                    "kind": "dispatch",
                    "seam_id": seam_id,
                    "producer": args.producer,
                    "deliverable": args.deliverable,
                    "decision_id": None,
                }
            )
        elif args.escalate:
            if not args.decision_id:
                raise UsageError("act --escalate requires --decision-id")
            pending = next(
                (
                    decision for decision in pending_decisions(args.coordination_id)
                    if decision.get("decision_id") == args.decision_id
                ),
                None,
            )
            if pending is None:
                raise UsageError(f"decision is not pending: {args.decision_id}")
            row.update(
                {
                    "kind": "escalate",
                    "seam_id": None,
                    "producer": None,
                    "deliverable": None,
                    "decision_id": args.decision_id,
                }
            )
            instance = pending.get("decision_instance_id")
            if isinstance(instance, str) and instance:
                row["decision_instance_id"] = instance
        elif args.halt:
            reason = (args.reason or "").strip()
            if not reason:
                raise UsageError("act --halt requires --reason")
            row.update(
                {
                    "kind": "halt",
                    "seam_id": None,
                    "producer": None,
                    "deliverable": None,
                    "decision_id": None,
                    "reason": reason,
                    "pending_decision_ids": decision_ids(pending_decisions(args.coordination_id)),
                    "halt_poll_seq": int(state.get("next_poll_seq") or 0),
                }
            )
        else:
            raise UsageError("act requires --dispatch, --escalate, --halt, or --handoff")
        append_jsonl(jsonl_path(args.coordination_id, "acts.jsonl"), row)
        if args.dispatch:
            append_jsonl(
                jsonl_path(args.coordination_id, "seams.jsonl"),
                {
                    "ts": now_local(),
                    "ledger_seq": ledger_seq,
                    "seam_id": row["seam_id"],
                    "producer": args.producer,
                    "consumers": [],
                    "status": "assigned",
                    "artifact": None,
                },
            )
        save_state(args.coordination_id, state)
        print(f"act {row['kind']} seq={seq}")
        return 0

def format_status(
    coordination_id: str,
    registry: dict,
    *,
    integrity_failed: bool = False,
) -> str:
    latest = latest_progress(coordination_id)
    registry_by_name = {node["name"]: node for node in registry_nodes(registry)}
    registry_names = sorted(node["name"] for node in registry_by_name.values() if node["role"] != "controller")
    pending = pending_decisions(coordination_id)
    unowned, malformed, stale_waiting_on = seams_waiting_counts(coordination_id)
    act = latest_act(coordination_id)
    halt = halted_act(coordination_id)
    state = load_state(coordination_id)
    config, broker_issues = validate_broker_config(registry)
    observers = state.get("compaction_observers")
    if not isinstance(observers, dict):
        observers = {}
    controller_node = next(
        (node for node in registry_by_name.values() if node["role"] == "controller"),
        None,
    )
    controller_observer = observers.get(controller_node.get("session_id")) if controller_node else None
    controller_compactions = (
        controller_observer.get("observed_count") if isinstance(controller_observer, dict) else None
    )
    controller_compactions_text = (
        str(controller_compactions)
        if type(controller_compactions) is int and controller_compactions >= 0
        else "?"
    )
    node_lines = []
    for name in sorted(set(registry_names) | set(latest)):
        row = latest.get(name, {})
        registry_node = registry_by_name.get(name)
        lifecycle = "active" if registry_node and registry_node.get("active", True) else "retired"
        if not registry_node:
            lifecycle = "unregistered"
        observer = observers.get(registry_node.get("session_id")) if registry_node else None
        compactions = observer.get("observed_count") if isinstance(observer, dict) else None
        compactions_text = str(compactions) if type(compactions) is int and compactions >= 0 else "?"
        node_lines.append(
            f"  {name}: lifecycle={lifecycle} state={row.get('state') or '-'} head={row.get('head') or '-'} "
            f"turn={row.get('turn') or '-'} last_report_ts={row.get('last_report_ts') or '-'} "
            f"compaction_count={compactions_text}"
        )
    pending_text = ", ".join(row.get("decision_id") for row in pending if row.get("decision_id")) or "-"
    act_text = "-"
    if act:
        act_text = f"seq={act.get('seq')} kind={act.get('kind')}"
        if act.get("kind") == "dispatch":
            act_text += f" seam={act.get('seam_id')} producer={act.get('producer')}"
        elif act.get("kind") == "halt":
            act_text += f" reason={act.get('reason') or '-'}"
        elif act.get("decision_id"):
            act_text += f" decision={act.get('decision_id')}"
    header_lines = ["STATUS"]
    if integrity_failed:
        header_lines.append("ledger_integrity: FAILED (partial rows are diagnostic only; current state is not authoritative)")
    if halt:
        header_lines.extend(
            [
                "halted: yes",
                f"halt_ts: {halt.get('ts') or '-'}",
                f"halt_reason: {halt.get('reason') or '-'}",
                f"halt_pending_decisions: {format_id_list(halt.get('pending_decision_ids') or [])}",
            ]
        )
    runtime_root = runtime_dir(coordination_id)
    missing_runtime = []
    for name in PREFLIGHT_RUNTIME_FILES:
        if not (runtime_root / name).is_file():
            missing_runtime.append(name)
    if missing_runtime:
        runtime_line = (
            f"runtime_uninitialized: yes; runtime: missing ({', '.join(missing_runtime)}); "
            f"run init --registry {registry_path(coordination_id)}"
        )
    else:
        runtime_line = f"runtime_uninitialized: no; runtime: ready ({runtime_root})"
    return "\n".join(
        header_lines
        + [
            f"registry: {registry_path(coordination_id)}",
            runtime_line,
            (
                f"broker_profile: {config['profile']} handoff_at={config['budget']['handoff_at']}"
                if config
                else f"broker_config: INVALID {format_broker_config_issues(broker_issues)}"
            ),
            f"controller_compaction_count: {controller_compactions_text}",
            f"budget_stage:    {budget_stage_text(registry, state)}",
            f"handoff_required: {handoff_required_text(registry, state)}",
            "nodes:",
            *(node_lines or ["  -"]),
            f"pending_decisions: {pending_text}",
            f"seams_unowned:   {unowned}",
            f"stale_waiting_on: {stale_waiting_on}",
            f"malformed_waiting_on: {malformed}",
            f"stale_reports:   {', '.join(sorted(stale_report_nodes(coordination_id))) or '-'}",
            f"stall_streak:    {stall_streak(coordination_id)}/{STALL_LIMIT}",
            f"dispatches_since_progress: {load_state(coordination_id).get('dispatches_since_progress', 0)}",
            f"docs_only_advances: {load_state(coordination_id).get('docs_only_advances', 0)}",
            f"last_act:        {act_text}",
            f"corrupt_ledger_lines: {corrupt_ledger_lines(coordination_id)}",
        ]
    )

def cmd_status(args, integrity_issues: list[tuple[str, int, str]] | None = None) -> int:
    registry = load_registry(args.coordination_id)
    if integrity_issues is None:
        integrity_issues = ledger_integrity_issues(args.coordination_id)
    if integrity_issues:
        print_integrity_failure(integrity_issues)
    print(format_status(args.coordination_id, registry, integrity_failed=bool(integrity_issues)))
    broker_issues = broker_config_issues(registry)
    if integrity_issues:
        return LEDGER_INTEGRITY_FAILED
    return 5 if broker_issues else 0

def cmd_heartbeat(args) -> int:
    """Controller 读取 thread 后，用 concrete progress 重置 HEAD 停滞计数。"""
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        registry = load_registry(args.coordination_id)
        require_broker_config(registry)
        children = {
            node["name"]
            for node in registry_nodes(registry)
            if node["role"] != "controller" and node.get("active", True)
        }
        if args.node not in children:
            raise UsageError(f"unknown child node: {args.node}")
        streak = stall_streak(args.coordination_id)
        minimum = max(1, STALL_LIMIT - HEARTBEAT_LEAD_ROUNDS)
        if not minimum <= streak < STALL_LIMIT:
            raise UsageError(
                f"heartbeat requires {minimum}/{STALL_LIMIT} <= stall_streak < "
                f"{STALL_LIMIT}/{STALL_LIMIT}; current={streak}/{STALL_LIMIT}"
            )
        evidence = args.evidence.strip()
        if not evidence:
            raise UsageError("heartbeat requires non-empty --evidence")
        state = load_state(args.coordination_id)
        reset_seq = int(state.get("next_poll_seq") or 0)
        if reset_seq < 1:
            raise UsageError("heartbeat requires at least one valid sync")
        state["stall_reset_seq"] = reset_seq
        save_state(args.coordination_id, state)
        print(
            f"heartbeat reset node={args.node} stall_streak={streak}/{STALL_LIMIT} "
            f"reset_seq={reset_seq}"
        )
        return 0

def cmd_stall_check(args) -> int:
    ensure_runtime(args.coordination_id)
    with coordination_write_lock(args.coordination_id):
        assert_ledger_integrity(args.coordination_id)
        require_broker_config(load_registry(args.coordination_id))
        halt = halted_act(args.coordination_id)
        if halt:
            pending = format_id_list(halt.get("pending_decision_ids") or [])
            print(f"HALTED (ts={halt.get('ts') or '-'}, reason={halt.get('reason') or '-'}, pending={pending})")
            return 4
        state = load_state(args.coordination_id)
        dispatches = int(state.get("dispatches_since_progress") or 0)
        answered_line = f"last_must_act_answered: {'yes' if last_must_act_answered(args.coordination_id) else 'no'}"
        unreported, already_escalated = pending_escalation_groups(args.coordination_id)
        if unreported:
            items = format_id_list(decision_ids(unreported))
            lines = [f"MUST_ESCALATE pending_decisions: {items} dispatches_since_progress={dispatches}"]
            if already_escalated:
                lines.append(f"already_escalated: {format_id_list(decision_ids(already_escalated))}")
            lines.append(answered_line)
            print("\n".join(lines))
            return 3
        pending_suffix = ""
        if already_escalated:
            pending_suffix = f" pending_escalated: {format_id_list(decision_ids(already_escalated))}"
        streak = stall_streak(args.coordination_id)
        if streak >= STALL_LIMIT:
            state["last_must_act_seq"] = int(state.get("next_act_seq") or 0)
            save_state(args.coordination_id, state)
            print(
                f"MUST_ACT stall_streak={streak}/{STALL_LIMIT} "
                f"dispatches_since_progress={dispatches}{pending_suffix}\n{answered_line}"
            )
            return 2
        if streak >= max(1, STALL_LIMIT - HEARTBEAT_LEAD_ROUNDS):
            print(
                f"CHECK_HEARTBEAT stall_streak={streak}/{STALL_LIMIT} "
                f"dispatches_since_progress={dispatches} read_thread_required=yes{pending_suffix}\n{answered_line}"
            )
            return 0
        print(f"OK stall_streak={streak}/{STALL_LIMIT} dispatches_since_progress={dispatches}{pending_suffix}\n{answered_line}")
        return 0

__all__ = [name for name in globals() if not name.startswith("_")]
