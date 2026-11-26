import sqlite3
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from scripts import session_board as board
from scripts import session_board_chat as chat


def test_column_rule_uses_a_30_minute_window():
    now = time.time()
    assert chat.column_of('自动', '运行中', now - 600, now) == '进行中'
    assert chat.column_of('自动', '运行中', now - 45 * 60, now) == '进行中'   # busy, just quiet
    assert chat.column_of('自动', '空闲', now - 20 * 60, now) == '进行中'       # recently active
    assert chat.column_of('自动', '空闲', now - 60, now) == '进行中'        # idle but active just now
    assert chat.column_of('自动', '空闲', now - 2 * 3600, now) == '待查看'
    assert chat.column_of('自动', '空闲', now - 3 * 86400, now) == '暂不关注'
    assert chat.column_of('自动', '空闲', now - 3 * 86400, now, 7) == '待查看'   # a wider 最近 window reaches back
    assert chat.column_of('自动', '空闲', now - 9 * 86400, now, 7) == '暂不关注'
    assert chat.column_of('已完成', '运行中', now, now) == '已完成'


def make_db(tmp_path, rows):
    dbpath = tmp_path / 'board.sqlite3'
    db = board.open_db(dbpath)
    now = time.time()
    with db:
        for ident, title, state, age_days in rows:
            db.execute("""INSERT INTO items(id,path,title,cwd,source_time,cursor,identity,generation,limited,
                          prefix_len,prefix_hash,aligning,entrypoint,human,state,synced_at)
                          VALUES(?,?,?,?,?,0,'i',0,0,0,'',0,'claude-desktop',1,?,?)""",
                       (ident, 'x.jsonl', title, 'D:/w', now - age_days * 86400, state, now))
    db.close()
    return dbpath


def test_tools_require_a_selector_and_can_bulk_archive(tmp_path, monkeypatch):
    dbpath = make_db(tmp_path, [('a', 'old one', '自动', 9), ('b', 'fresh one', '自动', 1)])
    monkeypatch.setattr(chat, '_rows', lambda _db, _home: [
        {'id': 'a', 'title': 'old one', 'lane': '暂不关注', 'runtime': '空闲', 'days_since_activity': 9.0, 'group_name': '', 'note': '', 'background': False},
        {'id': 'b', 'title': 'fresh one', 'lane': '待查看', 'runtime': '空闲', 'days_since_activity': 1.0, 'group_name': '', 'note': '', 'background': False}])
    try:
        chat.update_items(dbpath, tmp_path, {'state': '已完成'})
        assert False, 'selector required'
    except ValueError:
        pass
    out = chat.update_items(dbpath, tmp_path, {'no_activity_days': 7, 'state': '暂不关注'})
    assert out['changed'] == 1
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT state FROM items WHERE id='a'").fetchone()[0] == '暂不关注'
        assert db.execute("SELECT state FROM items WHERE id='b'").fetchone()[0] == '自动'


def test_cli_exposes_the_same_capability(tmp_path, capsys, monkeypatch):
    dbpath = make_db(tmp_path, [('a', 'old one', '自动', 9)])
    monkeypatch.setattr(chat, '_rows', lambda _db, _home: [
        {'id': 'a', 'title': 'old one', 'lane': '暂不关注', 'runtime': '空闲', 'days_since_activity': 9.0, 'group_name': '', 'note': '', 'background': False}])
    from scripts import session_board_cli as cli
    assert cli.main(['--db', str(dbpath), 'set', '--no-activity-days', '7', '--state', '暂不关注']) == 0
    assert 'changed' in capsys.readouterr().out
