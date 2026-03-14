"""Command-line entrypoint for simplified personal bootstrap workflows."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from agent_workbench.manifest import load_manifest
from agent_workbench.syncer import apply_manifest, pull_manifest, push_manifest, verify_manifest


def main() -> int:
    """Parse CLI arguments and dispatch bootstrap operations."""
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.handler(args)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level bootstrap CLI parser."""
    parser = argparse.ArgumentParser(prog="bootstrap")
    subparsers = parser.add_subparsers(dest="command", required=True)

    for name, handler in (("apply", handle_apply), ("verify", handle_verify), ("pull", handle_pull), ("push", handle_push)):
        command = subparsers.add_parser(name)
        command.add_argument("--target", required=True)
        if name == "push":
            command.add_argument("--skill", action="append", default=[])
        command.set_defaults(handler=handler)
    return parser


def handle_apply(args: argparse.Namespace) -> int:
    target = Path(args.target)
    manifest = load_manifest(target / "agent_assets.yaml")
    for line in apply_manifest(target, manifest):
        print(line)
    return 0


def handle_verify(args: argparse.Namespace) -> int:
    target = Path(args.target)
    manifest = load_manifest(target / "agent_assets.yaml")
    results = verify_manifest(target, manifest)
    for result in results:
        print(result.render())
    return 0 if all(result.status != "FAIL" for result in results) else 1


def handle_pull(args: argparse.Namespace) -> int:
    target = Path(args.target)
    manifest = load_manifest(target / "agent_assets.yaml")
    for line in pull_manifest(target, manifest):
        print(line)
    return 0


def handle_push(args: argparse.Namespace) -> int:
    target = Path(args.target)
    manifest = load_manifest(target / "agent_assets.yaml")
    for line in push_manifest(target, manifest, skill_names=args.skill):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
