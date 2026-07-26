#!/usr/bin/env python3
"""Read-only issue workflow snapshots, validation, reports, and plans.

This program never executes GitHub write commands. Triage owns confirmed writes.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


READ_ONLY_GH = {"issue", "pr"}


def load_yaml(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        value = yaml.safe_load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected mapping in {path}")
    return value


def load_json(path: str) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected object in {path}")
    return value


def write_json(value: Any, output: str | None) -> None:
    text = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    if output:
        Path(output).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)


def labels_of(issue: dict[str, Any]) -> set[str]:
    labels = issue.get("labels", [])
    return {item["name"] if isinstance(item, dict) else item for item in labels}


def number_of(issue: dict[str, Any]) -> Any:
    return issue.get("number", issue.get("id", "new"))


def contract_labels(contract: dict[str, Any]) -> set[str]:
    return {label for family in contract["labels"].values() for label in family}


def validate_issue(issue: dict[str, Any], contract: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    labels = labels_of(issue)
    families = contract["labels"]
    shape = labels & set(families["shape"])
    readiness = labels & set(families["readiness"])
    types = labels & set(families["type"])
    violations: list[dict[str, Any]] = []
    advisories: list[dict[str, Any]] = []
    issue_id = number_of(issue)

    def hard(rule: str, detail: str) -> None:
        violations.append({"issue": issue_id, "rule": rule, "detail": detail})

    if len(shape) > 1:
        hard("shape-at-most-one", f"multiple work shapes: {sorted(shape)}")
    is_initiative = "work:initiative" in shape
    if not is_initiative:
        if len(types) != 1:
            hard("type-exactly-one", f"found {sorted(types)}")
        if len(readiness) != 1:
            hard("readiness-exactly-one", f"found {sorted(readiness)}")
    else:
        if len(readiness) > 1:
            hard("initiative-readiness-at-most-one", f"found {sorted(readiness)}")
        invalid = readiness - set(contract["rules"]["initiative"]["allowedReadiness"])
        if invalid:
            hard("initiative-readiness", f"not allowed: {sorted(invalid)}")
        closure = re.search(r"^##\s+Closure condition\s*$\n+([^#\n].*?)(?=^##\s|\Z)", str(issue.get("body", "")), flags=re.IGNORECASE | re.MULTILINE | re.DOTALL)
        if not closure or not closure.group(1).strip():
            hard("initiative-closure-condition", "missing non-empty ## Closure condition section")
    if "blocked" in readiness and not issue.get("blockedBy"):
        if issue.get("relationsKnown", True):
            hard("blocked-requires-dependency", "blockedBy relation is missing")
        else:
            advisories.append({"issue": issue_id, "rule": "blocked-relation-unknown", "detail": "cannot verify blockedBy until native relations are read"})
    if "wontfix" in readiness and str(issue.get("state", "OPEN")).upper() == "OPEN":
        hard("wontfix-requires-closed", "wontfix issue is still open")
    if not issue.get("relationsKnown", True):
        advisories.append({"issue": issue_id, "rule": "relations-unknown", "detail": "native relations were not available in this snapshot"})
    return violations, advisories


def validate_snapshot(snapshot: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    hard: list[dict[str, Any]] = []
    advisory: list[dict[str, Any]] = []
    unknowns = list(snapshot.get("unknowns", []))
    if snapshot.get("contractVersion") != contract.get("contractVersion"):
        hard.append({"issue": None, "rule": "contract-version", "detail": "snapshot contractVersion differs from current contract"})
    for issue in snapshot.get("issues", []):
        if str(issue.get("state", "OPEN")).upper() != "OPEN":
            continue
        violations, notices = validate_issue(issue, contract)
        hard.extend(violations)
        advisory.extend(notices)
    return {"contractVersion": contract["contractVersion"], "hardViolations": hard, "advisories": advisory, "unknowns": unknowns}


def normalize_snapshot(raw: dict[str, Any], contract: dict[str, Any], repository: str | None = None) -> dict[str, Any]:
    issues = raw.get("issues", raw.get("issue", []))
    prs = raw.get("pullRequests", raw.get("pullRequests", raw.get("prs", [])))
    if not isinstance(issues, list) or not isinstance(prs, list):
        raise ValueError("issues and pullRequests must be arrays")
    return {
        "schemaVersion": 1,
        "contractVersion": contract["contractVersion"],
        "repository": repository or raw.get("repository"),
        "fetchedAt": datetime.now(timezone.utc).isoformat(),
        "issues": issues,
        "pullRequests": prs,
        "unknowns": raw.get("unknowns", []),
    }


def gh_read(repo: str, kind: str) -> list[dict[str, Any]]:
    if kind not in READ_ONLY_GH:
        raise ValueError("only gh issue/pr list reads are allowed")
    fields = "number,title,body,labels,assignees,state,url" if kind == "issue" else "number,title,body,labels,assignees,state,url,isDraft"
    command = ["gh", kind, "list", "--repo", repo, "--state", "open", "--limit", "100", "--json", fields]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "gh read failed")
    value = json.loads(result.stdout)
    if not isinstance(value, list):
        raise ValueError("gh list did not return an array")
    return value


def graphql_issues(repo: str) -> list[dict[str, Any]]:
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $name: String!) {
  repository(owner: $owner, name: $name) {
    issues(first: 100, states: OPEN) {
      nodes {
        number title body state url
        labels(first: 100) { nodes { name } }
        assignees(first: 20) { nodes { login } }
        parent { number }
        subIssues(first: 100) { nodes { number } }
        blockedBy(first: 100) { nodes { number } }
        blocking(first: 100) { nodes { number } }
      }
    }
  }
}
"""
    command = ["gh", "api", "graphql", "-f", f"query={query}", "-F", f"owner={owner}", "-F", f"name={name}"]
    result = subprocess.run(command, check=False, text=True, capture_output=True)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "gh GraphQL issue read failed")
    nodes = json.loads(result.stdout)["data"]["repository"]["issues"]["nodes"]
    normalized: list[dict[str, Any]] = []
    for issue in nodes:
        normalized.append({
            **issue,
            "labels": issue["labels"]["nodes"],
            "assignees": issue["assignees"]["nodes"],
            "parent": issue["parent"]["number"] if issue["parent"] else None,
            "subIssues": [child["number"] for child in issue["subIssues"]["nodes"]],
            "blockedBy": [dependency["number"] for dependency in issue["blockedBy"]["nodes"]],
            "blocking": [dependency["number"] for dependency in issue["blocking"]["nodes"]],
            "relationsKnown": True,
        })
    return normalized


