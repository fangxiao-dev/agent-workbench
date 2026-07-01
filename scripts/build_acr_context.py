#!/usr/bin/env python3
"""Build a minimal Docker context for Azure Container Registry remote builds."""

from __future__ import annotations

import argparse
import fnmatch
import json
import os
import posixpath
import shutil
import shlex
import sys
import tempfile
from pathlib import Path


DEFAULT_ROOT_FILES = (
    ".dockerignore",
    "package.json",
    "package-lock.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "yarn.lock",
    "bun.lockb",
    "pyproject.toml",
    "uv.lock",
    "requirements.txt",
    "README.md",
    "tsconfig.json",
    "turbo.json",
    "nx.json",
)

DEFAULT_EXCLUDES = (
    ".git",
    ".git/**",
    ".agents",
    ".agents/**",
    ".claude",
    ".claude/**",
    ".codex",
    ".codex/**",
    ".gemini",
    ".gemini/**",
    ".worktrees",
    ".worktrees/**",
    "node_modules",
    "node_modules/**",
    ".turbo",
    ".turbo/**",
    ".next",
    ".next/**",
    ".acr-context",
    ".acr-context/**",
    "dist",
    "dist/**",
    "coverage",
    "coverage/**",
    ".coverage",
    ".pytest_cache",
    ".pytest_cache/**",
    ".mypy_cache",
    ".mypy_cache/**",
    ".ruff_cache",
    ".ruff_cache/**",
    "__pycache__",
    "__pycache__/**",
    "playwright-report",
    "playwright-report/**",
    "test-results",
    "test-results/**",
    "tmp",
    "tmp/**",
    "temp",
    "temp/**",
    ".venv",
    ".venv/**",
    "venv",
    "venv/**",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a minimal Docker context for az acr build."
    )
    parser.add_argument(
        "--repo-root",
        default=".",
        help="Repository root to copy from. Defaults to the current directory.",
    )
    parser.add_argument(
        "--dockerfile",
        default="Dockerfile",
        help="Dockerfile path, relative to repo root unless absolute.",
    )
    parser.add_argument(
        "--output-dir",
        help="Directory to create or replace with the generated context. Defaults to a temp directory.",
    )
    parser.add_argument(
        "--include",
        action="append",
        default=[],
        help="Additional file, directory, or glob to include. Can be repeated.",
    )
    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        help="Additional exclude glob, relative to repo root. Can be repeated.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print files that would be copied without writing a context.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow replacing an existing output directory.",
    )
    return parser.parse_args()


def normalize_relative(path: str) -> str:
    normalized = path.replace("\\", "/").strip()
    normalized = posixpath.normpath(normalized)
    if normalized in ("", "."):
        return "."
    if normalized.startswith("../") or normalized == ".." or posixpath.isabs(normalized):
        raise ValueError(f"path escapes the repository root: {path}")
    return normalized


def is_excluded(relative_path: str, patterns: tuple[str, ...]) -> bool:
    relative_path = relative_path.replace("\\", "/")
    parts = relative_path.split("/")
    for pattern in patterns:
        if fnmatch.fnmatch(relative_path, pattern):
            return True
        if "/" not in pattern and pattern in parts:
            return True
    return False


def join_continued_lines(lines: list[str]) -> list[str]:
    joined: list[str] = []
    current = ""
    for raw in lines:
        line = raw.rstrip()
        if not current:
            current = line
        else:
            current += " " + line.lstrip()
        if current.endswith("\\"):
            current = current[:-1].rstrip()
            continue
        joined.append(current)
        current = ""
    if current:
        joined.append(current)
    return joined


def parse_copy_sources(dockerfile: Path) -> set[str]:
    sources: set[str] = set()
    lines = join_continued_lines(dockerfile.read_text(encoding="utf-8").splitlines())
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if " " not in stripped:
            continue
        instruction, rest = stripped.split(None, 1)
        if instruction.upper() not in {"COPY", "ADD"}:
            continue

        rest = rest.strip()
        if rest.startswith("["):
            try:
                values = json.loads(rest)
            except json.JSONDecodeError:
                continue
            if isinstance(values, list) and len(values) >= 2:
                for value in values[:-1]:
                    if isinstance(value, str):
                        maybe_add_source(sources, value)
            continue

        try:
            tokens = shlex.split(rest, posix=True)
        except ValueError:
            continue
        if len(tokens) < 2:
            continue

        context_tokens: list[str] = []
        skip_instruction = False
        for token in tokens:
            if token.startswith("--from="):
                skip_instruction = True
                break
            if token.startswith("--"):
                continue
            context_tokens.append(token)
        if skip_instruction or len(context_tokens) < 2:
            continue
        for value in context_tokens[:-1]:
            maybe_add_source(sources, value)
    return sources


