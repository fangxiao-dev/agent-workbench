#!/usr/bin/env python3
"""Collect explicit Stable Docs sources without deciding their disposition."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from contract_preflight import package_paths, run_preflight
from gate_recognition import TERMINAL_GATE_VERDICTS, resolve_gate
from stable_docs_config import ConfigError, discover_pending_paths, load_repository_config, resolve_project_path, resolve_target_branch


class CollectorError(RuntimeError):
    pass


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


def _pending_mentions(project: Path, pending: list[dict[str, Any]], package_id: str, package_path: str) -> bool:
    for row in pending:
        if row["status"] != "ok":
            continue
        text = resolve_project_path(project, row["pendingPath"]).read_text(encoding="utf-8-sig")
        if package_id in text or package_path in text:
            return True
    return False


def collect_inventory(project_root: Path | str, config_path: Path | str | None = None) -> dict[str, Any]:
    invoked = _git_root(project_root)
    project = _git_root(_main_worktree(invoked))
    config, metadata = load_repository_config(project, config_path)
    target_commit = resolve_target_branch(project, config["targetBranch"])
    preflight = run_preflight(project, config)
    pending = discover_pending_paths(project, config)
    packages = []
    for package in package_paths(project, config):
        relative = package.relative_to(project).as_posix()
        gate = resolve_gate(package)
        terminal = gate["recognition"] == "current" and gate["verdict"] in TERMINAL_GATE_VERDICTS
        target_reachable = _target_contains(project, gate["comparisonCommit"], target_commit) if terminal else None
        pending_registered = _pending_mentions(project, pending, package.name, relative)
        gap_catching = terminal and target_reachable is True and not pending_registered
        packages.append({
            "packageId": package.name,
            "path": relative,
            "gateRecognition": gate["recognition"],
            "gateVerdict": gate["verdict"],
            "comparisonCommit": gate["comparisonCommit"],
            "targetReachable": target_reachable,
            "pendingRegistered": pending_registered,
            "origin": "pending-registry" if pending_registered else ("gap-catching" if gap_catching else None),
            "gapCatchingCandidate": gap_catching,
            "durableDeltaCandidate": pending_registered or gap_catching,
            "reason": gate["reason"],
        })
    return {
        "project": {"repository": config["repository"], "targetBranch": config["targetBranch"], "targetBranchCommit": target_commit},
        "sourceWorktree": _worktree_context(project),
        "invokedWorktree": str(invoked),
        "config": metadata,
        "preflight": preflight,
        "pending": pending,
        "ignored": config["ignore"],
        "packages": packages,
        "packageCount": len(packages),
        "manualGateReviewCandidates": [row["packageId"] for row in packages if row["gateRecognition"] == "invalid"],
        "durableDeltaCandidates": [row["packageId"] for row in packages if row["durableDeltaCandidate"]],
        "pendingRegistryCandidates": [row["packageId"] for row in packages if row["origin"] == "pending-registry"],
        "gapCatchingCandidates": [row["packageId"] for row in packages if row["origin"] == "gap-catching"],
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
