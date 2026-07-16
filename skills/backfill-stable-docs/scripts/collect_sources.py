#!/usr/bin/env python3
"""Enumerate Stable Docs backfill inventory: packages, pending registrations, and
gap-catching / retirement candidates. This is a read-only enumeration helper —
it never decides disposition; the agent reads the listed evidence and judges."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from stable_docs_config import (
    ConfigError,
    discover_pending_paths,
    expand_roots,
    load_repository_config,
    path_matches_ignore,
    resolve_project_path,
    resolve_target_branch,
)


class CollectorError(RuntimeError):
    """Raised when source inventory cannot be collected safely."""


GATE_ENTRY_RE = re.compile(r"^#{1,6}\s+(?P<entry_id>\S+)\s*[·:]\s*(?P<verdict>pass|fail|blocked|defer)\b", re.IGNORECASE)
TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|\s*$")
TERMINAL_VERDICTS = {"pass", "fail", "defer"}


def _require_git_repository(path: Path | str) -> Path:
    root = Path(path).resolve()
    if not root.is_dir():
        raise CollectorError(f"project root is not a directory: {root}")
    completed = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise CollectorError(f"project root is not a Git repository: {root}")
    top_level = Path(completed.stdout.strip()).resolve()
    if top_level != root:
        raise CollectorError(f"project root must be the Git top level: {root}")
    return root


def _read_gate_verdict(gate_path: Path) -> str | None:
    """Return the verdict of the newest (topmost) gate entry, or None if no entry found."""
    if not gate_path.is_file():
        return None
    for line in gate_path.read_text(encoding="utf-8").splitlines():
        match = GATE_ENTRY_RE.match(line.strip())
        if match:
            return match.group("verdict").lower()
    return None


def extract_markdown_tables(path: Path) -> list[dict[str, Any]]:
    """Extract every Markdown table in a file as {"header", "rows", "line"} blocks."""
    if not path.is_file():
        return []
    lines = path.read_text(encoding="utf-8").splitlines()
    tables: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        header_match = TABLE_ROW_RE.match(lines[index].strip())
        if header_match and index + 1 < len(lines) and TABLE_SEP_RE.match(lines[index + 1].strip()):
            header = [cell.strip() for cell in header_match.group(1).split("|")]
            start_line = index + 1
            row_index = index + 2
            rows: list[list[str]] = []
            while row_index < len(lines):
                row_match = TABLE_ROW_RE.match(lines[row_index].strip())
                if not row_match:
                    break
                rows.append([cell.strip() for cell in row_match.group(1).split("|")])
                row_index += 1
            tables.append({"header": header, "rows": rows, "line": start_line})
            index = row_index
        else:
            index += 1
    return tables


def _load_done_record(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"items": [], "retiredPackages": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CollectorError(f"done record must be readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise CollectorError(f"done record must contain a JSON object: {path}")
    return {
        "items": payload.get("items", []) if isinstance(payload.get("items"), list) else [],
        "retiredPackages": (
            payload.get("retiredPackages", []) if isinstance(payload.get("retiredPackages"), list) else []
        ),
    }


def collect_inventory(
    *, project_root: Path | str, config_path: Path | str | None = None
) -> dict[str, Any]:
    project = _require_git_repository(project_root)
    try:
        config, config_metadata = load_repository_config(project, config_path)
    except ConfigError as error:
        raise CollectorError(str(error)) from error

    try:
        target_branch_commit = resolve_target_branch(project, config["targetBranch"])
        target_branch_gap = None
    except ConfigError as error:
        target_branch_commit = None
        target_branch_gap = str(error)

    pending_discovery = discover_pending_paths(project, config)
    config_gaps = [
        entry for entry in pending_discovery if entry["status"] in {"missing", "ambiguous"}
    ]
    pending_cold_starts = [
        entry for entry in pending_discovery if entry["status"] == "cold-start"
    ]

    pending_registrations: list[dict[str, Any]] = []
    pending_owners: dict[str, dict[str, set[str]]] = {}
    for entry in pending_discovery:
        if entry["status"] != "ok":
            continue
        owner = pending_owners.setdefault(
            entry["pendingPath"], {"layers": set(), "roots": set()}
        )
        owner["layers"].add(entry["stableDocsLayer"])
        owner["roots"].update(entry["stableDocsRoots"])
    for pending_relative, owner in sorted(pending_owners.items()):
        pending_path = resolve_project_path(project, pending_relative)
        for table in extract_markdown_tables(pending_path):
            for row in table["rows"]:
                pending_registrations.append(
                    {
                        "pendingFile": pending_relative,
                        "stableDocsLayers": sorted(owner["layers"]),
                        "stableDocsRoots": sorted(owner["roots"]),
                        "header": table["header"],
                        "row": row,
                    }
                )

    done_record = _load_done_record(resolve_project_path(project, config["records"]["done"]))
    resolved_package_ids = {
        item.get("sourcePackage")
        for item in done_record["items"]
        if isinstance(item, dict) and isinstance(item.get("sourcePackage"), str)
    }

    packages: list[dict[str, Any]] = []
    for implementations_root in expand_roots(project, config["implementations"]):
        for package_dir in sorted(p for p in implementations_root.iterdir() if p.is_dir()):
            relative_package_dir = package_dir.relative_to(project).as_posix()
            if path_matches_ignore(relative_package_dir, config["ignore"]) is not None:
                continue
            package_id = package_dir.relative_to(implementations_root).as_posix()
            gate_path = package_dir / "gate.md"
            has_gate = gate_path.is_file()
            verdict = _read_gate_verdict(gate_path)
            # A gate.md that exists but doesn't match the new `## <id> · <verdict>` heading
            # (i.e. every legacy/pre-redesign gate.md) is NOT the same as "no verdict yet" —
            # the collector genuinely cannot tell, so it must not silently default to "ignore".
            gate_verdict_parsed = has_gate and verdict is not None
            needs_manual_gate_review = has_gate and not gate_verdict_parsed
            referenced = any(
                package_id in cell or relative_package_dir in cell
                for registration in pending_registrations
                for cell in registration["row"]
            )
            is_terminal = gate_verdict_parsed and verdict in TERMINAL_VERDICTS
            packages.append(
                {
                    "packageId": package_id,
                    "path": relative_package_dir,
                    "implementationsRoot": implementations_root.relative_to(project).as_posix(),
                    "hasDesign": (package_dir / "design.md").is_file(),
                    "hasSpec": (package_dir / "spec.md").is_file(),
                    "hasGate": has_gate,
                    "gateVerdict": verdict,
                    "gateVerdictParsed": gate_verdict_parsed,
                    "needsManualGateReview": needs_manual_gate_review and not referenced,
                    "referencedInOpenPending": referenced,
                    "resolvedInDoneRecord": package_id in resolved_package_ids,
                    "gapCatchingCandidate": (
                        is_terminal and not referenced and package_id not in resolved_package_ids
                    ),
                    "retirementStructuralCandidate": (
                        is_terminal and not referenced and package_id in resolved_package_ids
                    ),
                }
            )

    return {
        "schemaVersion": 3,
        "project": {
            "repository": config["repository"],
            "targetBranch": config["targetBranch"],
            "targetBranchCommit": target_branch_commit,
        },
        "config": {"source": config_metadata["source"], "sha256": config_metadata["sha256"]},
        "targetBranchConfigGap": target_branch_gap,
        "pendingDiscovery": pending_discovery,
        "pendingConfigGaps": config_gaps,
        "pendingColdStarts": pending_cold_starts,
        "pendingRegistrationCount": len(pending_registrations),
        "pendingRegistrations": pending_registrations,
        "packageCount": len(packages),
        "gapCatchingCandidates": [p["packageId"] for p in packages if p["gapCatchingCandidate"]],
        "retirementStructuralCandidates": [
            p["packageId"] for p in packages if p["retirementStructuralCandidate"]
        ],
        "manualGateReviewCandidates": [
            p["packageId"] for p in packages if p["needsManualGateReview"]
        ],
        "packages": packages,
    }


def _render_markdown(inventory: dict[str, Any]) -> str:
    project = inventory["project"]
    lines = [
        "# Stable Docs Backfill Source Inventory",
        "",
        f"- Repository: `{project['repository']}`",
        f"- Target branch: `{project['targetBranch']}` -> `{project['targetBranchCommit'] or 'unresolved'}`",
        f"- Target branch config gap: {'yes' if inventory['targetBranchConfigGap'] else 'no'}",
        f"- Packages: {inventory['packageCount']}",
        f"- Open pending registrations: {inventory['pendingRegistrationCount']}",
        f"- Config gaps (ambiguous/missing `_pending.md`): {len(inventory['pendingConfigGaps'])}",
        f"- Pending cold starts (owner decision, non-blocking): {len(inventory['pendingColdStarts'])}",
        f"- Gap-catching candidates: {len(inventory['gapCatchingCandidates'])}",
        f"- Package Retirement structural candidates: {len(inventory['retirementStructuralCandidates'])}",
        f"- Needs manual gate review (gate.md present but not machine-parseable): {len(inventory['manualGateReviewCandidates'])}",
        "",
        "| Package | Gate verdict | Design | Spec | Open pending ref | Gap-catching | Retirement candidate | Manual gate review |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in inventory["packages"]:
        lines.append(
            "| {package_id} | {verdict} | {design} | {spec} | {referenced} | {gap} | {retire} | {manual} |".format(
                package_id=row["packageId"],
                verdict=row["gateVerdict"] or ("unparsed" if row["hasGate"] else "none"),
                design="yes" if row["hasDesign"] else "no",
                spec="yes" if row["hasSpec"] else "no",
                referenced="yes" if row["referencedInOpenPending"] else "no",
                gap="yes" if row["gapCatchingCandidate"] else "no",
                retire="yes" if row["retirementStructuralCandidate"] else "no",
                manual="yes" if row["needsManualGateReview"] else "no",
            )
        )
    return "\n".join(lines) + "\n"


def _path_under(root: Path, candidate: Path) -> bool:
    try:
        candidate.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        inventory = collect_inventory(project_root=args.project_root, config_path=args.config)
        rendered = (
            json.dumps(inventory, indent=2, sort_keys=True) + "\n"
            if args.format == "json"
            else _render_markdown(inventory)
        )
        if args.output is None:
            sys.stdout.write(rendered)
        else:
            project = Path(args.project_root).resolve()
            output = args.output.resolve()
            if not _path_under(project, output):
                raise CollectorError("output path must remain under project root")
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(rendered, encoding="utf-8", newline="\n")
        return 0
    except (CollectorError, ConfigError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