def maybe_add_source(sources: set[str], value: str) -> None:
    if "://" in value or value.startswith("$"):
        return
    try:
        sources.add(normalize_relative(value))
    except ValueError:
        return


def expand_include(repo_root: Path, pattern: str, excludes: tuple[str, ...]) -> set[str]:
    normalized = normalize_relative(pattern)
    matches: set[str] = set()
    if any(char in normalized for char in "*?["):
        candidates = repo_root.glob(normalized)
    else:
        candidates = [repo_root / normalized]
    for candidate in candidates:
        if not candidate.exists():
            continue
        if candidate.is_dir():
            for child in candidate.rglob("*"):
                if child.is_file():
                    rel = child.relative_to(repo_root).as_posix()
                    if not is_excluded(rel, excludes):
                        matches.add(rel)
        elif candidate.is_file():
            rel = candidate.relative_to(repo_root).as_posix()
            if not is_excluded(rel, excludes):
                matches.add(rel)
    return matches


def collect_files(
    repo_root: Path,
    dockerfile: Path,
    includes: list[str],
    excludes: tuple[str, ...],
) -> list[str]:
    selected: set[str] = set()
    selected.add(dockerfile.relative_to(repo_root).as_posix())

    for root_file in DEFAULT_ROOT_FILES:
        path = repo_root / root_file
        if path.is_file() and not is_excluded(root_file, excludes):
            selected.add(root_file)

    for source in parse_copy_sources(dockerfile):
        selected.update(expand_include(repo_root, source, excludes))

    for include in includes:
        selected.update(expand_include(repo_root, include, excludes))

    return sorted(selected)


def prepare_output_dir(output_dir: Path | None, force: bool) -> Path:
    if output_dir is None:
        return Path(tempfile.mkdtemp(prefix="acr-context-")).resolve()
    output_dir = output_dir.resolve()
    if output_dir.exists():
        if not force:
            raise FileExistsError(
                f"output directory already exists: {output_dir} (use --force to replace it)"
            )
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    return output_dir


def copy_files(repo_root: Path, output_dir: Path, files: list[str]) -> None:
    for relative in files:
        src = repo_root / relative
        dst = output_dir / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    dockerfile = Path(args.dockerfile)
    if not dockerfile.is_absolute():
        dockerfile = repo_root / dockerfile
    dockerfile = dockerfile.resolve()

    if not repo_root.is_dir():
        print(f"repo root does not exist: {repo_root}", file=sys.stderr)
        return 2
    if not dockerfile.is_file():
        print(f"Dockerfile does not exist: {dockerfile}", file=sys.stderr)
        return 2
    try:
        dockerfile.relative_to(repo_root)
    except ValueError:
        print("Dockerfile must be inside the repository root.", file=sys.stderr)
        return 2

    output_dir_arg = Path(args.output_dir).resolve() if args.output_dir else None
    output_excludes: tuple[str, ...] = ()
    if output_dir_arg is not None:
        try:
            output_rel = output_dir_arg.relative_to(repo_root).as_posix()
            output_excludes = (output_rel, f"{output_rel}/**")
        except ValueError:
            output_excludes = ()

    excludes = tuple(DEFAULT_EXCLUDES + output_excludes + tuple(args.exclude))
    files = collect_files(repo_root, dockerfile, args.include, excludes)

    if args.dry_run:
        for relative in files:
            print(relative)
        print(f"Would copy {len(files)} file(s).", file=sys.stderr)
        return 0

    try:
        output_dir = prepare_output_dir(
            output_dir_arg,
            args.force,
        )
    except FileExistsError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    copy_files(repo_root, output_dir, files)
    print(output_dir)
    print(f"Copied {len(files)} file(s) into {output_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