def snapshot_from_gh(repo: str, contract: dict[str, Any]) -> dict[str, Any]:
    unknowns: list[dict[str, str]] = []
    try:
        issues = graphql_issues(repo)
    except Exception as exc:  # report read scope honestly
        try:
            issues = gh_read(repo, "issue")
            for issue in issues:
                issue["relationsKnown"] = False
            unknowns.append({"scope": "native-relations", "reason": str(exc)})
        except Exception as fallback_exc:
            issues = []
            unknowns.append({"scope": "issues", "reason": f"{exc}; fallback failed: {fallback_exc}"})
    try:
        prs = gh_read(repo, "pr")
    except Exception as exc:
        prs = []
        unknowns.append({"scope": "pullRequests", "reason": str(exc)})
    return normalize_snapshot({"issues": issues, "pullRequests": prs, "unknowns": unknowns}, contract, repo)


def report(snapshot: dict[str, Any], contract: dict[str, Any], mode: str, issue_number: int | None) -> dict[str, Any]:
    audit = validate_snapshot(snapshot, contract)
    issues = [issue for issue in snapshot.get("issues", []) if str(issue.get("state", "OPEN")).upper() == "OPEN"]
    if issue_number is not None:
        issues = [issue for issue in issues if issue.get("number") == issue_number]
    groups = {"next-actions": [], "blocked": [], "initiatives": [], "hygiene": audit["hardViolations"]}
    for issue in issues:
        labels = labels_of(issue)
        item = {"number": number_of(issue), "title": issue.get("title", ""), "labels": sorted(labels), "directPullRequests": issue.get("pullRequests", [])}
        if "work:initiative" in labels:
            groups["initiatives"].append(item)
        if "blocked" in labels:
            groups["blocked"].append(item)
        if "work:initiative" not in labels and labels & {"needs-info", "ready-for-agent", "ready-for-human"}:
            groups["next-actions"].append(item)
    if mode == "issue" and issue_number is None:
        raise ValueError("--issue is required for issue mode")
    return {"mode": mode, "repository": snapshot.get("repository"), "counts": {key: len(value) for key, value in groups.items()}, "groups": groups, "advisories": audit["advisories"], "unknowns": audit["unknowns"]}


