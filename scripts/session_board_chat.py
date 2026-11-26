"""Board assistant: DeepSeek drives board state changes through a small, explicit tool set."""
from __future__ import annotations

import json
import os
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path

ENDPOINT = "https://api.deepseek.com/anthropic/v1/messages"
MODEL = "deepseek-v4-flash"
ACTIVE_WINDOW = 30 * 60
MAX_BULK = 300
STATES = ("进行中", "最近", "已完成", "暂不关注")
# The board stores this lane as 待查看 and shows it as 最近; the assistant only sees the shown name.
LANE_IN = {"待查看": "最近"}
STATE_OUT = {"最近": "待查看"}
SYSTEM = ("你是会话看板的助手。用户会用自然语言让你整理看板状态。"
          "只能通过提供的工具修改看板状态、分组和备注；不能删除或修改原生会话。"
          "先核对再动手：先用 list_items 看结果数量，再执行 update_items，最后用一两句中文说明改了什么。"
          "如果用户的要求会影响到大量会话或语义不清，先问一句再执行。")

TOOLS = [
    {"name": "list_items", "description": "列出看板上的会话（含栏位、最近活动时间、分组、是否后台会话）。",
     "input_schema": {"type": "object", "properties": {
         "lane": {"type": "string", "enum": list(STATES) + ["全部"], "description": "只看某一栏"},
         "title_contains": {"type": "string"},
         "no_activity_days": {"type": "number", "minimum": 0, "description": "只列最近活动早于 N 天的会话"},
         "attention_only": {"type": "boolean", "description": "只列被标记为需关注的会话"},
         "limit": {"type": "integer", "minimum": 1, "maximum": 200}}}},
    {"name": "update_items", "description": "批量修改看板会话的状态 / 分组 / 备注 / 是否在看板隐藏。必须提供至少一个选择条件。",
     "input_schema": {"type": "object", "properties": {
         "lane": {"type": "string", "enum": list(STATES) + ["全部"], "description": "选择该栏内的会话"},
         "title_contains": {"type": "string"},
         "ids": {"type": "array", "items": {"type": "string"}, "description": "直接指定的会话 ID"},
         "no_activity_days": {"type": "number", "minimum": 0, "description": "最近活动早于 N 天"},
         "clear_attention": {"type": "boolean", "description": "清除这些会话的需关注标记"},
         "state": {"type": "string", "enum": list(STATES)},
         "group_name": {"type": "string"},
         "note": {"type": "string"},
         "hidden": {"type": "boolean"}},
         "required": []}},
]


def api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    return (Path.home() / ".claude" / "secrets" / "deepseek.key").read_text(encoding="utf-8").strip()


def column_of(state: str, runtime: str, activity: float, now: float, recent_days: float = 1) -> str:
    """Same rule the board uses: user-set state wins, otherwise place by activity."""
    if state and state != "自动":
        return state
    age = now - float(activity or 0)
    # A busy session can sit quiet for a while (long tool run), so "running" alone counts.
    if runtime == "运行中" or age <= ACTIVE_WINDOW:
        return "进行中"
    return "待查看" if age <= recent_days * 86400 else "暂不关注"


def _rows(db_path: Path, home: Path) -> list[dict]:
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import session_board as sb  # local import keeps the module standalone
    live = sb.live_sessions(home)
    now = __import__("time").time()
    db = sqlite3.connect(db_path, timeout=20)
    db.row_factory = sqlite3.Row
    continued = {r[0] for r in db.execute("SELECT fork_of FROM items WHERE ifnull(fork_of,'')<>''")}
    out = []
    days = sb.recent_days(db)
    for row in db.execute("""SELECT id,title,cwd,group_name,note,state,source_time,hidden,entrypoint,human,
                                    attention_generation, attention_position,
                                    (SELECT MAX(event_time) FROM events WHERE item_id=items.id) AS last_event,
                                    (SELECT attention FROM summaries WHERE item_id=items.id) AS attention,
                                    (SELECT generation FROM summaries WHERE item_id=items.id) AS summary_generation,
                                    (SELECT position FROM summaries WHERE item_id=items.id) AS summary_position
                             FROM items WHERE hidden=0 ORDER BY source_time DESC"""):
        if row["id"] in continued:
            continue  # continued by a newer rewind/fork file
        if (row["entrypoint"] or "").startswith("sdk") or (not row["title"] and not row["human"]):
            continue  # background/sub sessions stay out of scope
        runtime = live.get(row["id"], {}).get("status", "未知")
        activity = sb.parse_activity([{"event_time": row["last_event"]}]) or row["source_time"]
        lane = column_of(row["state"], runtime, activity, now, days)
        pending = bool(row["attention"] and (row["summary_generation"], row["summary_position"])
                       > (row["attention_generation"], row["attention_position"]))
        out.append({"id": row["id"], "title": row["title"] or "", "lane": "最近" if lane == "待查看" else lane,
                    "pending": pending, "attention": row["attention"] or "",
                    "runtime": runtime, "days_since_activity": round((now - activity) / 86400, 1),
                    "group_name": row["group_name"], "note": row["note"], "background": bool((row["entrypoint"] or "").startswith("sdk") or (not row["title"] and not row["human"]))})
    db.close()
    return out


