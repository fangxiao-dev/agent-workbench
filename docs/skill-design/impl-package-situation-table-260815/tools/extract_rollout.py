"""Reusable utility for extracting compact decision timelines from Codex JSONL rollouts.

The input files are intentionally processed one physical line at a time.  The
script writes the three case timelines and this directory's summary file; it
does not mutate the repository or the source rollouts.

Usage from the repository root:
    python docs/skill-design/impl-package-situation-table-260815/tools/extract_rollout.py
    python docs/skill-design/impl-package-situation-table-260815/tools/extract_rollout.py \\
        --sessions-root C:\\Users\\me\\.codex\\sessions
    python docs/skill-design/impl-package-situation-table-260815/tools/extract_rollout.py \\
        --output-dir docs/skill-design/impl-package-situation-table-260815/replay
"""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator


MAX_TIMELINE_BYTES = 6_000_000
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parent

CASES: dict[str, tuple[str, ...]] = {
    "case1": (
        "019ffcd1-32b5-7ea0-9612-56f6a99be3f0",
        "019ffd06-70d7-7bc3-ba95-472f70e843c2",
    ),
    "case2": (
        "019ffd3a-4992-7973-b61b-a8b0aef4bf30",
        "019ffd5c-4c61-7fb3-8fe0-16a1d7d57874",
        "019ffd5c-f109-7d51-8d87-712f441fc60e",
        "019ffe79-09c8-7df2-a1ca-19c98dcf0191",
        "019fff39-ec22-7160-bec5-407090dbad5a",
        "019fff66-f618-7b41-9dd2-b6b6a70f6169",
        "019fff77-5074-7521-aeca-b58fccaea2f3",
        "01a000a4-abb7-7bf3-9ceb-4abb421b50d6",
        "01a000ff-a81d-71b0-9746-7c509a80c958",
    ),
    "case3": (
        "01a0012f-c343-77a0-b38e-8af4159ce0d7",
        "01a00156-2f48-7241-a471-44dfce868cb0",
        "01a004dc-c73b-7971-8b5a-ea92cbf128be",
    ),
}

ALL_SESSION_IDS = tuple(sid for session_ids in CASES.values() for sid in session_ids)

EVENT_TOOL_OUTPUT_TYPES = {
    "mcp_tool_call_end",
    "web_search_end",
    "shell_command_end",
    "exec_command_end",
    "tool_call_end",
}

COMMAND_NAMES = {"exec", "shell", "shell_command", "exec_command"}

BASE64_DATA_RE = re.compile(
    r"data:[^\s;,]+;base64,[A-Za-z0-9+/=_-]+", re.IGNORECASE
)
ENCRYPTED_RE = re.compile(r"\bgAAAA[A-Za-z0-9_-]{80,}\b")
LONG_BASE64_RE = re.compile(r"(?<![A-Za-z0-9+/=_-])[A-Za-z0-9+/]{160,}={0,2}(?![A-Za-z0-9+/=_-])")
EXIT_CODE_RE = re.compile(
    r"(?:exit\s*code|exit_code|return\s*code|returncode)\s*[:=]\s*(-?\d+)",
    re.IGNORECASE,
)
FILE_HEADER_RE = re.compile(
    r"(?im)^\s*(?:={3,}\s*[^=\r\n]{1,240}\s*={3,}|---\s*(?:begin\s+)?file\b|<file\b)\s*$"
)


@dataclass
class PassResult:
    records: int = 0
    kind_counts: Counter[str] = field(default_factory=Counter)
    truncated_counts: Counter[str] = field(default_factory=Counter)
    source_bytes: int = 0
    source_lines: int = 0
    invalid_json: int = 0
    source_first_ts: str | None = None
    source_last_ts: str | None = None
    timeline_first_ts: str | None = None
    timeline_last_ts: str | None = None
    redacted_base64: int = 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sessions-root",
        type=Path,
        default=None,
        help="Codex sessions root; defaults to %%USERPROFILE%%/.codex/sessions.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for the three timelines and summary.",
    )
    return parser.parse_args(argv)