def load_identity(path: str) -> dict[str, str]:
    data = load_yaml(path)
    aliases: dict[str, str] = {}
    for person in data.get("people", {}).values():
        login = person.get("github")
        for alias in person.get("aliases", []):
            if alias in aliases and aliases[alias] != login:
                raise ValueError(f"ambiguous alias: {alias}")
            aliases[alias] = login
    return aliases


def plan(snapshot: dict[str, Any], contract: dict[str, Any], intent: dict[str, Any], identity_path: str | None) -> dict[str, Any]:
    if intent.get("snapshotContractVersion") != snapshot.get("contractVersion"):
        raise ValueError("intent snapshotContractVersion does not match snapshot")
    aliases = load_identity(identity_path) if identity_path else {}
    existing = {issue.get("number"): issue for issue in snapshot.get("issues", [])}
    operations: list[dict[str, Any]] = []
    for change in intent.get("changes", []):
        number = change.get("issue", "new")
        before = existing.get(number, {})
        final_labels = sorted(change.get("labels", labels_of(before)))
        candidate = {**before, "number": number, "labels": final_labels, "state": change.get("state", before.get("state", "OPEN")), "blockedBy": change.get("blockedBy", before.get("blockedBy", [])), "body": change.get("body", before.get("body", ""))}
        violations, _ = validate_issue(candidate, contract)
        if violations:
            operations.append({"target": number, "status": "invalid", "violations": violations})
            continue
        operations.append({"target": number, "status": "ready-for-confirmation", "labelDiff": {"from": sorted(labels_of(before)), "to": final_labels}, "relations": {key: change[key] for key in ("parent", "blockedBy", "pullRequest") if key in change}})
        for mention in change.get("people", []):
            alias = mention.get("alias")
            login = aliases.get(alias)
            if not login:
                operations.append({"target": number, "status": "unknown", "operation": mention.get("kind"), "alias": alias})
            else:
                operations.append({"target": number, "status": "ready-for-confirmation", "operation": mention.get("kind"), "login": login})
    return {"snapshotContractVersion": snapshot["contractVersion"], "operations": operations, "writeBoundary": "This plan is not applied; triage must obtain confirmation before using gh."}


def contract_check(contract: dict[str, Any], initiative_template: str, identity: str | None) -> dict[str, Any]:
    required = {"labels", "rules", "handoff", "contractVersion"}
    missing = sorted(required - set(contract))
    body = Path(initiative_template).read_text(encoding="utf-8")
    errors = [f"missing contract key: {key}" for key in missing]
    if "## Closure condition" not in body:
        errors.append("initiative template is missing ## Closure condition")
    aliases = load_identity(identity) if identity else {}
    return {"ok": not errors, "contractVersion": contract.get("contractVersion"), "aliases": aliases, "errors": errors}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True)
    subparsers = parser.add_subparsers(dest="command", required=True)
    snapshot_parser = subparsers.add_parser("snapshot")
    snapshot_parser.add_argument("--repo")
    snapshot_parser.add_argument("--input")
    snapshot_parser.add_argument("--output")
    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--snapshot", required=True)
    report_parser = subparsers.add_parser("report")
    report_parser.add_argument("--snapshot", required=True)
    report_parser.add_argument("--mode", choices=("portfolio", "issue", "audit", "hygiene"), default="portfolio")
    report_parser.add_argument("--issue", type=int)
    plan_parser = subparsers.add_parser("plan")
    plan_parser.add_argument("--snapshot", required=True)
    plan_parser.add_argument("--intent", required=True)
    plan_parser.add_argument("--identity")
    check_parser = subparsers.add_parser("contract-check")
    check_parser.add_argument("--initiative-template", required=True)
    check_parser.add_argument("--identity")
    args = parser.parse_args()
    contract = load_yaml(args.contract)
    if args.command == "snapshot":
        raw = load_json(args.input) if args.input else snapshot_from_gh(args.repo, contract)
        result = normalize_snapshot(raw, contract, args.repo) if args.input else raw
        write_json(result, args.output)
    elif args.command == "validate":
        write_json(validate_snapshot(load_json(args.snapshot), contract), None)
    elif args.command == "report":
        write_json(report(load_json(args.snapshot), contract, args.mode, args.issue), None)
    elif args.command == "plan":
        write_json(plan(load_json(args.snapshot), contract, load_json(args.intent), args.identity), None)
    else:
        write_json(contract_check(contract, args.initiative_template, args.identity), None)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, yaml.YAMLError, json.JSONDecodeError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise SystemExit(2)
