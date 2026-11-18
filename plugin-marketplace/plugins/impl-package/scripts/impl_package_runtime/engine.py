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
#<<END>>


def command_archive_attempt(package: Path, attempt: str, revision: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    history = next((row for row in summary["_history"] if row["id"] == attempt), None)
    if history is None or history["lifecycle"] != "frozen":
        raise StateError(f"Attempt {attempt} is not frozen in current history")
    repo = _repo_root(package)
    resolved = _validate_commit(repo, revision)
    state_path = (package / STATE_PATH).resolve().relative_to(repo).as_posix()
    try:
        historical = json.loads(_run_git(repo, "show", f"{resolved}:{state_path}"))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid historical state at {resolved}") from exc
    if not isinstance(historical, dict):
        raise StateError(f"historical state at {resolved} must be an object")
    historical_attempt = historical.get("attempt")
    if not isinstance(historical_attempt, dict) or historical_attempt.get("id") != attempt:
        raise StateError(f"historical state at {resolved} does not belong to Attempt {attempt}")
    tickets = _ticket_snapshot(historical.get("tickets"))
    document_ids = {document["id"] for document in _ticket_documents(package, attempt)}
    if set(tickets) != document_ids:
        raise StateError(f"historical Ticket state does not match Attempt {attempt} Ticket files")
    created = _write_attempt_archive(package, attempt, tickets)
    return {"attempt": attempt, "revision": resolved, "idempotent": not created}


def command_init(package: Path, attempt: str, plan: str) -> dict[str, Any]:
    if PACKAGE_ID_RE.fullmatch(package.name) is None:
        raise StateError("package directory must use an immutable date-prefixed ID")
    repo = _repo_root(package)
    # 先把 plan、Ticket、Journey 覆盖、First visible step 的缺项一次性收齐，避免逐条报错试探。
    problems: list[str] = []
    try:
        info = _plan_info(package, repo, plan)
    except StateError as exc:
        info = None
        problems.append(str(exc))
    if info is not None and info["attempt"] != attempt:
        raise StateError("--attempt does not match the plan Attempt ID")
    command_check_spec(package, _package_relative(repo, package / "spec.md"))
    ticket_problems: list[str] = []
    try:
        documents = _ticket_documents(package, attempt, ticket_problems)
    except StateError as exc:
        documents = []
        ticket_problems.append(str(exc))
    problems.extend(ticket_problems)
    if not ticket_problems:
        problems.extend(_journey_coverage_errors(_journey_spec(package), documents))
        if info is not None:
            try:
                _validate_first_visible_step(info["harness"], _journey_spec(package), documents)
            except StateError as exc:
                problems.append(str(exc))
    if problems:
        raise StateError(f"package init 发现 {len(problems)} 处需修正：\n- " + "\n- ".join(problems))
    path = package / STATE_PATH
    if path.exists():
        current = _load_json(path)
        current_summary = _validate_state(package, current, projections=False)
        if current_summary["attempt"] == attempt:
            for document in current_summary["_documents"]:
                _approve_ticket(document)
            _refresh_projections(package, current)
            return _public(_validate_state(package, current))
        if not current_summary["_lifecycle"].frozen:
            raise StateError("current Attempt is not terminal; refusing to replace state")
        _write_attempt_archive(package, current_summary["attempt"], current["tickets"])
        previous = current["attemptHistory"]
    else:
        previous = []
    dependencies = _ticket_dependencies(documents)
    del dependencies
    history = list(previous)
    history.append({"id": attempt, "plan": info["path"], "lifecycle": "active", "gate": None, "executionRecord": f"execution/{attempt}/execution-record.md"})
    state: dict[str, Any] = {"formatVersion": FORMAT_VERSION, "attempt": {"id": attempt, "plan": info["path"]}, "attemptHistory": history, "predecessors": info["predecessors"], "tickets": {document["id"]: {"state": "PENDING"} for document in documents}, "evidenceIndex": {}, "activeCheckpoints": {}, "acceptance": {"contractBaseline": _contract_baseline(package, repo), "releaseOrder": info["releaseOrder"], "amendments": [], "harness": info["harness"]}}
    execution_record = _execution_record_path(package, attempt)
    created_execution_record = not execution_record.exists()
    if created_execution_record:
        _ensure_execution_record(package, attempt)
    try:
        _validate_state(package, state, projections=False)
        _write_json(path, state)
    except Exception:
        if created_execution_record and execution_record.exists():
            execution_record.unlink()
        raise
    for document in documents:
        _approve_ticket(document)
    _refresh_projections(package, state)
    return _public(_validate_state(package, state))


def command_validate(package: Path, commit: str | None, *, check_arrival_paths: bool = True) -> dict[str, Any]:
    repo = _repo_root(package)
    resolved = _validate_commit(repo, commit) if commit else None
    path = package / STATE_PATH
    if not path.exists():
        result = {"active": False, "reason": "no-active-attempt", "commit": resolved}
        if check_arrival_paths:
            result["findings"] = []
        return result
    summary = _validate_state(package, _load_json(path))
    result = _public(summary)
    if check_arrival_paths:
        comparison_commit = resolved or _run_git(repo, "rev-parse", "HEAD")
        result["findings"] = (
            _contract_doc_name_findings(package, summary)
            + _contract_amendment_findings(package, repo, summary["_acceptance"])
            + _plan_prose_gate_findings(repo, package, summary)
            + _arrival_path_absent_findings(package, summary)
            + _batch_estimate_absent_findings(package, summary)
            + _arrival_findings(repo, package, summary, comparison_commit)
            + _post_gate_pending_findings(summary)
        )
        result["comparisonCommit"] = comparison_commit
    result.update({"active": True, "commit": resolved})
    return result


def command_refresh_progress(package: Path) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _refresh_projections(package, state)
    return {"attempt": summary["attempt"], "progress": _package_relative(package, package / PROGRESS_PATH)}


AMENDMENT_CONTRACT_FILES = ("decision.md", "spec.md", "contract-design.md")


def _amendment_post_gate(summary: dict[str, Any], *, requested: bool = True) -> bool:
    """Amendments stay editable after a terminal Gate pass (text-only corrections); any other frozen Attempt stays closed."""
    lifecycle: Lifecycle = summary["_lifecycle"]
    if not lifecycle.frozen:
        return False
    if lifecycle.gate_verdict == "pass" and requested:
        return True
    hint = "; pass --post-gate to register a text-only correction after a Gate pass" if lifecycle.gate_verdict == "pass" else ""
    raise StateError(f"Attempt {summary['attempt']} is frozen by terminal Gate {lifecycle.gate_verdict}{hint}")


def _post_gate_spec_drift(frozen: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Wording may change; anything Gate evidence binds to (steps, entries, suites, rule bindings) may not."""
    def steps(spec: dict[str, Any]) -> dict[str, Any]:
        return {key: {field: value for field, value in row.items() if field != "expected"} for key, row in spec["steps"].items()}
    drift = [name for name, same in (
        ("Journey steps", steps(frozen) == steps(current)),
        ("Required Suites", frozen["suites"] == current["suites"]),
        ("Rule-to-Suite bindings", {r["Rule"]: r["Suite"] for r in frozen["rules"]} == {r["Rule"]: r["Suite"] for r in current["rules"]}),
    ) if not same]
    return drift


def command_amendment_add(
    package: Path,
    identifier: str,
    summary_text: str,
    affected: list[str],
    artifact: str | None = None,
    tickets: list[str] | None = None,
    post_gate: bool = False,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    frozen = _amendment_post_gate(summary, requested=post_gate)
    if not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", identifier) is None:
        raise StateError("amendment --id must be non-empty identifier text")
    if not isinstance(summary_text, str) or not summary_text.strip():
        raise StateError("amendment --summary must be non-empty")
    if not affected:
        raise StateError("amendment requires at least one --affected path")
    normalized_affected = [
        _package_relative_artifact(package, value, "amendment affected", must_exist=False)
        for value in affected
    ]
    if any("#" in value for value in normalized_affected) or len(set(normalized_affected)) != len(normalized_affected):
        raise StateError("amendment affected paths must be unique package-relative paths without anchors")
    wrong = [value for value in normalized_affected if value not in AMENDMENT_CONTRACT_FILES]
    if wrong:
        raise StateError(
            f"amendment --affected must name changed contract files ({', '.join(AMENDMENT_CONTRACT_FILES)}), got: {', '.join(wrong)}; "
            "repeat --affected once per file, and record impacted Tickets with --tickets"
        )
    ticket_ids = list(dict.fromkeys(item.strip() for item in (tickets or [])))
    unknown_tickets = [item for item in ticket_ids if item not in state["tickets"]]
    if unknown_tickets:
        raise StateError(f"amendment --tickets names unknown Ticket(s): {', '.join(unknown_tickets)}")
    repo = _repo_root(package)
    if frozen and "spec.md" in normalized_affected:
        drift = _post_gate_spec_drift(summary["_journeySpec"], validate_spec_document(package / "spec.md"))
        if drift:
            raise StateError(
                f"post-Gate amendment may change only wording; spec.md differs from the Gate spec in: {', '.join(drift)}; "
                "a change to what Gate evidence binds to needs a new Attempt"
            )
    affected_blobs = _working_tree_blobs(repo, package, normalized_affected)
    row = {
        "id": identifier,
        "summary": summary_text.strip(),
        "affected": normalized_affected,
        "affectedBlobs": {name: affected_blobs.get(name) for name in normalized_affected},
        "artifact": _package_relative_artifact(package, artifact or normalized_affected[0], "amendment artifact", must_exist=True),
        "status": "PENDING",
        "createdAt": _utc_timestamp(),
    }
    if ticket_ids:
        row["tickets"] = ticket_ids
    amendments = state["acceptance"]["amendments"]
    current = next((item for item in amendments if item["id"] == identifier), None)
    if current is not None:
        if any(current.get(key) != row[key] for key in row if key not in {"status", "createdAt"}):
            raise StateError(f"amendment {identifier} already exists with different content; use a new id")
        return {"id": identifier, "status": current["status"], "idempotent": True}
    candidate = json.loads(json.dumps(state, ensure_ascii=False))
    candidate["acceptance"]["amendments"].append(row)
    _validate_state(package, candidate, projections=False)
    _write_json(package / STATE_PATH, candidate)
    _refresh_projections(package, candidate)
    _best_effort_result(package, summary["attempt"], {
        "subject": f"amendment:{identifier}", "transition": "amendment", "id": identifier,
        "from": None, "to": "PENDING", "outcome": "PENDING", **({"postGate": True} if frozen else {}),
    })
    return {"id": identifier, "status": "PENDING", "idempotent": False}


def command_amendment_confirm(
    package: Path,
    identifier: str,
    confirmed_by: str,
    confirmed_revision: str | None,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    frozen = _amendment_post_gate(summary)
    if not isinstance(confirmed_by, str) or not confirmed_by.strip():
        raise StateError("--confirmed-by must be non-empty")
    repo = _repo_root(package)
    head = _run_git(repo, "rev-parse", "HEAD")
    revision = _validate_commit(repo, confirmed_revision or head)
    if not _is_ancestor(repo, revision, head):
        raise StateError("--confirmed-revision must be an ancestor of current HEAD")
    current = next((item for item in state["acceptance"]["amendments"] if item["id"] == identifier), None)
    if current is None:
        raise StateError(f"unknown amendment: {identifier}")
    successor = next((row["id"] for row in state["acceptance"]["amendments"] if identifier in row.get("supersedes", [])), None)
    if successor is not None:
        raise StateError(f"amendment {identifier} is superseded by {successor}; confirm {successor} instead")
    current_blobs = current.get("affectedBlobs", {})
    current_working_blobs = _working_tree_blobs(repo, package, current["affected"])
    changed = [
        path for path in current["affected"]
        if current_blobs.get(path) != current_working_blobs.get(path)
    ]
    if changed:
        raise StateError(f"amendment {identifier} no longer matches affected file contents: {', '.join(changed)}; "
            f"register a new amendment covering the current contract files, run `amendment supersede --id {identifier} --by <new id>`, and confirm the new one")
    if current["status"] == "CONFIRMED":
        if current["confirmedBy"] == confirmed_by.strip() and current["confirmedRevision"] == revision:
            return {"id": identifier, "status": "CONFIRMED", "idempotent": True}
        raise StateError(f"amendment {identifier} already has a different confirmation")
    if current["status"] != "PENDING":
        raise StateError(f"amendment {identifier} is {current['status']}; only PENDING amendments can be confirmed")
    candidate = json.loads(json.dumps(state, ensure_ascii=False))
    row = next(item for item in candidate["acceptance"]["amendments"] if item["id"] == identifier)
    row.update({"status": "CONFIRMED", "confirmedBy": confirmed_by.strip(), "confirmedRevision": revision, "confirmedAt": _utc_timestamp()})
    _validate_state(package, candidate, projections=False)
    _write_json(package / STATE_PATH, candidate)
    _refresh_projections(package, candidate)
    _best_effort_result(package, summary["attempt"], {
        "subject": f"amendment:{identifier}", "transition": "amendment", "id": identifier,
        "from": "PENDING", "to": "CONFIRMED", "outcome": "CONFIRMED", **({"postGate": True} if frozen else {}),
    })
    return {"id": identifier, "status": "CONFIRMED", "idempotent": False}


def _amendment_transition(package: Path, mutate: Any, subject_id: str, to: str, outcome_extra: dict[str, Any]) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    frozen = _amendment_post_gate(summary)
    candidate = json.loads(json.dumps(state, ensure_ascii=False))
    idempotent = mutate(candidate["acceptance"]["amendments"])
    if idempotent:
        return {"id": subject_id, "status": to, "idempotent": True}
    _validate_state(package, candidate, projections=False)
    _write_json(package / STATE_PATH, candidate)
    _refresh_projections(package, candidate)
    _best_effort_result(package, summary["attempt"], {
        "subject": f"amendment:{subject_id}", "transition": "amendment", "id": subject_id,
        "from": "PENDING", "to": to, "outcome": to, **outcome_extra, **({"postGate": True} if frozen else {}),
    })
    return {"id": subject_id, "status": to, "idempotent": False, **outcome_extra}


def command_amendment_supersede(package: Path, identifier: str, by: str) -> dict[str, Any]:
    """Mark an existing amendment as covered by a later one; superseded amendments no longer block the Gate."""
    def mutate(amendments: list[dict[str, Any]]) -> bool:
        old = next((row for row in amendments if row["id"] == identifier), None)
        new = next((row for row in amendments if row["id"] == by), None)
        if old is None or new is None or identifier == by:
            raise StateError(f"amendment supersede needs two distinct existing amendments: --id {identifier} --by {by}")
        if identifier in new.get("supersedes", []):
            return True
        if old["status"] != "PENDING":
            raise StateError(f"amendment {identifier} is {old['status']}; only PENDING amendments can be superseded")
        if new["status"] == "WITHDRAWN":
            raise StateError(f"amendment {by} is WITHDRAWN and cannot supersede {identifier}")
        # 只核对合同文件：旧版修订可能登记过 tickets/ 等非合同路径，而 add 已不接受这类路径，否则这些旧条永远无法被取代。
        missing = [path for path in old["affected"] if path in AMENDMENT_CONTRACT_FILES and path not in new["affected"]]
        if missing:
            raise StateError(f"amendment {by} must also list affected {', '.join(missing)} so that superseded {identifier} stays covered")
        new["supersedes"] = [*new.get("supersedes", []), identifier]
        return False
    return _amendment_transition(package, mutate, identifier, "SUPERSEDED", {"supersededBy": by})


def command_amendment_withdraw(package: Path, identifier: str, reason: str) -> dict[str, Any]:
    """Withdraw a PENDING amendment that no longer applies; it stays in state for the audit trail but never blocks the Gate."""
    if not isinstance(reason, str) or not reason.strip():
        raise StateError("amendment withdraw --reason must be non-empty")

    def mutate(amendments: list[dict[str, Any]]) -> bool:
        row = next((item for item in amendments if item["id"] == identifier), None)
        if row is None:
            raise StateError(f"unknown amendment: {identifier}")
        if row["status"] == "WITHDRAWN":
            return True
        if row["status"] != "PENDING":
            raise StateError(f"amendment {identifier} is {row['status']}; only PENDING amendments can be withdrawn")
        row.update({"status": "WITHDRAWN", "withdrawnReason": reason.strip(), "withdrawnAt": _utc_timestamp()})
        return False
    return _amendment_transition(package, mutate, identifier, "WITHDRAWN", {"reason": reason.strip()})


def command_sync_predecessors(package: Path) -> dict[str, Any]:
    """Re-read 前置包（Predecessors） from the current Plan into state, for a plan revised after init."""
    state = _load_json(package / STATE_PATH)
    repo = _repo_root(package)
    plan = _repo_relative(repo, state["attempt"]["plan"], "plan")
    candidate = json.loads(json.dumps(state, ensure_ascii=False))
    new = _predecessors_from_plan(package, repo, _read(repo / plan))
    if new == state["predecessors"]:
        return {"predecessors": new, "idempotent": True}
    candidate["predecessors"] = new
    summary = _validate_state(package, candidate, projections=False)
    _assert_mutable(summary)
    _write_json(package / STATE_PATH, candidate)
    _refresh_projections(package, candidate)
    return {"predecessors": new, "idempotent": False}


def _assert_mutable(summary: dict[str, Any]) -> None:
    if summary["_lifecycle"].frozen:
        raise StateError(f"Attempt {summary['attempt']} is frozen by terminal Gate {summary['_lifecycle'].gate_verdict}")


def _v36_record_valid(
    package: Path,
    record: dict[str, Any],
    comparison_commit: str,
    *,
    expected_environment: str | None = None,
    attempt_active: bool = True,
) -> bool:
    return evidence_record_valid(
        record,
        comparison_commit,
        repo=_repo_root(package),
        package=package,
        expected_environment=expected_environment,
        attempt_active=attempt_active,
    )


def _ticket_owned_evidence_keys(summary: dict[str, Any], identifier: str) -> list[str]:
    document = next(row for row in summary["_documents"] if row["id"] == identifier)
    suites = summary["_journeySpec"]["suites"]
    return [f"review:{identifier}"] + [
        f"suite:{suite_id}" for suite_id in document["coverage"]["suites"] if suites[suite_id]["scope"] == "ticket"
    ]


def _v36_ticket_satisfy_gaps(package: Path, state: dict[str, Any], summary: dict[str, Any], identifier: str, revision: str) -> list[str]:
    repo = _repo_root(package)
    head = _run_git(repo, "rev-parse", "HEAD")
    if not _is_ancestor(repo, revision, head):
        return ["--revision must be an ancestor of current HEAD"]
    document = next(row for row in summary["_documents"] if row["id"] == identifier)
    gaps = []
    spec = summary["_journeySpec"]
    lifecycle: Lifecycle = summary["_lifecycle"]
    for suite_id in document["coverage"]["suites"]:
        suite = spec["suites"][suite_id]
        records = state["evidenceIndex"].get(f"suite:{suite_id}", [])
        if not any(
            _v36_record_valid(
                package,
                record,
                revision,
                expected_environment=suite["environment"],
                attempt_active=not lifecycle.frozen,
            )
            for record in records
        ):
            template = json.dumps({"kind": "suite", "suiteId": suite_id, "environment": suite["environment"], "revision": revision, "artifact": "<package-relative file>", "conclusion": "supporting"}, ensure_ascii=False)
            gaps.append(f"Suite {suite_id} 缺少对当前 revision 有效的 supporting 记录；补登：echo '{template}' | impl_package_state.py --package <package> evidence add")
    if document["coverage"]["requiredReview"] != "none":
        records = state["evidenceIndex"].get(f"review:{identifier}", [])
        if not any(
            _v36_record_valid(package, record, revision, attempt_active=not lifecycle.frozen)
            for record in records
        ):
            template = json.dumps({"kind": "review", "ticket": identifier, "environment": "<env>", "revision": revision, "artifact": "execution/<attempt>/reviews/<file>", "conclusion": "supporting"}, ensure_ascii=False)
            gaps.append(f"Ticket {identifier} 缺少有效的 supporting review（需无未关闭 blocker）；补登：echo '{template}' | impl_package_state.py --package <package> evidence add")
    return gaps


def _validate_first_step_object_is_new(state: dict[str, Any], spec: dict[str, Any], record: dict[str, Any]) -> None:
    if record.get("kind") != "journey-step" or not record.get("outputRef"):
        return
    journey = next(item for item in spec["journeys"] if item["id"] == record["journeyId"])
    if record["stepId"] != journey["steps"][0]["id"]:
        return
    output_ref = record["outputRef"]
    for records in state["evidenceIndex"].values():
        for existing in records:
            if (
                existing.get("kind") == "journey-step"
                and existing.get("runId") != record["runId"]
                and output_ref in {existing.get("inputRef"), existing.get("outputRef")}
            ):
                suggested_ref = f"{record['runId']}-{output_ref}"
                raise StateError(
                    f"第 1 步产出的对象 {output_ref!r} 已在 run {existing['runId']} 中出现，"
                    f"每次 run 需新建业务对象；给 outputRef/inputRef 加 runId 前缀（例如 {suggested_ref!r}）"
                )


def _validate_journey_step_order(state: dict[str, Any], spec: dict[str, Any], record: dict[str, Any]) -> None:
    journey = next(item for item in spec["journeys"] if item["id"] == record["journeyId"])
    positions = {step["id"]: index for index, step in enumerate(journey["steps"])}
    current_position = positions[record["stepId"]]
    steps_by_position: dict[int, list[dict[str, Any]]] = {}
    for records in state["evidenceIndex"].values():
        for existing in records:
            # 一次 run 可连续走多条 Journey，顺序只在同一 Journey 内核对。
            if (
                existing.get("kind") == "journey-step"
                and existing.get("runId") == record["runId"]
                and existing.get("journeyId") == record["journeyId"]
            ):
                steps_by_position.setdefault(positions[existing["stepId"]], []).append(existing)
    if not steps_by_position:
        if current_position != 0:
            # 按影响范围复测：新 run 可从受影响步骤起步，但承接须对上其他 run 上一步的有效 outputRef。
            previous_step = journey["steps"][current_position - 1]
            inherited = record.get("inputRef")
            ok = isinstance(inherited, str) and any(
                existing.get("kind") == "journey-step"
                and existing.get("journeyId") == record["journeyId"]
                and existing.get("stepId") == previous_step["id"]
                and existing.get("conclusion") == "supporting"
                and not existing.get("invalidatedBy")
                and existing.get("outputRef") == inherited
                for records in state["evidenceIndex"].values()
                for existing in records
            )
            if not ok:
                raise StateError(
                    f"Journey run {record['runId']} must start at {journey['steps'][0]['id']}；"
                    "若第 1 步刚因对象复用被拒，先修正第 1 步的 outputRef/inputRef 再按 Spec 顺序重试。"
                    "按影响范围复测时可从受影响步骤起步，但其 inputRef 须等于其他 run 上一步的 outputRef"
                )
        return
    last_position = max(steps_by_position)
    if set(steps_by_position) != set(range(min(steps_by_position), last_position + 1)):
        raise StateError(f"Journey run {record['runId']} has a missing earlier step; start a new run")
    if current_position < last_position or current_position > last_position + 1:
        raise StateError(f"Journey run {record['runId']} must record steps in Spec order")
    if current_position == last_position + 1:
        last_record = steps_by_position[last_position][-1]
        if last_record.get("conclusion") != "supporting" or last_record.get("invalidatedBy"):
            raise StateError(f"Journey run {record['runId']} cannot continue after a failed or invalidated step")
    current_step = journey["steps"][current_position]
    handoff = current_step["handoff"]
    if current_position > 0 and handoff != "—":
        previous_step = journey["steps"][current_position - 1]
        previous_records = steps_by_position[current_position - 1]
        previous_record = previous_records[-1]
        previous_output = previous_record.get("outputRef")
        context = (
            f"Journey {journey['id']} 第 {current_position + 1} 步 {current_step['id']} "
            f"承接‘{handoff}’"
        )
        if not isinstance(previous_output, str) or not previous_output.strip():
            raise StateError(
                f"{context}无法核对：第 {current_position} 步 {previous_step['id']} 缺少 outputRef，"
                "期望值为上一条记录的 outputRef。请用 evidence invalidate --key "
                f"journey:{record['runId']}:{previous_step['id']} --invalidated-by <原因> 失效该步后补带 outputRef 重新登记，或另起 run。"
            )
        actual_input = record.get("inputRef")
        if not isinstance(actual_input, str) or not actual_input.strip():
            raise StateError(
                f"{context}缺少 inputRef；期望值为 {previous_output!r}，需与 "
                f"{previous_step['id']} 的 outputRef 完全相等。"
            )
        if actual_input != previous_output:
            raise StateError(
                f"{context}的 inputRef 与 {previous_step['id']} outputRef 不一致；"
                f"期望值为 {previous_output!r}，实际为 {actual_input!r}。"
            )


def command_evidence_add(package: Path, payload_text: str, dry_run: bool = False) -> dict[str, Any]:
    from impl_package_runtime import evidence_batch

    return evidence_batch.evidence_add(package, payload_text, dry_run)


def command_evidence_invalidate(package: Path, key: str, invalidated_by: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if not isinstance(invalidated_by, str) or not invalidated_by.strip():
        raise StateError("invalidated-by must be non-empty")
    if not isinstance(key, str) or not key.strip():
        raise StateError("evidence invalidate requires --key")
    records = state["evidenceIndex"].get(key)
    if not isinstance(records, list) or not records:
        raise StateError("evidence key not found")
    changed = False
    for record in records:
        previous = record.get("invalidatedBy")
        if previous is None:
            record["invalidatedBy"] = invalidated_by.strip()
            changed = True
        elif previous != invalidated_by.strip():
            raise StateError(f"evidence key {key} is already invalidated by {previous}")
    if changed:
        _validate_state(package, state, projections=False)
        _write_json(package / STATE_PATH, state)
        _refresh_projections(package, state)
    return {"evidenceKey": key, "invalidated": True, "idempotent": not changed}


def command_evidence_carry_forward(
    package: Path, key: str | None, to: str, reason: str | list[str] | None, judged_by: str,
    selects: list[str] | None = None, dry_run: bool = False,
) -> dict[str, Any]:
    """Record the agent's judgment that supporting evidence still covers runtime changes up to `to` (batched in evidence_batch)."""
    from impl_package_runtime import evidence_batch

    return evidence_batch.evidence_carry_forward(package, key, to, reason, judged_by, selects, dry_run)


def command_set_state(
    package: Path,
    identifier: str,
    target: str,
    expect: str,
    revision: str | None,
    environment: str | None,
    disposition: str | None,
    successor: str | None,
    evidence: str | None,
    revalidation_plan: str | None,
    invalidated_by: str | None = None,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if identifier not in state["tickets"] or target not in TICKET_STATES:
        raise StateError(f"unknown Ticket or invalid state: {identifier}/{target}")
    current = state["tickets"][identifier]["state"]
    if current != expect:
        raise StateError(f"stale ticket transition for {identifier}: expected {expect}, found {current}")
    repo = _repo_root(package)
    if target != "NEEDS-REVALIDATION" and invalidated_by is not None:
        raise StateError("--invalidated-by is only valid for NEEDS-REVALIDATION")

    if current == "RETIRED":
        if target != "RETIRED":
            raise StateError(f"RETIRED Ticket {identifier} is terminal; create a patch Attempt to continue")
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("repeating RETIRED requires the original --disposition and --evidence")
        normalized_retired = _repo_relative(repo, evidence, "retired evidence")
        existing = state["tickets"][identifier]
        if (
            disposition != existing.get("disposition")
            or normalized_retired != existing.get("evidence")
            or successor != existing.get("successor")
        ):
            raise StateError(f"RETIRED Ticket {identifier} is terminal; only an identical retry is idempotent")
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    if current == target and target != "NEEDS-REVALIDATION":
        return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True}

    invalidated_count = 0
    if target == "NEEDS-REVALIDATION":
        if not isinstance(invalidated_by, str) or not invalidated_by.strip():
            raise StateError("NEEDS-REVALIDATION requires a non-empty --invalidated-by")
        for key in _ticket_owned_evidence_keys(summary, identifier):
            for record in state["evidenceIndex"].get(key, []):
                if record.get("invalidatedBy") is None:
                    record["invalidatedBy"] = invalidated_by.strip()
                    invalidated_count += 1
        if current == target and invalidated_count == 0:
            return {"kind": "ticket", "id": identifier, "state": target, "idempotent": True, "invalidatedEvidence": 0}

    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"} and not revalidation_plan:
        raise StateError("returning to PENDING requires --revalidation-plan")
    if target == "PENDING" and current in {"BLOCKED", "NEEDS-REVALIDATION"}:
        _repo_relative(repo, revalidation_plan, "revalidation plan")
    if target == "SATISFIED":
        if not revision:
            revision = _run_git(repo, "rev-parse", "HEAD")
        if environment is not None and not environment.strip():
            raise StateError("SATISFIED --environment must be non-empty when provided")
        revision = _validate_commit(repo, revision)
        gaps = _v36_ticket_satisfy_gaps(package, state, summary, identifier, revision)
        unreleased = [
            dep for kind, dep in summary["_ticketDependencies"][identifier]
            if kind in {"implementation", "acceptance"} and not _ticket_released(state["tickets"], dep)
        ]
        if unreleased:
            gaps.append(f"Ticket implementation or acceptance dependencies are not released: {', '.join(unreleased)}")
        if gaps:
            raise StateError("SATISFIED rejected (all gaps):\n- " + "\n- ".join(gaps))
    if target == "BLOCKED" and not evidence:
        raise StateError("BLOCKED requires --evidence")
    normalized_evidence = _repo_relative(repo, evidence, "Ticket evidence") if evidence else None
    if target == "RETIRED":
        if disposition not in DISPOSITIONS or not evidence:
            raise StateError("RETIRED requires --disposition and --evidence")
        if disposition == "superseded" and not successor:
            raise StateError("superseded RETIRED requires --successor")
        state["tickets"][identifier] = {"state": "RETIRED", "disposition": disposition, "evidence": _repo_relative(repo, evidence, "retired evidence")}
        if successor:
            state["tickets"][identifier]["successor"] = successor
    if target != "RETIRED":
        state["tickets"][identifier] = {"state": target}
        if normalized_evidence and target in {"BLOCKED", "NEEDS-REVALIDATION"}:
            state["tickets"][identifier]["evidence"] = normalized_evidence
        if target == "SATISFIED":
            acceptance = {"revision": revision}
            if environment is not None:
                acceptance["environment"] = environment
            state["tickets"][identifier] = {"state": target, "acceptance": acceptance}
    _validate_state(package, state, projections=False)
    _write_json(package / STATE_PATH, state)
    _refresh_projections(package, state)
    result = {"kind": "ticket", "id": identifier, "state": target, "idempotent": False}
    if target == "NEEDS-REVALIDATION":
        result["invalidatedEvidence"] = invalidated_count
    if target in {"SATISFIED", "RETIRED"}:
        _best_effort_trail(
            package,
            summary["attempt"],
            {
                "subject": f"ticket:{identifier}",
                "kind": "result",
                "transition": "ticket-state",
                "from": current,
                "to": target,
                "outcome": target,
            },
        )
    return result


def _add_judgment(package: Path, payload: dict[str, Any]) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state)
    _assert_mutable(summary)
    if payload.get("purpose") != "judgment":
        raise StateError("er-add accepts judgment only; use checkpoint command")
    subject = payload.get("subject", "attempt")
    if subject != "attempt" and (not isinstance(subject, str) or not re.fullmatch(r"ticket:[^\s]+", subject) or subject.split(":", 1)[1] not in state["tickets"]):
        raise StateError(f"invalid judgment subject: {subject}")
    title, content = payload.get("title"), payload.get("content")
    if not isinstance(title, str) or not title.strip() or "\n" in title or not isinstance(content, str) or not content.strip():
        raise StateError("judgment requires one-line title and non-empty content")
    evidence = payload.get("evidence", [])
    if isinstance(evidence, str):
        evidence = [evidence]
    if not isinstance(evidence, list):
        raise StateError("judgment evidence must be a path or list")
    repo = _repo_root(package)
    normalized = [_repo_relative(repo, item, "judgment evidence") for item in evidence]
    path = _ensure_execution_record(package, summary["attempt"])
    _, entries = _parse_execution_record(path, summary["attempt"])
    same = next((row for row in entries if row["purpose"] == "judgment" and row["subject"] == subject and row["title"] == title.strip() and row["content"] == content.strip() and row["evidence"] == normalized), None)
    if same:
        return {"recordId": same["id"], "attempt": summary["attempt"], "idempotent": True}
    number = max((row["number"] for row in entries), default=0) + 1
    record_id = f"{summary['attempt']}-ER-{number:03d}"
    evidence_text = "\n".join(f"- {item}" for item in normalized) or "- none"
    block = f"\n## {record_id} · judgment\n\n- Subject: {subject}\n- Title: {title.strip()}\n- Next action: none\n\n### Evidence\n\n{evidence_text}\n\n### Content\n\n{content.strip()}\n"
    _write_text(path, _read(path).rstrip() + block)
    _refresh_projections(package, state)
    return {"recordId": record_id, "attempt": summary["attempt"], "idempotent": False}


def command_er_add(package: Path, input_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"er-add input is invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise StateError("er-add input must be an object")
    return _add_judgment(package, payload)


def validate_dispatch_receipt(receipt: Any) -> None:
    """Reject placeholders that cannot prove a host accepted the dispatch."""
    if isinstance(receipt, str):
        if receipt.strip():
            return
    elif isinstance(receipt, dict) and receipt:
        return
    raise StateError("trail dispatch receipt must be a non-empty string or object")


def _validate_resource_keys(value: Any, label: str = "resource_keys") -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not item.strip() for item in value
    ):
        raise StateError(f"{label} must be an array of non-empty strings")
    if len(value) != len(set(value)):
        raise StateError(f"{label} must not contain duplicates")
    return value


def _lease_directory(package: Path, attempt: str) -> Path:
    root = package.resolve()
    expected = root / EXECUTION_PATH / attempt / "leases"
    directory = expected.resolve()
    if directory != expected:
        raise StateError("resource lease directory must not traverse symlinks")
    try:
        directory.relative_to(root)
    except ValueError as exc:
        raise StateError("resource lease directory escapes package") from exc
    return directory


def _lease_record_path(directory: Path, resource_key: str) -> Path:
    digest = hashlib.sha256(resource_key.encode("utf-8")).hexdigest()
    return directory / f"{digest}.json"


def _read_lease_records(directory: Path) -> list[tuple[Path, dict[str, str]]]:
    if not directory.exists():
        return []
    records: list[tuple[Path, dict[str, str]]] = []
    for path in sorted(directory.iterdir()):
        if LEASE_FILE_RE.fullmatch(path.name) is None:
            continue
        if path.is_symlink() or path.resolve().parent != directory:
            raise StateError("resource lease file must stay inside the lease directory")
        value = _load_json(path)
        fields = {"lease_id", "resource_key", "owner", "owner_token"}
        if set(value) != fields or any(not isinstance(value[field], str) or not value[field] for field in fields):
            raise StateError(f"invalid resource lease record: {path.name}")
        if LEASE_ID_RE.fullmatch(value["lease_id"]) is None or _lease_record_path(directory, value["resource_key"]) != path:
            raise StateError(f"invalid resource lease identity: {path.name}")
        records.append((path, value))
    return records


def command_lease_acquire(package: Path, resource_keys: list[str], owner: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    _assert_mutable(summary)
    keys = _validate_resource_keys(resource_keys, "lease resource keys")
    if not keys:
        raise StateError("lease acquire requires at least one resource key")
    if not isinstance(owner, str) or not owner.strip():
        raise StateError("lease owner must be a non-empty string")

    directory = _lease_directory(package, summary["attempt"])
    directory.mkdir(parents=True, exist_ok=True)
    lease_id = uuid.uuid4().hex
    owner_token = secrets.token_urlsafe(32)
    created: list[Path] = []

    def rollback() -> list[Path]:
        residue = []
        for created_path in reversed(created):
            try:
                created_path.unlink(missing_ok=True)
            except OSError:
                residue.append(created_path)
        return residue

    record = {"lease_id": lease_id, "resource_key": "", "owner": owner.strip(), "owner_token": owner_token}
    for key in sorted(keys):
        path = _lease_record_path(directory, key)
        record["resource_key"] = key
        try:
            descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            residue = rollback()
            detail = f"; partial lease residue: {residue}" if residue else ""
            raise StateError(f"resource lease already held: {key}{detail}") from exc
        except OSError as exc:
            residue = rollback()
            detail = f"; partial lease residue: {residue}" if residue else ""
            raise StateError(f"resource lease creation failed: {exc}{detail}") from exc
        created.append(path)
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
                stream.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
        except OSError as exc:
            residue = rollback()
            detail = f"; partial lease residue: {residue}" if residue else ""
            raise StateError(f"resource lease creation failed: {exc}{detail}") from exc
    return {
        "attempt": summary["attempt"],
        "lease_id": lease_id,
        "owner": owner.strip(),
        "owner_token": owner_token,
        "lease_relative_paths": [path.relative_to(package.resolve()).as_posix() for path in created],
    }


def command_lease_release(package: Path, lease_id: str, owner_token: str) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    if not isinstance(lease_id, str) or LEASE_ID_RE.fullmatch(lease_id) is None:
        raise StateError("lease_id must be a valid lease id")
    if not isinstance(owner_token, str) or not owner_token:
        raise StateError("lease owner token must be non-empty")
    records = _read_lease_records(_lease_directory(package, summary["attempt"]))
    matching = [(path, record) for path, record in records if record["lease_id"] == lease_id]
    if not matching:
        return {"attempt": summary["attempt"], "lease_id": lease_id, "released": False, "idempotent": True}
    if any(not secrets.compare_digest(record["owner_token"], owner_token) for _, record in matching):
        raise StateError("resource lease owner token mismatch")
    for path, _ in matching:
        path.unlink()
    return {"attempt": summary["attempt"], "lease_id": lease_id, "released": True, "idempotent": False}


def _validate_dispatch_lease(package: Path, attempt: str, event: dict[str, Any]) -> None:
    if "lease_id" not in event:
        return
    lease_id = event["lease_id"]
    if not isinstance(lease_id, str) or LEASE_ID_RE.fullmatch(lease_id) is None:
        raise StateError("trail dispatch lease_id must be a valid lease id")
    records = [
        record
        for _, record in _read_lease_records(_lease_directory(package, attempt))
        if record["lease_id"] == lease_id
    ]
    if not records:
        raise StateError("trail dispatch lease_id does not identify a held lease")
    if len({(record["owner"], record["owner_token"]) for record in records}) != 1:
        raise StateError("trail dispatch lease records have inconsistent owners")
    if any(record["owner"] != event["worker"] for record in records):
        raise StateError("trail dispatch worker does not match lease owner")
    if not {record["resource_key"] for record in records} <= set(event["resource_keys"]):
        raise StateError("trail dispatch resource_keys do not include the held lease resources")


def _validate_code_delta(value: Any) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"base", "head"}:
        raise StateError("code_delta must contain exactly base and head")
    for field in ("base", "head"):
        if not isinstance(value[field], str) or FIXED_COMMIT_RE.fullmatch(value[field]) is None:
            raise StateError(f"code_delta.{field} must be a Git commit or snapshot commit")
    return value


def _validate_review_pending(value: Any) -> None:
    if not isinstance(value, dict):
        raise StateError("review.dispatch_pending value must be an object")
    for field in ("return_id", "consumption_id", "reason"):
        _trail_text_field(value, field, "review.dispatch_pending")
    _validate_code_delta(value.get("code_delta"))


def _validate_review_dispatch_fields(event: dict[str, Any]) -> None:
    has_phase = "review_phase" in event
    has_track = "review_track" in event
    phase_values = " | ".join(REVIEW_PHASE_VALUES)
    track_values = " | ".join(REVIEW_TRACK_VALUES)
    if has_phase != has_track:
        raise StateError(
            "review_phase 与 review_track 必须同时出现；"
            f"review_phase 合法值：{phase_values}；review_track 合法值：{track_values}"
        )
    if has_phase:
        phase = event["review_phase"]
        if not isinstance(phase, str) or phase not in REVIEW_PHASES:
            raise StateError(f"review_phase 合法值：{phase_values}；收到 {phase!r}")
        track = event["review_track"]
        if not isinstance(track, str) or track not in REVIEW_TRACKS:
            raise StateError(f"review_track 合法值：{track_values}；收到 {track!r}")
    if "review_recheck" in event and type(event["review_recheck"]) is not bool:
        raise StateError("review_recheck 必须是 boolean")


def _merge_trail_named_fields(event: dict[str, Any], named_fields: dict[str, Any]) -> dict[str, Any]:
    for field, value in named_fields.items():
        if value is None:
            continue
        if field in event:
            same = type(event[field]) is type(value) and event[field] == value
            if not same:
                option = f"--{field.replace('_', '-')}"
                raise StateError(f"trail append {option} conflicts with stdin {field}")
        else:
            event[field] = value
    return event


def _validate_trail_event(event: dict[str, Any]) -> dict[str, Any]:
    supplied_common = sorted(TRAIL_COMMON_FIELDS & event.keys())
    if supplied_common:
        fields = ", ".join(supplied_common)
        raise StateError(f"trail append fills {fields}; omit them from stdin JSON")
    kind = event.get("kind")
    if not isinstance(kind, str) or kind not in TRAIL_APPEND_KINDS:
        supported = ", ".join(sorted(TRAIL_APPEND_KINDS))
        raise StateError(f"invalid trail kind {kind!r}; trail append supports: {supported}")
    _trail_text_field(event, "subject", kind)
    if kind == "fact":
        key = event.get("key")
        if not isinstance(key, str) or not key.strip():
            raise StateError("trail fact requires a non-empty key")
        if key not in FACT_KEYS:
            raise StateError(f"trail append rejected fact key {key!r}：{describe_unknown_fact_keys((key,))}")
        if "value" not in event:
            raise StateError("trail fact requires value")
        if key == "review.dispatch_pending":
            _validate_review_pending(event["value"])
            event["value"].pop("capacity", None)
    elif kind == "escape":
        _trail_text_field(event, "deviation", kind)
        _trail_text_field(event, "reason", kind)
    elif kind == "dispatch":
        _trail_text_field(event, "worker", kind)
        for field in ("dispatch_id", "candidate_id", "mode", "chosen"):
            _trail_text_field(event, field, kind)
        if event["mode"] not in {"investigate", "implement", "fix", "verify"}:
            raise StateError("trail dispatch mode must be investigate|implement|fix|verify")
        for field in RETIRED_DISPATCH_FIELDS:
            event.pop(field, None)
        _validate_resource_keys(event.get("resource_keys"), "dispatch resource_keys")
        if "lease_id" in event:
            _trail_text_field(event, "lease_id", kind)
        validate_dispatch_receipt(event.get("receipt"))
        if event.get("outcome") != "RUNNING" or event.get("returned") is not False:
            raise StateError("trail dispatch requires outcome=RUNNING and returned=false")
        _validate_review_dispatch_fields(event)
    else:
        _trail_text_field(event, "outcome", kind)
        _trail_text_field(event, "of", kind)
        _trail_text_field(event, "return_id", kind)
        has_delta = "code_delta" in event
        has_consumption = "consumption_id" in event
        if has_delta != has_consumption:
            raise StateError("worker-return code_delta and consumption_id must appear together")
        if has_delta:
            _validate_code_delta(event["code_delta"])
            _trail_text_field(event, "consumption_id", kind)
        if "endedAt" in event:
            _validate_iso_timestamp(event["endedAt"], "trail worker-return endedAt")
        if "usage" in event:
            usage = event["usage"]
            if not isinstance(usage, dict) or set(usage) - {"input", "output", "costUsd"} or not {"input", "output"} <= set(usage):
                raise StateError("trail worker-return usage requires input/output and optional costUsd")
            for field in ("input", "output"):
                if type(usage[field]) is not int or usage[field] < 0:
                    raise StateError(f"trail worker-return usage.{field} must be a non-negative integer")
            if "costUsd" in usage and (
                isinstance(usage["costUsd"], bool)
                or not isinstance(usage["costUsd"], (int, float))
                or (isinstance(usage["costUsd"], float) and not math.isfinite(usage["costUsd"]))
                or usage["costUsd"] < 0
            ):
                raise StateError("trail worker-return usage.costUsd must be a non-negative number")
        if "failureClass" in event and (
            not isinstance(event["failureClass"], str)
            or event["failureClass"] not in {"flaky", "env", "real"}
        ):
            raise StateError("trail worker-return failureClass must be flaky|env|real")
    return event


def _current_validation_result(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> ValidationResult:
    """Authoritative validation result: the same projection check `package validate` runs."""
    try:
        _validate_projections(package, state, summary)
    except StateError:
        return ValidationResult(projection_drift=True, source="engine projection validation")
    return ValidationResult(projection_drift=False, source="engine projection validation")


def _validate_actual_dispatch(
    package: Path,
    event: dict[str, Any],
    rows: list[dict[str, Any]],
    validation_result: ValidationResult | None = None,
) -> None:
    blockers = dispatch_admission(package, event, validation_result)
    foundation = [blocker["reason"] for blocker in blockers if blocker.get("type") == "foundation"]
    if foundation:
        raise StateError(
            f"trail dispatch is withheld by global blocking: {foundation}；"
            "运行 situation.py render 查看详情"
        )
    if blockers:
        raise StateError("trail dispatch is withheld: " + "; ".join(blocker["reason"] for blocker in blockers))

    if "reviews" in event:
        _trail_text_field(event, "reviews", "dispatch")
        _trail_text_field(event, "consumption_id", "dispatch")
        code_delta = _validate_code_delta(event.get("code_delta"))
        returned = next(
            (
                row
                for row in rows
                if row.get("kind") == "worker-return" and row.get("return_id") == event["reviews"]
            ),
            None,
        )
        if returned is None or returned.get("code_delta") != code_delta or returned.get("consumption_id") != event["consumption_id"]:
            raise StateError("review dispatch must reference a matching worker-return code_delta and consumption_id")
        if returned.get("subject") != event.get("subject"):
            raise StateError("review dispatch subject must match the reviewed worker-return")


def _validate_worker_return(event: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    dispatch = next(
        (row for row in rows if row.get("kind") == "dispatch" and row.get("dispatch_id") == event["of"]),
        None,
    )
    if dispatch is None:
        raise StateError("worker-return of must reference an existing dispatch_id")
    if event.get("subject") != dispatch.get("subject"):
        raise StateError("worker-return subject must match its dispatch")
    prior_for_dispatch = [
        row
        for row in rows
        if row.get("kind") == "worker-return" and row.get("of") == event["of"]
    ]
    if prior_for_dispatch and not any(_same_event(row, event) for row in prior_for_dispatch):
        raise StateError(f"dispatch {event['of']} already has a worker-return")
    reused = [row for row in rows if row.get("kind") == "worker-return" and row.get("return_id") == event["return_id"]]
    if reused and not any(_same_event(row, event) for row in reused):
        raise StateError(f"return_id already exists: {event['return_id']}")


def _validate_review_pending_against_return(event: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    value = event["value"]
    returned = next(
        (
            row
            for row in rows
            if row.get("kind") == "worker-return" and row.get("return_id") == value["return_id"]
        ),
        None,
    )
    if returned is None or returned.get("code_delta") != value["code_delta"] or returned.get("consumption_id") != value["consumption_id"]:
        raise StateError("review.dispatch_pending must reference a matching worker-return")
    if returned.get("subject") != event.get("subject"):
        raise StateError("review.dispatch_pending subject must match its worker-return")


def command_trail_append(
    package: Path,
    input_text: str,
    named_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    try:
        event = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"trail append input is invalid JSON: {exc}") from exc
    if not isinstance(event, dict):
        raise StateError("trail append input must be an object")
    if named_fields:
        event = _merge_trail_named_fields(event, named_fields)
    event = _validate_trail_event(event)
    state = _load_json(package / STATE_PATH)
    # Dispatch reports projection drift as a global blocking slug instead of a bare mismatch error.
    summary = _validate_state(package, state, projections=event["kind"] != "dispatch")
    _assert_mutable(summary)
    rows = _active_trail_rows(package, summary["attempt"])
    if event["kind"] == "dispatch":
        reused = [
            row
            for row in rows
            if row.get("kind") == "dispatch" and row.get("dispatch_id") == event["dispatch_id"]
        ]
        if reused:
            same = next((row for row in reused if _same_event(row, event)), None)
            if same is None:
                raise StateError(f"dispatch_id already exists: {event['dispatch_id']}")
            return {
                "attempt": summary["attempt"],
                "kind": event["kind"],
                "path": f"execution/{summary['attempt']}/{ACTIVE_TRAIL_NAME}",
                "appended": False,
                "seq": same.get("seq"),
            }
    if event["kind"] == "fact" and event.get("key") == "review.dispatch_pending":
        _validate_review_pending_against_return(event, rows)
    elif event["kind"] == "dispatch":
        _validate_dispatch_lease(package, summary["attempt"], event)
        _validate_actual_dispatch(package, event, rows, _current_validation_result(package, state, summary))
    elif event["kind"] == "worker-return":
        _validate_worker_return(event, rows)
        same = next((row for row in rows if row.get("kind") == "worker-return" and _same_event(row, event)), None)
        if same is not None:
            return {"attempt": summary["attempt"], "kind": event["kind"],
                    "path": f"execution/{summary['attempt']}/{ACTIVE_TRAIL_NAME}", "appended": False, "seq": same.get("seq")}
    appended = _append_trail(package, summary["attempt"], event)
    matching = [row for row in _active_trail_rows(package, summary["attempt"]) if _same_event(row, event)]
    return {
        "attempt": summary["attempt"],
        "kind": event["kind"],
        "path": f"execution/{summary['attempt']}/{ACTIVE_TRAIL_NAME}",
        "appended": appended,
        "seq": matching[-1].get("seq") if matching else None,
    }


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
