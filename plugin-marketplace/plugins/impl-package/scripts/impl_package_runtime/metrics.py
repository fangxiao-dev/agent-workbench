"""Read-only package execution metrics."""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import engine
import review_track_stats


TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")
TRACKS = ("Track A", "Track B", "Track C", "Track D")
IMPACTS = ("seam", "safety", "local", "unknown")


def _nonnegative_number(value: Any) -> bool:
    return (
        type(value) is int and value >= 0
        or type(value) is float and math.isfinite(value) and value >= 0
    )


def _metric(value: Any, source: Any, missing: str | None = None) -> dict[str, Any]:
    return {"value": value, "source": source, "missingReason": missing}


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _trail_rows(package: Path, attempt: str) -> tuple[list[dict[str, Any]], list[str], list[str]]:
    directory = package / "execution" / attempt
    archives = sorted(
        (path for path in directory.glob("trail.[0-9][0-9][0-9].jsonl") if path.is_file()),
        key=lambda path: int(TRAIL_ARCHIVE_RE.fullmatch(path.name).group(1)),
    ) if directory.is_dir() else []
    active = directory / "trail.jsonl"
    paths = [*archives, *([active] if active.is_file() else [])]
    rows: list[dict[str, Any]] = []
    warnings: list[str] = []
    sources: list[str] = []
    for path in paths:
        relative = path.relative_to(package).as_posix()
        sources.append(relative)
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except (OSError, UnicodeError):
            warnings.append(f"cannot read {relative}")
            continue
        for line_number, line in enumerate(lines, start=1):
            if not line.strip():
                continue
            source = f"{relative}:{line_number}"
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                warnings.append(f"{source}: invalid JSON ({exc.msg})")
                continue
            if not isinstance(value, dict):
                warnings.append(f"{source}: row is not an object")
                continue
            rows.append({"row": value, "source": source})
    if not paths:
        sources = [f"execution/{attempt}/trail*.jsonl (no files found)"]
    return rows, sources, warnings


def _row_order(entry: dict[str, Any]) -> tuple[float, int, int]:
    row = entry["row"]
    parsed = _parse_time(row.get("ts"))
    timestamp = parsed.timestamp() if parsed else math.inf
    seq = row.get("seq")
    return (timestamp, seq if type(seq) is int else 2**63, entry.get("index", 0))


def _read_selected_state(package: Path, state: dict[str, Any], attempt: str, history_row: dict[str, Any]) -> dict[str, Any] | None:
    if state.get("attempt", {}).get("id") == attempt:
        return state
    archive = package / ".impl-package" / "attempts" / f"{attempt}.json"
    if archive.is_file():
        try:
            snapshot = engine._load_json(archive)
            if snapshot.get("attempt") == attempt and isinstance(snapshot.get("tickets"), dict):
                return {"attempt": {"id": attempt}, "tickets": snapshot["tickets"]}
        except engine.StateError:
            pass
    gate = history_row.get("gate")
    commit = gate.get("commit") if isinstance(gate, dict) else None
    if isinstance(commit, str):
        repo = engine._repo_root(package)
        state_path = (package / engine.STATE_PATH).resolve().relative_to(repo).as_posix()
        code, stdout, _ = engine._run_git_result(repo, "show", f"{commit}:{state_path}", encoding="utf-8")
        if code == 0:
            try:
                historical = json.loads(stdout)
                if isinstance(historical, dict) and historical.get("attempt", {}).get("id") == attempt:
                    return historical
            except json.JSONDecodeError:
                pass
    return None


def _ticket_event(rows: list[dict[str, Any]], ticket: str) -> dict[str, Any] | None:
    matches = [
        entry for entry in rows
        if entry["row"].get("kind") == "result"
        and entry["row"].get("transition") == "ticket-state"
        and entry["row"].get("subject") == f"ticket:{ticket}"
        and entry["row"].get("to") == "SATISFIED"
    ]
    return min(matches, key=_row_order) if matches else None


