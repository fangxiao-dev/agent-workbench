#!/usr/bin/env python3
"""Track do-review rounds beside the canonical ledger.

open registers the tracks a round must run; record stores each track's return;
close refuses until every registered track has returned; export (after close)
lists the round's reports. Fix dispatch, the canonical summary and the overall
verdict all start from a closed round.

A review group owns the findings it raises. `triage` records each accepted finding
(source plan-gap | impl-drift, class design | control, severity P0 | P1 | P2) and moves
it open -> fixed -> verified (a failed verification reopens it; or downgraded). `status`
derives the group state (plan-open, plan-pass, code-open, code-closed, converged), the
`capReached` flag and the next action. references/review-topology.md lists the same states and transitions.

Round counts are only a backstop: plan rounds warn from PLAN_WARN_ROUND on (counted
since the last passed plan round), code rounds stop at CODE_ROUND_CAP and need a fresh
group id (`open --succeeds <group>`, which takes over the unresolved findings). Group
state is counted across every ledger in the same directory (the package's
execution/<attempt>/reviews/, or the do-review temp folder without --package), so a new
ledger for a new head does not restart the count.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_ledger import validate_ledger_path  # noqa: E402

PLAN_WARN_ROUND = 3
CODE_ROUND_CAP = 5
GROUP_CHAIN_WARN = 3
REOPEN_ROOT_CUT = 2
PHASES = ("plan", "initial", "finding-closure", "terminal-final")
SOURCES = ("plan-gap", "impl-drift")
CLASSES = ("design", "control")
SEVERITIES = ("P0", "P1", "P2")
FINDING_STATES = ("open", "fixed", "verified", "downgraded")
VERDICTS = ("PASS", "FAIL", "UNCERTAIN", "INCOMPLETE")


def state_path(ledger: Path) -> Path:
    if not ledger.is_file():
        raise ValueError(f"ledger does not exist, create it first: {ledger}")
    return ledger.with_suffix(".rounds.json")


def load(path: Path) -> dict:
    if not path.exists():
        return {"schemaVersion": 2, "rounds": [], "findings": []}
    state = json.loads(path.read_text(encoding="utf-8"))
    state.setdefault("findings", [])
    return state


def save(path: Path, state: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def current_open(state: dict, group: str | None = None) -> dict:
    rounds = state["rounds"]
    if not rounds or rounds[-1]["closed"]:
        raise ValueError("no open round; run `open` first")
    if group is not None and rounds[-1]["group"] != group:
        raise ValueError(f"the open round belongs to group {rounds[-1]['group']}, not {group}")
    return rounds[-1]


def overall(tracks: dict) -> str:
    verdicts = [track["verdict"] for track in tracks.values()]
    if "FAIL" in verdicts:
        return "FAIL"
    if "UNCERTAIN" in verdicts:
        return "UNCERTAIN"
    return "PASS" if all(v == "PASS" for v in verdicts) else "INCOMPLETE"


def sibling_states(ledger: Path) -> list[tuple[Path, dict]]:
    """Every rounds file beside this ledger (the ledger's own file first, even if new)."""
    own = state_path(ledger)
    others = sorted(p for p in ledger.parent.glob("*.rounds.json") if p != own)
    return [(p, load(p)) for p in [own, *others]]


def group_rounds(ledger: Path, group: str) -> list[dict]:
    return [r for _, state in sibling_states(ledger) for r in state["rounds"] if r["group"] == group]


def ordered_rounds(ledger: Path, group: str) -> list[dict]:
    return sorted(group_rounds(ledger, group), key=lambda r: r.get("openSeq", r.get("closeSeq", 0)))


def group_findings(ledger: Path, group: str) -> list[tuple[Path, dict, dict]]:
    return [(p, state, f) for p, state in sibling_states(ledger) for f in state["findings"] if f["group"] == group]


def rounds_used(ledger: Path, group: str, plan: bool) -> int:
    """Rounds of one kind (plan or code) this group has opened on every ledger beside this one."""
    return sum(1 for r in group_rounds(ledger, group) if (r["phase"] == "plan") == plan)


def plan_streak(ledger: Path, group: str) -> int:
    """Plan rounds since the group's last passed plan round: a new topic starts the count again."""
    streak = 0
    for r in ordered_rounds(ledger, group):
        if r["phase"] == "plan":
            streak = 0 if r["closed"] and overall(r["tracks"]) == "PASS" else streak + 1
    return streak


def next_seq(ledger: Path) -> int:
    """Global order of events across ledgers; wall clocks can tie, a counter cannot."""
    seqs = [0]
    for _, state in sibling_states(ledger):
        seqs += [r.get(key, 0) for r in state["rounds"] for key in ("openSeq", "closeSeq")]
        seqs += [f.get("fixedSeq", 0) for f in state["findings"]]
    return max(seqs) + 1


def next_finding_id(ledger: Path, group: str) -> str:
    numbers = [int(f["id"][1:]) for _, _, f in group_findings(ledger, group)]
    return f"F{max(numbers, default=0) + 1}"


def latest_closed_round(ledger: Path, group: str) -> dict:
    closed = [r for r in group_rounds(ledger, group) if r["closed"]]
    if not closed:
        raise ValueError(f"group {group} has no closed round; triage only after `close` succeeds")
    return max(closed, key=lambda r: r.get("closeSeq", 0))


def chain_depth(ledger: Path, group: str) -> int:
    """Groups in a row (this one included) that follow each other through --succeeds."""
    depth, seen = 1, {group}
    while True:
        previous = next((r["succeeds"] for r in group_rounds(ledger, group) if r.get("succeeds")), None)
        if previous is None or previous in seen:
            return depth
        depth, group = depth + 1, previous
        seen.add(group)


def blocking(finding: dict) -> bool:
    """A finding keeps its group incomplete until verified (or, for control type, self-closed) or downgraded."""
    return finding["status"] in ("open", "fixed")


def group_status(ledger: Path, group: str, chain: bool = True) -> dict:
    rounds = ordered_rounds(ledger, group)
    if not rounds:
        raise ValueError(f"group {group} has no rounds")
    findings = [f for _, _, f in group_findings(ledger, group)]
    closed = [r for r in rounds if r["closed"]]
    open_round = next((r for r in rounds if not r["closed"]), None)
    code_rounds = sum(1 for r in rounds if r["phase"] != "plan")
    plan_passed = any(r["phase"] == "plan" and overall(r["tracks"]) == "PASS" for r in closed)
    unresolved = [f["id"] for f in findings if blocking(f)]
    gaps = [f["id"] for f in findings if f["source"] == "plan-gap" and blocking(f)]
    reasons: list[str] = []
    if open_round:
        reasons.append("a round is still open")
    if not code_rounds:
        reasons.append("no code round yet")
    if unresolved:
        reasons.append(f"findings not verified or downgraded: {', '.join(unresolved)}")
    if closed:
        last = max(closed, key=lambda r: r.get("closeSeq", 0))
        fresh = [
            f["id"]
            for f in findings
            if f["class"] == "design" and f["status"] != "downgraded" and (f["ledger"], f["round"]) == (last.get("ledger"), last["round"])
        ]
        if fresh:
            reasons.append(f"the last round raised new design findings: {', '.join(fresh)}")
    complete = not reasons
    predecessors = sorted({r["succeeds"] for r in rounds if r.get("succeeds")})
    # The group's own work is not proof: a fresh group must find nothing important itself.
    # Findings taken over from the previous group were raised there, not here.
    raised = [f["id"] for f in findings if f["class"] == "design" and f["status"] != "downgraded" and "from" not in f]
    converged = bool(
        chain and complete and predecessors and not raised and all(group_status(ledger, p, False)["complete"] for p in predecessors)
    )
    if open_round:
        state = "plan-open" if open_round["phase"] == "plan" else "code-open"
    elif gaps:
        state = "plan-open"
    elif not code_rounds:
        state = "plan-pass" if plan_passed else "plan-open"
    elif converged:
        state = "converged"
    else:
        state = "code-closed"
    # Not a state of its own: a group that used its code rounds and is still incomplete.
    capped = state == "code-closed" and not complete and code_rounds >= CODE_ROUND_CAP
    if state in ("plan-open", "code-open") and open_round:
        action = "record every track and close the open round"
    elif state == "plan-open":
        action = (
            "revise the plan, `triage fixed --commit <plan commit>`, then open a plan round: a PASS verifies the fix"
            if gaps
            else "open a plan round and fix its findings until one passes"
        )
    elif state == "plan-pass":
        action = "open a code round (--phase initial)"
    elif capped:
        action = f"code round cap reached: open a fresh group (--succeeds {group}); its unresolved findings move to the new group"
    elif state == "converged":
        action = "review converged"
    elif unresolved:
        action = "fix the open findings, then verify them in the next round (只核实关闭)"
    elif not complete:
        action = "open another round in this group"
    elif predecessors:
        action = f"this fresh group raised design findings ({', '.join(raised)}): open another fresh group (--succeeds {group}) to confirm"
    else:
        action = f"open a fresh group (--succeeds {group}) for one full-scope round"
    return {
        "group": group,
        "state": state,
        "complete": complete,
        "converged": converged,
        "capReached": capped,
        "reasons": reasons,
        "planRounds": len(rounds) - code_rounds,
        "codeRounds": code_rounds,
        "findings": {s: sum(1 for f in findings if f["status"] == s) for s in FINDING_STATES},
        "succeeds": predecessors,
        "raisedDesignFindings": raised,
        "nextAction": action,
    }


def status(args: argparse.Namespace) -> int:
    return emit(group_status(validate_ledger_path(args.ledger, args.package), args.group))


def summary(state: dict, round_: dict, ledger: Path) -> dict:
    used = round_.get("groupRound") or sum(
        1 for r in state["rounds"] if r["group"] == round_["group"] and r["round"] <= round_["round"]
    )
    is_plan = round_["phase"] == "plan"
    return {
        "round": round_["round"],
        "group": round_["group"],
        "groupRound": used,
        "phase": round_["phase"],
        "overall": overall(round_["tracks"]),
        "tracks": [{"track": label, **t} for label, t in round_["tracks"].items()],
        "needsTriage": [label for label, t in round_["tracks"].items() if t["verdict"] != "PASS"],
        "freshGroupRequired": (not is_plan) and used >= CODE_ROUND_CAP,
        "openFindings": sum(1 for _, _, f in group_findings(ledger, round_["group"]) if blocking(f)),
    }


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def check_predecessor(ledger: Path, group: str, predecessor: str) -> None:
    if predecessor == group:
        raise ValueError("a group cannot succeed itself")
    if group_rounds(ledger, group):
        raise ValueError("--succeeds belongs on the first round of a fresh group")
    previous = group_status(ledger, predecessor, False)
    if not (previous["complete"] or previous["capReached"]):
        raise ValueError(
            f"predecessor group {predecessor} is {previous['state']}; a fresh group follows a complete group or one at the code-round cap"
        )


def take_over(ledger: Path, predecessor: str, group: str) -> list[str]:
    """Moves the predecessor's unresolved findings to the new group, so the chain can still complete."""
    moved: list[str] = []
    for path, state in sibling_states(ledger):
        changed = False
        for f in state["findings"]:
            if f["group"] == predecessor and blocking(f):
                f["group"], f["from"] = group, predecessor
                moved.append(f["id"])
                changed = True
        if changed:
            save(path, state)
    return moved


def open_round(args: argparse.Namespace) -> int:
    ledger = validate_ledger_path(args.ledger, args.package)
    path = state_path(ledger)
    state = load(path)
    if state["rounds"] and not state["rounds"][-1]["closed"]:
        raise ValueError(f"round {state['rounds'][-1]['round']} is still open; record every track and close it first")
    tracks: dict = {}
    for spec in args.track:
        label, _, leaf = spec.partition("=")
        label = label.strip()
        if not label or label in tracks:
            raise ValueError(f"empty or duplicate track: {spec!r}")
        tracks[label] = {"leaf": leaf.strip() or None, "verdict": None, "report": None}
    is_plan = args.phase == "plan"
    used = rounds_used(ledger, args.group, is_plan)
    warnings: list[str] = []
    if is_plan:
        streak = plan_streak(ledger, args.group)
        if streak + 1 >= PLAN_WARN_ROUND:
            warnings.append(
                f"plan round {streak + 1} of group {args.group} since its last passed plan round: check whether the review is stuck in local detail and whether the requirement can be narrowed at its root"
            )
    else:
        if used >= CODE_ROUND_CAP:
            raise ValueError(f"group {args.group} has used {used} code rounds (cap {CODE_ROUND_CAP}); open the next round with a fresh group id (--succeeds)")
        existing = group_rounds(ledger, args.group)
        gaps = [f["id"] for _, _, f in group_findings(ledger, args.group) if f["source"] == "plan-gap" and blocking(f)]
        if gaps:
            raise ValueError(f"plan gaps are still open ({', '.join(gaps)}); revise the plan and verify it in a plan round first")
        if any(r["phase"] == "plan" for r in existing) and not any(
            r["phase"] == "plan" and r["closed"] and overall(r["tracks"]) == "PASS" for r in existing
        ):
            raise ValueError(f"group {args.group} has no plan round closed with PASS; the plan must pass before code is reviewed")
    taken: list[str] = []
    if args.succeeds:
        check_predecessor(ledger, args.group, args.succeeds)
        depth = chain_depth(ledger, args.succeeds) + 1
        if depth >= GROUP_CHAIN_WARN:
            warnings.append(
                f"{depth} fresh groups in a row have not converged: stop and decide whether the requirement can be cut near its root, or ask the Owner"
            )
        taken = take_over(ledger, args.succeeds, args.group)
        state = load(path)
    round_ = {
        "round": len(state["rounds"]) + 1,
        "ledger": ledger.name,
        "group": args.group,
        "groupRound": used + 1,
        "phase": args.phase,
        "tracks": tracks,
        "closed": False,
        "openSeq": next_seq(ledger),
    }
    if args.succeeds:
        round_["succeeds"] = args.succeeds
    state["rounds"].append(round_)
    save(path, state)
    payload = {"round": round_["round"], "group": args.group, "groupRound": used + 1, "tracks": list(tracks)}
    if taken:
        payload["takenOver"] = taken
    if warnings:
        payload["warnings"] = warnings
    return emit(payload)


def record(args: argparse.Namespace) -> int:
    path = state_path(validate_ledger_path(args.ledger, args.package))
    state = load(path)
    round_ = current_open(state, args.group)
    track = round_["tracks"].get(args.track)
    if track is None:
        raise ValueError(f"track {args.track!r} is not registered for round {round_['round']}: {', '.join(round_['tracks'])}")
    if track["verdict"] is not None:
        raise ValueError(f"track {args.track!r} already returned in round {round_['round']}")
    if not args.report.strip():
        raise ValueError("--report must name the track's report artifact")
    track["verdict"], track["report"] = args.verdict, args.report
    save(path, state)
    pending = [label for label, t in round_["tracks"].items() if t["verdict"] is None]
    return emit({"round": round_["round"], "track": args.track, "verdict": args.verdict, "pending": pending})


def verify_plan_gaps(ledger: Path, round_: dict) -> list[str]:
    """A passing plan round verifies the plan-gap fixes recorded before it opened."""
    verified: list[str] = []
    for path, state in sibling_states(ledger):
        changed = False
        for f in state["findings"]:
            if (
                f["group"] == round_["group"]
                and f["source"] == "plan-gap"
                and f["status"] == "fixed"
                and f.get("fixedSeq", 0) < round_.get("openSeq", 0)
            ):
                f["status"] = "verified"
                verified.append(f["id"])
                changed = True
        if changed:
            save(path, state)
    return verified


def close(args: argparse.Namespace) -> int:
    ledger = validate_ledger_path(args.ledger, args.package)
    path = state_path(ledger)
    state = load(path)
    round_ = current_open(state, args.group)
    missing = [label for label, t in round_["tracks"].items() if t["verdict"] is None]
    if missing:
        raise ValueError(f"round {round_['round']} cannot close; missing tracks: {', '.join(missing)}")
    round_["closed"] = True
    round_["closeSeq"] = next_seq(ledger)
    save(path, state)
    verified = verify_plan_gaps(ledger, round_) if round_["phase"] == "plan" and overall(round_["tracks"]) == "PASS" else []
    result = summary(state, round_, ledger)
    if verified:
        result["verifiedPlanGaps"] = verified
    return emit(result)


def export(args: argparse.Namespace) -> int:
    ledger = validate_ledger_path(args.ledger, args.package)
    path = state_path(ledger)
    state = load(path)
    if not state["rounds"]:
        raise ValueError("no rounds recorded")
    wanted = state["rounds"][-1]["round"] if args.round is None else args.round
    round_ = next((r for r in state["rounds"] if r["round"] == wanted), None)
    if round_ is None:
        raise ValueError(f"round {wanted} does not exist")
    if not round_["closed"]:
        raise ValueError(f"round {round_['round']} is not closed; export only after `close` succeeds")
    return emit(summary(state, round_, ledger))


def find_finding(ledger: Path, group: str, finding_id: str) -> tuple[Path, dict, dict]:
    for found in group_findings(ledger, group):
        if found[2]["id"] == finding_id:
            return found
    raise ValueError(f"group {group} has no finding {finding_id!r}")


def closed_round_of_group(state: dict, group: str, number: int) -> dict:
    round_ = next((r for r in state["rounds"] if r["round"] == number and r["group"] == group), None)
    if round_ is None:
        raise ValueError(f"round {number} of group {group} is not in this ledger")
    if not round_["closed"]:
        raise ValueError(f"round {number} is not closed; triage only after `close` succeeds")
    return round_


def triage(args: argparse.Namespace) -> int:
    ledger = validate_ledger_path(args.ledger, args.package)
    action = args.action
    # Without --round, triage refers to the group's latest closed round (round numbers are per ledger).
    chosen = lambda: (  # noqa: E731
        latest_closed_round(ledger, args.group)
        if args.round is None
        else closed_round_of_group(load(state_path(ledger)), args.group, args.round)
    )
    if action == "add":
        if not (args.source and args.klass and args.severity and args.summary and args.summary.strip()):
            raise ValueError("add needs --source, --class, --severity and --summary")
        path = state_path(ledger)
        state = load(path)
        round_ = chosen()
        finding = {
            "id": next_finding_id(ledger, args.group),
            "group": args.group,
            "ledger": round_.get("ledger", ledger.name),
            "round": round_["round"],
            "source": args.source,
            "class": args.klass,
            "severity": args.severity,
            "summary": args.summary.strip(),
            "status": "open",
            "reopens": 0,
        }
        state["findings"].append(finding)
        save(path, state)
        return emit(finding)
    if not args.id:
        raise ValueError(f"{action} needs --id")
    path, state, finding = find_finding(ledger, args.group, args.id)
    if action == "fixed":
        if finding["status"] != "open":
            raise ValueError(f"{finding['id']} is {finding['status']}; only an open finding can be marked fixed")
        if not (args.commit and args.commit.strip()):
            raise ValueError("fixed needs --commit")
        finding["fixCommit"] = args.commit.strip()
        if args.self_verified:
            if finding["class"] != "control":
                raise ValueError("--self-verified is only for control-type findings; design-type fixes are verified by the group")
            finding["status"], finding["selfVerified"] = "verified", True
        else:
            finding["status"] = "fixed"
        finding["fixedSeq"] = next_seq(ledger)
    elif action == "verify":
        if finding["status"] != "fixed":
            raise ValueError(f"{finding['id']} is {finding['status']}; verify only a fixed finding")
        round_ = chosen()
        if round_.get("closeSeq", 0) <= finding["fixedSeq"]:
            raise ValueError(f"round {round_['round']} closed before {finding['id']} was fixed; verify in a later round")
        finding["status"] = "verified"
    elif action == "reopen":
        if finding["status"] not in ("fixed", "verified"):
            raise ValueError(f"{finding['id']} is {finding['status']}; only a fixed finding can be reopened")
        reopens = finding["reopens"] + 1
        if reopens >= REOPEN_ROOT_CUT and not (args.root_cut and args.root_cut.strip()):
            raise ValueError(
                f"{finding['id']} would be reopened {reopens} times; state first whether the requirement can be cut at its root (--root-cut '<one sentence>')"
            )
        finding["reopens"], finding["status"] = reopens, "open"
        if args.root_cut and args.root_cut.strip():
            finding["rootCut"] = args.root_cut.strip()
    elif action == "downgrade":
        if finding["status"] == "downgraded":
            raise ValueError(f"{finding['id']} is already downgraded")
        if not (args.reason and args.reason.strip()):
            raise ValueError("downgrade needs --reason")
        finding["status"], finding["downgradeReason"] = "downgraded", args.reason.strip()
    save(path, state)
    return emit(finding)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--package", type=Path, help="validate a package-local ledger path")
        p.add_argument("--ledger", required=True)
        return p

    p = common(sub.add_parser("open", help="open a round and register the tracks it must run"))
    p.add_argument("--group", required=True, help="review-group id; a group stops at CODE_ROUND_CAP code rounds")
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--succeeds", help="first round of a fresh group: the complete (or capped) group it re-reviews; its unresolved findings move here")
    p.add_argument("--track", action="append", required=True, help="`Track A` or `Track A=<subagent_type>`; repeat per track")
    p.set_defaults(handler=open_round)

    p = common(sub.add_parser("record", help="record one track's return in the open round"))
    p.add_argument("--group", help="optional: must be the open round's group")
    p.add_argument("--track", required=True)
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--report", required=True, help="the track's report artifact path")
    p.set_defaults(handler=record)

    p = common(sub.add_parser("close", help="close the open round; refuses while any track is missing"))
    p.add_argument("--group", help="optional: must be the open round's group")
    p.set_defaults(handler=close)

    p = common(sub.add_parser("triage", help="record and track the group's accepted findings"))
    p.add_argument("action", choices=("add", "fixed", "verify", "reopen", "downgrade"))
    p.add_argument("--group", required=True)
    p.add_argument("--id")
    p.add_argument("--round", type=int, help="closed round of this ledger; default: the group's latest closed round")
    p.add_argument("--source", choices=SOURCES)
    p.add_argument("--class", dest="klass", choices=CLASSES)
    p.add_argument("--severity", choices=SEVERITIES)
    p.add_argument("--summary")
    p.add_argument("--commit")
    p.add_argument("--self-verified", action="store_true")
    p.add_argument("--root-cut")
    p.add_argument("--reason")
    p.set_defaults(handler=triage)

    p = common(sub.add_parser("status", help="print a group's state and the next action"))
    p.add_argument("--group", required=True)
    p.set_defaults(handler=status)

    p = common(sub.add_parser("export", help="print a closed round's summary and reports to triage"))
    p.add_argument("--round", type=int)
    p.set_defaults(handler=export)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.handler(args)
    except (OSError, ValueError) as error:
        print(f"review_rounds: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
