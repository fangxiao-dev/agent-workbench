"""package-level and amendment commands."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .attempt_store import (
    _approve_ticket,
    _best_effort_result,
    _ensure_execution_record,
    _execution_record_path,
    _ticket_snapshot,
    _write_attempt_archive,
)
from .cmd_evidence import (
    _assert_mutable,
)
from .journey_evidence import (
    _package_relative_artifact,
)
from .plan_tickets import (
    _arrival_findings,
    _arrival_path_absent_findings,
    _batch_estimate_absent_findings,
    _contract_amendment_findings,
    _contract_baseline,
    _contract_doc_name_findings,
    _package_relative,
    _plan_info,
    _plan_prose_gate_findings,
    _post_gate_pending_findings,
    _predecessors_from_plan,
    _ticket_dependencies,
    _ticket_documents,
    _validate_first_visible_step,
    _working_tree_blobs,
    command_check_spec,
)
from .spec_journey import (
    _journey_coverage_errors,
    _journey_spec,
    validate_spec_document,
)
from .state_core import (
    FORMAT_VERSION,
    Lifecycle,
    PACKAGE_ID_RE,
    PROGRESS_PATH,
    STATE_PATH,
    StateError,
    _is_ancestor,
    _load_json,
    _read,
    _repo_relative,
    _repo_root,
    _run_git,
    _utc_timestamp,
    _validate_commit,
    _write_json,
)
from .validate_state import (
    _public,
    _refresh_projections,
    _validate_state,
)


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
