#!/usr/bin/env python3
"""Minimal, deterministic state ledger for eng-plan-review.

The ledger protects review/apply invariants. It intentionally does not model
reviewer roles, question trees, critic passes, or branch scheduling.
"""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import time
from typing import Any, Iterator


SCHEMA_VERSION = 1
DIMENSIONS = ("scope", "architecture", "code_quality", "tests", "performance")
MATERIALITY_STATES = {"reviewed", "not_applicable", "finding"}
SEVERITIES = {"P0", "P1", "P2", "P3"}
RESOLUTION_STATES = {"pending", "accepted", "rejected", "deferred"}
AUTHORITIES = {"agent", "owner"}
OWNER_GATES = {"required", "not_required"}
OUTSIDE_VOICE_STATES = {"complete", "unavailable"}


class LedgerError(ValueError):
    """Raised when a ledger invariant would be violated."""


def _pid_exists(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _remove_stale_lock(lock_path: Path, minimum_age: float = 30.0) -> bool:
    try:
        original_bytes = lock_path.read_bytes()
        original_stat = lock_path.stat()
        lock_data = json.loads(original_bytes.decode("utf-8"))
        pid = int(lock_data["pid"])
        created = float(lock_data["created"])
    except (FileNotFoundError, OSError):
        return False
    except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError):
        if time.time() - original_stat.st_mtime < minimum_age:
            return False
        try:
            if lock_path.read_bytes() != original_bytes or lock_path.stat() != original_stat:
                return False
            lock_path.unlink()
            return True
        except (FileNotFoundError, OSError):
            return False
    if time.time() - created < minimum_age or _pid_exists(pid):
        return False
    try:
        current = json.loads(lock_path.read_text(encoding="utf-8"))
        if current != lock_data:
            return False
        lock_path.unlink()
        return True
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return False


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tree_snapshot(path: Path) -> tuple[str, list[dict[str, str]]]:
    entries: list[dict[str, str]] = []
    for child in sorted((item for item in path.rglob("*") if item.is_file()), key=lambda p: p.as_posix()):
        entries.append(
            {
                "path": child.relative_to(path).as_posix(),
                "sha256": _sha256_file(child),
            }
        )
    return _sha256_bytes(_canonical_bytes(entries)), entries


def snapshot_path(path_value: str | os.PathLike[str], kind: str | None = None) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve(strict=True)
    actual_kind = kind or ("tree" if path.is_dir() else "file")
    if actual_kind == "file":
        if not path.is_file():
            raise LedgerError(f"expected file dependency: {path}")
        digest = _sha256_file(path)
        result: dict[str, Any] = {"kind": "file", "path": str(path), "sha256": digest}
    elif actual_kind == "tree":
        if not path.is_dir():
            raise LedgerError(f"expected tree dependency: {path}")
        digest, entries = _tree_snapshot(path)
        result = {"kind": "tree", "path": str(path), "sha256": digest, "entries": entries}
    else:
        raise LedgerError(f"unsupported dependency kind: {actual_kind}")
    result["identity"] = str(path)
    return result


