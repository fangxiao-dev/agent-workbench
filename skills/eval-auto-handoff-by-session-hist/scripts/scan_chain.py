#!/usr/bin/env python3
"""Reconstruct the real lineage chain of Codex auto-handoff sessions.

Deterministically replaces the manual chain-reconstruction phase: locates
rollout files by session id, extracts lineage evidence, follows spawn edges
to discover missing links, and reports claimed-vs-real order mismatches.

Evidence policy (mirrors the skill's Core Principles):
- HARD  : parent-side create_thread/fork_thread function_call_output threadId;
          child-side session_meta.thread_source.
- SOFT  : <source_thread_id> inside codex_delegation envelopes. The OUTERMOST
          one is platform-generated (usually right); NESTED ones are hand-copied
          and frequently stale. Reported only for cross-checking.

Usage:
  python scan_chain.py <session-id> [<session-id> ...]
      [--sessions-dir ~/.codex/sessions] [--no-follow] [--json]

Output: markdown chain table + warnings on stdout (or JSON with --json).
"""
import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
SRC_RE = re.compile(r"<source_thread_id>\s*([0-9a-f-]{36})\s*</source_thread_id>", re.I)


def parse_ts(ts):
    """Parse rollout ISO timestamp; returns None on failure."""
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def find_file(sessions_dir, sid):
    """Locate a rollout file by session-id substring under sessions_dir."""
    hits = sorted(sessions_dir.rglob(f"*{sid}*.jsonl"))
    return hits[0] if hits else None


def scan_file(path):
    """Single pass over one rollout file; collect lineage + window facts."""
    node = {
        "path": str(path),
        "size_kb": round(path.stat().st_size / 1024),
        "id": None,
        "cwd": None,
        "thread_source": None,
        "first_ts": None,
        "last_ts": None,
        "spawn_attempts": [],   # (tool, ok, child_id_or_error_head)
        "children": [],         # successfully spawned thread ids, in order
        "envelope_ids": [],     # source_thread_id values in first user msgs, outermost first
    }
    pending = {}  # call_id -> tool name, for create/fork_thread output matching
    user_msgs_seen = 0
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            try:
                o = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = o.get("timestamp")
            if ts:
                node["first_ts"] = node["first_ts"] or ts
                node["last_ts"] = ts
            pl = o.get("payload") or {}
            if o.get("type") == "session_meta":
                node["id"] = pl.get("id")
                node["cwd"] = pl.get("cwd")
                node["thread_source"] = pl.get("thread_source")
                continue
            pt = pl.get("type")
            if pt == "function_call" and pl.get("name") in ("create_thread", "fork_thread"):
                pending[pl.get("call_id")] = pl.get("name")
            elif pt == "function_call_output" and pl.get("call_id") in pending:
                tool = pending.pop(pl["call_id"])
                out = pl.get("output")
                s = out if isinstance(out, str) else json.dumps(out, ensure_ascii=False)
                m = UUID_RE.search(s or "")
                if m and "threadId" in (s or ""):
                    node["children"].append(m.group(0).lower())
                    node["spawn_attempts"].append((tool, True, m.group(0).lower()))
                else:
                    node["spawn_attempts"].append((tool, False, (s or "")[:120].replace("\n", " ")))
            elif pt == "message" and pl.get("role") == "user" and user_msgs_seen < 4 and not node["envelope_ids"]:
                # Envelope sits in one of the first user messages (after AGENTS preamble).
                user_msgs_seen += 1
                text = "".join(c.get("text", "") for c in pl.get("content") or [] if isinstance(c, dict))
                node["envelope_ids"] = [x.lower() for x in SRC_RE.findall(text)]
    return node


