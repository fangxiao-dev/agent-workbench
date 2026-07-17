#!/usr/bin/env python3
"""Run the Impl-Package contract preflight used by backfill.

Backfill deliberately does not understand package state or perform migration.
The canonical Impl-Package state engine owns contract detection.  This module
only invokes its ``contract-status`` command, reports the result, and blocks a
read-only backfill when any package is not on the current contract.
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


class ContractPreflightError(RuntimeError):
    """Raised when read-only backfill cannot trust package contract state."""

    def __init__(self, message: str, statuses: list[dict[str, Any]] | None = None) -> None:
        super().__init__(message)
        self.statuses = statuses or []


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

    The state engine may return a non-zero exit code for a blocked status.  A
    valid JSON status is still consumed in that case; malformed or absent JSON
    is converted to ``invalid`` so callers fail closed.
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
    """Inspect every configured package and return a machine-readable summary."""

    project = Path(project_root).resolve()
    statuses = [inspect_package(package) for package in package_paths(project, config)]
    blocked = [row for row in statuses if row["status"] != "current"]
    overall = "current" if not blocked else (
        "upgradeRequired"
        if any(row["status"] == "upgradeRequired" for row in blocked)
        else "invalid"
    )
    return {
        "contractVersion": CONTRACT_VERSION,
        "status": overall,
        "packageCount": len(statuses),
        "blockedPackageCount": len(blocked),
        "packages": statuses,
    }


def require_current(project_root: Path | str, config: dict[str, Any]) -> dict[str, Any]:
    """Return preflight data or stop before any read-only backfill work."""

    result = run_preflight(project_root, config)
    if result["status"] != "current":
        blocked = [
            f"{Path(row['package']).name}: {row.get('status')}"
            for row in result["packages"]
            if row.get("status") != "current"
        ]
        raise ContractPreflightError(
            "contract preflight blocked backfill; upgrade and validate these packages first: "
            + ", ".join(blocked),
            result["packages"],
        )
    return result


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
    except (ConfigError, OSError, ContractPreflightError) as error:
        print(json.dumps({"contractVersion": CONTRACT_VERSION, "status": "invalid", "error": str(error)}))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result["status"] == "current" else 2


if __name__ == "__main__":
    raise SystemExit(main())
