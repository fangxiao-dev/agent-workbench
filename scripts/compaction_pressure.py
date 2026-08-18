"""Emit a safe, read-only compaction-pressure projection for the current session."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import median
from typing import Any
from urllib.parse import unquote

from rollout_pulse import compaction_intervals, read_rollout, read_session_meta


PRESSURE_RATIO = 0.8
ABSOLUTE_FLOOR_MIN = 20
RECENT_INTERVALS = 3
MIN_INTERVALS_FOR_HIGH = 3
GROK_CONTEXT_USAGE_THRESHOLD = 80
GROK_AVERAGE_INTERVAL_SECONDS = 1800


@dataclass(frozen=True)
class _SessionCandidate:
    host: str
    path: Path
    updated_at: float
    signals_path: Path | None = None


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


def _host_report(report: dict[str, object], host: str) -> dict[str, object]:
    return {
        **report,
        "explanation": f"{host}: {report['explanation']}",
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


def grok_pressure_report(signals: dict[str, Any]) -> dict[str, object]:
    """Project Grok's aggregate signals without inventing compaction timestamps."""
    count = signals.get("compactionCount")
    duration = signals.get("sessionDurationSeconds")
    usage = signals.get("contextWindowUsage")
    valid_count = isinstance(count, int) and not isinstance(count, bool) and count >= 0
    valid_duration = isinstance(duration, (int, float)) and not isinstance(duration, bool) and duration >= 0
    valid_usage = isinstance(usage, (int, float)) and not isinstance(usage, bool)
    compactions = count if valid_count else 0
    usage_high = valid_usage and usage >= GROK_CONTEXT_USAGE_THRESHOLD
    average_seconds: float | None = None
    cadence_high = False
    if valid_count and valid_duration and count >= 2:
        average_seconds = duration / count
        cadence_high = average_seconds <= GROK_AVERAGE_INTERVAL_SECONDS

    high = usage_high or cadence_high
    usage_text = (
        f"contextWindowUsage={usage}% >= {GROK_CONTEXT_USAGE_THRESHOLD}%"
        if usage_high
        else (
            f"contextWindowUsage={usage}% < {GROK_CONTEXT_USAGE_THRESHOLD}%"
            if valid_usage
            else "contextWindowUsage unavailable"
        )
    )
    if cadence_high:
        cadence_text = (
            f"compactionCount={count}, sessionDurationSeconds={duration}, "
            f"average={_number(average_seconds / 60)} min <= {GROK_AVERAGE_INTERVAL_SECONDS // 60} min"
        )
    elif valid_count and valid_duration and count >= 2:
        cadence_text = (
            f"compactionCount={count}, sessionDurationSeconds={duration}, "
            f"average={_number(average_seconds / 60)} min > {GROK_AVERAGE_INTERVAL_SECONDS // 60} min"
        )
    elif valid_count:
        cadence_text = f"compactionCount={count}; average cadence threshold requires at least 2 compactions"
    else:
        cadence_text = "compactionCount unavailable"
    explanation = (
        f"{usage_text}; {cadence_text}; compaction timestamps are not provided by Grok, "
        "so last_interval_min=null and shrinking=false"
    )
    return {
        "compactions": compactions,
        "last_interval_min": None,
        "shrinking": False,
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


def _codex_candidate(sessions_root: Path, current_dir: Path) -> tuple[_SessionCandidate | None, str | None]:
    path, explanation = _latest_matching_rollout(sessions_root, current_dir)
    if path is None:
        return None, explanation
    try:
        modified = path.stat().st_mtime
    except OSError as exc:
        return None, f"matched rollout cannot be stat'ed: {exc}"
    return _SessionCandidate("codex", path, modified), None


def _parse_updated_at(value: Any) -> float | None:
    if not isinstance(value, str) or not value.strip():
        return None
    timestamp = value.strip()
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    try:
        return datetime.fromisoformat(timestamp).timestamp()
    except (OverflowError, TypeError, ValueError, OSError):
        return None


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def _grok_cwd(summary_path: Path, root: Path, summary: dict[str, Any]) -> str | None:
    cwd = summary.get("cwd")
    if isinstance(cwd, str) and cwd.strip():
        return cwd
    try:
        relative = summary_path.parent.relative_to(root)
    except ValueError:
        return None
    if not relative.parts:
        return None
    return unquote(relative.parts[0])


def _grok_candidates(sessions_root: Path, current_dir: Path) -> tuple[list[_SessionCandidate], str | None]:
    if not sessions_root.is_dir():
        return [], f"sessions root does not exist: {sessions_root}"
    try:
        summaries = list(sessions_root.rglob("summary.json"))
    except OSError as exc:
        return [], f"unable to scan sessions root: {exc}"

    candidates: list[_SessionCandidate] = []
    for summary_path in summaries:
        summary = _read_json(summary_path)
        if summary is None or not _cwd_matches(_grok_cwd(summary_path, sessions_root, summary), current_dir):
            continue
        signals_path = summary_path.parent / "signals.json"
        try:
            fallback_time = max(
                summary_path.stat().st_mtime,
                signals_path.stat().st_mtime if signals_path.exists() else 0,
                summary_path.parent.stat().st_mtime,
            )
        except OSError:
            continue
        updated_at = _parse_updated_at(summary.get("updated_at")) or fallback_time
        candidates.append(_SessionCandidate("grok", summary_path.parent, updated_at, signals_path))

    if not candidates:
        if not summaries:
            return [], f"no session summaries under sessions root: {sessions_root}"
        return [], f"no Grok session matches current directory: {current_dir.resolve()}"
    return sorted(candidates, key=lambda candidate: candidate.updated_at, reverse=True), None


def _candidate_report(candidate: _SessionCandidate) -> dict[str, object]:
    if candidate.host == "codex":
        try:
            rollout = read_rollout(candidate.path)
        except OSError as exc:
            return _host_report(_empty_report(f"matched rollout cannot be read: {exc}"), candidate.host)
        return _host_report(pressure_report(rollout.compactions), candidate.host)

    assert candidate.signals_path is not None
    signals = _read_json(candidate.signals_path)
    if signals is None:
        return _host_report(_empty_report("matched session signals.json cannot be read"), candidate.host)
    return _host_report(grok_pressure_report(signals), candidate.host)


def build_report(
    sessions_root: Path | None = None,
    current_dir: Path | None = None,
    *,
    grok_sessions_root: Path | None = None,
    host: str = "auto",
) -> dict[str, object]:
    if host not in {"auto", "codex", "grok"}:
        raise ValueError(f"unsupported host: {host}")
    root = sessions_root or Path(os.path.expanduser("~")) / ".codex" / "sessions"
    grok_root = grok_sessions_root or Path(os.path.expanduser("~")) / ".grok" / "sessions"
    directory = current_dir or Path.cwd()
    candidates: list[_SessionCandidate] = []
    explanations: list[str] = []
    if host in {"auto", "codex"}:
        candidate, explanation = _codex_candidate(root, directory)
        if candidate is not None:
            candidates.append(candidate)
        elif explanation:
            explanations.append(f"codex: {explanation}")
    if host in {"auto", "grok"}:
        grok_candidates, explanation = _grok_candidates(grok_root, directory)
        if grok_candidates:
            candidates.append(grok_candidates[0])
        elif explanation:
            explanations.append(f"grok: {explanation}")
    if not candidates:
        return _empty_report("; ".join(explanations) or "no matching session")
    selected = max(candidates, key=lambda candidate: (candidate.updated_at, candidate.host))
    return _candidate_report(selected)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Emit current Codex or Grok session compaction pressure as JSON")
    parser.add_argument(
        "--sessions-root",
        type=Path,
        help="Codex sessions root",
    )
    parser.add_argument("--grok-sessions-root", type=Path, help="Grok sessions root")
    parser.add_argument("--cwd", type=Path, help="working directory to match instead of the process cwd")
    parser.add_argument("--host", choices=("codex", "grok", "auto"), default="auto")
    args = parser.parse_args(argv)
    print(
        json.dumps(
            build_report(
                args.sessions_root,
                args.cwd,
                grok_sessions_root=args.grok_sessions_root,
                host=args.host,
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