def fmt_window(node):
    a, b = parse_ts(node["first_ts"]), parse_ts(node["last_ts"])
    if not a or not b:
        return "?", "?"
    mins = int((b - a).total_seconds() // 60)
    return f"{a:%m-%d %H:%M}–{b:%H:%M}Z", f"{mins}m"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="+", help="claimed session ids, in claimed order")
    ap.add_argument("--sessions-dir", default=str(Path.home() / ".codex" / "sessions"))
    ap.add_argument("--no-follow", action="store_true", help="do not auto-scan discovered missing links")
    ap.add_argument("--json", action="store_true", help="emit machine-readable JSON instead of markdown")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except AttributeError:
        pass

    sessions_dir = Path(args.sessions_dir).expanduser()
    claimed = [x.lower() for x in args.ids]
    nodes, not_found, queue, seen = {}, [], list(claimed), set()
    while queue:
        sid = queue.pop(0)
        if sid in seen:
            continue
        seen.add(sid)
        path = find_file(sessions_dir, sid)
        if not path:
            not_found.append(sid)
            continue
        node = scan_file(path)
        node["discovered"] = sid not in claimed
        nodes[sid] = node
        if not args.no_follow:
            queue.extend(c for c in node["children"] if c not in seen)

    parent_of = {c: pid for pid, n in nodes.items() for c in n["children"]}
    # Chain order: roots first (no known parent), then follow spawn edges.
    roots = [sid for sid in nodes if sid not in parent_of]
    order, visited = [], set()
    for r in sorted(roots, key=lambda s: nodes[s]["first_ts"] or ""):
        cur = [r]
        while cur:
            sid = cur.pop(0)
            if sid in visited:
                continue
            visited.add(sid)
            order.append(sid)
            cur = sorted((c for c in nodes[sid]["children"] if c in nodes),
                         key=lambda s: nodes[s]["first_ts"] or "") + cur

    warnings = []
    real_claimed = [sid for sid in order if sid in claimed]
    if real_claimed != claimed:
        warnings.append("claimed order != real chain order — report this as a headline finding")
    for sid in nodes:
        n = nodes[sid]
        if n["discovered"]:
            warnings.append(f"missing link discovered (not in claimed list): {sid}")
        actual = parent_of.get(sid)
        if n["envelope_ids"] and actual and n["envelope_ids"][0] != actual:
            warnings.append(f"{sid}: outermost envelope claims {n['envelope_ids'][0]} but real parent is {actual}")
        if len(n["envelope_ids"]) > 1:
            stale = [e for e in n["envelope_ids"][1:] if e != actual]
            if stale:
                warnings.append(f"{sid}: nested envelope ids {stale} differ from real parent {actual} (hand-copied lineage, untrusted)")
        if n["thread_source"] == "subagent" and not actual:
            warnings.append(f"{sid}: thread_source=subagent but parent not found among scanned files")
        for tool, ok, detail in n["spawn_attempts"]:
            if not ok:
                warnings.append(f"{sid}: failed {tool} attempt: {detail}")
    for sid in not_found:
        warnings.append(f"session file not found for: {sid}")

    if args.json:
        print(json.dumps({"order": order, "claimed": claimed, "nodes": nodes, "warnings": warnings},
                         ensure_ascii=False, indent=1))
        return

    print("# Reconstructed Chain\n")
    print("| # | session id | window (UTC) | dur | source | spawned | size | claimed pos |")
    print("|---|------------|--------------|-----|--------|---------|------|-------------|")
    for i, sid in enumerate(order, 1):
        n = nodes[sid]
        win, dur = fmt_window(n)
        spawned = ", ".join(c[:13] for c in n["children"]) or "—"
        pos = "MISSING from claimed list" if n["discovered"] else f"#{claimed.index(sid) + 1}"
        print(f"| {i} | `{sid}` | {win} | {dur} | {n['thread_source']} | {spawned} | {n['size_kb']}KB | {pos} |")
    print("\n## Files\n")
    for sid in order:
        print(f"- `{sid[:13]}` → {nodes[sid]['path']}")
    print("\n## Warnings\n")
    for w in warnings or ["(none) chain evidence is internally consistent"]:
        print(f"- ⚠️ {w}" if warnings else f"- {w}")


if __name__ == "__main__":
    main()
