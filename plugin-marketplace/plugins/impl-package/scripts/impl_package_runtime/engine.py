"""Ticket-first Impl-Package state runtime (format 3.6, Journey acceptance).

The runtime has one state axis: Tickets.  A package whose state is not
formatVersion 3.6 is rejected.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import secrets
import subprocess
import sys
import tempfile
import uuid
import zipfile
from contextvars import ContextVar
from dataclasses import dataclass
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from situation import (
    dispatch_admission,
    ValidationResult,
    FACT_KEYS,
    REVIEW_PHASES,
    REVIEW_PHASE_VALUES,
    REVIEW_TRACKS,
    REVIEW_TRACK_VALUES,
    describe_unknown_fact_keys,
    carried_forward_error,
    evidence_record_valid,
    evidence_revision_coverage,
    live_package_reference_fact,
    terminal_coverage_fact,
)

#<<FACADE>>
from .state_core import (
    STATE_PATH,
    ATTEMPT_ARCHIVE_PATH,
    PROGRESS_PATH,
    EXECUTION_PATH,
    ACTIVE_TRAIL_NAME,
    TRAIL_ARCHIVE_RE,
    GATE_PATH,
    FORMAT_VERSION,
    TICKET_STATES,
    TERMINAL_VERDICTS,
    VERDICTS,
    TIMINGS,
    CONCLUSIONS,
    DISPOSITIONS,
    TRAIL_APPEND_KINDS,
    RETIRED_DISPATCH_FIELDS,
    TRAIL_COMMON_FIELDS,
    FIXED_COMMIT_RE,
    LEASE_ID_RE,
    LEASE_FILE_RE,
    ATTEMPT_RE,
    COMPOSITION_RE,
    DECISION_RE,
    SPEC_RE,
    PLAN_RE,
    PREDECESSORS_RE,
    ACCEPTANCE_JOURNEY_RE,
    RELEASE_ORDER_RE,
    TICKET_ID_RE,
    PUBLICATION_RE,
    BATCH_ESTIMATE_RE,
    ARRIVAL_PATH_RE,
    DEPENDENCY_HEADING_RE,
    ARRIVAL_SEGMENT_RE,
    ER_ENTRY_RE,
    COMMIT_RE,
    PACKAGE_ID_RE,
    ATTEMPT_ID_RE,
    StateError,
    Lifecycle,
    _GitResult,
    _git_query_cache,
    git_query_scope,
    _cacheable_git_query,
    _hash_object_paths,
    _run_git_result,
    _invalidate_working_tree_hash,
    _run_git,
    _repo_root,
    _read,
    _load_json,
    _write_text,
    _write_json,
    _utc_timestamp,
    _validate_iso_timestamp,
    _repo_relative,
    _validate_commit,
    _is_ancestor,
    _state_format_version,
    require_current_format,
)
from .attempt_store import (
    _attempt_archive_path,
    _ticket_snapshot,
    _write_attempt_archive,
    _trail_path,
    _trail_identity,
    _trail_append_lock,
    _trail_next_seq,
    _append_trail,
    _best_effort_trail,
    _best_effort_result,
    _next_trail_archive,
    _rotate_trail,
    _best_effort_trail_rotation,
    _valid_successor,
    _gate_info,
    _lifecycle,
    _approve_ticket,
    _execution_record_path,
    _new_execution_record,
    _ensure_execution_record,
    _entry_field,
    _parse_execution_record,
    _set_execution_record_status,
    _trail_text_field,
    _active_trail_rows,
    _same_event,
)
from .spec_journey import (
    _markdown_section,
    _table_cells,
    _markdown_table,
    _chapter_headings,
    _chapter_references,
    _resolve_chapter_reference,
    _chapter_label,
    _spec_coverage_findings,
    _journey_spec_text,
    _journey_spec,
    _frozen_journey_spec,
    _journey_expected_surface,
    validate_spec_document,
    _coverage_list,
    _ticket_coverage,
    _journey_coverage_errors,
    _validate_journey_coverage,
)
from .plan_tickets import (
    _field,
    _predecessors_from_plan,
    _normalize_state_predecessors,
    _package_relative,
    HARNESS_PLAN_FORMATS,
    _harness_from_plan,
    _validate_first_visible_step,
    _plan_info,
    _arrival_paths,
    _ticket_documents,
    _batch_estimate_absent_findings,
    _append_ticket_document,
    _ticket_dependencies,
    _reject_cycles,
    _git_grep_symbol,
    PLAN_GATE_RE,
    CONTRACT_DOC_NAMES,
    _contains_ticket_id,
    _contract_doc_name_findings,
    _plan_prose_gate_findings,
    _arrival_path_absent_findings,
    _arrival_findings,
    _working_tree_blobs,
    _contract_baseline,
    _pending_amendments,
    _contract_amendment_findings,
    _post_gate_pending_findings,
    command_check_spec,
)
from .journey_evidence import (
    _package_relative_artifact,
    _trace_action_method,
    _trace_action_description,
    _playwright_trace_actions,
    _validate_journey_surface_evidence,
    _validate_journey_evidence_index,
    _evidence_field_error,
    _normalize_journey_evidence,
)
from .acceptance import (
    _escape,
    _format_aliases,
    _v36_acceptance_status,
    _journey_reaches,
    _render_progress,
    _validate_projections,
)
from .validate_state import (
    _validate_checkpoints,
    _attempt_history,
    ready_tickets,
    _ticket_released,
    _validate_acceptance_state,
    _validate_state,
    _refresh_projections,
    _public,
)
from .cmd_evidence import (
    _assert_mutable,
    _v36_record_valid,
    _ticket_owned_evidence_keys,
    _v36_ticket_satisfy_gaps,
    _validate_first_step_object_is_new,
    _validate_journey_step_order,
    command_evidence_add,
    command_evidence_invalidate,
    command_evidence_carry_forward,
    command_set_state,
    _add_judgment,
    command_er_add,
)
from .cmd_package import (
    command_archive_attempt,
    command_init,
    command_validate,
    command_refresh_progress,
    AMENDMENT_CONTRACT_FILES,
    _amendment_post_gate,
    _post_gate_spec_drift,
    command_amendment_add,
    command_amendment_confirm,
    _amendment_transition,
    command_amendment_supersede,
    command_amendment_withdraw,
    command_sync_predecessors,
)
from .cmd_trail import (
    validate_dispatch_receipt,
    _validate_resource_keys,
    _lease_directory,
    _lease_record_path,
    _read_lease_records,
    command_lease_acquire,
    command_lease_release,
    _validate_dispatch_lease,
    _validate_code_delta,
    _validate_review_pending,
    _validate_review_dispatch_fields,
    _merge_trail_named_fields,
    _validate_trail_event,
    _current_validation_result,
    _validate_actual_dispatch,
    _validate_worker_return,
    _validate_review_pending_against_return,
    command_trail_append,
)
#<<END>>


def command_checkpoint(
    package: Path,
    subject: str,
    next_action: str,
    blocker: str | None,
    evidence: list[str],
    handoff: bool = False,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if subject != "attempt" and (not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid checkpoint subject: {subject}")
    repo = _repo_root(package)
    state["activeCheckpoints"][subject] = {"next": next_action.strip(), "blocker": blocker.strip() if blocker else None, "evidence": [_repo_relative(repo, item, "checkpoint evidence") for item in evidence]}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    _best_effort_trail(
        package,
        summary["attempt"],
        {
            "subject": subject,
            "kind": "checkpoint",
            "checkpoint": True,
            **state["activeCheckpoints"][subject],
        },
    )
    if handoff:
        _best_effort_trail_rotation(package, summary["attempt"])
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": subject,
                "kind": "handoff",
                "checkpoint": True,
                **state["activeCheckpoints"][subject],
            },
        )
    return {"subject": subject, "checkpoint": state["activeCheckpoints"][subject], "idempotent": False}


def _update_history(state: dict[str, Any], attempt: str, lifecycle: str, gate: dict[str, Any] | None) -> None:
    for row in state["attemptHistory"]:
        if row["id"] == attempt:
            row["lifecycle"] = lifecycle
            row["gate"] = gate
            return


def _v36_gate_gaps(
    package: Path,
    state: dict[str, Any],
    summary: dict[str, Any],
    comparison_commit: str,
    durable: list[str],
    no_durable_reason: str | None,
) -> tuple[list[str], dict[str, Any], Any, Any]:
    lifecycle: Lifecycle = summary["_lifecycle"]
    status = _v36_acceptance_status(package, state, summary, comparison_commit, attempt_active=not lifecycle.frozen)
    gaps: list[str] = []
    gaps.extend(
        f"合同文件 {row['path']} 相对 contractBaseline 有变化但未登记 Amendment；"
        "合同已变更，需登记 Amendment 并经 Owner 确认"
        for row in status["unregisteredAmendments"]
    )
    for journey in status["journeys"]:
        if journey["reach"] != journey["total"]:
            hint = "；API 预演已走通，仍需页面/文件/记录证据" if journey["rehearsalReach"] == journey["total"] else ""
            gaps.append(
                f"Journey {journey['id']} 尚未在同一 run 走通全部页面/文件/记录步骤 "
                f"（有效步骤走通 {journey['reach']}/{journey['total']}，API 预演 {journey['rehearsalReach']}/{journey['total']}）{hint}"
            )
    for suite in status["suites"]:
        if not suite["valid"]:
            gaps.append(f"Required Suite {suite['id']} 缺少当前有效的 supporting 记录")
    gaps.extend(
        f"Evidence {key} 的 supporting 记录待复验；若变更不影响运行时，用 "
        f"evidence carry-forward --key {key} --to <HEAD> --reason <理由> --judged-by <人>"
        for key in status["staleEvidence"]
    )
    for ticket, row in state["tickets"].items():
        if row["state"] != "SATISFIED":
            gaps.append(f"Required Ticket {ticket} 状态为 {row['state']}，需要 SATISFIED")
    for ticket, edges in summary["_ticketDependencies"].items():
        for kind, dependency in edges:
            if not _ticket_released(state["tickets"], dependency):
                gaps.append(f"Ticket {ticket} 的 {kind} 入边 {dependency} 未释放")
    if status["pendingAmendments"]:
        gaps.extend(f"合同修订 {row['id']} 待 Owner 确认：{row['summary']}" for row in status["pendingAmendments"])
    if status["releaseRequired"] and not status["releaseValid"]:
        gaps.append("Plan 要求发布顺序，但缺少当前有效的 release 记录")
    coverage = terminal_coverage_fact(package)
    if not coverage.known or coverage.value is not True:
        label = "unknown" if not coverage.known else "incomplete"
        gaps.append(f"terminal review coverage {label}：{coverage.reason or '未通过'}")
    live_references = live_package_reference_fact(package)
    if not live_references.known:
        gaps.append(f"live package reference 无法判定：{live_references.reason or 'unknown'}")
    elif live_references.value is True:
        gaps.append(
            (live_references.reason or "package 含活体 package 引用")
            + "；先将每条引用通过 /impl-package:backfill-stable-docs 吸收进 stable docs，再把当前 package 改为引用 stable docs"
        )
    if not durable and not (no_durable_reason and no_durable_reason.strip()):
        gaps.append("terminal Gate 需要 Durable Delta 或 --no-durable-delta-reason")
    return gaps, status, coverage, live_references


def _owner_summary(
    status: dict[str, Any],
    comparison_commit: str,
    verdict: str,
    reason: str,
) -> list[str]:
    lines = ["## Owner Summary\n"]
    for journey in status["journeys"]:
        lines.append(
            f"- {journey['id']} {journey['title']}：有效步骤走通 {journey['reach']}/{journey['total']} · "
            f"API 预演 {journey['rehearsalReach']}/{journey['total']}\n"
        )
    if status.get("walkingSkeletonOverdue"):
        first_visible = status["firstVisibleStep"]
        lines.append(
            f"- walking skeleton：{first_visible['step']} 应在 {first_visible['ticket']} 合入后走通，尚未走通\n"
        )
    valid_suites = sum(1 for row in status["suites"] if row["valid"])
    lines.append(f"- 套件：{valid_suites}/{len(status['suites'])} 通过\n")
    for row in status.get("carriedForwardEvidence", []):
        lines.append(
            f"- 沿用证据：{row['key']} {row['from'][:7]}→{row['to'][:7]}，{row['reason']}（{row['judgedBy']}判断）\n"
        )
    pending = status["pendingAmendments"]
    unregistered = status["unregisteredAmendments"]
    if pending:
        descriptions = "；".join(f"{row['id']} {row['summary']}" for row in pending)
        lines.append(f"- 合同修订：{len(pending)} 条待 Owner 确认（{descriptions}）\n")
    elif unregistered:
        files = "、".join(row["path"] for row in unregistered)
        lines.append(f"- 合同修订：存在漏登文件 {files}\n")
    else:
        lines.append("- 合同修订：无待确认或漏登\n")
    if not status["releaseRequired"]:
        release = "未要求"
    else:
        release = "已记录" if status["releaseValid"] else "缺失"
    lines.append(f"- 发布顺序：{release}\n")
    lines.append(f"- 最终版本：{comparison_commit[:7]}\n")
    conclusion = reason.strip() or ("所有验收项已满足" if verdict == "pass" else "仍有验收缺口")
    lines.append(f"- 结论：{verdict} — {conclusion}\n")
    manual = [
        f"{item['stepId']}（{item['manualBy']}）"
        for journey in status["journeys"]
        for item in journey["manualWalkthroughs"]
    ]
    if manual:
        lines.append(f"- 走查：{'、'.join(manual)}\n")
    return lines


def _best_effort_metrics_path(package: Path, attempt: str) -> str | None:
    try:
        from .metrics import write_metrics

        path = write_metrics(package, attempt)
        return path.relative_to(package.resolve()).as_posix()
    except Exception as exc:  # metrics are observational; Gate remains authoritative
        print(f"warning: Gate committed but metrics report failed: {exc}", file=sys.stderr)
        return None


def command_gate(package: Path, verdict: str, commit: str, reason: str, evidence: list[str], durable: list[str], no_durable_reason: str | None, environment: str | None) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    repo = _repo_root(package)
    resolved = _validate_commit(repo, commit)
    lifecycle: Lifecycle = summary["_lifecycle"]
    if lifecycle.frozen:
        if lifecycle.gate and lifecycle.gate["verdict"] == verdict and lifecycle.gate["commit"] == resolved:
            _write_attempt_archive(package, summary["attempt"], state["tickets"])
            _best_effort_result(package, summary["attempt"], {
                "subject": f"attempt:{summary['attempt']}", "transition": "gate", "verdict": verdict,
                "commit": resolved, "outcome": verdict,
            })
            result = {"formatVersion": summary["formatVersion"], "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": True}
            if verdict == "pass":
                metrics_path = _best_effort_metrics_path(package, summary["attempt"])
                if metrics_path:
                    result["_metricsPath"] = metrics_path
            return result
        raise StateError(f"Attempt {summary['attempt']} is already frozen by terminal Gate {lifecycle.gate_verdict}")
    if verdict in TERMINAL_VERDICTS and resolved != _run_git(repo, "rev-parse", "HEAD"):
        raise StateError("terminal Gate comparison commit must equal current HEAD")
    if verdict in TERMINAL_VERDICTS and not durable and not (no_durable_reason and no_durable_reason.strip()) and verdict != "pass":
        raise StateError("terminal Gate requires --durable-delta or --no-durable-delta-reason")
    if verdict == "pass":
        gaps, v36_status, _coverage, _live_references = _v36_gate_gaps(
            package, state, summary, resolved, durable, no_durable_reason,
        )
        if gaps:
            raise StateError("pass Gate rejected: " + "; ".join(gaps))
    else:
        v36_status = _v36_acceptance_status(
            package, state, summary, resolved, attempt_active=not lifecycle.frozen,
        )
    normalized_evidence = [_repo_relative(repo, item, "gate evidence") for item in evidence]
    if verdict in TERMINAL_VERDICTS:
        state["activeCheckpoints"] = {}
    gate = {"verdict": verdict, "commit": resolved, "environment": environment}
    _update_history(state, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", gate)
    if verdict in TERMINAL_VERDICTS:
        _validate_state(
            package,
            state,
            projections=False,
            frozen_contract_commit=resolved,
        )
    lines = ["# Gate\n", f"- Verdict: {verdict}\n", f"- Attempt: {summary['attempt']}\n", f"- Comparison commit: {resolved}\n", f"- Reason: {reason.strip()}\n"]
    lines.append("\n")
    lines.extend(_owner_summary(v36_status, resolved, verdict, reason))
    lines.append("\n## Evidence\n")
    lines.extend(f"- {item}\n" for item in normalized_evidence) or lines.append("- none\n")
    lines.append("\n## Durable Deltas\n")
    lines.extend(f"- {item}\n" for item in durable) or lines.append(f"- Reason: {no_durable_reason or 'none'}\n")
    _write_text(package / GATE_PATH, "".join(lines))
    _set_execution_record_status(package, summary["attempt"], "frozen" if verdict in TERMINAL_VERDICTS else "active", verdict)
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    if verdict in TERMINAL_VERDICTS:
        _write_attempt_archive(package, summary["attempt"], state["tickets"])
    _best_effort_result(package, summary["attempt"], {
        "subject": f"attempt:{summary['attempt']}", "transition": "gate", "verdict": verdict,
        "commit": resolved, "outcome": verdict,
    })
    result = {"formatVersion": summary["formatVersion"], "verdict": verdict, "attempt": summary["attempt"], "commit": resolved, "idempotent": False}
    if verdict == "pass":
        metrics_path = _best_effort_metrics_path(package, summary["attempt"])
        if metrics_path:
            result["_metricsPath"] = metrics_path
    return result
