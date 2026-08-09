#!/usr/bin/env python3
"""Create a readable Stable Docs item ID from source path and local delta ID."""

from __future__ import annotations

import argparse
from pathlib import PurePosixPath


def make_item_id(source: str, delta_id: str) -> str:
    path = PurePosixPath(source.replace("\\", "/").strip())
    if path.is_absolute() or ".." in path.parts or str(path) in {"", "."}:
        raise ValueError("source must be repository-relative")
    clean = delta_id.strip()
    if not clean or any(character.isspace() for character in clean):
        raise ValueError("delta-id must be non-empty and contain no whitespace")
    return f"{path.as_posix()}::{clean}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--delta-id", required=True)
    args = parser.parse_args()
    print(make_item_id(args.source, args.delta_id))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
