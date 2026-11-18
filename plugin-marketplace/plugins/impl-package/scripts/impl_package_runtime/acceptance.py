"""Acceptance status derivation and progress projections."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from situation import (
    evidence_record_valid,
    evidence_revision_coverage,
)

from .attempt_store import (
    _execution_record_path,
    _parse_execution_record,
)
from .journey_evidence import (
    _validate_journey_surface_evidence,
)
from .plan_tickets import (
    _contract_amendment_findings,
    _pending_amendments,
)
from .spec_journey import (
    _journey_expected_surface,
)
from .state_core import (
    Lifecycle,
    PROGRESS_PATH,
    StateError,
    _read,
    _repo_root,
    _run_git,
)


def _escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format_aliases(revisions: dict[str, str | None]) -> str:
    values = [value for value in revisions.values() if value]
    return " / ".join(values) if values else "none (Git commit is the history anchor)"


def _v36_acceptance_status(
    package: Path,
    state: dict[str, Any],
    summary: dict[str, Any],
    comparison_commit: str,
    *,
    attempt_active: bool,
) -> dict[str, Any]:
    repo = _repo_root(package)
    spec = summary["_journeySpec"]
    records_by_key = state["evidenceIndex"]
    stale: set[str] = set()
    carried_rows: list[dict[str, str]] = []
    current_supporting_keys: set[str] = set()
    stale_journey_keys: dict[str, set[str]] = {}
    stale_run_setup_ids: set[str] = set()
    run_records: dict[tuple[str, str], list[tuple[str, dict[str, Any]]]] = {}
    run_journeys: dict[str, set[str]] = {}
    surface_validity: dict[int, bool] = {}
    first_visible = summary["_acceptance"]["harness"]["firstVisibleStep"]
    first_visible_records: list[dict[str, Any]] = []
    setup_validity: dict[tuple[str, str], bool] = {}

    def has_valid_run_setup(run_id: str, environment: str) -> bool:
        key = (run_id, environment)
        if key not in setup_validity:
            setup_validity[key] = any(
                evidence_record_valid(
                    record,
                    comparison_commit,
                    repo=repo,
                    package=package,
                    expected_environment=environment,
                    attempt_active=attempt_active,
                )
                for record in records_by_key.get(f"run-setup:{run_id}", [])
                if record.get("kind") == "run-setup"
            )
        return setup_validity[key]

    for evidence_key, records in records_by_key.items():
        for record in records:
            kind = record["kind"]
            expected_environment = spec["suites"][record["suiteId"]]["environment"] if kind == "suite" else None
            valid = evidence_record_valid(
                record,
                comparison_commit,
                repo=repo,
                package=package,
                expected_environment=expected_environment,
                attempt_active=attempt_active,
            )
            if kind == "journey-step":
                step = spec["steps"][record["stepId"]]
                try:
                    _validate_journey_surface_evidence(package, step, record)
                    surface_validity[id(record)] = True
                except (OSError, StateError):
                    surface_validity[id(record)] = False
                    valid = False
            if valid and record["conclusion"] == "supporting" and "carriedForward" in record:
                if evidence_revision_coverage(record, comparison_commit, repo=repo, package=package) == "carried":
                    carried_rows.append({
                        "key": evidence_key, "from": record["revision"], "to": record["carriedForward"]["to"],
                        "reason": record["carriedForward"]["reason"], "judgedBy": record["carriedForward"]["judgedBy"],
                    })
            if record["conclusion"] == "supporting":
                if not valid:
                    stale.add(evidence_key)
                    if kind == "journey-step":
                        stale_journey_keys.setdefault(evidence_key, set()).add(record["journeyId"])
                    elif kind == "run-setup":
                        stale_run_setup_ids.add(record["runId"])
                elif kind != "journey-step":
                    # 同 key 后补的有效 run-setup 取代旧的已失效记录；journey-step 仍按旅程是否走通判定。
                    current_supporting_keys.add(evidence_key)
            if kind == "journey-step":
                run_records.setdefault((record["journeyId"], record["runId"]), []).append((evidence_key, record))
                run_journeys.setdefault(record["runId"], set()).add(record["journeyId"])

    journey_rows = []
    complete_journeys: set[str] = set()
    for journey in spec["journeys"]:
        best_reach = 0
        best_rehearsal_reach = 0
        surface_counts = {surface: 0 for surface in ("page", "file", "api", "log")}
        manual_walkthroughs: set[tuple[str, str]] = set()
        run_rows = []
        env_valid: dict[str, list[dict[str, list[dict[str, Any]]]]] = {}
        for (journey_id, _run_id), records in run_records.items():
            if journey_id != journey["id"]:
                continue
            environments = {record["environment"] for _, record in records}
            if len(environments) != 1:
                continue
            environment = next(iter(environments))
            by_step: dict[str, list[dict[str, Any]]] = {}
            for _, record in records:
                by_step.setdefault(record["stepId"], []).append(record)
            reach = 0
            rehearsal_reach = 0
            run_surface_counts = {surface: 0 for surface in ("page", "file", "api", "log")}
            valid_by_step: dict[str, list[dict[str, Any]]] = {}
            for step in journey["steps"]:
                valid_by_step[step["id"]] = [
                    record
                    for record in by_step.get(step["id"], [])
                    if surface_validity.get(id(record), False)
                    and has_valid_run_setup(_run_id, environment)
                    and evidence_record_valid(
                        record,
                        comparison_commit,
                        repo=repo,
                        package=package,
                        expected_environment=environment,
                        attempt_active=attempt_active,
                    )
                ]
                if step["id"] == first_visible["step"]:
                    expected_surface = _journey_expected_surface(step)
                    first_visible_records.extend(
                        record for record in valid_by_step[step["id"]]
                        if record["surface"] == expected_surface
                    )
                for record in valid_by_step[step["id"]]:
                    run_surface_counts[record["surface"]] += 1
                    if record["surface"] == "page" and record.get("manualBy"):
                        manual_walkthroughs.add((step["id"], record["manualBy"]))
            for step in journey["steps"]:
                valid_records = valid_by_step[step["id"]]
                if not valid_records:
                    break
                rehearsal_reach += 1
            for step in journey["steps"]:
                valid_records = valid_by_step[step["id"]]
                if not valid_records:
                    break
                expected_surface = _journey_expected_surface(step)
                if not any(record["surface"] == expected_surface for record in valid_records):
                    break
                reach += 1
            if reach == len(journey["steps"]):
                complete_journeys.add(journey["id"])
            env_valid.setdefault(environment, []).append(valid_by_step)
            best_reach = max(best_reach, reach)
            best_rehearsal_reach = max(best_rehearsal_reach, rehearsal_reach)
            for surface, count in run_surface_counts.items():
                surface_counts[surface] += count
            run_rows.append({
                "runId": _run_id,
                "reach": reach,
                "rehearsalReach": rehearsal_reach,
                "surfaceCounts": run_surface_counts,
            })
        # 按影响范围复测：跨 run 每步取最新有效证据，承接处用 inputRef==上一步 outputRef 校验（沿用步已按 carriedForward 计入有效）。
        for runs_valid in env_valid.values():
            if len(runs_valid) < 2:
                continue
            outputs: set[str | None] | None = None
            merged = 0
            for index, step in enumerate(journey["steps"]):
                expected_surface = _journey_expected_surface(step)
                candidates = [
                    record
                    for valid_by_step in runs_valid
                    for record in valid_by_step[step["id"]]
                    if record["surface"] == expected_surface
                    and (
                        index == 0
                        or step["handoff"] == "—"
                        or (record.get("inputRef") and record["inputRef"] in outputs)
                    )
                ]
                if not candidates:
                    break
                outputs = {record.get("outputRef") for record in candidates}
                merged += 1
            if merged == len(journey["steps"]):
                complete_journeys.add(journey["id"])
            best_reach = max(best_reach, merged)
        journey_rows.append({
            "id": journey["id"],
            "title": journey["terminalResult"],
            "reach": best_reach,
            "rehearsalReach": best_rehearsal_reach,
            "total": len(journey["steps"]),
            "surfaceCounts": surface_counts,
            "runs": run_rows,
            "manualWalkthroughs": [
                {"stepId": step_id, "manualBy": manual_by}
                for step_id, manual_by in sorted(manual_walkthroughs)
            ],
        })

    stale.difference_update(current_supporting_keys)
    for evidence_key, journey_ids in stale_journey_keys.items():
        if journey_ids & complete_journeys:
            stale.discard(evidence_key)
    for run_id in stale_run_setup_ids:
        associated_journeys = run_journeys.get(run_id, set())
        if associated_journeys and associated_journeys <= complete_journeys:
            stale.discard(f"run-setup:{run_id}")

    suite_rows = []
    for suite_id, suite in spec["suites"].items():
        valid = any(
            evidence_record_valid(
                record,
                comparison_commit,
                repo=repo,
                package=package,
                expected_environment=suite["environment"],
                attempt_active=attempt_active,
            )
            for record in records_by_key.get(f"suite:{suite_id}", [])
        )
        suite_rows.append({"id": suite_id, "valid": valid})

    release_required = summary["_acceptance"]["releaseOrder"] == "required"
    release_valid = any(
        evidence_record_valid(
            record,
            comparison_commit,
            repo=repo,
            package=package,
            attempt_active=attempt_active,
        )
        for record in records_by_key.get("release", [])
        if record["kind"] == "release"
    )
    pending = _pending_amendments(summary["_acceptance"]["amendments"])
    unregistered = _contract_amendment_findings(package, repo, summary["_acceptance"])
    first_visible_ticket = first_visible["ticket"]
    return {
        "journeys": journey_rows,
        "suites": suite_rows,
        "staleEvidence": sorted(stale),
        "carriedForwardEvidence": carried_rows,
        "pendingAmendments": pending,
        "unregisteredAmendments": unregistered,
        "releaseRequired": release_required,
        "releaseValid": release_valid,
        "firstVisibleStep": dict(first_visible),
        "walkingSkeletonOverdue": state["tickets"][first_visible_ticket]["state"] == "SATISFIED" and not first_visible_records,
    }


def _journey_reaches(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> dict[str, int]:
    lifecycle: Lifecycle = summary["_lifecycle"]
    repo = _repo_root(package)
    head = _run_git(repo, "rev-parse", "HEAD")
    status = _v36_acceptance_status(package, state, summary, head, attempt_active=not lifecycle.frozen)
    return {row["id"]: row["reach"] for row in status["journeys"]}


def _render_progress(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> str:
    lifecycle: Lifecycle = summary["_lifecycle"]
    blockers = [f"ticket:{key}" for key, row in state["tickets"].items() if row["state"] == "BLOCKED"]
    lines = [f"# Attempt Progress · {summary['attempt']}", "", "> machine-owned projection；使用 `refresh-progress` 重建，不直接编辑。", "", f"- Attempt: {summary['attempt']}", f"- Contract aliases: {_format_aliases(summary['revisions'])}", "- Composition: tickets=true, dag=false", f"- Lifecycle: {lifecycle.value}", f"- Latest gate: {lifecycle.gate_verdict}", f"- Blockers: {', '.join(blockers) if blockers else 'none'}"]
    spec = summary["_journeySpec"]
    status = _v36_acceptance_status(
        package,
        state,
        summary,
        _run_git(_repo_root(package), "rev-parse", "HEAD"),
        attempt_active=not lifecycle.frozen,
    )
    reaches = {row["id"]: row for row in status["journeys"]}
    lines.extend(["", "## Journey Progress", ""])
    for journey in spec["journeys"]:
        progress = reaches[journey["id"]]
        total = len(journey["steps"])
        lines.append(
            f"- {journey['id']} 有效步骤走通 {progress['reach']}/{total} · "
            f"API 预演 {progress['rehearsalReach']}/{total}"
        )
    lines.extend(["", "## Required Suite Results", "", "| Suite | Kind | Scope | Latest conclusion |", "| --- | --- | --- | --- |"])
    for suite_id, suite in spec["suites"].items():
        records = state["evidenceIndex"].get(f"suite:{suite_id}", [])
        latest = records[-1] if records else None
        valid = any(row["id"] == suite_id and row["valid"] for row in status["suites"])
        conclusion = "supporting" if valid else ("待复验" if latest and latest["conclusion"] == "supporting" else latest["conclusion"] if latest else "none")
        if latest and latest.get("invalidatedBy") and not valid:
            conclusion = "待复验"
        lines.append(f"| {suite_id} | {suite['kind']} | {suite['scope']} | {conclusion} |")
    if not spec["suites"]:
        lines.append("| none | none | none | none |")
    lines.extend(["", "## Ticket Status", "", "| Ticket | State | Journey steps | Suites |", "| --- | --- | --- | --- |"])
    for document in summary["_documents"]:
        identifier = document["id"]
        coverage = document["coverage"]
        lines.append(f"| {identifier} | {state['tickets'][identifier]['state']} | {_escape(', '.join(coverage['journeySteps']) or 'none')} | {_escape(', '.join(coverage['suites']) or 'none')} |")
    lines.extend(["", "## Active Checkpoints", "", "| Subject | Status | Next action | Evidence |", "| --- | --- | --- | --- |"])
    checkpoints = state["activeCheckpoints"] if not lifecycle.frozen else {}
    if checkpoints:
        for subject, row in checkpoints.items():
            lines.append(f"| {subject} | active | {_escape(row['next'])} | {_escape(', '.join(row['evidence']) or 'none')} |")
    else:
        lines.append("| none | none | none | none |")
    lines.extend(["", "## Attempt History", "", "| Attempt | Lifecycle | Gate | Execution Record |", "| --- | --- | --- | --- |"])
    for row in state["attemptHistory"]:
        gate = row["gate"].get("verdict", "open") if isinstance(row["gate"], dict) else "open"
        lines.append(f"| {row['id']} | {row['lifecycle']} | {gate} | {row['executionRecord']} |")
    return "\n".join(lines) + "\n"


def _validate_projections(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> None:
    for document in summary["_documents"]:
        if document["publication"] != "Approved":
            raise StateError(f"Ticket {document['id']} must be Approved")
    er_path = _execution_record_path(package, summary["attempt"])
    metadata, _ = _parse_execution_record(er_path, summary["attempt"], entries=False)
    lifecycle: Lifecycle = summary["_lifecycle"]
    if metadata != {"attempt": lifecycle.attempt, "lifecycle": lifecycle.value, "gate": lifecycle.gate_verdict}:
        raise StateError("current Attempt Execution Record lifecycle projection mismatch")
    expected_progress = _render_progress(package, state, summary)
    if not (package / PROGRESS_PATH).is_file() or _read(package / PROGRESS_PATH) != expected_progress:
        raise StateError("progress projection mismatch; run refresh-progress")
