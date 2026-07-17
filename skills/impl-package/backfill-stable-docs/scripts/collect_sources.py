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
from contract_preflight import (
    CONTRACT_VERSION,
    ContractPreflightError,
    require_current,
)
from gate_recognition import TERMINAL_GATE_VERDICTS, resolve_gate


class CollectorError(RuntimeError):
    """Raised when source inventory cannot be collected safely."""


TABLE_ROW_RE = re.compile(r"^\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\|[\s:|-]+\|\s*$")


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
    *,
    project_root: Path | str,
    config_path: Path | str | None = None,
    preflight: bool = True,
) -> dict[str, Any]:
    project = _require_git_repository(project_root)
    try:
        config, config_metadata = load_repository_config(project, config_path)
    except ConfigError as error:
        raise CollectorError(str(error)) from error

    try:
        contract_preflight = require_current(project, config) if preflight else {
            "contractVersion": CONTRACT_VERSION,
            "status": "skipped",
            "packageCount": 0,
            "blockedPackageCount": 0,
            "packages": [],
        }
    except ContractPreflightError as error:
        raise CollectorError(str(error)) from error
    contract_by_path = {
        Path(row["package"]).resolve(): row for row in contract_preflight["packages"]
    }

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
            gate = resolve_gate(package_dir)
            has_gate = gate["hasGate"]
            verdict = gate["gateResolution"]
            applies_to_current_revision = gate.get("appliesToCurrentRevision")
            referenced = any(
                package_id in cell or relative_package_dir in cell
                for registration in pending_registrations
                for cell in registration["row"]
            )
            is_terminal = (
                (
                    gate["kind"] == "indexed" and applies_to_current_revision is True
                )
                and verdict in TERMINAL_GATE_VERDICTS
            )
            packages.append(
                {
                    "packageId": package_id,
                    "path": relative_package_dir,
                    "contractVersion": contract_by_path.get(package_dir.resolve(), {}).get("contractVersion"),
                    "contractStatus": contract_by_path.get(package_dir.resolve(), {}).get("status"),
                    "implementationsRoot": implementations_root.relative_to(project).as_posix(),
                    "hasDesign": (package_dir / "design.md").is_file(),
                    "hasSpec": (package_dir / "spec.md").is_file(),
                    "hasGate": has_gate,
                    "gateRecognition": gate["kind"],
                    "gateResolution": verdict,
                    "gateAppliesToCurrentRevision": applies_to_current_revision,
                    "needsManualGateReview": gate["needsManualGateReview"],
                    "reason": gate["reason"],
                    "referencedInOpenPending": referenced,
                    "resolvedInDoneRecord": package_id in resolved_package_ids,
                    "gapCatchingStructuralCandidate": (
                        is_terminal and not referenced and package_id not in resolved_package_ids
                    ),
                    "retirementStructuralCandidate": (
                        is_terminal and not referenced and package_id in resolved_package_ids
                    ),
                }
            )

    return {
        "contractVersion": CONTRACT_VERSION,
        "contractPreflight": contract_preflight,
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
        "gapCatchingStructuralCandidates": [
            p["packageId"] for p in packages if p["gapCatchingStructuralCandidate"]
        ],
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
        "# 常青文档回刷来源清单",
        "",
        f"- 仓库：`{project['repository']}`",
        f"- Impl-Package contract：`{inventory['contractVersion']}`",
        f"- Contract preflight：`{inventory['contractPreflight']['status']}`",
        f"- 目标分支：`{project['targetBranch']}` -> `{project['targetBranchCommit'] or '未解析'}`",
        f"- 目标分支配置缺口：{'是' if inventory['targetBranchConfigGap'] else '否'}",
        f"- 任务包数量：{inventory['packageCount']}",
        f"- 未关闭 pending 登记：{inventory['pendingRegistrationCount']}",
        f"- 配置缺口（`_pending.md` 歧义/缺失）：{len(inventory['pendingConfigGaps'])}",
        f"- Pending 冷启动（需 owner 决定，非阻断）：{len(inventory['pendingColdStarts'])}",
        f"- Gap-catching 结构候选（尚未核验 Git reachability）：{len(inventory['gapCatchingStructuralCandidates'])}",
        f"- 任务包退役结构候选：{len(inventory['retirementStructuralCandidates'])}",
        f"- 需要人工 Gate 复核（mismatch/manual）：{len(inventory['manualGateReviewCandidates'])}",
        "",
        "| 任务包 | Gate 识别 | Gate 判决 | 适用于当前修订 | Design | Spec | 存在未关闭 pending 引用 | Gap-catching 结构候选 | 退役候选 | 人工 Gate 复核 | 原因 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in inventory["packages"]:
        lines.append(
            "| {package_id} | {recognition} | {resolution} | {applies} | {design} | {spec} | {referenced} | {gap} | {retire} | {manual} | {reason} |".format(
                package_id=row["packageId"],
                recognition=row["gateRecognition"] or "none",
                resolution=row["gateResolution"] or "none",
                applies=(
                    "是"
                    if row["gateAppliesToCurrentRevision"] is True
                    else "否"
                    if row["gateAppliesToCurrentRevision"] is False
                    else "未知"
                ),
                design="是" if row["hasDesign"] else "否",
                spec="是" if row["hasSpec"] else "否",
                referenced="是" if row["referencedInOpenPending"] else "否",
                gap="是" if row["gapCatchingStructuralCandidate"] else "否",
                retire="是" if row["retirementStructuralCandidate"] else "否",
                manual="是" if row["needsManualGateReview"] else "否",
                reason=(row["reason"] or "").replace("|", "\\|"),
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
