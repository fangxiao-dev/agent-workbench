import argparse
import collections
import datetime as dt
import json
import re
from pathlib import Path


DEFAULT_FILES = [
    r"C:\Users\Xiao\.codex\sessions\2026\08\11\rollout-2026-08-11T15-51-52-019ff118-08c4-72a1-9189-aac3c4a74b7c.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\12\rollout-2026-08-12T21-38-29-019ff77b-bd60-7d71-8035-e7410b23ab89.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T01-00-17-019ff834-7ee0-7a90-b36e-a1f4303c5238.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T06-27-26-019ff960-0217-7e83-acfa-cd1b6c7e5ab4.jsonl",
    r"C:\Users\Xiao\.codex\sessions\2026\08\13\rollout-2026-08-13T09-42-10-019ffa12-4994-7ea3-ac29-3ca4498304e7.jsonl",
]

MAX_TEXT = 30000
MAX_OUTPUT = 50000


def parse_ts(value):
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def compact_text(value, limit=MAX_TEXT):
    if value is None:
        return ""
    if not isinstance(value, str):
        try:
            value = json.dumps(value, ensure_ascii=False)
        except Exception:
            value = str(value)
    if len(value) <= limit:
        return value
    half = max(1000, (limit - 100) // 2)
    return value[:half] + "\n...[TRUNCATED %d CHARS]...\n" % (len(value) - 2 * half) + value[-half:]


def string_parts(value, depth=0):
    if depth > 5:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(string_parts(item, depth + 1))
        return out
    if isinstance(value, dict):
        out = []
        preferred = ("text", "message", "output", "summary", "content", "detail", "description")
        seen = set()
        for key in preferred:
            if key in value:
                seen.add(key)
                out.extend(string_parts(value[key], depth + 1))
        for key, item in value.items():
            if key not in seen and key not in {"data", "image", "blob", "bytes"}:
                if isinstance(item, (str, list, dict)):
                    out.extend(string_parts(item, depth + 1))
        return out
    return []


def payload_text(payload):
    if not isinstance(payload, dict):
        return ""
    ptype = payload.get("type")
    if ptype == "function_call":
        return str(payload.get("arguments", ""))
    if ptype == "function_call_output":
        return compact_text("\n".join(string_parts(payload.get("output", ""))), MAX_OUTPUT)
    if ptype == "custom_tool_call_output":
        return compact_text("\n".join(string_parts(payload.get("output", ""))), MAX_OUTPUT)
    if ptype == "message":
        return "\n".join(part for part in string_parts(payload.get("content", [])) if part)
    if ptype == "reasoning":
        return "\n".join(part for part in string_parts(payload) if part)
    return "\n".join(part for part in string_parts(payload) if part)


def safe_call_args(payload):
    args = payload.get("arguments", "") if isinstance(payload, dict) else ""
    if not isinstance(args, str):
        args = json.dumps(args, ensure_ascii=False)
    return compact_text(args, MAX_TEXT)


def iter_events(path):
    with open(path, "r", encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            try:
                event = json.loads(line)
            except Exception as exc:
                yield {"_parse_error": str(exc), "_line_no": line_no}
                continue
            event["_line_no"] = line_no
            yield event


def build_index(files, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    schema = {}
    sessions = []
    all_records = []
    all_calls = []
    for sidx, filename in enumerate(files, 1):
        path = Path(filename)
        label = f"S{sidx}"
        top_counts = collections.Counter()
        payload_counts = collections.Counter()
        events = 0
        parse_errors = []
        timestamps = []
        records = []
        calls_by_id = {}
        order = 0
        for event in iter_events(path):
            line_no = event.get("_line_no")
            if "_parse_error" in event:
                parse_errors.append({"line": line_no, "error": event["_parse_error"]})
                continue
            events += 1
            top_type = event.get("type", "<missing>")
            top_counts[top_type] += 1
            timestamp = event.get("timestamp")
            parsed = parse_ts(timestamp)
            if parsed is not None:
                timestamps.append(parsed)
            payload = event.get("payload")
            ptype = payload.get("type") if isinstance(payload, dict) else None
            if ptype is not None:
                payload_counts[f"{top_type}:{ptype}"] += 1
            order += 1
            base = {
                "session": label,
                "session_file": str(path),
                "line": line_no,
                "order": order,
                "timestamp": timestamp,
                "top_type": top_type,
                "payload_type": ptype,
            }
            if top_type == "response_item" and isinstance(payload, dict):
                if ptype in {"function_call", "custom_tool_call"}:
                    if ptype == "function_call":
                        name = payload.get("name")
                        raw_args = payload.get("arguments", "")
                        call_form = "native"
                    else:
                        name = payload.get("name")
                        raw_args = payload.get("input", "")
                        call_form = "custom_tool"
                    if not isinstance(raw_args, str):
                        raw_args = json.dumps(raw_args, ensure_ascii=False)
                    call = dict(base)
                    call.update({
                        "kind": "function_call",
                        "call_form": call_form,
                        "name": name,
                        "call_id": payload.get("call_id"),
                        "arguments": compact_text(raw_args, MAX_TEXT),
                        "arguments_len": len(raw_args),
                        "output": "",
                        "output_len": 0,
                        "output_line": None,
                        "output_timestamp": None,
                    })
                    records.append(call)
                    calls_by_id[payload.get("call_id")] = call
                elif ptype in {"function_call_output", "custom_tool_call_output"}:
                    call_id = payload.get("call_id")
                    output = "\n".join(string_parts(payload.get("output", "")))
                    call = calls_by_id.get(call_id)
                    if call is not None:
                        call["output"] = compact_text(output, MAX_OUTPUT)
                        call["output_len"] = len(output)
                        call["output_line"] = line_no
                        call["output_timestamp"] = timestamp
                    else:
                        records.append({
                            **base,
                            "kind": "orphan_function_call_output",
                            "call_id": call_id,
                            "output": compact_text(output, MAX_OUTPUT),
                            "output_len": len(output),
                        })
                elif ptype in {"message", "reasoning"}:
                    text = payload_text(payload)
                    records.append({**base, "kind": ptype, "role": payload.get("role"), "text": compact_text(text)})
            elif top_type == "event_msg":
                text = payload_text(payload)
                records.append({**base, "kind": "event_msg", "event_msg_type": ptype, "text": compact_text(text)})
            elif top_type not in {"session_meta"}:
                text = payload_text(payload)
                if text:
                    records.append({**base, "kind": top_type, "text": compact_text(text)})
        session = {
            "session": label,
            "file": str(path),
            "size": path.stat().st_size,
            "events": events,
            "parse_errors": parse_errors,
            "top_type_counts": dict(top_counts),
            "payload_type_counts": dict(payload_counts),
            "start": min(timestamps).isoformat() if timestamps else None,
            "end": max(timestamps).isoformat() if timestamps else None,
            "function_calls": sum(1 for r in records if r.get("kind") == "function_call"),
            "records": len(records),
        }
        sessions.append(session)
        all_records.extend(records)
        all_calls.extend(r for r in records if r.get("kind") == "function_call")
        schema[label] = {"top_type_counts": dict(top_counts), "payload_type_counts": dict(payload_counts)}

    with open(out_dir / "schema_summary.json", "w", encoding="utf-8") as handle:
        json.dump({"sessions": sessions, "schema": schema}, handle, ensure_ascii=False, indent=2)
    with open(out_dir / "records.jsonl", "w", encoding="utf-8") as handle:
        for record in all_records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    with open(out_dir / "function_calls.jsonl", "w", encoding="utf-8") as handle:
        for call in all_calls:
            handle.write(json.dumps(call, ensure_ascii=False) + "\n")
    return sessions, all_records, all_calls


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="analysis_data")
    parser.add_argument("--files", nargs="*", default=DEFAULT_FILES)
    args = parser.parse_args()
    sessions, records, calls = build_index([Path(x) for x in args.files], Path(args.out))
    print(json.dumps({"sessions": sessions, "function_calls": len(calls), "records": len(records)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
