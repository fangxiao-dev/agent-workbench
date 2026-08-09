#!/usr/bin/env python3
"""Emit the minimum live Git and Impl-Package state needed for a handoff."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Any


def run(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def git(worktree: Path, *args: str) -> str:
    result = run(["git", *args], worktree)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout.strip()


def relative_path(value: str) -> str:
    raw = value.replace("\\", "/").strip()
    path = PurePosixPath(raw)
    if not raw or path.is_absolute() or ".." in path.parts:
        raise ValueError("--package-path must be repository-relative")
    return path.as_posix()


def dirty_paths(worktree: Path) -> list[str]:
    lines = git(worktree, "status", "--short", "--untracked-files=all").splitlines()
    paths: list[str] = []
    for line in lines:
        value = line[3:].strip() if len(line) >= 4 else line.strip()
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        paths.append(value.replace("\\", "/"))
    return paths


def package_status(worktree: Path, package_value: str) -> dict[str, Any]:
    package_relative = relative_path(package_value)
    package = (worktree / Path(*PurePosixPath(package_relative).parts)).resolve()
    try:
        package.relative_to(worktree)
    except ValueError as exc:
        raise ValueError("package path escapes worktree") from exc
    if not package.is_dir():
        raise ValueError(f"package does not exist: {package_relative}")
    validator = (
        Path(__file__).resolve().parents[3]
        / "plugin-marketplace"
        / "plugins"
        / "impl-package"
        / "scripts"
        / "impl_package_state.py"
    )
    result = run([sys.executable, str(validator), "--package", str(package), "status"], worktree)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or "package validation failed")
    return {"path": package_relative, "state": json.loads(result.stdout)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--package-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    worktree = Path(args.worktree).resolve(strict=True)
    head = git(worktree, "rev-parse", "HEAD")
    branch = git(worktree, "rev-parse", "--abbrev-ref", "HEAD")
    paths = dirty_paths(worktree)
    result: dict[str, Any] = {
        "worktree": str(worktree),
        "branch": branch,
        "head": head,
        "headMatchesExpected": None if args.expected_head is None else head.lower() == args.expected_head.lower(),
        "dirtyPaths": paths,
    }
    if args.package_path:
        result["package"] = package_status(worktree, args.package_path)
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, json.JSONDecodeError) as error:
        print(f"compact-anchor: {error}", file=sys.stderr)
        raise SystemExit(2) from error
