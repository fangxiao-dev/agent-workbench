"""A local, read-only observer for Claude session transcripts."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
import threading
import tempfile
import time
from collections import deque
from datetime import datetime
try:
    from scripts import session_board_chat, session_board_hosts, session_board_summary
except ModuleNotFoundError:
    import session_board_chat
    import session_board_hosts
    import session_board_summary
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HTML = Path(__file__).with_name("session_board.html")
WEEK = 7 * 86400
INITIAL_BYTES = 128 * 1024
HEAD_BYTES = 256 * 1024
MAX_LINE = 4 * 1024 * 1024
UUID = re.compile(r"^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$", re.I)
INJECTED = re.compile(r"^(<[a-z][a-z-]*[\s>]|\[Request interrupted)")
SYNC_LOCK = threading.Lock()
HOST = session_board_hosts.get_host()   # swap here to support another host
LIVE_LOCK = threading.Lock()
LIVE_CACHE = {}


def open_db(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=20)
    db.row_factory = sqlite3.Row
    db.executescript("""
    PRAGMA journal_mode=WAL;
    CREATE TABLE IF NOT EXISTS items (
      id TEXT PRIMARY KEY, path TEXT NOT NULL, title TEXT NOT NULL DEFAULT '', cwd TEXT NOT NULL DEFAULT '',
      source_time REAL NOT NULL DEFAULT 0, cursor INTEGER NOT NULL DEFAULT 0, identity TEXT NOT NULL DEFAULT '',
      generation INTEGER NOT NULL DEFAULT 0, limited INTEGER NOT NULL DEFAULT 0,
      prefix_len INTEGER NOT NULL DEFAULT 0, prefix_hash TEXT NOT NULL DEFAULT '', aligning INTEGER NOT NULL DEFAULT 0, entrypoint TEXT, human INTEGER NOT NULL DEFAULT 0, fork_of TEXT,
      state TEXT NOT NULL DEFAULT '待查看', group_name TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
      hidden INTEGER NOT NULL DEFAULT 0, read_generation INTEGER NOT NULL DEFAULT 0, read_cursor INTEGER NOT NULL DEFAULT 0,
      read_at REAL, synced_at REAL, error TEXT NOT NULL DEFAULT ''
    );
    CREATE TABLE IF NOT EXISTS events (
      item_id TEXT NOT NULL, generation INTEGER NOT NULL, position INTEGER NOT NULL,
      kind TEXT NOT NULL, text TEXT NOT NULL, event_time TEXT NOT NULL DEFAULT '',
      PRIMARY KEY(item_id, generation, position)
    );
    CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS usage (at REAL NOT NULL, kind TEXT NOT NULL,
      in_tokens INTEGER NOT NULL DEFAULT 0, out_tokens INTEGER NOT NULL DEFAULT 0);
    CREATE TABLE IF NOT EXISTS summaries (
      item_id TEXT PRIMARY KEY, generation INTEGER NOT NULL, position INTEGER NOT NULL,
      summary TEXT NOT NULL, attention TEXT NOT NULL, created_at REAL NOT NULL,
      error TEXT NOT NULL DEFAULT '', attempted_at REAL NOT NULL DEFAULT 0
    );
    """)
    with db:
        db.execute('BEGIN IMMEDIATE')
        for table, columns in {
            'items': {'prefix_len': 'INTEGER NOT NULL DEFAULT 0', 'prefix_hash': "TEXT NOT NULL DEFAULT ''",
                      'aligning': 'INTEGER NOT NULL DEFAULT 0', 'entrypoint': 'TEXT', 'fork_of': 'TEXT',
                      'human': 'INTEGER NOT NULL DEFAULT 0', 'fork_of': 'TEXT'},
            'summaries': {'attempted_at': 'REAL NOT NULL DEFAULT 0'},
        }.items():
            existing = {row['name'] for row in db.execute(f'PRAGMA table_info({table})')}
            for name, definition in columns.items():
                if name not in existing:
                    db.execute(f'ALTER TABLE {table} ADD COLUMN {name} {definition}')
    return db


def visible_text(record: dict) -> tuple[str, str] | None:
    kind = record.get("type")
    if kind not in ("user", "assistant") or record.get("isSidechain") or record.get("isMeta"):
        return None
    message = record.get("message")
    if not isinstance(message, dict) or message.get("role") != kind:
        return None
    content = message.get("content")
    if isinstance(content, str):
        text = content
    elif isinstance(content, list):
        text = "\n".join(str(block.get("text", "")) for block in content
                         if isinstance(block, dict) and block.get("type") == "text")
    else:
        return None
    text = text.strip()
    # Harness-injected wrappers (<task-notification>, <system-reminder>, ...) are not conversation.
    if not text or (kind == "user" and INJECTED.match(text)):
        return None
    if kind == "assistant" and text.lower().rstrip(".") == "no response requested":
        return None
    return kind, text[:2000]


def classify(path: Path) -> tuple[str, int, str]:
    """Host-specific metadata for one transcript, via the active adapter."""
    return HOST.classify(path)


def sync_file(db: sqlite3.Connection, path: Path, now: float) -> None:
    ident = path.stem
    if not UUID.fullmatch(ident):
        return
    info = path.stat()
    if not path.is_file() or path.is_symlink():
        return
    row = db.execute("SELECT * FROM items WHERE id=?", (ident,)).fetchone()
    identity = f"{info.st_dev}:{info.st_ino}"
    prefix_len = row['prefix_len'] if row else 0
    with path.open('rb') as probe:
        prefix = probe.read(prefix_len or min(256, info.st_size))
    prefix_changed = bool(row and prefix_len and hashlib.sha256(prefix).hexdigest() != row['prefix_hash'])
    reset = bool(row and (row["identity"] != identity or info.st_size < row["cursor"] or prefix_changed))
    if reset:
        with path.open('rb') as probe:
            prefix = probe.read(min(256, info.st_size))
    prefix_len = len(prefix)
    prefix_hash = hashlib.sha256(prefix).hexdigest() if prefix else ''
    generation = row["generation"] + int(reset) if row else 0
    start = row['cursor'] if row and not reset else max(0, info.st_size - INITIAL_BYTES)
    limited = bool(row['limited']) if row and not reset else bool(start)
    aligning = bool(row['aligning']) if row and not reset else bool(start)
    events = deque(maxlen=40)
    event_count = 0
    warning = row['error'] if row and not reset and row['error'].startswith('部分') else ''
    title = row["title"] if row else ""
    cwd = row["cwd"] if row else ""
    with path.open("rb") as stream:
        stream.seek(start)
        if aligning:
            alignment = stream.readline(MAX_LINE + 1)
            if alignment.endswith(b'\n'):
                aligning = False
                start = stream.tell()
            elif (not row or reset) and info.st_size <= MAX_LINE:
                stream.seek(0)
                start = 0
                aligning = False
            else:
                # Initial window fell inside an oversized unfinished record.
                start = stream.tell()
                warning = '部分过大记录正在跳过'
        cursor = start
        while not aligning:
            position = stream.tell()
            line = stream.readline(MAX_LINE + 1)
            if not line:
                break
            if len(line) > MAX_LINE:
                cursor = stream.tell()
                aligning = not line.endswith(b'\n')
                warning = '部分过大记录已跳过'
                limited = True
                if aligning:
                    break
                continue
            if not line.endswith(b"\n"):
                break
            cursor = stream.tell()
            try:
                record = json.loads(line)
            except (UnicodeDecodeError, json.JSONDecodeError):
                warning = '部分记录格式无效，已跳过'
                limited = True
                continue
            if not isinstance(record, dict):
                continue
            if record.get("type") == "custom-title" and isinstance(record.get("customTitle"), str):
                title = record["customTitle"][:200]
            if isinstance(record.get("cwd"), str):
                cwd = record["cwd"][:1000]
            text = visible_text(record)
            if text:
                event_count += 1
                if event_count > 40:
                    limited = True
                events.append((ident, generation, position, text[0], text[1], str(record.get("timestamp") or "")[:40]))
    with db:
        db.execute('BEGIN IMMEDIATE')
        latest = db.execute('SELECT cursor,generation,identity FROM items WHERE id=?', (ident,)).fetchone()
        if (row is None and latest is not None) or (row is not None and
                (latest is None or (latest['cursor'], latest['generation'], latest['identity']) !=
                 (row['cursor'], row['generation'], row['identity']))):
            return
        # A newly discovered session starts read: only later activity counts as new.
        # state '自动' = the user has not triaged it; the board places it by runtime/recency.
        db.execute("""INSERT INTO items(id,path,title,cwd,source_time,cursor,identity,generation,limited,prefix_len,prefix_hash,aligning,synced_at,error,read_generation,read_cursor,entrypoint,human,fork_of,state)
          VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'自动') ON CONFLICT(id) DO UPDATE SET
          path=excluded.path,title=excluded.title,cwd=excluded.cwd,source_time=excluded.source_time,
          cursor=excluded.cursor,identity=excluded.identity,generation=excluded.generation,
          limited=excluded.limited,prefix_len=excluded.prefix_len,prefix_hash=excluded.prefix_hash,
          aligning=excluded.aligning,synced_at=excluded.synced_at,error=excluded.error""",
          (ident, str(path), title, cwd, info.st_mtime, cursor, identity, generation, int(limited), prefix_len, prefix_hash, int(aligning), now, warning, generation, cursor, *(classify(path) if row is None else ('', 0, ''))))
        db.executemany("INSERT OR IGNORE INTO events VALUES(?,?,?,?,?,?)", events)
        db.execute("""DELETE FROM events WHERE item_id=? AND rowid NOT IN
                      (SELECT rowid FROM events WHERE item_id=? ORDER BY generation DESC,position DESC LIMIT 40)""", (ident, ident))


def live_sessions(home: Path, fresh: bool = False) -> dict:
    key = str(home.resolve())
    with LIVE_LOCK:
        cached = LIVE_CACHE.get(key)
        if cached and not fresh and time.monotonic() - cached[0] < 5:
            return cached[1]
        result = _live_sessions(home)
        LIVE_CACHE[key] = (time.monotonic(), result)
        return result


def _live_sessions(home: Path) -> dict:
    return HOST.live(home)


def sync(db_path: Path, home: Path) -> dict:
    with SYNC_LOCK:
        return _sync(db_path, home)


def _sync(db_path: Path, home: Path) -> dict:
    db = open_db(db_path)
    now = time.time()
    errors = 0
    if not HOST.transcripts(home):
        db.close()
        return {"ok": False, "error": f"宿主 {HOST.name} 没有可读取的会话"}
    marker = db.execute("SELECT value FROM meta WHERE key='links'").fetchone()
    relink = marker is None or marker['value'] != '4'
    if relink:  # links now also follow compaction; recompute every transcript's parent once
        with db:
            db.execute("UPDATE items SET entrypoint=NULL")
    for old in db.execute("SELECT id,path FROM items WHERE entrypoint IS NULL").fetchall():
        try:
            entry, human, parent = classify(Path(old['path']))
        except OSError:
            entry, human, parent = '', 0, ''
        with db:
            db.execute("UPDATE items SET entrypoint=?,human=?,fork_of=CASE WHEN ?<>'' THEN ? ELSE ifnull(fork_of,'') END WHERE id=?",
                       (entry, human, parent, parent, old['id']))
    if relink:
        with db:
            db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('links','4')")
    try:
        known = {row['id']: row for row in db.execute("SELECT id,source_time,cursor,error,identity FROM items")}
        for path in HOST.transcripts(home):
            try:
                if path.is_symlink() or path.parent.is_symlink():
                    continue
                info = path.stat()
                modified = info.st_mtime
                previous = known.get(path.stem)
                if modified >= now - WEEK:
                    identity = f'{info.st_dev}:{info.st_ino}'
                    if (not previous or previous['source_time'] != modified or previous['cursor'] != info.st_size
                            or previous['identity'] != identity
                            or (previous['error'] and not previous['error'].startswith('部分'))):
                        sync_file(db, path, now)
                elif previous and previous['source_time'] != modified:
                    with db:
                        db.execute("UPDATE items SET source_time=? WHERE id=?", (modified, path.stem))
            except (OSError, ValueError, sqlite3.Error) as exc:
                errors += 1
                with db:
                    db.execute("UPDATE items SET error=? WHERE id=?", (str(exc)[:200], path.stem))
    except OSError:
        db.close()
        return {"ok": False, "error": "扫描会话目录失败"}
    # A session that continues another one (compaction keeps the Desktop conversation, not the file id).
    with db:
        for ident, info in live_sessions(home, fresh=True).items():
            previous = info.get("previous")
            if previous:
                db.execute("UPDATE items SET fork_of=? WHERE id=? AND ifnull(fork_of,'')=''", (previous, ident))
        # The newer transcript replaces the earlier card, so the user's triage has to follow it.
        for link in db.execute("SELECT id, fork_of FROM items WHERE ifnull(fork_of,'')<>''").fetchall():
            prior = db.execute("SELECT state, group_name, note, hidden FROM items WHERE id=?",
                               (link["fork_of"],)).fetchone()
            if prior:
                db.execute("UPDATE items SET state=?, group_name=?, note=?, hidden=? "
                           "WHERE id=? AND state='自动' AND group_name='' AND note='' AND hidden=0",
                           (prior["state"], prior["group_name"], prior["note"], prior["hidden"], link["id"]))
    with db:
        db.execute("DELETE FROM events WHERE item_id IN (SELECT id FROM items WHERE source_time < ?)", (now - WEEK,))
        db.execute("DELETE FROM summaries WHERE item_id IN (SELECT id FROM items WHERE source_time < ?)", (now - WEEK,))
    db.close()
    return {"ok": True, "errors": errors, "time": now}


def superseded_ids(db_path: Path) -> set[str]:
    """Sessions a newer rewind/fork/compaction file continues; they should not appear as separate cards."""
    db = open_db(db_path)
    try:
        ids = {row["id"] for row in db.execute("SELECT id FROM items")}
        parents = {row["fork_of"] for row in db.execute("SELECT fork_of FROM items WHERE ifnull(fork_of,'')<>''")}
    finally:
        db.close()
    return {parent for parent in parents if parent in ids}


def add_usage(db_path: Path, kind: str, usage: dict) -> None:
    # One row per model call: "summary" is the automatic digest, "chat" is what the user asked for.
    try:
        prompt = int(usage.get("input_tokens") or 0)
        answer = int(usage.get("output_tokens") or 0)
    except (TypeError, ValueError, AttributeError):
        return
    if prompt <= 0 and answer <= 0:
        return
    db = open_db(db_path)
    try:
        with db:
            db.execute("INSERT INTO usage(at,kind,in_tokens,out_tokens) VALUES(?,?,?,?)",
                       (time.time(), kind, prompt, answer))
    finally:
        db.close()


def usage_totals(db, since: float) -> dict:
    totals = {kind: [0, 0] for kind in ("summary", "chat")}
    for row in db.execute("SELECT kind, SUM(in_tokens), SUM(out_tokens) FROM usage WHERE at>=? GROUP BY kind",
                          (since,)):
        if row[0] in totals:
            totals[row[0]] = [int(row[1] or 0), int(row[2] or 0)]
    return totals


def usage_ranges(db) -> dict:
    now = time.time()
    midnight = time.mktime(time.localtime()[:3] + (0, 0, 0, 0, 0, -1))
    return {"1h": usage_totals(db, now - 3600), "today": usage_totals(db, midnight),
            "7d": usage_totals(db, now - 7 * 86400)}


def in_temp(cwd: str) -> bool:
    """Worker CLI runs happen in the OS temp dir; the board is for desktop conversations."""
    if not cwd:
        return False
    root = os.path.normcase(os.path.abspath(tempfile.gettempdir())) + os.sep
    return os.path.normcase(os.path.abspath(cwd)).startswith(root)


def recent_days(db) -> int:
    # How far back the 最近 lane reaches; chosen in the lane header, one day unless stored otherwise.
    row = db.execute("SELECT value FROM meta WHERE key='recent_days'").fetchone()
    try:
        days = int(row["value"]) if row else 1
    except (TypeError, ValueError):
        days = 1
    return days if days in (1, 3, 7) else 1


def parse_activity(events: list[dict]) -> float:
    for event in events:
        stamp = event.get("event_time") or ""
        try:
            return datetime.fromisoformat(stamp.replace("Z", "+00:00")).timestamp()
        except ValueError:
            continue
    return 0.0


def list_items(db_path: Path, home: Path) -> list[dict]:
    db = open_db(db_path)
    live = live_sessions(home)
    superseded = {r["fork_of"] for r in db.execute("SELECT fork_of FROM items WHERE ifnull(fork_of,'')<>''")}
    parents = {row["id"]: row["fork_of"] for row in db.execute("SELECT id, fork_of FROM items")}
    items = []
    for row in db.execute("SELECT * FROM items ORDER BY source_time DESC"):
        if row["id"] in superseded:
            continue  # continued by a newer rewind/fork file
        item = dict(row)
        # Background/sub sessions: launched through the SDK, untitled without a human start, or run from a temp dir.
        item['agent'] = bool((row['entrypoint'] or '').startswith('sdk') or (not row['title'] and not row['human'])
                             or in_temp(row['cwd']))
        info = live.get(item["id"], {})
        item["runtime"] = info.get("status", "未知")
        item["link"] = info.get("link", "")
        item["title"] = item["title"] or info.get("name") or ""
        item["events"] = [dict(event) for event in db.execute(
            "SELECT generation,position,kind,text,event_time FROM events WHERE item_id=? ORDER BY generation DESC,position DESC LIMIT 8", (item["id"],))]
        # Activity means the last real message: the host also rewrites bookkeeping lines, which bump the file
        # mtime without anything happening in the conversation.
        item["activity"] = parse_activity(item["events"]) or item["source_time"]
        if not item["title"]:
            # Untitled sessions still need a recognizable label; derive one from the first human message.
            first = next((e["text"] for e in reversed(item["events"]) if e["kind"] == "user"), "")
            item["title"] = " ".join(first.split())[:40] or "未命名会话"
            item["title_derived"] = True
        item["unread"] = any(e["generation"] > item["read_generation"] or
                             (e["generation"] == item["read_generation"] and e["position"] >= item["read_cursor"]) for e in item["events"])
        summary = db.execute("SELECT * FROM summaries WHERE item_id=?", (item['id'],)).fetchone()
        item['summary'] = dict(summary) if summary else None
        if item['summary'] and item['events']:
            latest = item['events'][0]
            item['summary']['stale'] = (summary['generation'], summary['position']) < (latest['generation'], latest['position'])
        depth, walk, seen = 0, parents.get(item["id"]), set()
        while walk and walk in parents and walk not in seen:
            seen.add(walk)
            depth += 1
            walk = parents.get(walk)
        item["forks"] = depth
        for field in ("path", "identity", "prefix_hash", "prefix_len", "fork_of"):
            item.pop(field, None)
        items.append(item)
    db.close()
    return items


def update_item(db_path: Path, ident: str, data: dict) -> None:
    allowed = {"state", "group_name", "note", "hidden", "mark_read", "read_generation", "read_cursor"}
    if not UUID.fullmatch(ident) or not isinstance(data, dict) or not data or set(data) - allowed:
        raise ValueError("无效请求")
    if "state" in data and data["state"] not in ("待查看", "进行中", "暂不关注", "已完成"):
        raise ValueError("无效状态")
    for key, limit in (("group_name", 100), ("note", 2000)):
        if key in data and (not isinstance(data[key], str) or len(data[key]) > limit):
            raise ValueError("内容过长或格式错误")
    if any(key in data and not isinstance(data[key], bool) for key in ("hidden", "mark_read")):
        raise ValueError("无效标记")
    if data.get("mark_read") and any(type(data.get(key)) is not int or data[key] < 0 for key in ("read_generation", "read_cursor")):
        raise ValueError("缺少已展示位置")
    db = open_db(db_path)
    try:
        with db:
            row = db.execute("SELECT * FROM items WHERE id=?", (ident,)).fetchone()
            if row is None:
                raise ValueError("会话不存在")
            for key in ("state", "group_name", "note", "hidden"):
                if key in data:
                    db.execute(f"UPDATE items SET {key}=? WHERE id=?", (data[key], ident))
            if data.get("mark_read"):
                requested = (data['read_generation'], data['read_cursor'])
                current = (row['generation'], row['cursor'])
                previous = (row['read_generation'], row['read_cursor'])
                if requested > current or requested[0] != current[0]:
                    raise ValueError("会话已更新，请刷新后重试")
                if requested >= previous:
                    db.execute("UPDATE items SET read_generation=?,read_cursor=?,read_at=? WHERE id=?",
                               (*requested, time.time(), ident))
    finally:
        db.close()


def summary_ids(db_path: Path, home: Path) -> set[str]:
    """Sessions worth a model call: the running lane only, minus background and "btw:" side questions."""
    live = live_sessions(home)
    db = open_db(db_path)
    days = recent_days(db)
    wanted = set()
    try:
        for row in db.execute("""SELECT id,title,entrypoint,human,state,source_time,
                              (SELECT MAX(event_time) FROM events WHERE item_id=items.id) AS last_event
                              FROM items WHERE hidden=0"""):
            if (row['entrypoint'] or '').startswith('sdk') or (not row['title'] and not row['human']):
                continue
            if (row['title'] or '').strip().lower().startswith('btw'):
                continue
            activity = parse_activity([{'event_time': row['last_event']}]) or row['source_time']
            column = session_board_chat.column_of(row['state'], live.get(row['id'], {}).get('status', '未知'),
                                                  activity, time.time(), days)
            if column == '进行中':
                wanted.add(row['id'])
    finally:
        db.close()
    return wanted - superseded_ids(db_path)


def make_handler(db_path: Path, home: Path, token: str, port: int, summary_command: list[str] | None = None):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def permitted(self, write=False):
            host = self.headers.get("Host", "")
            origin = self.headers.get("Origin")
            expected = f"http://127.0.0.1:{port}"
            return (host == f"127.0.0.1:{port}" and (not origin or origin == expected)
                    and (not write or (origin == expected and secrets.compare_digest(self.headers.get("X-Board-Token", ""), token))))

        def reply(self, status, body, content_type="application/json; charset=utf-8"):
            content = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'")
            self.end_headers()
            self.wfile.write(content)

        def do_GET(self):
            if not self.permitted():
                return self.reply(403, {"error": "请求来源不允许"})
            path = urlsplit(self.path).path
            if path == "/":
                page = HTML.read_text(encoding="utf-8").replace("__BOARD_TOKEN__", token)
                return self.reply(200, page.encode("utf-8"), "text/html; charset=utf-8")
            if path == "/api/items":
                if not secrets.compare_digest(self.headers.get('X-Board-Token', ''), token):
                    return self.reply(403, {'error': '请求未授权'})
                db = open_db(db_path)
                try:
                    days = recent_days(db)
                    usage = usage_ranges(db)
                finally:
                    db.close()
                return self.reply(200, {"items": list_items(db_path, home), "recent_days": days, "usage": usage})
            return self.reply(404, {"error": "未找到"})

        def do_POST(self):
            if not self.permitted(write=True):
                return self.reply(403, {"error": "请求来源不允许"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if not 0 < length <= 8192:
                    raise ValueError("请求大小无效")
                data = json.loads(self.rfile.read(length))
                path = urlsplit(self.path).path
                if path == "/api/sync":
                    result = sync(db_path, home)
                    if result.get('ok') and summary_command:
                        wanted = summary_ids(db_path, home)
                        threading.Thread(target=session_board_summary.update_summaries,
                                         args=(db_path, summary_command, wanted), daemon=True).start()
                    return self.reply(200, result)
                if path == "/api/chat":
                    if not isinstance(data, dict) or not isinstance(data.get("message"), str) or not data["message"].strip():
                        raise ValueError("消息不能为空")
                    try:
                        return self.reply(200, session_board_chat.chat(db_path, home, data["message"].strip()))
                    except (OSError, ValueError, KeyError) as exc:
                        return self.reply(502, {"error": f"助手调用失败：{exc}"})
                if path == "/api/settings":
                    days = data.get("recent_days") if isinstance(data, dict) else None
                    if days not in (1, 3, 7):
                        raise ValueError("时间范围无效")
                    db = open_db(db_path)
                    with db:
                        db.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('recent_days',?)", (str(days),))
                    db.close()
                    return self.reply(200, {"ok": True, "recent_days": days})
                if path.startswith("/api/items/"):
                    update_item(db_path, path.removeprefix("/api/items/"), data)
                    return self.reply(200, {"ok": True})
                return self.reply(404, {"error": "未找到"})
            except (ValueError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                return self.reply(400, {"error": str(exc)})
    return Handler


def main():
    parser = argparse.ArgumentParser(description="本地 Claude session 看板")
    parser.add_argument("--port", type=int, default=43188)
    parser.add_argument("--db", type=Path, required=True, help="看板数据库路径；包含会话文本，请选择私有位置")
    parser.add_argument("--claude-home", type=Path, default=Path.home() / ".claude")
    summaries = parser.add_mutually_exclusive_group()
    summaries.add_argument("--summary-command", help="JSON 字符串数组；配置后会将所选会话文本发送给此命令")
    summaries.add_argument("--ollama-model", help="启用本机 Ollama 摘要；会向本机服务发送所选会话文本")
    summaries.add_argument("--deepseek-model", nargs="?", const="deepseek-v4-flash",
                           help="启用 DeepSeek 摘要（默认 deepseek-v4-flash）；会把所选会话文本发送给 DeepSeek")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("端口必须在 1 到 65535 之间")
    try:
        adapters = [('session_board_ollama.py', args.ollama_model), ('session_board_deepseek.py', args.deepseek_model)]
        chosen = next(((n, m) for n, m in adapters if m), None)
        command = ([sys.executable, str(Path(__file__).with_name(chosen[0])), '--model', chosen[1]] if chosen
                   else json.loads(args.summary_command) if args.summary_command else None)
    except ValueError:
        parser.error("摘要命令必须是 JSON 字符串数组")
    if command is not None and (not isinstance(command, list) or not command or any(not isinstance(s, str) or not s for s in command)):
        parser.error("摘要命令必须是非空 JSON 字符串数组")
    token = secrets.token_urlsafe(32)
    server = ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(args.db, args.claude_home, token, args.port, command))
    server.daemon_threads = True
    stop = threading.Event()

    def watch():
        while not stop.is_set():
            try:
                result = sync(args.db, args.claude_home)
                if result.get('ok') and command:
                    session_board_summary.update_summaries(args.db, command, summary_ids(args.db, args.claude_home))
            except (OSError, sqlite3.Error):
                print('后台同步失败；请检查数据库和会话目录权限', flush=True)
            stop.wait(30)

    threading.Thread(target=watch, daemon=True).start()
    print(f"Session 看板：http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    finally:
        stop.set()
        server.server_close()


if __name__ == "__main__":
    main()
