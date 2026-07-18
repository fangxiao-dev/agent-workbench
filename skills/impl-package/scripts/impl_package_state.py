#!/usr/bin/env python3
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import string
from pathlib import Path
from typing import Any


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "assets" / "impl-package-state-config.json"
CURRENT_CONTRACT_VERSION = "3.2"
CONTRACT_VERSION_PATTERN = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def _contract_version(value: Any) -> tuple[int, int] | None:
    """Parse the canonical string contract version without float semantics."""
    if not isinstance(value, str):
        return None
    match = CONTRACT_VERSION_PATTERN.fullmatch(value)
    return (int(match.group(1)), int(match.group(2))) if match else None


def _contract_status_for_version(value: Any) -> str:
    parsed = _contract_version(value)
    current = _contract_version(CURRENT_CONTRACT_VERSION)
    if parsed is None or current is None:
        return "invalid"
    if parsed == current:
        return "current"
    return "upgradeRequired" if parsed < current else "unsupportedFuture"


def _load_config(path: Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    try:
        config = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"cannot load Impl-Package state config: {path}: {exc}") from exc
    if not isinstance(config, dict) or set(config) != {"contractVersion", "stateVocabulary", "documents", "projections", "gate"}:
        raise RuntimeError("Impl-Package state config has invalid top-level shape")
    if config.get("contractVersion") != CURRENT_CONTRACT_VERSION:
        raise RuntimeError(f"unsupported Impl-Package contractVersion: {config.get('contractVersion')!r}")
    vocab = config["stateVocabulary"]
    if not isinstance(vocab, dict) or set(vocab) != {"task", "legacyTaskRead", "ticket", "gateVerdict", "terminalGateVerdict", "initialState"}:
        raise RuntimeError("Impl-Package state vocabulary has invalid shape")
    for name in ("task", "ticket", "gateVerdict", "terminalGateVerdict"):
        values = vocab[name]
        if not isinstance(values, list) or not values or len(values) != len(set(values)) or any(not isinstance(value, str) or not value for value in values):
            raise RuntimeError(f"Impl-Package {name} vocabulary must contain unique non-empty strings")
    legacy_task_read = vocab["legacyTaskRead"]
    if (
        not isinstance(legacy_task_read, list)
        or len(legacy_task_read) != len(set(legacy_task_read))
        or any(not isinstance(value, str) or not value for value in legacy_task_read)
        or set(legacy_task_read) & set(vocab["task"])
    ):
        raise RuntimeError("legacyTaskRead must contain unique task states outside the writable vocabulary")
    if not set(vocab["terminalGateVerdict"]).issubset(vocab["gateVerdict"]):
        raise RuntimeError("terminal gate verdicts must be a subset of gate verdicts")
    if not isinstance(vocab["initialState"], dict) or set(vocab["initialState"]) != {"task", "ticket"}:
        raise RuntimeError("initialState must define task and ticket")
    if vocab["initialState"]["task"] not in vocab["task"] or vocab["initialState"]["ticket"] not in vocab["ticket"]:
        raise RuntimeError("initialState values must belong to their vocabularies")
    documents = config["documents"]
    document_keys = {
        "compositionPattern", "attemptPattern", "ticketIdPattern", "taskHeadingPattern", "taskBlockPattern",
        "taskStatePattern", "taskTableRowPattern", "ticketStatePattern", "dagArtifactPatterns", "ticketArtifactPatterns", "revisionDeclarationPattern",
    }
    if not isinstance(documents, dict) or set(documents) != document_keys:
        raise RuntimeError("Impl-Package document configuration has invalid shape")
    capture_arity = {
        "compositionPattern": 2,
        "attemptPattern": 1,
        "ticketIdPattern": 1,
        "taskHeadingPattern": 1,
        "taskStatePattern": 1,
        "taskTableRowPattern": 1,
        "ticketStatePattern": 1,
        "revisionDeclarationPattern": 0,
    }
    for key, expected_groups in capture_arity.items():
        try:
            compiled = re.compile(documents[key])
        except (TypeError, re.error) as exc:
            raise RuntimeError(f"invalid configured regex {key}: {exc}") from exc
        if compiled.groups != expected_groups:
            raise RuntimeError(f"configured regex {key} must expose exactly {expected_groups} capture groups")
    if "{task_id}" not in documents["taskBlockPattern"]:
        raise RuntimeError("taskBlockPattern must contain {task_id}")
    try:
        re.compile(documents["taskBlockPattern"].format(task_id="T1"))
    except (TypeError, re.error) as exc:
        raise RuntimeError(f"invalid configured regex taskBlockPattern: {exc}") from exc
    for key in ("dagArtifactPatterns", "ticketArtifactPatterns"):
        if not isinstance(documents[key], list) or not documents[key] or any(not isinstance(value, str) or not value for value in documents[key]):
            raise RuntimeError(f"{key} must contain non-empty glob strings")
    projections = config["projections"]
    if not isinstance(projections, dict) or set(projections) != {"markers", "revisionSet", "runtimeTask", "runtimeTicket", "gateStatus"}:
        raise RuntimeError("Impl-Package projection configuration has invalid shape")
    if set(projections["markers"]) != {"revisionSet", "runtimeState", "gateStatus"} or set(projections["revisionSet"]) != {"decision", "spec", "plan"}:
        raise RuntimeError("Impl-Package marker or revision projection configuration is invalid")
    marker_values = list(projections["markers"].values())
    if len(marker_values) != len(set(marker_values)) or any(not isinstance(value, str) or not value or re.search(r"\s", value) for value in marker_values):
        raise RuntimeError("Impl-Package marker names must be unique non-empty tokens")
    if set(projections["runtimeTask"]) != {"header", "row"} or set(projections["gateStatus"]) != {"empty", "finalized"}:
        raise RuntimeError("Impl-Package runtime projection configuration is invalid")
    def fields(template: Any) -> set[str]:
        if not isinstance(template, str) or not template:
            raise RuntimeError("Impl-Package projection templates must be non-empty strings")
        return {field for _, field, _, _ in string.Formatter().parse(template) if field is not None}
    expected_projection_fields = {
        ("revisionSet", "decision"): {"decision"},
        ("revisionSet", "spec"): {"decision", "spec"},
        ("revisionSet", "plan"): {"decision", "spec", "plan"},
        ("gateStatus", "empty"): set(),
        ("gateStatus", "finalized"): {"id", "verdict"},
    }
    for (section, name), expected in expected_projection_fields.items():
        if fields(projections[section][name]) != expected:
            raise RuntimeError(f"Impl-Package projection {section}.{name} has invalid placeholders")
    runtime_task = projections["runtimeTask"]
    if not isinstance(runtime_task["header"], list) or not runtime_task["header"] or any(not isinstance(line, str) or not line for line in runtime_task["header"]):
        raise RuntimeError("runtimeTask.header must contain non-empty strings")
    if fields(runtime_task["row"]) != {"id", "state", "evidence"} or fields(projections["runtimeTicket"]) != {"state", "evidence"}:
        raise RuntimeError("runtime projection placeholders are invalid")
    gate = config["gate"]
    if not isinstance(gate, dict) or set(gate) != {"headingPattern", "entryIdPattern", "attemptFieldPattern", "supersedesFieldPattern", "revisionSetFieldPattern", "noneTokens", "scaffoldNoneToken"}:
        raise RuntimeError("Impl-Package gate configuration has invalid shape")
    if any(token in gate["headingPattern"] for token in (".*", ".+", "(?s", "\\Z", "(?=")):
        raise RuntimeError("gate headingPattern may describe only one heading line; entry span is fixed by the safety kernel")
    try:
        heading = re.compile(gate["headingPattern"].format(verdicts="|".join(map(re.escape, vocab["gateVerdict"]))), re.M)
        entry_id = re.compile(gate["entryIdPattern"])
        attempt_field = re.compile(gate["attemptFieldPattern"])
        supersedes_field = re.compile(gate["supersedesFieldPattern"])
        revision_set_field = re.compile(gate["revisionSetFieldPattern"])
    except (KeyError, TypeError, re.error) as exc:
        raise RuntimeError(f"invalid configured gate regex: {exc}") from exc
    if set(heading.groupindex) != {"id", "verdict"} or entry_id.groups < 2 or attempt_field.groups < 1 or supersedes_field.groups < 1 or revision_set_field.groups != 3:
        raise RuntimeError("configured gate regexes do not expose required capture groups")
    heading_sample = f"## initial-G1 · {vocab['gateVerdict'][0]}\n"
    heading_match = heading.fullmatch(heading_sample)
    if heading_match is None or heading_match.group("id") != "initial-G1" or heading_match.group("verdict") != vocab["gateVerdict"][0]:
        raise RuntimeError("configured gate headingPattern must match exactly one canonical heading line")
    if not isinstance(gate["noneTokens"], list) or not gate["noneTokens"] or any(not isinstance(value, str) or not value for value in gate["noneTokens"]):
        raise RuntimeError("gate noneTokens must contain non-empty strings")
    if not isinstance(gate["scaffoldNoneToken"], str) or gate["scaffoldNoneToken"] not in gate["noneTokens"]:
        raise RuntimeError("gate scaffoldNoneToken must be one of noneTokens")
    return config


CONFIG = _load_config()
RUNTIME_STATE = Path(".impl-package/runtime-state.json")
REVISION_BINDINGS = Path(".impl-package/revision-bindings.json")
TASK_STATES = frozenset(CONFIG["stateVocabulary"]["task"])
LEGACY_TASK_READ_STATES = frozenset(CONFIG["stateVocabulary"]["legacyTaskRead"])
TASK_READ_STATES = TASK_STATES | LEGACY_TASK_READ_STATES
TICKET_STATES = frozenset(CONFIG["stateVocabulary"]["ticket"])
GATE_VERDICTS = frozenset(CONFIG["stateVocabulary"]["gateVerdict"])
TERMINAL_GATE_VERDICTS = frozenset(CONFIG["stateVocabulary"]["terminalGateVerdict"])
GATE_HEADING_PATTERN = CONFIG["gate"]["headingPattern"].format(verdicts="|".join(map(re.escape, GATE_VERDICTS)))
GATE_BLOCK_RE = re.compile(rf"(?ms){GATE_HEADING_PATTERN}.*?(?=^##\s|\Z)")


class StateError(RuntimeError):
    pass


