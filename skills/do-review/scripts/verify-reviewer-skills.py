from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = SCRIPT_DIR.parent / "references" / "reviewer-registry.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verify that requested do-review skills have readable canonical SKILL.md files."
    )
    parser.add_argument(
        "--workbench-root",
        type=Path,
        required=True,
        help="Root containing the skills directory.",
    )
    parser.add_argument(
        "--skills",
        nargs="+",
        default=[],
        help="Reviewer skill names to verify (default: code-review module-review).",
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Canonical path for a custom reviewer skill from the active skill catalog.",
    )
    return parser.parse_args()


def load_registry() -> dict[str, dict[str, object]]:
    return json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))


def verify_skill(root: Path, name: str, entry: dict[str, object]) -> Path:
    relative_path = entry["canonical_skill_path"]
    if not isinstance(relative_path, str):
        raise ValueError(f"{name}: canonical_skill_path must be a string")

    root = root.resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents:
        raise ValueError(f"{name}: canonical path escapes workbench root: {relative_path}")
    if not path.is_file():
        raise FileNotFoundError(f"{name}: missing canonical SKILL.md: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(f"{name}: unreadable canonical SKILL.md: {path}: {error}") from error

    if not re.search(rf"(?m)^name:\s*{re.escape(name)}\s*$", content):
        raise ValueError(f"{name}: frontmatter name does not match canonical path: {path}")
    return path


def verify_custom_skill(root: Path, value: str) -> tuple[str, Path]:
    name, separator, raw_path = value.partition("=")
    if not separator or not name or not raw_path:
        raise ValueError("--skill-path must use NAME=PATH")

    candidate = Path(raw_path)
    path = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"{name}: missing canonical SKILL.md: {path}")
    try:
        content = path.read_text(encoding="utf-8")
    except OSError as error:
        raise OSError(f"{name}: unreadable canonical SKILL.md: {path}: {error}") from error
    if not re.search(rf"(?m)^name:\s*{re.escape(name)}\s*$", content):
        raise ValueError(f"{name}: frontmatter name does not match canonical path: {path}")
    return name, path


def main() -> int:
    args = parse_args()
    registry = load_registry()
    errors: list[str] = []

    names = args.skills or (["code-review", "module-review"] if not args.skill_path else [])
    if not names and not args.skill_path:
        errors.append("no reviewer skills requested")

    for name in names:
        entry = registry.get(name)
        if entry is None:
            errors.append(f"{name}: no canonical path is registered")
            continue
        try:
            path = verify_skill(args.workbench_root, name, entry)
            print(f"OK {name}: {path}")
        except (OSError, ValueError) as error:
            errors.append(str(error))

    for value in args.skill_path:
        try:
            name, path = verify_custom_skill(args.workbench_root, value)
            print(f"OK {name}: {path}")
        except (OSError, ValueError) as error:
            errors.append(str(error))

    if errors:
        for error in errors:
            print(f"ERROR {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
