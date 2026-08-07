#!/usr/bin/env python3
"""Verify explicit Stable Docs paths, links, audit shape, and package inventory."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from collect_sources import CollectorError, collect_inventory
from stable_docs_config import ConfigError, load_repository_config, resolve_project_path, resolve_target_branch


LINK_RE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^#{1,6}\s+(.+?)\s*#*\s*$")
VALID_DISPOSITIONS = {"candidate", "already-covered", "conflict", "no-delta"}


class VerificationError(RuntimeError):
    pass


def _markdown_files(path: Path) -> list[Path]:
    if path.is_file():
        return [path] if path.suffix.lower() == ".md" else []
    result: list[Path] = []
    if path.is_dir():
        for current, directories, files in os.walk(path):
            directories.sort()
            for name in sorted(files):
                candidate = Path(current) / name
                if candidate.suffix.lower() == ".md":
                    result.append(candidate)
    return result


def _slug(value: str) -> str:
    return re.sub(r"\s+", "-", re.sub(r"[^\w\- ]", "", value.strip().lower()))


def _check_paths(project: Path, config: dict[str, Any]) -> str:
    # Pending is optional and may be empty; done is a disposition ledger that may not exist yet.
    values = [
        *config["implementations"],
        *config["stableDocs"]["systemKnowledge"],
        *config["stableDocs"]["contextKnowledge"],
        *config["stableDocs"]["moduleKnowledge"],
    ]
    missing = [value for value in values if not resolve_project_path(project, value).exists()]
    if missing:
        raise VerificationError("configured paths are missing: " + ", ".join(missing))
    return f"{len(values)} explicit paths exist"


def _check_links(project: Path, config: dict[str, Any]) -> str:
    failures: list[str] = []
    checked = 0
    values = [*config["stableDocs"]["systemKnowledge"], *config["stableDocs"]["contextKnowledge"], *config["stableDocs"]["moduleKnowledge"]]
    for value in values:
        for markdown in _markdown_files(resolve_project_path(project, value)):
            text = markdown.read_text(encoding="utf-8")
            for match in LINK_RE.finditer(text):
                raw = match.group(1).strip().split(maxsplit=1)[0].strip("<>")
                if not raw or raw.startswith(("http://", "https://", "mailto:")):
                    continue
                path_value, _, anchor = unquote(raw).partition("#")
                target = markdown if not path_value else (markdown.parent / path_value).resolve()
                try:
                    target.relative_to(project)
                except ValueError:
                    failures.append(f"{markdown.relative_to(project)} -> {raw} escapes repository")
                    continue
                checked += 1
                if not target.exists():
                    failures.append(f"{markdown.relative_to(project)} -> {raw} missing")
                elif anchor and target.is_file() and target.suffix.lower() == ".md":
                    headings = {_slug(found.group(1)) for line in target.read_text(encoding="utf-8").splitlines() if (found := HEADING_RE.match(line))}
                    if anchor.lower() not in headings:
                        failures.append(f"{markdown.relative_to(project)} -> {raw} missing anchor")
    if failures:
        raise VerificationError("; ".join(failures[:20]))
    return f"{checked} local links resolved"


def _check_audit(path: Path | None) -> str:
    if path is None:
        return "audit JSON not requested"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise VerificationError("audit JSON must be readable") from error
    if payload.get("mode") != "audit" or not isinstance(payload.get("items"), list):
        raise VerificationError("audit JSON must contain mode=audit and items")
    for index, item in enumerate(payload["items"]):
        if not isinstance(item, dict) or item.get("disposition") not in VALID_DISPOSITIONS or not isinstance(item.get("id"), str):
            raise VerificationError(f"audit items[{index}] is invalid")
    return f"{len(payload['items'])} audit items are valid"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    parser.add_argument("--audit-json", type=Path)
    args = parser.parse_args()
    try:
        project = args.project_root.resolve()
        config, metadata = load_repository_config(project, args.config)
        checks = [
            ("configured-paths", lambda: _check_paths(project, config)),
            ("target-branch", lambda: f"target resolves to {resolve_target_branch(project, config['targetBranch'])}"),
            ("canonical-links", lambda: _check_links(project, config)),
            ("audit", lambda: _check_audit(args.audit_json.resolve() if args.audit_json else None)),
            ("inventory", lambda: f"{collect_inventory(project, args.config)['packageCount']} packages enumerated"),
        ]
        results = []
        for name, check in checks:
            try:
                results.append({"check": name, "result": "passed", "detail": check()})
            except (ConfigError, CollectorError, VerificationError, OSError) as error:
                results.append({"check": name, "result": "failed", "detail": str(error)})
        failed = sum(row["result"] == "failed" for row in results)
        payload = {"config": metadata, "passed": failed == 0, "checks": results, "summary": {"total": len(results), "passed": len(results) - failed, "failed": failed}}
    except (ConfigError, OSError) as error:
        payload = {"passed": False, "error": str(error)}
        failed = 1
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
