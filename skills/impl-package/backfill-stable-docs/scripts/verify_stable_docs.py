#!/usr/bin/env python3
"""Run Stable Docs Backfill verification checks (backfill output contract 3.2)."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable
from urllib.parse import unquote

from collect_sources import CollectorError, collect_inventory
from contract_preflight import CONTRACT_VERSION, run_preflight
from stable_docs_config import (
    ConfigError,
    discover_pending_paths,
    load_repository_config,
    resolve_target_branch,
)


LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
VALID_DISPOSITIONS = {"candidate", "already-covered", "conflict", "no-delta"}
VALID_ORIGINS = {"pending-registry", "gap-catching"}


class VerificationError(RuntimeError):
    """Raised for a failed verification check."""


def _check_contract_preflight(project: Path, config: dict[str, Any]) -> str:
    result = run_preflight(project, config)
    return (
        f"contract {result['contractVersion']} inspected for {result['packageCount']} package(s); "
        f"{result['advisoryPackageCount']} contract drift advisory package(s)"
    )


def _slug(value: str) -> str:
    value = re.sub(r"[^\w\- ]", "", value.strip().lower(), flags=re.UNICODE)
    return re.sub(r"\s+", "-", value)


def _markdown_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".md" else []
    if path.is_dir():
        return sorted(item for item in path.rglob("*.md") if item.is_file())
    return []


def _pattern_targets(project: Path, pattern: str) -> list[Path]:
    if any(ch in pattern for ch in "*?["):
        return sorted(project.glob(pattern))
    candidate = (project / pattern).resolve()
    return [candidate] if candidate.exists() else []


def _check_paths(project: Path, config: dict[str, Any]) -> str:
    patterns = [
        *config["implementations"],
        *config["stableDocs"]["systemKnowledge"],
        *config["stableDocs"]["contextKnowledge"],
        *config["stableDocs"]["moduleKnowledge"],
    ]
    missing = [pattern for pattern in patterns if not _pattern_targets(project, pattern)]
    if missing:
        raise VerificationError("configured paths do not match any file/directory: " + ", ".join(missing))
    return f"{len(patterns)} configured path patterns matched at least one target"


def _check_target_branch(project: Path, config: dict[str, Any]) -> str:
    try:
        commit = resolve_target_branch(project, config["targetBranch"])
    except ConfigError as error:
        raise VerificationError(str(error)) from error
    return f"targetBranch {config['targetBranch']} resolved to {commit}"


def _check_pending_discovery(project: Path, config: dict[str, Any]) -> str:
    entries = discover_pending_paths(project, config)
    gaps = [entry for entry in entries if entry["status"] in {"missing", "ambiguous"}]
    cold_starts = [entry for entry in entries if entry["status"] == "cold-start"]
    if gaps:
        detail = "; ".join(
            f"{entry['stableDocsLayer']}:{','.join(entry['stableDocsRoots'])}: {entry['status']}"
            for entry in gaps
        )
        raise VerificationError(f"_pending.md discovery has {len(gaps)} config gap(s): {detail}")
    resolved = sum(1 for entry in entries if entry["status"] == "ok")
    return f"{resolved} stable authority roots resolved; {len(cold_starts)} cold-start owner decision(s)"


def _check_links(project: Path, config: dict[str, Any]) -> str:
    failures: list[str] = []
    checked = 0
    roots = [
        *config["stableDocs"]["systemKnowledge"],
        *config["stableDocs"]["contextKnowledge"],
        *config["stableDocs"]["moduleKnowledge"],
    ]
    markdown_files: list[Path] = []
    for pattern in roots:
        for target in _pattern_targets(project, pattern):
            markdown_files.extend(_markdown_files(target))
    for markdown in sorted(set(markdown_files)):
        text = markdown.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            raw = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
            if not raw or raw.startswith(("http://", "https://", "mailto:")):
                continue
            path_part, _, anchor = unquote(raw).partition("#")
            target = markdown if not path_part else (markdown.parent / path_part).resolve()
            try:
                target.relative_to(project)
            except ValueError:
                failures.append(f"{markdown.relative_to(project)} -> {raw} escapes project")
                continue
            checked += 1
            if not target.exists():
                failures.append(f"{markdown.relative_to(project)} -> {raw} missing target")
                continue
            if anchor and target.is_file() and target.suffix.lower() == ".md":
                headings = {
                    _slug(line_match.group(1))
                    for line in target.read_text(encoding="utf-8").splitlines()
                    if (line_match := HEADING_RE.match(line))
                }
                if anchor.lower() not in headings:
                    failures.append(f"{markdown.relative_to(project)} -> {raw} missing anchor")
    if failures:
        raise VerificationError("; ".join(failures[:20]))
    return f"{checked} local Markdown links/anchors resolved"


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError(f"{label} must be readable JSON: {path}") from error
    if not isinstance(payload, dict):
        raise VerificationError(f"{label} must contain a JSON object")
    return payload


def _check_audit(audit: dict[str, Any] | None) -> str:
    if audit is None:
        return "audit JSON not requested"
    if audit.get("contractVersion") != CONTRACT_VERSION or audit.get("mode") != "audit":
        raise VerificationError(
            f"audit JSON must use contractVersion {CONTRACT_VERSION} and mode audit"
        )
    items = audit.get("items")
    if not isinstance(items, list):
        raise VerificationError("audit items must be an array")
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise VerificationError(f"audit items[{index}] must be an object")
        origin = item.get("origin")
        if origin not in VALID_ORIGINS:
            raise VerificationError(f"audit items[{index}] has invalid origin: {origin!r}")
        if origin == "pending-registry" and not item.get("pendingRef"):
            raise VerificationError(f"audit items[{index}] origin=pending-registry requires pendingRef")
        if item.get("disposition") not in VALID_DISPOSITIONS:
            raise VerificationError(f"audit items[{index}] has invalid disposition")
        if not isinstance(item.get("source"), str) or not isinstance(item.get("statement"), str):
            raise VerificationError(f"audit items[{index}] lacks source or statement")
    for field in ("pendingClosures", "gapCatchingCandidates", "retirementCandidates", "blockers"):
        if not isinstance(audit.get(field), list):
            raise VerificationError(f"audit {field} must be an array")
    return f"{len(items)} audit items use valid origin/disposition values"


def _check_inventory_candidates(project: Path, config_path: Path | None) -> str:
    inventory = collect_inventory(project_root=project, config_path=config_path)
    recognition_counts = {
        kind: sum(1 for row in inventory["packages"] if row["gateRecognition"] == kind)
        for kind in ("indexed", "mismatch", "manual")
    }
    return (
        f"{inventory['packageCount']} packages enumerated; "
        f"indexed={recognition_counts['indexed']}, mismatch={recognition_counts['mismatch']}, "
        f"manual={recognition_counts['manual']}; "
        f"{len(inventory['contractAdvisoryPackages'])} contract drift advisory package(s); "
        f"{len(inventory['gapCatchingStructuralCandidates'])} gap-catching structural candidates pending Git reachability review; "
        f"{len(inventory['retirementStructuralCandidates'])} Package Retirement structural candidates; "
        f"{len(inventory['manualGateReviewCandidates'])} need manual gate.md review (mismatch/manual)"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--audit-json", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        project = args.project_root.resolve()
        config, metadata = load_repository_config(project, args.config)
        audit = (
            _load_json(args.audit_json.resolve(), "audit JSON")
            if args.audit_json is not None
            else None
        )
    except (ConfigError, VerificationError) as error:
        sys.stdout.write(json.dumps({"passed": False, "error": str(error)}, indent=2) + "\n")
        return 2

    checks: list[tuple[str, Callable[[], str]]] = [
        ("contract-preflight", lambda: _check_contract_preflight(project, config)),
        ("configured-paths", lambda: _check_paths(project, config)),
        ("target-branch", lambda: _check_target_branch(project, config)),
        ("pending-discovery", lambda: _check_pending_discovery(project, config)),
        ("canonical-links", lambda: _check_links(project, config)),
        ("audit-contract", lambda: _check_audit(audit)),
        ("inventory-candidates", lambda: _check_inventory_candidates(project, args.config)),
    ]
    results: list[dict[str, str]] = []
    for name, check in checks:
        try:
            results.append({"check": name, "result": "passed", "detail": check()})
        except (ConfigError, VerificationError, CollectorError, OSError, UnicodeError) as error:
            results.append({"check": name, "result": "failed", "detail": str(error)})
    failed = sum(1 for result in results if result["result"] == "failed")
    payload = {
        "contractVersion": CONTRACT_VERSION,
        "configSha256": metadata["sha256"],
        "passed": failed == 0,
        "checks": results,
        "summary": {"total": len(results), "passed": len(results) - failed, "failed": failed},
    }
    sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