def _require_current_contract(state: Any, label: str) -> None:
    if not isinstance(state, dict):
        raise StateError(f"{label} is not a JSON object")
    status = (
        "upgradeRequired"
        if "contractVersion" not in state
        else _contract_status_for_version(state.get("contractVersion"))
    )
    if status == "current":
        if "schemaVersion" in state:
            raise StateError(f"invalid {label}: legacy schemaVersion is not supported")
        return
    if status == "upgradeRequired":
        raise StateError(f"{label} contract upgrade required (current: {CURRENT_CONTRACT_VERSION})")
    if status == "unsupportedFuture":
        raise StateError(f"unsupported future {label} contractVersion: {state.get('contractVersion')!r}")
    raise StateError(f"invalid {label} contractVersion: {state.get('contractVersion')!r}")


def _atomic_write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _atomic_write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    except BaseException:
        try:
            os.unlink(temp_name)
        except FileNotFoundError:
            pass
        raise


def _empty_runtime_state(package_id: str) -> dict[str, Any]:
    return {
        "contractVersion": CURRENT_CONTRACT_VERSION,
        "purpose": "internal-machine-sidecar",
        "ownerFacing": False,
        "packageId": package_id,
        "tasks": [],
        "tickets": [],
        "artifacts": [],
        "gate": {"allocations": [], "entries": []},
    }


def _empty_revision_bindings() -> dict[str, Any]:
    return {
        "contractVersion": CURRENT_CONTRACT_VERSION,
        "purpose": "internal-machine-sidecar",
        "ownerFacing": False,
        "current": {},
        "bindings": [],
    }


def _current_attempt(package: Path) -> tuple[str, Path] | None:
    path = package / REVISION_BINDINGS
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    attempt = state.get("current", {}).get("attempt")
    if not attempt:
        return None
    return attempt["id"], _package_artifact(package, attempt["plan"])


def _current_revision_set(package: Path) -> dict[str, str] | None:
    path = package / REVISION_BINDINGS
    if not path.is_file():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    current = state.get("current", {})
    _assert_revision_selection_keys(current)
    return {
        "decision": current.get("decision", {}).get("revision", "N/A"),
        "spec": current.get("spec", {}).get("revision", "N/A"),
        "plan": current.get("attempt", {}).get("revision", "N/A"),
    }


def _assert_revision_selection_keys(current: Any) -> None:
    if not isinstance(current, dict):
        raise StateError("revision current selection must be an object")
    unsupported = sorted(set(current) - {"decision", "spec", "attempt"})
    if unsupported:
        raise StateError(f"unsupported revision selection key: {unsupported[0]}")


def _composition(plan_text: str) -> tuple[bool, bool]:
    match = re.search(CONFIG["documents"]["compositionPattern"], plan_text, re.I)
    if not match:
        raise StateError("current plan has no parseable Composition declaration")
    return match.group(1).lower() == "true", match.group(2).lower() == "true"


def _document_attempt(text: str) -> str | None:
    match = re.search(CONFIG["documents"]["attemptPattern"], text)
    return match.group(1) if match else None


def _package_file_names(package: Path, committed: bool) -> list[str]:
    if not committed:
        return [
            path.relative_to(package).as_posix()
            for path in package.rglob("*")
            if path.is_file() and not _is_investigation_path(path.relative_to(package).as_posix())
        ]
    repo = _git_root(package)
    package_relative = package.resolve().relative_to(repo).as_posix()
    output = _git(repo, "ls-tree", "-r", "--name-only", "HEAD", "--", package_relative)
    prefix = package_relative.rstrip("/") + "/"
    return [
        line[len(prefix) :]
        for line in output.splitlines()
        if line.startswith(prefix) and not _is_investigation_path(line[len(prefix) :])
    ]


def _attempt_dag_artifact(package: Path, attempt: str, committed: bool = False) -> str | None:
    patterns = CONFIG["documents"]["dagArtifactPatterns"]
    candidates = [name for name in _package_file_names(package, committed) if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)]
    matches = [name for name in candidates if _document_attempt(_state_document(package, name, committed)) == attempt]
    if len(matches) > 1:
        raise StateError(f"earned DAG for attempt {attempt} resolves to {len(matches)} candidate files")
    return matches[0] if matches else None


def _attempt_ticket_documents(package: Path, attempt: str, committed: bool = False) -> dict[str, tuple[str, str]]:
    documents: dict[str, tuple[str, str]] = {}
    patterns = CONFIG["documents"]["ticketArtifactPatterns"]
    names = [name for name in _package_file_names(package, committed) if any(fnmatch.fnmatchcase(name, pattern) for pattern in patterns)]
    for name in sorted(names):
        text = _state_document(package, name, committed)
        if _document_attempt(text) != attempt:
            continue
        id_match = re.search(CONFIG["documents"]["ticketIdPattern"], text)
        if not id_match or id_match.group(1) in documents:
            raise StateError("earned ticket identity is missing or duplicated")
        documents[id_match.group(1)] = (name, text)
    return documents


def _dag_task_ids(dag_text: str) -> tuple[list[str], bool]:
    """Return task IDs from a legacy task-record DAG or the current minimal table."""
    legacy_ids = re.findall(CONFIG["documents"]["taskHeadingPattern"], dag_text)
    if legacy_ids:
        if len(legacy_ids) != len(set(legacy_ids)):
            raise StateError("earned DAG has duplicate task records")
        return legacy_ids, True
    runtime_marker = f"<!-- impl-package:projection {CONFIG['projections']['markers']['runtimeState']} begin -->"
    task_graph = dag_text.split(runtime_marker, 1)[0]
    table_ids = re.findall(CONFIG["documents"]["taskTableRowPattern"], task_graph)
    if len(table_ids) != len(set(table_ids)):
        raise StateError("minimal Task DAG table has duplicate task IDs")
    return table_ids, False


def _seed_earned_records(package: Path, state: dict[str, Any], revision_state: dict[str, Any] | None = None) -> None:
    if revision_state is None:
        current = _current_attempt(package)
    else:
        selection = revision_state.get("current", {}).get("attempt")
        current = (selection["id"], _package_artifact(package, selection["plan"])) if selection else None
    if current is None:
        return
    attempt, plan_path = current
    tickets_earned, dag_earned = _composition(plan_path.read_text(encoding="utf-8"))
    if dag_earned:
        dag_artifact = _attempt_dag_artifact(package, attempt)
        if dag_artifact:
            dag_path = package / dag_artifact
            dag_text = dag_path.read_text(encoding="utf-8")
            task_ids, legacy_records = _dag_task_ids(dag_text)
            if not task_ids:
                raise StateError("earned DAG contains no task records")
            task_records = []
            existing_tasks = {
                row["id"]: row for row in state.get("tasks", []) if row.get("attempt") == attempt
            }
            for task_id in task_ids:
                if task_id in existing_tasks:
                    task_records.append(existing_tasks[task_id])
                    continue
                task_state = CONFIG["stateVocabulary"]["initialState"]["task"]
                if legacy_records:
                    block_pattern = CONFIG["documents"]["taskBlockPattern"].format(task_id=re.escape(task_id))
                    block_match = re.search(block_pattern, dag_text)
                    assert block_match is not None
                    state_match = re.search(CONFIG["documents"]["taskStatePattern"], block_match.group(0))
                    task_state = state_match.group(1) if state_match else task_state
                if task_state not in TASK_READ_STATES:
                    raise StateError(f"unsupported task state for {task_id}: {task_state}")
                task_records.append(
                    {
                        "attempt": attempt,
                        "id": task_id,
                        "state": task_state,
                        "evidence": f"{dag_path.relative_to(package).as_posix()}#{task_id}",
                    }
                )
            state["tasks"] = [
                row for row in state.get("tasks", []) if row.get("attempt") != attempt
            ] + task_records
    if tickets_earned:
        ticket_documents = _attempt_ticket_documents(package, attempt)
        ticket_records = []
        existing_tickets = {
            row["id"]: row for row in state.get("tickets", []) if row.get("attempt") == attempt
        }
        for ticket_id, (ticket_artifact, text) in ticket_documents.items():
            if ticket_id in existing_tickets:
                ticket_records.append(existing_tickets[ticket_id])
                continue
            value_match = re.search(CONFIG["documents"]["ticketStatePattern"], text)
            ticket_state = (
                value_match.group(1).strip().upper().replace(" ", "_")
                if value_match
                else CONFIG["stateVocabulary"]["initialState"]["ticket"]
            )
            if ticket_state not in TICKET_STATES:
                raise StateError(f"unsupported ticket state for {ticket_id}: {ticket_state}")
            ticket_records.append(
                {
                    "attempt": attempt,
                    "id": ticket_id,
                    "state": ticket_state,
                    "evidence": f"{ticket_artifact}#runtime-acceptance-status",
                }
            )
        if ticket_documents:
            state["tickets"] = [
                row for row in state.get("tickets", []) if row.get("attempt") != attempt
            ] + ticket_records


def command_init(package: Path, package_id: str) -> dict[str, Any]:
    if not package.is_dir():
        raise StateError(f"package directory does not exist: {package}")
    runtime_path = package / RUNTIME_STATE
    revision_path = package / REVISION_BINDINGS
    runtime = _empty_runtime_state(package_id)
    revision = _empty_revision_bindings()

    if runtime_path.exists():
        runtime = json.loads(runtime_path.read_text(encoding="utf-8"))
        _require_current_contract(runtime, "runtime state")
        if runtime.get("packageId") != package_id:
            raise StateError(f"packageId mismatch: expected {package_id!r}, found {runtime.get('packageId')!r}")
    if revision_path.exists():
        revision = json.loads(revision_path.read_text(encoding="utf-8"))
        _require_current_contract(revision, "revision bindings")
        if (
            set(revision) != {"contractVersion", "purpose", "ownerFacing", "current", "bindings"}
            or revision.get("purpose") != "internal-machine-sidecar"
            or revision.get("ownerFacing") is not False
            or not isinstance(revision.get("current"), dict)
            or not isinstance(revision.get("bindings"), list)
        ):
            raise StateError("revision sidecar has invalid initialization envelope")

    before = json.dumps(runtime, sort_keys=True)
    _seed_earned_records(package, runtime)
    if not revision_path.exists():
        _atomic_write_json(revision_path, revision)
    if not runtime_path.exists() or json.dumps(runtime, sort_keys=True) != before:
        _atomic_write_json(runtime_path, runtime)
    return runtime


