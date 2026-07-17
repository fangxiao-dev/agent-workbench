#!/usr/bin/env python3
"""Create a draft Harness adapter and readiness report from an Impl-Package."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_harness_prepare import PrepareError, prepare_adapter


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--source-ref", required=True)
    parser.add_argument("--package", required=True, help="Repository-relative Impl-Package path.")
    parser.add_argument("--parent-profile", required=True, help="Path stored in the generated manifest, relative to its future location or absolute.")
    parser.add_argument("--output", type=Path, help="Write the generated draft manifest here; otherwise print it.")
    parser.add_argument("--readiness-output", type=Path, help="Write JSON readiness evidence here; otherwise print it to stderr.")
    parser.add_argument("--timeout-seconds", type=int, default=1800)
    parser.add_argument("--max-parallel-parents", type=int, default=2)
    args = parser.parse_args()
    try:
        manifest, readiness = prepare_adapter(args.repository_root, args.source_ref, args.package, args.parent_profile, args.timeout_seconds, args.max_parallel_parents)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(manifest, encoding="utf-8")
        else:
            print(manifest, end="")
        readiness_text = json.dumps(readiness, ensure_ascii=False, indent=2)
        if args.readiness_output:
            args.readiness_output.parent.mkdir(parents=True, exist_ok=True)
            args.readiness_output.write_text(readiness_text + "\n", encoding="utf-8")
        else:
            print(readiness_text, file=sys.stderr)
        return 0
    except PrepareError as error:
        print(f"[X] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
