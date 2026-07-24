#!/usr/bin/env python3
"""Route a discussion mode and participant set to the existing workflows."""
from __future__ import annotations

import argparse
from pathlib import Path
import tempfile

import blind_opening
import blind_opening_then_ledger
import discuss_orchestrator as orchestrator


DEFAULT_AGENTS = ("codex", "claude")
FULL_AGENTS = ("codex", "claude", "grok")


def resolve_agents(value: str) -> list[str]:
    if value.strip().lower() == "full":
        return list(FULL_AGENTS)
    agents = orchestrator.parse_agents(value)
    if len(agents) != 2 or len(set(agents)) != 2:
        raise ValueError("--agents must be full or exactly two distinct agents: codex, claude, grok")
    return agents


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Route Ledger, Blind Opening, or Blind Opening + Ledger")
    parser.add_argument("--mode", choices=["ledger", "blind", "combined"], default="ledger", help="workflow mode (default: ledger)")
    parser.add_argument("--root", default=".", help="target project root")
    parser.add_argument("--topic", required=True, help="topic or target document")
    parser.add_argument("--slug", help="artifact or ledger slug")
    parser.add_argument("--agents", default=",".join(DEFAULT_AGENTS), help="full, or exactly two of: codex, claude, grok")
    parser.add_argument("--max-rounds", type=int, default=5, help="full participant cycles for ledger/combined (default 5)")
    parser.add_argument("--timeout-s", type=int, default=300, help="per-agent timeout in seconds")
    parser.add_argument("--output-dir", default=str(Path(tempfile.gettempdir()) / "discuss-ledger"), help="Blind Opening artifact directory")
    parser.add_argument("--fake", action="store_true", help="use deterministic fake participants")
    return parser


def downstream_args(args: argparse.Namespace, agents: list[str]) -> list[str]:
    common = ["--root", args.root, "--topic", args.topic, "--agents", ",".join(agents), "--timeout-s", str(args.timeout_s)]
    if args.slug:
        common.extend(["--slug", args.slug])
    if args.fake:
        common.append("--fake")
    if args.mode == "ledger":
        return [*common, "--max-rounds", str(args.max_rounds)]
    if args.mode == "blind":
        return [*common, "--output-dir", args.output_dir]
    return [*common, "--max-rounds", str(args.max_rounds), "--output-dir", args.output_dir]


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        agents = resolve_agents(args.agents)
        forwarded = downstream_args(args, agents)
        if args.mode == "ledger":
            return orchestrator.main(forwarded)
        if args.mode == "blind":
            return blind_opening.main(forwarded)
        return blind_opening_then_ledger.main(forwarded)
    except ValueError as exc:
        build_parser().error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
