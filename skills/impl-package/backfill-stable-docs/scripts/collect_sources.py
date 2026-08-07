#!/usr/bin/env python3
"""Collect explicit Stable Docs sources without deciding their disposition."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

from contract_preflight import package_paths, run_preflight
from gate_recognition import TERMINAL_GATE_VERDICTS, resolve_gate
from make_item_id import make_item_id
from stable_docs_config import (
    ConfigError,
    discover_pending_paths,
    find_done_match,
    load_done_records,
    load_repository_config,
    resolve_project_path,
    resolve_target_branch,
)


class CollectorError(RuntimeError):
    pass


ITEM_ID_RE = re.compile(r"(?P<source>[A-Za-z0-9][A-Za-z0-9._/-]*)::(?P<delta>[^\s`*]+)")
DURABLE_SECTION_RE = re.compile(r"(?ms)^##\s+Durable Deltas\s*\n(.*?)(?=^##\s+|\Z)")
DELTA_LINE_RE = re.compile(r"^- (?P<delta>[A-Za-z0-9][A-Za-z0-9._-]*)\s*:\s*(?P<text>.+?)\s*$")
NONE_LINE_RE = re.compile(r"^- none\s*$", re.IGNORECASE)
REASON_LINE_RE = re.compile(r"^- Reason\s*:", re.IGNORECASE)
STRIKE_RE = re.compile(r"~~.*?~~")


def _git_root(value: Path | str) -> Path:
    root = Path(value).resolve()
    result = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=root, capture_output=True, text=True, check=False)
    if result.returncode or Path(result.stdout.strip()).resolve() != root:
        raise CollectorError("project root must be the Git top level")
    return root


def _git(project: Path, *args: str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=project, capture_output=True, text=True, check=False)
    if ok and result.returncode:
        raise CollectorError(result.stderr.strip() or result.stdout.strip() or "git command failed")
    return result


def _main_worktree(project: Path) -> Path:
    output = _git(project, "worktree", "list", "--porcelain").stdout.splitlines()
    first = next((line.removeprefix("worktree ") for line in output if line.startswith("worktree ")), None)
    if first is None:
        raise CollectorError("cannot resolve the main Git worktree")
    return Path(first).resolve()


def _worktree_context(project: Path) -> dict[str, Any]:
    branch = _git(project, "symbolic-ref", "--quiet", "--short", "HEAD", ok=False)
    return {
        "path": str(project),
        "branch": branch.stdout.strip() if branch.returncode == 0 else None,
        "head": _git(project, "rev-parse", "HEAD").stdout.strip(),
        "dirty": bool(_git(project, "status", "--porcelain").stdout.strip()),
    }


def _target_contains(project: Path, commit: str | None, target_commit: str) -> bool | None:
    if commit is None:
        return None
    result = _git(project, "merge-base", "--is-ancestor", commit, target_commit, ok=False)
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    raise CollectorError(result.stderr.strip() or "cannot evaluate target branch reachability")


def parse_durable_deltas(gate_text: str) -> dict[str, Any]:
    """Parse Gate Durable Deltas into readable delta IDs. `none` yields no candidates."""
    match = DURABLE_SECTION_RE.search(gate_text)
    if match is None:
        return {"status": "missing", "deltas": [], "reason": "Durable Deltas section is absent"}
    body = match.group(1)
    deltas: list[dict[str, str]] = []
    saw_none = False
    for raw in body.splitlines():
        line = raw.strip()
        if not line or not line.startswith("-"):
            continue
        if NONE_LINE_RE.match(line):
            saw_none = True
            continue
        if REASON_LINE_RE.match(line):
            continue
        found = DELTA_LINE_RE.match(line)
        if found is None:
            continue
        delta_id = found.group("delta")
        text = found.group("text").strip()
        if delta_id.lower() == "none":
            saw_none = True
            continue
        deltas.append({"deltaId": delta_id, "statement": text})
    if saw_none and not deltas:
        return {"status": "none", "deltas": [], "reason": "Gate Durable Deltas is none"}
    if not deltas:
        return {"status": "empty", "deltas": [], "reason": "Durable Deltas has no readable delta-id lines"}
    return {"status": "ok", "deltas": deltas, "reason": None}


def parse_pending_items(project: Path, pending: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Extract open pending-registry item IDs. Pending is optional and never suppresses gap-catching."""
    items: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in pending:
        if row["status"] != "ok":
            continue
        text = resolve_project_path(project, row["pendingPath"]).read_text(encoding="utf-8-sig")
        for line_no, raw in enumerate(text.splitlines(), start=1):
            if "~~" in raw and STRIKE_RE.sub("", raw).strip() == "":
                continue
            open_text = STRIKE_RE.sub("", raw)
            for match in ITEM_ID_RE.finditer(open_text):
                source = match.group("source").replace("\\", "/")
                delta_id = match.group("delta")
                try:
                    item_id = make_item_id(source, delta_id)
                except ValueError:
                    continue
                if item_id in seen:
                    continue
                seen.add(item_id)
                items.append({
                    "id": item_id,
                    "packagePath": source,
                    "deltaId": delta_id,
                    "pendingPath": row["pendingPath"],
                    "line": line_no,
                    "origin": "pending-registry",
                })
    return items