def _dispatch_metrics(rows: list[dict[str, Any]], ticket_ids: list[str], trail_sources: list[str]) -> tuple[dict[str, Any], dict[str, list[dict[str, Any]]]]:
    dispatches = [entry for entry in rows if entry["row"].get("kind") == "dispatch"]
    returns: dict[str, list[dict[str, Any]]] = {}
    for entry in rows:
        row = entry["row"]
        if row.get("kind") == "worker-return" and isinstance(row.get("of"), str):
            returns.setdefault(row["of"], []).append(entry)

    modes: dict[str, list[dict[str, Any]]] = {mode: [] for mode in ("investigate", "implement", "fix", "verify")}
    modes.setdefault("unknown", [])
    for entry in dispatches:
        mode = entry["row"].get("mode")
        modes.setdefault(mode if isinstance(mode, str) else "unknown", []).append(entry)

    durations = []
    for dispatch in dispatches:
        row = dispatch["row"]
        dispatch_id = row.get("dispatch_id")
        matches = returns.get(dispatch_id, []) if isinstance(dispatch_id, str) else []
        source = dispatch["source"]
        if len(matches) != 1:
            reason = "no matching worker-return" if not matches else "multiple worker-returns match dispatch"
            durations.append({"dispatchId": dispatch_id, "seconds": _metric(None, source, reason)})
            continue
        returned = matches[0]
        start = _parse_time(row.get("ts"))
        end = _parse_time(returned["row"].get("endedAt"))
        end_source = "endedAt"
        if end is None:
            end = _parse_time(returned["row"].get("ts"))
            end_source = "worker-return.ts"
        duration_source = [source, f"{returned['source']} ({end_source})"]
        if start is None or end is None:
            reason = "dispatch ts or worker-return end time is missing or invalid"
            seconds = None
        elif end < start:
            reason = "worker-return end time precedes dispatch ts"
            seconds = None
        else:
            reason = None
            seconds = round((end - start).total_seconds(), 6)
        durations.append({
            "dispatchId": _metric(dispatch_id, source, None if dispatch_id is not None else "dispatch_id is missing"),
            "seconds": _metric(seconds, duration_source, reason),
        })

    ticket_counts: dict[str, Any] = {}
    for ticket in ticket_ids:
        own = [entry for entry in dispatches if entry["row"].get("subject") == f"ticket:{ticket}"]
        counts = {
            "fix": sum(entry["row"].get("mode") == "fix" for entry in own),
            "verify": sum(entry["row"].get("mode") == "verify" for entry in own),
            "review": sum(entry["row"].get("mode") == "review" or bool(entry["row"].get("review_track")) for entry in own),
        }
        source = [entry["source"] for entry in own] or trail_sources
        ticket_counts[ticket] = {
            mode: _metric(count, source, None if own else "no dispatch recorded for this Ticket")
            for mode, count in counts.items()
        }
        ticket_counts[ticket]["repeatedFix"] = _metric(
            max(0, counts["fix"] - 1), source,
            None if own else "no dispatch recorded for this Ticket",
        )

    return {
        "total": _metric(len(dispatches), trail_sources),
        "byMode": {mode: _metric(len(entries), [item["source"] for item in entries] or trail_sources) for mode, entries in modes.items()},
        "durations": durations,
        "ticketCounts": ticket_counts,
    }, dispatches


def _ticket_metrics(
    ticket_ids: list[str], rows: list[dict[str, Any]], selected_state: dict[str, Any] | None,
    state_source: str, trail_sources: list[str],
) -> dict[str, Any]:
    result: dict[str, Any] = {}
    tickets = selected_state.get("tickets") if isinstance(selected_state, dict) else None
    for ticket in ticket_ids:
        starts = [
            entry for entry in rows
            if entry["row"].get("kind") == "dispatch" and entry["row"].get("subject") == f"ticket:{ticket}"
        ]
        start = min(starts, key=_row_order) if starts else None
        satisfied = _ticket_event(rows, ticket)
        duration = None
        duration_source: Any = [entry["source"] for entry in starts] or trail_sources
        reason = None
        if start is None:
            reason = "no dispatch recorded for this Ticket"
        elif satisfied is None:
            duration_source = [start["source"], *trail_sources]
            reason = "no SATISFIED result recorded"
        else:
            start_time = _parse_time(start["row"].get("ts"))
            end_time = _parse_time(satisfied["row"].get("ts"))
            duration_source = [start["source"], satisfied["source"]]
            if start_time is None or end_time is None:
                reason = "dispatch or SATISFIED result ts is missing or invalid"
            elif end_time < start_time:
                reason = "SATISFIED result precedes the first dispatch"
            else:
                duration = round((end_time - start_time).total_seconds(), 6)
        state_value = tickets.get(ticket) if isinstance(tickets, dict) else None
        result[ticket] = {
            "state": _metric(state_value, state_source, None if state_value is not None else "Ticket state snapshot is unavailable"),
            "firstDispatchAt": _metric(start["row"].get("ts") if start else None, start["source"] if start else trail_sources, "no dispatch recorded for this Ticket" if start is None else (None if _parse_time(start["row"].get("ts")) else "dispatch ts is missing or invalid")),
            "satisfiedAt": _metric(satisfied["row"].get("ts") if satisfied else None, satisfied["source"] if satisfied else trail_sources, "no SATISFIED result recorded" if satisfied is None else (None if _parse_time(satisfied["row"].get("ts")) else "SATISFIED result ts is missing or invalid")),
            "wallClockSeconds": _metric(duration, duration_source, reason),
        }
    return result