def list_items(db_path: Path, home: Path, args: dict) -> dict:
    rows = _rows(db_path, home)
    lane = LANE_IN.get(args.get("lane"), args.get("lane"))
    if lane and lane != "全部":
        rows = [r for r in rows if r["lane"] == lane]
    needle = (args.get("title_contains") or "").strip().lower()
    if needle:
        rows = [r for r in rows if needle in r["title"].lower()]
    if args.get("no_activity_days") is not None:
        cutoff = float(args["no_activity_days"])
        rows = [r for r in rows if r["days_since_activity"] >= cutoff]
    if args.get("attention_only"):
        rows = [r for r in rows if r.get("pending")]
    limit = int(args.get("limit") or 40)
    return {"count": len(rows), "items": rows[:limit]}


def update_items(db_path: Path, home: Path, args: dict) -> dict:
    changes = {k: args[k] for k in ("state", "group_name", "note", "hidden") if k in args}
    clear_attention = bool(args.get("clear_attention"))
    if not changes and not clear_attention:
        raise ValueError("没有要修改的字段")
    if "state" in changes:
        if changes["state"] not in STATES:
            raise ValueError("状态无效")
        changes["state"] = STATE_OUT.get(changes["state"], changes["state"])
    if not any(k in args for k in ("lane", "title_contains", "ids", "no_activity_days")):
        raise ValueError("必须提供选择条件，避免误改全部会话")
    rows = _rows(db_path, home)
    if args.get("ids"):
        ids = set(args["ids"])
        rows = [r for r in rows if r["id"] in ids]
    lane = LANE_IN.get(args.get("lane"), args.get("lane"))
    if lane and lane != "全部":
        rows = [r for r in rows if r["lane"] == lane]
    needle = (args.get("title_contains") or "").strip().lower()
    if needle:
        rows = [r for r in rows if needle in r["title"].lower()]
    if "no_activity_days" in args:
        cutoff = float(args["no_activity_days"])
        rows = [r for r in rows if r["days_since_activity"] >= cutoff]
    if len(rows) > MAX_BULK:
        raise ValueError(f"命中 {len(rows)} 个会话，超过单次上限 {MAX_BULK}，请缩小范围")
    db = sqlite3.connect(db_path, timeout=20)
    try:
        with db:
            for row in rows:
                sets, values = [], []
                for key, value in changes.items():
                    sets.append(f"{key}=?")
                    values.append(int(value) if key == "hidden" else value)
                if sets:
                    db.execute(f"UPDATE items SET {', '.join(sets)} WHERE id=?", (*values, row["id"]))
                if clear_attention:
                    # Acknowledge the summary that raised the flag; a newer summary raises it again.
                    db.execute("UPDATE items SET attention_generation=ifnull("
                               "(SELECT generation FROM summaries WHERE item_id=items.id),-1),"
                               " attention_position=ifnull((SELECT position FROM summaries WHERE item_id=items.id),-1)"
                               " WHERE id=?", (row["id"],))
    finally:
        db.close()
    return {"changed": len(rows), "titles": [r["title"][:30] for r in rows[:10]]}


def _count_usage(db_path: Path, usage) -> None:
    if not isinstance(usage, dict):
        return
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from scripts import session_board as sb
    sb.add_usage(db_path, "chat", usage)


def run_tool(db_path: Path, home: Path, name: str, args: dict) -> dict:
    if name == "list_items":
        return list_items(db_path, home, args or {})
    if name == "update_items":
        return update_items(db_path, home, args or {})
    raise ValueError(f"未知工具 {name}")


def chat(db_path: Path, home: Path, message: str, timeout: int = 90) -> dict:
    messages = [{"role": "user", "content": message[:2000]}]
    actions: list[str] = []
    for _ in range(5):
        body = {"model": MODEL, "max_tokens": 1500, "thinking": {"type": "enabled"}, "reasoning_effort": "low",
                "system": SYSTEM, "tools": TOOLS, "messages": messages}
        request = urllib.request.Request(ENDPOINT, data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json", "x-api-key": api_key(),
                                                  "anthropic-version": "2023-06-01"}, method="POST")
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(request, timeout=timeout) as response:
            data = json.loads(response.read(2 * 1024 * 1024))
        _count_usage(db_path, data.get("usage"))
        blocks = data.get("content") or []
        if data.get("stop_reason") != "tool_use":
            text = "".join(b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text").strip()
            return {"reply": text or "（没有返回内容）", "actions": actions}
        messages.append({"role": "assistant", "content": blocks})
        results = []
        for block in blocks:
            if not isinstance(block, dict) or block.get("type") != "tool_use":
                continue
            try:
                out = run_tool(db_path, home, block.get("name"), block.get("input") or {})
                text = json.dumps(out, ensure_ascii=False)[:4000]
                if block.get("name") == "update_items":
                    actions.append(f"修改 {out['changed']} 个会话")
            except (ValueError, sqlite3.Error) as exc:
                text = f"错误：{exc}"
            results.append({"type": "tool_result", "tool_use_id": block.get("id"), "content": text})
        messages.append({"role": "user", "content": results})
    return {"reply": "执行步数过多，已停止；请缩小范围再试。", "actions": actions}
