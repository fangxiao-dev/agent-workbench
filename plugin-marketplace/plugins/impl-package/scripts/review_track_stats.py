#!/usr/bin/env python3
"""Count canonical review findings across an Impl-Package execution chain."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


FACT_KEY = "review.canonical_summary"
SCHEMA_VERSION = 1
TRACKS = ("Track A", "Track B", "Track C", "Track D")
CLASSIFICATIONS = {"blocker", "follow-up"}
LIFECYCLES = {"open", "closed"}
PHASES = {"initial", "finding-closure", "terminal-final"}
ATTEMPT_ID_RE = re.compile(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})$")
TRAIL_ARCHIVE_RE = re.compile(r"^trail\.(\d{3})\.jsonl$")

SCRIPT_DIR = Path(__file__).resolve().parent
STATE_CLI = SCRIPT_DIR / "impl_package_state.py"


class ReviewStatsError(ValueError):
    """The requested review-stat operation cannot be completed safely."""


def _non_empty_string(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReviewStatsError(f"{label} must be a non-empty string")
    return value.strip()


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def validate_canonical_summary(value: Any, *, allow_empty_tracks: bool = False) -> dict[str, Any]:
    """Validate and return a normalized machine-readable canonical summary."""

    if not isinstance(value, dict):
        raise ReviewStatsError("canonical summary must be an object")
    required = {"schemaVersion", "reviewRunId", "phase", "resolvedHead", "findings"}
    missing = sorted(required - set(value))
    if missing:
        raise ReviewStatsError(f"canonical summary missing: {', '.join(missing)}")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != SCHEMA_VERSION:
        raise ReviewStatsError(f"schemaVersion must be {SCHEMA_VERSION}")

    normalized = dict(value)
    normalized["reviewRunId"] = _non_empty_string(value["reviewRunId"], "reviewRunId")
    normalized["phase"] = _non_empty_string(value["phase"], "phase")
    if normalized["phase"] not in PHASES:
        raise ReviewStatsError(f"phase must be one of: {', '.join(sorted(PHASES))}")
    normalized["resolvedHead"] = _non_empty_string(value["resolvedHead"], "resolvedHead")
    if re.fullmatch(r"[0-9a-fA-F]{40}", normalized["resolvedHead"]) is None:
        raise ReviewStatsError("resolvedHead must be a 40-character commit SHA")

    findings = value["findings"]
    if not isinstance(findings, list):
        raise ReviewStatsError("findings must be a list")
    normalized_findings: list[dict[str, Any]] = []
    finding_keys: set[str] = set()
    for index, finding in enumerate(findings):
        if not isinstance(finding, dict):
            raise ReviewStatsError(f"findings[{index}] must be an object")
        finding_required = {
            "findingKey",
            "id",
            "title",
            "ticketIds",
            "tracks",
            "classification",
            "lifecycle",
        }
        finding_missing = sorted(finding_required - set(finding))
        if finding_missing:
            raise ReviewStatsError(
                f"findings[{index}] missing: {', '.join(finding_missing)}"
            )
        item = dict(finding)
        item["findingKey"] = _non_empty_string(finding["findingKey"], f"findings[{index}].findingKey")
        if item["findingKey"] in finding_keys:
            raise ReviewStatsError(f"findings[{index}] has a duplicate findingKey")
        finding_keys.add(item["findingKey"])
        item["id"] = _non_empty_string(finding["id"], f"findings[{index}].id")
        item["title"] = _non_empty_string(finding["title"], f"findings[{index}].title")

        ticket_ids = finding["ticketIds"]
        if not isinstance(ticket_ids, list):
            raise ReviewStatsError(f"findings[{index}].ticketIds must be a list")
        item_tickets: list[str] = []
        for ticket_index, ticket_id in enumerate(ticket_ids):
            normalized_ticket = _non_empty_string(
                ticket_id, f"findings[{index}].ticketIds[{ticket_index}]"
            )
            if normalized_ticket in item_tickets:
                raise ReviewStatsError(f"findings[{index}] has a duplicate ticketId")
            item_tickets.append(normalized_ticket)
        if not item_tickets:
            raise ReviewStatsError(f"findings[{index}] has no ticketIds")
        item["ticketIds"] = item_tickets

        tracks = finding["tracks"]
        if not isinstance(tracks, list):
            raise ReviewStatsError(f"findings[{index}].tracks must be a list")
        item_tracks: list[str] = []
        for track_index, track in enumerate(tracks):
            normalized_track = _non_empty_string(
                track, f"findings[{index}].tracks[{track_index}]"
            )
            if normalized_track not in TRACKS:
                raise ReviewStatsError(
                    f"findings[{index}].tracks[{track_index}] must be one of: {', '.join(TRACKS)}"
                )
            if normalized_track in item_tracks:
                raise ReviewStatsError(f"findings[{index}] has a duplicate track")
            item_tracks.append(normalized_track)
        if not item_tracks and not allow_empty_tracks:
            raise ReviewStatsError(
                f"findings[{index}] has no tracks; empty tracks are only valid for legacy backfill"
            )
        item["tracks"] = item_tracks

        classification = _non_empty_string(
            finding["classification"], f"findings[{index}].classification"
        )
        if classification not in CLASSIFICATIONS:
            raise ReviewStatsError(
                f"findings[{index}].classification must be one of: {', '.join(sorted(CLASSIFICATIONS))}"
            )
        item["classification"] = classification
        lifecycle = _non_empty_string(finding["lifecycle"], f"findings[{index}].lifecycle")
        if lifecycle not in LIFECYCLES:
            raise ReviewStatsError(
                f"findings[{index}].lifecycle must be one of: {', '.join(sorted(LIFECYCLES))}"
            )
        item["lifecycle"] = lifecycle
        normalized_findings.append(item)
    normalized["findings"] = normalized_findings
    return normalized


def _empty_track_counts() -> dict[str, dict[str, int]]:
    return {track: {"caught": 0, "open": 0, "closed": 0} for track in TRACKS}


def _empty_coverage() -> dict[str, Any]:
    return {
        "attempts": 0,
        "trails": 0,
        "summaries": 0,
        "findingsRead": 0,
        "findings": 0,
        "reviewActivityRows": 0,
        "warnings": [],
    }


def _warn(warnings: list[str], message: str) -> None:
    if message not in warnings:
        warnings.append(message)


def _timestamp_sort_key(value: Any) -> tuple[int, int, float | str]:
    if not isinstance(value, str) or not value.strip():
        return (0, 0, 0.0)
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return (1, 0, parsed.astimezone(timezone.utc).timestamp())
    except ValueError:
        return (0, 1, raw)


def _sequence_sort_key(value: Any) -> tuple[int, int, float | str]:
    if value is None or isinstance(value, bool):
        return (0, 0, 0.0)
    if isinstance(value, int):
        return (1, 0, float(value))
    return (0, 1, str(value))


def _valid_row_metadata(row: dict[str, Any], source: str, warnings: list[str]) -> bool:
    sequence = row.get("seq")
    if type(sequence) is not int or sequence < 1:
        _warn(warnings, f"{source}: canonical summary fact has an invalid seq")
        return False
    timestamp = row.get("ts")
    timestamp_key = _timestamp_sort_key(timestamp)
    if (
        not isinstance(timestamp, str)
        or not timestamp.strip()
        or timestamp_key[0] != 1
        or timestamp_key[1] != 0
    ):
        _warn(warnings, f"{source}: canonical summary fact has an invalid ts")
        return False
    return True


def _load_json(path: Path, *, label: str | None = None) -> Any:
    display = label or str(path)
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError) as exc:
        raise ReviewStatsError(f"cannot read {display}") from exc
    except json.JSONDecodeError as exc:
        raise ReviewStatsError(f"invalid JSON in {display}: {exc.msg}") from exc


def _selected_attempts(
    package: Path, attempt: str | None, warnings: list[str], coverage: dict[str, Any]
) -> list[tuple[int, str]]:
    state_path = package / ".impl-package" / "state.json"
    try:
        state = _load_json(state_path, label=".impl-package/state.json")
    except ReviewStatsError as exc:
        _warn(warnings, str(exc))
        return []
    if not isinstance(state, dict):
        _warn(warnings, "state.json must contain an object")
        return []
    history = state.get("attemptHistory")
    if not isinstance(history, list):
        _warn(warnings, "state.json attemptHistory must be a list")
        return []
    if not history:
        _warn(warnings, "state.json attemptHistory is empty")
    selected: list[tuple[int, str]] = []
    seen: set[str] = set()
    matched = False
    for index, row in enumerate(history):
        if not isinstance(row, dict):
            _warn(warnings, f"attemptHistory[{index}] is not an object")
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or ATTEMPT_ID_RE.fullmatch(identifier) is None:
            _warn(warnings, f"attemptHistory[{index}] has an invalid id")
            continue
        if identifier in seen:
            _warn(warnings, f"attemptHistory contains duplicate Attempt ID: {identifier}")
            continue
        seen.add(identifier)
        if attempt is not None and identifier != attempt:
            continue
        matched = True
        selected.append((index, identifier))
    if attempt is not None and not matched:
        _warn(warnings, f"requested attempt is not present in attemptHistory: {attempt}")
    coverage["attempts"] = len(selected)
    return selected


def _trail_files(attempt_dir: Path) -> list[Path]:
    archives = sorted(
        (
            path
            for path in attempt_dir.iterdir()
            if path.is_file() and TRAIL_ARCHIVE_RE.fullmatch(path.name)
        ),
        key=lambda path: int(TRAIL_ARCHIVE_RE.fullmatch(path.name).group(1)),  # type: ignore[union-attr]
    ) if attempt_dir.is_dir() else []
    active = attempt_dir / "trail.jsonl"
    if active.is_file():
        archives.append(active)
    return archives


def _iter_trail_rows(
    package: Path,
    attempts: Iterable[tuple[int, str]],
    warnings: list[str],
    coverage: dict[str, Any],
) -> Iterable[tuple[dict[str, Any], tuple[Any, ...], str, str]]:
    for attempt_index, attempt_id in attempts:
        attempt_dir = package / "execution" / attempt_id
        try:
            files = _trail_files(attempt_dir)
        except OSError:
            _warn(warnings, f"cannot list execution/{attempt_id}")
            continue
        if not files:
            continue
        for trail_index, path in enumerate(files):
            coverage["trails"] += 1
            relative = path.relative_to(package).as_posix()
            try:
                lines = path.read_text(encoding="utf-8-sig").splitlines()
            except (OSError, UnicodeError):
                _warn(warnings, f"cannot read {relative}")
                continue
            for line_number, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    _warn(warnings, f"{relative}:{line_number} is not valid JSON: {exc.msg}")
                    continue
                if not isinstance(row, dict):
                    _warn(warnings, f"{relative}:{line_number} is not an object")
                    continue
                order = (
                    _timestamp_sort_key(row.get("ts")),
                    _sequence_sort_key(row.get("seq")),
                    attempt_index,
                    trail_index,
                    line_number,
                )
                yield row, order, attempt_id, f"{relative}:{line_number}"


def _scan_summaries(
    package: Path, attempt: str | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    coverage = _empty_coverage()
    warnings: list[str] = []
    selected = _selected_attempts(package, attempt, warnings, coverage)
    summaries: list[dict[str, Any]] = []
    for row, order, attempt_id, source in _iter_trail_rows(package, selected, warnings, coverage):
        if row.get("kind") in {"dispatch", "worker-return"} and row.get("review_track") in TRACKS:
            coverage["reviewActivityRows"] += 1
        if row.get("kind") != "fact" or row.get("key") != FACT_KEY:
            continue
        if not _valid_row_metadata(row, source, warnings):
            continue
        try:
            summary = validate_canonical_summary(row.get("value"), allow_empty_tracks=True)
        except ReviewStatsError as exc:
            _warn(warnings, f"{source}: invalid canonical summary: {exc}")
            continue
        coverage["summaries"] += 1
        coverage["findingsRead"] += len(summary["findings"])
        for finding in summary["findings"]:
            if not finding["tracks"]:
                _warn(
                    warnings,
                    f"{source}: canonical finding has no track attribution; counted as unattributed",
                )
        summaries.append(
            {
                "summary": summary,
                "row": row,
                "order": order,
                "attempt": attempt_id,
                "source": source,
            }
        )
    if coverage["reviewActivityRows"] and not coverage["summaries"]:
        _warn(
            warnings,
            "review activity exists but no canonical summary facts were found; bug counts are incomplete",
        )
    return summaries, coverage, warnings


def _aggregate_counts(
    findings: list[dict[str, Any]],
) -> tuple[dict[str, int], dict[str, dict[str, int]]]:
    totals = {
        "unique": len(findings),
        "open": sum(item["lifecycle"] == "open" for item in findings),
        "closed": sum(item["lifecycle"] == "closed" for item in findings),
        "trackContributions": 0,
        "unattributed": 0,
    }
    tracks = _empty_track_counts()
    for finding in findings:
        finding_tracks = finding["tracks"]
        if not finding_tracks:
            totals["unattributed"] += 1
        for track in finding_tracks:
            totals["trackContributions"] += 1
            tracks[track]["caught"] += 1
            tracks[track][finding["lifecycle"]] += 1
    return totals, tracks


def _aggregate(
    findings: list[dict[str, Any]], ticket_filter: str | None
) -> tuple[dict[str, int], dict[str, dict[str, int]], dict[str, dict[str, Any]]]:
    totals, tracks = _aggregate_counts(findings)
    by_ticket: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        for ticket_id in finding["ticketIds"]:
            if ticket_filter is not None and ticket_id != ticket_filter:
                continue
            by_ticket.setdefault(ticket_id, []).append(finding)

    tickets: dict[str, dict[str, Any]] = {}
    for ticket_id in sorted(by_ticket):
        ticket_totals, ticket_tracks = _aggregate_counts(by_ticket[ticket_id])
        tickets[ticket_id] = {**ticket_totals, "tracks": ticket_tracks}
    return totals, tracks, tickets


def calculate_review_stats(
    package: Path, attempt: str | None = None, ticket: str | None = None
) -> dict[str, Any]:
    """Calculate review finding counts from every selected Attempt trail."""

    package = Path(package)
    if attempt is not None:
        attempt = _non_empty_string(attempt, "attempt")
    if ticket is not None:
        ticket = _non_empty_string(ticket, "ticket")
    summaries, coverage, warnings = _scan_summaries(package, attempt)
    latest_runs: dict[str, dict[str, Any]] = {}
    for entry in summaries:
        run_id = entry["summary"]["reviewRunId"]
        previous = latest_runs.get(run_id)
        if previous is None or entry["order"] >= previous["order"]:
            latest_runs[run_id] = entry
    latest: dict[str, tuple[dict[str, Any], tuple[Any, ...]]] = {}
    for entry in latest_runs.values():
        summary = entry["summary"]
        for finding in summary["findings"]:
            key = finding["findingKey"]
            previous = latest.get(key)
            if previous is None or entry["order"] >= previous[1]:
                latest[key] = (finding, entry["order"])
    findings = [
        finding
        for finding, _order in latest.values()
        if ticket is None or ticket in finding["ticketIds"]
    ]
    coverage["findings"] = len(findings)
    coverage["warnings"] = warnings
    totals, tracks, tickets = _aggregate(findings, ticket)
    return {
        "version": 1,
        "totals": totals,
        "tracks": tracks,
        "tickets": tickets,
        "coverage": coverage,
    }


def _append_via_state_cli(
    package: Path,
    summary: dict[str, Any],
    *,
    import_id: str | None = None,
    import_index: int | None = None,
    import_count: int | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "kind": "fact",
        "subject": f"review:{summary['reviewRunId']}",
        "key": FACT_KEY,
        "value": summary,
    }
    if import_id is not None:
        event["importId"] = import_id
        event["importIndex"] = import_index
        event["importCount"] = import_count
    command = [
        sys.executable,
        str(STATE_CLI),
        "--package",
        str(package),
        "--no-situation",
        "trail",
        "append",
    ]
    try:
        result = subprocess.run(
            command,
            input=json.dumps(event, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
    except OSError as exc:
        raise ReviewStatsError(f"trail append failed: {exc}") from exc
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "state CLI failed"
        raise ReviewStatsError(f"trail append failed: {detail}")
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ReviewStatsError(f"trail append returned invalid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise ReviewStatsError("trail append returned a non-object")
    return payload


def _load_manifest(path: Path) -> tuple[str, list[dict[str, Any]]]:
    try:
        manifest = _load_json(path)
    except ReviewStatsError:
        raise
    if not isinstance(manifest, dict):
        raise ReviewStatsError("manifest must be an object")
    import_id = _non_empty_string(manifest.get("importId"), "manifest.importId")
    summaries = manifest.get("summaries")
    if not isinstance(summaries, list) or not summaries:
        raise ReviewStatsError("manifest.summaries must be a non-empty list")
    normalized: list[dict[str, Any]] = []
    for index, summary in enumerate(summaries):
        try:
            normalized.append(validate_canonical_summary(summary, allow_empty_tracks=True))
        except ReviewStatsError as exc:
            raise ReviewStatsError(f"manifest.summaries[{index}] is invalid: {exc}") from exc
    return import_id, normalized


def _existing_import_rows(
    package: Path, import_id: str
) -> tuple[list[dict[str, Any]], list[str]]:
    coverage = _empty_coverage()
    warnings: list[str] = []
    selected = _selected_attempts(package, None, warnings, coverage)
    rows: list[dict[str, Any]] = []
    for row, _order, attempt_id, source in _iter_trail_rows(package, selected, warnings, coverage):
        if row.get("importId") != import_id:
            continue
        if row.get("kind") != "fact" or row.get("key") != FACT_KEY:
            _warn(warnings, f"{source}: importId is not attached to a canonical summary fact")
            continue
        if not _valid_row_metadata(row, source, warnings):
            continue
        rows.append({"row": row, "attempt": attempt_id, "source": source})
    return rows, warnings


def _manifest_matches(
    existing: list[dict[str, Any]], summaries: list[dict[str, Any]], import_id: str
) -> tuple[list[int], int]:
    expected_count = len(summaries)
    indexed: dict[int, dict[str, Any]] = {}
    unindexed: list[dict[str, Any]] = []
    for entry in existing:
        row = entry["row"]
        import_count = row.get("importCount")
        if import_count is not None and (
            type(import_count) is not int or import_count < 1
        ):
            raise ReviewStatsError(f"importId {import_id} contains an invalid importCount")
        if import_count is not None and import_count != expected_count:
            raise ReviewStatsError(
                f"importId {import_id} was previously used with a different summary count"
            )
        index = row.get("importIndex")
        if index is not None and (type(index) is not int or index < 0):
            raise ReviewStatsError(f"importId {import_id} contains an invalid importIndex")
        if isinstance(index, int) and not isinstance(index, bool):
            if index < 0 or index >= expected_count:
                raise ReviewStatsError(f"importId {import_id} contains an invalid importIndex")
            previous = indexed.get(index)
            if previous is not None and _canonical_json(previous.get("value")) != _canonical_json(row.get("value")):
                raise ReviewStatsError(f"importId {import_id} has conflicting importIndex {index}")
            indexed[index] = row
        else:
            unindexed.append(row)

    missing: list[int] = []
    for index, summary in enumerate(summaries):
        candidate = indexed.get(index)
        if candidate is None and unindexed:
            expected = _canonical_json(summary)
            match_at = next(
                (position for position, row in enumerate(unindexed) if _canonical_json(row.get("value")) == expected),
                None,
            )
            if match_at is not None:
                unindexed.pop(match_at)
                candidate = {"value": summary}
        if candidate is None:
            missing.append(index)
            continue
        if _canonical_json(candidate.get("value")) != _canonical_json(summary):
            raise ReviewStatsError(f"importId {import_id} has conflicting summary at index {index}")
    return missing, expected_count - len(missing)


def record_summary(package: Path, summary: Any) -> dict[str, Any]:
    normalized = validate_canonical_summary(summary)
    payload = _append_via_state_cli(package, normalized)
    return {"reviewRunId": normalized["reviewRunId"], **payload}


def backfill_manifest(package: Path, manifest: Path, *, apply: bool) -> dict[str, Any]:
    import_id, summaries = _load_manifest(Path(manifest))
    existing, scan_warnings = _existing_import_rows(Path(package), import_id)
    missing, matched = _manifest_matches(existing, summaries, import_id)
    result: dict[str, Any] = {
        "importId": import_id,
        "dryRun": not apply,
        "summaries": len(summaries),
        "alreadyApplied": bool(existing) and not missing,
        "wouldAppend": len(missing),
        "appended": 0,
        "skipped": matched,
        "warnings": scan_warnings,
    }
    if not apply:
        return result
    for index in missing:
        payload = _append_via_state_cli(
            Path(package),
            summaries[index],
            import_id=import_id,
            import_index=index,
            import_count=len(summaries),
        )
        result["appended"] += 1 if payload.get("appended") is not False else 0
        result["skipped"] += 1 if payload.get("appended") is False else 0
    result["alreadyApplied"] = result["appended"] == 0
    return result


def _text_report(payload: dict[str, Any]) -> str:
    totals = payload["totals"]
    lines = [
        "Review findings",
        f"Unique: {totals['unique']} (open {totals['open']}, closed {totals['closed']})",
        f"Track contributions: {totals['trackContributions']} · unattributed: {totals['unattributed']}",
    ]
    for track, counts in payload["tracks"].items():
        lines.append(
            f"{track}: {counts['caught']} (open {counts['open']}, closed {counts['closed']})"
        )
    if payload["tickets"]:
        lines.append("Tickets:")
        for ticket_id, ticket in payload["tickets"].items():
            lines.append(
                f"  {ticket_id}: {ticket['unique']} (open {ticket['open']}, closed {ticket['closed']})"
            )
    warnings = payload.get("coverage", {}).get("warnings", [])
    if warnings:
        lines.append("Warnings:")
        lines.extend(f"  - {warning}" for warning in warnings)
    return "\n".join(lines)


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    show = commands.add_parser("show", help="calculate review finding statistics")
    show.add_argument("--package", type=Path, required=True)
    show.add_argument("--attempt")
    show.add_argument("--ticket")
    show.add_argument("--format", choices=("json", "text"), default="json")

    record = commands.add_parser("record", help="append one canonical summary to the active Attempt trail")
    record.add_argument("--package", type=Path, required=True)

    backfill = commands.add_parser("backfill", help="import a structured legacy summary manifest")
    backfill.add_argument("--package", type=Path, required=True)
    backfill.add_argument("--manifest", type=Path, required=True)
    mode = backfill.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "show":
            payload = calculate_review_stats(args.package, args.attempt, args.ticket)
            if args.format == "text":
                print(_text_report(payload))
            else:
                _print_json(payload)
            return 0
        if args.command == "record":
            raw = sys.stdin.read()
            try:
                value = json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ReviewStatsError(f"record input is not valid JSON: {exc}") from exc
            _print_json(record_summary(args.package, value))
            return 0
        if args.command == "backfill":
            _print_json(backfill_manifest(args.package, args.manifest, apply=args.apply))
            return 0
        raise ReviewStatsError(f"unknown command: {args.command}")
    except (OSError, ReviewStatsError) as exc:
        print(f"review_track_stats: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