def _load_runtime_state(package: Path) -> tuple[Path, dict[str, Any]]:
    path = package / RUNTIME_STATE
    if not path.is_file():
        raise StateError(f"runtime state does not exist: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    _require_current_contract(state, "runtime state")
    return path, state


def command_set_state(
    package: Path,
    kind: str,
    identifier: str,
    target: str,
    attempt: str,
    expected: str,
    evidence: str,
) -> dict[str, Any]:
    path, state = _load_runtime_state(package)
    current = _current_attempt(package)
    if current is None or current[0] != attempt:
        raise StateError(f"current attempt mismatch: expected {attempt!r}")
    if any(
        row.get("attempt") == attempt and row.get("verdict") in TERMINAL_GATE_VERDICTS
        for row in state.get("gate", {}).get("entries", [])
    ):
        raise StateError(f"attempt is frozen by terminal gate: {attempt}")
    key = "tasks" if kind == "task" else "tickets"
    allowed = TASK_STATES if kind == "task" else TICKET_STATES
    if target not in allowed:
        raise StateError(f"unsupported {kind} state: {target}")
    matches = [row for row in state.get(key, []) if row.get("attempt") == attempt and row.get("id") == identifier]
    if len(matches) != 1:
        raise StateError(f"{kind} {identifier} resolves to {len(matches)} runtime records")
    record = matches[0]
    if record.get("state") == target and record.get("evidence") == evidence:
        return state
    if record.get("state") != expected:
        raise StateError(f"expected state {expected!r}, found {record.get('state')!r}")
    record["state"] = target
    record["evidence"] = evidence
    _atomic_write_json(path, state)
    _refresh_runtime_projections(package, state, attempt)
    return state


def _runtime_dag_path(package: Path, attempt: str) -> Path:
    artifact = _attempt_dag_artifact(package, attempt)
    if artifact is None:
        raise StateError(f"earned DAG for attempt {attempt} is missing")
    return package / artifact


def _refresh_runtime_projections(package: Path, state: dict[str, Any], attempt: str) -> list[str]:
    changed: list[str] = []
    tasks = [row for row in state.get("tasks", []) if row.get("attempt") == attempt]
    if tasks:
        dag_path = _runtime_dag_path(package, attempt)
        text = dag_path.read_text(encoding="utf-8")
        runtime_task = CONFIG["projections"]["runtimeTask"]
        rows = list(runtime_task["header"])
        rows.extend(runtime_task["row"].format(**row) for row in tasks)
        updated = _replace_projection(text, CONFIG["projections"]["markers"]["runtimeState"], "\n".join(rows))
        if updated != text:
            _atomic_write_text(dag_path, updated)
            changed.append(dag_path.relative_to(package).as_posix())
    tickets = [row for row in state.get("tickets", []) if row.get("attempt") == attempt]
    if tickets:
        ticket_files = {identifier: package / artifact for identifier, (artifact, _) in _attempt_ticket_documents(package, attempt).items()}
        for row in tickets:
            ticket_path = ticket_files.get(row["id"])
            if ticket_path is None:
                raise StateError(f"ticket projection target missing: {row['id']}")
            text = ticket_path.read_text(encoding="utf-8")
            body = CONFIG["projections"]["runtimeTicket"].format(**row)
            updated = _replace_projection(text, CONFIG["projections"]["markers"]["runtimeState"], body)
            if updated != text:
                _atomic_write_text(ticket_path, updated)
                changed.append(ticket_path.relative_to(package).as_posix())
    return changed


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append_artifact(state: dict[str, Any], record: dict[str, Any]) -> bool:
    existing = next((row for row in state.get("artifacts", []) if row.get("id") == record["id"]), None)
    if existing is not None:
        if existing != record:
            raise StateError(f"artifact ID collision: {record['id']}")
        return False
    known = {row.get("id") for row in state.get("artifacts", [])}
    record_types = {row.get("id"): row.get("recordType") for row in state.get("artifacts", [])}
    active = set(known)
    for row in state.get("artifacts", []):
        active.difference_update(row.get("supersedes") or [])
        if row.get("tombstones"):
            active.discard(row["tombstones"])
    pointers = list(record.get("supersedes") or [])
    if record.get("tombstones"):
        pointers.append(record["tombstones"])
    missing = [pointer for pointer in pointers if pointer not in active]
    if missing:
        raise StateError(f"artifact pointer does not resolve to an active record: {missing}")
    if record.get("recordType") == "artifact" and any(record_types.get(pointer) != "artifact" for pointer in pointers):
        raise StateError("artifact supersedes must target active artifact records")
    state.setdefault("artifacts", []).append(record)
    return True


def _is_investigation_path(artifact_path: str) -> bool:
    path_parts = [part.casefold() for part in artifact_path.replace("\\", "/").split("/") if part]
    return "investigations" in path_parts


def _reject_investigation_artifact(artifact_path: str, kind: str) -> None:
    if kind.casefold() in {"investigation", "investigations"} or _is_investigation_path(artifact_path):
        raise StateError("investigations are not structured runtime artifacts")


def command_record_artifact(
    package: Path,
    identifier: str,
    artifact_path: str,
    kind: str,
    evidence: str,
    supersedes: list[str] | None = None,
) -> dict[str, Any]:
    path, state = _load_runtime_state(package)
    _reject_investigation_artifact(artifact_path, kind)
    source = Path(artifact_path).resolve()
    if not source.is_file():
        raise StateError(f"artifact file does not exist: {source}")
    record = {
        "recordType": "artifact",
        "id": identifier,
        "kind": kind,
        "path": artifact_path,
        "hash": {"algorithm": "sha256", "value": _sha256_file(source)},
        "supersedes": list(supersedes or []),
        "tombstones": None,
        "evidence": evidence,
    }
    if _append_artifact(state, record):
        _atomic_write_json(path, state)
    return state


def command_tombstone_artifact(
    package: Path, identifier: str, target: str, evidence: str
) -> dict[str, Any]:
    path, state = _load_runtime_state(package)
    record = {
        "recordType": "tombstone",
        "id": identifier,
        "kind": None,
        "path": None,
        "hash": None,
        "supersedes": [],
        "tombstones": target,
        "evidence": evidence,
    }
    if _append_artifact(state, record):
        _atomic_write_json(path, state)
    return state


def _canonical_gate_block(block: str) -> str:
    normalized = block.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    return normalized.rstrip("\n") + "\n"


def gate_block_hash(block: str) -> str:
    return hashlib.sha256(_canonical_gate_block(block).encode("utf-8")).hexdigest()


def _gate_blocks(text: str) -> list[dict[str, Any]]:
    blocks = []
    for match in GATE_BLOCK_RE.finditer(text.replace("\r\n", "\n").replace("\r", "\n")):
        entry_id = match.group("id")
        id_match = re.fullmatch(CONFIG["gate"]["entryIdPattern"], entry_id)
        attempt = id_match.group(1) if id_match else None
        number = int(id_match.group(2)) if id_match else None
        block = match.group(0)
        attempt_match = re.search(CONFIG["gate"]["attemptFieldPattern"], block)
        supersedes_match = re.search(CONFIG["gate"]["supersedesFieldPattern"], block)
        revision_set_match = re.search(CONFIG["gate"]["revisionSetFieldPattern"], block)
        supersedes = supersedes_match.group(1) if supersedes_match else None
        if supersedes in CONFIG["gate"]["noneTokens"]:
            supersedes = None
        blocks.append(
            {
                "id": entry_id,
                "attempt": attempt_match.group(1) if attempt_match else attempt,
                "number": number,
                "verdict": match.group("verdict"),
                "supersedes": supersedes,
                "revisionSet": (
                    {
                        "decision": revision_set_match.group(1),
                        "spec": revision_set_match.group(2),
                        "plan": revision_set_match.group(3),
                    }
                    if revision_set_match
                    else None
                ),
                "block": block,
            }
        )
    return blocks


def _gate_header() -> str:
    marker = CONFIG["projections"]["markers"]["gateStatus"]
    return (
        "# 门禁账本（Gate Ledger）\n\n"
        f"<!-- impl-package:projection {marker} begin -->\n"
        f"{CONFIG['projections']['gateStatus']['empty']}\n"
        f"<!-- impl-package:projection {marker} end -->\n\n"
        "> 最新记录在前、仅允许追加。已存在 entry 不得修改。\n\n"
    )


def _gate_scaffold(entry_id: str, attempt: str, supersedes: str | None) -> str:
    verdict_choices = "|".join(CONFIG["stateVocabulary"]["gateVerdict"])
    none_token = CONFIG["gate"]["scaffoldNoneToken"]
    return (
        f"## {entry_id} · <{verdict_choices}>\n\n"
        f"- 执行尝试 ID（Attempt ID）：{attempt}\n"
        f"- 取代（Supersedes）：{supersedes or none_token}\n"
        "- 评估时间（Evaluated at）：\n"
        "- 修订集合（Revision set）：\n"
        "- 绑定校验（Binding validation）：\n"
        "- 执行组合（Composition）：\n"
        "- 比较点（Comparison point）：\n"
        "- 证据（Evidence）：\n"
        "- 未解决 blocker / deferred item：\n"
        "- 判决理由（Verdict reason）：\n\n"
        "### 长期增量（Durable Deltas）\n\n"
        "- 无\n\n"
    )


def _insert_latest_gate(text: str, scaffold: str) -> str:
    first_entry = re.search(r"(?m)^##\s", text)
    if first_entry:
        return text[: first_entry.start()] + scaffold + text[first_entry.start() :]
    return text.rstrip() + "\n\n" + scaffold


def command_new_gate_entry(
    package: Path, attempt: str, operation_id: str
) -> dict[str, Any]:
    state_path, state = _load_runtime_state(package)
    allocations = state.setdefault("gate", {}).setdefault("allocations", [])
    existing = [row for row in allocations if row.get("operationId") == operation_id]
    if len(existing) > 1:
        raise StateError(f"duplicate gate operationId: {operation_id}")
    if existing:
        allocation = existing[0]
        if allocation.get("attempt") != attempt:
            raise StateError(f"gate operationId attempt mismatch: {operation_id}")
    else:
        numbers = [row["number"] for row in allocations if row.get("attempt") == attempt]
        number = max(numbers, default=0) + 1
        allocation = {
            "operationId": operation_id,
            "attempt": attempt,
            "number": number,
            "entryId": f"{attempt}-G{number}",
        }
        allocations.append(allocation)
        _atomic_write_json(state_path, state)
    gate_path = package / "gate.md"
    text = _package_artifact(package, "gate.md").read_text(encoding="utf-8") if gate_path.exists() else _gate_header()
    entry_id = allocation["entryId"]
    if not re.search(rf"(?m)^##\s+{re.escape(entry_id)}\s+·\s+", text):
        finalized = state.get("gate", {}).get("entries", [])
        prior = max(
            (row for row in finalized if row.get("attempt") == attempt),
            key=lambda row: row.get("number", 0),
            default=None,
        )
        text = _insert_latest_gate(text, _gate_scaffold(entry_id, attempt, prior.get("id") if prior else None))
        _atomic_write_text(gate_path, text)
    return {"entryId": entry_id, "number": allocation["number"], "operationId": operation_id}


def _replace_projection(text: str, name: str, body: str) -> str:
    pattern = re.compile(
        rf"(?ms)(<!-- impl-package:projection {re.escape(name)} begin -->\n).*?(<!-- impl-package:projection {re.escape(name)} end -->)"
    )
    updated, count = pattern.subn(rf"\g<1>{body.rstrip()}\n\g<2>", text)
    if count != 1:
        raise StateError(f"projection {name!r} resolves to {count} marker regions")
    return updated


def _machine_owned_contract(text: str, plan: bool) -> str:
    pattern = re.compile(
        r"(?ms)(<!-- impl-package:projection (?P<name>[^\s]+) begin -->\n).*?(<!-- impl-package:projection (?P=name) end -->)"
    )
    normalized = pattern.sub(
        lambda match: f"{match.group(1)}<impl-package-projection:{match.group('name')}>\n{match.group(3)}",
        text,
    )
    return _plan_contract(normalized) if plan else normalized


def _selection_for_alias(state: dict[str, Any], alias: str) -> dict[str, Any]:
    matches = []
    for key in ("decision", "spec", "attempt"):
        selection = state.get("current", {}).get(key)
        if selection and selection.get("revision") == alias:
            matches.append(selection)
    if len(matches) != 1:
        raise StateError(f"alias {alias} resolves to {len(matches)} current selections")
    return matches[0]


def _assert_projection_only(package: Path, binding: dict[str, Any], candidate_text: str) -> None:
    baseline = _git_blob_text(package, binding["blob"])
    plan = binding.get("mode") == "plan-contract-v1"
    if _machine_owned_contract(baseline, plan) != _machine_owned_contract(candidate_text, plan):
        raise StateError("diff outside machine-owned marker regions requires revision judgment")


def command_rebind(
    package: Path,
    alias: str,
    reason: str,
    evidence: str,
    confirm_contract_impact_none: bool,
) -> dict[str, Any]:
    path, state = _load_revision_state(package)
    selection = _selection_for_alias(state, alias)
    active = _active_binding(state, selection)
    artifact = active["artifact"]
    candidate_text = _artifact_text(package, artifact, committed=False)
    if reason == "projection":
        _assert_projection_only(package, active, candidate_text)
    elif not confirm_contract_impact_none:
        raise StateError("editorial rebind requires --confirm-contract-impact-none")
    blob = _worktree_blob(package, artifact)
    if blob == active.get("blob"):
        return state
    rebound = dict(active)
    rebound["blob"] = blob
    rebound["id"] = _binding_id(rebound)
    rebound["supersedes"] = active["id"]
    rebound["evidence"] = evidence
    existing = next((row for row in state.get("bindings", []) if row.get("id") == rebound["id"]), None)
    if existing is not None and existing != rebound:
        raise StateError(f"binding ID collision: {rebound['id']}")
    if existing is None:
        state.setdefault("bindings", []).append(rebound)
        _atomic_write_json(path, state)
    return state


def _revision_projection(state: dict[str, Any], kind: str) -> str:
    current = state.get("current", {})
    decision = current.get("decision", {}).get("revision", "N/A")
    spec = current.get("spec", {}).get("revision", "N/A")
    plan = current.get("attempt", {}).get("revision", "N/A")
    return CONFIG["projections"]["revisionSet"][kind].format(decision=decision, spec=spec, plan=plan)


def _validate_revision_projections(package: Path, state: dict[str, Any], committed: bool) -> None:
    marker = CONFIG["projections"]["markers"]["revisionSet"]
    targets: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    priority = {"decision": 0, "spec": 1, "plan": 2}
    for key, kind in (("decision", "decision"), ("spec", "spec"), ("attempt", "plan")):
        selection = state.get("current", {}).get(key)
        if not selection:
            continue
        artifact = selection.get("artifact") or selection.get("plan")
        current_kind, selections = targets.get(artifact, (kind, []))
        targets[artifact] = (kind if priority[kind] > priority[current_kind] else current_kind, selections + [selection])
    for artifact, (kind, _) in targets.items():
        text = _artifact_text(package, artifact, committed)
        try:
            projected = _replace_projection(text, marker, _revision_projection(state, kind))
        except StateError as exc:
            raise StateError(f"revision projection mismatch in {artifact}: {exc}") from exc
        if projected != text:
            raise StateError(f"revision projection mismatch in {artifact}")
        marker_elided = _machine_owned_contract(text, plan=False)
        if re.search(CONFIG["documents"]["revisionDeclarationPattern"], marker_elided):
            raise StateError(f"revision declaration outside machine-owned projection in {artifact}")


def command_refresh_projections(package: Path) -> dict[str, Any]:
    _, revision_state = _load_revision_state(package)
    targets: dict[str, tuple[str, list[dict[str, Any]]]] = {}
    priority = {"decision": 0, "spec": 1, "plan": 2}
    for key, kind in (("decision", "decision"), ("spec", "spec"), ("attempt", "plan")):
        selection = revision_state.get("current", {}).get(key)
        if not selection:
            continue
        artifact = selection.get("artifact") or selection.get("plan")
        current_kind, selections = targets.get(artifact, (kind, []))
        targets[artifact] = (kind if priority[kind] > priority[current_kind] else current_kind, selections + [selection])
    changes: list[tuple[list[str], Path, str, str]] = []
    for artifact, (kind, selections) in targets.items():
        artifact_path = _package_artifact(package, artifact)
        text = artifact_path.read_text(encoding="utf-8")
        revision_marker = CONFIG["projections"]["markers"]["revisionSet"]
        if f"<!-- impl-package:projection {revision_marker} begin -->" not in text:
            raise StateError(f"revision projection marker is missing: {artifact}")
        updated = _replace_projection(text, revision_marker, _revision_projection(revision_state, kind))
        if updated != text:
            for selection in selections:
                _assert_projection_only(package, _active_binding(revision_state, selection), updated)
            changes.append(([selection["revision"] for selection in selections], artifact_path, updated, artifact))
    for aliases, artifact_path, updated, _ in changes:
        _atomic_write_text(artifact_path, updated)
        for alias in aliases:
            command_rebind(package, alias, "projection", "machine:refresh-projections", False)
    changed_paths = [artifact for _, _, _, artifact in changes]
    runtime_path = package / RUNTIME_STATE
    current_attempt = revision_state.get("current", {}).get("attempt", {}).get("id")
    if runtime_path.is_file() and current_attempt:
        _, runtime_state = _load_runtime_state(package)
        changed_paths.extend(_refresh_runtime_projections(package, runtime_state, current_attempt))
        gate_path = package / "gate.md"
        if gate_path.is_file():
            text = _package_artifact(package, "gate.md").read_text(encoding="utf-8")
            entries = [row for row in runtime_state.get("gate", {}).get("entries", []) if row.get("attempt") == current_attempt]
            if entries:
                latest = max(entries, key=lambda row: row["number"])
                body = CONFIG["projections"]["gateStatus"]["finalized"].format(id=latest["id"], verdict=latest["verdict"])
            else:
                body = CONFIG["projections"]["gateStatus"]["empty"]
            updated = _replace_projection(text, CONFIG["projections"]["markers"]["gateStatus"], body)
            if updated != text:
                _atomic_write_text(gate_path, updated)
                changed_paths.append("gate.md")
    return {"changed": changed_paths}


def command_finalize_gate_entry(package: Path, entry_id: str) -> dict[str, Any]:
    state_path, state = _load_runtime_state(package)
    allocations = [
        row for row in state.get("gate", {}).get("allocations", []) if row.get("entryId") == entry_id
    ]
    if len(allocations) != 1:
        raise StateError(f"gate entry resolves to {len(allocations)} allocations: {entry_id}")
    allocation = allocations[0]
    gate_path = _package_artifact(package, "gate.md")
    blocks = [row for row in _gate_blocks(gate_path.read_text(encoding="utf-8")) if row["id"] == entry_id]
    if len(blocks) != 1:
        raise StateError(f"gate entry resolves to {len(blocks)} finalized Markdown blocks: {entry_id}")
    parsed = blocks[0]
    for field in ("attempt", "number"):
        if parsed[field] != allocation[field]:
            raise StateError(f"gate {field} mismatch for {entry_id}")
    current_revision_set = _current_revision_set(package)
    if parsed.get("revisionSet") is None:
        raise StateError(f"gate revision set is missing for {entry_id}")
    if current_revision_set is None or parsed["revisionSet"] != current_revision_set:
        raise StateError(f"gate revision set does not match current revisions for {entry_id}")
    prior = [
        row for row in state.get("gate", {}).get("entries", [])
        if row.get("attempt") == parsed["attempt"] and row.get("id") != entry_id
    ]
    expected_supersedes = prior[-1]["id"] if prior else None
    if parsed.get("supersedes") != expected_supersedes:
        raise StateError(f"gate supersedes mismatch for {entry_id}")
    record = {
        "id": entry_id,
        "attempt": parsed["attempt"],
        "number": parsed["number"],
        "verdict": parsed["verdict"],
        "supersedes": parsed["supersedes"],
        "entry": {
            "path": "gate.md",
            "anchor": entry_id,
            "bindingMode": "gate-entry-v1",
            "contentSha256": gate_block_hash(parsed["block"]),
        },
    }
    entries = state.setdefault("gate", {}).setdefault("entries", [])
    existing = next((row for row in entries if row.get("id") == entry_id), None)
    if existing is not None and existing != record:
        raise StateError(f"finalized gate entry changed after indexing: {entry_id}")
    if existing is None:
        entries.append(record)
        _atomic_write_json(state_path, state)
    text = gate_path.read_text(encoding="utf-8")
    gate_status = CONFIG["projections"]["gateStatus"]["finalized"].format(id=entry_id, verdict=parsed["verdict"])
    text = _replace_projection(text, CONFIG["projections"]["markers"]["gateStatus"], gate_status)
    _atomic_write_text(gate_path, text)
    return record


def resolve_gate(package: Path) -> dict[str, Any]:
    gate_path = package / "gate.md"
    if not gate_path.is_file():
        return {
            "kind": None,
            "hasGate": False,
            "gateResolution": None,
            "appliesToCurrentRevision": None,
            "needsManualGateReview": False,
            "reason": None,
        }
    try:
        text = _package_artifact(package, "gate.md").read_text(encoding="utf-8")
    except StateError as exc:
        return {
            "kind": "mismatch", "hasGate": True, "entryId": None, "gateResolution": None,
            "appliesToCurrentRevision": None,
            "needsManualGateReview": True, "reason": str(exc),
        }
    blocks = _gate_blocks(text)
    runtime_path = package / RUNTIME_STATE
    if not runtime_path.is_file():
        return {
            "kind": "manual",
            "hasGate": True,
            "entryId": None,
            "gateResolution": None,
            "appliesToCurrentRevision": None,
            "needsManualGateReview": True,
            "reason": "runtime state is missing; gate cannot be trusted",
        }
    try:
        state = json.loads(runtime_path.read_text(encoding="utf-8"))
        _require_current_contract(state, "runtime state")
        _validate_gate_index(state, text)
        current = _current_attempt(package)
        if current is None:
            raise StateError("current attempt cannot be resolved")
        current_attempt = current[0]
        gate = state.get("gate", {})
        entries = [row for row in gate.get("entries", []) if row.get("attempt") == current_attempt]
        if not entries:
            current_allocations = [row for row in gate.get("allocations", []) if row.get("attempt") == current_attempt]
            current_blocks = [row for row in blocks if row.get("attempt") == current_attempt]
            if current_allocations or current_blocks:
                raise StateError(f"runtime gate index has an unfinished entry for current attempt: {current_attempt}")
            indexed_by_id = {row.get("id"): row for row in gate.get("entries", [])}
            index = next((indexed_by_id.get(block.get("id")) for block in blocks if block.get("id") in indexed_by_id), None)
            if index is None:
                return {
                    "kind": None,
                    "hasGate": True,
                    "entryId": None,
                    "gateResolution": None,
                    "appliesToCurrentRevision": None,
                    "needsManualGateReview": False,
                    "reason": None,
                }
        else:
            index = max(entries, key=lambda row: row.get("number", 0))
        allocations = [row for row in gate.get("allocations", []) if row.get("entryId") == index.get("id")]
        if len(allocations) != 1:
            raise StateError("finalized gate entry has no unique matching allocation")
        allocation = allocations[0]
        expected_id = f"{index.get('attempt')}-G{index.get('number')}"
        if (
            not isinstance(index.get("number"), int)
            or isinstance(index.get("number"), bool)
            or index["number"] < 1
            or index.get("id") != expected_id
            or any(index.get(field) != allocation.get(source) for field, source in (("id", "entryId"), ("attempt", "attempt"), ("number", "number")))
        ):
            raise StateError("finalized gate entry does not match its allocation")
        matches = [row for row in blocks if row["id"] == index.get("id")]
        if len(matches) != 1:
            raise StateError("indexed Markdown entry is missing or duplicated")
        parsed = matches[0]
        entry_revision_set = parsed.get("revisionSet")
        if entry_revision_set is None:
            raise StateError("indexed gate entry has no parseable revision set")
        current_revision_set = _current_revision_set(package)
        if current_revision_set is None:
            raise StateError("current revision set cannot be resolved")
        expected = index.get("entry", {})
        if expected.get("path") != "gate.md" or expected.get("anchor") != index.get("id"):
            raise StateError("gate pointer is not package-local gate.md")
        if expected.get("bindingMode") != "gate-entry-v1":
            raise StateError("unsupported gate binding mode")
        if expected.get("contentSha256") != gate_block_hash(parsed["block"]):
            raise StateError("gate entry content binding mismatch")
        for field in ("id", "attempt", "number", "verdict", "supersedes"):
            if index.get(field) != parsed.get(field):
                raise StateError(f"gate entry field mismatch: {field}")
        current_blocks = [row for row in blocks if row.get("attempt") == current_attempt]
        if entries and (not current_blocks or current_blocks[0]["id"] != index["id"]):
            raise StateError("Markdown contains a newer unindexed verdict")
        applies_to_current_revision = entry_revision_set == current_revision_set
        return {
            "kind": "indexed",
            "hasGate": True,
            "entryId": index["id"],
            "gateResolution": index["verdict"] if applies_to_current_revision else None,
            "appliesToCurrentRevision": applies_to_current_revision,
            "entryRevisionSet": entry_revision_set,
            "currentRevisionSet": current_revision_set,
            "needsManualGateReview": False,
            "reason": None,
        }
    except (KeyError, TypeError, ValueError, json.JSONDecodeError, StateError) as exc:
        return {
            "kind": "mismatch",
            "hasGate": True,
            "entryId": None,
            "gateResolution": None,
            "appliesToCurrentRevision": None,
            "needsManualGateReview": True,
            "reason": str(exc),
        }


def _binding_id(binding: dict[str, Any]) -> str:
    revision = binding["revision"]
    blob = binding["blob"]
    attempt = binding.get("attempt")
    return f"{attempt}:{revision}@{blob}" if attempt else f"{revision}@{blob}"


def _git_root(path: Path) -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=path,
        text=True,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.returncode != 0:
        raise StateError(f"package is not inside a Git worktree: {path}")
    return Path(result.stdout.strip()).resolve()


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise StateError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.strip()


def _git_text(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args], cwd=repo, text=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
    if result.returncode != 0:
        raise StateError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.replace("\r\n", "\n").replace("\r", "\n")


def _package_artifact(package: Path, artifact: str, *, must_exist: bool = True) -> Path:
    if Path(artifact).is_absolute():
        raise StateError(f"artifact path must be package-relative: {artifact}")
    candidate = (package / artifact).resolve()
    try:
        candidate.relative_to(package.resolve())
    except ValueError as exc:
        raise StateError(f"artifact path escapes package: {artifact}") from exc
    if must_exist and not candidate.is_file():
        raise StateError(f"artifact does not exist: {candidate}")
    return candidate


def _lexical_package_artifact(package: Path, artifact: str) -> Path:
    relative = Path(artifact)
    if relative.is_absolute() or ".." in relative.parts:
        raise StateError(f"artifact path must stay package-relative: {artifact}")
    return package.resolve().joinpath(relative)


def _committed_artifact(package: Path, artifact: str) -> tuple[Path, Path, str]:
    repo = _git_root(package)
    path = _lexical_package_artifact(package, artifact)
    try:
        relative = path.relative_to(repo).as_posix()
    except ValueError as exc:
        raise StateError(f"artifact path escapes repository: {artifact}") from exc
    entry = _git(repo, "ls-tree", "HEAD", "--", relative)
    if not entry or not entry.split(maxsplit=1)[0].startswith("100"):
        raise StateError(f"committed artifact is missing or not a regular file: {artifact}")
    return repo, path, relative


def _worktree_blob(package: Path, artifact: str) -> str:
    repo = _git_root(package)
    path = _package_artifact(package, artifact)
    relative = path.relative_to(repo).as_posix()
    return _git(repo, "hash-object", "-w", f"--path={relative}", "--", str(path))


def _committed_blob(package: Path, artifact: str) -> str:
    repo, _, relative = _committed_artifact(package, artifact)
    return _git(repo, "rev-parse", f"HEAD:{relative}")


def _git_blob_text(package: Path, blob: str) -> str:
    repo = _git_root(package)
    return _git_text(repo, "cat-file", "blob", blob)


def _artifact_text(package: Path, artifact: str, committed: bool) -> str:
    if not committed:
        path = _package_artifact(package, artifact)
        return path.read_text(encoding="utf-8").replace("\r\n", "\n").replace("\r", "\n")
    repo, _, relative = _committed_artifact(package, artifact)
    return _git_text(repo, "show", f"HEAD:{relative}")


def _artifact_exists(package: Path, artifact: str, committed: bool) -> bool:
    if not committed:
        lexical = _lexical_package_artifact(package, artifact)
        if not lexical.exists() and not lexical.is_symlink():
            return False
        return _package_artifact(package, artifact).is_file()
    repo = _git_root(package)
    path = _lexical_package_artifact(package, artifact)
    try:
        relative = path.relative_to(repo).as_posix()
    except ValueError as exc:
        raise StateError(f"artifact path escapes repository: {artifact}") from exc
    entry = _git(repo, "ls-tree", "HEAD", "--", relative)
    if not entry:
        return False
    if not entry.split(maxsplit=1)[0].startswith("100"):
        raise StateError(f"committed artifact is not a regular file: {artifact}")
    return True


def _state_document(package: Path, artifact: str, committed: bool) -> str:
    """Read a package-local document from the selected validation context."""
    return _artifact_text(package, artifact, committed)


def _runtime_projection_body(records: list[dict[str, Any]]) -> str:
    runtime_task = CONFIG["projections"]["runtimeTask"]
    rows = list(runtime_task["header"])
    rows.extend(runtime_task["row"].format(**row) for row in records)
    return "\n".join(rows)


def _validate_record_set(
    records: Any, *, kind: str, attempt: str, expected_ids: list[str], allowed_states: set[str]
) -> list[dict[str, Any]]:
    if not isinstance(records, list):
        raise StateError(f"runtime {kind} records must be an array")
    current = [row for row in records if isinstance(row, dict) and row.get("attempt") == attempt]
    identities = [(row.get("attempt"), row.get("id")) for row in records if isinstance(row, dict)]
    if len(identities) != len(set(identities)) or len(identities) != len(records):
        raise StateError(f"runtime {kind} records are not unique by attempt and id")
    for row in records:
        if not isinstance(row, dict) or set(row) != {"attempt", "id", "state", "evidence"}:
            raise StateError(f"runtime {kind} record has invalid shape")
        if not all(isinstance(row[field], str) and row[field] for field in ("attempt", "id", "state", "evidence")):
            raise StateError(f"runtime {kind} record has empty fields")
        if row["state"] not in allowed_states:
            raise StateError(f"unsupported {kind} state: {row['state']}")
    actual_ids = [row["id"] for row in current]
    if sorted(actual_ids) != sorted(expected_ids):
        raise StateError(f"runtime {kind} records do not match earned artifacts")
    return current


def _validate_artifact_chain(records: Any) -> None:
    if not isinstance(records, list):
        raise StateError("runtime artifact records must be an array")
    known: set[str] = set()
    active: set[str] = set()
    record_types: dict[str, str] = {}
    sha256 = re.compile(r"[0-9a-f]{64}")
    for row in records:
        if not isinstance(row, dict) or set(row) != {
            "recordType", "id", "kind", "path", "hash", "supersedes", "tombstones", "evidence"
        }:
            raise StateError("artifact record has invalid shape")
        identifier = row.get("id")
        if not isinstance(identifier, str) or not identifier or identifier in known:
            raise StateError("artifact record ID is empty or duplicated")
        if not isinstance(row.get("evidence"), str) or not row["evidence"]:
            raise StateError(f"artifact evidence is missing: {identifier}")
        if row.get("recordType") == "artifact":
            digest = row.get("hash")
            if not isinstance(row.get("kind"), str) or not row["kind"] or not isinstance(row.get("path"), str) or not row["path"]:
                raise StateError(f"artifact metadata is invalid: {identifier}")
            _reject_investigation_artifact(row["path"], row["kind"])
            if not isinstance(digest, dict) or digest.get("algorithm") != "sha256" or not sha256.fullmatch(str(digest.get("value", ""))):
                raise StateError(f"artifact hash is invalid: {identifier}")
            if row.get("tombstones") is not None or not isinstance(row.get("supersedes"), list):
                raise StateError(f"artifact discriminator fields are invalid: {identifier}")
            pointers = row["supersedes"]
        elif row.get("recordType") == "tombstone":
            if any(row.get(field) is not None for field in ("kind", "path", "hash")) or row.get("supersedes") != []:
                raise StateError(f"tombstone discriminator fields are invalid: {identifier}")
            pointers = [row.get("tombstones")]
        else:
            raise StateError(f"unsupported artifact recordType: {row.get('recordType')!r}")
        if len(pointers) != len(set(pointers)) or any(not isinstance(pointer, str) or pointer not in active for pointer in pointers):
            raise StateError(f"artifact pointer is not an active backward reference: {identifier}")
        if row.get("recordType") == "artifact" and any(record_types.get(pointer) != "artifact" for pointer in pointers):
            raise StateError(f"artifact supersedes a non-artifact record: {identifier}")
        active.difference_update(pointers)
        known.add(identifier)
        active.add(identifier)
        record_types[identifier] = row["recordType"]


def _validate_gate_index(state: dict[str, Any], gate_text: str | None) -> None:
    gate = state.get("gate")
    if not isinstance(gate, dict) or set(gate) != {"allocations", "entries"}:
        raise StateError("runtime gate state has invalid shape")
    allocations = gate["allocations"]
    entries = gate["entries"]
    if not isinstance(allocations, list) or not isinstance(entries, list):
        raise StateError("runtime gate collections must be arrays")
    operation_ids: set[str] = set()
    entry_ids: set[str] = set()
    attempt_numbers: set[tuple[str, int]] = set()
    allocation_by_id: dict[str, dict[str, Any]] = {}
    for row in allocations:
        if not isinstance(row, dict) or set(row) != {"operationId", "attempt", "number", "entryId"}:
            raise StateError("gate allocation has invalid shape")
        expected_id = f"{row.get('attempt')}-G{row.get('number')}"
        if (
            not isinstance(row.get("operationId"), str)
            or not row["operationId"]
            or not isinstance(row.get("attempt"), str)
            or not row["attempt"]
            or not isinstance(row.get("number"), int)
            or isinstance(row.get("number"), bool)
            or row["number"] < 1
            or row.get("entryId") != expected_id
            or row["operationId"] in operation_ids
            or row["entryId"] in entry_ids
            or (row["attempt"], row["number"]) in attempt_numbers
        ):
            raise StateError("gate allocation identity is invalid or duplicated")
        operation_ids.add(row["operationId"])
        entry_ids.add(row["entryId"])
        attempt_numbers.add((row["attempt"], row["number"]))
        allocation_by_id[row["entryId"]] = row
    blocks = _gate_blocks(gate_text) if gate_text is not None else []
    finalized: set[str] = set()
    latest_by_attempt: dict[str, str] = {}
    for row in entries:
        if not isinstance(row, dict) or set(row) != {"id", "attempt", "number", "verdict", "supersedes", "entry"}:
            raise StateError("gate entry has invalid shape")
        allocation = allocation_by_id.get(row.get("id"))
        if allocation is None or any(row.get(field) != allocation.get(source) for field, source in (("attempt", "attempt"), ("number", "number"), ("id", "entryId"))):
            raise StateError("finalized gate entry has no matching allocation")
        if row["id"] in finalized or row.get("verdict") not in GATE_VERDICTS:
            raise StateError("finalized gate entry identity or verdict is invalid")
        if row.get("supersedes") != latest_by_attempt.get(row["attempt"]):
            raise StateError("finalized gate supersedes chain is invalid")
        pointer = row.get("entry")
        matches = [block for block in blocks if block["id"] == row["id"]]
        if (
            not isinstance(pointer, dict)
            or set(pointer) != {"path", "anchor", "bindingMode", "contentSha256"}
            or pointer.get("path") != "gate.md"
            or pointer.get("anchor") != row["id"]
            or pointer.get("bindingMode") != "gate-entry-v1"
            or len(matches) != 1
            or matches[0].get("revisionSet") is None
            or pointer.get("contentSha256") != gate_block_hash(matches[0]["block"])
            or any(row.get(field) != matches[0].get(field) for field in ("id", "attempt", "number", "verdict", "supersedes"))
        ):
            raise StateError("finalized gate entry content binding mismatch")
        finalized.add(row["id"])
        latest_by_attempt[row["attempt"]] = row["id"]


def _validate_runtime_state(package: Path, revision_state: dict[str, Any], committed: bool) -> None:
    runtime_text = _state_document(package, RUNTIME_STATE.as_posix(), committed)
    try:
        state = json.loads(runtime_text)
    except json.JSONDecodeError as exc:
        raise StateError("runtime state is not valid JSON") from exc
    _require_current_contract(state, "runtime state")
    required = {"contractVersion", "purpose", "ownerFacing", "packageId", "tasks", "tickets", "artifacts", "gate"}
    if set(state) != required or state.get("purpose") != "internal-machine-sidecar" or state.get("ownerFacing") is not False:
        raise StateError("runtime state has invalid top-level shape")
    if not isinstance(state.get("packageId"), str) or not state["packageId"]:
        raise StateError("runtime packageId is missing")
    attempt_selection = revision_state.get("current", {}).get("attempt")
    if not attempt_selection:
        expected_tasks: list[str] = []
        expected_tickets: list[str] = []
        attempt = ""
        tickets_earned = dag_earned = False
    else:
        attempt = attempt_selection["id"]
        plan_text = _state_document(package, attempt_selection["plan"], committed)
        tickets_earned, dag_earned = _composition(plan_text)
        if dag_earned:
            dag_relative = _attempt_dag_artifact(package, attempt, committed)
            if dag_relative:
                dag_text = _state_document(package, dag_relative, committed)
                expected_tasks, _ = _dag_task_ids(dag_text)
                if not expected_tasks:
                    raise StateError("earned DAG contains no task records")
            else:
                dag_text = None
                expected_tasks = []
        else:
            dag_text = None
            expected_tasks = []
        ticket_documents: dict[str, str] = {}
        if tickets_earned:
            ticket_documents = {identifier: text for identifier, (_, text) in _attempt_ticket_documents(package, attempt, committed).items()}
        expected_tickets = list(ticket_documents)
    tasks = _validate_record_set(state["tasks"], kind="task", attempt=attempt, expected_ids=expected_tasks, allowed_states=TASK_READ_STATES)
    tickets = _validate_record_set(state["tickets"], kind="ticket", attempt=attempt, expected_ids=expected_tickets, allowed_states=TICKET_STATES)
    runtime_marker = CONFIG["projections"]["markers"]["runtimeState"]
    if tasks and dag_text is not None and _replace_projection(dag_text, runtime_marker, _runtime_projection_body(tasks)) != dag_text:
        raise StateError("runtime projection mismatch in DAG")
    if tickets_earned:
        for row in tickets:
            expected = CONFIG["projections"]["runtimeTicket"].format(**row)
            if _replace_projection(ticket_documents[row["id"]], runtime_marker, expected) != ticket_documents[row["id"]]:
                raise StateError(f"runtime projection mismatch in ticket {row['id']}")
    _validate_artifact_chain(state["artifacts"])
    gate_text = None
    if _artifact_exists(package, "gate.md", committed):
        gate_text = _state_document(package, "gate.md", committed)
    _validate_gate_index(state, gate_text)
    if gate_text is not None:
        current_entries = [row for row in state["gate"]["entries"] if row.get("attempt") == attempt]
        if current_entries:
            latest = max(current_entries, key=lambda row: row["number"])
            gate_status = CONFIG["projections"]["gateStatus"]["finalized"].format(id=latest["id"], verdict=latest["verdict"])
        else:
            gate_status = CONFIG["projections"]["gateStatus"]["empty"]
        if _replace_projection(gate_text, CONFIG["projections"]["markers"]["gateStatus"], gate_status) != gate_text:
            raise StateError("gate status projection mismatch")


PLAN_ER_PATTERN = re.compile(r"(?ms)^## (?:执行记录|Execution Record)[ \t]*\n.*?(?=^## [^#]|\Z)")


def _execution_record(text: str) -> str:
    matches = PLAN_ER_PATTERN.findall(text)
    if len(matches) != 1:
        raise StateError("plan has no unique Execution Record section")
    return matches[0]


def _plan_contract(text: str) -> str:
    replaced, count = PLAN_ER_PATTERN.subn("## Execution Record\n<impl-package-er-marker>\n", text, count=1)
    if count != 1:
        raise StateError("plan has no unique Execution Record section")
    return replaced


def _validate_er_history(
    package: Path, artifact: str, baseline_blob: str, candidate_text: str, committed: bool
) -> None:
    repo = _git_root(package)
    path = _lexical_package_artifact(package, artifact) if committed else _package_artifact(package, artifact)
    relative = path.relative_to(repo).as_posix()
    commits = _git(repo, "log", "--format=%H", "--reverse", "--", relative).splitlines()
    baseline_index: int | None = None
    for index, commit in enumerate(commits):
        blob = _git(repo, "rev-parse", f"{commit}:{relative}")
        if blob == baseline_blob:
            baseline_index = index
            break
    if baseline_index is None:
        if committed:
            raise StateError(f"plan baseline blob is not reachable from history: {baseline_blob}")
        return
    previous = _git_blob_text(package, baseline_blob)
    for commit in commits[baseline_index + 1 :]:
        current = _git_text(repo, "show", f"{commit}:{relative}")
        if not _execution_record(current).startswith(_execution_record(previous)):
            raise StateError("Execution Record append-only violation in Git history")
        previous = current
    if not committed and not _execution_record(candidate_text).startswith(_execution_record(previous)):
        raise StateError("Execution Record append-only violation in working tree")


def _load_revision_state(package: Path) -> tuple[Path, dict[str, Any]]:
    path = package / REVISION_BINDINGS
    if not path.is_file():
        raise StateError(f"revision sidecar does not exist: {path}")
    state = json.loads(path.read_text(encoding="utf-8"))
    _require_current_contract(state, "revision bindings")
    return path, state


def _revision_state_for_context(package: Path, committed: bool) -> dict[str, Any]:
    if not committed:
        return _load_revision_state(package)[1]
    try:
        state = json.loads(_artifact_text(package, REVISION_BINDINGS.as_posix(), True))
    except json.JSONDecodeError as exc:
        raise StateError("committed revision sidecar is not valid JSON") from exc
    _require_current_contract(state, "revision bindings")
    return state


def _active_binding(state: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    superseded = {row.get("supersedes") for row in state.get("bindings", []) if row.get("supersedes")}
    matches = []
    for row in state.get("bindings", []):
        if row.get("id") in superseded:
            continue
        if row.get("artifact") != (current.get("artifact") or current.get("plan")):
            continue
        if row.get("revision") != current.get("revision"):
            continue
        if current.get("id") is not None and row.get("attempt") != current.get("id"):
            continue
        matches.append(row)
    if len(matches) != 1:
        raise StateError(f"current revision resolves to {len(matches)} active bindings")
    return matches[0]


def _registration_binding(
    package: Path,
    state: dict[str, Any],
    kind: str,
    alias: str,
    artifact: str | None,
    attempt: str | None,
    evidence: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    expected_prefix = {"decision": "D", "spec": "S", "plan": "P"}[kind]
    if re.fullmatch(rf"{expected_prefix}[1-9]\d*", alias) is None:
        raise StateError(f"invalid {kind} revision alias: {alias}")
    current = state.setdefault("current", {})
    current_key = kind if kind != "plan" else "attempt"
    if artifact is None:
        existing = current.get(current_key, {})
        artifact = existing.get("artifact") or existing.get("plan")
    if not artifact:
        raise StateError(f"--artifact is required when no current {kind} artifact exists")
    _reject_investigation_artifact(artifact, "revision-binding")
    if artifact == "design.md":
        raise StateError("legacy design.md artifact is not supported; use decision.md")
    if kind == "decision" and artifact not in {"decision.md", "spec.md"}:
        raise StateError("decision revision artifact must be decision.md or lightweight spec.md")
    if not isinstance(evidence, str) or not evidence:
        raise StateError(f"{kind} revision evidence is required")
    if kind == "plan" and (not isinstance(attempt, str) or not attempt):
        raise StateError("--attempt is required for plan registration")
    blob = _worktree_blob(package, artifact)
    binding: dict[str, Any] = {
        "artifact": artifact,
        "revision": alias,
        "mode": "plan-contract-v1" if kind == "plan" else "exact-blob",
        "blob": blob,
        "supersedes": None,
        "evidence": evidence,
    }
    if kind == "plan":
        binding["attempt"] = attempt
    binding["id"] = _binding_id(binding)
    return binding, ({"id": attempt, "plan": artifact, "revision": alias} if kind == "plan" else {"artifact": artifact, "revision": alias})


def command_register_revisions(
    package: Path,
    registrations: list[dict[str, Any]],
) -> dict[str, Any]:
    if not registrations:
        raise StateError("at least one revision registration is required")
    path, state = _load_revision_state(package)
    candidate = json.loads(json.dumps(state))
    current = candidate.setdefault("current", {})
    seen_kinds: set[str] = set()
    for registration in registrations:
        kind = registration.get("kind")
        if kind not in {"decision", "spec", "plan"}:
            raise StateError(f"unsupported revision kind: {kind!r}")
        if kind in seen_kinds:
            raise StateError(f"duplicate registration kind: {kind}")
        seen_kinds.add(kind)
        binding, selection = _registration_binding(
            package,
            candidate,
            kind,
            registration.get("alias", ""),
            registration.get("artifact"),
            registration.get("attempt"),
            registration.get("evidence", ""),
        )
        existing = next((row for row in candidate.get("bindings", []) if row.get("id") == binding["id"]), None)
        if existing is not None and existing != binding:
            raise StateError(f"binding ID collision: {binding['id']}")
        if existing is None:
            same_semantic = [
                row for row in candidate.get("bindings", [])
                if row.get("artifact") == binding["artifact"]
                and row.get("revision") == binding["revision"]
                and row.get("attempt") == binding.get("attempt")
                and row.get("id") not in {row.get("supersedes") for row in candidate.get("bindings", []) if row.get("supersedes")}
            ]
            if same_semantic and any(row.get("blob") != binding["blob"] for row in same_semantic):
                raise StateError(f"revision {binding['revision']} already exists with a different blob; use rebind for editorial changes")
            candidate.setdefault("bindings", []).append(binding)
        if kind == "plan":
            current["attempt"] = selection
        else:
            current[kind] = selection
    runtime_path, runtime_state = _load_runtime_state(package)
    _seed_earned_records(package, runtime_state, candidate)
    _validate_revision_bindings(package, candidate, committed=False)
    _atomic_write_json(path, candidate)
    _atomic_write_json(runtime_path, runtime_state)
    command_refresh_projections(package)
    command_validate(package, committed=False)
    return candidate


def command_register_revision(
    package: Path,
    kind: str,
    alias: str,
    artifact: str | None,
    attempt: str | None,
    evidence: str,
) -> dict[str, Any]:
    return command_register_revisions(
        package,
        [{"kind": kind, "alias": alias, "artifact": artifact, "attempt": attempt, "evidence": evidence}],
    )


def _validate_revision_bindings(package: Path, state: dict[str, Any], committed: bool) -> list[str]:
    _require_current_contract(state, "revision bindings")
    if set(state) != {"contractVersion", "purpose", "ownerFacing", "current", "bindings"}:
        raise StateError("revision sidecar has invalid top-level shape")
    if state.get("purpose") != "internal-machine-sidecar" or state.get("ownerFacing") is not False:
        raise StateError("revision sidecar discriminator is invalid")
    bindings = state.get("bindings")
    if not isinstance(bindings, list) or any(not isinstance(row, dict) for row in bindings):
        raise StateError("revision bindings must be an array of objects")
    repo = _git_root(package)
    known: dict[str, dict[str, Any]] = {}
    superseded: set[str] = set()
    semantic_terminals: dict[tuple[Any, ...], int] = {}
    for row in bindings:
        mode = row.get("mode")
        if mode not in ("exact-blob", "plan-contract-v1"):
            raise StateError(f"unsupported binding mode: {mode!r}")
        alias_pattern = r"[DS][1-9]\d*" if mode == "exact-blob" else r"P[1-9]\d*"
        if not isinstance(row.get("revision"), str) or re.fullmatch(alias_pattern, row["revision"]) is None:
            raise StateError(f"revision alias does not match binding mode: {row.get('revision')!r}")
        required = {"artifact", "revision", "mode", "blob", "id", "supersedes", "evidence"}
        if mode == "plan-contract-v1":
            required.add("attempt")
        if set(row) != required:
            raise StateError("revision binding has invalid canonical shape")
        _reject_investigation_artifact(row["artifact"], "revision-binding")
        if row["artifact"] == "design.md":
            raise StateError("legacy design.md artifact is not supported; use decision.md")
        if row["revision"].startswith("D") and row["artifact"] not in {"decision.md", "spec.md"}:
            raise StateError("decision revision binding artifact must be decision.md or lightweight spec.md")
        if not all(isinstance(row.get(field), str) and row[field] for field in ("artifact", "revision", "blob")):
            raise StateError("revision binding has empty identity fields")
        if not re.fullmatch(r"[0-9a-f]{40,64}", row["blob"]):
            raise StateError("revision binding blob OID is invalid")
        if subprocess.run(["git", "cat-file", "-e", f"{row['blob']}^{{blob}}"], cwd=repo, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode != 0:
            raise StateError(f"revision binding blob is missing: {row['blob']}")
        semantic = (row.get("attempt"), row["revision"], row["artifact"])
        semantic_terminals[semantic] = semantic_terminals.get(semantic, 0) + 1
        if row["id"] != _binding_id(row) or not isinstance(row.get("evidence"), str) or not row["evidence"]:
            raise StateError("revision binding ID or evidence is invalid")
        if row["id"] in known:
            raise StateError(f"duplicate binding identity: {row['id']}")
        pointer = row.get("supersedes")
        if pointer is not None:
            target = known.get(pointer)
            if target is None or (target.get("attempt"), target["revision"], target["artifact"]) != semantic or pointer in superseded:
                raise StateError("revision supersedes is not an active backward reference for the same revision")
            superseded.add(pointer)
            semantic_terminals[semantic] -= 1
        known[row["id"]] = row
    if any(count != 1 for count in semantic_terminals.values()):
        raise StateError("revision identity does not have exactly one terminal binding")
    current = state.get("current", {})
    _assert_revision_selection_keys(current)
    selection_shapes = {
        "decision": {"artifact", "revision"},
        "spec": {"artifact", "revision"},
        "attempt": {"id", "plan", "revision"},
    }
    for key, expected_shape in selection_shapes.items():
        selection = current.get(key)
        if selection is not None and (not isinstance(selection, dict) or set(selection) != expected_shape):
            raise StateError(f"current {key} selection has invalid canonical shape")
    checked: list[str] = []
    for key in ("decision", "spec", "attempt"):
        selection = current.get(key)
        if not selection:
            continue
        binding = _active_binding(state, selection)
        expected_prefix = {"decision": "D", "spec": "S", "attempt": "P"}[key]
        expected_mode = "plan-contract-v1" if key == "attempt" else "exact-blob"
        if not re.fullmatch(rf"{expected_prefix}[1-9]\d*", str(selection.get("revision", ""))) or binding.get("mode") != expected_mode:
            raise StateError(f"current {key} selection has invalid revision identity")
        artifact = binding["artifact"]
        actual = _committed_blob(package, artifact) if committed else _worktree_blob(package, artifact)
        mode = binding.get("mode")
        if mode == "exact-blob" and actual != binding.get("blob"):
            raise StateError(f"binding mismatch for {binding['revision']}: {binding.get('blob')} != {actual}")
        if mode == "plan-contract-v1":
            if actual != binding.get("blob"):
                baseline_text = _git_blob_text(package, binding["blob"])
                candidate_text = _artifact_text(package, artifact, committed)
                _validate_er_history(package, artifact, binding["blob"], candidate_text, committed)
                baseline = _plan_contract(baseline_text)
                candidate = _plan_contract(candidate_text)
                if baseline != candidate:
                    raise StateError(f"plan contract mismatch for {binding['revision']}")
        if mode not in ("exact-blob", "plan-contract-v1"):
            raise StateError(f"unsupported binding mode: {binding.get('mode')!r}")
        checked.append(binding["revision"])
    return checked


def command_validate(package: Path, committed: bool) -> dict[str, Any]:
    state = _revision_state_for_context(package, committed)
    checked = _validate_revision_bindings(package, state, committed)
    _validate_revision_projections(package, state, committed)
    if not _artifact_exists(package, RUNTIME_STATE.as_posix(), committed):
        raise StateError("runtime state is missing (contract upgrade required)")
    _validate_runtime_state(package, state, committed)
    return {
        "ok": True,
        "context": "committed" if committed else "working-tree",
        "contractVersion": CURRENT_CONTRACT_VERSION,
        "checked": checked,
    }


CONTRACT_STATUS_EXIT_CODES = {
    "current": 0,
    "invalid": 2,
    "upgradeRequired": 3,
    "unsupportedFuture": 4,
}


def _contract_component_status(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"status": "upgradeRequired", "contractVersion": None, "reason": "missing"}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {"status": "invalid", "contractVersion": None, "reason": "invalid-json"}
    if not isinstance(value, dict):
        return {"status": "invalid", "contractVersion": None, "reason": "top-level-not-object"}
    if "contractVersion" not in value:
        # Pre-3.2 sidecars are not parsed; callers must migrate them to the current schema.
        return {
            "status": "upgradeRequired",
            "contractVersion": None,
            "reason": "missing-contractVersion",
        }
    status = _contract_status_for_version(value.get("contractVersion"))
    if status != "current":
        return {
            "status": status,
            "contractVersion": value.get("contractVersion"),
            "reason": "contract-version",
        }
    if "schemaVersion" in value:
        return {
            "status": "invalid",
            "contractVersion": value.get("contractVersion"),
            "reason": "legacy-schemaVersion",
        }
    if path.name == REVISION_BINDINGS.name and isinstance(value.get("current"), dict):
        current = value["current"]
        if "design" in current:
            return {
                "status": "invalid",
                "contractVersion": value.get("contractVersion"),
                "reason": "legacy-design-selection",
            }
        decision = current.get("decision")
        if isinstance(decision, dict) and decision.get("artifact") == "design.md":
            return {
                "status": "invalid",
                "contractVersion": value.get("contractVersion"),
                "reason": "legacy-design-artifact",
            }
    if path.name == REVISION_BINDINGS.name and isinstance(value.get("bindings"), list):
        for binding in value["bindings"]:
            if isinstance(binding, dict) and (
                binding.get("artifact") == "design.md"
                or (str(binding.get("revision", "")).startswith("D") and binding.get("artifact") not in {"decision.md", "spec.md"})
            ):
                return {
                    "status": "invalid",
                    "contractVersion": value.get("contractVersion"),
                    "reason": "legacy-design-artifact",
                }
    return {
        "status": status,
        "contractVersion": value.get("contractVersion"),
        "reason": None if status == "current" else "contract-version",
    }


def command_contract_status(package: Path) -> dict[str, Any]:
    if not package.is_dir():
        return {
            "ok": False,
            "status": "invalid",
            "contractVersion": CURRENT_CONTRACT_VERSION,
            "currentContractVersion": CURRENT_CONTRACT_VERSION,
            "components": {},
            "reason": "package-directory-missing",
        }
    components = {
        "revisionBindings": _contract_component_status(package / REVISION_BINDINGS),
        "runtimeState": _contract_component_status(package / RUNTIME_STATE),
    }
    statuses = [component["status"] for component in components.values()]
    if "unsupportedFuture" in statuses:
        status = "unsupportedFuture"
        reason = "component-uses-future-contract"
    elif "invalid" in statuses:
        status = "invalid"
        reason = "component-contract-is-invalid"
    elif "upgradeRequired" in statuses:
        status = "upgradeRequired"
        reason = "component-requires-upgrade"
    else:
        status = "current"
        reason = None
    return {
        "ok": status == "current",
        "status": status,
        "contractVersion": CURRENT_CONTRACT_VERSION,
        "currentContractVersion": CURRENT_CONTRACT_VERSION,
        "components": components,
        "reason": reason,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Maintain Impl-Package structured state")
    parser.add_argument("--package", required=True, type=Path)
    subparsers = parser.add_subparsers(dest="command", required=True)
    init_parser = subparsers.add_parser("init")
    init_parser.add_argument("--package-id", required=True)
    subparsers.add_parser("contract-status")
    register_parser = subparsers.add_parser("register-revision")
    register_parser.add_argument("kind", choices=("decision", "spec", "plan"))
    register_parser.add_argument("alias")
    register_parser.add_argument("--artifact")
    register_parser.add_argument("--attempt")
    register_parser.add_argument("--evidence", required=True)
    batch_register_parser = subparsers.add_parser("register-revisions")
    for kind in ("decision", "spec", "plan"):
        batch_register_parser.add_argument(f"--{kind}", dest=f"{kind}_alias")
        batch_register_parser.add_argument(f"--{kind}-artifact", dest=f"{kind}_artifact")
        batch_register_parser.add_argument(f"--{kind}-evidence", dest=f"{kind}_evidence")
    batch_register_parser.add_argument("--attempt")
    validate_parser = subparsers.add_parser("validate")
    validate_mode = validate_parser.add_mutually_exclusive_group(required=True)
    validate_mode.add_argument("--working-tree", action="store_true")
    validate_mode.add_argument("--committed", action="store_true")
    state_parser = subparsers.add_parser("set-state")
    state_parser.add_argument("kind", choices=("task", "ticket"))
    state_parser.add_argument("identifier")
    state_parser.add_argument("state")
    state_parser.add_argument("--attempt", required=True)
    state_parser.add_argument("--expect", required=True)
    state_parser.add_argument("--evidence", required=True)
    artifact_parser = subparsers.add_parser("record-artifact")
    artifact_parser.add_argument("identifier")
    artifact_parser.add_argument("path")
    artifact_parser.add_argument("--kind", required=True)
    artifact_parser.add_argument("--evidence", required=True)
    supersede_parser = subparsers.add_parser("supersede-artifact")
    supersede_parser.add_argument("old_identifier")
    supersede_parser.add_argument("new_identifier")
    supersede_parser.add_argument("path")
    supersede_parser.add_argument("--kind", required=True)
    supersede_parser.add_argument("--evidence", required=True)
    tombstone_parser = subparsers.add_parser("tombstone-artifact")
    tombstone_parser.add_argument("identifier")
    tombstone_parser.add_argument("--target", required=True)
    tombstone_parser.add_argument("--evidence", required=True)
    new_gate_parser = subparsers.add_parser("new-gate-entry")
    new_gate_parser.add_argument("--attempt", required=True)
    new_gate_parser.add_argument("--operation-id", required=True)
    finalize_parser = subparsers.add_parser("finalize-gate-entry")
    finalize_parser.add_argument("entry_id")
    subparsers.add_parser("resolve-gate")
    rebind_parser = subparsers.add_parser("rebind")
    rebind_parser.add_argument("alias")
    rebind_parser.add_argument("--reason", choices=("projection", "editorial"), required=True)
    rebind_parser.add_argument("--evidence", required=True)
    rebind_parser.add_argument("--confirm-contract-impact-none", action="store_true")
    subparsers.add_parser("refresh-projections")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        package = args.package.resolve()
        if args.command == "init":
            result = command_init(package, args.package_id)
        elif args.command == "contract-status":
            result = command_contract_status(package)
        elif args.command == "register-revision":
            result = command_register_revision(
                package, args.kind, args.alias, args.artifact, args.attempt, args.evidence
            )
        elif args.command == "register-revisions":
            registrations = []
            for kind in ("decision", "spec", "plan"):
                alias = getattr(args, f"{kind}_alias")
                if alias is None:
                    if any(getattr(args, f"{kind}_{suffix}") is not None for suffix in ("artifact", "evidence")):
                        raise StateError(f"--{kind}-artifact/--{kind}-evidence require --{kind}")
                    continue
                evidence = getattr(args, f"{kind}_evidence")
                if not evidence:
                    raise StateError(f"--{kind}-evidence is required with --{kind}")
                registrations.append(
                    {
                        "kind": kind,
                        "alias": alias,
                        "artifact": getattr(args, f"{kind}_artifact"),
                        "attempt": args.attempt if kind == "plan" else None,
                        "evidence": evidence,
                    }
                )
            if args.attempt and not args.plan_alias:
                raise StateError("--attempt requires --plan")
            result = command_register_revisions(package, registrations)
        elif args.command == "validate":
            result = command_validate(package, committed=args.committed)
        elif args.command == "set-state":
            result = command_set_state(
                package,
                args.kind,
                args.identifier,
                args.state,
                args.attempt,
                args.expect,
                args.evidence,
            )
        elif args.command == "record-artifact":
            result = command_record_artifact(
                package, args.identifier, args.path, args.kind, args.evidence
            )
        elif args.command == "supersede-artifact":
            result = command_record_artifact(
                package,
                args.new_identifier,
                args.path,
                args.kind,
                args.evidence,
                supersedes=[args.old_identifier],
            )
        elif args.command == "tombstone-artifact":
            result = command_tombstone_artifact(
                package, args.identifier, args.target, args.evidence
            )
        elif args.command == "new-gate-entry":
            result = command_new_gate_entry(package, args.attempt, args.operation_id)
        elif args.command == "finalize-gate-entry":
            result = command_finalize_gate_entry(package, args.entry_id)
        elif args.command == "resolve-gate":
            result = resolve_gate(package)
        elif args.command == "rebind":
            result = command_rebind(
                package,
                args.alias,
                args.reason,
                args.evidence,
                args.confirm_contract_impact_none,
            )
        elif args.command == "refresh-projections":
            result = command_refresh_projections(package)
        else:
            raise StateError(f"unsupported command: {args.command}")
    except (OSError, json.JSONDecodeError, StateError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    if args.command == "contract-status":
        return CONTRACT_STATUS_EXIT_CODES[result["status"]]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
