"""Print a compact health readout for one Codex rollout, without dumping transcript text.

Reads the JSONL one physical line at a time and emits only aggregates: compaction
cadence, context pressure, tool-call mix and the trailing assistant turn. Intended for
checking on a long-running main session cheaply.

    python scripts/rollout_pulse.py <session-id-or-path>
    python scripts/rollout_pulse.py 01a00e82 --sessions-root C:\\Users\\me\\.codex\\sessions
"""

from __future__ import annotations

import argparse
import collections
import json
import os
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path


@dataclass
class RolloutData:
    path: Path
    meta: dict[str, object]
    compactions: list[str]
    usage: list[tuple[str, int, int]]
    calls: collections.Counter[str]
    assistant: list[tuple[str, str]]
    window: object


def resolve(target: str, sessions_root: Path) -> Path:
    candidate = Path(target)
    if candidate.is_file():
        return candidate
    matches = sorted(sessions_root.rglob(f"*{target}*.jsonl"))
    if not matches:
        raise SystemExit(f"no rollout matching {target!r} under {sessions_root}")
    return matches[-1]


def minutes_between(a: str, b: str) -> float:
    fmt = "%H:%M:%S"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 60


def compaction_intervals(compactions: list[str]) -> list[float]:
    return [
        minutes_between(compactions[index - 1], compactions[index])
        for index in range(1, len(compactions))
    ]


def _session_meta(record: dict[str, object]) -> dict[str, object]:
    payload = record.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}
    timestamp = str(record.get("timestamp", ""))
    return {
        "cwd": payload.get("cwd"),
        "started": timestamp[:19],
        "cli": payload.get("cli_version"),
    }


def read_session_meta(path: Path) -> dict[str, object]:
    try:
        with path.open(encoding="utf-8", errors="replace") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                if isinstance(record, dict) and record.get("type") == "session_meta":
                    return _session_meta(record)
    except OSError:
        return {}
    return {}


def read_rollout(path: Path) -> RolloutData:
    meta: dict[str, object] = {}
    compactions: list[str] = []
    usage: list[tuple[str, int, int]] = []
    calls: collections.Counter[str] = collections.Counter()
    assistant: list[tuple[str, str]] = []
    window = None

    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict):
                continue
            kind = record.get("type")
            payload = record.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
            clock = str(record.get("timestamp", ""))[11:19]

            if kind == "session_meta" and not meta:
                meta = _session_meta(record)
            elif kind == "compacted":
                compactions.append(clock)
            elif kind == "event_msg" and payload.get("type") == "token_count":
                info = payload.get("info") or {}
                if not isinstance(info, dict):
                    info = {}
                window = info.get("model_context_window") or window
                totals = info.get("total_token_usage") or {}
                if isinstance(totals, dict) and totals.get("input_tokens"):
                    usage.append((clock, totals["input_tokens"], totals.get("output_tokens") or 0))
            elif kind == "response_item":
                if payload.get("type") == "function_call":
                    calls[str(payload.get("name"))] += 1
                elif payload.get("type") in {"local_shell_call", "custom_tool_call"}:
                    calls[payload["type"]] += 1
                elif payload.get("type") == "message" and payload.get("role") == "assistant":
                    text = " ".join(
                        part.get("text", "")
                        for part in payload.get("content") or []
                        if isinstance(part, dict)
                    ).strip()
                    if text:
                        assistant.append((clock, text))

    return RolloutData(path, meta, compactions, usage, calls, assistant, window)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", help="session id, id fragment, or path to the rollout")
    parser.add_argument(
        "--sessions-root",
        default=os.path.join(os.path.expanduser("~"), ".codex", "sessions"),
    )
    parser.add_argument("--tail", type=int, default=1, help="trailing assistant turns to show")
    parser.add_argument("--chars", type=int, default=700, help="chars per trailing turn")
    args = parser.parse_args()

    path = resolve(args.target, Path(args.sessions_root))

    rollout = read_rollout(path)

    print(f"file      {path.name}")
    print(f"started   {rollout.meta.get('started')}   cwd {rollout.meta.get('cwd')}")
    print(f"window    {rollout.window}")

    if rollout.compactions:
        gaps = [f"{gap:.0f}m" for gap in compaction_intervals(rollout.compactions)]
        print(f"compact   {len(rollout.compactions)} 次  at {' '.join(rollout.compactions)}")
        if gaps:
            print(f"          间隔 {' → '.join(gaps)}   （缩短 = 工作集在长大）")
    else:
        print("compact   0 次")

    if rollout.usage:
        first, last = rollout.usage[0], rollout.usage[-1]
        span = minutes_between(first[0], last[0]) or 1
        print(
            f"tokens    累计输入 {last[1]/1e6:.1f}M  输出 {last[2]/1e3:.0f}K"
            f"  ≈{(last[1]-first[1])/span/1e3:.0f}K 输入/分钟"
        )

    if rollout.calls:
        mix = "  ".join(f"{name}×{count}" for name, count in rollout.calls.most_common(8))
        print(f"calls     {sum(rollout.calls.values())} 次   {mix}")

    print(f"turns     assistant {len(rollout.assistant)} 次")
    for clock, text in rollout.assistant[-max(0, args.tail) :]:
        body = " ".join(text.split())
        print(f"\n[{clock}] {body[: args.chars]}")


if __name__ == "__main__":
    main()
