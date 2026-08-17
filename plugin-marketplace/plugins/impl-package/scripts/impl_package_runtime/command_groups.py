"""The single grouped CLI registry for the Ticket-first 3.5 runtime."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import engine


def _emit(action: Callable[[], dict[str, Any]]) -> int:
    try:
        result = action()
    except (engine.StateError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


def _expect(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expect", required=True)


def _ticket_transition(package: Path, args: argparse.Namespace, target: str) -> dict[str, Any]:
    return engine.command_set_state(
        package, args.id, target, args.expect,
        getattr(args, "revision", None), getattr(args, "environment", None),
        getattr(args, "disposition", None), getattr(args, "successor", None),
        getattr(args, "evidence", None), getattr(args, "revalidation_plan", None),
        getattr(args, "claim", None), getattr(args, "invalidated_by", None),
    )


def _parser(group: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=f"impl_package_state.py --package <package> {group}")
    commands = parser.add_subparsers(dest="command", required=True)
    if group == "package":
        init = commands.add_parser("init", help="initialize a 3.5 Ticket-only package")
        init.add_argument("--attempt", required=True)
        init.add_argument("--plan", required=True)
        for name in ("status", "validate"):
            child = commands.add_parser(name)
            child.add_argument("--commit")
        commands.add_parser("refresh-progress", help="refresh machine-owned projections")
    elif group == "ticket":
        transition = commands.add_parser("transition", help="legacy set-state compatibility alias")
        transition.add_argument("kind", choices=("ticket",))
        transition.add_argument("id")
        transition.add_argument("state", choices=sorted(engine.TICKET_STATES))
        _expect(transition)
        transition.add_argument("--revision")
        transition.add_argument("--environment")
        transition.add_argument("--disposition", choices=sorted(engine.DISPOSITIONS))
        transition.add_argument("--successor")
        transition.add_argument("--evidence")
        transition.add_argument("--revalidation-plan")
        transition.add_argument("--claim", action="append", default=[])
        transition.add_argument("--invalidated-by")
        for command, target, help_text in (
            ("satisfy", "SATISFIED", "mark a Ticket SATISFIED"),
            ("block", "BLOCKED", "mark a Ticket BLOCKED"),
            ("needs-revalidation", "NEEDS-REVALIDATION", "mark a Ticket NEEDS-REVALIDATION"),
            ("pending", "PENDING", "return a Ticket to PENDING"),
            ("retire", "RETIRED", "mark a Ticket RETIRED"),
        ):
            child = commands.add_parser(command, help=help_text)
            child.set_defaults(target=target)
            child.add_argument("id")
            _expect(child)
            if target == "SATISFIED":
                child.add_argument("--revision", required=True)
                child.add_argument("--environment", required=True)
            elif target == "BLOCKED":
                child.add_argument("--evidence", required=True)
            elif target == "NEEDS-REVALIDATION":
                child.add_argument("--evidence")
                child.add_argument("--claim", action="append", required=True)
                child.add_argument("--invalidated-by", required=True)
            elif target == "PENDING":
                child.add_argument("--revalidation-plan")
            else:
                child.add_argument("--disposition", choices=sorted(engine.DISPOSITIONS), required=True)
                child.add_argument("--evidence", required=True)
                child.add_argument("--successor")
    elif group == "evidence":
        commands.add_parser("add", help="add a JSON evidence record from stdin")
        invalidate = commands.add_parser("invalidate", help="invalidate one evidence artifact")
        invalidate.add_argument("--ticket", required=True)
        invalidate.add_argument("--claim", required=True)
        invalidate.add_argument("--artifact", required=True)
        invalidate.add_argument("--invalidated-by", required=True)
    elif group == "recovery":
        checkpoint = commands.add_parser("checkpoint", help="overwrite the active checkpoint")
        checkpoint.add_argument("--subject", default="attempt")
        checkpoint.add_argument("--next", required=True)
        checkpoint.add_argument("--blocker")
        checkpoint.add_argument("--evidence", action="append", default=[])
        checkpoint.add_argument("--handoff", action="store_true")
        commands.add_parser("judgment", help="append a judgment JSON payload from stdin")
    elif group == "gate":
        for verdict in sorted(engine.VERDICTS):
            child = commands.add_parser(verdict, help=f"write a {verdict} Gate")
            child.set_defaults(verdict=verdict)
            child.add_argument("--comparison-commit", required=True)
            child.add_argument("--reason", required=True)
            child.add_argument("--evidence", action="append", default=[])
            child.add_argument("--durable-delta", action="append", default=[])
            child.add_argument("--no-durable-delta-reason")
            child.add_argument("--environment")
    else:
        raise KeyError(group)
    return parser


def _normalize_gate_argv(argv: list[str]) -> list[str]:
    """Accept legacy option-before-verdict spelling and unique option prefixes."""
    verdicts = set(engine.VERDICTS)
    value_options = {
        "--comparison-commit", "--reason", "--evidence", "--durable-delta",
        "--no-durable-delta-reason", "--environment",
    }

    def value_option(token: str) -> tuple[str | None, bool]:
        name, separator, _value = token.partition("=")
        matches = [option for option in value_options if option.startswith(name)]
        return (matches[0], bool(separator)) if len(matches) == 1 else (None, False)

    cursor = 0
    while cursor < len(argv):
        value = argv[cursor]
        if value in verdicts:
            return argv if cursor == 0 else [value, *argv[:cursor], *argv[cursor + 1 :]]
        option, inline_value = value_option(value)
        cursor += 1 if option is not None and inline_value else 2 if option is not None else 1
    return argv


def _run(package: Path, group: str, args: argparse.Namespace) -> dict[str, Any]:
    if group == "package":
        if args.command == "init":
            return engine.command_init(package, args.attempt, args.plan)
        if args.command in {"status", "validate"}:
            return engine.command_validate(package, args.commit)
        return engine.command_refresh_progress(package)
    if group == "ticket":
        return _ticket_transition(package, args, args.state if args.command == "transition" else args.target)
    if group == "evidence":
        return (engine.command_evidence_add(package, sys.stdin.read()) if args.command == "add" else
                engine.command_evidence_invalidate(package, args.ticket, args.claim, args.artifact, args.invalidated_by))
    if group == "recovery":
        return (engine.command_checkpoint(package, args.subject, args.next, args.blocker, args.evidence, args.handoff) if args.command == "checkpoint" else
                engine.command_er_add(package, sys.stdin.read()))
    return engine.command_gate(package, args.verdict, args.comparison_commit, args.reason, args.evidence,
                               args.durable_delta, args.no_durable_delta_reason, args.environment)


def main(package: Path, group: str, argv: list[str]) -> int:
    args = _parser(group).parse_args(_normalize_gate_argv(argv) if group == "gate" else argv)
    return _emit(lambda: _run(package.resolve(), group, args))