def _done_reason(match: dict[str, Any]) -> str:
    commit = match.get("comparisonCommit") or "unspecified-commit"
    disposition = match.get("disposition")
    base = f"matched records.done id={match.get('id')} comparisonCommit={commit}"
    if disposition:
        return f"{base} disposition={disposition}"
    return base


def collect_inventory(project_root: Path | str, config_path: Path | str | None = None) -> dict[str, Any]:
    invoked = _git_root(project_root)
    project = _git_root(_main_worktree(invoked))
    config, metadata = load_repository_config(project, config_path)
    target_commit = resolve_target_branch(project, config["targetBranch"])
    preflight = run_preflight(project, config)
    pending = discover_pending_paths(project, config)
    pending_items = parse_pending_items(project, pending)
    done = load_done_records(project, config)

    packages: list[dict[str, Any]] = []
    inventory_items: list[dict[str, Any]] = []
    by_id: dict[str, dict[str, Any]] = {}

    def upsert_item(row: dict[str, Any]) -> None:
        existing = by_id.get(row["id"])
        if existing is None:
            by_id[row["id"]] = row
            inventory_items.append(row)
            return
        # Prefer pending-registry when both sources surface the same open item.
        if existing.get("origin") == "gap-catching" and row.get("origin") == "pending-registry":
            existing["origin"] = "pending-registry"
            existing["pendingPath"] = row.get("pendingPath")
            existing["line"] = row.get("line")
        if existing.get("status") == "candidate" and row.get("status") == "filtered-by-done":
            return
        if row.get("status") == "filtered-by-done" and existing.get("status") != "filtered-by-done":
            existing["status"] = "filtered-by-done"
            existing["doneFilterReason"] = row.get("doneFilterReason")

    package_index: dict[str, dict[str, Any]] = {}
    for package in package_paths(project, config):
        relative = package.relative_to(project).as_posix()
        gate = resolve_gate(package)
        terminal = gate["recognition"] == "current" and gate["verdict"] in TERMINAL_GATE_VERDICTS
        target_reachable = _target_contains(project, gate["comparisonCommit"], target_commit) if terminal else None
        gate_text = (package / "gate.md").read_text(encoding="utf-8-sig") if (package / "gate.md").is_file() else ""
        durable = parse_durable_deltas(gate_text) if gate_text else {"status": "missing", "deltas": [], "reason": "gate.md is absent"}
        package_row = {
            "packageId": package.name,
            "path": relative,
            "gateRecognition": gate["recognition"],
            "gateVerdict": gate["verdict"],
            "comparisonCommit": gate["comparisonCommit"],
            "targetReachable": target_reachable,
            "durableDeltaStatus": durable["status"],
            "durableDeltas": [],
            "pendingRegistered": False,
            "origin": None,
            "gapCatchingCandidate": False,
            "durableDeltaCandidate": False,
            "candidateItemIds": [],
            "doneFilteredItemIds": [],
            "reason": gate["reason"] or durable.get("reason"),
        }
        package_index[relative] = package_row
        packages.append(package_row)

        if not (terminal and target_reachable is True):
            continue
        for delta in durable["deltas"]:
            try:
                item_id = make_item_id(relative, delta["deltaId"])
            except ValueError:
                continue
            package_row["durableDeltas"].append({
                "deltaId": delta["deltaId"],
                "statement": delta["statement"],
                "itemId": item_id,
            })
            match = find_done_match(
                done,
                item_id=item_id,
                package_path=relative,
                delta_id=delta["deltaId"],
                comparison_commit=gate["comparisonCommit"],
            )
            if match is not None:
                reason = _done_reason(match)
                package_row["doneFilteredItemIds"].append(item_id)
                upsert_item({
                    "id": item_id,
                    "packageId": package.name,
                    "packagePath": relative,
                    "deltaId": delta["deltaId"],
                    "comparisonCommit": gate["comparisonCommit"],
                    "statement": delta["statement"],
                    "origin": "gap-catching",
                    "status": "filtered-by-done",
                    "doneFilterReason": reason,
                })
                continue
            package_row["candidateItemIds"].append(item_id)
            package_row["gapCatchingCandidate"] = True
            package_row["durableDeltaCandidate"] = True
            if package_row["origin"] is None:
                package_row["origin"] = "gap-catching"
            upsert_item({
                "id": item_id,
                "packageId": package.name,
                "packagePath": relative,
                "deltaId": delta["deltaId"],
                "comparisonCommit": gate["comparisonCommit"],
                "statement": delta["statement"],
                "origin": "gap-catching",
                "status": "candidate",
                "doneFilterReason": None,
            })

    for pending_item in pending_items:
        source = pending_item["packagePath"]
        package_row = package_index.get(source)
        package_id = package_row["packageId"] if package_row else Path(source).name
        comparison = package_row["comparisonCommit"] if package_row else None
        match = find_done_match(
            done,
            item_id=pending_item["id"],
            package_path=source,
            delta_id=pending_item["deltaId"],
            comparison_commit=comparison,
        )
        if package_row is not None:
            package_row["pendingRegistered"] = True
        if match is not None:
            reason = _done_reason(match)
            if package_row is not None and pending_item["id"] not in package_row["doneFilteredItemIds"]:
                package_row["doneFilteredItemIds"].append(pending_item["id"])
            upsert_item({
                "id": pending_item["id"],
                "packageId": package_id,
                "packagePath": source,
                "deltaId": pending_item["deltaId"],
                "comparisonCommit": comparison,
                "statement": None,
                "origin": "pending-registry",
                "pendingPath": pending_item["pendingPath"],
                "line": pending_item["line"],
                "status": "filtered-by-done",
                "doneFilterReason": reason,
            })
            continue
        if package_row is not None:
            if pending_item["id"] not in package_row["candidateItemIds"]:
                package_row["candidateItemIds"].append(pending_item["id"])
            package_row["durableDeltaCandidate"] = True
            if package_row["origin"] is None:
                package_row["origin"] = "pending-registry"
        upsert_item({
            "id": pending_item["id"],
            "packageId": package_id,
            "packagePath": source,
            "deltaId": pending_item["deltaId"],
            "comparisonCommit": comparison,
            "statement": None,
            "origin": "pending-registry",
            "pendingPath": pending_item["pendingPath"],
            "line": pending_item["line"],
            "status": "candidate",
            "doneFilterReason": None,
        })

    candidates = [row for row in inventory_items if row["status"] == "candidate"]
    done_filtered = [row for row in inventory_items if row["status"] == "filtered-by-done"]
    return {
        "project": {"targetBranch": config["targetBranch"], "targetBranchCommit": target_commit},
        "sourceWorktree": _worktree_context(project),
        "invokedWorktree": str(invoked),
        "config": metadata,
        "preflight": preflight,
        "pending": pending,
        "done": {
            "path": done["path"],
            "status": done["status"],
            "itemCount": done["itemCount"],
            "reason": done.get("reason"),
        },
        "ignored": config["ignore"],
        "packages": packages,
        "items": inventory_items,
        "packageCount": len(packages),
        "manualGateReviewCandidates": [row["packageId"] for row in packages if row["gateRecognition"] == "invalid"],
        "durableDeltaCandidates": [row["id"] for row in candidates],
        "pendingRegistryCandidates": [row["id"] for row in candidates if row["origin"] == "pending-registry"],
        "gapCatchingCandidates": [row["id"] for row in candidates if row["origin"] == "gap-catching"],
        "doneFilteredItems": [
            {"id": row["id"], "origin": row["origin"], "doneFilterReason": row["doneFilterReason"]}
            for row in done_filtered
        ],
        "targetUnreachablePackages": [row["packageId"] for row in packages if row["targetReachable"] is False],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        payload = collect_inventory(args.project_root, args.config)
        text = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        if args.output:
            project = Path(args.project_root).resolve()
            output = args.output if args.output.is_absolute() else project / args.output
            try:
                output.resolve().relative_to(project)
            except ValueError as error:
                raise CollectorError("output must be inside the repository") from error
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(text, encoding="utf-8", newline="\n")
        else:
            sys.stdout.write(text)
    except (CollectorError, ConfigError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
