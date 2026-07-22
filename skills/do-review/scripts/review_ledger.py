#!/usr/bin/env python3
"""Create and update the canonical do-review ledger in the user temp folder."""

from __future__ import annotations

import argparse
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


LEDGER_NAME = re.compile(r"^\d{10}-[a-z0-9]+(?:-[a-z0-9]+)*-[0-9a-f]{7}\.md$")


def ledger_directory() -> Path:
    return Path(os.environ.get("TEMP") or os.environ.get("TMP") or tempfile.gettempdir()).resolve() / "do-review"


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        raise ValueError("slug must contain at least one ASCII letter or digit")
    return slug


def validate_ledger_path(value: str) -> Path:
    path = Path(value).resolve()
    directory = ledger_directory()
    if path.parent != directory or not LEDGER_NAME.fullmatch(path.name):
        raise ValueError(f"ledger path must be a do-review temp ledger: {directory}\\<YYMMDDHHMM>-<slug>-<shortsha>.md")
    return path


def create(args: argparse.Namespace) -> int:
    directory = ledger_directory()
    directory.mkdir(parents=True, exist_ok=True)
    slug = slugify(args.slug)
    short_sha = args.head_sha.lower()[:7]
    if not re.fullmatch(r"[0-9a-f]{7}", short_sha):
        raise ValueError("head-sha must start with at least seven hexadecimal characters")
    timestamp = args.timestamp or datetime.now().strftime("%y%m%d%H%M")
    if not re.fullmatch(r"\d{10}", timestamp):
        raise ValueError("timestamp must use YYMMDDHHMM")
    path = directory / f"{timestamp}-{slug}-{short_sha}.md"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing ledger: {path}")
    content = f"""# do-review canonical ledger

- Ledger path: `{path}`
- Review slug: `{slug}`
- Created at (local): `{datetime.now().astimezone().isoformat(timespec='seconds')}`
- Resolved base SHA: `{args.base_sha}`
- Resolved head SHA: `{args.head_sha}`
- Mode: `{args.mode}`
- Round cap: `{args.round_cap}`
- Owner: `main-session`
- Status: `in-progress`

## Review rounds

| Round | Track verdicts | New accepted | Convergence note |
| --- | --- | --- | --- |

## Known findings ledger

| ID | Title | Severity | Classification | Source | Status | Evidence | Main-session decision |
| --- | --- | --- | --- | --- | --- | --- | --- |

## Verification and decisions

- Stop reason: `pending`
"""
    path.write_text(content, encoding="utf-8", newline="\n")
    print(path)
    return 0


def write(args: argparse.Namespace) -> int:
    path = validate_ledger_path(args.ledger)
    content = sys.stdin.read()
    if not content.strip():
        raise ValueError("refusing to write an empty ledger")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content.rstrip() + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)
    print(path)
    return 0


def show(args: argparse.Namespace) -> int:
    path = validate_ledger_path(args.ledger)
    sys.stdout.write(path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    create_parser = subparsers.add_parser("create", help="create a new canonical ledger")
    create_parser.add_argument("--slug", required=True)
    create_parser.add_argument("--base-sha", required=True)
    create_parser.add_argument("--head-sha", required=True)
    create_parser.add_argument("--mode", required=True)
    create_parser.add_argument("--round-cap", required=True)
    create_parser.add_argument("--timestamp", help="YYMMDDHHMM; intended for deterministic tests")
    create_parser.set_defaults(handler=create)

    write_parser = subparsers.add_parser("write", help="atomically replace an existing ledger from stdin")
    write_parser.add_argument("--ledger", required=True)
    write_parser.set_defaults(handler=write)

    show_parser = subparsers.add_parser("show", help="read an existing ledger")
    show_parser.add_argument("--ledger", required=True)
    show_parser.set_defaults(handler=show)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"review_ledger: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
