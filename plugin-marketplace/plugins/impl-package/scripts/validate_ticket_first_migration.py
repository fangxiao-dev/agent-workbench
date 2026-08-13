"""Read-only validator for a one-time 3.4 -> 3.5 package migration.

The validator deliberately does not copy, move, commit, or edit a package.
The package session owns staging and the single switch commit; this tool only
decides whether the staged candidate satisfies the migration contract.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TIMINGS = {"early-falsification", "remaining-completion"}
CONCLUSIONS = {"supporting", "contradictory", "inconclusive"}
TICKET_STATES = {"PENDING", "BLOCKED", "NEEDS-REVALIDATION", "SATISFIED", "RETIRED"}
DISPOSITIONS = {"waived", "superseded"}
COMMIT_RE = re.compile(r"[0-9a-fA-F]{7,64}")
EDGE_RE = re.compile(r"-\s*(implementation|acceptance|release)\s*:\s*([^\s]+)")
ATTEMPT_ID_RE = re.compile(r"(?:initial|[A-Za-z0-9][A-Za-z0-9_-]{0,79})")
ATTEMPT_RE = re.compile(r"(?m)^(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:](?:\*\*)?\s*([^\s*]+)")
PUBLICATION_RE = re.compile(r"(?m)^\*\*(?:Publication Status|发布状态（Publication Status）)[：:]\*\*\s*(Draft|Approved)\s*$")
ER_ENTRY_RE = re.compile(r"(?m)^## ([^\s]+-ER-(\d{3})) · (checkpoint|judgment)\s*$")
TICKET_ID_RE = re.compile(r"(?m)^\s*\*\*Ticket ID[：:]\*\*\s*([^\s]+)")
DECISION_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Decision Revision|决策修订（Decision Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(D\d+)\b")
SPEC_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Spec Revision|规格修订（Spec Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(S\d+)\b")
PLAN_RE = re.compile(r"(?m)^\s*(?:\*\*)?(?:Plan Revision|计划修订（Plan Revision）)(?:\*\*)?\s*[：:](?:\*\*)?\s*(P\d+)\b")
RUNTIME_ACCEPTANCE_MARKER = "impl-package:projection runtime-acceptance"


class MigrationError(RuntimeError):
    pass


def _json(path: Path) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MigrationError(f"cannot read JSON: {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MigrationError(f"JSON root must be an object: {path}")
    return value


def _relative_artifact(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MigrationError("evidence artifact must be non-empty")
    raw = value.replace("\\", "/").split("#", 1)[0]
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw) or ".." in Path(raw).parts:
        raise MigrationError(f"evidence artifact must be repository-relative: {value}")
    return raw


def _artifact(repo: Path, value: str, field: str) -> str:
    """Validate a repository-relative artifact and its optional text anchor."""
    if not isinstance(value, str) or not value.strip():
        raise MigrationError(f"{field} must be a non-empty repository-relative path")
    raw = value.strip().replace("\\", "/")
    path = _relative_artifact(raw)
    resolved = (repo / Path(*path.split("/"))).resolve()
    try:
        resolved.relative_to(repo.resolve())
    except ValueError as exc:
        raise MigrationError(f"{field} resolves outside the repository: {value}") from exc
    if not resolved.is_file():
        raise MigrationError(f"{field} does not exist: {path}")
    if "#" in raw:
        anchor = raw.split("#", 1)[1].strip()
        if not anchor:
            raise MigrationError(f"{field} has an empty anchor: {value}")
        if anchor.lower() not in resolved.read_text(encoding="utf-8").lower():
            raise MigrationError(f"{field} anchor is not present: {value}")
    return path


def _commit(repo: Path, value: str, field: str) -> str:
    if not isinstance(value, str) or COMMIT_RE.fullmatch(value) is None:
        raise MigrationError(f"{field} must be a Git commit ID")
    result = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--verify", f"{value}^{{commit}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise MigrationError(f"{field} is not a resolvable Git commit: {value}")
    return result.stdout.strip()


def _entry_field(block: str, name: str, *, optional: bool = False) -> str | None:
    match = re.search(rf"(?m)^- {re.escape(name)}:[ \t]*(.*?)[ \t]*$", block)
    if match:
        return match.group(1)
    if optional:
        return None
    raise MigrationError(f"Execution Record entry is missing {name}")


def _parse_execution_record_text(text: str, path: str, expected_attempt: str | None = None) -> tuple[dict[str, str], list[dict]]:
    """Parse the machine-readable ER shape emitted by the 3.5 runtime.

    This intentionally checks only facts that can be proved from the candidate
    itself.  Source-baseline parsing uses the same parser and turns failures
    into warnings rather than making migration depend on an old ER format.
    """
    heading = re.search(r"(?m)^# Execution Record · ([^\s]+)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    lifecycle = re.search(r"(?m)^- Lifecycle:\s*(active|frozen)\s*$", text)
    gate = re.search(r"(?m)^- Gate:\s*(open|pass|fail|blocked|defer)\s*$", text)
    if not heading or not attempt or not lifecycle or not gate:
        raise MigrationError(f"invalid Execution Record header: {path}")
    if heading.group(1) != attempt.group(1) or (expected_attempt and attempt.group(1) != expected_attempt):
        raise MigrationError(f"Execution Record Attempt mismatch: {path}")

    matches = list(ER_ENTRY_RE.finditer(text))
    entries: list[dict] = []
    previous = 0
    seen: set[str] = set()
    for index, match in enumerate(matches):
        record_id, number, purpose = match.group(1), int(match.group(2)), match.group(3)
        if not record_id.startswith(attempt.group(1) + "-ER-") or record_id in seen or number != previous + 1:
            raise MigrationError(f"invalid Execution Record ID sequence: {record_id}")
        seen.add(record_id)
        previous = number
        block = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
        sections = re.search(r"(?ms)^### Evidence\s*$\n(.*?)^### Content\s*$\n(.*)\Z", block.strip())
        if sections is None:
            raise MigrationError(f"Execution Record {record_id} is missing Evidence or Content")
        subject = _entry_field(block, "Subject")
        title = _entry_field(block, "Title")
        if not subject or not subject.strip():
            raise MigrationError(f"Execution Record {record_id} has an empty Subject")
        if not title or not title.strip() or "\n" in title:
            raise MigrationError(f"Execution Record {record_id} has an empty or multi-line Title")

        evidence_block = sections.group(1).strip()
        if not evidence_block:
            raise MigrationError(f"Execution Record {record_id} has an empty Evidence section")
        evidence_lines = evidence_block.splitlines()
        if evidence_lines == ["- none"]:
            evidence: list[str] = []
        else:
            evidence = []
            for line in evidence_lines:
                if not line.startswith("- ") or not line[2:].strip():
                    raise MigrationError(f"Execution Record {record_id} has invalid Evidence")
                evidence.append(line[2:].strip())
        content = sections.group(2).strip()
        if purpose == "judgment" and not content:
            raise MigrationError(f"Execution Record {record_id} judgment Content must be non-empty")
        entries.append(
            {
                "id": record_id,
                "number": number,
                "purpose": purpose,
                "subject": subject.strip(),
                "title": title.strip(),
                "evidence": evidence,
                "content": content,
            }
        )
    return {"attempt": attempt.group(1), "lifecycle": lifecycle.group(1), "gate": gate.group(1)}, entries


def _parse_execution_record(path: Path, expected_attempt: str | None = None) -> tuple[dict[str, str], list[dict]]:
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MigrationError(f"cannot read Execution Record: {path}: {exc}") from exc
    return _parse_execution_record_text(str(text), str(path), expected_attempt)


def _normalize_er_value(value: object) -> object:
    """Normalize line endings and insignificant edge whitespace for comparison."""
    if isinstance(value, list):
        return tuple(_normalize_er_value(item) for item in value)
    return "\n".join(line.rstrip() for line in str(value).replace("\r\n", "\n").replace("\r", "\n").splitlines()).strip()


def _history(repo: Path, package: Path, value: object, attempt: dict) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise MigrationError("candidate must retain lightweight attempt history")
    result: list[dict] = []
    seen_ids: set[str] = set()
    for row in value:
        required = {"id", "plan", "lifecycle", "gate", "executionRecord"}
        if not isinstance(row, dict) or set(row) != required:
            raise MigrationError("attemptHistory rows must contain id, plan, lifecycle, gate, executionRecord")
        if not isinstance(row["id"], str) or ATTEMPT_ID_RE.fullmatch(row["id"]) is None:
            raise MigrationError("attemptHistory id must be a valid Attempt ID")
        if row["id"] in seen_ids:
            raise MigrationError(f"attemptHistory contains duplicate Attempt ID: {row['id']}")
        seen_ids.add(row["id"])
        if row["lifecycle"] not in {"active", "frozen"}:
            raise MigrationError(f"invalid attemptHistory lifecycle: {row['lifecycle']!r}")
        plan = _artifact(repo, row["plan"], "attemptHistory plan")
        if isinstance(row["executionRecord"], str) and "#" in row["executionRecord"]:
            raise MigrationError("attemptHistory executionRecord may not contain a text anchor")
        execution_record = _artifact(package, row["executionRecord"], "attemptHistory executionRecord")
        expected_execution_record = f"execution/{row['id']}/execution-record.md"
        if "#" in execution_record or execution_record != expected_execution_record:
            raise MigrationError(
                f"attemptHistory executionRecord must bind {expected_execution_record}"
            )
        gate = row["gate"]
        if gate is not None:
            if not isinstance(gate, dict) or set(gate) - {"verdict", "commit", "environment"} or not {"verdict", "commit"} <= set(gate):
                raise MigrationError("attemptHistory gate must be null or contain verdict and commit")
            if gate["verdict"] not in {"pass", "fail", "defer", "blocked"}:
                raise MigrationError(f"invalid attemptHistory gate verdict: {gate['verdict']!r}")
            gate = dict(gate)
            gate["commit"] = _commit(repo, gate["commit"], "attemptHistory gate commit")
            if gate.get("environment") is not None and (not isinstance(gate["environment"], str) or not gate["environment"].strip()):
                raise MigrationError("attemptHistory gate environment must be non-empty or null")
        result.append({**row, "plan": plan, "executionRecord": execution_record, "gate": gate})
    if result[-1]["id"] != attempt.get("id") or result[-1]["plan"] != attempt.get("plan"):
        raise MigrationError("attemptHistory must end with the current Attempt")
    return result


def _progress_escape(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def _progress_aliases(plan_text: str) -> str:
    revisions = [pattern.search(plan_text) for pattern in (DECISION_RE, SPEC_RE, PLAN_RE)]
    values = [match.group(1) for match in revisions if match]
    return " / ".join(values) if values else "none (Git commit is the history anchor)"


def _progress_projection(plan_text: str, state: dict, history: list[dict], attempt: str) -> str:
    """Render the machine-owned progress projection used by runtime 3.5.

    This is deliberately kept as a small mechanical equivalent of the runtime
    renderer rather than importing a mutating CLI module during migration.
    """
    current = history[-1]
    lifecycle = current["lifecycle"]
    gate = current["gate"].get("verdict", "open") if isinstance(current["gate"], dict) else "open"
    blockers = [f"ticket:{key}" for key, row in state["tickets"].items() if row["state"] == "BLOCKED"]
    lines = [
        f"# Attempt Progress · {attempt}",
        "",
        "> machine-owned projection；使用 `refresh-progress` 重建，不直接编辑。",
        "",
        f"- Attempt: {attempt}",
        f"- Contract aliases: {_progress_aliases(plan_text)}",
        "- Composition: tickets=true, dag=false",
        f"- Lifecycle: {lifecycle}",
        f"- Latest gate: {gate}",
        f"- Blockers: {', '.join(blockers) if blockers else 'none'}",
        "",
        "## Ticket Acceptance",
        "",
        "| Ticket | State | Evidence |",
        "| --- | --- | --- |",
    ]
    for identifier, row in state["tickets"].items():
        claims = ", ".join(sorted(state["evidenceIndex"].get(identifier, {}))) or "none"
        lines.append(f"| {identifier} | {row['state']} | {_progress_escape(claims)} |")
    lines.extend([
        "",
        "## Active Checkpoints",
        "",
        "| Subject | Status | Next action | Evidence |",
        "| --- | --- | --- | --- |",
    ])
    checkpoints = state["activeCheckpoints"] if lifecycle != "frozen" else {}
    if checkpoints:
        for subject, row in checkpoints.items():
            lines.append(
                f"| {subject} | active | {_progress_escape(row['next'])} | "
                f"{_progress_escape(', '.join(row['evidence']) or 'none')} |"
            )
    else:
        lines.append("| none | none | none | none |")
    lines.extend([
        "",
        "## Attempt History",
        "",
        "| Attempt | Lifecycle | Gate | Execution Record |",
        "| --- | --- | --- | --- |",
    ])
    for row in history:
        row_gate = row["gate"].get("verdict", "open") if isinstance(row["gate"], dict) else "open"
        lines.append(f"| {row['id']} | {row['lifecycle']} | {row_gate} | {row['executionRecord']} |")
    return "\n".join(lines) + "\n"


def _validate_progress(package: Path, plan_text: str, state: dict, history: list[dict], attempt: str) -> None:
    path = package / "progress.md"
    if not path.is_file():
        raise MigrationError("candidate progress.md is required")
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise MigrationError(f"cannot read candidate progress.md: {exc}") from exc
    expected = _progress_projection(plan_text, state, history, attempt)
    if actual != expected:
        raise MigrationError("candidate progress.md projection mismatch; run refresh-progress")


def _runtime_validate(package: Path) -> None:
    """Run the exact 3.5 runtime validator without invoking any writer path."""
    scripts_dir = str(Path(__file__).resolve().parent)
    if scripts_dir not in sys.path:
        sys.path.insert(0, scripts_dir)
    try:
        from impl_package_runtime import engine
    except (ImportError, OSError) as exc:
        raise MigrationError(f"cannot load 3.5 runtime validator: {exc}") from exc
    try:
        engine.command_validate(package, None)
    except engine.StateError as exc:
        raise MigrationError(f"3.5 runtime validate rejected candidate: {exc}") from exc
    except OSError as exc:
        raise MigrationError(f"3.5 runtime validate could not read candidate: {exc}") from exc


def _warning(code: str, message: str, *, attempt: str, path: str, **details: object) -> dict:
    return {"code": code, "message": message, "attempt": attempt, "path": path, **details}


def _execution_records(repo: Path, package: Path, history: list[dict], pre_anchor: str | None) -> list[dict]:
    """Validate candidate ERs and optionally compare them with the anchor tree.

    Candidate errors are admission failures.  A source ER that is absent or in
    an older/unreadable format is retained as a structured warning because a
    migration must not pretend it can prove historical content it cannot read.
    """
    parsed: dict[str, tuple[dict[str, str], list[dict]]] = {}
    warnings: list[dict] = []
    for row in history:
        path = package / Path(*row["executionRecord"].split("/"))
        metadata, entries = _parse_execution_record(path, row["id"])
        expected_gate = "open" if row["gate"] is None else row["gate"]["verdict"]
        expected = {"attempt": row["id"], "lifecycle": row["lifecycle"], "gate": expected_gate}
        if metadata != expected:
            raise MigrationError(
                f"Execution Record header does not match attemptHistory row {row['id']}"
            )
        parsed[row["id"]] = (metadata, entries)

    if pre_anchor is None:
        return warnings

    for row in history:
        candidate_path = package / Path(*row["executionRecord"].split("/"))
        try:
            source_path = candidate_path.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            # _history already proves this cannot happen; keep the warning
            # contract defensive if path handling changes in the future.
            warnings.append(_warning(
                "source-execution-record-unavailable",
                "pre-anchor Execution Record is outside the repository",
                attempt=row["id"],
                path=row["executionRecord"],
            ))
            continue
        source = subprocess.run(
            ["git", "-C", str(repo), "show", f"{pre_anchor}:{source_path}"],
            capture_output=True,
            text=False,
            check=False,
        )
        if source.returncode:
            warnings.append(_warning(
                "source-execution-record-unavailable",
                "pre-anchor Execution Record could not be read",
                attempt=row["id"],
                path=row["executionRecord"],
                sourceRevision=pre_anchor,
            ))
            continue
        try:
            source_text = source.stdout.decode("utf-8")
            source_metadata, source_entries = _parse_execution_record_text(
                source_text, f"{pre_anchor}:{source_path}", row["id"]
            )
        except (MigrationError, OSError, UnicodeDecodeError) as exc:
            warnings.append(_warning(
                "source-execution-record-unparseable",
                "pre-anchor Execution Record uses an unreadable or legacy format",
                attempt=row["id"],
                path=row["executionRecord"],
                sourceRevision=pre_anchor,
                detail=str(exc),
            ))
            continue

        candidate_metadata, candidate_entries = parsed[row["id"]]
        if source_metadata != candidate_metadata:
            warnings.append(_warning(
                "source-execution-record-header-diff",
                "candidate Execution Record header differs from the pre-anchor header",
                attempt=row["id"],
                path=row["executionRecord"],
                sourceRevision=pre_anchor,
            ))
        source_judgments = {
            entry["id"]: entry for entry in source_entries if entry["purpose"] == "judgment"
        }
        candidate_judgments = {
            entry["id"]: entry for entry in candidate_entries if entry["purpose"] == "judgment"
        }
        missing_ids = sorted(set(source_judgments) - set(candidate_judgments))
        extra_ids = sorted(set(candidate_judgments) - set(source_judgments))
        if missing_ids or extra_ids:
            raise MigrationError(
                f"candidate judgment IDs differ from pre-anchor for {row['id']}: "
                f"missing={missing_ids or []}, extra={extra_ids or []}"
            )
        comparable = ("purpose", "subject", "title", "evidence", "content")
        for record_id, source_entry in source_judgments.items():
            candidate_entry = candidate_judgments[record_id]
            changed = [
                field
                for field in comparable
                if _normalize_er_value(source_entry.get(field))
                != _normalize_er_value(candidate_entry.get(field))
            ]
            if changed:
                raise MigrationError(
                    f"candidate judgment {record_id} content differs from pre-anchor "
                    f"for {row['id']}: fields={changed}"
                )
    return warnings


def _repo_root(package: Path) -> Path:
    result = subprocess.run(["git", "-C", str(package), "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=False)
    if result.returncode:
        raise MigrationError("package is not inside a Git worktree")
    return Path(result.stdout.strip()).resolve()


def _walk(root: Path):
    if not root.is_dir():
        return
    for child in root.iterdir():
        yield child
        if child.is_dir():
            yield from _walk(child)


def _ticket_claims(package: Path, attempt: str) -> dict[str, set[str]]:
    claims: dict[str, set[str]] = {}
    ticket_dir = package / "tickets"
    paths = sorted((child for child in ticket_dir.iterdir() if child.is_file() and child.suffix.lower() == ".md"), key=lambda child: child.name) if ticket_dir.is_dir() else []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        identifier = TICKET_ID_RE.search(text)
        ticket_attempt = ATTEMPT_RE.search(text)
        if identifier and ticket_attempt and ticket_attempt.group(1) == attempt:
            if RUNTIME_ACCEPTANCE_MARKER in text:
                raise MigrationError(f"Ticket {identifier.group(1)} contains retired Runtime Acceptance projection")
            publication = PUBLICATION_RE.search(text)
            if publication is None:
                raise MigrationError(f"missing Publication Status in {path.name}")
            if publication.group(1) != "Approved":
                raise MigrationError(f"Ticket {identifier.group(1)} must be Approved")
            if identifier.group(1) in claims:
                raise MigrationError(f"duplicate Ticket ID for Attempt {attempt}: {identifier.group(1)}")
            claim_ids = set(re.findall(r"Stable claim ID：\s*`([^`]+)`", text))
            if not claim_ids:
                raise MigrationError(f"Ticket {identifier.group(1)} has no stable claim IDs")
            claims[identifier.group(1)] = claim_ids
    return claims


def _ticket_claim_timings(package: Path, attempt: str) -> dict[str, dict[str, str]]:
    timings: dict[str, dict[str, str]] = {}
    ticket_dir = package / "tickets"
    paths = sorted((child for child in ticket_dir.iterdir() if child.is_file() and child.suffix.lower() == ".md"), key=lambda child: child.name) if ticket_dir.is_dir() else []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        identifier = TICKET_ID_RE.search(text)
        ticket_attempt = ATTEMPT_RE.search(text)
        if not identifier or not ticket_attempt or ticket_attempt.group(1) != attempt:
            continue
        matches = list(re.finditer(r"Stable claim ID：\s*`([^`]+)`", text))
        mapped: dict[str, str] = {}
        for index, match in enumerate(matches):
            segment = text[match.end(): matches[index + 1].start() if index + 1 < len(matches) else len(text)]
            timing_values = [match.group(1) for line in segment.splitlines() if re.match(r"^\s*-\s*证据时机：", line) for match in [re.search(r"证据时机：\s*`([^`]+)`", line)] if match]
            if not timing_values:
                heading_start = text.rfind("## ", 0, match.start())
                heading_end = text.find("\n", heading_start)
                heading = text[heading_start:heading_end if heading_end >= 0 else len(text)]
                if "安全不变量" in heading:
                    value = "early-falsification"
                else:
                    raise MigrationError(f"Ticket {identifier.group(1)} claim {match.group(1)} has no evidence timing")
            else:
                if len(set(timing_values)) != 1:
                    raise MigrationError(f"Ticket {identifier.group(1)} claim {match.group(1)} has conflicting evidence timing")
                value = timing_values[0]
            if value not in TIMINGS:
                raise MigrationError(f"Ticket {identifier.group(1)} has invalid evidence timing")
            if match.group(1) in mapped and mapped[match.group(1)] != value:
                raise MigrationError(f"Ticket {identifier.group(1)} claim {match.group(1)} has conflicting evidence timing")
            mapped[match.group(1)] = value
        timings[identifier.group(1)] = mapped
    return timings


def _ticket_dependencies(package: Path, attempt: str, ticket_ids: set[str]) -> dict[str, list[tuple[str, str]]]:
    dependencies: dict[str, list[tuple[str, str]]] = {}
    ticket_dir = package / "tickets"
    paths = sorted((child for child in ticket_dir.iterdir() if child.is_file() and child.suffix.lower() == ".md"), key=lambda child: child.name) if ticket_dir.is_dir() else []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        identifier = TICKET_ID_RE.search(text)
        ticket_attempt = re.search(r"(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:]\s*(?:\*\*)?\s*([^\s*]+)", text)
        if not identifier or not ticket_attempt or ticket_attempt.group(1) != attempt:
            continue
        section = re.search(r"(?ms)^## 阻塞依赖\s*$\n(.*?)(?=^## |\Z)", text)
        values: list[tuple[str, str]] = []
        if section:
            for line in section.group(1).splitlines():
                stripped = line.strip()
                if not stripped.startswith("-") or stripped.lower() in {"- none", "- 无"}:
                    continue
                match = EDGE_RE.fullmatch(stripped)
                if match is None or match.group(2) not in ticket_ids:
                    raise MigrationError(f"invalid dependency in {identifier.group(1)}: {stripped}")
                values.append((match.group(1), match.group(2)))
        dependencies[identifier.group(1)] = values
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(ticket: str) -> None:
        if ticket in visiting:
            raise MigrationError(f"Ticket dependency graph contains a cycle at {ticket}")
        if ticket in visited:
            return
        visiting.add(ticket)
        for _, dependency in dependencies.get(ticket, []):
            visit(dependency)
        visiting.remove(ticket)
        visited.add(ticket)

    for ticket in dependencies:
        visit(ticket)
    return dependencies


def _ticket_released(tickets: dict[str, dict], identifier: str, visiting: set[str] | None = None) -> bool:
    visiting = set() if visiting is None else visiting
    if identifier in visiting or identifier not in tickets:
        return False
    visiting.add(identifier)
    row = tickets[identifier]
    if row["state"] == "SATISFIED":
        return True
    if row["state"] != "RETIRED":
        return False
    if row.get("disposition") == "waived":
        return True
    successor = row.get("successor")
    return isinstance(successor, str) and _ticket_released(tickets, successor, visiting)


def validate_migration(package: Path, *, pre_anchor: str | None = None) -> dict:
    state_path = package / ".impl-package" / "state.json"
    repo = _repo_root(package)
    if not (package / "spec.md").is_file():
        raise MigrationError("spec.md is required for an active Attempt")
    legacy = _json(package / "migration" / "legacy-state.json") if (package / "migration" / "legacy-state.json").is_file() else None
    candidate = _json(state_path)
    if legacy is not None and legacy.get("formatVersion") != "3.4":
        raise MigrationError("legacy input must be formatVersion 3.4")
    if candidate.get("formatVersion") != "3.5":
        raise MigrationError("candidate must be formatVersion 3.5")
    expected = {"formatVersion", "attempt", "attemptHistory", "tickets", "evidenceIndex", "activeCheckpoints"}
    if set(candidate) != expected:
        raise MigrationError("candidate has unexpected state fields; tasks/resume are not allowed")
    attempt = candidate.get("attempt")
    if (
        not isinstance(attempt, dict)
        or set(attempt) != {"id", "plan"}
        or not isinstance(attempt["id"], str)
        or ATTEMPT_ID_RE.fullmatch(attempt["id"]) is None
        or not isinstance(attempt["plan"], str)
    ):
        raise MigrationError("candidate attempt must contain id and plan")
    plan_rel = _artifact(repo, attempt["plan"], "candidate plan")
    plan = repo / Path(*plan_rel.split("#", 1)[0].split("/"))
    try:
        plan.resolve().relative_to(package.resolve())
    except ValueError as exc:
        raise MigrationError("candidate plan must be inside the package") from exc
    plan_text = plan.read_text(encoding="utf-8")
    if not re.search(r"Composition[^\n]*tickets=true,\s*dag=false", plan_text, re.I):
        raise MigrationError("candidate plan must declare tickets=true, dag=false")
    plan_attempt = ATTEMPT_RE.search(plan_text)
    if plan_attempt is None or plan_attempt.group(1) != attempt["id"]:
        raise MigrationError("candidate Attempt ID does not match the current plan")
    if not isinstance(candidate["tickets"], dict) or not candidate["tickets"]:
        raise MigrationError("candidate must retain Ticket records")
    ticket_claims = _ticket_claims(package, attempt["id"])
    claim_timings = _ticket_claim_timings(package, attempt["id"])
    if set(ticket_claims) != set(candidate["tickets"]):
        raise MigrationError("candidate Ticket state does not match current Ticket documents")
    for ticket, row in candidate["tickets"].items():
        if not isinstance(row, dict) or row.get("state") not in TICKET_STATES:
            raise MigrationError(f"invalid Ticket state record: {ticket}")
        state = row["state"]
        if state == "PENDING" and set(row) != {"state"}:
            raise MigrationError(f"PENDING Ticket {ticket} may not carry legacy evidence fields")
        if state == "SATISFIED":
            if set(row) != {"state", "acceptance"} or not isinstance(row["acceptance"], dict) or set(row["acceptance"]) != {"revision", "environment"}:
                raise MigrationError(f"SATISFIED Ticket {ticket} requires acceptance revision/environment")
            _commit(repo, row["acceptance"]["revision"], f"Ticket {ticket} acceptance revision")
            if not isinstance(row["acceptance"]["environment"], str) or not row["acceptance"]["environment"].strip():
                raise MigrationError(f"Ticket {ticket} acceptance environment must be non-empty")
        elif state == "BLOCKED":
            if set(row) != {"state", "evidence"}:
                raise MigrationError(f"BLOCKED Ticket {ticket} requires evidence")
            _artifact(repo, row["evidence"], f"BLOCKED {ticket} evidence")
        elif state == "NEEDS-REVALIDATION":
            if set(row) not in ({"state"}, {"state", "evidence"}):
                raise MigrationError(f"invalid NEEDS-REVALIDATION Ticket: {ticket}")
            if "evidence" in row:
                _artifact(repo, row["evidence"], f"revalidation {ticket} evidence")
        elif state == "RETIRED":
            allowed_retired = {"state", "disposition", "evidence"} | ({"successor"} if row.get("disposition") == "superseded" else set())
            if set(row) != allowed_retired:
                raise MigrationError(f"RETIRED Ticket {ticket} requires disposition and evidence")
            if row["disposition"] not in DISPOSITIONS:
                raise MigrationError(f"invalid RETIRED disposition for {ticket}")
            _artifact(repo, row["evidence"], f"RETIRED {ticket} evidence")
            if row["disposition"] == "superseded" and (not isinstance(row.get("successor"), str) or row["successor"] not in candidate["tickets"] or row["successor"] == ticket):
                raise MigrationError(f"RETIRED superseded Ticket {ticket} requires a valid successor")
    normalized_anchor = _commit(repo, pre_anchor, "pre-migration anchor") if pre_anchor is not None else None
    history = _history(repo, package, candidate["attemptHistory"], attempt)
    warnings = _execution_records(repo, package, history, normalized_anchor)
    if any(row["id"] == attempt["id"] and row["lifecycle"] != "active" for row in history[:-1]):
        raise MigrationError("current Attempt may not appear as a frozen historical row")
    dependencies = _ticket_dependencies(package, attempt["id"], set(candidate["tickets"]))
    for ticket, edges in dependencies.items():
        row = candidate["tickets"][ticket]
        if row["state"] == "SATISFIED" and any(kind in {"implementation", "acceptance"} and not _ticket_released(candidate["tickets"], dependency) for kind, dependency in edges):
            raise MigrationError(f"SATISFIED Ticket {ticket} has an unreleased implementation/acceptance dependency")
    for retired_ticket, row in candidate["tickets"].items():
        if row["state"] == "RETIRED" and row.get("disposition") == "superseded":
            inbound = [(ticket, kind) for ticket, edges in dependencies.items() for kind, dependency in edges if dependency == retired_ticket]
            if inbound:
                raise MigrationError(f"superseded Ticket {retired_ticket} still has inbound edges: {inbound}")
    archive = package / "migration" / "archive" / "task-handoffs"
    if any("task-handoffs" in str(item).replace("\\", "/") for item in _walk(package / "execution")):
        raise MigrationError("active execution tree still contains task-handoffs")
    index = candidate["evidenceIndex"]
    if not isinstance(index, dict):
        raise MigrationError("candidate evidenceIndex must be nested by Ticket/claim")
    records = []
    evidence_by_ticket: dict[str, dict[str, list[dict]]] = {}
    for ticket, claim_map in index.items():
        if ticket not in candidate["tickets"] or not isinstance(claim_map, dict):
            raise MigrationError(f"invalid evidenceIndex Ticket: {ticket}")
        if set(claim_map) - ticket_claims.get(ticket, set()):
            raise MigrationError(f"evidenceIndex has unknown claim for {ticket}")
        for claim, values in claim_map.items():
            if not isinstance(values, list):
                raise MigrationError(f"evidenceIndex[{ticket}][{claim}] must be a list")
            for record in values:
                required = {"timing", "artifact", "revision", "environment", "conclusion"}
                if not isinstance(record, dict) or not required <= set(record):
                    raise MigrationError(f"incomplete evidence record: {ticket}/{claim}")
                if record["timing"] not in TIMINGS or record["conclusion"] not in CONCLUSIONS:
                    raise MigrationError(f"invalid evidence timing/conclusion: {ticket}/{claim}")
                if claim_timings.get(ticket, {}).get(claim) != record["timing"]:
                    raise MigrationError(f"evidence timing does not match Ticket claim: {ticket}/{claim}")
                artifact = _artifact(repo, record["artifact"], f"evidence {ticket}/{claim}")
                if "task-handoffs/" in artifact:
                    raise MigrationError("Task Handoff cannot be acceptance evidence")
                _commit(repo, record["revision"], f"evidence {ticket}/{claim} revision")
                if not isinstance(record["environment"], str) or not record["environment"].strip():
                    raise MigrationError(f"evidence {ticket}/{claim} environment must be non-empty")
                if "invalidatedBy" in record and record["invalidatedBy"] is not None and (not isinstance(record["invalidatedBy"], str) or not record["invalidatedBy"].strip()):
                    raise MigrationError(f"evidence {ticket}/{claim} invalidatedBy must be text or null")
                evidence_by_ticket.setdefault(ticket, {}).setdefault(claim, []).append(record)
                records.append((ticket, claim, artifact))
    for ticket, required_claims in ticket_claims.items():
        if not required_claims <= set(index.get(ticket, {})):
            raise MigrationError(f"candidate evidenceIndex is missing claims for {ticket}")
    for ticket, row in candidate["tickets"].items():
        if row["state"] != "SATISFIED":
            continue
        acceptance_revision = _commit(repo, row["acceptance"]["revision"], f"Ticket {ticket} acceptance revision")
        environment = row["acceptance"]["environment"]
        for claim in ticket_claims[ticket]:
            current = [record for record in evidence_by_ticket.get(ticket, {}).get(claim, []) if _commit(repo, record["revision"], f"evidence {ticket}/{claim} revision") == acceptance_revision and record["environment"] == environment and not record.get("invalidatedBy")]
            if not any(record["conclusion"] == "supporting" for record in current):
                raise MigrationError(f"SATISFIED Ticket {ticket} is missing current supporting evidence for {claim}")
            if any(record["conclusion"] in {"contradictory", "inconclusive"} for record in current):
                raise MigrationError(f"SATISFIED Ticket {ticket} has contradictory current evidence for {claim}")
    checkpoints = candidate["activeCheckpoints"]
    if not isinstance(checkpoints, dict):
        raise MigrationError("candidate activeCheckpoints must be an object")
    for subject, value in checkpoints.items():
        if subject != "attempt" and subject not in {f"ticket:{ticket}" for ticket in candidate["tickets"]}:
            raise MigrationError(f"invalid active checkpoint subject: {subject}")
        if not isinstance(value, dict) or set(value) != {"next", "blocker", "evidence"} or not isinstance(value["next"], str) or not value["next"].strip():
            raise MigrationError(f"invalid active checkpoint: {subject}")
        if value["blocker"] is not None and (not isinstance(value["blocker"], str) or not value["blocker"].strip()):
            raise MigrationError(f"invalid active checkpoint blocker: {subject}")
        if not isinstance(value["evidence"], list) or any(not isinstance(item, str) for item in value["evidence"]):
            raise MigrationError(f"invalid active checkpoint evidence: {subject}")
        for item in value["evidence"]:
            _artifact(repo, item, f"checkpoint {subject} evidence")
    if not archive.is_dir():
        raise MigrationError("legacy Task Handoffs must be archived")
    _validate_progress(package, plan_text, candidate, history, attempt["id"])
    _runtime_validate(package)
    return {"valid": True, "formatVersion": "3.5", "attempt": attempt["id"], "tickets": len(candidate["tickets"]), "evidenceRecords": len(records), "preMigrationAnchor": normalized_anchor, "warnings": warnings}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--package", type=Path, required=True)
    parser.add_argument("--pre-anchor", required=True)
    args = parser.parse_args(argv)
    try:
        result = validate_migration(args.package.resolve(), pre_anchor=args.pre_anchor)
    except (MigrationError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