def resolve_sessions_root(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit.expanduser().resolve()
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        return (Path(user_profile) / ".codex" / "sessions").resolve()
    return (Path.home() / ".codex" / "sessions").resolve()


def locate_rollouts(root: Path) -> dict[str, Path]:
    if not root.is_dir():
        raise FileNotFoundError(f"sessions root does not exist: {root}")

    found: dict[str, list[Path]] = {sid: [] for sid in ALL_SESSION_IDS}
    for path in root.rglob("*.jsonl"):
        for sid in ALL_SESSION_IDS:
            if sid in path.name:
                found[sid].append(path)

    missing = [sid for sid, paths in found.items() if not paths]
    duplicates = {sid: paths for sid, paths in found.items() if len(paths) > 1}
    if missing:
        raise FileNotFoundError("missing rollout(s): " + ", ".join(missing))
    if duplicates:
        details = "; ".join(
            f"{sid}: {', '.join(str(p) for p in paths)}"
            for sid, paths in duplicates.items()
        )
        raise RuntimeError("multiple rollouts matched a session id: " + details)
    return {sid: paths[0] for sid, paths in found.items()}


def iter_jsonl(path: Path) -> Iterator[tuple[int, dict[str, Any]]]:
    # utf-8-sig handles a possible BOM on the first line.  errors=replace keeps
    # one damaged text field from preventing the rest of a rollout being read.
    with path.open("r", encoding="utf-8-sig", errors="replace", newline="") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                yield line_number, {}
                continue
            if isinstance(value, dict):
                yield line_number, value
            else:
                yield line_number, {}


def text_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"))
    except (TypeError, ValueError):
        return str(value)


def redact_base64(text: str) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return "[omitted base64/image data]"

    text = BASE64_DATA_RE.sub(replace, text)
    text = ENCRYPTED_RE.sub(replace, text)
    text = LONG_BASE64_RE.sub(replace, text)
    return text, count


def omit_file_echo(text: str) -> str:
    """Drop an obvious large file dump, while retaining normal long messages."""
    if len(text) <= 2000 or not FILE_HEADER_RE.search(text):
        return text
    if text.count("\n") < 8:
        return text
    return f"[omitted obvious file-content echo; original_chars={len(text)}]"


def clean_text(text: str) -> tuple[str, int]:
    text, redactions = redact_base64(text)
    text = omit_file_echo(text)
    return text, redactions


def truncate(text: str, limit: int) -> tuple[str, bool]:
    if len(text) <= limit:
        return text, False
    return text[:limit] + "…", True


def content_text(content: Any) -> str:
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            item_type = str(item.get("type", ""))
            if item_type in {"input_text", "output_text", "text", "refusal"}:
                value = item.get("text")
                if isinstance(value, str):
                    parts.append(value)
        return "\n".join(parts)
    if isinstance(content, str):
        return content
    return ""


def summary_text(payload: dict[str, Any]) -> str:
    summary = payload.get("summary")
    if isinstance(summary, list):
        parts = []
        for item in summary:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                if item.get("type") in {None, "summary_text", "text"}:
                    parts.append(item["text"])
        return "\n".join(parts)
    return text_value(summary)


def clean_json_value(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: dict[str, Any] = {}
        for key, child in value.items():
            key_lower = str(key).lower()
            if any(token in key_lower for token in ("encrypted", "base64", "image", "audio")):
                cleaned[key] = "[omitted encoded/media data]"
            else:
                cleaned[key] = clean_json_value(child)
        return cleaned
    if isinstance(value, list):
        return [clean_json_value(child) for child in value]
    if isinstance(value, str):
        return redact_base64(value)[0]
    return value


def clean_tool_param(value: Any) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped[:1] in {"{", "["}:
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                return json.dumps(
                    clean_json_value(parsed), ensure_ascii=False, separators=(",", ":")
                )
        return redact_base64(value)[0]
    return json.dumps(clean_json_value(value), ensure_ascii=False, separators=(",", ":"))


def is_command_call(name: str, params: str) -> bool:
    return extract_command_line(name, params) is not None


def quoted_field_value(text: str, start: int) -> str | None:
    """Read a JS/JSON quoted string beginning at start, if it is complete."""
    if start >= len(text) or text[start] not in {"'", '"'}:
        return None
    quote = text[start]
    escaped = False
    end = start + 1
    while end < len(text):
        char = text[end]
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == quote:
            literal = text[start : end + 1]
            try:
                if quote == '"':
                    return json.loads(literal)
                return ast.literal_eval(literal)
            except (SyntaxError, ValueError, json.JSONDecodeError):
                return None
        end += 1
    return None


def extract_command_line(name: str, params: str) -> str | None:
    """Return only a nested shell/exec command, not its JS wrapper.

    The rollout's `exec` calls also carry orchestration snippets such as
    apply_patch and wait.  Those are ordinary tool parameters and stay under
    the 400-character budget.  Only an actual shell/exec `command`/`cmd`
    argument receives the no-truncation rule.
    """
    lower_name = name.lower()
    nested_shell = re.search(
        r"(?:tools\.)?(?:shell_command|exec_command)\s*\(", params, re.I
    )
    if nested_shell is None and lower_name not in {"shell", "shell_command", "exec_command"}:
        # A direct JSON/dict argument can still be a command call.
        try:
            parsed = json.loads(params)
        except (json.JSONDecodeError, TypeError):
            parsed = None
        if isinstance(parsed, dict):
            for key in ("command", "cmd"):
                if isinstance(parsed.get(key), str):
                    return parsed[key]
        return None

    field_match = re.search(
        r"(?:[\"'](?:command|cmd)[\"']|\b(?:command|cmd))\s*:\s*",
        params,
        re.I,
    )
    if field_match is not None:
        value = quoted_field_value(params, field_match.end())
        if value is not None:
            return value
    if lower_name in {"shell", "shell_command", "exec_command"}:
        return params
    return None


def make_tool_call(payload: dict[str, Any]) -> tuple[dict[str, Any], bool, int]:
    name = text_value(payload.get("name")) or "unknown"
    raw_params = payload.get("input") if "input" in payload else payload.get("arguments")
    raw_param_text = text_value(raw_params)
    command_line = extract_command_line(name, raw_param_text)
    params = clean_tool_param(raw_params)
    prefix = f"{name}: "
    if command_line is not None:
        # The full shell/exec command is decision-bearing.  The surrounding
        # JS wrapper, workdir and timeout are not part of the command line.
        command_line, redactions = redact_base64(command_line)
        text = prefix + command_line
        return {"kind": "tool_call", "name": name, "text": text}, False, redactions
    text, was_truncated = truncate(prefix + params, 400)
    return {"kind": "tool_call", "name": name, "text": text}, was_truncated, 0


def walk_output(value: Any, parts: list[str], limit: int = 100_000) -> None:
    if sum(len(part) for part in parts) >= limit:
        return
    if isinstance(value, str):
        parts.append(value[: max(0, limit - sum(len(part) for part in parts))])
        return
    if isinstance(value, list):
        for child in value:
            walk_output(child, parts, limit)
            if sum(len(part) for part in parts) >= limit:
                return
        return
    if not isinstance(value, dict):
        return

    preferred_keys = ("text", "output", "message", "result", "error", "detail")
    visited: set[str] = set()
    for key in preferred_keys:
        if key in value:
            visited.add(key)
            walk_output(value[key], parts, limit)
    if parts:
        return
    for key, child in value.items():
        key_lower = str(key).lower()
        if key_lower in {"image", "images", "audio", "data", "encrypted_content"}:
            continue
        if key_lower in {"call_id", "id", "status", "type", "name"}:
            continue
        if key not in visited:
            walk_output(child, parts, limit)
            if sum(len(part) for part in parts) >= limit:
                return


def exit_nonzero(value: Any, visible_text: str) -> str:
    codes = EXIT_CODE_RE.findall(visible_text)
    if codes:
        try:
            return "true" if int(codes[-1]) != 0 else "false"
        except ValueError:
            pass
    if isinstance(value, dict):
        for key in ("exit_code", "returncode", "return_code"):
            code = value.get(key)
            if isinstance(code, (int, float)):
                return "true" if code != 0 else "false"
        if value.get("isError") is True or value.get("is_error") is True:
            return "true"
        status = str(value.get("status", "")).lower()
        if status in {"failed", "error", "cancelled", "canceled", "timeout", "timed_out"}:
            return "true"
        if status in {"completed", "success", "succeeded", "ok"}:
            return "false"
    return "unknown"


def make_tool_out(payload: dict[str, Any], event_type: str | None = None) -> tuple[dict[str, Any], bool, int]:
    value = payload.get("output") if "output" in payload else payload.get("result")
    parts: list[str] = []
    walk_output(value, parts)
    raw_text = "\n".join(parts)
    status = exit_nonzero(value, raw_text)
    raw_text, redactions = clean_text(raw_text)
    if not raw_text:
        raw_text = "[no textual tool output]"
    if event_type:
        raw_text = f"event={event_type}; {raw_text}"
    raw_text = f"exit_nonzero={status}; {raw_text}"
    text, was_truncated = truncate(raw_text, 200)
    return {"kind": "tool_out", "text": text}, was_truncated, redactions


def make_row(
    record: dict[str, Any],
    timestamp: str,
    budget: dict[str, int],
) -> tuple[dict[str, Any] | None, str | None, int]:
    record_type = record.get("type")
    payload = record.get("payload")
    if not isinstance(payload, dict):
        return None, None, 0

    payload_type = payload.get("type")
    kind: str | None = None
    name: str | None = None
    text = ""
    redactions = 0
    original_kind = None

    if record_type == "response_item" and payload_type == "message":
        role = payload.get("role")
        if role not in {"user", "assistant"}:
            return None, None, 0
        kind = str(role)
        original_kind = kind
        text, redactions = clean_text(content_text(payload.get("content")))
    elif record_type == "response_item" and payload_type == "reasoning":
        text, redactions = clean_text(summary_text(payload))
        if not text:
            return None, None, redactions
        kind = "reasoning"
        original_kind = kind
    elif record_type == "response_item" and payload_type in {"custom_tool_call", "function_call"}:
        row, was_truncated, redactions = make_tool_call(payload)
        return row, "tool_call" if was_truncated else None, redactions
    elif record_type == "response_item" and payload_type in {
        "custom_tool_call_output",
        "function_call_output",
    }:
        row, was_truncated, redactions = make_tool_out(payload)
        return row, "tool_out" if was_truncated else None, redactions
    elif record_type == "event_msg" and payload_type in EVENT_TOOL_OUTPUT_TYPES:
        row, was_truncated, redactions = make_tool_out(payload, str(payload_type))
        return row, "tool_out" if was_truncated else None, redactions
    else:
        # event_msg user_message/agent_message/agent_reasoning are duplicate
        # envelopes for the canonical response_item records.  session_meta,
        # world_state, turn_context, token_count and lifecycle events are
        # metadata rather than a decision/action row.
        return None, None, 0

    limit = budget[kind]
    text, was_truncated = truncate(text, limit)
    row = {"kind": kind, "text": text}
    return row, original_kind if was_truncated else None, redactions


def add_timestamp_bounds(result: PassResult, timestamp: str, source: bool) -> None:
    if not timestamp:
        return
    if source:
        if result.source_first_ts is None or timestamp < result.source_first_ts:
            result.source_first_ts = timestamp
        if result.source_last_ts is None or timestamp > result.source_last_ts:
            result.source_last_ts = timestamp


def write_case_timeline(
    case_name: str,
    session_ids: Iterable[str],
    paths: dict[str, Path],
    output_path: Path,
    budget: dict[str, int],
) -> PassResult:
    result = PassResult()
    temp_path = output_path.with_suffix(output_path.suffix + ".tmp")
    if temp_path.exists():
        temp_path.unlink()

    seq = 0
    last_timestamp = ""
    try:
        with temp_path.open("w", encoding="utf-8", newline="\n") as output:
            for sid in session_ids:
                path = paths[sid]
                result.source_bytes += path.stat().st_size
                for _line_number, record in iter_jsonl(path):
                    result.source_lines += 1
                    if not record:
                        result.invalid_json += 1
                        continue
                    raw_timestamp = record.get("timestamp")
                    if raw_timestamp not in (None, ""):
                        last_timestamp = text_value(raw_timestamp)
                    add_timestamp_bounds(result, last_timestamp, source=True)

                    row, truncated_kind, redactions = make_row(record, last_timestamp, budget)
                    result.redacted_base64 += redactions
                    if row is None:
                        continue
                    seq += 1
                    row_out: dict[str, Any] = {
                        "seq": seq,
                        "sid": sid[-8:],
                        "ts": last_timestamp,
                        "kind": row["kind"],
                    }
                    if row["kind"] == "tool_call":
                        row_out["name"] = row["name"]
                    row_out["text"] = row["text"]
                    output.write(json.dumps(row_out, ensure_ascii=False, separators=(",", ":")))
                    output.write("\n")
                    result.records += 1
                    result.kind_counts[row["kind"]] += 1
                    if truncated_kind:
                        result.truncated_counts[truncated_kind] += 1
                    row_timestamp = last_timestamp
                    if row_timestamp:
                        if result.timeline_first_ts is None:
                            result.timeline_first_ts = row_timestamp
                        result.timeline_last_ts = row_timestamp
        os.replace(temp_path, output_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    return result


def parse_iso(timestamp: str | None) -> datetime | None:
    if not timestamp:
        return None
    try:
        value = timestamp.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


def format_span(first: str | None, last: str | None) -> str:
    if not first or not last:
        return "未知"
    start = parse_iso(first)
    end = parse_iso(last)
    if start is None or end is None:
        return f"{first} → {last}"
    seconds = int((end - start).total_seconds())
    days, remainder = divmod(max(seconds, 0), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, secs = divmod(remainder, 60)
    duration = " ".join(
        part
        for part in (
            f"{days}d" if days else "",
            f"{hours}h" if hours else "",
            f"{minutes}m" if minutes else "",
            f"{secs}s" if secs or not (days or hours or minutes) else "",
        )
        if part
    )
    return f"{first} → {last}（{duration}）"


def sample_indices(count: int, sample_size: int = 20) -> set[int]:
    if count <= sample_size:
        return set(range(1, count + 1))
    return {
        1 + int((index * (count - 1) / (sample_size - 1)) + 0.5)
        for index in range(sample_size)
    }


def read_samples(path: Path, count: int) -> list[str]:
    wanted = sample_indices(count)
    samples: list[str] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if line_number in wanted:
                samples.append(line.rstrip("\r\n"))
    return samples


def format_counter(counter: Counter[str]) -> str:
    if not counter:
        return "无"
    return ", ".join(f"`{kind}` {counter[kind]}" for kind in ("user", "assistant", "tool_call", "tool_out", "reasoning") if counter[kind])


def format_truncations(counter: Counter[str]) -> str:
    if not counter:
        return "无（本案例使用默认预算且没有行被字符预算截断）"
    return ", ".join(f"`{kind}` {count} 行" for kind, count in counter.items())


def truncation_judgment(result: PassResult) -> str:
    affected = []
    if result.truncated_counts["user"]:
        affected.append("user 长 continuation/指令的后半段")
    if result.truncated_counts["assistant"]:
        affected.append("assistant 长回复的后半段")
    if result.truncated_counts["reasoning"]:
        affected.append("reasoning 摘要的后半段")
    if result.truncated_counts["tool_out"]:
        affected.append("tool_out 的后半段")
    if not affected:
        return "未发现字符预算截断；tool_call 命令行始终完整保留。"
    return (
        "存在潜在误伤，具体是 "
        + "、".join(affected)
        + "；这类行的截断点之后可能还有决定依据。tool_call 的命令行没有被字符预算截断，"
        "但工具输出和 reasoning 本来就只保留摘要/前缀，因此不能据此证明其后半段没有额外决策信息。"
    )


def build_summary(
    output_dir: Path,
    results: dict[str, PassResult],
    chosen_budgets: dict[str, dict[str, int]],
    samples: dict[str, list[str]],
) -> str:
    lines = [
        "# Rollout 抽取摘要",
        "",
        f"阈值：每份 timeline 最大 `{MAX_TIMELINE_BYTES:,}` bytes；脚本按逐行 JSONL 流式读取，输出可重复覆盖。",
        "",
        "## 实际 JSONL 结构",
        "",
        "抽样并核对 14 个文件后，实际每行都是顶层 `timestamp`、`type`、`payload`。`session_meta` 的 `payload` 含 `session_id/id/cwd/model_provider/dynamic_tools` 等元数据；其 `dynamic_tools` 很深，所以不能依赖有限 JSON 深度解析。消息使用 `type=response_item`、`payload.type=message`，通过 `payload.role=user|assistant` 区分，正文在 `payload.content[]` 的 `input_text/output_text.text`。可读推理使用 `payload.type=reasoning` 的 `summary[]` 中 `summary_text.text`；同记录的 `encrypted_content` 被丢弃。",
        "",
        "工具调用实际出现两种形态：`response_item.payload.type=custom_tool_call` 使用 `name/input/status/call_id`（常见 `name=exec`，其 input 是嵌套的 `tools.shell_command` 或 `tools.exec_command` 调用），旧/协作调用使用 `function_call` 的 `name/namespace/arguments/call_id`（抽样见 `spawn_agent`、`wait`、`list_agents`）。对应结果是 `custom_tool_call_output` 或 `function_call_output` 的 `output`，可能是字符串或含 `text` 的列表。`event_msg` 也有 `user_message/agent_message/agent_reasoning` 镜像事件，本抽取选择 `response_item` 主记录避免重复；`world_state/turn_context/token_count` 等元数据不进入 timeline。",
        "",
        "所有图片、音频、base64/加密字段和明显的超长文件全文回显都被过滤。每个 `tool_call` 行保留工具名；命令类 `exec/shell` 的完整调用参数保留，普通工具参数最多 400 字符。",
        "",
    ]

    for index, case_name in enumerate(CASES, 1):
        result = results[case_name]
        timeline_path = output_dir / f"timeline-{case_name}.jsonl"
        lines.extend(
            [
                f"## 案例 {index}",
                "",
                f"- session 数：{len(CASES[case_name])}",
                f"- session 顺序：{', '.join(CASES[case_name])}",
                f"- rollout 原始总字节：{result.source_bytes:,}",
                f"- timeline 字节：{timeline_path.stat().st_size:,}",
                f"- timeline 记录条数：{result.records:,}",
                f"- kind 分布：{format_counter(result.kind_counts)}",
                f"- rollout 时间跨度：{format_span(result.source_first_ts, result.source_last_ts)}",
                f"- timeline 时间跨度：{format_span(result.timeline_first_ts, result.timeline_last_ts)}",
                f"- 使用预算：user={chosen_budgets[case_name]['user']}，assistant={chosen_budgets[case_name]['assistant']}，reasoning={chosen_budgets[case_name]['reasoning']}，tool_out={chosen_budgets[case_name]['tool_out']}；tool_call 命令参数不设长度上限",
                f"- 字符截断统计：{format_truncations(result.truncated_counts)}",
                f"- 解析异常行：{result.invalid_json}；过滤的编码/媒体片段：{result.redacted_base64}",
                "",
                "### 决策信息截断判断",
                "",
                truncation_judgment(result),
                "",
                "### 时间线抽样（20 条）",
                "",
                "```jsonl",
            ]
        )
        lines.extend(samples[case_name])
        lines.extend(["```", ""])
    return "\n".join(lines) + "\n"


def run(args: argparse.Namespace) -> int:
    sessions_root = resolve_sessions_root(args.sessions_root)
    output_dir = args.output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = locate_rollouts(sessions_root)

    budget_passes = (
        {"user": 600, "assistant": 600, "reasoning": 300, "tool_out": 200},
        {"user": 600, "assistant": 600, "reasoning": 300, "tool_out": 100},
        {"user": 600, "assistant": 600, "reasoning": 150, "tool_out": 100},
        {"user": 600, "assistant": 300, "reasoning": 150, "tool_out": 100},
    )

    results: dict[str, PassResult] = {}
    chosen_budgets: dict[str, dict[str, int]] = {}
    for case_name, session_ids in CASES.items():
        output_path = output_dir / f"timeline-{case_name}.jsonl"
        for budget in budget_passes:
            result = write_case_timeline(case_name, session_ids, paths, output_path, budget)
            size = output_path.stat().st_size
            if size <= MAX_TIMELINE_BYTES:
                results[case_name] = result
                chosen_budgets[case_name] = dict(budget)
                break
        else:
            raise RuntimeError(
                f"{output_path.name} remains over {MAX_TIMELINE_BYTES} bytes after all allowed reductions: "
                f"{output_path.stat().st_size} bytes"
            )

    samples = {
        case_name: read_samples(
            output_dir / f"timeline-{case_name}.jsonl", results[case_name].records
        )
        for case_name in CASES
    }
    summary_path = output_dir / "timeline-summary.md"
    summary_path.write_text(
        build_summary(output_dir, results, chosen_budgets, samples),
        encoding="utf-8",
        newline="\n",
    )

    for case_name in CASES:
        path = output_dir / f"timeline-{case_name}.jsonl"
        print(f"{path.name}: {path.stat().st_size} bytes, {results[case_name].records} records")
    print(f"timeline-summary.md: {summary_path.stat().st_size} bytes")
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(parse_args(argv))
    except (FileNotFoundError, RuntimeError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

