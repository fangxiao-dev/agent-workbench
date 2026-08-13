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


def _token_usage_from_event(event: dict) -> tuple[dict | None, int | None, str | None]:
    info = None
    token_event = False
    if event.get("type") == "token_count":
        token_event = True
        info = event.get("info")
    else:
        payload = event.get("payload")
        if isinstance(payload, dict) and payload.get("type") == "token_count":
            token_event = True
            info = payload.get("info")
    if not token_event:
        return None, None, None
    if not isinstance(info, dict):
        return None, None, "token_count.info is not an object"

    last = info.get("last_token_usage")
    context = info.get("model_context_window")
    if last is None:
        return None, None, "last_token_usage is missing"
    if not isinstance(last, dict):
        return None, None, "last_token_usage is not an object"
    input_tokens = last.get("input_tokens")
    if type(input_tokens) is not int or input_tokens < 0:
        return None, None, "last_token_usage.input_tokens is invalid"
    if type(context) is not int or context <= 0:
        return None, None, "model_context_window is invalid"
    return {"input_tokens": input_tokens}, context, None


def _baseline(thread_id: str, path: Path) -> dict:
    return {
        "path": str(path),
        "offset": path.stat().st_size,
        "observed_count": 0,
        "last_window_number": None,
        "last_window_id": None,
        "last_token_usage": None,
        "model_context_window": None,
        "token_usage_available": False,
        "token_usage_error": "baseline at rollout EOF",
    }


def observe_rollout(thread_id: str, previous: dict | None, sessions_root: Path) -> dict:
    """增量读取 compaction 与 token_count；首次只在当前 rollout EOF 建 baseline。"""
    if previous is None:
        path = rollout_path_for_thread(thread_id, sessions_root)
        return _baseline(thread_id, path)

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
    last_token_usage = previous.get("last_token_usage")
    model_context_window = previous.get("model_context_window")
    token_usage_available = previous.get("token_usage_available") is True
    token_usage_error = previous.get("token_usage_error")
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
            try:
                event = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError):
                continue
            if not isinstance(event, dict) or event.get("type") != "compacted":
                compacted = False
            else:
                compacted = True
            if compacted:
                payload = event.get("payload")
                if not isinstance(payload, dict):
                    raise RolloutCompactionError(f"compacted event missing payload for {thread_id}")
                window_number = payload.get("window_number")
                window_id = payload.get("window_id")
                if type(window_number) is not int or window_number < 1 or not isinstance(window_id, str) or not window_id:
                    raise RolloutCompactionError(f"compacted event missing window identity for {thread_id}")
                if last_number is not None and window_number < last_number:
                    raise RolloutCompactionError(f"compaction window regressed for {thread_id}")
                if window_number != last_number or window_id != last_id:
                    observed_count += 1
                    last_number = window_number
                    last_id = window_id

            token_usage, context_window, token_error = _token_usage_from_event(event)
            if token_usage is not None or token_error is not None:
                if token_error:
                    last_token_usage = None
                    model_context_window = None
                    token_usage_available = False
                    token_usage_error = token_error
                else:
                    last_token_usage = token_usage
                    model_context_window = context_window
                    token_usage_available = True
                    token_usage_error = None

    return {
        "path": str(path),
        "offset": committed_offset,
        "observed_count": observed_count,
        "last_window_number": last_number,
        "last_window_id": last_id,
        "last_token_usage": last_token_usage,
        "model_context_window": model_context_window,
        "token_usage_available": token_usage_available,
        "token_usage_error": token_usage_error,
    }


def observe_compactions(thread_id: str, previous: dict | None, sessions_root: Path) -> dict:
    """兼容入口：返回同一个增量 observer 的 compaction 与 token 字段。"""
    return observe_rollout(thread_id, previous, sessions_root)
