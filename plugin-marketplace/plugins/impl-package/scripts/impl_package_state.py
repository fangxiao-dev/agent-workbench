#!/usr/bin/env python3
"""Current execution state and readable projections for Impl-Package.

Git commit IDs are the only persisted version anchors. D/S/P aliases are
optional human-readable labels for legacy packages. The helper deliberately has no content identity,
artifact ledger, migration chain, or legacy reader.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


STATE_PATH = Path(".impl-package/state.json")
PROGRESS_PATH = Path("progress.md")
EXECUTION_PATH = Path("execution")
GATE_PATH = Path("gate.md")
FORMAT_VERSION = "3.4"

TASK_STATES = {
    "PENDING", "READY", "RUNNING", "BLOCKED", "FAILED",
    "NEEDS-REVALIDATION", "DONE", "WAIVED", "SUPERSEDED",
}
TICKET_STATES = {
    "PENDING", "BLOCKED", "NEEDS-REVALIDATION",
    "SATISFIED", "WAIVED", "SUPERSEDED",
}
TASK_DEPENDENCY_RELEASING = {"DONE", "WAIVED", "SUPERSEDED"}
TICKET_DEPENDENCY_RELEASING = {"SATISFIED", "WAIVED", "SUPERSEDED"}
TERMINAL_VERDICTS = {"pass", "fail", "defer"}
VERDICTS = TERMINAL_VERDICTS | {"blocked"}

ATTEMPT_RE = re.compile(
    r"(?m)^(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:](?:\*\*)?\s*([^\s*]+)"
)
COMPOSITION_RE = re.compile(r"Composition[^\n]*tickets=(true|false),\s*dag=(true|false)", re.I)
DECISION_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Decision Revision|决策修订（Decision Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(D\d+)\b")
SPEC_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Spec Revision|规格修订（Spec Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(S\d+)\b")
PLAN_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Plan Revision|计划修订（Plan Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(P\d+)\b")
TICKET_ID_RE = re.compile(r"(?m)^\s*\*\*Ticket ID[：:]\*\*\s*([^\s]+)")
PUBLICATION_RE = re.compile(r"(?m)^(\*\*(?:Publication Status|发布状态（Publication Status）)[：:]\*\*\s*)(Draft|Approved)\s*$")
COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
PACKAGE_ID_RE = re.compile(r"^(?:\d{6}|\d{8}|\d{4}-\d{2}-\d{2})[-_][A-Za-z0-9].+")
ATTEMPT_ID_RE = re.compile(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})")
ER_ENTRY_RE = re.compile(r"(?m)^## ([^\s]+-ER-(\d{3})) · (checkpoint|judgment)\s*$")


class StateError(RuntimeError):
    pass


@dataclass(frozen=True)
class AttemptLifecycle:
    ACTIVE = "active"
    FROZEN = "frozen"

    attempt: str
    gate: dict[str, Any] | None
    value: str

    @classmethod
    def derive(cls, attempt: str, observed_gate: dict[str, Any] | None) -> AttemptLifecycle:
        gate = observed_gate if observed_gate and observed_gate["attempt"] == attempt else None
        value = cls.FROZEN if gate and gate["verdict"] in TERMINAL_VERDICTS else cls.ACTIVE
        return cls(attempt=attempt, gate=gate, value=value)

    @property
    def active(self) -> bool:
        return self.value == self.ACTIVE

    @property
    def frozen(self) -> bool:
        return self.value == self.FROZEN

    @property
    def gate_verdict(self) -> str:
        return self.gate["verdict"] if self.gate else "open"

    def project_resume(self, resume: dict[str, Any]) -> dict[str, Any]:
        if self.active:
            return resume
        return {"blocker": None, "next": None, "evidence": None}


def _run_git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise StateError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result.stdout.strip()


def _repo_root(package: Path) -> Path:
    return Path(_run_git(package, "rev-parse", "--show-toplevel")).resolve()


def _repo_relative(repo: Path, value: str, field: str, *, must_exist: bool = True) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StateError(f"{field} must be a non-empty repository-relative path")
    raw = value.strip().replace("\\", "/")
    path = PurePosixPath(raw.split("#", 1)[0])
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw) or raw.startswith("//") or ".." in path.parts or str(path) in {"", "."}:
        raise StateError(f"{field} must be a repository-relative path: {value!r}")
    resolved = (repo / Path(*path.parts)).resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise StateError(f"{field} escapes the repository: {value!r}") from exc
    if must_exist and not resolved.exists():
        raise StateError(f"{field} does not exist: {path.as_posix()}")
    anchor = "#" + raw.split("#", 1)[1] if "#" in raw else ""
    return path.as_posix() + anchor


def _package_relative(package: Path, path: Path) -> str:
    return path.resolve().relative_to(package.resolve()).as_posix()


def _read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        raise StateError(f"cannot read {path}: {exc}") from exc


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(_read(path))
    except json.JSONDecodeError as exc:
        raise StateError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise StateError(f"{path} must contain a JSON object")
    return value


def _write_text(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp_name = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def _field(pattern: re.Pattern[str], text: str, label: str, *, optional: bool = False) -> str | None:
    match = pattern.search(text)
    if match:
        return match.group(1)
    if optional:
        return None
    raise StateError(f"missing {label}")


def _plan_info(package: Path, repo: Path, plan_value: str) -> dict[str, Any]:
    plan_rel = _repo_relative(repo, plan_value, "plan")
    plan_path = repo / plan_rel.split("#", 1)[0]
    try:
        plan_path.resolve().relative_to(package.resolve())
    except ValueError as exc:
        raise StateError("current plan must be inside the package") from exc
    if not (package / "spec.md").is_file():
        raise StateError("spec.md is required for an active Attempt")
    text = _read(plan_path)
    composition = COMPOSITION_RE.search(text)
    if composition is None:
        raise StateError("plan is missing Composition tickets/dag fields")
    attempt = _field(ATTEMPT_RE, text, "Attempt ID")
    if ATTEMPT_ID_RE.fullmatch(str(attempt)) is None:
        raise StateError(f"invalid Attempt ID: {attempt!r}")
    return {
        "path": plan_rel,
        "attempt": attempt,
        "decision": _field(DECISION_RE, text, "Decision Revision", optional=True),
        "spec": _field(SPEC_RE, text, "Spec Revision", optional=True),
        "plan": _field(PLAN_RE, text, "Plan Revision", optional=True),
        "tickets": composition.group(1).lower() == "true",
        "dag": composition.group(2).lower() == "true",
    }


def _ticket_documents(package: Path, attempt: str) -> list[dict[str, Any]]:
    directory = package / "tickets"
    if not directory.is_dir():
        raise StateError("Composition earns tickets but tickets/ is missing")
    result: list[dict[str, Any]] = []
    for child in sorted(directory.iterdir(), key=lambda item: item.name):
        if not child.is_file() or child.suffix.lower() != ".md":
            continue
        text = _read(child)
        identifier = _field(TICKET_ID_RE, text, f"Ticket ID in {child.name}")
        ticket_attempt = _field(ATTEMPT_RE, text, f"Attempt ID in {child.name}")
        if ticket_attempt != attempt:
            continue
        if any(row["id"] == identifier for row in result):
            raise StateError(f"duplicate Ticket ID for Attempt {attempt}: {identifier}")
        publication_match = PUBLICATION_RE.search(text)
        if publication_match is None:
            raise StateError(f"missing Publication Status in {child.name}")
        publication = publication_match.group(2)
        result.append({"id": str(identifier), "path": child, "text": text, "publication": publication})
    if not result:
        raise StateError(f"Composition earns tickets but no Ticket belongs to Attempt {attempt}")
    return result


def _dag_path(package: Path, attempt: str) -> Path:
    return package / ("dag.md" if attempt == "initial" else f"{attempt}.patch-dag.md")


def _dag_contract(package: Path, attempt: str) -> dict[str, list[str]]:
    path = _dag_path(package, attempt)
    if not path.is_file():
        raise StateError(f"Composition earns DAG but {path.name} is missing")
    text = _read(path)
    section = re.search(r"(?ms)^## Task graph\s*$\n(.*?)(?=^## |\Z)", text)
    if section is None:
        raise StateError("earned DAG is missing the Task graph section")
    result: dict[str, list[str]] = {}
    for line in section.group(1).splitlines():
        if not re.match(r"^\|\s*T[1-9]\d*\s*\|", line):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) < 5:
            raise StateError(f"invalid DAG Task row: {line}")
        identifier = cells[0]
        if identifier in result:
            raise StateError(f"duplicate Task ID: {identifier}")
        if not cells[1] or cells[1].lower() in {"none", "n/a"}:
            raise StateError(f"Task {identifier} is missing Primary ownership")
        raw_dependencies = cells[2]
        dependencies = [] if raw_dependencies.lower() == "none" else [item.strip() for item in raw_dependencies.split(",") if item.strip()]
        if any(re.fullmatch(r"T[1-9]\d*", item) is None for item in dependencies):
            raise StateError(f"Task {identifier} has invalid dependency syntax")
        result[identifier] = dependencies
    if not result:
        raise StateError("earned DAG has no Task rows")
    for identifier, dependencies in result.items():
        unknown = [item for item in dependencies if item not in result]
        if unknown:
            raise StateError(f"Task {identifier} has unknown dependencies: {', '.join(unknown)}")
    _reject_cycles(result, "Task DAG")
    return result


def _ticket_dependencies(documents: list[dict[str, Any]]) -> dict[str, list[tuple[str, str]]]:
    identifiers = {row["id"] for row in documents}
    result: dict[str, list[tuple[str, str]]] = {}
    for row in documents:
        section = re.search(r"(?ms)^## 阻塞依赖\s*$\n(.*?)(?=^## |\Z)", row["text"])
        dependencies: list[tuple[str, str]] = []
        if section:
            for line in section.group(1).splitlines():
                stripped = line.strip()
                if not stripped.startswith("-") or stripped.lower() in {"- none", "- 无"}:
                    continue
                match = re.fullmatch(r"-\s*(implementation|acceptance|release)\s*:\s*([^\s]+)", stripped)
                if match is None:
                    raise StateError(f"Ticket {row['id']} has invalid typed dependency: {stripped}")
                dependency = match.group(2)
                if dependency not in identifiers:
                    raise StateError(f"Ticket {row['id']} has unknown dependency: {dependency}")
                dependencies.append((match.group(1), dependency))
        result[row["id"]] = dependencies
    _reject_cycles({key: [item for _, item in value] for key, value in result.items()}, "Ticket dependency graph")
    return result


def _reject_cycles(graph: dict[str, list[str]], label: str) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> None:
        if node in visiting:
            raise StateError(f"{label} contains a cycle at {node}")
        if node in visited:
            return
        visiting.add(node)
        for dependency in graph[node]:
            visit(dependency)
        visiting.remove(node)
        visited.add(node)

    for node in graph:
        visit(node)


def _gate_info(package: Path, repo: Path) -> dict[str, Any] | None:
    path = package / GATE_PATH
    if not path.exists():
        return None
    text = _read(path)
    verdict = re.search(r"(?m)^- Verdict:\s*(pass|fail|blocked|defer)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    commit = re.search(r"(?m)^- Comparison commit:\s*([0-9a-fA-F]{7,64})\s*$", text)
    if not verdict or not attempt or not commit:
        raise StateError("gate.md is missing Verdict, Attempt, or Comparison commit")
    resolved = _validate_commit(repo, commit.group(1))
    return {"verdict": verdict.group(1), "attempt": attempt.group(1), "commit": resolved}


def _validate_commit(repo: Path, commit: str) -> str:
    if COMMIT_RE.fullmatch(commit) is None:
        raise StateError(f"invalid Git commit ID: {commit!r}")
    return _run_git(repo, "rev-parse", "--verify", f"{commit}^{{commit}}")


def _validate_records(
    repo: Path,
    records: Any,
    states: set[str],
    label: str,
    *,
    live_evidence: bool,
) -> dict[str, Any]:
    if not isinstance(records, dict):
        raise StateError(f"{label} must be an object keyed by ID")
    for identifier, row in records.items():
        if not isinstance(identifier, str) or not identifier or not isinstance(row, dict) or set(row) != {"state", "evidence"}:
            raise StateError(f"invalid {label} record: {identifier!r}")
        if row["state"] not in states:
            raise StateError(f"invalid {label} state for {identifier}: {row['state']!r}")
        evidence = row["evidence"]
        if evidence is not None:
            row["evidence"] = _repo_relative(
                repo,
                evidence,
                f"{label} {identifier} evidence",
                must_exist=live_evidence,
            )
        elif row["state"] != "PENDING":
            raise StateError(f"{label} {identifier} state {row['state']} requires evidence")
    return records


def _projection(text: str, name: str) -> str | None:
    begin = f"<!-- impl-package:projection {name} begin -->"
    end = f"<!-- impl-package:projection {name} end -->"
    if begin not in text and end not in text:
        return None
    if text.count(begin) != 1 or text.count(end) != 1 or text.index(begin) > text.index(end):
        raise StateError(f"invalid {name} projection markers")
    return text.split(begin, 1)[1].split(end, 1)[0].strip()


def _replace_projection(text: str, name: str, heading: str, body: str) -> str:
    begin = f"<!-- impl-package:projection {name} begin -->"
    end = f"<!-- impl-package:projection {name} end -->"
    current = _projection(text, name)
    block = f"{begin}\n{body.rstrip()}\n{end}"
    if current is None:
        return text.rstrip() + f"\n\n## {heading}\n\n{block}\n"
    prefix, rest = text.split(begin, 1)
    _, suffix = rest.split(end, 1)
    return prefix + block + suffix


def _ticket_projection(row: dict[str, Any]) -> str:
    evidence = row["evidence"] or "none"
    return f"- Runtime Acceptance Status: {row['state']}\n- Acceptance evidence: {evidence}"


def _publish_ticket(document: dict[str, Any], row: dict[str, Any]) -> None:
    text = document["text"]
    text = PUBLICATION_RE.sub("**Publication Status：** Approved", text, count=1)
    text = _replace_projection(text, "runtime-acceptance", "Runtime Acceptance", _ticket_projection(row))
    _write_text(document["path"], text)
    document.update({"text": text, "publication": "Approved"})


def _task_handoff_path(package: Path, attempt: str, task: str) -> Path:
    return package / EXECUTION_PATH / attempt / "task-handoffs" / f"{task}-handoff.md"


def _dag_projection(package: Path, attempt: str, tasks: dict[str, Any]) -> str:
    lines = ["| Task | State | Evidence | Handoff |", "| --- | --- | --- | --- |"]
    for identifier, row in tasks.items():
        handoff_path = _task_handoff_path(package, attempt, identifier)
        handoff = _package_relative(package, handoff_path) if handoff_path.is_file() else "none"
        lines.append(f"| {identifier} | {row['state']} | {row['evidence'] or 'none'} | {handoff} |")
    return "\n".join(lines)


def _execution_record_path(package: Path, attempt: str) -> Path:
    return package / EXECUTION_PATH / attempt / "execution-record.md"


def _new_execution_record(attempt: str) -> str:
    return (
        f"# Execution Record · {attempt}\n\n"
        f"- Attempt: {attempt}\n"
        "- Lifecycle: active\n"
        "- Gate: open\n\n"
        "> 记录无法从 current state、Git 或验证产物可靠推导的 checkpoint 与 judgment。\n"
        "> 本文件不使用 seal、内容身份或审计链；terminal Gate 后停止写入。\n"
    )


def _ensure_execution_record(package: Path, attempt: str) -> Path:
    path = _execution_record_path(package, attempt)
    if not path.exists():
        _write_text(path, _new_execution_record(attempt))
    metadata, _ = _parse_execution_record(path, attempt)
    if metadata["attempt"] != attempt:
        raise StateError(f"Execution Record Attempt mismatch: {path}")
    return path


def _entry_field(block: str, name: str, *, optional: bool = False) -> str | None:
    match = re.search(rf"(?m)^- {re.escape(name)}:\s*(.*?)\s*$", block)
    if match:
        return match.group(1)
    if optional:
        return None
    raise StateError(f"Execution Record entry is missing {name}")


def _parse_execution_record(path: Path, expected_attempt: str | None = None) -> tuple[dict[str, str], list[dict[str, Any]]]:
    text = _read(path)
    heading = re.search(r"(?m)^# Execution Record · ([^\s]+)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    lifecycle = re.search(r"(?m)^- Lifecycle:\s*(active|frozen)\s*$", text)
    gate = re.search(r"(?m)^- Gate:\s*(open|pass|fail|blocked|defer)\s*$", text)
    if not heading or not attempt or not lifecycle or not gate:
        raise StateError(f"invalid Execution Record header: {path}")
    if heading.group(1) != attempt.group(1) or (expected_attempt and attempt.group(1) != expected_attempt):
        raise StateError(f"Execution Record Attempt mismatch: {path}")
    matches = list(ER_ENTRY_RE.finditer(text))
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    previous_number = 0
    for index, match in enumerate(matches):
        record_id, number, purpose = match.group(1), int(match.group(2)), match.group(3)
        if not record_id.startswith(attempt.group(1) + "-ER-") or record_id in seen or number <= previous_number:
            raise StateError(f"invalid Execution Record ID sequence: {record_id}")
        seen.add(record_id)
        previous_number = number
        block = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        sections = re.search(r"(?ms)^### Evidence\s*$\n(.*?)^### Content\s*$\n(.*)\Z", block.strip())
        if sections is None:
            raise StateError(f"Execution Record {record_id} is missing Evidence or Content")
        evidence: list[str] = []
        for line in sections.group(1).strip().splitlines():
            if line.strip() in {"- none", ""}:
                continue
            if not line.startswith("- "):
                raise StateError(f"Execution Record {record_id} has invalid evidence")
            evidence.append(line[2:].strip())
        next_action = _entry_field(block, "Next action")
        entries.append({
            "id": record_id,
            "number": number,
            "purpose": purpose,
            "subject": _entry_field(block, "Subject"),
            "supersedes": _entry_field(block, "Supersedes"),
            "title": _entry_field(block, "Title"),
            "nextAction": None if next_action == "none" else next_action,
            "evidence": evidence,
            "content": sections.group(2).strip(),
        })
    return {"attempt": attempt.group(1), "lifecycle": lifecycle.group(1), "gate": gate.group(1)}, entries


def _set_execution_record_status(package: Path, attempt: str, lifecycle: str, gate: str) -> None:
    path = _ensure_execution_record(package, attempt)
    text = _read(path)
    text = re.sub(r"(?m)^- Lifecycle:\s*(?:active|frozen)\s*$", f"- Lifecycle: {lifecycle}", text, count=1)
    text = re.sub(r"(?m)^- Gate:\s*(?:open|pass|fail|blocked|defer)\s*$", f"- Gate: {gate}", text, count=1)
    _write_text(path, text)


def _normalize_payload(
    repo: Path,
    state: dict[str, Any],
    payload: Any,
    *,
    live_evidence: bool = True,
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise StateError("er-add input must be a JSON object")
    allowed = {"purpose", "subject", "title", "content", "nextAction", "evidence"}
    unsupported = set(payload) - allowed
    if unsupported:
        raise StateError(f"unsupported fields: {', '.join(sorted(unsupported))}")
    purpose = payload.get("purpose")
    if purpose not in {"checkpoint", "judgment"}:
        raise StateError(f"unsupported Execution Record purpose: {purpose!r}")
    subject = payload.get("subject", "attempt")
    if subject != "attempt":
        match = re.fullmatch(r"(ticket|task):([^\s]+)", str(subject))
        if match is None:
            raise StateError(f"invalid Execution Record subject: {subject!r}")
        key = "tickets" if match.group(1) == "ticket" else "tasks"
        if match.group(2) not in state[key]:
            raise StateError(f"unknown Execution Record subject: {subject}")
    title = payload.get("title")
    content = payload.get("content")
    if not isinstance(title, str) or not title.strip() or "\n" in title:
        raise StateError("Execution Record title must be one non-empty line")
    if not isinstance(content, str) or not content.strip():
        raise StateError("Execution Record content must be non-empty")
    next_action = payload.get("nextAction")
    if purpose == "checkpoint" and (not isinstance(next_action, str) or not next_action.strip() or "\n" in next_action):
        raise StateError("checkpoint requires one-line nextAction")
    if purpose == "judgment" and next_action is not None:
        raise StateError("judgment does not accept nextAction")
    raw_evidence = payload.get("evidence", [])
    if isinstance(raw_evidence, str):
        raw_evidence = [raw_evidence]
    if not isinstance(raw_evidence, list) or any(not isinstance(item, str) for item in raw_evidence):
        raise StateError("Execution Record evidence must be a path or list of paths")
    evidence = [
        _repo_relative(repo, item, "Execution Record evidence", must_exist=live_evidence)
        for item in raw_evidence
    ]
    return {
        "purpose": purpose,
        "subject": str(subject),
        "title": title.strip(),
        "content": content.strip(),
        "nextAction": next_action.strip() if isinstance(next_action, str) else None,
        "evidence": evidence,
    }


def _same_payload(entry: dict[str, Any], payload: dict[str, Any]) -> bool:
    return all(entry[key] == payload[key] for key in ("purpose", "subject", "title", "content", "nextAction", "evidence"))


def _render_entry(record_id: str, payload: dict[str, Any], supersedes: str | None) -> str:
    evidence = "\n".join(f"- {item}" for item in payload["evidence"]) or "- none"
    return (
        f"\n## {record_id} · {payload['purpose']}\n\n"
        f"- Subject: {payload['subject']}\n"
        f"- Supersedes: {supersedes or 'none'}\n"
        f"- Title: {payload['title']}\n"
        f"- Next action: {payload['nextAction'] or 'none'}\n\n"
        f"### Evidence\n\n{evidence}\n\n"
        f"### Content\n\n{payload['content']}\n"
    )


def _active_checkpoints(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    active: dict[str, dict[str, Any]] = {}
    for entry in entries:
        if entry["purpose"] == "checkpoint":
            active[entry["subject"]] = entry
    return list(active.values())


def _assert_mutable(lifecycle: AttemptLifecycle) -> None:
    if lifecycle.frozen:
        raise StateError(
            f"Attempt {lifecycle.attempt} is frozen by terminal Gate {lifecycle.gate_verdict}"
        )


def _ready_tasks(graph: dict[str, list[str]], tasks: dict[str, Any]) -> list[str]:
    return [
        identifier for identifier, dependencies in graph.items()
        if tasks[identifier]["state"] == "PENDING"
        and all(tasks[item]["state"] in TASK_DEPENDENCY_RELEASING for item in dependencies)
    ]


def _ready_tickets(dependencies: dict[str, list[tuple[str, str]]], tickets: dict[str, Any]) -> list[str]:
    return [
        identifier for identifier, edges in dependencies.items()
        if tickets[identifier]["state"] == "PENDING"
        and all(tickets[item]["state"] in TICKET_DEPENDENCY_RELEASING for kind, item in edges if kind == "implementation")
    ]


def _validate_state(package: Path, state: dict[str, Any], *, projections: bool = True) -> dict[str, Any]:
    expected_fields = {"formatVersion", "attempt", "tasks", "tickets", "resume"}
    if set(state) != expected_fields:
        raise StateError(f"state.json must use formatVersion {FORMAT_VERSION} and contain attempt, tasks, tickets, resume")
    if state["formatVersion"] != FORMAT_VERSION:
        raise StateError(f"unsupported state formatVersion {state['formatVersion']!r}; expected {FORMAT_VERSION!r}")
    repo = _repo_root(package)
    attempt = state.get("attempt")
    if not isinstance(attempt, dict) or set(attempt) != {"id", "plan"}:
        raise StateError("state attempt must contain id and plan")
    if not isinstance(attempt["id"], str) or not attempt["id"]:
        raise StateError("state attempt id is invalid")
    if ATTEMPT_ID_RE.fullmatch(attempt["id"]) is None:
        raise StateError(f"invalid state Attempt ID: {attempt['id']!r}")
    info = _plan_info(package, repo, attempt["plan"])
    if info["attempt"] != attempt["id"]:
        raise StateError("state Attempt ID does not match the current plan")
    lifecycle = AttemptLifecycle.derive(attempt["id"], _gate_info(package, repo))
    documents = _ticket_documents(package, attempt["id"]) if info["tickets"] else []
    graph = _dag_contract(package, attempt["id"]) if info["dag"] else {}
    tasks = _validate_records(
        repo,
        state["tasks"],
        TASK_STATES,
        "task",
        live_evidence=lifecycle.active,
    )
    tickets = _validate_records(
        repo,
        state["tickets"],
        TICKET_STATES,
        "ticket",
        live_evidence=lifecycle.active,
    )
    if set(tasks) != set(graph):
        raise StateError("task state does not match the earned DAG")
    if set(tickets) != {row["id"] for row in documents}:
        raise StateError("ticket state does not match earned Ticket files for the current Attempt")
    dependencies = _ticket_dependencies(documents) if documents else {}
    for identifier, row in tasks.items():
        if row["state"] in {"READY", "RUNNING"} and not all(tasks[item]["state"] in TASK_DEPENDENCY_RELEASING for item in graph[identifier]):
            raise StateError(f"Task {identifier} is {row['state']} while dependencies are not released")
    resume = state.get("resume")
    if not isinstance(resume, dict) or set(resume) != {"blocker", "next", "evidence"}:
        raise StateError("resume must contain blocker, next, and evidence")
    for key in ("blocker", "next"):
        if resume[key] is not None and (not isinstance(resume[key], str) or not resume[key].strip()):
            raise StateError(f"resume {key} must be null or non-empty text")
    if resume["evidence"] is not None:
        resume["evidence"] = _repo_relative(
            repo,
            resume["evidence"],
            "resume evidence",
            must_exist=lifecycle.active,
        )
    summary = {
        "formatVersion": FORMAT_VERSION,
        "attempt": attempt["id"],
        "revisions": {"decision": info["decision"], "spec": info["spec"], "plan": info["plan"]},
        "composition": {"tickets": info["tickets"], "dag": info["dag"]},
        "tasks": len(tasks),
        "tickets": len(tickets),
        "readyTasks": _ready_tasks(graph, tasks),
        "readyTickets": _ready_tickets(dependencies, tickets),
        "gate": lifecycle.gate,
        "_lifecycle": lifecycle,
        "_info": info,
        "_documents": documents,
        "_graph": graph,
        "_ticketDependencies": dependencies,
    }
    if projections:
        _validate_projections(package, state, summary)
    return summary


def _escape_table(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _format_aliases(revisions: dict[str, str | None]) -> str:
    values = [value for value in (revisions["decision"], revisions["spec"], revisions["plan"]) if value]
    return " / ".join(values) if values else "none (Git commit is the history anchor)"


def _attempt_history(package: Path, lifecycle: AttemptLifecycle) -> list[dict[str, str]]:
    root = package / EXECUTION_PATH
    if not root.is_dir():
        return []
    result: list[dict[str, str]] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir():
            continue
        path = child / "execution-record.md"
        if not path.is_file():
            continue
        metadata, _ = _parse_execution_record(path, child.name)
        if child.name == lifecycle.attempt:
            metadata = {
                "attempt": lifecycle.attempt,
                "lifecycle": lifecycle.value,
                "gate": lifecycle.gate_verdict,
            }
        metadata["path"] = _package_relative(package, path)
        result.append(metadata)
    return result


def _render_progress(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> str:
    attempt = summary["attempt"]
    lifecycle = summary["_lifecycle"]
    current_gate = lifecycle.gate_verdict
    resume = lifecycle.project_resume(state["resume"])
    revisions = summary["revisions"]
    composition = summary["composition"]
    blockers: list[str] = []
    if resume["blocker"]:
        blockers.append(resume["blocker"])
    blockers.extend(f"task:{identifier}" for identifier, row in state["tasks"].items() if row["state"] == "BLOCKED")
    blockers.extend(f"ticket:{identifier}" for identifier, row in state["tickets"].items() if row["state"] == "BLOCKED")
    er_path = _ensure_execution_record(package, attempt)
    _, entries = _parse_execution_record(er_path, attempt)
    lines = [
        f"# Attempt Progress · {attempt}", "",
        "> machine-owned projection；使用 `refresh-progress` 重建，不直接编辑。", "",
        f"- Attempt: {attempt}",
        f"- Contract aliases: {_format_aliases(revisions)}",
        f"- Composition: tickets={str(composition['tickets']).lower()}, dag={str(composition['dag']).lower()}",
        f"- Lifecycle: {lifecycle.value}",
        f"- Latest gate: {current_gate}",
        f"- Blockers: {', '.join(_escape_table(item) for item in blockers) if blockers else 'none'}", "",
    ]
    if composition["tickets"]:
        lines.extend(["## Ticket Acceptance", "", "| Ticket | State | Evidence |", "| --- | --- | --- |"])
        for identifier, row in state["tickets"].items():
            lines.append(f"| {identifier} | {row['state']} | {_escape_table(row['evidence'] or 'none')} |")
        lines.append("")
    else:
        lines.extend(["## Acceptance", "", "- Source: spec.md", ""])
    if composition["dag"]:
        lines.extend(["## Task Execution", "", "| Task | State | Evidence | Handoff |", "| --- | --- | --- | --- |"])
        for identifier, row in state["tasks"].items():
            handoff_path = _task_handoff_path(package, attempt, identifier)
            handoff = _package_relative(package, handoff_path) if handoff_path.is_file() else "none"
            lines.append(f"| {identifier} | {row['state']} | {_escape_table(row['evidence'] or 'none')} | {handoff} |")
        lines.append("")
    lines.extend(["## Active Checkpoints", "", "| Record | Subject | Status | Next action | Evidence |", "| --- | --- | --- | --- | --- |"])
    active = _active_checkpoints(entries) if lifecycle.active else []
    if active:
        for entry in active:
            status = "active"
            if entry["subject"] != "attempt":
                kind, identifier = entry["subject"].split(":", 1)
                collection = state["tickets"] if kind == "ticket" else state["tasks"]
                if collection[identifier]["state"] in {"NEEDS-REVALIDATION", "SUPERSEDED"}:
                    status = "stale"
            evidence = ", ".join(entry["evidence"]) or "none"
            lines.append(f"| {entry['id']} | {entry['subject']} | {status} | {_escape_table(entry['nextAction'])} | {_escape_table(evidence)} |")
    else:
        lines.append("| none | attempt | none | none | none |")
    lines.extend(["", "## Resume", "", f"- Blocker: {resume['blocker'] or 'none'}", f"- Next action: {resume['next'] or 'none'}", f"- Evidence: {resume['evidence'] or 'none'}", "", "## Attempt History", "", "| Attempt | Lifecycle | Gate | Execution Record |", "| --- | --- | --- | --- |"])
    for row in _attempt_history(package, lifecycle):
        lines.append(f"| {row['attempt']} | {row['lifecycle']} | {row['gate']} | {row['path']} |")
    return "\n".join(lines) + "\n"


def _refresh_projections(package: Path, state: dict[str, Any]) -> dict[str, Any]:
    summary = _validate_state(package, state, projections=False)
    for document in summary["_documents"]:
        _publish_ticket(document, state["tickets"][document["id"]])
    if summary["composition"]["dag"]:
        path = _dag_path(package, summary["attempt"])
        text = _replace_projection(_read(path), "runtime-state", "Runtime State", _dag_projection(package, summary["attempt"], state["tasks"]))
        _write_text(path, text)
    _ensure_execution_record(package, summary["attempt"])
    _write_text(package / PROGRESS_PATH, _render_progress(package, state, summary))
    return summary


def _validate_projections(package: Path, state: dict[str, Any], summary: dict[str, Any]) -> None:
    for document in summary["_documents"]:
        if document["publication"] != "Approved":
            raise StateError(f"Ticket {document['id']} must be Approved while its runtime state exists")
        expected = _ticket_projection(state["tickets"][document["id"]])
        if _projection(document["text"], "runtime-acceptance") != expected:
            raise StateError(f"Ticket {document['id']} runtime projection mismatch")
    if summary["composition"]["dag"]:
        path = _dag_path(package, summary["attempt"])
        expected = _dag_projection(package, summary["attempt"], state["tasks"])
        if _projection(_read(path), "runtime-state") != expected:
            raise StateError("DAG runtime projection mismatch")
    er_path = _execution_record_path(package, summary["attempt"])
    if not er_path.is_file():
        raise StateError("current Attempt Execution Record is missing")
    metadata, entries = _parse_execution_record(er_path, summary["attempt"])
    lifecycle = summary["_lifecycle"]
    expected_metadata = {
        "attempt": lifecycle.attempt,
        "lifecycle": lifecycle.value,
        "gate": lifecycle.gate_verdict,
    }
    if metadata != expected_metadata:
        raise StateError("current Attempt Execution Record lifecycle projection mismatch")
    repo = _repo_root(package)
    for entry in entries:
        _normalize_payload(
            repo,
            state,
            {key: entry[key] for key in ("purpose", "subject", "title", "content", "nextAction", "evidence") if entry[key] is not None},
            live_evidence=lifecycle.active,
        )
    expected_progress = _render_progress(package, state, summary)
    progress_path = package / PROGRESS_PATH
    if not progress_path.is_file() or _read(progress_path) != expected_progress:
        raise StateError("progress projection mismatch; run refresh-progress")


def _public_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in summary.items() if not key.startswith("_")}


def command_init(package: Path, attempt: str, plan: str) -> dict[str, Any]:
    if PACKAGE_ID_RE.fullmatch(package.name) is None:
        raise StateError("package directory must use an immutable date-prefixed ID")
    repo = _repo_root(package)
    info = _plan_info(package, repo, plan)
    if info["attempt"] != attempt:
        raise StateError("--attempt does not match the plan Attempt ID")
    path = package / STATE_PATH
    previous_lifecycle: AttemptLifecycle | None = None
    if path.exists():
        current = _load_json(path)
        current_attempt = current.get("attempt", {}).get("id")
        if current_attempt == attempt:
            if current.get("attempt", {}).get("plan") != info["path"]:
                raise StateError("current Attempt is already bound to a different plan")
            current_summary = _validate_state(package, current, projections=False)
            current_lifecycle = current_summary["_lifecycle"]
            if current_lifecycle.frozen:
                current["resume"] = {"blocker": None, "next": None, "evidence": None}
                _write_json(path, current)
                _set_execution_record_status(
                    package,
                    current_attempt,
                    current_lifecycle.value,
                    current_lifecycle.gate_verdict,
                )
            _refresh_projections(package, current)
            return _public_summary(_validate_state(package, current))
        # A previous terminal Attempt is frozen history. Validate its bound
        # contracts and runtime state, but do not require legacy projections to
        # match before a new strict Attempt replaces the active projection.
        previous = _validate_state(package, current, projections=False)
        previous_lifecycle = previous["_lifecycle"]
        if not previous_lifecycle.frozen:
            raise StateError("current Attempt is not terminal; refusing to replace state")
    documents = _ticket_documents(package, attempt) if info["tickets"] else []
    graph = _dag_contract(package, attempt) if info["dag"] else {}
    _ticket_dependencies(documents)
    if previous_lifecycle is not None:
        _set_execution_record_status(
            package,
            previous_lifecycle.attempt,
            previous_lifecycle.value,
            previous_lifecycle.gate_verdict,
        )
    state = {
        "formatVersion": FORMAT_VERSION,
        "attempt": {"id": attempt, "plan": info["path"]},
        "tasks": {identifier: {"state": "PENDING", "evidence": None} for identifier in graph},
        "tickets": {document["id"]: {"state": "PENDING", "evidence": None} for document in documents},
        "resume": {"blocker": None, "next": None, "evidence": None},
    }
    _validate_state(package, state, projections=False)
    for document in documents:
        _publish_ticket(document, state["tickets"][document["id"]])
    _write_json(path, state)
    _ensure_execution_record(package, attempt)
    _refresh_projections(package, state)
    return _public_summary(_validate_state(package, state))


def command_validate(package: Path, commit: str | None) -> dict[str, Any]:
    repo = _repo_root(package)
    resolved_commit = _validate_commit(repo, commit) if commit else None
    path = package / STATE_PATH
    if not path.exists():
        return {"active": False, "reason": "no-active-attempt", "commit": resolved_commit}
    result = _public_summary(_validate_state(package, _load_json(path)))
    result.update({"active": True, "commit": resolved_commit})
    return result


def command_refresh_progress(package: Path) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _refresh_projections(package, state)
    return {"attempt": summary["attempt"], "progress": _package_relative(package, package / PROGRESS_PATH)}


def command_set_state(package: Path, kind: str, identifier: str, target: str, expect: str, evidence: str | None) -> dict[str, Any]:
    path = package / STATE_PATH
    state = _load_json(path)
    summary = _validate_state(package, state)
    _assert_mutable(summary["_lifecycle"])
    key = "tasks" if kind == "task" else "tickets"
    allowed = TASK_STATES if kind == "task" else TICKET_STATES
    if target not in allowed:
        raise StateError(f"invalid {kind} state: {target}")
    if identifier not in state.get(key, {}):
        raise StateError(f"unknown {kind}: {identifier}")
    repo = _repo_root(package)
    normalized = _repo_relative(repo, evidence, f"{kind} evidence") if evidence else None
    if target != "PENDING" and normalized is None:
        raise StateError(f"{kind} state {target} requires --evidence")
    current = state[key][identifier]
    if current == {"state": target, "evidence": normalized}:
        _refresh_projections(package, state)
        return {"kind": kind, "id": identifier, "state": target, "evidence": normalized, "idempotent": True}
    if current["state"] != expect:
        raise StateError(f"stale {kind} transition for {identifier}: expected {expect}, found {current['state']}")
    if kind == "task" and target in {"READY", "RUNNING"}:
        dependencies = summary["_graph"][identifier]
        if not all(state["tasks"][item]["state"] in TASK_DEPENDENCY_RELEASING for item in dependencies):
            raise StateError(f"Task {identifier} dependencies are not released")
    if kind == "ticket" and target == "SATISFIED":
        dependencies = summary["_ticketDependencies"][identifier]
        if not all(state["tickets"][item]["state"] in TICKET_DEPENDENCY_RELEASING for edge, item in dependencies if edge in {"implementation", "acceptance"}):
            raise StateError(f"Ticket {identifier} implementation or acceptance dependencies are not released")
    state[key][identifier] = {"state": target, "evidence": normalized}
    _validate_state(package, state, projections=False)
    _write_json(path, state)
    _refresh_projections(package, state)
    return {"kind": kind, "id": identifier, "state": target, "evidence": normalized, "idempotent": False}


def _add_execution_record(package: Path, payload: Any, *, resume_blocker: str | None | object = ...) -> dict[str, Any]:
    path = package / STATE_PATH
    state = _load_json(path)
    summary = _validate_state(package, state)
    _assert_mutable(summary["_lifecycle"])
    repo = _repo_root(package)
    normalized = _normalize_payload(repo, state, payload)
    attempt = state["attempt"]["id"]
    er_path = _ensure_execution_record(package, attempt)
    _, entries = _parse_execution_record(er_path, attempt)
    existing = next((entry for entry in entries if _same_payload(entry, normalized)), None)
    if existing is None:
        number = max((entry["number"] for entry in entries), default=0) + 1
        record_id = f"{attempt}-ER-{number:03d}"
        supersedes = None
        if normalized["purpose"] == "checkpoint":
            supersedes = next((entry["id"] for entry in reversed(entries) if entry["purpose"] == "checkpoint" and entry["subject"] == normalized["subject"]), None)
        _write_text(er_path, _read(er_path).rstrip() + _render_entry(record_id, normalized, supersedes))
        idempotent = False
    else:
        record_id = existing["id"]
        idempotent = True
    if normalized["purpose"] == "checkpoint":
        blocker = state["resume"]["blocker"] if resume_blocker is ... else resume_blocker
        state["resume"] = {
            "blocker": blocker,
            "next": normalized["nextAction"],
            "evidence": normalized["evidence"][0] if normalized["evidence"] else None,
        }
        _write_json(path, state)
    _refresh_projections(package, state)
    return {"recordId": record_id, "attempt": attempt, "idempotent": idempotent}


def command_er_add(package: Path, input_text: str) -> dict[str, Any]:
    try:
        payload = json.loads(input_text)
    except json.JSONDecodeError as exc:
        raise StateError(f"er-add input is invalid JSON: {exc}") from exc
    return _add_execution_record(package, payload)


def command_checkpoint(package: Path, next_action: str, blocker: str | None, evidence: str | None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "purpose": "checkpoint",
        "subject": "attempt",
        "title": "Resume checkpoint",
        "content": blocker.strip() if blocker else "No active blocker.",
        "nextAction": next_action,
    }
    if evidence:
        payload["evidence"] = evidence
    result = _add_execution_record(package, payload, resume_blocker=blocker.strip() if blocker else None)
    state = _load_json(package / STATE_PATH)
    result["resume"] = state["resume"]
    return result


def command_gate(
    package: Path,
    verdict: str,
    commit: str,
    reason: str,
    evidence: list[str],
    durable: list[str],
    no_durable_reason: str | None,
) -> dict[str, Any]:
    state = _load_json(package / STATE_PATH)
    summary = _validate_state(package, state, projections=False)
    repo = _repo_root(package)
    resolved_commit = _validate_commit(repo, commit)
    current_lifecycle = summary["_lifecycle"]
    existing = current_lifecycle.gate
    if current_lifecycle.frozen:
        assert existing is not None
        if existing["verdict"] == verdict and existing["commit"] == resolved_commit:
            state["resume"] = {"blocker": None, "next": None, "evidence": None}
            _write_json(package / STATE_PATH, state)
            _set_execution_record_status(
                package,
                summary["attempt"],
                current_lifecycle.value,
                current_lifecycle.gate_verdict,
            )
            _refresh_projections(package, state)
            return {"formatVersion": FORMAT_VERSION, "verdict": verdict, "attempt": summary["attempt"], "commit": resolved_commit, "idempotent": True}
        raise StateError(f"Attempt {summary['attempt']} is already frozen by terminal Gate {existing['verdict']}")
    _validate_projections(package, state, summary)
    next_lifecycle = AttemptLifecycle.derive(
        summary["attempt"],
        {"attempt": summary["attempt"], "verdict": verdict, "commit": resolved_commit},
    )
    if next_lifecycle.frozen:
        head = _run_git(repo, "rev-parse", "--verify", "HEAD^{commit}")
        if resolved_commit != head:
            raise StateError(f"terminal Gate comparison commit must equal current HEAD {head}")
    if next_lifecycle.frozen and not durable and not (no_durable_reason and no_durable_reason.strip()):
        raise StateError("terminal Gate requires --durable-delta or --no-durable-delta-reason")
    if verdict == "pass":
        unfinished_tasks = [identifier for identifier, row in state["tasks"].items() if row["state"] not in TASK_DEPENDENCY_RELEASING]
        unfinished_tickets = [identifier for identifier, row in state["tickets"].items() if row["state"] not in TICKET_DEPENDENCY_RELEASING]
        if unfinished_tasks or unfinished_tickets:
            raise StateError(f"pass Gate has unfinished Tasks/Tickets: {', '.join(unfinished_tasks + unfinished_tickets)}")
    evidence_paths = [_repo_relative(repo, item, "gate evidence") for item in evidence]
    findings = package / "execution-findings.md"
    if next_lifecycle.frozen and findings.is_file():
        findings_rel = _repo_relative(repo, _package_relative(repo, findings), "execution findings")
        if not any(item.split("#", 1)[0] == findings_rel for item in evidence_paths):
            raise StateError("terminal Gate must route existing execution-findings.md through --evidence")
    revisions = summary["revisions"]
    lines = [
        "# Gate\n",
        f"- Verdict: {verdict}\n",
        f"- Attempt: {summary['attempt']}\n",
        f"- Contract aliases: {_format_aliases(revisions)}\n",
        f"- Comparison commit: {resolved_commit}\n",
        f"- Reason: {reason.strip()}\n",
        "\n## Evidence\n",
    ]
    lines.extend(f"- {item}\n" for item in evidence_paths)
    if not evidence_paths:
        lines.append("- none\n")
    lines.append("\n## Durable Deltas\n")
    lines.extend(f"- {item}\n" for item in durable)
    if not durable:
        lines.extend(["- none\n", f"- Reason: {no_durable_reason.strip() if no_durable_reason else 'not evaluated for blocked Gate'}\n"])
    _write_text(package / GATE_PATH, "".join(lines))
    if next_lifecycle.frozen:
        state["resume"] = {"blocker": None, "next": None, "evidence": None}
        _write_json(package / STATE_PATH, state)
    _set_execution_record_status(
        package,
        summary["attempt"],
        next_lifecycle.value,
        next_lifecycle.gate_verdict,
    )
    _refresh_projections(package, state)
    return {"formatVersion": FORMAT_VERSION, "verdict": verdict, "attempt": summary["attempt"], "commit": resolved_commit, "idempotent": False}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init")
    init.add_argument("--attempt", required=True)
    init.add_argument("--plan", required=True)
    for name in ("status", "validate"):
        child = commands.add_parser(name)
        child.add_argument("--commit")
    commands.add_parser("refresh-progress")
    commands.add_parser("er-add")
    state = commands.add_parser("set-state")
    state.add_argument("kind", choices=("task", "ticket"))
    state.add_argument("id")
    state.add_argument("state")
    state.add_argument("--expect", required=True)
    state.add_argument("--evidence")
    checkpoint = commands.add_parser("checkpoint")
    checkpoint.add_argument("--next", required=True)
    checkpoint.add_argument("--blocker")
    checkpoint.add_argument("--evidence")
    gate = commands.add_parser("gate")
    gate.add_argument("verdict", choices=sorted(VERDICTS))
    gate.add_argument("--comparison-commit", required=True)
    gate.add_argument("--reason", required=True)
    gate.add_argument("--evidence", action="append", default=[])
    gate.add_argument("--durable-delta", action="append", default=[])
    gate.add_argument("--no-durable-delta-reason")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    package = args.package.resolve()
    try:
        if args.command == "init":
            result = command_init(package, args.attempt, args.plan)
        elif args.command in {"status", "validate"}:
            result = command_validate(package, args.commit)
        elif args.command == "refresh-progress":
            result = command_refresh_progress(package)
        elif args.command == "set-state":
            result = command_set_state(package, args.kind, args.id, args.state, args.expect, args.evidence)
        elif args.command == "checkpoint":
            result = command_checkpoint(package, args.next, args.blocker, args.evidence)
        elif args.command == "er-add":
            result = command_er_add(package, sys.stdin.read())
        else:
            result = command_gate(
                package,
                args.verdict,
                args.comparison_commit,
                args.reason,
                args.evidence,
                args.durable_delta,
                args.no_durable_delta_reason,
            )
    except (StateError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
