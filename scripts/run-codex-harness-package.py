#!/usr/bin/env python3
"""Validate, plan, and explicitly execute one parent stage from a package manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codex_harness_package import ManifestError, execute_stage, load_manifest, plan_summary, ready_stages


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path)
    parser.add_argument("--completed", default="", help="Comma-separated stage IDs already accepted by the integration parent.")
    parser.add_argument("--sensitive-root", action="append", default=[], help="Repository-relative sensitive source root; accepted only by on_demand stages.")
    parser.add_argument("--allow-sensitive-originals", action="store_true", help="Required together with --sensitive-root when executing an on_demand sensitive stage.")
    parser.add_argument("--execute", action="store_true", help="Run one parent stage through App Server. Omit for read-only planning.")
    parser.add_argument("--stage", help="Stage ID required with --execute.")
    parser.add_argument("--worktree", type=Path, help="Existing isolated Git worktree required with --execute.")
    parser.add_argument("--serial-handoff", type=Path, help="Optional committed-and-verified handoff JSON required to reuse a serial worktree.")
    parser.add_argument("--delivery-program-id", help="Delivery program identity bound to --serial-handoff.")
    parser.add_argument("--timeout-seconds", type=int)
    args = parser.parse_args()
    try:
        manifest = load_manifest(args.manifest, args.repository_root)
        completed = {item.strip() for item in args.completed.split(",") if item.strip()}
        if not args.execute:
            print(json.dumps(plan_summary(manifest, completed, tuple(args.sensitive_root)), ensure_ascii=False, indent=2))
            return 0
        if not args.stage or not args.worktree:
            raise ManifestError("--execute requires --stage and --worktree")
        if args.sensitive_root and not args.allow_sensitive_originals:
            raise ManifestError("--sensitive-root requires explicit --allow-sensitive-originals for execution")
        if (args.serial_handoff is None) != (args.delivery_program_id is None):
            raise ManifestError("--serial-handoff and --delivery-program-id must be supplied together")
        stage = next((item for item in manifest.stages if item.id == args.stage), None)
        if stage is None:
            raise ManifestError(f"unknown stage: {args.stage}")
        if stage not in ready_stages(manifest, completed):
            raise ManifestError(f"stage {args.stage} is not ready for the supplied completed set")
        handoff = json.loads(args.serial_handoff.read_text(encoding="utf-8")) if args.serial_handoff else None
        result = execute_stage(manifest, stage, args.worktree.resolve(), args.timeout_seconds or manifest.timeout_seconds, tuple(args.sensitive_root), serial_handoff=handoff, delivery_program_id=args.delivery_program_id)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] in {"passed", "needs_owner"} else 2
    except ManifestError as error:
        print(f"[X] {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
