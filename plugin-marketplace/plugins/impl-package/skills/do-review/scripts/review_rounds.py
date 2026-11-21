#!/usr/bin/env python3
"""Track do-review rounds beside the canonical ledger.

open registers the tracks a round must run; record stores each track's return;
close refuses until every registered track has returned; export (after close)
lists the round's reports. Fix dispatch, the canonical summary and the overall
verdict all start from a closed round. A group that has used 3 rounds cannot
open another round: use a fresh group id. Group rounds are counted across every
ledger in the same directory (the package's execution/<attempt>/reviews/, or the
do-review temp folder without --package), so a new ledger for a new head does not
restart the count.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from review_ledger import validate_ledger_path  # noqa: E402

GROUP_ROUND_CAP = 3
PHASES = ("initial", "finding-closure", "terminal-final")
VERDICTS = ("PASS", "FAIL", "UNCERTAIN", "INCOMPLETE")


def state_path(ledger: Path) -> Path:
    if not ledger.is_file():
        raise ValueError(f"ledger does not exist, create it first: {ledger}")
    return ledger.with_suffix(".rounds.json")


def load(path: Path) -> dict:
    if not path.exists():
        return {"schemaVersion": 1, "rounds": []}
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, state: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    os.replace(temporary, path)


def current_open(state: dict) -> dict:
    rounds = state["rounds"]
    if not rounds or rounds[-1]["closed"]:
        raise ValueError("no open round; run `open` first")
    return rounds[-1]


def overall(tracks: dict) -> str:
    verdicts = [track["verdict"] for track in tracks.values()]
    if "FAIL" in verdicts:
        return "FAIL"
    if "UNCERTAIN" in verdicts:
        return "UNCERTAIN"
    return "PASS" if all(v == "PASS" for v in verdicts) else "INCOMPLETE"


def group_rounds_used(ledger: Path, group: str) -> int:
    """Rounds this group has opened on every ledger beside this one."""
    return sum(
        1
        for sibling in ledger.parent.glob("*.rounds.json")
        for r in load(sibling)["rounds"]
        if r["group"] == group
    )


def summary(state: dict, round_: dict) -> dict:
    used = round_.get("groupRound") or sum(
        1 for r in state["rounds"] if r["group"] == round_["group"] and r["round"] <= round_["round"]
    )
    return {
        "round": round_["round"],
        "group": round_["group"],
        "groupRound": used,
        "phase": round_["phase"],
        "overall": overall(round_["tracks"]),
        "tracks": [{"track": label, **t} for label, t in round_["tracks"].items()],
        "needsTriage": [label for label, t in round_["tracks"].items() if t["verdict"] != "PASS"],
        "freshGroupRequired": used >= GROUP_ROUND_CAP,
    }


def emit(payload: dict) -> int:
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def open_round(args: argparse.Namespace) -> int:
    ledger = validate_ledger_path(args.ledger, args.package)
    path = state_path(ledger)
    state = load(path)
    if state["rounds"] and not state["rounds"][-1]["closed"]:
        raise ValueError(f"round {state['rounds'][-1]['round']} is still open; record every track and close it first")
    used = group_rounds_used(ledger, args.group)
    if used >= GROUP_ROUND_CAP:
        raise ValueError(f"group {args.group} has used {used} rounds (cap {GROUP_ROUND_CAP}); open the next round with a fresh group id")
    tracks: dict = {}
    for spec in args.track:
        label, _, leaf = spec.partition("=")
        label = label.strip()
        if not label or label in tracks:
            raise ValueError(f"empty or duplicate track: {spec!r}")
        tracks[label] = {"leaf": leaf.strip() or None, "verdict": None, "report": None}
    round_ = {"round": len(state["rounds"]) + 1, "group": args.group, "groupRound": used + 1, "phase": args.phase, "tracks": tracks, "closed": False}
    state["rounds"].append(round_)
    save(path, state)
    return emit({"round": round_["round"], "group": args.group, "groupRound": used + 1, "tracks": list(tracks)})


def record(args: argparse.Namespace) -> int:
    path = state_path(validate_ledger_path(args.ledger, args.package))
    state = load(path)
    round_ = current_open(state)
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


def close(args: argparse.Namespace) -> int:
    path = state_path(validate_ledger_path(args.ledger, args.package))
    state = load(path)
    round_ = current_open(state)
    missing = [label for label, t in round_["tracks"].items() if t["verdict"] is None]
    if missing:
        raise ValueError(f"round {round_['round']} cannot close; missing tracks: {', '.join(missing)}")
    round_["closed"] = True
    save(path, state)
    return emit(summary(state, round_))


def export(args: argparse.Namespace) -> int:
    path = state_path(validate_ledger_path(args.ledger, args.package))
    state = load(path)
    if not state["rounds"]:
        raise ValueError("no rounds recorded")
    wanted = state["rounds"][-1]["round"] if args.round is None else args.round
    round_ = next((r for r in state["rounds"] if r["round"] == wanted), None)
    if round_ is None:
        raise ValueError(f"round {wanted} does not exist")
    if not round_["closed"]:
        raise ValueError(f"round {round_['round']} is not closed; export only after `close` succeeds")
    return emit(summary(state, round_))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p: argparse.ArgumentParser) -> argparse.ArgumentParser:
        p.add_argument("--package", type=Path, help="validate a package-local ledger path")
        p.add_argument("--ledger", required=True)
        return p

    p = common(sub.add_parser("open", help="open a round and register the tracks it must run"))
    p.add_argument("--group", required=True, help="review-group id; a group runs at most 3 rounds")
    p.add_argument("--phase", required=True, choices=PHASES)
    p.add_argument("--track", action="append", required=True, help="`Track A` or `Track A=<subagent_type>`; repeat per track")
    p.set_defaults(handler=open_round)

    p = common(sub.add_parser("record", help="record one track's return in the open round"))
    p.add_argument("--track", required=True)
    p.add_argument("--verdict", required=True, choices=VERDICTS)
    p.add_argument("--report", required=True, help="the track's report artifact path")
    p.set_defaults(handler=record)

    p = common(sub.add_parser("close", help="close the open round; refuses while any track is missing"))
    p.set_defaults(handler=close)

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
