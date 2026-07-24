"""Compose Blind Opening with the existing Discuss Ledger workflow."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import tempfile

import blind_opening
import discuss_orchestrator as orchestrator


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Blind Opening, then normal Discuss Ledger")
    parser.add_argument("--root", default=".", help="target project root")
    parser.add_argument("--topic", required=True, help="topic or target document")
    parser.add_argument("--slug", help="shared result and ledger slug")
    parser.add_argument("--agents", default="codex,claude", help="comma list: codex, claude, grok")
    parser.add_argument("--max-rounds", type=int, default=5, help="full participant cycles (default 5)")
    parser.add_argument("--timeout-s", type=int, default=300, help="per agent timeout in seconds")
    parser.add_argument("--output-dir", default=str(Path(tempfile.gettempdir()) / "discuss-ledger"))
    parser.add_argument("--fake", action="store_true", help="use deterministic fake participants")
    return parser


def run_combined(*, root: Path, topic: str, slug: str, agents: list[str], max_rounds: int, timeout_s: int, output_dir: Path, fake: bool) -> int:
    ledger_path = root / orchestrator.ledger.DEFAULT_DIR / f"discuss-{slug}.md"
    if ledger_path.exists():
        raise blind_opening.BlindOpeningError(f"LEDGER_EXISTS: {ledger_path}")
    opening = blind_opening.run_blind_opening(
        root=root,
        topic=topic,
        slug=slug,
        agents=agents,
        timeout_s=timeout_s,
        output_dir=output_dir,
        fake=fake,
    )
    print(f"Blind Opening Markdown: {opening['artifacts']['markdown']}")
    orchestrator.ledger.init_ledger(root=root, topic=topic, slug=slug, initiator=agents[0], participants=agents)
    for point in opening["initial_points"]:
        orchestrator.ledger.add_point(root=root, slug=slug, author=agents[0], summary=point["summary"], body=point["body"])
    return orchestrator.orchestrate(
        root=root,
        topic=topic,
        slug=slug,
        agents=agents,
        max_rounds=max_rounds,
        fake=fake,
        timeout_s=timeout_s,
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        root, topic = orchestrator.resolve_root_and_topic(args.root, args.topic)
        agents = orchestrator.parse_agents(args.agents)
        slug = args.slug or orchestrator.ledger.derive_slug(topic)
        return run_combined(
            root=root,
            topic=topic,
            slug=slug,
            agents=agents,
            max_rounds=args.max_rounds,
            timeout_s=args.timeout_s,
            output_dir=Path(args.output_dir),
            fake=args.fake,
        )
    except (blind_opening.BlindOpeningError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
