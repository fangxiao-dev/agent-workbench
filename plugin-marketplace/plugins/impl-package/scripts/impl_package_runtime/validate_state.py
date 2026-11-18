"""State validation and projection refresh."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .acceptance import (
    _render_progress,
    _validate_projections,
)
from .attempt_store import (
    _ensure_execution_record,
    _lifecycle,
    _valid_successor,
)
from .journey_evidence import (
    _package_relative_artifact,
    _validate_journey_evidence_index,
)
from .plan_tickets import (
    _normalize_state_predecessors,
    _plan_info,
    _ticket_dependencies,
    _ticket_documents,
    _validate_first_visible_step,
)
from .spec_journey import (
    _frozen_journey_spec,
    _journey_spec,
    _validate_journey_coverage,
)
from .state_core import (
    ATTEMPT_ID_RE,
    DISPOSITIONS,
    FIXED_COMMIT_RE,
    FORMAT_VERSION,
    PROGRESS_PATH,
    StateError,
    TICKET_STATES,
    _repo_relative,
    _repo_root,
    _state_format_version,
    _validate_commit,
    _validate_iso_timestamp,
    _write_text,
)


def _validate_checkpoints(repo: Path, checkpoints: Any, ticket_ids: set[str], *, live: bool) -> dict[str, dict[str, Any]]:
    if not isinstance(checkpoints, dict):
        raise StateError("activeCheckpoints must be an object")
    result: dict[str, dict[str, Any]] = {}
    for subject, value in checkpoints.items():
        if subject != "attempt":
            match = re.fullmatch(r"ticket:([^\s]+)", subject)
            if not match or match.group(1) not in ticket_ids:
                raise StateError(f"invalid active checkpoint subject: {subject}")
        if not isinstance(value, dict) or set(value) != {"next", "blocker", "evidence"}:
            raise StateError(f"activeCheckpoints[{subject}] must contain next, blocker, evidence")
        if not isinstance(value["next"], str) or not value["next"].strip():
            raise StateError(f"activeCheckpoints[{subject}].next must be non-empty")
        if value["blocker"] is not None and (not isinstance(value["blocker"], str) or not value["blocker"].strip()):
            raise StateError(f"activeCheckpoints[{subject}].blocker must be null or non-empty")
        if not isinstance(value["evidence"], list) or any(not isinstance(item, str) for item in value["evidence"]):
            raise StateError(f"activeCheckpoints[{subject}].evidence must be a list")
        result[subject] = dict(value)
        result[subject]["evidence"] = [_repo_relative(repo, item, f"checkpoint {subject} evidence", must_exist=live) for item in value["evidence"]]
    return result


def _attempt_history(state: dict[str, Any], package: Path) -> list[dict[str, Any]]:
    history = state.get("attemptHistory")
    if not isinstance(history, list):
        raise StateError("attemptHistory must be a list")
    repo = _repo_root(package)
    result = []
    for row in history:
        if not isinstance(row, dict) or set(row) != {"id", "plan", "lifecycle", "gate", "executionRecord"}:
            raise StateError("invalid attemptHistory record")
        if not isinstance(row["id"], str) or ATTEMPT_ID_RE.fullmatch(row["id"]) is None:
            raise StateError("attemptHistory id must be valid")
        if row["lifecycle"] not in {"active", "frozen"}:
            raise StateError("attemptHistory lifecycle must be active or frozen")
        plan = _repo_relative(repo, row["plan"], "attemptHistory plan")
        execution_record = _repo_relative(package, row["executionRecord"], "attemptHistory executionRecord")
        gate = row["gate"]
        if gate is not None:
            if not isinstance(gate, dict) or set(gate) - {"verdict", "commit", "environment"} or not {"verdict", "commit"} <= set(gate):
                raise StateError("attemptHistory gate must be null or contain verdict and commit")
            if gate["verdict"] not in {"pass", "fail", "defer", "blocked"}:
                raise StateError("invalid attemptHistory gate verdict")
            gate = dict(gate)
            gate["commit"] = _validate_commit(repo, gate["commit"])
        result.append({**row, "plan": plan, "executionRecord": execution_record, "gate": gate})
    return result


def ready_tickets(dependencies: dict[str, list[tuple[str, str]]], tickets: dict[str, Any]) -> list[str]:
    return [identifier for identifier, edges in dependencies.items() if tickets[identifier]["state"] == "PENDING" and all(_ticket_released(tickets, item) for kind, item in edges if kind == "implementation")]


def _ticket_released(tickets: dict[str, Any], identifier: str, visiting: set[str] | None = None) -> bool:
    visiting = set() if visiting is None else visiting
    if identifier in visiting:
        return False
    visiting.add(identifier)
    row = tickets.get(identifier)
    if not isinstance(row, dict):
        return False
    if row["state"] == "SATISFIED":
        return True
    if row["state"] != "RETIRED":
        return False
    if row.get("disposition") == "waived":
        return True
    successor = row.get("successor")
    if isinstance(successor, str) and "/" in successor:
        return True  # successor lives in another Attempt; the retirement itself releases dependents
    return isinstance(successor, str) and successor in tickets and _ticket_released(tickets, successor, visiting)


def _validate_acceptance_state(package: Path, repo: Path, acceptance: Any, info: dict[str, Any], *, validate_live_artifacts: bool = True) -> dict[str, Any]:
    if not isinstance(acceptance, dict) or set(acceptance) != {"contractBaseline", "releaseOrder", "amendments", "harness"}:
        raise StateError("3.6 acceptance must contain contractBaseline, releaseOrder, amendments, harness")
    if not isinstance(acceptance["releaseOrder"], str) or acceptance["releaseOrder"] not in {"required", "none"} or acceptance["releaseOrder"] != info["releaseOrder"]:
        raise StateError("state acceptance.releaseOrder does not match the Plan")
    harness = acceptance["harness"]
    if (
        not isinstance(harness, dict)
        or set(harness) != {"setup", "precheck", "cleanup", "isolation", "firstVisibleStep"}
        or any(not isinstance(harness.get(field), str) or not harness[field].strip() for field in ("setup", "precheck", "cleanup"))
        or harness.get("isolation") != "per-run"
        or not isinstance(harness.get("firstVisibleStep"), dict)
        or set(harness["firstVisibleStep"]) != {"step", "ticket"}
        or any(not isinstance(harness["firstVisibleStep"].get(field), str) or not harness["firstVisibleStep"][field].strip() for field in ("step", "ticket"))
    ):
        raise StateError("state acceptance.harness fields are invalid")
    if harness != info["harness"]:
        raise StateError("state acceptance.harness does not match the Plan")
    if not isinstance(acceptance["amendments"], list):
        raise StateError("state acceptance.amendments must be a list")
    live = validate_live_artifacts and not _lifecycle(package, info["attempt"], repo).frozen
    amendment_ids: set[str] = set()
    for amendment in acceptance["amendments"]:
        if not isinstance(amendment, dict):
            raise StateError("amendment must be an object")
        status = amendment.get("status")
        base = {"id", "summary", "affected", "artifact", "status"}
        expected = base | ({"confirmedBy", "confirmedRevision"} if status == "CONFIRMED" else set())
        expected |= {"withdrawnReason", "withdrawnAt"} if status == "WITHDRAWN" else set()
        expected |= {field for field in ("createdAt", "confirmedAt") if field in amendment}
        if "affectedBlobs" in amendment:
            expected.add("affectedBlobs")
        if "tickets" in amendment:
            expected.add("tickets")
            tickets = amendment["tickets"]
            if not isinstance(tickets, list) or not all(isinstance(item, str) and item.strip() for item in tickets) or len(set(tickets)) != len(tickets):
                raise StateError("amendment tickets must be a list of unique Ticket IDs")
        if "supersedes" in amendment:
            expected.add("supersedes")
            superseded = amendment["supersedes"]
            if not isinstance(superseded, list) or not superseded or not all(isinstance(item, str) and item.strip() for item in superseded) or len(set(superseded)) != len(superseded):
                raise StateError("amendment supersedes must be a non-empty list of unique amendment IDs")
        if status not in {"PENDING", "CONFIRMED", "WITHDRAWN"} or set(amendment) != expected:
            raise StateError("amendment fields/status do not match PENDING, CONFIRMED or WITHDRAWN")
        if status == "WITHDRAWN":
            if not isinstance(amendment["withdrawnReason"], str) or not amendment["withdrawnReason"].strip():
                raise StateError("withdrawn amendment withdrawnReason must be non-empty")
            _validate_iso_timestamp(amendment["withdrawnAt"], "amendment withdrawnAt")
        identifier = amendment.get("id")
        if not isinstance(identifier, str) or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", identifier) is None or identifier in amendment_ids:
            raise StateError("amendment id must be unique non-empty text")
        amendment_ids.add(identifier)
        if not isinstance(amendment.get("summary"), str) or not amendment["summary"].strip():
            raise StateError(f"amendment {identifier} summary must be non-empty")
        affected = amendment.get("affected")
        if not isinstance(affected, list) or not affected:
            raise StateError(f"amendment {identifier} affected must be a non-empty path list")
        normalized_affected = []
        for item in affected:
            normalized = _package_relative_artifact(package, item, f"amendment {identifier} affected", must_exist=False)
            if "#" in normalized:
                raise StateError(f"amendment {identifier} affected paths cannot contain anchors")
            normalized_affected.append(normalized)
        if len(set(normalized_affected)) != len(normalized_affected):
            raise StateError(f"amendment {identifier} affected paths must be unique")
        amendment["affected"] = normalized_affected
        if "affectedBlobs" in amendment:
            blobs = amendment["affectedBlobs"]
            if not isinstance(blobs, dict) or set(blobs) != set(normalized_affected):
                raise StateError(f"amendment {identifier} affectedBlobs must match affected paths")
            if any(value is not None and (not isinstance(value, str) or FIXED_COMMIT_RE.fullmatch(value) is None) for value in blobs.values()):
                raise StateError(f"amendment {identifier} affectedBlobs values must be full Git blob hashes or null")
        amendment["artifact"] = _package_relative_artifact(package, amendment.get("artifact"), f"amendment {identifier} artifact", must_exist=live)
        if "createdAt" in amendment:
            _validate_iso_timestamp(amendment["createdAt"], f"amendment {identifier} createdAt")
        if status == "CONFIRMED":
            if not isinstance(amendment["confirmedBy"], str) or not amendment["confirmedBy"].strip():
                raise StateError(f"amendment {identifier} confirmedBy must be non-empty")
            amendment["confirmedRevision"] = _validate_commit(repo, amendment["confirmedRevision"])
            if "confirmedAt" in amendment:
                _validate_iso_timestamp(amendment["confirmedAt"], f"amendment {identifier} confirmedAt")
        elif "confirmedAt" in amendment:
            raise StateError(f"non-confirmed amendment {identifier} cannot contain confirmedAt")
    for amendment in acceptance["amendments"]:
        unknown = [item for item in amendment.get("supersedes", []) if item not in amendment_ids or item == amendment["id"]]
        if unknown:
            raise StateError(f"amendment {amendment['id']} supersedes unknown amendment(s): {', '.join(unknown)}")
    baseline = acceptance["contractBaseline"]
    if not isinstance(baseline, dict) or set(baseline) != {"head", "files"}:
        raise StateError("state acceptance.contractBaseline must contain head and files")
    if not isinstance(baseline["head"], str):
        raise StateError("state acceptance.contractBaseline.head must be a commit ID")
    baseline["head"] = _validate_commit(repo, baseline["head"])
    files = baseline["files"]
    if not isinstance(files, dict) or "spec.md" not in files or set(files) - {"decision.md", "spec.md", "contract-design.md"}:
        raise StateError("state acceptance.contractBaseline.files must contain spec.md and only contract document hashes")
    if any(not isinstance(value, str) or FIXED_COMMIT_RE.fullmatch(value) is None for value in files.values()):
        raise StateError("state acceptance.contractBaseline.files values must be full Git blob hashes")
    return acceptance


def _validate_state(
    package: Path,
    state: dict[str, Any],
    *,
    projections: bool = True,
    validate_live_artifacts: bool = True,
    frozen_contract_commit: str | None = None,
) -> dict[str, Any]:
    if not isinstance(state, dict):
        raise StateError("state.json must be an object")
    _state_format_version(state)
    expected = ("formatVersion", "attempt", "attemptHistory", "predecessors", "tickets", "evidenceIndex", "activeCheckpoints", "acceptance")
    if set(state) != set(expected):
        raise StateError(f"state.json must use formatVersion {FORMAT_VERSION} and contain exactly: {', '.join(expected)}")
    repo = _repo_root(package)
    attempt = state["attempt"]
    if not isinstance(attempt, dict) or set(attempt) != {"id", "plan"} or not isinstance(attempt["id"], str) or ATTEMPT_ID_RE.fullmatch(attempt["id"]) is None:
        raise StateError("state attempt must contain a valid id and plan")
    info = _plan_info(package, repo, attempt["plan"])
    acceptance = _validate_acceptance_state(package, repo, state["acceptance"], info, validate_live_artifacts=validate_live_artifacts)
    if info["attempt"] != attempt["id"]:
        raise StateError("state Attempt ID does not match current plan")
    predecessors = _normalize_state_predecessors(package, repo, state["predecessors"])
    if predecessors != info["predecessors"]:
        raise StateError("state predecessors do not match the current plan")
    lifecycle = _lifecycle(package, attempt["id"], repo)
    live_artifacts = validate_live_artifacts and lifecycle.value == "active" and frozen_contract_commit is None
    if lifecycle.frozen or frozen_contract_commit is not None:
        journey_spec = _frozen_journey_spec(
            package,
            repo,
            frozen_contract_commit or lifecycle.gate["commit"],
            acceptance,
        )
    else:
        journey_spec = _journey_spec(package)
    documents = _ticket_documents(package, attempt["id"])
    _validate_journey_coverage(journey_spec, documents)
    _validate_first_visible_step(info["harness"], journey_spec, documents)
    ticket_ids = {row["id"] for row in documents}
    tickets = state["tickets"]
    if not isinstance(tickets, dict) or set(tickets) != ticket_ids:
        raise StateError("ticket state does not match current Attempt Ticket files")
    for identifier, row in tickets.items():
        if not isinstance(row, dict) or row.get("state") not in TICKET_STATES:
            raise StateError(f"invalid Ticket state record: {identifier}")
        if row["state"] == "RETIRED":
            allowed_retired = {"state", "disposition", "evidence"} | ({"successor"} if row.get("disposition") == "superseded" else set())
            if set(row) != allowed_retired or row["disposition"] not in DISPOSITIONS or not isinstance(row["evidence"], str):
                raise StateError(f"RETIRED Ticket {identifier} requires disposition")
            _repo_relative(repo, row["evidence"], f"RETIRED {identifier} evidence", must_exist=live_artifacts)
            if row["disposition"] == "superseded" and not _valid_successor(package, row.get("successor"), identifier, attempt["id"], ticket_ids):
                raise StateError(f"RETIRED superseded Ticket {identifier} requires a valid successor (same-attempt Ticket ID or <attempt>/<ticket>)")
        elif row["state"] == "SATISFIED":
            acceptance_fields = {"revision"}
            if isinstance(row.get("acceptance"), dict) and "environment" in row["acceptance"]:
                acceptance_fields.add("environment")
            if set(row) != {"state", "acceptance"} or not isinstance(row["acceptance"], dict) or set(row["acceptance"]) != acceptance_fields:
                raise StateError(f"SATISFIED Ticket {identifier} requires acceptance revision")
            _validate_commit(repo, row["acceptance"]["revision"])
            if "environment" in row["acceptance"] and (not isinstance(row["acceptance"]["environment"], str) or not row["acceptance"]["environment"].strip()):
                raise StateError(f"SATISFIED Ticket {identifier} acceptance environment must be non-empty")
        elif row["state"] == "BLOCKED":
            if set(row) != {"state", "evidence"} or not isinstance(row["evidence"], str):
                raise StateError(f"BLOCKED Ticket {identifier} requires evidence")
            _repo_relative(repo, row["evidence"], f"BLOCKED {identifier} evidence", must_exist=live_artifacts)
        elif row["state"] == "NEEDS-REVALIDATION":
            if set(row) not in ({"state"}, {"state", "evidence"}):
                raise StateError(f"invalid NEEDS-REVALIDATION record: {identifier}")
            if "evidence" in row:
                _repo_relative(repo, row["evidence"], f"revalidation {identifier} evidence", must_exist=live_artifacts)
        elif set(row) != {"state"}:
            raise StateError(f"invalid Ticket state record: {identifier}")
    dependencies = _ticket_dependencies(documents)
    for retired_ticket, row in tickets.items():
        if row["state"] != "RETIRED" or row.get("disposition") != "superseded":
            continue
        inbound = [
            (ticket, kind)
            for ticket, edges in dependencies.items()
            for kind, dependency in edges
            if dependency == retired_ticket
        ]
        if inbound:
            raise StateError(f"superseded Ticket {retired_ticket} still has inbound edges: {inbound}")
    evidence = _validate_journey_evidence_index(package, repo, state["evidenceIndex"], journey_spec, ticket_ids, live=live_artifacts)
    checkpoints = _validate_checkpoints(repo, state["activeCheckpoints"], ticket_ids, live=live_artifacts)
    history = _attempt_history(state, package)
    if not history or history[-1]["id"] != attempt["id"]:
        raise StateError("attemptHistory must end with current Attempt")
    summary = {"formatVersion": FORMAT_VERSION, "attempt": attempt["id"], "revisions": {"decision": info["decision"], "spec": info["spec"], "plan": info["plan"]}, "predecessors": predecessors, "composition": {"tickets": True, "dag": False}, "tasks": 0, "tickets": len(tickets), "readyTickets": ready_tickets(dependencies, tickets), "gate": lifecycle.gate, "_lifecycle": lifecycle, "_info": info, "_documents": documents, "_ticketDependencies": dependencies, "_evidence": evidence, "_checkpoints": checkpoints, "_history": history, "_journeySpec": journey_spec, "_acceptance": acceptance}
    if projections:
        _validate_projections(package, state, summary)
    return summary


def _refresh_projections(package: Path, state: dict[str, Any]) -> dict[str, Any]:
    summary = _validate_state(package, state, projections=False)
    _ensure_execution_record(package, summary["attempt"])
    _write_text(package / PROGRESS_PATH, _render_progress(package, state, summary))
    _validate_projections(package, state, summary)
    return summary


def _public(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if not key.startswith("_")}
