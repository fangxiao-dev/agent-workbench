"""The single grouped CLI registry for the Ticket-first runtime (format 3.6)."""

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

from . import cmd_gate, engine, impact, usage_log


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
        usage_log.note_error(type(exc).__name__, str(exc))
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


def _emit_report(package: Path, group: str, args: argparse.Namespace) -> int:
    """Read-only reports with a text/JSON choice and (for preflight) a meaningful exit code."""
    try:
        engine.require_current_format(package)
        if group == "evidence":
            result = impact.evidence_impact(package, args.to, args.judged_by)
            text, code = impact.render_impact(result), 0
        else:
            result = cmd_gate.gate_preflight(package, args.comparison_commit, args.durable_delta, args.no_durable_delta_reason)
            code = 0 if result["ok"] else 1
            text = cmd_gate.render_preflight(result, summary_only=args.summary)
            if args.quiet and not args.summary:
                return code
    except (engine.StateError, OSError) as exc:
        usage_log.note_error(type(exc).__name__, str(exc))
        print(str(exc), file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, sort_keys=True) if args.json else text)
    return code


def _expect(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--expect", required=True)


def _ticket_transition(package: Path, args: argparse.Namespace, target: str) -> dict[str, Any]:
    return engine.command_set_state(
        package, args.id, target, args.expect,
        getattr(args, "revision", None), getattr(args, "environment", None),
        getattr(args, "disposition", None), getattr(args, "successor", None),
        getattr(args, "evidence", None), getattr(args, "revalidation_plan", None),
        getattr(args, "invalidated_by", None),
    )


EVIDENCE_ADD_EPILOG = """Every record needs kind, artifact, revision, environment, conclusion; minimum JSON per kind:
  journey-step: {"kind":"journey-step","runId":"r1","journeyId":"J1","stepId":"J1-S1","actor":"agent","entry":"<Spec entry>","surface":"page","artifact":"<package-relative file>","revision":"<commit>","environment":"local","conclusion":"supporting"}
  run-setup:    {"kind":"run-setup","runId":"r1","artifact":"<package-relative file>","revision":"<commit>","environment":"local","conclusion":"supporting"}
  suite:        {"kind":"suite","suiteId":"<id>","artifact":"<package-relative file>","revision":"<commit>","environment":"<Spec environment>","conclusion":"supporting"}
  review:       {"kind":"review","ticket":"T01","artifact":"execution/<attempt>/reviews/<file>","revision":"<commit>","environment":"local","conclusion":"supporting"}
  release:      {"kind":"release","artifact":"<package-relative file>","revision":"<commit>","environment":"local","conclusion":"supporting"}
Optional (journey-step): inputRef, outputRef, manualBy."""


EVIDENCE_ADD_RULES = """
Commit only the minimum evidence the Gate depends on: one screenshot per page step, one returned file/response per file/API step.
Keep raw artifacts (traces, full logs, DB dumps) in the git-ignored output/qa/<runId>/ instead.
  journey-step surface=page: artifact is a Playwright trace .zip, or a package image (.png/.jpg/.jpeg/.webp) together with manualBy
  journey-step surface=file: artifact is the produced file itself (not .md/.txt/.log); no manualBy
  journey-step surface=log: any package file; no manualBy
Artifact paths are relative to the package directory and the file must already exist."""

TRAIL_APPEND_TERMINAL_SUMMARY = """

Terminal review coverage (written once the final terminal-final review has returned; comparisonHead must be the full current HEAD SHA):
  {"kind":"fact","subject":"attempt","key":"review.terminal_summary","value":{
     "reviewRunId":"<ReviewRun id>","comparisonHead":"<HEAD full SHA>","safetyApplicable":false,
     "results":[
       {"track":"Track A","verdict":"PASS","reviewedHead":"<HEAD full SHA>","artifact":"<package-relative report>"},
       {"track":"Track C","verdict":"PASS","reviewedHead":"<SHA>","artifact":"<package-relative report>"}]}}
  Each report's first four lines: verdict: PASS / reviewed-head: <SHA> / review-run: <id> / review-track: Track A|C|D.
  safetyApplicable=true additionally needs a Track D result. A track reviewed at an older head needs "reused":true and "reuseEvidence":"<package-relative file>" (never Track A)."""


def _parser(group: str) -> argparse.ArgumentParser:
    parser = usage_log.UsageArgumentParser(prog=f"impl_package_state.py --package <package> {group}")
    commands = parser.add_subparsers(dest="command", required=True)
    if group == "package":
        check_spec = commands.add_parser("check-spec", help="validate the 3.6 Spec contract before package initialization")
        check_spec.add_argument("--spec", help="repository-relative Spec path (default: <package>/spec.md)")
        commands.add_parser("sync-predecessors", help="re-read 前置包（Predecessors） from the current Plan into state")
        init = commands.add_parser("init", help="initialize a 3.6 Journey package from the Plan")
        init.add_argument("--attempt", required=True)
        init.add_argument(
            "--plan", required=True,
            help="plan path relative to the repository root (not the package dir), e.g. docs/.../<package>/p1.patch-plan.md",
        )
        archive = commands.add_parser("archive-attempt", help="backfill a frozen Attempt Ticket snapshot")
        archive.add_argument("--attempt", required=True)
        archive.add_argument("--from-revision", required=True)
        status = commands.add_parser(
            "status",
            help="read-only snapshot of the current Attempt: lifecycle, Tickets, evidence coverage, projection drift",
            description=(
                "Print the current Attempt's validated state as JSON without writing anything. "
                "Use it to see where a package stands or to confirm progress.md / the Execution Record still match state.json. "
                "Unlike `validate`, it skips the contract, Plan and arrival-path findings."
            ),
            epilog="Example:\n  python impl_package_state.py --package docs/implementations/<package> package status",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        status.add_argument("--commit", help="commit to resolve and report (default: none)")
        validate = commands.add_parser("validate", help="validate state and report contract / arrival-path findings")
        validate.add_argument("--commit")
        commands.add_parser("refresh-progress", help="refresh machine-owned projections")
        amendment = commands.add_parser("amendment", help="register or confirm a contract amendment")
        amendment_commands = amendment.add_subparsers(dest="amendment_action", required=True)
        add = amendment_commands.add_parser("add", help="register a pending amendment")
        add.add_argument("--id", required=True)
        add.add_argument("--summary", required=True)
        add.add_argument(
            "--affected", action="append", required=True,
            help="changed contract file: decision.md, spec.md or contract-design.md; repeat once per file",
        )
        add.add_argument("--artifact", help="package-relative artifact describing the change (default: first --affected)")
        add.add_argument("--tickets", action="append", default=[], help="impacted Ticket ID; repeat once per Ticket")
        add.add_argument(
            "--post-gate", action="store_true",
            help="after a terminal Gate pass: register a wording-only correction (Journey steps, Suites and Rule bindings must stay identical); needs Owner confirm, Gate stays pass",
        )
        supersede = amendment_commands.add_parser("supersede", help="mark a PENDING amendment as covered by a later one")
        supersede.add_argument("--id", required=True, help="PENDING amendment being superseded")
        supersede.add_argument("--by", required=True, help="later amendment that covers it (must list the same contract files)")
        withdraw = amendment_commands.add_parser("withdraw", help="withdraw a PENDING amendment that no longer applies")
        withdraw.add_argument("--id", required=True)
        withdraw.add_argument("--reason", required=True)
        confirm = amendment_commands.add_parser("confirm", help="confirm pending amendments")
        confirm.add_argument("--id", action="append", required=True, help="amendment id; repeat to confirm several")
        confirm.add_argument("--confirmed-by", required=True, help="Owner name, required, e.g. --confirmed-by Owner")
        confirm.add_argument("--confirmed-revision", help="commit the Owner confirmed (default: HEAD)")
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
                child.add_argument("--revision", help="commit the evidence is checked against (default: HEAD)")
                child.add_argument("--environment")
            elif target == "BLOCKED":
                child.add_argument("--evidence", required=True)
            elif target == "NEEDS-REVALIDATION":
                child.add_argument("--evidence")
                child.add_argument("--invalidated-by", required=True)
            elif target == "PENDING":
                child.add_argument("--revalidation-plan")
            else:
                child.add_argument("--disposition", choices=sorted(engine.DISPOSITIONS), required=True)
                child.add_argument("--evidence", required=True)
                child.add_argument("--successor")
    elif group == "evidence":
        commands.add_parser(
            "add",
            help="add JSON evidence record(s) from stdin",
            description="Add evidence from stdin: one JSON object, a JSON array, or JSON Lines (one record per line). A batch is all-or-nothing; errors name the failing line.",
            epilog=EVIDENCE_ADD_EPILOG + EVIDENCE_ADD_RULES,
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        check = commands.add_parser(
            "check",
            help="dry-run `evidence add` on a file; writes nothing",
            description=(
                "Run the same validation as `evidence add` against a JSON / JSON Lines file without recording anything. "
                "Use it before `evidence add` to catch a bad artifact path, revision or record shape; errors name the failing line."
            ),
            epilog="Example:\n  python impl_package_state.py --package docs/implementations/<package> evidence check --file evidence.jsonl",
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
        check.add_argument("--file", required=True, help="JSON object, JSON array or JSON Lines file")
        invalidate = commands.add_parser("invalidate", help="invalidate the records of one evidence key")
        invalidate.add_argument("--key", required=True)
        invalidate.add_argument("--invalidated-by", required=True)
        impact = commands.add_parser(
            "impact",
            help="read-only: which evidence needs a rerun vs can be carried forward up to --to",
            description=(
                "For every Required Suite and Journey run, intersect the runtime files changed since the evidence revision with the paths it covers. "
                "Suite coverage: `covers: a/, b/` in the Spec Entry cell, else the directory of each `--spec <file>`. "
                "Journey coverage: `covers:` in a step cell, else path/route tokens in 操作入口/观察表面; underivable counts as affected. "
                "Prints rerun commands and one ready `evidence carry-forward` batch."
            ),
        )
        impact.add_argument("--to", required=True)
        impact.add_argument("--judged-by", help="name written into the generated carry-forward command")
        impact.add_argument("--json", action="store_true")
        carry = commands.add_parser(
            "carry-forward",
            help="record the agent judgment that evidence still holds up to a later commit (single --key or batched --select groups)",
            description=(
                "Carry supporting evidence forward to --to. Use --key K --reason R for one key, or repeat "
                "--select <selector> --reason <text> pairs (matched in order) for a whole batch: "
                "run:<runId> (run-setup + all journey steps), kind:suite, kind:review, ticket:<id> (its review key), key:<key>. "
                "The batch is atomic; --dry-run lists each group's keys and the runtime files changed since each record's revision."
            ),
        )
        carry.add_argument("--key")
        carry.add_argument("--select", action="append", default=[])
        carry.add_argument("--to", required=True)
        carry.add_argument("--reason", action="append", default=[])
        carry.add_argument("--judged-by", required=True)
        carry.add_argument("--dry-run", action="store_true", help="write nothing; report keys and runtime-changed files per group")
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
        append = commands.add_parser(
            "append",
            help="append a validated manual trail event from stdin",
            description="Append one validated manual trail event from stdin.",
            epilog=(
                "Minimum valid stdin JSON:\n"
                '  {"subject":"attempt","kind":"escape","deviation":"manual route","reason":"no matching situation"}\n\n'
                'ER judgment is separate: `recovery judgment` requires "purpose":"judgment":\n'
                '  {"purpose":"judgment","subject":"attempt","title":"Decision","content":"Keep the narrow path."}'
                + TRAIL_APPEND_TERMINAL_SUMMARY
            ),
            formatter_class=argparse.RawDescriptionHelpFormatter,
        )
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
            child.add_argument("--commit", action="store_true", help="after the Gate is written, commit only the package directory (no attribution trailer)")
        pre = commands.add_parser("preflight", help="read-only: run every `gate pass` check and list gaps with fix commands")
        pre.add_argument("--comparison-commit", help="default: HEAD")
        pre.add_argument("--durable-delta", action="append", default=[])
        pre.add_argument("--no-durable-delta-reason")
        pre.add_argument("--json", action="store_true")
        pre.add_argument("--quiet", action="store_true", help="print nothing; use the exit code")
        pre.add_argument("--summary", action="store_true", help="one-line result (with --quiet, only this line)")
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
    if not (group == "package" and args.command == "check-spec"):
        engine.require_current_format(package)
    if group == "package":
        if args.command == "check-spec":
            return engine.command_check_spec(package, args.spec)
        if args.command == "init":
            return engine.command_init(package, args.attempt, args.plan)
        if args.command == "sync-predecessors":
            return engine.command_sync_predecessors(package)
        if args.command == "archive-attempt":
            return engine.command_archive_attempt(package, args.attempt, args.from_revision)
        if args.command in {"status", "validate"}:
            return engine.command_validate(package, args.commit, check_arrival_paths=args.command == "validate")
        if args.command == "amendment":
            if args.amendment_action == "add":
                return engine.command_amendment_add(package, args.id, args.summary, args.affected, args.artifact, args.tickets, args.post_gate)
            if args.amendment_action == "supersede":
                return engine.command_amendment_supersede(package, args.id, args.by)
            if args.amendment_action == "withdraw":
                return engine.command_amendment_withdraw(package, args.id, args.reason)
            results = [
                engine.command_amendment_confirm(package, identifier, args.confirmed_by, args.confirmed_revision)
                for identifier in args.id
            ]
            return results[0] if len(results) == 1 else {"results": results}
        return engine.command_refresh_progress(package)
    if group == "ticket":
        return _ticket_transition(package, args, args.target)
    if group == "evidence":
        if args.command == "add":
            return engine.command_evidence_add(package, sys.stdin.read())
        if args.command == "check":
            return engine.command_evidence_add(package, Path(args.file).read_text(encoding="utf-8"), dry_run=True)
        if args.command == "carry-forward":
            return engine.command_evidence_carry_forward(
                package, args.key, args.to, args.reason, args.judged_by, args.select, args.dry_run,
            )
        return engine.command_evidence_invalidate(package, args.key, args.invalidated_by)
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
                               args.durable_delta, args.no_durable_delta_reason, args.environment, args.commit)


def _main(package: Path, group: str, argv: list[str], *, no_situation: bool = False) -> int:
    no_situation = no_situation or "--no-situation" in argv or os.environ.get("IMPL_PACKAGE_NO_SITUATION") == "1"
    argv = [value for value in argv if value != "--no-situation"]
    args = _parser(group).parse_args(_normalize_gate_argv(argv) if group == "gate" else argv)
    trigger = group in {"ticket", "evidence", "recovery", "gate", "trail"}
    validate = group == "package" and args.command == "validate"
    if (group, args.command) in {("evidence", "impact"), ("gate", "preflight")}:
        return _emit_report(package.resolve(), group, args)
    return _emit(
        lambda: _run(package.resolve(), group, args),
        package=package.resolve(),
        append_situation=(trigger or validate) and not no_situation,
        append_situation_on_error=validate and not no_situation,
    )


def main(package: Path, group: str, argv: list[str], *, no_situation: bool = False) -> int:
    with engine.git_query_scope():
        return _main(package, group, argv, no_situation=no_situation)