def _critical_path_metrics(
    dependencies: dict[str, list[tuple[str, str]]] | None,
    ticket_ids: list[str], rows: list[dict[str, Any]], dispatches: list[dict[str, Any]], trail_sources: list[str],
) -> dict[str, Any]:
    if dependencies is None:
        return {
            "edges": _metric(None, "Ticket dependency documents", "Ticket dependency graph could not be read"),
            "dispatchesBeforeFirstDownstreamImplement": _metric(None, trail_sources, "Ticket dependency graph could not be read"),
        }
    edges = []
    downstream_implementations = []
    for downstream in ticket_ids:
        for kind, upstream in dependencies.get(downstream, []):
            if kind != "implementation":
                continue
            sat = _ticket_event(rows, upstream)
            candidates = [
                entry for entry in dispatches
                if entry["row"].get("subject") == f"ticket:{downstream}" and entry["row"].get("mode") == "implement"
            ]
            implementation = min(candidates, key=_row_order) if candidates else None
            if implementation:
                downstream_implementations.append(implementation)
            sat_source = sat["source"] if sat else trail_sources
            impl_source = implementation["source"] if implementation else trail_sources
            sat_time = _parse_time(sat["row"].get("ts")) if sat else None
            impl_time = _parse_time(implementation["row"].get("ts")) if implementation else None
            wait = None
            wait_reason = None
            if sat is None:
                wait_reason = "upstream Ticket has no SATISFIED result"
            elif implementation is None:
                wait_reason = "downstream Ticket has no implement dispatch"
            elif sat_time is None or impl_time is None:
                wait_reason = "upstream result or downstream dispatch ts is missing or invalid"
            elif impl_time < sat_time:
                wait_reason = "downstream implement dispatch precedes upstream SATISFIED result"
            else:
                wait = round((impl_time - sat_time).total_seconds(), 6)
            sat_seq = sat["row"].get("seq") if sat else None
            impl_seq = implementation["row"].get("seq") if implementation else None
            upstream_spent = None
            if type(sat_seq) is int:
                upstream_spent = sum(
                    entry["row"].get("subject") == f"ticket:{upstream}"
                    and type(entry["row"].get("seq")) is int
                    and entry["row"]["seq"] < sat_seq
                    for entry in dispatches
                )
            package_before = None
            if type(impl_seq) is int:
                package_before = sum(type(entry["row"].get("seq")) is int and entry["row"]["seq"] < impl_seq for entry in dispatches)
            source = [item for item in (sat_source, impl_source) if isinstance(item, str)]
            edges.append({
                "upstream": _metric(upstream, "Ticket dependency documents"),
                "downstream": _metric(downstream, "Ticket dependency documents"),
                "upstreamSatisfiedAt": _metric(sat["row"].get("ts") if sat else None, sat_source, "no SATISFIED result" if sat is None else (None if sat_time else "invalid result ts")),
                "firstImplementDispatchAt": _metric(implementation["row"].get("ts") if implementation else None, impl_source, "no implement dispatch" if implementation is None else (None if impl_time else "invalid dispatch ts")),
                "waitSeconds": _metric(wait, source or trail_sources, wait_reason),
                "upstreamDispatchesBeforeSatisfied": _metric(upstream_spent, [entry["source"] for entry in dispatches] or trail_sources, "upstream SATISFIED result has no valid seq" if upstream_spent is None else None),
                "packageDispatchesBeforeDownstreamImplement": _metric(package_before, [entry["source"] for entry in dispatches] or trail_sources, "downstream implement dispatch has no valid seq" if package_before is None else None),
            })
    first_implementation = min(downstream_implementations, key=_row_order) if downstream_implementations else None
    before_count = None
    reason = None
    if first_implementation is None:
        reason = "no downstream implementation dispatch recorded"
    elif type(first_implementation["row"].get("seq")) is not int:
        reason = "first downstream implement dispatch has no valid seq"
    else:
        before_count = sum(
            type(entry["row"].get("seq")) is int
            and entry["row"]["seq"] < first_implementation["row"]["seq"]
            for entry in dispatches
        )
    return {
        "edges": _metric(edges, [entry["source"] for entry in dispatches] or trail_sources, None),
        "dispatchesBeforeFirstDownstreamImplement": _metric(
            before_count, first_implementation["source"] if first_implementation else trail_sources, reason,
        ),
    }


