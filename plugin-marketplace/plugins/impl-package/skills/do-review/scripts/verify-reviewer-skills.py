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
        "--plugin-root",
        "--workbench-root",
        dest="plugin_root",
        type=Path,
        required=True,
        help="Impl-Package plugin root containing the flat skills directory.",
    )
    parser.add_argument(
        "--skills",
        nargs="+",
        default=None,
        help="Reviewer skill names to verify. Omit to verify registry default_tracks.",
    )
    parser.add_argument(
        "--skill-path",
        action="append",
        default=[],
        metavar="NAME=PATH",
        help="Canonical path for a custom reviewer skill from the active skill catalog.",
    )
    return parser.parse_args()


def load_registry() -> dict[str, object]:
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if not isinstance(registry, dict):
        raise ValueError("reviewer registry must be a JSON object")
    return registry


def registry_reviewers(registry: dict[str, object]) -> dict[str, dict[str, object]]:
    reviewers = registry.get("reviewers")
    if not isinstance(reviewers, dict):
        raise ValueError("reviewer registry reviewers must be an object")
    invalid = [name for name, entry in reviewers.items() if not isinstance(name, str) or not isinstance(entry, dict)]
    if invalid:
        raise ValueError("reviewer registry reviewers must map names to objects")
    return reviewers


def registry_default_skill_names(registry: dict[str, object]) -> list[str]:
    tracks = registry.get("default_tracks")
    if not isinstance(tracks, list) or not tracks:
        raise ValueError("reviewer registry default_tracks must be a non-empty array")

    names: list[str] = []
    for index, track in enumerate(tracks, start=1):
        if not isinstance(track, dict):
            raise ValueError(f"default track {index} must be an object")
        label = track.get("label")
        name = track.get("skill")
        if not isinstance(label, str) or not label:
            raise ValueError(f"default track {index} must have a non-empty label")
        if not isinstance(name, str) or not name:
            raise ValueError(f"default track {index} must have a non-empty skill")
        if name in names:
            raise ValueError(f"default_tracks contains duplicate reviewer: {name}")
        names.append(name)
    return names


def selected_registry_names(
    registry: dict[str, object], requested_names: list[str] | None, custom_paths: list[str]
) -> list[str]:
    if requested_names is not None:
        return requested_names
    return [] if custom_paths else registry_default_skill_names(registry)


def verify_skill(root: Path, name: str, entry: dict[str, object]) -> Path:
    relative_path = entry["canonical_skill_path"]
    if not isinstance(relative_path, str):
        raise ValueError(f"{name}: canonical_skill_path must be a string")

    root = root.resolve()
    path = (root / relative_path).resolve()
    if root not in path.parents:
        raise ValueError(f"{name}: canonical path escapes plugin root: {relative_path}")
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
    root = root.resolve()
    if path != root and root not in path.parents:
        raise ValueError(f"{name}: canonical path escapes plugin root: {raw_path}")
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
    errors: list[str] = []

    try:
        registry = load_registry()
        reviewers = registry_reviewers(registry)
        names = selected_registry_names(registry, args.skills, args.skill_path)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 1
    if not names and not args.skill_path:
        errors.append("no reviewer skills requested")

    for name in names:
        entry = reviewers.get(name)
        if entry is None:
            errors.append(f"{name}: no canonical path is registered")
            continue
        try:
            path = verify_skill(args.plugin_root, name, entry)
            print(f"OK {name}: {path}")
        except (OSError, ValueError) as error:
            errors.append(str(error))

    for value in args.skill_path:
        try:
            name, path = verify_custom_skill(args.plugin_root, value)
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
