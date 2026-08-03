#!/usr/bin/env python3
"""Report Impl-Package contract status for Stable Docs Backfill.

Backfill deliberately does not understand package state or perform migration.
The canonical Impl-Package state engine owns contract detection. This module
only invokes its ``contract-status`` command and reports advisory drift. A
non-current package lowers trust in machine Gate evidence, but it does not
block an agent from reading package evidence during audit.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterable

from stable_docs_config import (
    ConfigError,
    expand_roots,
    load_repository_config,
    path_matches_ignore,
)


CONTRACT_VERSION = "3.2"
STATUS_VALUES = frozenset({"current", "upgradeRequired", "unsupportedFuture", "invalid"})
STATE_ENGINE = Path(__file__).resolve().parents[2] / "scripts" / "impl_package_state.py"


def _invalid_status(package: Path, reason: str) -> dict[str, Any]:
    return {
        "package": package.as_posix(),
        "status": "invalid",
        "contractVersion": None,
        "currentContractVersion": CONTRACT_VERSION,
        "reason": reason,
    }


def inspect_package(package: Path, *, state_engine: Path = STATE_ENGINE) -> dict[str, Any]:
    """Ask the canonical state engine for one package's contract status.

    The state engine may return a non-zero exit code for a non-current status.
    A valid JSON status is still consumed in that case; malformed or absent
    JSON is converted to ``invalid`` so callers know machine Gate evidence is
    untrusted and must inspect the package manually.
    """

    command = [
        sys.executable,
        str(state_engine),
        "--package",
        str(package),
        "contract-status",
    ]
    completed = subprocess.run(
        command,
        cwd=package,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    try:
        payload = json.loads(completed.stdout)
    except (json.JSONDecodeError, TypeError) as error:
        detail = completed.stderr.strip() or f"canonical status output is not JSON: {error}"
        return _invalid_status(package, detail)
    if not isinstance(payload, dict):
        return _invalid_status(package, "canonical status output must be a JSON object")
    status = payload.get("status")
    if status not in STATUS_VALUES:
        return _invalid_status(package, f"canonical status is unsupported: {status!r}")
    result = {
        "package": package.as_posix(),
        "status": status,
        "contractVersion": payload.get("contractVersion"),
        "currentContractVersion": payload.get("currentContractVersion", CONTRACT_VERSION),
    }
    if isinstance(payload.get("components"), dict):
        result["components"] = payload["components"]
    if payload.get("reason"):
        result["reason"] = payload["reason"]
    if completed.returncode != 0 and status == "current":
        result["status"] = "invalid"
        result["reason"] = completed.stderr.strip() or "canonical contract-status exited unsuccessfully"
    return result


def package_paths(project_root: Path, config: dict[str, Any]) -> list[Path]:
    """Enumerate implementation package directories using repository config."""

    packages: list[Path] = []
    seen: set[Path] = set()
    for implementations_root in expand_roots(project_root, config["implementations"]):
        for package in sorted(path for path in implementations_root.iterdir() if path.is_dir()):
            relative = package.relative_to(project_root).as_posix()
            if path_matches_ignore(relative, config["ignore"]) is not None:
                continue
            resolved = package.resolve()
            if resolved not in seen:
                seen.add(resolved)
                packages.append(resolved)
    return packages


def run_preflight(project_root: Path | str, config: dict[str, Any]) -> dict[str, Any]:
    """Inspect every configured package and return a non-blocking summary."""

    project = Path(project_root).resolve()
    statuses = [inspect_package(package) for package in package_paths(project, config)]
    advisories = [row for row in statuses if row["status"] != "current"]
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": "current" if not advisories else "advisory",
        "packageCount": len(statuses),
        "advisoryPackageCount": len(advisories),
        "packages": statuses,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project = args.project_root.resolve()
        config, _ = load_repository_config(project, args.config)
        result = run_preflight(project, config)
    except (ConfigError, OSError) as error:
        print(json.dumps({"contractVersion": CONTRACT_VERSION, "status": "invalid", "error": str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