def _git_value(repo: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return completed.stdout.strip() or None


def _repo_metadata(repo_root: str | os.PathLike[str] | None, target: Path) -> dict[str, Any]:
    candidate = Path(repo_root).expanduser().resolve() if repo_root else target.parent
    discovered = _git_value(candidate, "rev-parse", "--show-toplevel")
    root = Path(discovered).resolve() if discovered else candidate
    return {
        "root": str(root),
        "branch": _git_value(root, "branch", "--show-current"),
        "head": _git_value(root, "rev-parse", "HEAD"),
    }


def _new_run_id() -> str:
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"epr-{timestamp}-{secrets.token_hex(4)}"


def _atomic_write(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(data, stream, ensure_ascii=False, sort_keys=True, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        if os.name != "nt":
            directory_fd = os.open(path.parent, os.O_RDONLY)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace_bytes(path: Path, value: bytes, expected_sha256: str) -> None:
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".apply", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        if _sha256_file(path) != expected_sha256:
            raise LedgerError("target changed after verification; guarded Apply stopped")
        os.replace(temporary, path)
        if _sha256_file(path) != _sha256_bytes(value):
            raise LedgerError("guarded Apply output verification failed")
    finally:
        temporary.unlink(missing_ok=True)


def _write_backup(path: Path, value: bytes) -> None:
    try:
        with path.open("xb") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
    except FileExistsError:
        if path.read_bytes() != value:
            raise LedgerError(f"preimage backup collision: {path}")


@contextlib.contextmanager
def _ledger_lock(path: Path, timeout: float = 5.0) -> Iterator[None]:
    lock_path = path.with_name(f"{path.name}.lock")
    deadline = time.monotonic() + timeout
    descriptor: int | None = None
    token = secrets.token_hex(16)
    while descriptor is None:
        try:
            descriptor = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            if _remove_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                raise LedgerError(f"timed out acquiring ledger lock: {lock_path}")
            time.sleep(0.02)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            json.dump(
                {"pid": os.getpid(), "created": time.time(), "token": token},
                stream,
                ensure_ascii=True,
                sort_keys=True,
                separators=(",", ":"),
            )
            stream.flush()
            os.fsync(stream.fileno())
        descriptor = None
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        release_deadline = time.monotonic() + 1.0
        while True:
            try:
                lock_data = json.loads(lock_path.read_text(encoding="utf-8"))
                if lock_data.get("token") != token:
                    break
                lock_path.unlink(missing_ok=True)
                break
            except FileNotFoundError:
                break
            except (OSError, json.JSONDecodeError):
                if time.monotonic() >= release_deadline:
                    break
                time.sleep(0.01)


def _read_ledger(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise LedgerError(f"ledger not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise LedgerError(f"invalid ledger JSON: {path}: {exc}") from exc
    if data.get("schema_version") != SCHEMA_VERSION:
        raise LedgerError(f"unsupported ledger schema: {data.get('schema_version')}")
    return data


def init_ledger(
    targets: list[str],
    baselines: list[str] | None = None,
    *,
    repo_root: str | None = None,
    skill_version: str = "dev",
    temp_root: str | os.PathLike[str] | None = None,
) -> Path:
    if not targets:
        raise LedgerError("at least one target is required")
    target_snapshots = [snapshot_path(item) for item in targets]
    reference_snapshots = [snapshot_path(item) for item in (baselines or [])]
    target_path = Path(target_snapshots[0]["path"])
    run_id = _new_run_id()
    root = Path(temp_root) if temp_root else Path(tempfile.gettempdir()) / "eng-plan-review"
    run_directory = root / run_id
    run_directory.mkdir(parents=True, exist_ok=False)
    ledger_path = run_directory / "ledger.json"
    ledger = {
        "schema_version": SCHEMA_VERSION,
        "run": {
            "run_id": run_id,
            "created_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "skill_version": skill_version,
            "repo": _repo_metadata(repo_root, target_path),
        },
        "baseline": {"targets": target_snapshots, "references": reference_snapshots},
        "materiality": {},
        "review_state": {"outside_voice": "pending", "reason": None, "degraded": False},
        "findings": {},
        "authorization": None,
        "verification": {"baseline_stale": False},
        "revision": 0,
    }
    _atomic_write(ledger_path, ledger)
    return ledger_path


def _validate_source(source: Any) -> dict[str, Any]:
    if not isinstance(source, dict) or source.get("actor") != "owner":
        raise LedgerError("owner source must declare actor=owner")
    if not source.get("channel") or not source.get("reference"):
        raise LedgerError("owner source requires channel and reference")
    normalized = dict(source)
    statement = normalized.pop("statement", None)
    if statement:
        normalized["statement_sha256"] = _sha256_bytes(str(statement).encode("utf-8"))
    if not normalized.get("statement_sha256"):
        raise LedgerError("owner source requires statement or statement_sha256")
    return normalized


def _validate_authorization_source(source: Any, expected_manifest_hash: str) -> dict[str, Any]:
    normalized = _validate_source(source)
    if source.get("action") != "apply":
        raise LedgerError("authorization source requires action=apply")
    if source.get("manifest_hash") != expected_manifest_hash:
        raise LedgerError("authorization source must bind the exact manifest hash")
    normalized["action"] = "apply"
    normalized["manifest_hash"] = expected_manifest_hash
    return normalized


def _validate_resolution(resolution: Any, owner_gate: str) -> dict[str, Any]:
    if resolution is None:
        return {"state": "pending", "authority": None, "source": None}
    if not isinstance(resolution, dict) or resolution.get("state") not in RESOLUTION_STATES:
        raise LedgerError("resolution has an invalid state")
    state = resolution["state"]
    authority = resolution.get("authority")
    source = resolution.get("source")
    if state == "pending":
        if authority is not None or source is not None:
            raise LedgerError("pending resolution cannot declare authority or source")
        return {"state": state, "authority": None, "source": None}
    if authority not in AUTHORITIES:
        raise LedgerError(f"{state} resolution requires agent or owner authority")
    if owner_gate == "required" and state in {"accepted", "rejected"} and authority != "owner":
        raise LedgerError("owner-gated finding cannot be resolved by an agent")
    if authority == "owner":
        source = _validate_source(source)
    elif source is not None:
        raise LedgerError("agent resolution cannot attach an owner source")
    return {"state": state, "authority": authority, "source": source}


def _finding_from_record(record: dict[str, Any], previous: dict[str, Any] | None) -> dict[str, Any]:
    required = ("id", "section", "claim", "risk", "severity", "confidence", "evidence", "evidence_dependencies", "recommendation", "owner_gate")
    missing = [name for name in required if not record.get(name)]
    if missing:
        raise LedgerError(f"formal finding missing fields: {', '.join(missing)}")
    if record["section"] not in DIMENSIONS:
        raise LedgerError(f"invalid finding section: {record['section']}")
    if record["severity"] not in SEVERITIES:
        raise LedgerError(f"invalid severity: {record['severity']}")
    if record["owner_gate"] not in OWNER_GATES:
        raise LedgerError(f"invalid owner gate: {record['owner_gate']}")
    if not isinstance(record["evidence"], list) or not record["evidence"]:
        raise LedgerError("formal finding requires non-empty evidence")
    if not isinstance(record["evidence_dependencies"], list) or not record["evidence_dependencies"]:
        raise LedgerError("formal finding requires evidence dependencies")
    dependencies = []
    for dependency in record["evidence_dependencies"]:
        if not isinstance(dependency, dict) or not dependency.get("path"):
            raise LedgerError("evidence dependency requires path")
        dependencies.append(snapshot_path(dependency["path"], dependency.get("kind")))
    finding = {
        "id": record["id"],
        "section": record["section"],
        "claim": record["claim"],
        "risk": record["risk"],
        "severity": record["severity"],
        "confidence": record["confidence"],
        "evidence": record["evidence"],
        "evidence_dependencies": dependencies,
        "recommendation": record["recommendation"],
        "owner_gate": record["owner_gate"],
        "resolution": _validate_resolution(record.get("resolution"), record["owner_gate"]),
        "stale": False,
        "stale_dependencies": [],
    }
    comparable = dict(finding)
    if previous:
        previous_comparable = {key: value for key, value in previous.items() if key != "revision"}
        revision = previous["revision"] if previous_comparable == comparable else previous["revision"] + 1
    else:
        revision = 1
    finding["revision"] = revision
    return finding


def record_ledger(ledger_path: str | os.PathLike[str], record: dict[str, Any]) -> dict[str, Any]:
    path = Path(ledger_path).resolve()
    with _ledger_lock(path):
        ledger = _read_ledger(path)
        record_type = record.get("type")
        if record_type == "candidate":
            raise LedgerError("candidates are exploratory and cannot be recorded in the ledger")
        if record_type == "review_state":
            outside_voice = record.get("outside_voice")
            reason = record.get("reason")
            if outside_voice not in OUTSIDE_VOICE_STATES:
                raise LedgerError("review_state requires outside_voice=complete or unavailable")
            if outside_voice == "unavailable" and (not isinstance(reason, str) or not reason.strip()):
                raise LedgerError("unavailable Outside Voice requires a reason")
            value = {
                "outside_voice": outside_voice,
                "reason": reason.strip() if isinstance(reason, str) and reason.strip() else None,
                "degraded": outside_voice == "unavailable",
            }
            changed = ledger["review_state"] != value
            ledger["review_state"] = value
        elif record_type == "materiality":
            dimension = record.get("dimension")
            status = record.get("status")
            reason = record.get("reason")
            if dimension not in DIMENSIONS or status not in MATERIALITY_STATES:
                raise LedgerError("invalid materiality dimension or status")
            if not isinstance(reason, str) or not reason.strip():
                raise LedgerError("materiality record requires a reason")
            value = {"status": status, "reason": reason.strip()}
            if record.get("finding_ids") is not None:
                finding_ids = record["finding_ids"]
                if (
                    not isinstance(finding_ids, list)
                    or not finding_ids
                    or any(not isinstance(item, str) or not item.strip() for item in finding_ids)
                    or len(set(finding_ids)) != len(finding_ids)
                ):
                    raise LedgerError("finding_ids must be a non-empty list of unique strings")
                value["finding_ids"] = finding_ids
            changed = ledger["materiality"].get(dimension) != value
            ledger["materiality"][dimension] = value
        elif record_type == "finding":
            finding_id = record.get("id")
            if not isinstance(finding_id, str) or not finding_id.strip():
                raise LedgerError("finding requires a stable id")
            previous = ledger["findings"].get(finding_id)
            value = _finding_from_record(record, previous)
            changed = previous != value
            ledger["findings"][finding_id] = value
        else:
            raise LedgerError("record type must be review_state, materiality, or finding")
        if changed:
            ledger["revision"] += 1
            ledger["authorization"] = None
            _atomic_write(path, ledger)
        return ledger


def _manifest_payload(ledger: dict[str, Any]) -> dict[str, Any]:
    findings = []
    unresolved = []
    for finding_id in sorted(ledger["findings"]):
        finding = ledger["findings"][finding_id]
        resolution = finding["resolution"]
        findings.append(
            {
                "id": finding_id,
                "revision": finding["revision"],
                "recommendation": finding["recommendation"],
                "owner_gate": finding["owner_gate"],
                "resolution": resolution,
                "stale": finding["stale"],
            }
        )
        if resolution["state"] in {"pending", "deferred"}:
            unresolved.append(finding_id)
    return {
        "run_id": ledger["run"]["run_id"],
        "baseline": ledger["baseline"],
        "materiality": ledger["materiality"],
        "review_state": ledger["review_state"],
        "findings": findings,
        "unresolved": unresolved,
        "baseline_stale": ledger["verification"]["baseline_stale"],
    }


def manifest_hash(ledger: dict[str, Any]) -> str:
    return _sha256_bytes(_canonical_bytes(_manifest_payload(ledger)))


def _validate_materiality_consistency(ledger: dict[str, Any]) -> None:
    findings_by_section: dict[str, set[str]] = {dimension: set() for dimension in DIMENSIONS}
    for finding_id, finding in ledger["findings"].items():
        findings_by_section[finding["section"]].add(finding_id)
    for dimension in DIMENSIONS:
        materiality = ledger["materiality"][dimension]
        actual_ids = findings_by_section[dimension]
        declared_ids = set(materiality.get("finding_ids", []))
        if materiality["status"] == "finding":
            if not actual_ids:
                raise LedgerError(f"materiality {dimension}=finding requires a formal finding")
            if declared_ids != actual_ids:
                raise LedgerError(f"materiality {dimension} finding_ids must match formal findings")
        elif actual_ids:
            raise LedgerError(f"materiality {dimension}={materiality['status']} conflicts with formal findings")
        elif declared_ids:
            raise LedgerError(f"materiality {dimension} cannot declare finding_ids without finding status")


def status_ledger(ledger_path: str | os.PathLike[str]) -> dict[str, Any]:
    ledger = _read_ledger(Path(ledger_path).resolve())
    missing_dimensions = [item for item in DIMENSIONS if item not in ledger["materiality"]]
    pending = []
    owner_required = []
    stale = []
    for finding_id, finding in ledger["findings"].items():
        if finding["resolution"]["state"] in {"pending", "deferred"}:
            pending.append(finding_id)
        if finding["owner_gate"] == "required" and finding["resolution"]["state"] in {"pending", "deferred"}:
            owner_required.append(finding_id)
        if finding["stale"]:
            stale.append(finding_id)
    current_hash = manifest_hash(ledger)
    authorization = ledger.get("authorization")
    return {
        "run_id": ledger["run"]["run_id"],
        "ledger": str(Path(ledger_path).resolve()),
        "revision": ledger["revision"],
        "manifest_hash": current_hash,
        "missing_materiality": missing_dimensions,
        "outside_voice": ledger["review_state"]["outside_voice"],
        "degraded": ledger["review_state"]["degraded"],
        "pending": sorted(pending),
        "owner_required": sorted(owner_required),
        "stale_findings": sorted(stale),
        "baseline_stale": ledger["verification"]["baseline_stale"],
        "authorized": bool(authorization and authorization.get("manifest_hash") == current_hash),
    }


def _current_digest(resource: dict[str, Any]) -> str | None:
    try:
        return snapshot_path(resource["path"], resource["kind"])["sha256"]
    except (FileNotFoundError, LedgerError):
        return None


def _verify_in_place(ledger: dict[str, Any]) -> bool:
    baseline_stale = any(
        _current_digest(resource) != resource["sha256"]
        for group in ("targets", "references")
        for resource in ledger["baseline"][group]
    )
    changed = ledger["verification"].get("baseline_stale") != baseline_stale
    ledger["verification"]["baseline_stale"] = baseline_stale
    for finding in ledger["findings"].values():
        stale_dependencies = sorted(
            dependency["identity"]
            for dependency in finding["evidence_dependencies"]
            if _current_digest(dependency) != dependency["sha256"]
        )
        finding_stale = bool(stale_dependencies)
        if finding.get("stale") != finding_stale or finding.get("stale_dependencies") != stale_dependencies:
            finding["stale"] = finding_stale
            finding["stale_dependencies"] = stale_dependencies
            changed = True
    if changed:
        ledger["revision"] += 1
        ledger["authorization"] = None
    return changed


def verify_ledger(
    ledger_path: str | os.PathLike[str], expected_manifest_hash: str | None = None
) -> dict[str, Any]:
    path = Path(ledger_path).resolve()
    with _ledger_lock(path):
        ledger = _read_ledger(path)
        changed = _verify_in_place(ledger)
        if changed:
            _atomic_write(path, ledger)
        result = status_ledger(path)
        authorization = ledger.get("authorization")
        result["manifest_matches"] = expected_manifest_hash is None or expected_manifest_hash == result["manifest_hash"]
        result["authorization_matches"] = bool(
            authorization and authorization.get("manifest_hash") == result["manifest_hash"]
        )
        result["ok"] = bool(
            result["manifest_matches"]
            and result["authorization_matches"]
            and not result["baseline_stale"]
            and not result["stale_findings"]
            and not result["missing_materiality"]
        )
        return result


def authorize_ledger(
    ledger_path: str | os.PathLike[str], expected_manifest_hash: str, source: dict[str, Any]
) -> dict[str, Any]:
    path = Path(ledger_path).resolve()
    normalized_source = _validate_authorization_source(source, expected_manifest_hash)
    with _ledger_lock(path):
        ledger = _read_ledger(path)
        changed = _verify_in_place(ledger)
        if changed:
            _atomic_write(path, ledger)
        missing = [item for item in DIMENSIONS if item not in ledger["materiality"]]
        stale = [item["id"] for item in ledger["findings"].values() if item["stale"]]
        blocking_p0 = [
            item["id"]
            for item in ledger["findings"].values()
            if item["severity"] == "P0" and item["resolution"]["state"] != "accepted"
        ]
        owner_required = [
            item["id"]
            for item in ledger["findings"].values()
            if item["owner_gate"] == "required" and item["resolution"]["state"] in {"pending", "deferred"}
        ]
        if missing:
            raise LedgerError(f"cannot authorize before materiality scan: {', '.join(missing)}")
        _validate_materiality_consistency(ledger)
        if ledger["review_state"]["outside_voice"] == "pending":
            raise LedgerError("cannot authorize before Outside Voice completes or is marked unavailable")
        if ledger["verification"]["baseline_stale"]:
            raise LedgerError("cannot authorize a stale baseline")
        if stale:
            raise LedgerError(f"cannot authorize stale findings: {', '.join(sorted(stale))}")
        if owner_required:
            raise LedgerError(f"cannot authorize unresolved owner-gated findings: {', '.join(sorted(owner_required))}")
        if blocking_p0:
            raise LedgerError(f"cannot authorize unresolved P0 findings: {', '.join(sorted(blocking_p0))}")
        current_hash = manifest_hash(ledger)
        if expected_manifest_hash != current_hash:
            raise LedgerError("manifest hash does not match current ledger state")
        existing = ledger.get("authorization")
        authorization = {
            "manifest_hash": current_hash,
            "actor": "owner",
            "source": normalized_source,
            "authorized_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        }
        if not existing or existing.get("manifest_hash") != current_hash or existing.get("source") != normalized_source:
            ledger["authorization"] = authorization
            ledger["revision"] += 1
            _atomic_write(path, ledger)
        return status_ledger(path)


def apply_verified_output(
    ledger_path: str | os.PathLike[str], proposed_output: str | os.PathLike[str]
) -> dict[str, Any]:
    path = Path(ledger_path).resolve()
    proposed_path = Path(proposed_output).resolve(strict=True)
    proposed_bytes = proposed_path.read_bytes()
    with _ledger_lock(path):
        ledger = _read_ledger(path)
        changed = _verify_in_place(ledger)
        if changed:
            _atomic_write(path, ledger)
        status = status_ledger(path)
        if status["missing_materiality"]:
            raise LedgerError("guarded Apply requires a complete materiality scan")
        _validate_materiality_consistency(ledger)
        if ledger["review_state"]["outside_voice"] == "pending":
            raise LedgerError("guarded Apply requires Outside Voice completion or degradation")
        if status["baseline_stale"] or status["stale_findings"]:
            raise LedgerError("guarded Apply stopped because the review baseline is stale")
        if not status["authorized"]:
            raise LedgerError("guarded Apply requires authorization for the current manifest")
        targets = ledger["baseline"]["targets"]
        if len(targets) != 1 or targets[0]["kind"] != "file":
            raise LedgerError("guarded Apply currently supports exactly one target file")
        target = Path(targets[0]["path"])
        expected_sha256 = targets[0]["sha256"]
        backup = path.parent / f"pre-apply-{expected_sha256[:12]}.bak"
        with _ledger_lock(target):
            preimage = target.read_bytes()
            if _sha256_bytes(preimage) != expected_sha256:
                raise LedgerError("target changed after verification; guarded Apply stopped")
            _write_backup(backup, preimage)
            _atomic_replace_bytes(target, proposed_bytes, expected_sha256)
        result = status_ledger(path)
        result.update(
            {
                "applied": True,
                "target": str(target),
                "output_sha256": _sha256_bytes(proposed_bytes),
                "preimage_backup": str(backup),
            }
        )
        return result


def _load_json_argument(value: str) -> dict[str, Any]:
    if value == "-":
        payload = sys.stdin.read()
    else:
        payload = Path(value).read_text(encoding="utf-8")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise LedgerError("JSON input must be an object")
    return parsed


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    init = subparsers.add_parser("init")
    init.add_argument("--target", action="append", required=True)
    init.add_argument("--baseline", action="append", default=[])
    init.add_argument("--repo")
    init.add_argument("--skill-version", default="dev")

    record = subparsers.add_parser("record")
    record.add_argument("--ledger", required=True)
    record.add_argument("--input", required=True)

    status = subparsers.add_parser("status")
    status.add_argument("--ledger", required=True)

    authorize = subparsers.add_parser("authorize")
    authorize.add_argument("--ledger", required=True)
    authorize.add_argument("--manifest-hash", required=True)
    authorize.add_argument("--source", required=True)

    verify = subparsers.add_parser("verify")
    verify.add_argument("--ledger", required=True)
    verify.add_argument("--manifest-hash")
    verify.add_argument("--apply-output")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "init":
            ledger_path = init_ledger(
                args.target,
                args.baseline,
                repo_root=args.repo,
                skill_version=args.skill_version,
            )
            output: dict[str, Any] = {"ledger": str(ledger_path), **status_ledger(ledger_path)}
        elif args.command == "record":
            record_ledger(args.ledger, _load_json_argument(args.input))
            output = status_ledger(args.ledger)
        elif args.command == "status":
            output = status_ledger(args.ledger)
        elif args.command == "authorize":
            output = authorize_ledger(args.ledger, args.manifest_hash, _load_json_argument(args.source))
        elif args.command == "verify" and args.apply_output:
            output = apply_verified_output(args.ledger, args.apply_output)
        else:
            output = verify_ledger(args.ledger, args.manifest_hash)
        print(json.dumps(output, ensure_ascii=False, sort_keys=True))
        return 0 if args.command != "verify" or output.get("applied") or output["ok"] else 1
    except (LedgerError, OSError, json.JSONDecodeError) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
