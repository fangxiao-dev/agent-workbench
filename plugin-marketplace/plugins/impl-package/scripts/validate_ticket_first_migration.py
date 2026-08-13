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


def _history(repo: Path, package: Path, value: object, attempt: dict) -> list[dict]:
    if not isinstance(value, list) or not value:
        raise MigrationError("candidate must retain lightweight attempt history")
    result: list[dict] = []
    for row in value:
        required = {"id", "plan", "lifecycle", "gate", "executionRecord"}
        if not isinstance(row, dict) or set(row) != required:
            raise MigrationError("attemptHistory rows must contain id, plan, lifecycle, gate, executionRecord")
        if not isinstance(row["id"], str) or not row["id"].strip():
            raise MigrationError("attemptHistory id must be non-empty")
        if row["lifecycle"] not in {"active", "frozen"}:
            raise MigrationError(f"invalid attemptHistory lifecycle: {row['lifecycle']!r}")
        plan = _artifact(repo, row["plan"], "attemptHistory plan")
        execution_record = _artifact(package, row["executionRecord"], "attemptHistory executionRecord")
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
        identifier = re.search(r"\*\*Ticket ID[：:]\*\*\s*([^\s]+)", text)
        ticket_attempt = re.search(r"(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:]\s*(?:\*\*)?\s*([^\s*]+)", text)
        if identifier and ticket_attempt and ticket_attempt.group(1) == attempt:
            claims[identifier.group(1)] = set(re.findall(r"Stable claim ID：\s*`([^`]+)`", text))
    return claims


def _ticket_claim_timings(package: Path, attempt: str) -> dict[str, dict[str, str]]:
    timings: dict[str, dict[str, str]] = {}
    ticket_dir = package / "tickets"
    paths = sorted((child for child in ticket_dir.iterdir() if child.is_file() and child.suffix.lower() == ".md"), key=lambda child: child.name) if ticket_dir.is_dir() else []
    for path in paths:
        text = path.read_text(encoding="utf-8")
        identifier = re.search(r"\*\*Ticket ID[：:]\*\*\s*([^\s]+)", text)
        ticket_attempt = re.search(r"(?:\*\*)?(?:Attempt ID|执行尝试 ID（Attempt ID）)(?:\*\*)?\s*[：:]\s*(?:\*\*)?\s*([^\s*]+)", text)
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
        identifier = re.search(r"\*\*Ticket ID[：:]\*\*\s*([^\s]+)", text)
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
    if not isinstance(attempt, dict) or set(attempt) != {"id", "plan"} or not isinstance(attempt["id"], str) or not isinstance(attempt["plan"], str):
        raise MigrationError("candidate attempt must contain id and plan")
    plan_rel = _artifact(repo, attempt["plan"], "candidate plan")
    plan = repo / Path(*plan_rel.split("#", 1)[0].split("/"))
    try:
        plan.resolve().relative_to(package.resolve())
    except ValueError as exc:
        raise MigrationError("candidate plan must be inside the package") from exc
    if not re.search(r"Composition[^\n]*tickets=true,\s*dag=false", plan.read_text(encoding="utf-8"), re.I):
        raise MigrationError("candidate plan must declare tickets=true, dag=false")
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
            if set(row) - {"state", "disposition", "evidence", "successor"} or not {"state", "disposition", "evidence"} <= set(row):
                raise MigrationError(f"RETIRED Ticket {ticket} requires disposition and evidence")
            if row["disposition"] not in DISPOSITIONS:
                raise MigrationError(f"invalid RETIRED disposition for {ticket}")
            _artifact(repo, row["evidence"], f"RETIRED {ticket} evidence")
            if row["disposition"] == "superseded" and (not isinstance(row.get("successor"), str) or row["successor"] not in candidate["tickets"] or row["successor"] == ticket):
                raise MigrationError(f"RETIRED superseded Ticket {ticket} requires a valid successor")
    history = _history(repo, package, candidate["attemptHistory"], attempt)
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
    normalized_anchor = _commit(repo, pre_anchor, "pre-migration anchor") if pre_anchor is not None else None
    return {"valid": True, "formatVersion": "3.5", "attempt": attempt["id"], "tickets": len(candidate["tickets"]), "evidenceRecords": len(records), "preMigrationAnchor": normalized_anchor}


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
