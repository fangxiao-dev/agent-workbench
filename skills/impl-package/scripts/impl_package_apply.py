#!/usr/bin/env python3
"""Deterministic, planning-only Impl-Package apply helpers.

The publish-plan command owns only local Draft -> Approved ticket publication,
revision registration, projections, and structured-state validation.  It does
    not commit, push, call GitHub, or mutate application implementation/runtime data.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any


SCRIPT_PATH = Path(__file__).resolve()
SKILLS_ROOT = SCRIPT_PATH.parents[2]
STATE_SCRIPT = SCRIPT_PATH.with_name("impl_package_state.py")
REVIEW_LEDGER_SCRIPT = SKILLS_ROOT / "plan-review" / "scripts" / "review_ledger.py"
JOURNAL_RELATIVE = Path(".impl-package/publish-plan-transaction.json")


def _load_state_module() -> Any:
    spec = importlib.util.spec_from_file_location("impl_package_state_for_apply", STATE_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load state engine: {STATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


STATE = _load_state_module()


class ApplyError(RuntimeError):
    pass


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _read_json_object(path_value: str, label: str) -> dict[str, Any]:
    try:
        payload = sys.stdin.read() if path_value == "-" else Path(path_value).read_text(encoding="utf-8")
        value = json.loads(payload)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ApplyError(f"{label} is not readable JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ApplyError(f"{label} must be a JSON object")
    return value


def _statement_hash(source: dict[str, Any]) -> str | None:
    statement = source.get("statement")
    if isinstance(statement, str) and statement:
        return _sha256(statement.encode("utf-8"))
    value = source.get("statement_sha256")
    return value if isinstance(value, str) and value else None


def _normalized_owner_source(source: dict[str, Any], manifest_hash: str) -> dict[str, Any]:
    required = ("actor", "channel", "reference")
    if source.get("actor") != "owner":
        raise ApplyError("owner authorization actor must be owner")
    if any(not isinstance(source.get(field), str) or not source[field] for field in required):
        raise ApplyError("owner authorization requires channel and reference")
    if source.get("action") != "apply":
        raise ApplyError("owner authorization action must be apply")
    if source.get("manifest_hash") != manifest_hash:
        raise ApplyError("owner authorization does not bind the current review manifest")
    statement_hash = _statement_hash(source)
    if statement_hash is None:
        raise ApplyError("owner authorization requires statement or statement_sha256")
    return {
        "actor": "owner",
        "channel": source["channel"],
        "reference": source["reference"],
        "action": "apply",
        "manifest_hash": manifest_hash,
        "statement_sha256": statement_hash,
    }


def _verify_review_and_authorization(
    package: Path,
    ledger_path: Path,
    authorization_path: str,
    deadline: float,
) -> dict[str, Any]:
    if not ledger_path.is_file():
        raise ApplyError(f"review ledger does not exist: {ledger_path}")
    if not REVIEW_LEDGER_SCRIPT.is_file():
        raise ApplyError(f"review ledger verifier is unavailable: {REVIEW_LEDGER_SCRIPT}")
    remaining = max(0.1, deadline - time.monotonic())
    try:
        result = subprocess.run(
            [sys.executable, str(REVIEW_LEDGER_SCRIPT), "verify-clearance", "--ledger", str(ledger_path)],
            capture_output=True,
            text=True,
            check=False,
            timeout=remaining,
        )
    except subprocess.TimeoutExpired as exc:
        raise ApplyError("clearance verification exceeded the apply deadline") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout).strip().replace("\n", " ")
        raise ApplyError(f"review clearance verification failed: {detail or 'unknown blocker'}")
    try:
        clearance = json.loads(result.stdout)
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ApplyError(f"review clearance result is invalid: {exc}") from exc
    if not isinstance(clearance, dict) or not clearance.get("ok"):
        blockers = clearance.get("clearance_blockers", []) if isinstance(clearance, dict) else []
        raise ApplyError(f"review clearance has blockers: {', '.join(map(str, blockers)) or 'unknown blocker'}")
    manifest_hash = clearance.get("manifest_hash")
    authorization = ledger.get("authorization") if isinstance(ledger, dict) else None
    if not isinstance(manifest_hash, str) or not isinstance(authorization, dict):
        raise ApplyError("review ledger has no current owner authorization")
    stored_source = authorization.get("source")
    if authorization.get("manifest_hash") != manifest_hash or not isinstance(stored_source, dict):
        raise ApplyError("review ledger owner authorization is stale or malformed")
    supplied = _normalized_owner_source(_read_json_object(authorization_path, "owner authorization"), manifest_hash)
    stored = _normalized_owner_source(
        {
            **stored_source,
            "action": "apply",
            "manifest_hash": manifest_hash,
        },
        manifest_hash,
    )
    if supplied != stored:
        raise ApplyError("supplied owner authorization does not match the ledger authorization")
    _validate_fast_path_baseline(package, ledger)
    return {"manifest_hash": manifest_hash, "clearance": clearance}


def _validate_fast_path_baseline(package: Path, ledger: dict[str, Any]) -> None:
    package_root = package.resolve()
    baseline = ledger.get("baseline")
    if not isinstance(baseline, dict):
        raise ApplyError("review ledger baseline is missing")
    resources = list(baseline.get("targets", [])) + list(baseline.get("references", []))
    if not resources:
        raise ApplyError("review ledger baseline is empty")
    for resource in resources:
        path_value = resource.get("path") if isinstance(resource, dict) else None
        if not isinstance(path_value, str):
            raise ApplyError("review baseline contains an invalid path")
        path = Path(path_value).resolve()
        try:
            path.relative_to(package_root)
        except ValueError as exc:
            raise ApplyError(
                f"fast plan apply requires a package-local review baseline; outside path: {path}"
            ) from exc


def _section(text: str, names: tuple[str, ...]) -> str:
    headings = "|".join(re.escape(name) for name in names)
    match = re.search(rf"(?ms)^##\s+(?:{headings})\s*\r?\n(.*?)(?=^##\s|\Z)", text)
    if not match:
        raise ApplyError(f"document section is missing: {' / '.join(names)}")
    return match.group(1)


def _field(text: str, names: tuple[str, ...], value_pattern: str, label: str) -> str:
    labels = "|".join(re.escape(name) for name in names)
    patterns = (
        rf"(?m)^\s*\*\*(?:{labels})[：:]\*\*\s*({value_pattern})\s*$",
        rf"(?m)^\s*(?:{labels})\s*[：:]\s*({value_pattern})\s*$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    raise ApplyError(f"{label} is missing")


PUBLICATION_RE = re.compile(
    r"(?m)^\s*\*\*(?:发布状态（Publication Status）|Publication Status)[：:]\*\*\s*(Draft|Approved)(?=\r?$)"
)


def _publication_status_and_output(text: str) -> tuple[str, str]:
    matches = list(PUBLICATION_RE.finditer(text))
    if len(matches) != 1:
        raise ApplyError("ticket must contain exactly one Draft/Approved publication status")
    status = matches[0].group(1)
    if status == "Approved":
        return status, text
    start, end = matches[0].span(1)
    return status, text[:start] + "Approved" + text[end:]


def _acceptance_ids(text: str) -> list[str]:
    section = _section(text, ("验收标准", "Acceptance Criteria"))
    matches = list(re.finditer(r"(?im)^\s*[-*]\s*(?:\*\*)?(AC-\d+)\b", section))
    if not matches:
        matches = list(re.finditer(r"\b(AC-\d+)\b", section))
    ids = [match.group(1) for match in matches]
    if not ids or len(ids) != len(set(ids)):
        raise ApplyError("each ticket must contain unique acceptance criteria")
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(section)
        block = section[match.start() : end]
        if not re.search(r"证据|evidence|manual|人工", block, re.I):
            raise ApplyError(f"{match.group(1)} has no planned evidence or manual verifier")
    return ids


def _typed_edges(text: str, ticket_ids: set[str]) -> list[tuple[str, str, str]]:
    section = _section(text, ("阻塞依赖", "Blocking Dependencies"))
    edges: list[tuple[str, str, str]] = []
    for raw_line in section.splitlines():
        line = raw_line.strip()
        if (
            not line
            or line.lower() == "none"
            or line == "无"
            or "没有阻塞边" in line
            or "when there are no blocking" in line.lower()
        ):
            continue
        match = re.fullmatch(r"-\s*(implementation|acceptance|release)\s*:\s*([^\s]+)", line, re.I)
        if not match:
            raise ApplyError(f"invalid typed ticket dependency: {line}")
        kind, blocker = match.group(1).lower(), match.group(2)
        if blocker not in ticket_ids:
            raise ApplyError(f"ticket dependency references a missing same-attempt ticket: {blocker}")
        edges.append((blocker, "", kind))
    return edges


def _graph_for_ticket(ticket_id: str, edges: list[tuple[str, str, str]], ticket_ids: set[str]) -> list[tuple[str, str, str]]:
    return [(blocker, ticket_id, kind) for blocker, _, kind in edges]


def _validate_graph(ticket_ids: list[str], edges_by_ticket: dict[str, list[tuple[str, str, str]]]) -> None:
    all_edges: list[tuple[str, str, str]] = []
    order = {ticket_id: index for index, ticket_id in enumerate(ticket_ids)}
    for ticket_id, edges in edges_by_ticket.items():
        for blocker, _, kind in edges:
            if blocker == ticket_id:
                raise ApplyError(f"ticket dependency is self-referential: {ticket_id}")
            all_edges.append((blocker, ticket_id, kind))
            if order[blocker] >= order[ticket_id]:
                raise ApplyError("ticket files are not in deterministic dependency-compatible order")
    graph: dict[str, list[str]] = {ticket_id: [] for ticket_id in ticket_ids}
    for blocker, dependent, _ in all_edges:
        graph[blocker].append(dependent)
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ticket_id: str) -> None:
        if ticket_id in visiting:
            raise ApplyError("typed ticket dependency graph is cyclic")
        if ticket_id in visited:
            return
        visiting.add(ticket_id)
        for dependent in graph[ticket_id]:
            visit(dependent)
        visiting.remove(ticket_id)
        visited.add(ticket_id)

    for ticket_id in ticket_ids:
        visit(ticket_id)


def _validate_dag(package: Path, attempt: str, ticket_ids: list[str], earned: bool, expected: dict[str, str]) -> None:
    dag_relative = STATE._attempt_dag_artifact(package, attempt)
    if not earned:
        if dag_relative is not None:
            raise ApplyError("current Composition earns no DAG but a same-attempt DAG exists")
        return
    if dag_relative is None:
        raise ApplyError("current Composition earns a DAG but the same-attempt DAG is missing")
    dag_path = STATE._package_artifact(package, dag_relative)
    dag_text = dag_path.read_text(encoding="utf-8")
    task_ids, _ = STATE._dag_task_ids(dag_text)
    if not task_ids:
        raise ApplyError("earned DAG has no Task records")
    revision_match = re.search(
        r"(?m)^-\s*(?:修订集合（Revision set）|Revision set)[：:]\s*(D\d+|N/A)\s*/\s*(S\d+|N/A)\s*/\s*(P\d+|N/A)\s*$",
        dag_text,
    )
    if not revision_match or revision_match.groups() != (expected["decision"], expected["spec"], expected["plan"]):
        raise ApplyError("DAG revision binding does not match the requested D/S/P set")
    missing_tickets = [ticket_id for ticket_id in ticket_ids if ticket_id not in dag_text]
    if missing_tickets:
        raise ApplyError(f"DAG does not cover tickets: {', '.join(missing_tickets)}")


def _validate_tickets(
    package: Path,
    attempt: str,
    expected: dict[str, str],
    require_approved: bool,
) -> tuple[list[str], dict[Path, bytes], dict[str, Any]]:
    documents = STATE._attempt_ticket_documents(package, attempt)
    if len(documents) < 2:
        raise ApplyError("planning-only publish requires at least two earned tickets")
    ticket_ids = list(documents)
    intended: dict[Path, bytes] = {}
    edges_by_ticket: dict[str, list[tuple[str, str, str]]] = {}
    statuses: dict[str, str] = {}
    for ticket_id, (relative, text) in documents.items():
        if STATE._document_attempt(text) != attempt:
            raise ApplyError(f"ticket {ticket_id} does not belong to attempt {attempt}")
        spec_revision = _field(text, ("规格修订（Spec Revision）", "Spec Revision"), r"S\d+|N/A", f"ticket {ticket_id} Spec Revision")
        plan_revision = _field(text, ("计划修订（Plan Revision）", "Plan Revision"), r"P\d+|N/A", f"ticket {ticket_id} Plan Revision")
        if spec_revision != expected["spec"] or plan_revision != expected["plan"]:
            raise ApplyError(f"ticket {ticket_id} is not bound to {expected['spec']}/{expected['plan']}")
        _acceptance_ids(text)
        statuses[ticket_id], _ = _publication_status_and_output(text)
        if require_approved and statuses[ticket_id] != "Approved":
            raise ApplyError(f"ticket {ticket_id} is not Approved")
        edges_by_ticket[ticket_id] = _typed_edges(text, set(documents))
        path = STATE._package_artifact(package, relative)
        if statuses[ticket_id] == "Draft":
            try:
                raw_text = path.read_bytes().decode("utf-8")
            except (OSError, UnicodeError) as exc:
                raise ApplyError(f"ticket {ticket_id} is not readable UTF-8: {exc}") from exc
            _, raw_published_text = _publication_status_and_output(raw_text)
            intended[path] = raw_published_text.encode("utf-8")
    _validate_graph(ticket_ids, edges_by_ticket)
    return ticket_ids, intended, {"statuses": statuses, "edges": edges_by_ticket}


def _infer_artifact(package: Path, current: dict[str, Any], kind: str, explicit: str | None) -> str:
    key = kind if kind != "plan" else "attempt"
    if explicit:
        return explicit
    existing = current.get(key, {})
    artifact = existing.get("artifact") or existing.get("plan")
    if artifact:
        return artifact
    if kind == "decision":
        if (package / "decision.md").is_file():
            return "decision.md"
        candidates = ["spec.md"] if (package / "spec.md").is_file() else []
    elif kind == "spec":
        candidates = ["spec.md"] if (package / "spec.md").is_file() else []
    else:
        candidates = [
            name
            for name in STATE._package_file_names(package, committed=False)
            if name == "plan.md" or name.endswith(".patch-plan.md") or name.endswith(".plan.md")
        ]
    if len(candidates) != 1:
        raise ApplyError(f"cannot infer a unique {kind} artifact; pass --{kind}-artifact")
    return candidates[0]


def _build_context(
    package: Path,
    aliases: dict[str, str],
    artifacts: dict[str, str | None],
    attempt_override: str | None,
) -> dict[str, Any]:
    _, current_state = STATE._load_revision_state(package)
    current = current_state.get("current", {})
    plan_artifact = _infer_artifact(package, current, "plan", artifacts.get("plan"))
    attempt = attempt_override or current.get("attempt", {}).get("id")
    if not attempt:
        attempt = STATE._document_attempt(STATE._package_artifact(package, plan_artifact).read_text(encoding="utf-8"))
    if not attempt:
        raise ApplyError("current plan attempt cannot be inferred; pass --attempt")
    registrations = []
    for kind in ("decision", "spec", "plan"):
        artifact = _infer_artifact(package, current, kind, artifacts.get(kind))
        registrations.append(
            {
                "kind": kind,
                "alias": aliases[kind],
                "artifact": artifact,
                "attempt": attempt if kind == "plan" else None,
                "evidence": f"impl-package-apply:publish-plan/{aliases[kind]}",
            }
        )
    _, _, candidate, runtime_candidate = STATE._build_registration_candidate(package, registrations)
    selection = candidate.get("current", {}).get("attempt")
    if not selection or selection.get("id") != attempt:
        raise ApplyError("requested plan attempt does not match the candidate revision binding")
    plan_path = STATE._package_artifact(package, selection["plan"])
    tickets_earned, dag_earned = STATE._composition(plan_path.read_text(encoding="utf-8"))
    if not tickets_earned:
        raise ApplyError("fast plan apply requires Composition tickets=true")
    expected = {"decision": aliases["decision"], "spec": aliases["spec"], "plan": aliases["plan"]}
    ticket_ids, intended_tickets, ticket_summary = _validate_tickets(package, attempt, expected, False)
    _validate_dag(package, attempt, ticket_ids, dag_earned, expected)
    return {
        "registrations": registrations,
        "candidate": candidate,
        "runtime_candidate": runtime_candidate,
        "attempt": attempt,
        "plan": selection["plan"],
        "tickets": ticket_ids,
        "ticket_intended": intended_tickets,
        "ticket_summary": ticket_summary,
        "expected": expected,
        "dag": dag_earned,
    }


def _target_paths(package: Path, context: dict[str, Any]) -> list[Path]:
    paths: set[Path] = {
        package / STATE.REVISION_BINDINGS,
        package / STATE.RUNTIME_STATE,
        package / STATE.REGISTRATION_JOURNAL,
        package / JOURNAL_RELATIVE,
    }
    candidate = context["candidate"]
    for selection in candidate.get("current", {}).values():
        if isinstance(selection, dict):
            artifact = selection.get("artifact") or selection.get("plan")
            if artifact:
                paths.add(STATE._package_artifact(package, artifact))
    attempt = context["attempt"]
    dag = STATE._attempt_dag_artifact(package, attempt)
    if dag:
        paths.add(STATE._package_artifact(package, dag))
    for ticket_id in context["tickets"]:
        relative, _ = STATE._attempt_ticket_documents(package, attempt)[ticket_id]
        paths.add(STATE._package_artifact(package, relative))
    gate = package / "gate.md"
    if gate.is_file():
        paths.add(gate)
    return sorted(paths, key=lambda path: path.relative_to(package).as_posix())


def _snapshot(package: Path, paths: list[Path]) -> dict[Path, bytes | None]:
    snapshot: dict[Path, bytes | None] = {}
    for path in paths:
        try:
            snapshot[path] = path.read_bytes()
        except FileNotFoundError:
            snapshot[path] = None
    return snapshot


def _journal_payload(package: Path, context: dict[str, Any], snapshot: dict[Path, bytes | None], phase: str) -> dict[str, Any]:
    repo = STATE._git_root(package)
    files = []
    for path, content in snapshot.items():
        files.append(
            {
                "path": path.resolve().relative_to(package.resolve()).as_posix(),
                "content": None if content is None else base64.b64encode(content).decode("ascii"),
                "sha256": None if content is None else _sha256(content),
            }
        )
    return {
        "version": 1,
        "phase": phase,
        "operation": {
            "decision": context["expected"]["decision"],
            "spec": context["expected"]["spec"],
            "plan": context["expected"]["plan"],
            "attempt": context["attempt"],
            "tickets": context["tickets"],
        },
        "worktreeStatus": _git_status(repo),
        "files": files,
    }


def _git_status(repo: Path) -> list[str]:
    result = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise ApplyError(f"cannot inspect worktree status: {result.stderr.strip() or 'git status failed'}")
    return sorted(line for line in result.stdout.splitlines() if line)


def _status_map(lines: list[str], repo: Path) -> dict[Path, str]:
    statuses: dict[Path, str] = {}
    for line in lines:
        value = line[3:] if len(line) >= 3 else ""
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        if value:
            statuses[(repo / value).resolve()] = line[:2]
    return statuses


def _write_journal(package: Path, payload: dict[str, Any]) -> None:
    STATE._atomic_write_json(package / JOURNAL_RELATIVE, payload)


def _read_journal(package: Path) -> tuple[Path, dict[str, Any]] | None:
    path = package / JOURNAL_RELATIVE
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ApplyError(f"publish transaction journal is invalid: {exc}") from exc
    if not isinstance(payload, dict) or payload.get("version") != 1 or not isinstance(payload.get("files"), list):
        raise ApplyError("publish transaction journal has an invalid shape")
    return path, payload


def _snapshot_from_journal(package: Path, payload: dict[str, Any]) -> dict[Path, bytes | None]:
    snapshot: dict[Path, bytes | None] = {}
    for entry in payload["files"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or "content" not in entry:
            raise ApplyError("publish transaction journal contains an invalid file entry")
        path = STATE._package_artifact(package, entry["path"], must_exist=False)
        content = entry["content"]
        if content is None:
            if entry.get("sha256") is not None:
                raise ApplyError("publish transaction journal contains an invalid missing-file hash")
            snapshot[path] = None
        elif isinstance(content, str):
            try:
                value = base64.b64decode(content, validate=True)
            except ValueError as exc:
                raise ApplyError("publish transaction journal contains invalid snapshot bytes") from exc
            expected_hash = entry.get("sha256")
            if not isinstance(expected_hash, str) or _sha256(value) != expected_hash:
                raise ApplyError("publish transaction journal snapshot hash does not match its bytes")
            snapshot[path] = value
        else:
            raise ApplyError("publish transaction journal snapshot content is invalid")
    return snapshot


def _remove(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def _restore(snapshot: dict[Path, bytes | None]) -> None:
    for path, content in snapshot.items():
        if content is None:
            _remove(path)
        else:
            STATE._atomic_write_bytes(path, content)


def _assert_snapshot(package: Path, snapshot: dict[Path, bytes | None]) -> None:
    for path, expected in snapshot.items():
        actual = path.read_bytes() if path.exists() else None
        if actual != expected:
            raise ApplyError(f"transaction recovery could not restore {path.relative_to(package).as_posix()}")


def _operation_from_journal(payload: dict[str, Any]) -> dict[str, Any]:
    operation = payload.get("operation")
    if not isinstance(operation, dict) or not all(isinstance(operation.get(key), str) for key in ("decision", "spec", "plan", "attempt")):
        raise ApplyError("publish transaction journal operation is invalid")
    tickets = operation.get("tickets")
    if not isinstance(tickets, list) or any(not isinstance(ticket, str) for ticket in tickets):
        raise ApplyError("publish transaction journal ticket set is invalid")
    return operation


def _recover_pending(package: Path) -> None:
    pending = _read_journal(package)
    if pending is not None:
        journal_path, payload = pending
        snapshot = _snapshot_from_journal(package, payload)
        repo = STATE._git_root(package)
        target_paths = set(snapshot)
        baseline_status = _status_map(payload.get("worktreeStatus", []), repo)
        current_status = _status_map(_git_status(repo), repo)
        for status_path in set(baseline_status) | set(current_status):
            if status_path not in target_paths and baseline_status.get(status_path) != current_status.get(status_path):
                raise ApplyError("interrupted publish found changed worktree state outside its transaction targets")
        operation = _operation_from_journal(payload)
        expected = {
            "decision": operation["decision"],
            "spec": operation["spec"],
            "plan": operation["plan"],
        }
        try:
            _validate_final_state(package, operation["attempt"], expected, operation["tickets"])
        except ApplyError:
            try:
                _restore(snapshot)
                _assert_snapshot(package, snapshot)
                STATE._recover_registration_transaction(package)
                _assert_snapshot(package, snapshot)
            except Exception as exc:
                raise ApplyError(f"interrupted publish recovery failed; journal retained: {exc}") from exc
        else:
            _remove(package / STATE.REGISTRATION_JOURNAL)
        _remove(journal_path)
    elif (package / STATE.REGISTRATION_JOURNAL).exists():
        try:
            STATE._recover_registration_transaction(package)
            STATE.command_validate(package, committed=False)
        except Exception as exc:
            raise ApplyError(f"registration transaction recovery failed: {exc}") from exc


def _validate_final_state(package: Path, attempt: str, expected: dict[str, str], ticket_ids: list[str]) -> dict[str, Any]:
    STATE.command_validate(package, committed=False)
    _, revision_state = STATE._load_revision_state(package)
    current = revision_state.get("current", {})
    actual = {
        "decision": current.get("decision", {}).get("revision"),
        "spec": current.get("spec", {}).get("revision"),
        "plan": current.get("attempt", {}).get("revision"),
    }
    if actual != expected:
        raise ApplyError(f"revision binding summary is not {expected['decision']}/{expected['spec']}/{expected['plan']}")
    if current.get("attempt", {}).get("id") != attempt:
        raise ApplyError("current attempt does not match the published plan")
    actual_ticket_ids, _, _ = _validate_tickets(package, attempt, expected, True)
    if actual_ticket_ids != ticket_ids:
        raise ApplyError("published ticket set differs from the transaction ticket set")
    _, plan_path = STATE._current_attempt(package) or (None, None)
    if plan_path is None:
        raise ApplyError("current attempt plan is missing after publish")
    _, dag_earned = STATE._composition(plan_path.read_text(encoding="utf-8"))
    _validate_dag(package, attempt, ticket_ids, dag_earned, expected)
    STATE._assert_attempt_decomposition_revision_bindings(package, attempt, expected)
    return {"revisionSet": actual, "attempt": attempt, "tickets": ticket_ids}


def _ensure_deadline(deadline: float, phase: str) -> None:
    if time.monotonic() > deadline:
        raise ApplyError(f"apply deadline exceeded during {phase}")


def _publish_plan(args: argparse.Namespace) -> int:
    package = args.package.resolve()
    if not package.is_dir():
        raise ApplyError(f"package directory does not exist: {package}")
    if args.timeout_seconds <= 0:
        raise ApplyError("--timeout-seconds must be greater than zero")
    started = time.monotonic()
    deadline = started + args.timeout_seconds
    _recover_pending(package)
    aliases = {"decision": args.decision, "spec": args.spec, "plan": args.plan}
    artifacts = {"decision": args.decision_artifact, "spec": args.spec_artifact, "plan": args.plan_artifact}
    ledger_info = _verify_review_and_authorization(package, args.ledger.resolve(), args.authorization, deadline)
    del ledger_info
    _ensure_deadline(deadline, "authorization")
    context = _build_context(package, aliases, artifacts, args.attempt)
    _ensure_deadline(deadline, "preflight")
    paths = _target_paths(package, context)
    snapshot = _snapshot(package, paths)
    journal_path = package / JOURNAL_RELATIVE
    _write_journal(package, _journal_payload(package, context, snapshot, "prepared"))
    try:
        for path, content in context["ticket_intended"].items():
            STATE._atomic_write_bytes(path, content)
        STATE.command_register_revisions(package, context["registrations"], validate=False)
        _validate_final_state(package, context["attempt"], context["expected"], context["tickets"])
        _ensure_deadline(deadline, "final validation")
        _remove(package / STATE.REGISTRATION_JOURNAL)
        _remove(journal_path)
        if journal_path.exists():
            raise ApplyError("publish applied but transaction journal cleanup failed")
    except BaseException as exc:
        try:
            _restore(snapshot)
            _assert_snapshot(package, snapshot)
            _remove(package / STATE.REGISTRATION_JOURNAL)
            _remove(journal_path)
        except Exception as rollback_exc:
            raise ApplyError(f"publish failed and rollback is incomplete: {rollback_exc}") from exc
        if isinstance(exc, ApplyError):
            raise
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise ApplyError(f"publish interrupted and rolled back: {exc}") from exc
        raise ApplyError(f"publish failed and rolled back: {exc}") from exc
    return 0


def _summary_status(text: str) -> str:
    matches = list(PUBLICATION_RE.finditer(text))
    return matches[0].group(1) if len(matches) == 1 else "invalid"


def _sync_working_unit(args: argparse.Namespace) -> int:
    package = args.package.resolve()
    if not package.is_dir():
        raise ApplyError(f"package directory does not exist: {package}")
    context = "committed" if args.committed else "working-tree"
    STATE.command_validate(package, committed=args.committed)
    _, revisions = STATE._load_revision_state(package)
    current = revisions.get("current", {})
    attempt = current.get("attempt", {})
    if not attempt:
        raise ApplyError("package has no current plan attempt")
    ticket_docs = STATE._attempt_ticket_documents(package, attempt["id"], committed=args.committed)
    statuses = []
    for ticket_id, (_, text) in ticket_docs.items():
        statuses.append((ticket_id, _summary_status(text)))
    revision_set = (
        current.get("decision", {}).get("revision", "N/A"),
        current.get("spec", {}).get("revision", "N/A"),
        attempt.get("revision", "N/A"),
    )
    approved = sum(status == "Approved" for _, status in statuses)
    dag = STATE._attempt_dag_artifact(package, attempt["id"], committed=args.committed)
    lines = [
        f"## Implementation Package {package.name}",
        "",
        f"- Repository: `{args.repo}`",
        f"- PR: #{args.pr}",
        f"- Issue: #{args.issue}",
        f"- Revisions: {revision_set[0]} / {revision_set[1]} / {revision_set[2]}",
        f"- Attempt: `{attempt['id']}`",
        f"- Tickets: {approved}/{len(statuses)} Approved",
        f"- DAG: `{dag or 'not earned'}`",
        f"- State validation: `{context}`",
        "",
        "### Summary",
        "",
        f"Planning-only apply published the current ticket bundle and registered {revision_set[0]}/{revision_set[1]}/{revision_set[2]}.",
        "No implementation, database, application-runtime, commit, push, or remote mutation is performed by this helper.",
        "",
        "### Ticket status",
        "",
    ]
    lines.extend(f"- `{ticket_id}`: {status}" for ticket_id, status in statuses)
    output = "\n".join(lines) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        sys.stdout.write(output)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Deterministic Impl-Package planning apply helpers")
    subparsers = parser.add_subparsers(dest="command", required=True)
    publish = subparsers.add_parser("publish-plan")
    publish.add_argument("--package", required=True, type=Path)
    publish.add_argument("--decision", required=True)
    publish.add_argument("--spec", required=True)
    publish.add_argument("--plan", required=True)
    publish.add_argument("--ledger", required=True, type=Path)
    publish.add_argument("--authorization", required=True, help="owner authorization JSON path, or - for stdin")
    publish.add_argument("--attempt")
    publish.add_argument("--decision-artifact")
    publish.add_argument("--spec-artifact")
    publish.add_argument("--plan-artifact")
    publish.add_argument("--timeout-seconds", type=float, default=90.0)
    sync = subparsers.add_parser("sync-working-unit")
    sync.add_argument("--package", required=True, type=Path)
    sync.add_argument("--repo", required=True)
    sync.add_argument("--pr", required=True, type=int)
    sync.add_argument("--issue", required=True, type=int)
    sync.add_argument("--output", type=Path)
    sync.add_argument("--committed", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "publish-plan":
            _publish_plan(args)
            print("APPLIED")
        else:
            _sync_working_unit(args)
        return 0
    except (ApplyError, OSError, STATE.StateError) as exc:
        print(f"BLOCKER {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