def _review_metrics(package: Path, attempt: str, version: str, rows: list[dict[str, Any]], ticket_ids: list[str], upstream_tickets: set[str]) -> tuple[dict[str, Any], list[dict[str, Any]], list[str]]:
    stats = review_track_stats.calculate_review_stats(package, attempt)
    canonical_sources = [
        entry["source"] for entry in rows
        if entry["row"].get("kind") == "fact" and entry["row"].get("key") == review_track_stats.FACT_KEY
    ]
    terminal_rows = [
        entry for entry in rows
        if entry["row"].get("kind") == "fact" and entry["row"].get("key") == "review.terminal_summary"
    ]
    terminal = max(terminal_rows, key=_row_order) if terminal_rows else None
    warnings = list(stats.get("coverage", {}).get("warnings", []))

    valid_summaries = []
    for entry in rows:
        row = entry["row"]
        if row.get("kind") != "fact" or row.get("key") != review_track_stats.FACT_KEY:
            continue
        if not review_track_stats._valid_row_metadata(row, entry["source"], warnings):
            continue
        try:
            value = review_track_stats.validate_canonical_summary(
                row.get("value"), allow_empty_tracks=True, format_version=version,
            )
        except review_track_stats.ReviewStatsError as exc:
            warnings.append(f"{entry['source']}: invalid canonical summary: {exc}")
            continue
        valid_summaries.append({"summary": value, "entry": entry})

    latest_runs: dict[str, dict[str, Any]] = {}
    for item in valid_summaries:
        run_id = item["summary"]["reviewRunId"]
        previous = latest_runs.get(run_id)
        if previous is None or _row_order(item["entry"]) >= _row_order(previous["entry"]):
            latest_runs[run_id] = item
    latest_findings: dict[str, dict[str, Any]] = {}
    for item in latest_runs.values():
        for finding in item["summary"]["findings"]:
            key = finding["findingKey"]
            previous = latest_findings.get(key)
            if previous is None or _row_order(item["entry"]) >= _row_order(previous["entry"]):
                latest_findings[key] = {"finding": finding, "entry": item["entry"]}
    findings = list(latest_findings.values())
    by_impact = {}
    for impact in IMPACTS:
        count = sum(item["finding"].get("impact") == impact for item in findings)
        by_impact[impact] = _metric(count, [item["entry"]["source"] for item in findings] or canonical_sources, None)
    unclassified = sum("impact" not in item["finding"] for item in findings)
    by_impact["unclassified"] = _metric(
        unclassified, [item["entry"]["source"] for item in findings] or canonical_sources,
        "3.5 findings may omit impact" if unclassified else None,
    )
    upstream_associations = [
        item for item in findings
        for ticket in item["finding"].get("ticketIds", [])
        if ticket in upstream_tickets
    ]
    severe = sum(item["finding"].get("impact") in {"seam", "safety"} for item in upstream_associations)
    denominator = len(upstream_associations)
    ratio = severe / denominator if denominator else None
    ratio_reason = None if denominator else (
        "no upstream Ticket findings" if upstream_tickets else "no Ticket has a downstream implementation dependency"
    )
    return {
        "total": _metric(stats["totals"]["unique"], canonical_sources, None if stats["coverage"]["summaries"] else "no valid canonical summary facts"),
        "byTrack": {track: _metric(stats["tracks"][track]["caught"], canonical_sources, None if stats["coverage"]["summaries"] else "no valid canonical summary facts") for track in TRACKS},
        "byTicket": {
            ticket: _metric(stats.get("tickets", {}).get(ticket, {}).get("unique", 0), canonical_sources,
                            None if stats["coverage"]["summaries"] else "no valid canonical summary facts")
            for ticket in ticket_ids
        },
        "byImpact": by_impact,
        "upstreamSeamSafetyRatio": _metric(
            {"numerator": severe, "denominator": denominator, "ratio": ratio}, canonical_sources, ratio_reason,
        ),
        "terminalSummary": _metric(
            terminal["row"].get("value") if terminal else None,
            terminal["source"] if terminal else ["review.terminal_summary trail facts"],
            None if terminal else "no review.terminal_summary fact",
        ),
        "reviewSummaryCount": _metric(len(valid_summaries), canonical_sources, None if valid_summaries else "no valid canonical summary facts"),
    }, findings, warnings


