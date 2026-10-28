"""The single grouped CLI registry for the Ticket-first 3.5 runtime."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Callable
from contextlib import redirect_stderr, redirect_stdout
from io import StringIO
from pathlib import Path
from typing import Any

import situation

from . import engine


def _text(value: Any, missing: str = "?") -> str:
    if value is None:
        return missing
    if isinstance(value, bool):
        return str(value).lower()
    return str(value)


def _count(value: Any) -> int:
    if isinstance(value, list):
        return len(value)
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    return 1 if value else 0


def _situation_footer(package: Path) -> str | None:
    stdout = StringIO()
    stderr = StringIO()
    try:
        with redirect_stdout(stdout), redirect_stderr(stderr):
            code = situation.main(["render", "--package", str(package), "--json"])
        if code != 0:
            return None
        rendered = json.loads(stdout.getvalue())
        if not isinstance(rendered, dict):
            return None
        if "runnable" in rendered:
            lines = ["[处境]"]
            for partition in ("blocking", "runnable", "withheld", "in_flight"):
                lines.append(f"{partition}:")
                items = rendered.get(partition, [])
                lines.extend("  " + json.dumps(item, ensure_ascii=False, separators=(",", ":")) for item in items)
                if not items:
                    lines.append("  none")
            return "\n".join(lines)
        selected = rendered.get("selected")
        if not isinstance(selected, dict):
            selected = {}
        slug = selected.get("slug") or rendered.get("unmatched") or "（无）"
        lines = [
            f"[处境] {_text(slug, '（无）')} · "
            f"basis={_text(selected.get('basis'))} · judgment={_text(selected.get('judgment'))}",
        ]
        actions = selected.get("actions")
        if isinstance(actions, list) and actions:
            lines.append("动作:")
            for action in actions:
                if not isinstance(action, dict):
                    continue
                marker = "（默认）" if action.get("default") else ""
                lines.append(
                    f"  - {_text(action.get('id'), '')}{marker}: "
                    f"{_text(action.get('do'), '')} — {_text(action.get('effect'), '')}"
                )
        lines.append(
            f"并列匹配: {_count(rendered.get('parallel_matches'))} | "
            f"未判定: {_count(rendered.get('undetermined'))} | "
            f"未匹配: {_count(rendered.get('unmatched'))}"
        )
        lines.append(f"协议: {_text(selected.get('protocol'), '')}")
        return "\n".join(lines)
    except Exception:
        return None


def _emit(
    action: Callable[[], dict[str, Any]],
    *,
    package: Path,
    append_situation: bool = False,
    append_situation_on_error: bool = False,
) -> int:
    should_append_situation = False
    try:
        result = action()
    except (engine.StateError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        should_append_situation = append_situation_on_error
        code = 1
    else:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        should_append_situation = append_situation
        code = 0
    if should_append_situation:
        footer = _situation_footer(package)
        if footer:
            print(footer)
    return code


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
        archive = commands.add_parser("archive-attempt", help="backfill a frozen Attempt Ticket snapshot")
        archive.add_argument("--attempt", required=True)
        archive.add_argument("--from-revision", required=True)
        for name in ("status", "validate"):
            child = commands.add_parser(name)
            child.add_argument("--commit")
        commands.add_parser("refresh-progress", help="refresh machine-owned projections")
    elif group == "ticket":
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
        invalidate.add_argument("--key")
        invalidate.add_argument("--ticket")
        invalidate.add_argument("--claim")
        invalidate.add_argument("--artifact")
        invalidate.add_argument("--invalidated-by", required=True)
        retire_claim = commands.add_parser("retire-claim", help="remove an invalidated orphan claim")
        retire_claim.add_argument("--ticket", required=True)
        retire_claim.add_argument("--claim", required=True)
    elif group == "recovery":
        checkpoint = commands.add_parser("checkpoint", help="overwrite the active checkpoint")
        checkpoint.add_argument("--subject", default="attempt")
        checkpoint.add_argument("--next", required=True)
        checkpoint.add_argument("--blocker")
        checkpoint.add_argument("--evidence", action="append", default=[])
        checkpoint.add_argument("--handoff", action="store_true")
        commands.add_parser("judgment", help="append a judgment JSON payload from stdin")
        lease = commands.add_parser("lease", help="acquire or release exclusive resource leases")
        lease_commands = lease.add_subparsers(dest="lease_action", required=True)
        acquire = lease_commands.add_parser("acquire", help="atomically acquire one or more resource keys")
        acquire.add_argument("--key", action="append", required=True)
        acquire.add_argument("--owner", required=True)
        release = lease_commands.add_parser("release", help="release a lease after cleanup")
        release.add_argument("--lease-id", required=True)
        release.add_argument("--owner-token", required=True)
    elif group == "trail":
        append = commands.add_parser("append", help="append a validated manual trail event from stdin")
        append.add_argument("--review-phase", choices=situation.REVIEW_PHASE_VALUES)
        append.add_argument("--review-track", choices=situation.REVIEW_TRACK_VALUES)
        append.add_argument("--review-recheck", action="store_true", default=None)
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
        if args.command == "archive-attempt":
            return engine.command_archive_attempt(package, args.attempt, args.from_revision)
        if args.command in {"status", "validate"}:
            return engine.command_validate(package, args.commit, check_arrival_paths=args.command == "validate")
        return engine.command_refresh_progress(package)
    if group == "ticket":
        return _ticket_transition(package, args, args.target)
    if group == "evidence":
        if args.command == "add":
            return engine.command_evidence_add(package, sys.stdin.read())
        if args.command == "invalidate":
            return engine.command_evidence_invalidate(package, args.ticket, args.claim, args.artifact, args.invalidated_by, args.key)
        return engine.command_evidence_retire_claim(package, args.ticket, args.claim)
    if group == "recovery":
        if args.command == "checkpoint":
            return engine.command_checkpoint(package, args.subject, args.next, args.blocker, args.evidence, args.handoff)
        if args.command == "judgment":
            return engine.command_er_add(package, sys.stdin.read())
        if args.lease_action == "acquire":
            return engine.command_lease_acquire(package, args.key, args.owner)
        return engine.command_lease_release(package, args.lease_id, args.owner_token)
    if group == "trail":
        return engine.command_trail_append(
            package,
            sys.stdin.read(),
            {
                "review_phase": args.review_phase,
                "review_track": args.review_track,
                "review_recheck": args.review_recheck,
            },
        )
    return engine.command_gate(package, args.verdict, args.comparison_commit, args.reason, args.evidence,
                               args.durable_delta, args.no_durable_delta_reason, args.environment)


def main(package: Path, group: str, argv: list[str], *, no_situation: bool = False) -> int:
    no_situation = no_situation or "--no-situation" in argv or os.environ.get("IMPL_PACKAGE_NO_SITUATION") == "1"
    argv = [value for value in argv if value != "--no-situation"]
    args = _parser(group).parse_args(_normalize_gate_argv(argv) if group == "gate" else argv)
    trigger = group in {"ticket", "evidence", "recovery", "gate", "trail"}
    validate = group == "package" and args.command == "validate"
    return _emit(
        lambda: _run(package.resolve(), group, args),
        package=package.resolve(),
        append_situation=(trigger or validate) and not no_situation,
        append_situation_on_error=validate and not no_situation,
    )
