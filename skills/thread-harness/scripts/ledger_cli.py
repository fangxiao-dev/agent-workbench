#!/usr/bin/env python3
"""Public CLI parser and compatibility dispatch for thread-harness."""

from __future__ import annotations

import argparse
import sys

from ledger_runtime import (
    INTEGRITY_GUARDED_COMMANDS,
    LEDGER_INTEGRITY_FAILED,
    LedgerError,
    LedgerIntegrityError,
    UsageError,
    ledger_integrity_issues,
    print_integrity_failure,
)
from ledger_registry import configure_routing
from ledger_commands import (
    cmd_act,
    cmd_decide,
    cmd_heartbeat,
    cmd_init,
    cmd_preflight,
    cmd_report,
    cmd_route,
    cmd_seam,
    cmd_stall_check,
    cmd_status,
    cmd_sync,
)

class UsageErrorParser(argparse.ArgumentParser):
    """用法错误退出 64（EX_USAGE），不用 argparse 默认的 2。

    2 是 stall-check 的 MUST_ACT。若用法错误也退 2，broker 会把一次拼错的命令
    读成"必须行动"，或者反过来把真正的 MUST_ACT 当成拼写问题忽略掉。退出码
    必须在语义上唯一。
    """

    def error(self, message):
        self.print_usage(sys.stderr)
        print(f"ERROR: {message}", file=sys.stderr)
        raise SystemExit(64)

def build_parser() -> argparse.ArgumentParser:
    parser = UsageErrorParser(description="thread-harness append-only ledger")
    sub = parser.add_subparsers(dest="command", required=True)

    def add_routing_args(command):
        routing = command.add_mutually_exclusive_group(required=True)
        routing.add_argument("--registry")
        routing.add_argument("--coordination-id")

    init = sub.add_parser("init", help="initialize the append-only runtime")
    add_routing_args(init)
    init.set_defaults(func=cmd_init)

    sync = sub.add_parser("sync", help="record one controller sync projection")
    add_routing_args(sync)
    sync.add_argument("--round", required=True, type=int)
    sync.set_defaults(func=cmd_sync)

    route = sub.add_parser("route", help="route a node to a new session")
    route.add_argument("--registry", required=True)
    route.add_argument("--node", required=True)
    route.add_argument("--new-session", required=True)
    route.add_argument("--expect-current")
    route.set_defaults(func=cmd_route)

    report = sub.add_parser("report", help="append a controller or task report")
    add_routing_args(report)
    report.add_argument("--node", required=True)
    report.add_argument("--state", required=True)
    report.add_argument("--round", type=int, default=0)
    report.add_argument("--head")
    report.add_argument(
        "--source-session",
        help="Child H1 source session; omit for controller reports.",
    )
    report.add_argument("--waiting-on", action="extend", nargs="+", default=[])
    report.add_argument("--note")
    report.set_defaults(func=cmd_report)

    seam = sub.add_parser("seam", help="record or deliver a seam")
    add_routing_args(seam)
    # Ledger keys use the bare ID; waiting_on-style input is normalized at the CLI boundary.
    seam.add_argument(
        "--seam-id",
        required=True,
        help='seam ID as "<id>" or "seam:<id>"; stored canonically as "<id>"',
    )
    seam.add_argument("--producer", required=True)
    seam.add_argument("--consumers", action="extend", nargs="+", default=[])
    seam.add_argument("--deliver")
    seam.set_defaults(func=cmd_seam)

    decide = sub.add_parser("decide", help="record or answer a decision")
    add_routing_args(decide)
    decide.add_argument("--raise", dest="raise_id")
    decide.add_argument("--by")
    decide.add_argument("--blocks", action="extend", nargs="+", default=[])
    decide.add_argument("--question")
    decide.add_argument("--answer")
    decide.add_argument("--text")
    decide.set_defaults(func=cmd_decide)

    act = sub.add_parser("act", help="append a dispatch, escalation, halt, or handoff")
    add_routing_args(act)
    mode = act.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dispatch", action="store_true")
    mode.add_argument("--escalate", action="store_true")
    mode.add_argument("--halt", action="store_true")
    mode.add_argument("--handoff", action="store_true")
    act.add_argument(
        "--seam-id",
        help='seam ID as "<id>" or "seam:<id>"; stored canonically as "<id>"',
    )
    act.add_argument("--producer")
    act.add_argument("--deliverable")
    act.add_argument("--decision-id")
    act.add_argument("--reason")
    act.add_argument("--source-session")
    act.add_argument("--node")
    act.set_defaults(func=cmd_act)

    status = sub.add_parser("status", help="project current ledger status")
    add_routing_args(status)
    status.set_defaults(func=cmd_status)

    heartbeat = sub.add_parser("heartbeat", help="record node heartbeat evidence")
    add_routing_args(heartbeat)
    heartbeat.add_argument("--node", required=True)
    heartbeat.add_argument("--evidence", required=True)
    heartbeat.set_defaults(func=cmd_heartbeat)

    stall = sub.add_parser("stall-check", help="classify current stall action")
    add_routing_args(stall)
    stall.set_defaults(func=cmd_stall_check)

    preflight = sub.add_parser("preflight", help="validate registry and runtime inputs")
    add_routing_args(preflight)
    preflight.set_defaults(func=cmd_preflight)
    return parser

def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    try:
        configure_routing(args)
        if args.command in INTEGRITY_GUARDED_COMMANDS:
            issues = ledger_integrity_issues(args.coordination_id)
            if issues:
                if args.command == "status":
                    return cmd_status(args, integrity_issues=issues)
                print_integrity_failure(issues)
                return LEDGER_INTEGRITY_FAILED
        return args.func(args)
    except LedgerIntegrityError as exc:
        print_integrity_failure(exc.issues)
        return LEDGER_INTEGRITY_FAILED
    except UsageError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 64
    except LedgerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

__all__ = ["build_parser", "main"]