def _journey_metrics(
    package: Path, version: str, state: dict[str, Any] | None, history_row: dict[str, Any],
    trail_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    source = ".impl-package/state.json evidenceIndex"
    if version != "3.6":
        return _metric(None, source, "Journey metrics require formatVersion 3.6")
    if not isinstance(state, dict) or not isinstance(state.get("evidenceIndex"), dict):
        return _metric(None, source, "selected Attempt evidenceIndex is unavailable")
    try:
        spec = engine._journey_spec(package)
    except engine.StateError as exc:
        return _metric(None, "spec.md", f"Journey Spec could not be read: {exc}")
    gate = history_row.get("gate")
    comparison = gate.get("commit") if isinstance(gate, dict) else None
    if not isinstance(comparison, str):
        repo = engine._repo_root(package)
        comparison = engine._run_git(repo, "rev-parse", "HEAD")
    attempt_active = history_row.get("lifecycle") == "active"
    repo = engine._repo_root(package)
    harness = state.get("acceptance", {}).get("harness") if isinstance(state.get("acceptance"), dict) else None
    if not isinstance(harness, dict):
        info = engine._plan_info(package, repo, history_row["plan"])
        harness = {"firstVisibleStep": info["harness"]["firstVisibleStep"]}
    first_visible = harness["firstVisibleStep"]
    first_visible_step = spec["steps"].get(first_visible["step"])
    if first_visible_step is None:
        return _metric(None, "plan.md and spec.md", "First visible step is missing from the Journey Spec")
    if trail_rows is None:
        trail_rows, _, _ = _trail_rows(package, str(history_row["id"]))
    first_dispatch_times = [
        timestamp
        for entry in trail_rows
        if entry["row"].get("kind") == "dispatch"
        if (timestamp := _parse_time(entry["row"].get("ts"))) is not None
    ]
    first_dispatch = min(first_dispatch_times) if first_dispatch_times else None
    records = [
        record
        for group in state["evidenceIndex"].values()
        if isinstance(group, list)
        for record in group
        if isinstance(record, dict) and record.get("kind") == "journey-step"
    ]
    setup_records = {
        run_id: [
            record for record in group
            if isinstance(record, dict) and record.get("kind") == "run-setup"
        ]
        for key, group in state["evidenceIndex"].items()
        if isinstance(group, list) and key.startswith("run-setup:")
        for run_id in [key.removeprefix("run-setup:")]
    }
    valid_setup_cache: dict[tuple[str, str], list[dict[str, Any]]] = {}

    def valid_setups(run_id: str, environment: str) -> list[dict[str, Any]]:
        key = (run_id, environment)
        if key not in valid_setup_cache:
            valid_setup_cache[key] = [
                record for record in setup_records.get(run_id, [])
                if engine.evidence_record_valid(
                    record, comparison, repo=repo, package=package,
                    expected_environment=environment, attempt_active=attempt_active,
                )
            ]
        return valid_setup_cache[key]

    output = []
    first_visible_matches: list[dict[str, Any]] = []
    for journey in spec["journeys"]:
        steps = journey["steps"]
        runs: dict[str, list[dict[str, Any]]] = {}
        for record in records:
            if record.get("journeyId") == journey["id"] and isinstance(record.get("runId"), str):
                runs.setdefault(record["runId"], []).append(record)
        run_rows = []
        for run_id, run_records in sorted(runs.items()):
            environments = {record.get("environment") for record in run_records}
            environment = next(iter(environments)) if len(environments) == 1 else None
            valid_by_step: dict[str, list[dict[str, Any]]] = {}
            for step in steps:
                for record in run_records:
                    if record.get("stepId") != step["id"] or environment is None:
                        continue
                    if not valid_setups(run_id, environment):
                        continue
                    if not engine.evidence_record_valid(
                        record, comparison, repo=repo, package=package,
                        expected_environment=environment, attempt_active=attempt_active,
                    ):
                        continue
                    try:
                        engine._validate_journey_surface_evidence(package, step, record)
                    except (OSError, engine.StateError):
                        continue
                    valid_by_step.setdefault(step["id"], []).append(record)
            if first_visible_step["journeyId"] == journey["id"]:
                first_visible_matches.extend(
                    record for record in valid_by_step.get(first_visible["step"], [])
                    if record.get("surface") == engine._journey_expected_surface(first_visible_step)
                )
            step_rows = []
            for step in steps:
                valid = valid_by_step.get(step["id"], [])
                timed = [(record, _parse_time(record.get("recordedAt"))) for record in valid]
                timed = [(record, timestamp) for record, timestamp in timed if timestamp is not None]
                first = min(timed, key=lambda item: item[1]) if timed else None
                step_rows.append({
                    "stepId": _metric(step["id"], "spec.md"),
                    "validRecordCount": _metric(len(valid), ".impl-package/state.json evidenceIndex"),
                    "surfaceCounts": {
                        surface: _metric(sum(record.get("surface") == surface for record in valid), ".impl-package/state.json evidenceIndex")
                        for surface in ("page", "file", "api", "log")
                    },
                    "firstValidAt": _metric(
                        first[0].get("recordedAt") if first else None,
                        ".impl-package/state.json evidenceIndex",
                        None if first else ("valid evidence has no valid recordedAt" if valid else "no valid evidence for this step"),
                    ),
                })
            first_step = steps[0]["id"] if steps else None
            last_step = steps[-1]["id"] if steps else None
            first_records = [record for record in run_records if record.get("stepId") == first_step]
            last_records = [record for record in run_records if record.get("stepId") == last_step]
            first_times = [_parse_time(record.get("recordedAt")) for record in first_records]
            last_times = [_parse_time(record.get("recordedAt")) for record in last_records]
            first_times = [value for value in first_times if value is not None]
            last_times = [value for value in last_times if value is not None]
            start_time = min(first_times) if first_times else None
            end_time = max(last_times) if last_times else None
            interval = round((end_time - start_time).total_seconds(), 6) if start_time and end_time and end_time >= start_time else None
            timed_setups = [
                (record, timestamp)
                for record in valid_setups(run_id, environment or "")
                if (timestamp := _parse_time(record.get("recordedAt"))) is not None
            ] if environment is not None else []
            first_setup = min(timed_setups, key=lambda item: item[1]) if timed_setups else None
            setup_time = first_setup[1] if first_setup else None
            first_run_step_times = [
                timestamp
                for record in valid_by_step.get(first_step, [])
                if first_step is not None and record.get("surface") == engine._journey_expected_surface(steps[0])
                if (timestamp := _parse_time(record.get("recordedAt"))) is not None
            ] if steps else []
            first_run_step_time = min(first_run_step_times) if first_run_step_times else None
            setup_to_first_step = (
                round((first_run_step_time - setup_time).total_seconds(), 6)
                if setup_time is not None and first_run_step_time is not None and first_run_step_time >= setup_time
                else None
            )
            missing_steps = [step["id"] for step in steps if not valid_by_step.get(step["id"])]
            page_missing_steps = [
                step["id"] for step in steps
                if not any(
                    record.get("surface") == engine._journey_expected_surface(step)
                    for record in valid_by_step.get(step["id"], [])
                )
            ]
            rehearsal_reach = 0
            page_reach = 0
            for step in steps:
                valid = valid_by_step.get(step["id"], [])
                if not valid:
                    break
                rehearsal_reach += 1
            for step in steps:
                valid = valid_by_step.get(step["id"], [])
                if not valid:
                    break
                expected_surface = engine._journey_expected_surface(step)
                if not any(record.get("surface") == expected_surface for record in valid):
                    break
                page_reach += 1
            valid_records = [record for step_records in valid_by_step.values() for record in step_records]
            surface_counts = {
                surface: sum(record.get("surface") == surface for record in valid_records)
                for surface in ("page", "file", "api", "log")
            }
            complete = bool(steps) and environment is not None and page_reach == len(steps)
            rehearsal_complete = bool(steps) and environment is not None and rehearsal_reach == len(steps)
            run_rows.append({
                "runId": _metric(run_id, ".impl-package/state.json evidenceIndex"),
                "stepCount": _metric(len(run_records), ".impl-package/state.json evidenceIndex"),
                "uniqueStepCount": _metric(len({record.get("stepId") for record in run_records}), ".impl-package/state.json evidenceIndex"),
                "pageReach": _metric(page_reach, "spec.md and .impl-package/state.json evidenceIndex"),
                "rehearsalReach": _metric(rehearsal_reach, "spec.md and .impl-package/state.json evidenceIndex"),
                "surfaceCounts": {
                    surface: _metric(count, ".impl-package/state.json evidenceIndex")
                    for surface, count in surface_counts.items()
                },
                "firstLastRecordedAtSeconds": _metric(
                    interval, ".impl-package/state.json evidenceIndex",
                    None if interval is not None else "first or last step recordedAt is missing or invalid",
                ),
                "setupAt": _metric(
                    first_setup[0].get("recordedAt") if first_setup else None,
                    ".impl-package/state.json evidenceIndex",
                    None if setup_time is not None else ("valid run-setup has no valid recordedAt" if valid_setups(run_id, environment or "") else "no valid run-setup"),
                ),
                "setupToFirstStepSeconds": _metric(
                    setup_to_first_step,
                    ".impl-package/state.json evidenceIndex",
                    None if setup_to_first_step is not None else "setup or first step recordedAt is missing, invalid, or out of order",
                ),
                "steps": step_rows,
                "complete": _metric(complete, ".impl-package/state.json evidenceIndex and final comparison revision",
                                     None if complete else (f"no valid page/file/log evidence for Journey steps: {', '.join(page_missing_steps)}" if environment is not None else "run contains multiple environments")),
                "rehearsalComplete": _metric(rehearsal_complete, ".impl-package/state.json evidenceIndex and final comparison revision",
                                              None if rehearsal_complete else (f"no valid evidence for Journey steps: {', '.join(missing_steps)}" if environment is not None else "run contains multiple environments")),
            })
        best_page_reach = max((row["pageReach"]["value"] for row in run_rows), default=0)
        best_rehearsal_reach = max((row["rehearsalReach"]["value"] for row in run_rows), default=0)
        journey_surface_counts = {
            surface: sum(row["surfaceCounts"][surface]["value"] for row in run_rows)
            for surface in ("page", "file", "api", "log")
        }
        output.append({
            "journeyId": _metric(journey["id"], "spec.md"),
            "preparation": _metric(journey["preparation"], "spec.md", "no preparation note"),
            "runCount": _metric(len(runs), ".impl-package/state.json evidenceIndex"),
            "runs": _metric(run_rows, ".impl-package/state.json evidenceIndex", None),
            "pageReach": _metric(best_page_reach, "spec.md and .impl-package/state.json evidenceIndex"),
            "rehearsalReach": _metric(best_rehearsal_reach, "spec.md and .impl-package/state.json evidenceIndex"),
            "surfaceCounts": {
                surface: _metric(count, ".impl-package/state.json evidenceIndex")
                for surface, count in journey_surface_counts.items()
            },
            "complete": _metric(any(row["complete"]["value"] is True for row in run_rows), ".impl-package/state.json evidenceIndex and final comparison revision",
                                 None if run_rows else "no run recorded for this Journey"),
            "rehearsalComplete": _metric(any(row["rehearsalComplete"]["value"] is True for row in run_rows), ".impl-package/state.json evidenceIndex and final comparison revision",
                                          None if run_rows else "no run recorded for this Journey"),
        })
    first_visible_timed = [
        (record, timestamp)
        for record in first_visible_matches
        if (timestamp := _parse_time(record.get("recordedAt"))) is not None
    ]
    first_visible_recorded_at = min(first_visible_timed, key=lambda item: item[1])[0].get("recordedAt") if first_visible_timed else None
    visible_time = min((item[1] for item in first_visible_timed), default=None)
    first_visible_delay = (
        round((visible_time - first_dispatch).total_seconds(), 6)
        if visible_time is not None and first_dispatch is not None and visible_time >= first_dispatch
        else None
    )
    result = _metric(output, source, None)
    result["firstVisibleStep"] = {
        "declared": _metric(
            {"step": first_visible["step"], "ticket": first_visible["ticket"]},
            "plan.md",
        ),
        "firstRecordedAt": _metric(
            first_visible_recorded_at,
            ".impl-package/state.json evidenceIndex",
            None if first_visible_recorded_at is not None else "no valid matching first-visible-step record with recordedAt",
        ),
        "secondsFromFirstDispatch": _metric(
            first_visible_delay,
            ".impl-package/state.json evidenceIndex and execution trail",
            None if first_visible_delay is not None else "first matching record or first dispatch is missing, invalid, or out of order",
        ),
    }
    return result


def _amendment_metrics(version: str, state: dict[str, Any] | None) -> dict[str, Any]:
    source = ".impl-package/state.json acceptance.amendments"
    if version != "3.6":
        return _metric(None, source, "Amendments require formatVersion 3.6")
    if not isinstance(state, dict) or not isinstance(state.get("acceptance"), dict):
        return _metric(None, source, "selected Attempt acceptance data is unavailable")
    amendments = state["acceptance"].get("amendments")
    if not isinstance(amendments, list):
        return _metric(None, source, "acceptance.amendments is missing or invalid")
    output = []
    for amendment in amendments:
        if not isinstance(amendment, dict):
            continue
        created = _parse_time(amendment.get("createdAt"))
        confirmed = _parse_time(amendment.get("confirmedAt"))
        elapsed = round((confirmed - created).total_seconds(), 6) if created and confirmed and confirmed >= created else None
        reason = None if elapsed is not None else (
            "createdAt is missing or invalid" if created is None else
            "amendment is not confirmed (confirmedAt is missing)" if confirmed is None else
            "confirmedAt precedes createdAt"
        )
        output.append({
            "id": _metric(amendment.get("id"), source),
            "createdAt": _metric(amendment.get("createdAt"), source, None if created else "createdAt is missing or invalid"),
            "confirmedAt": _metric(amendment.get("confirmedAt"), source, None if confirmed else "amendment is not confirmed or confirmedAt is missing"),
            "elapsedSeconds": _metric(elapsed, source, reason),
        })
    return _metric(output, source, None)


def _usage_metrics(worker_returns: list[dict[str, Any]], trail_sources: list[str]) -> tuple[dict[str, Any], dict[str, Any]]:
    returns = [entry for entry in worker_returns]
    values: dict[str, list[tuple[float, str]]] = {"input": [], "output": [], "costUsd": []}
    failures = {name: [] for name in ("flaky", "env", "real")}
    for entry in returns:
        row = entry["row"]
        usage = row.get("usage")
        if isinstance(usage, dict):
            for field in ("input", "output", "costUsd"):
                value = usage.get(field)
                if field in usage and _nonnegative_number(value):
                    values[field].append((value, entry["source"]))
        failure = row.get("failureClass")
        if isinstance(failure, str) and failure in failures:
            failures[failure].append(entry["source"])
    usage_report = {}
    for field, entries in values.items():
        total = sum(value for value, _source in entries) if entries else None
        reason = None if entries else f"no worker-return usage.{field} values recorded"
        usage_report[field] = _metric(total, [source for _value, source in entries] or trail_sources, reason)
        usage_report[field]["recordCount"] = len(entries)
    failure_report = {
        "counts": {name: _metric(len(sources), sources or trail_sources) for name, sources in failures.items()},
        "total": _metric(sum(map(len, failures.values())), [entry["source"] for entry in returns] or trail_sources,
                         None if returns else "no worker-return records"),
    }
    return usage_report, failure_report


def _coverage(version: str, rows: list[dict[str, Any]], state: dict[str, Any] | None, trail_sources: list[str]) -> dict[str, Any]:
    worker_returns = [entry for entry in rows if entry["row"].get("kind") == "worker-return"]
    output = {}
    for field in ("endedAt", "usage", "failureClass"):
        def valid(row: dict[str, Any]) -> bool:
            value = row.get(field)
            if field == "endedAt":
                return _parse_time(value) is not None
            if field == "usage":
                return isinstance(value, dict) and {"input", "output"} <= set(value) and all(
                    type(value.get(key)) is int and value[key] >= 0 for key in ("input", "output")
                )
            return isinstance(value, str) and value in {"flaky", "env", "real"}

        filled = sum(valid(entry["row"]) for entry in worker_returns)
        missing = None if worker_returns and filled == len(worker_returns) else (
            "no worker-return records" if not worker_returns else f"{len(worker_returns) - filled} worker-return records omit or have invalid {field}"
        )
        output[field] = _metric(
            {"filled": filled, "records": len(worker_returns), "rate": filled / len(worker_returns)} if worker_returns else None,
            [entry["source"] for entry in worker_returns] or trail_sources,
            missing,
        )
    raw_findings = []
    canonical_sources = []
    for entry in rows:
        row = entry["row"]
        if row.get("kind") == "fact" and row.get("key") == review_track_stats.FACT_KEY:
            canonical_sources.append(entry["source"])
            value = row.get("value")
            if isinstance(value, dict) and isinstance(value.get("findings"), list):
                raw_findings.extend(value["findings"])
    impact_filled = sum(isinstance(item, dict) and item.get("impact") in IMPACTS for item in raw_findings)
    output["impact"] = _metric(
        {"filled": impact_filled, "records": len(raw_findings), "rate": impact_filled / len(raw_findings)} if raw_findings else None,
        canonical_sources or ["review.canonical_summary trail facts"],
        None if raw_findings and impact_filled == len(raw_findings) else (
            "no canonical finding records" if not raw_findings else f"{len(raw_findings) - impact_filled} finding records omit or have invalid impact"
        ),
    )
    if version != "3.6":
        output["recordedAt"] = _metric(None, ".impl-package/state.json evidenceIndex", "3.5 evidence records do not write recordedAt")
    else:
        evidence_index = state.get("evidenceIndex") if isinstance(state, dict) else None
        records = [record for items in evidence_index.values() if isinstance(items, list) for record in items if isinstance(record, dict)] if isinstance(evidence_index, dict) else []
        filled = sum(_parse_time(record.get("recordedAt")) is not None for record in records)
        output["recordedAt"] = _metric(
            {"filled": filled, "records": len(records), "rate": filled / len(records)} if records else None,
            ".impl-package/state.json evidenceIndex",
            None if records and filled == len(records) else (
                "no evidence records" if not records else f"{len(records) - filled} evidence records omit or have invalid recordedAt"
            ),
        )
    return output


def _report(package: Path, attempt: str | None = None) -> tuple[dict[str, Any], str]:
    package = package.resolve()
    state = engine._load_json(package / engine.STATE_PATH)
    version = engine._state_format_version(state)
    active_attempt = state.get("attempt", {}).get("id")
    history = state.get("attemptHistory")
    if not isinstance(active_attempt, str) or not isinstance(history, list):
        raise engine.StateError("state.json must contain attempt.id and attemptHistory")
    attempt = attempt or active_attempt
    history_row = next((row for row in history if isinstance(row, dict) and row.get("id") == attempt), None)
    if history_row is None:
        raise engine.StateError(f"Attempt is not present in state attemptHistory: {attempt}")
    selected_state = _read_selected_state(package, state, attempt, history_row)
    state_source = ".impl-package/state.json" if attempt == active_attempt else f".impl-package/attempts/{attempt}.json or gate revision"
    try:
        documents = engine._ticket_documents(package, attempt, version)
        ticket_ids = [item["id"] for item in documents]
        dependencies = engine._ticket_dependencies(documents)
    except engine.StateError:
        documents = []
        ticket_ids = sorted(selected_state.get("tickets", {})) if isinstance(selected_state, dict) and isinstance(selected_state.get("tickets"), dict) else []
        dependencies = None
    rows, trail_sources, warnings = _trail_rows(package, attempt)
    for index, entry in enumerate(rows):
        entry["index"] = index
    dispatch, dispatch_rows = _dispatch_metrics(rows, ticket_ids, trail_sources)
    tickets = _ticket_metrics(ticket_ids, rows, selected_state, state_source, trail_sources)
    upstream_tickets = {
        upstream
        for edges in (dependencies or {}).values()
        for kind, upstream in edges
        if kind == "implementation"
    }
    findings, _latest_findings, review_warnings = _review_metrics(package, attempt, version, rows, ticket_ids, upstream_tickets)
    warnings.extend(warning for warning in review_warnings if warning not in warnings)
    worker_returns = [entry for entry in rows if entry["row"].get("kind") == "worker-return"]
    usage, failures = _usage_metrics(worker_returns, trail_sources)
    gate = history_row.get("gate") if isinstance(history_row, dict) else None
    comparison = gate.get("commit") if isinstance(gate, dict) else None
    if not isinstance(comparison, str):
        try:
            repo = engine._repo_root(package)
            comparison = engine._run_git(repo, "rev-parse", "HEAD")
        except engine.StateError:
            comparison = None
    if version == "3.6" and selected_state is not None and not isinstance(comparison, str):
        journeys = _metric(None, ".impl-package/state.json evidenceIndex", "final comparison commit is unavailable")
    elif version == "3.6":
        journeys = _journey_metrics(package, version, selected_state, history_row, rows)
    else:
        journeys = _journey_metrics(package, version, selected_state, history_row, rows)
    report = {
        "schemaVersion": _metric(1, "impl-package metrics schema"),
        "formatVersion": _metric(version, ".impl-package/state.json formatVersion"),
        "attempt": _metric(attempt, ".impl-package/state.json attemptHistory"),
        "dispatch": dispatch,
        "tickets": tickets,
        "criticalPathWait": _critical_path_metrics(dependencies, ticket_ids, rows, dispatch_rows, trail_sources),
        "findings": findings,
        "journeys": journeys,
        "amendments": _amendment_metrics(version, selected_state),
        "usage": usage,
        "failures": failures,
        "coverage": _coverage(version, rows, selected_state, trail_sources),
        "readWarnings": _metric(warnings, trail_sources, None if not warnings else "some source rows could not be fully interpreted"),
    }
    return report, attempt


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        engine._invalidate_working_tree_hash(path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_metrics(package: Path, attempt: str | None = None, out: Path | None = None) -> Path:
    report, selected_attempt = _report(package, attempt)
    path = Path(out) if out is not None else Path(package) / "execution" / selected_attempt / "metrics.json"
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    _write_json(path, report)
    return path


def command_metrics(package: Path, attempt: str | None = None, out: Path | None = None) -> dict[str, Any]:
    report, selected_attempt = _report(package, attempt)
    path = Path(out) if out is not None else Path(package) / "execution" / selected_attempt / "metrics.json"
    if not path.is_absolute():
        path = Path.cwd() / path
    path = path.resolve()
    _write_json(path, report)
    relative = path.relative_to(Path(package).resolve()).as_posix() if path.is_relative_to(Path(package).resolve()) else str(path)
    modes = report["dispatch"]["byMode"]
    lines = [
        "Package metrics",
        f"Attempt: {selected_attempt} ({report['formatVersion']['value']})",
        f"Dispatches: {report['dispatch']['total']['value']} · " + ", ".join(f"{key} {value['value']}" for key, value in modes.items()),
        f"Tickets with wall-clock: {sum(item['wallClockSeconds']['value'] is not None for item in report['tickets'].values())}/{len(report['tickets'])}",
        f"Implementation dependency edges: {len(report['criticalPathWait']['edges']['value'] or []) if report['criticalPathWait']['edges']['value'] is not None else '?'}",
        f"Findings: {report['findings']['total']['value']} · impact " + ", ".join(f"{key} {value['value']}" for key, value in report['findings']['byImpact'].items()),
        f"Usage: input {report['usage']['input']['value']} · output {report['usage']['output']['value']} · cost USD {report['usage']['costUsd']['value']}",
        f"Report: {relative}",
    ]
    return {"path": relative, "summary": "\n".join(lines), "report": report}
