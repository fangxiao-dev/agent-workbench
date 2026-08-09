#!/usr/bin/env python3
"""Validate current implementation package state before stable-doc audit."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from stable_docs_config import ConfigError, expand_roots, load_repository_config, path_matches_ignore


STATE_ENGINE = Path(__file__).resolve().parents[2] / "scripts" / "impl_package_state.py"


def package_paths(project: Path, config: dict[str, Any]) -> list[Path]:
    result: list[Path] = []
    for root in expand_roots(project, config["implementations"]):
        for child in sorted(root.iterdir(), key=lambda item: item.name):
            if child.is_dir() and path_matches_ignore(child.relative_to(project).as_posix(), config["ignore"]) is None:
                result.append(child.resolve())
    return result


def inspect_package(package: Path) -> dict[str, Any]:
    completed = subprocess.run([sys.executable, str(STATE_ENGINE), "--package", str(package), "validate"], cwd=package, capture_output=True, text=True, check=False)
    if completed.returncode:
        return {"package": package.as_posix(), "status": "invalid", "reason": completed.stderr.strip()}
    return {"package": package.as_posix(), "status": "valid", "state": json.loads(completed.stdout)}


def run_preflight(project_root: Path | str, config: dict[str, Any]) -> dict[str, Any]:
    project = Path(project_root).resolve()
    rows = [inspect_package(path) for path in package_paths(project, config)]
    return {"status": "valid" if all(row["status"] == "valid" for row in rows) else "advisory", "packageCount": len(rows), "invalidPackageCount": sum(row["status"] == "invalid" for row in rows), "packages": rows}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--config", type=Path)
    args = parser.parse_args()
    try:
        config, _ = load_repository_config(args.project_root, args.config)
        payload = run_preflight(args.project_root, config)
    except (ConfigError, OSError) as error:
        print(json.dumps({"status": "invalid", "error": str(error)}))
        return 2
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
