"""Emit a safe, read-only compaction-pressure projection for the current session."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from statistics import median
from typing import Any

from rollout_pulse import compaction_intervals, read_rollout, read_session_meta


PRESSURE_RATIO = 0.8
ABSOLUTE_FLOOR_MIN = 20
RECENT_INTERVALS = 3
MIN_INTERVALS_FOR_HIGH = 3


def _path_key(value: str) -> str:
    return os.path.normcase(os.path.normpath(os.path.abspath(os.path.expanduser(value))))


def _cwd_matches(session_cwd: Any, current_dir: Path) -> bool:
    if not isinstance(session_cwd, str) or not session_cwd.strip():
        return False
    current_key = _path_key(str(current_dir.resolve()))
    session_key = _path_key(session_cwd)
    return session_key == current_key or session_key.startswith(current_key + os.sep)


def _empty_report(explanation: str) -> dict[str, object]:
    return {
        "compactions": 0,
        "last_interval_min": None,
        "shrinking": False,
        "high": False,
        "explanation": explanation,
    }


def _number(value: float) -> int | float:
    rounded = round(value, 2)
    return int(rounded) if rounded.is_integer() else rounded


def pressure_report(compactions: list[str]) -> dict[str, object]:
    count = len(compactions)
    if not compactions:
        return _empty_report("matched rollout has zero compactions")

    try:
        intervals = compaction_intervals(compactions)
    except ValueError:
        return {
            **_empty_report("matched rollout has invalid compaction timestamps"),
            "compactions": count,
        }

    if not intervals:
        if count > 1:
            return {
                **_empty_report("matched rollout has invalid compaction timestamps"),
                "compactions": count,
            }
        return {
            **_empty_report("matched rollout has only one compaction; no interval can be measured"),
            "compactions": count,
        }

    last_interval = intervals[-1]
    recent = intervals[-RECENT_INTERVALS:]
    baseline = intervals[0]
    recent_median = median(recent)
    shrinking = len(intervals) >= 2 and recent_median < baseline
    enough = len(intervals) >= MIN_INTERVALS_FOR_HIGH
    degrading = enough and baseline > 0 and recent_median <= baseline * PRESSURE_RATIO
    # A relative test alone cannot fire on a session that was never healthy: if the very
    # first interval is already short it becomes the baseline. The absolute floor covers
    # sustained churn regardless of where the session started.
    churning = enough and recent_median <= ABSOLUTE_FLOOR_MIN
    high = degrading or churning
    if degrading:
        explanation = (
            f"recent median interval {_number(recent_median)} min is at most "
            f"{PRESSURE_RATIO:.0%} of the first interval {_number(baseline)} min"
        )
    elif churning:
        explanation = (
            f"recent median interval {_number(recent_median)} min is at or below the "
            f"{ABSOLUTE_FLOOR_MIN} min floor; the session has been churning throughout"
        )
    elif len(intervals) < MIN_INTERVALS_FOR_HIGH:
        explanation = "not enough intervals for a sustained pressure trend"
    elif not shrinking:
        explanation = "recent compaction cadence is not shorter than the first interval"
    else:
        explanation = (
            f"recent cadence shortened, but its median {_number(recent_median)} min is not "
            f"at least 20% below the first interval {_number(baseline)} min"
        )
    return {
        "compactions": count,
        "last_interval_min": _number(last_interval),
        "shrinking": shrinking,
        "high": high,
        "explanation": explanation,
    }


def _latest_matching_rollout(sessions_root: Path, current_dir: Path) -> tuple[Path | None, str | None]:
    if not sessions_root.is_dir():
        return None, f"sessions root does not exist: {sessions_root}"

    candidates: list[tuple[float, Path]] = []
    try:
        paths = sessions_root.rglob("*.jsonl")
        for path in paths:
            try:
                modified = path.stat().st_mtime
            except OSError:
                continue
            candidates.append((modified, path))
    except OSError as exc:
        return None, f"unable to scan sessions root: {exc}"

    for _, path in sorted(candidates, key=lambda item: item[0], reverse=True):
        meta = read_session_meta(path)
        if _cwd_matches(meta.get("cwd"), current_dir):
            return path, None

    if not candidates:
        return None, f"no rollout files under sessions root: {sessions_root}"
    if candidates:
        return None, f"no rollout matches current directory: {current_dir.resolve()}"
    return None, "no matching rollout"


def build_report(
    sessions_root: Path | None = None,
    current_dir: Path | None = None,
) -> dict[str, object]:
    root = sessions_root or Path(os.path.expanduser("~")) / ".codex" / "sessions"
    directory = current_dir or Path.cwd()
    path, explanation = _latest_matching_rollout(root, directory)
    if path is None:
        return _empty_report(explanation or "no matching rollout")
    try:
        rollout = read_rollout(path)
    except OSError as exc:
        return _empty_report(f"matched rollout cannot be read: {exc}")
    return pressure_report(rollout.compactions)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit current Codex rollout compaction pressure as JSON")
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=Path(os.path.expanduser("~")) / ".codex" / "sessions",
    )
    args = parser.parse_args(argv)
    print(json.dumps(build_report(args.sessions_root), ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
