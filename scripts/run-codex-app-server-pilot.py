#!/usr/bin/env python3
"""Thin scenario wrapper for the Codex Harness parent controller."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from codex_harness_controller import inspect_thread, run
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_controller import inspect_thread, run


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--scenario", choices=("smoke", "simple", "parallel", "ambiguous", "boundary", "timeout", "impl-package"), default="smoke")
    parser.add_argument("--inspect-thread")
    args = parser.parse_args()
    try:
        if args.inspect_thread:
            return inspect_thread(args.repository_root.resolve(), args.inspect_thread)
        return run(args.repository_root.resolve(), args.timeout_seconds, args.scenario)
    except Exception as error:
        print(f"[X] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
