"""trail event validation, leases and trail-append command."""

from __future__ import annotations

import hashlib
import json
import math
import os
import secrets
import uuid
from pathlib import Path
from typing import Any

from situation import (
    FACT_KEYS,
    REVIEW_PHASES,
    REVIEW_PHASE_VALUES,
    REVIEW_TRACKS,
    REVIEW_TRACK_VALUES,
    ValidationResult,
    describe_unknown_fact_keys,
    dispatch_admission,
)

from .acceptance import (
    _validate_projections,
)
from .attempt_store import (
    _active_trail_rows,
    _append_trail,
    _same_event,
    _trail_text_field,
)
from .cmd_evidence import (
    _assert_mutable,
)
from .state_core import (
    ACTIVE_TRAIL_NAME,
    EXECUTION_PATH,
    FIXED_COMMIT_RE,
    LEASE_FILE_RE,
    LEASE_ID_RE,
    RETIRED_DISPATCH_FIELDS,
    STATE_PATH,
    StateError,
    TRAIL_APPEND_KINDS,
    TRAIL_COMMON_FIELDS,
    _load_json,
    _validate_iso_timestamp,
)
from .validate_state import (
    _validate_state,
)


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
