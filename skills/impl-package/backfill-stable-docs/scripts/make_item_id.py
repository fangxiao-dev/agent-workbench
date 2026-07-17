#!/usr/bin/env python3
"""Create a stable audit item ID from its durable identity fields."""

from __future__ import annotations

import argparse
import hashlib
import json
import re


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def make_item_id(source: str, destination: str | None, statement: str) -> str:
    payload = json.dumps(
        {
            "source": source.replace("\\", "/").strip(),
            "destination": (destination or "none").replace("\\", "/").strip(),
            "statement": normalize_text(statement),
        },
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "SDB-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--destination")
    parser.add_argument("--statement", required=True)
    args = parser.parse_args()
    print(make_item_id(args.source, args.destination, args.statement))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
