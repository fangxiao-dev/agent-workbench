#!/usr/bin/env python3
"""按 thread id 定位 Codex rollout，并增量观测 compaction。"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid


class RolloutCompactionError(Exception):
    pass


def rollout_path_for_thread(thread_id: str, sessions_root: Path) -> Path:
    """只查看 UUIDv7 创建日期对应的目录，不递归扫描 sessions。"""
    try:
        parsed = uuid.UUID(thread_id)
    except (AttributeError, TypeError, ValueError) as exc:
        raise RolloutCompactionError(f"invalid thread id: {thread_id}") from exc
    if parsed.version != 7:
        raise RolloutCompactionError(f"thread id is not UUIDv7: {thread_id}")

    timestamp_ms = int(parsed.hex[:12], 16)
    created = datetime.fromtimestamp(timestamp_ms / 1000, timezone.utc).astimezone()
    day_dir = Path(sessions_root) / created.strftime("%Y/%m/%d")
    matches = list(day_dir.glob(f"*{thread_id}*.jsonl")) if day_dir.is_dir() else []
    if not matches:
        raise RolloutCompactionError(f"rollout not found for thread id {thread_id}: {day_dir}")
    if len(matches) != 1:
        raise RolloutCompactionError(f"multiple rollouts found for thread id {thread_id}: {day_dir}")
    return matches[0]


def observe_compactions(thread_id: str, previous: dict | None, sessions_root: Path) -> dict:
    """从上次 byte offset 起观测新 compaction；首次调用只建立 EOF 基线。"""
    if previous is None:
        path = rollout_path_for_thread(thread_id, sessions_root)
        return {
            "path": str(path),
            "offset": path.stat().st_size,
            "observed_count": 0,
            "last_window_number": None,
            "last_window_id": None,
        }

    try:
        path = Path(previous["path"])
        offset = int(previous["offset"])
        observed_count = int(previous["observed_count"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RolloutCompactionError(f"invalid compaction observer state for {thread_id}") from exc
    if offset < 0 or observed_count < 0:
        raise RolloutCompactionError(f"invalid compaction observer state for {thread_id}")
    if not path.is_file():
        path = rollout_path_for_thread(thread_id, sessions_root)
    size = path.stat().st_size
    if size < offset:
        raise RolloutCompactionError(f"rollout shrank below saved offset for {thread_id}: {path}")

    last_number = previous.get("last_window_number")
    last_id = previous.get("last_window_id")
    committed_offset = offset
    with path.open("rb") as stream:
        stream.seek(offset)
        while True:
            raw = stream.readline()
            if not raw:
                break
            if not raw.endswith(b"\n"):
                break
            committed_offset = stream.tell()
            if b"compacted" not in raw:
                continue
            try:
                event = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(event, dict) or event.get("type") != "compacted":
                continue
            payload = event.get("payload")
            if not isinstance(payload, dict):
                raise RolloutCompactionError(f"compacted event missing payload for {thread_id}")
            window_number = payload.get("window_number")
            window_id = payload.get("window_id")
            if type(window_number) is not int or window_number < 1 or not isinstance(window_id, str) or not window_id:
                raise RolloutCompactionError(f"compacted event missing window identity for {thread_id}")
            if last_number is not None and window_number < last_number:
                raise RolloutCompactionError(f"compaction window regressed for {thread_id}")
            if window_number == last_number and window_id == last_id:
                continue
            observed_count += 1
            last_number = window_number
            last_id = window_id

    return {
        "path": str(path),
        "offset": committed_offset,
        "observed_count": observed_count,
        "last_window_number": last_number,
        "last_window_id": last_id,
    }
