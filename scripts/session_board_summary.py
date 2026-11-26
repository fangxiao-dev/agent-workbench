"""Optional user-configured summary command; session text is supplied on stdin."""
from __future__ import annotations

import json
import sqlite3
import subprocess
import threading
import time

_LOCK = threading.Lock()


def _record_usage(db_path, usage: dict) -> None:
    try:
        from scripts import session_board as board  # imported late: the board imports this module
    except ModuleNotFoundError:
        import session_board as board
    board.add_usage(db_path, "summary", usage)


def summarize(command: list[str], payload: dict, timeout: int = 60) -> dict:
    if not command or any(not isinstance(arg, str) or not arg for arg in command):
        raise ValueError("摘要命令格式无效")
    result = subprocess.run(command, input=json.dumps(payload, ensure_ascii=False), text=True,
                            encoding="utf-8", stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=timeout, check=False, shell=False)
    if result.returncode:
        tail = (result.stderr or '').strip().splitlines()
        raise RuntimeError((tail[-1][:80] if tail else '') or "摘要命令执行失败")
    try:
        response = json.loads(result.stdout)
    except (json.JSONDecodeError, UnicodeError) as exc:
        raise ValueError("摘要命令没有返回有效 JSON") from exc
    if not isinstance(response, dict) or not isinstance(response.get("summary"), str) or not isinstance(response.get("attention", ""), str):
        raise ValueError("摘要结果需要 summary 和 attention 文本")
    usage = response.get("usage")
    return {"summary": response["summary"][:2000], "attention": response.get("attention", "")[:1000],
            "usage": usage if isinstance(usage, dict) else None}


def update_summaries(db_path, command: list[str], wanted: set[str] | None = None, min_gap: int = 30) -> None:
    if not _LOCK.acquire(blocking=False):
        return
    try:
        db = sqlite3.connect(db_path, timeout=20)
        db.row_factory = sqlite3.Row
        db.execute("""CREATE TABLE IF NOT EXISTS summaries (
          item_id TEXT PRIMARY KEY, generation INTEGER NOT NULL, position INTEGER NOT NULL,
          summary TEXT NOT NULL, attention TEXT NOT NULL, created_at REAL NOT NULL,
          error TEXT NOT NULL DEFAULT '', attempted_at REAL NOT NULL DEFAULT 0)""")
        db.commit()
        # Finished or muted items are not worth model calls.
        # Background/sub sessions are hidden on the board by default: skip them so calls are not spent on content the user never sees.
        ids = [r[0] for r in db.execute(
            "SELECT id FROM items WHERE hidden=0 AND state IN ('自动','待查看','进行中')"
            " AND NOT (ifnull(entrypoint,'') LIKE 'sdk%' OR (ifnull(title,'')='' AND human=0)) ORDER BY source_time DESC")]
        if wanted is not None:
            ids = [ident for ident in ids if ident in wanted]
        attempted = 0
        now = time.time()
        for ident in ids:
            item = db.execute("SELECT * FROM items WHERE id=? AND hidden=0", (ident,)).fetchone()
            events = db.execute("SELECT generation,position,kind,text,event_time FROM events WHERE item_id=? ORDER BY generation DESC,position DESC LIMIT 12", (ident,)).fetchall()
            if not item or not events:
                continue
            newest = events[0]
            previous = db.execute("SELECT * FROM summaries WHERE item_id=?", (ident,)).fetchone()
            # Only when the conversation moved since the last summary, and never faster than the refresh interval.
            if previous and ((previous['generation'], previous['position']) >= (newest['generation'], newest['position'])
                             or (previous['attempted_at'] and now - previous['attempted_at'] < min_gap)
                             or (previous['error'] and now - previous['attempted_at'] < max(min_gap, 300))):
                continue
            payload = {"title": item['title'], "note": item['note'], "scope": "最近最多12条消息",
                       "events": [{"kind": e['kind'], "text": e['text'], "time": e['event_time']} for e in reversed(events)]}
            try:
                result = summarize(command, payload)
                if result.get("usage"):
                    _record_usage(db_path, result["usage"])
                with db:
                    db.execute("""INSERT INTO summaries VALUES(?,?,?,?,?,?, '', ?) ON CONFLICT(item_id) DO UPDATE SET
                      generation=excluded.generation,position=excluded.position,summary=excluded.summary,
                      attention=excluded.attention,created_at=excluded.created_at,error='',attempted_at=excluded.attempted_at""",
                      (ident, newest['generation'], newest['position'], result['summary'], result['attention'], time.time(), time.time()))
            except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired, UnicodeError) as exc:
                reason = ('超时' if isinstance(exc, subprocess.TimeoutExpired) else str(exc) or type(exc).__name__)[:80]
                with db:
                    db.execute("""INSERT INTO summaries VALUES(?, -1, -1, '', '', 0, ?, ?)
                      ON CONFLICT(item_id) DO UPDATE SET error=excluded.error,attempted_at=excluded.attempted_at""",
                               (ident, '摘要生成失败：' + reason, time.time()))
            attempted += 1
            if attempted >= 8:
                break
        db.close()
    finally:
        _LOCK.release()
