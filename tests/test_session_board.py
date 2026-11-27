import io
import json
import os
import sqlite3
import sys
import tempfile
import time
import threading
import http.client
from pathlib import Path

from scripts import session_board as board
from scripts import session_board_hosts
from scripts import session_board_summary
from scripts import session_board_ollama


def titled(name='T'):
    return (json.dumps({'type': 'custom-title', 'customTitle': name}, ensure_ascii=False) + '\n').encode()


def record(kind, text, **extra):
    return (json.dumps({'type': kind, 'message': {'role': kind, 'content': text}, **extra}, ensure_ascii=False) + '\n').encode()


def setup_source(tmp_path):
    home = tmp_path / 'claude'
    source = home / 'projects' / 'project' / '11111111-1111-4111-8111-111111111111.jsonl'
    source.parent.mkdir(parents=True)
    return home, source, tmp_path / 'board.db'


def test_incremental_incomplete_and_user_state(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'start') + b'{"type":')
    assert board.sync(dbpath, home)['ok']
    item = board.list_items(dbpath, home)[0]
    assert [e['text'] for e in item['events']] == ['start']
    tag = board.create_tag(dbpath, 'alpha', board.TAG_COLORS[0])
    board.update_item(dbpath, item['id'], {'state': '已完成', 'tags': [tag['id']], 'note': 'keep'})
    with source.open('ab') as f:
        f.write(b'"assistant","message":{"role":"assistant","content":"done"}}\n')
    assert board.sync(dbpath, home)['ok']
    item = board.list_items(dbpath, home)[0]
    assert {e['text'] for e in item['events']} == {'start', 'done'}
    assert (item['state'], item['note']) == ('已完成', 'keep')
    assert [t['name'] for t in item['tags']] == ['alpha']
    assert board.sync(dbpath, home)['ok']
    assert len(board.list_items(dbpath, home)[0]['events']) == 2


def test_large_unfinished_first_record_is_not_skipped(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    full = record('assistant', 'x' * (board.INITIAL_BYTES + 1024))
    source.write_bytes(full[:-20])
    board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['cursor'] == 0
    with source.open('ab') as stream:
        stream.write(full[-20:])
    board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['events'][0]['text'].startswith('xxx')


def test_first_import_of_huge_unfinished_line_stays_bounded(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'MAX_LINE', 200)
    monkeypatch.setattr(board, 'INITIAL_BYTES', 50)
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(b'x' * 1000)
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['cursor'] == 1000 and item['aligning'] == 1
    with source.open('ab') as stream:
        stream.write(b'end\n' + record('assistant', 'later'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['events'][0]['text'] == 'later'
    assert item['aligning'] == 0


def test_oversized_complete_line_does_not_block_following_events(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'MAX_LINE', 150)
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'x' * 300) + record('assistant', 'later'))
    for _ in range(4):
        board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['events'][0]['text'] == 'later'
    assert item['limited'] and '跳过' in item['error']


def test_existing_oversized_unfinished_line_advances_bounded_cursor(tmp_path, monkeypatch):
    monkeypatch.setattr(board, 'MAX_LINE', 150)
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'first'))
    board.sync(dbpath, home)
    with source.open('ab') as stream:
        stream.write(b'x' * 500)
    board.sync(dbpath, home)
    first = board.list_items(dbpath, home)[0]
    assert first['aligning'] and first['cursor'] < source.stat().st_size
    board.sync(dbpath, home)
    second = board.list_items(dbpath, home)[0]
    assert second['cursor'] > first['cursor']
    with source.open('ab') as stream:
        stream.write(b'\n' + record('assistant', 'later'))
    for _ in range(8):
        board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['events'][0]['text'] == 'later'


def test_corrupt_complete_line_does_not_block_later_events(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(b'{bad json}\n' + record('assistant', 'later'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['events'][0]['text'] == 'later'
    assert item['limited'] and '格式无效' in item['error']
    board.sync(dbpath, home)
    assert '格式无效' in board.list_items(dbpath, home)[0]['error']


def agent_flag(tmp_path, *records):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(b''.join(records))
    board.sync(dbpath, home)
    return board.list_items(dbpath, home)[0]['agent']


def test_untitled_session_gets_derived_label(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', '帮我把发票号补全'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['title'] == '帮我把发票号补全' and item['title_derived']


def test_subagent_sessions_are_flagged(tmp_path):
    titled = (json.dumps({'type': 'custom-title', 'customTitle': 'mine'}) + '\n').encode()
    assert agent_flag(tmp_path / 'a', record('user', 'go', entrypoint='sdk-cli'), titled)        # programmatic launch
    assert agent_flag(tmp_path / 'b', record('user', 'go', entrypoint='claude-desktop'))          # untitled, not human-typed
    assert not agent_flag(tmp_path / 'c', record('user', 'go', entrypoint='claude-desktop'), titled)
    assert not agent_flag(tmp_path / 'd', record('user', 'go', entrypoint='cli', origin={'kind': 'human'}))


def test_new_item_is_untriaged(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'x'))
    board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['state'] == '自动'


def test_new_session_starts_read_and_later_events_are_unread(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'old'))
    board.sync(dbpath, home)
    assert not board.list_items(dbpath, home)[0]['unread']
    with source.open('ab') as stream:
        stream.write(record('assistant', 'new'))
    board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['unread']


def test_read_marker_uses_rendered_cursor(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'old'))
    board.sync(dbpath, home)
    stale = board.list_items(dbpath, home)[0]
    with source.open('ab') as stream:
        stream.write(record('assistant', 'new'))
    board.sync(dbpath, home)
    board.update_item(dbpath, stale['id'], {'mark_read': True, 'read_generation': stale['generation'], 'read_cursor': stale['cursor']})
    assert board.list_items(dbpath, home)[0]['unread']


def test_recent_discovery_and_hidden_retained(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'result'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    board.update_item(dbpath, item['id'], {'hidden': True, 'note': 'retained'})
    old = time.time() - 8 * 86400
    os.utime(source, (old, old))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['hidden'] and item['note'] == 'retained'
    assert item['events'] == []
    with source.open('ab') as stream:
        stream.write(record('assistant', 'new event'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['hidden'] and item['note'] == 'retained'
    assert item['events'][0]['text'] == 'new event'


def test_truncated_transcript_has_new_generation(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'long ' * 100))
    board.sync(dbpath, home)
    source.write_bytes(record('assistant', 'new'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['generation'] == 1
    assert item['events'][0]['text'] == 'new'


def test_replaced_file_is_not_silently_skipped(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'original'))
    board.sync(dbpath, home)
    replacement = source.with_suffix('.replacement')
    replacement.write_bytes(record('assistant', 'replacement ' * 10))
    os.replace(replacement, source)
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['generation'] == 1
    assert item['events'][0]['text'].startswith('replacement')


def test_rewrite_with_same_inode_and_larger_size_is_detected(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'original'))
    board.sync(dbpath, home)
    source.write_bytes(record('assistant', 'replacement ' * 20))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['generation'] == 1
    assert item['events'][0]['text'].startswith('replacement')


def test_event_cache_is_bounded(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(b''.join(record('assistant', f'event {n}') for n in range(60)))
    board.sync(dbpath, home)
    with sqlite3.connect(dbpath) as db:
        assert db.execute('SELECT COUNT(*) FROM events').fetchone()[0] == 40
    assert board.list_items(dbpath, home)[0]['limited']


def test_legacy_schema_columns_are_added(tmp_path):
    dbpath = tmp_path / 'legacy.sqlite3'
    with sqlite3.connect(dbpath) as db:
        db.execute("CREATE TABLE items (id TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE summaries (item_id TEXT PRIMARY KEY)")
    db = board.open_db(dbpath)
    try:
        items = {row['name'] for row in db.execute('PRAGMA table_info(items)')}
        summaries = {row['name'] for row in db.execute('PRAGMA table_info(summaries)')}
        assert {'prefix_len', 'prefix_hash', 'aligning'} <= items
        assert 'attempted_at' in summaries
    finally:
        db.close()


def test_injected_wrappers_are_not_conversation():
    host = session_board_hosts.ClaudeDesktopHost()
    for text in ('<task-notification>x</task-notification>', '<system-reminder>x</system-reminder>', '<command-name>/model</command-name>'):
        assert host.message({'type': 'user', 'message': {'role': 'user', 'content': text}}) is None
    assert host.message({'type': 'user', 'message': {'role': 'user', 'content': '<pasted_content id="1">hi</pasted_content>'}})[:2] == ('user', 'hi')
    relayed = '<pasted_content id="2"> Another Claude session sent a message: <agent-message>x</agent-message>'
    assert host.message({'type': 'user', 'message': {'role': 'user', 'content': relayed}}) is None


def test_boilerplate_reply_is_not_an_event():
    assert session_board_hosts.ClaudeDesktopHost().message(
        {'type': 'assistant', 'message': {'role': 'assistant', 'content': 'No response requested.'}}) is None


def test_untrusted_tool_content_filtered():
    host = session_board_hosts.ClaudeDesktopHost()
    assert host.message({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'secret'}]}}) is None
    assert host.message({'type': 'assistant', 'message': {'role': 'assistant', 'content': [
        {'type': 'thinking', 'thinking': 'hidden'}, {'type': 'text', 'text': '<b>plain</b>'}]}})[:2] == ('assistant', '<b>plain</b>')


def test_reject_invalid_mutation(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'hi'))
    board.sync(dbpath, home)
    ident = board.list_items(dbpath, home)[0]['id']
    try:
        board.update_item(dbpath, ident, {'cursor': 999})
        assert False
    except ValueError:
        pass


def test_summary_command_accepts_only_synthetic_payload():
    command = [sys.executable, '-c', 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"summary":d["events"][0]["text"],"attention":""}))']
    result = session_board_summary.summarize(command, {'events': [{'text': 'synthetic'}]})
    assert (result['summary'], result['attention']) == ('synthetic', '')


def test_ollama_adapter_sends_only_to_local_endpoint(monkeypatch, capsys):
    class Response:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def read(self, limit): return json.dumps({'response': '{"summary":"done","attention":""}'}).encode()
    def fake_urlopen(request, timeout):
        assert request.full_url == 'http://127.0.0.1:11434/api/generate'
        assert json.loads(request.data)['model'] == 'test-model'
        return Response()
    class Opener:
        open = staticmethod(fake_urlopen)
    def fake_build_opener(handler):
        assert handler.proxies == {}
        return Opener()
    monkeypatch.setattr(session_board_ollama.urllib.request, 'build_opener', fake_build_opener)
    monkeypatch.setattr(sys, 'stdin', io.StringIO('{"events":[]}'))
    monkeypatch.setattr(sys, 'argv', ['adapter', '--model', 'test-model'])
    session_board_ollama.main()
    assert json.loads(capsys.readouterr().out)['summary'] == 'done'


def test_summary_updates_only_for_new_events(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled() + record('assistant', 'synthetic'))
    board.sync(dbpath, home)
    command = [sys.executable, '-c', 'import json,sys; d=json.load(sys.stdin); print(json.dumps({"summary":d["events"][0]["text"]}))']
    session_board_summary.update_summaries(dbpath, command)
    with sqlite3.connect(dbpath) as db:
        first = db.execute('SELECT summary,created_at FROM summaries').fetchone()
    session_board_summary.update_summaries(dbpath, command)
    with sqlite3.connect(dbpath) as db:
        second = db.execute('SELECT summary,created_at FROM summaries').fetchone()
    assert first == second
    assert first[0] == 'synthetic'


def test_summary_round_is_finished_only_when_its_queue_drains(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled() + record('assistant', 'synthetic'))
    board.sync(dbpath, home)
    # 0.4s inside the command, so the round is observably active while it runs.
    command = [sys.executable, '-c',
               'import json,time; time.sleep(0.4); print(json.dumps({"summary": "s", "attention": ""}))']
    worker = threading.Thread(target=session_board_summary.update_summaries, args=(dbpath, command))
    worker.start()
    deadline = time.time() + 5
    seen = {}
    while time.time() < deadline:
        seen = session_board_summary.progress()
        if seen['active'] and seen['total']:
            break
        time.sleep(0.02)
    assert seen['active'] is True and seen['total'] == 1
    worker.join(10)
    done = session_board_summary.progress()
    assert (done['active'], done['done'], done['total']) == (False, 1, 1)
    assert done['finished_at'] > 0


def test_summary_round_skips_when_nothing_moved(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled() + record('assistant', 'synthetic'))
    board.sync(dbpath, home)
    command = [sys.executable, '-c', 'import json; print(json.dumps({"summary": "s", "attention": ""}))']
    session_board_summary.update_summaries(dbpath, command, min_gap=0)
    session_board_summary.update_summaries(dbpath, command, min_gap=0)
    assert session_board_summary.progress()['total'] == 0   # nothing new: the round owes no calls


def test_repeated_rewinds_collapse_into_the_newest_card(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    parent = source.stem
    source.write_bytes(titled('同一个会话') + record('user', 'first'))
    board.sync(dbpath, home)
    first = source.with_name('44444444-4444-4444-8444-444444444444.jsonl')
    first.write_bytes(titled('同一个会话') + record('assistant', 'branch one', requestSessionId=parent))
    second = source.with_name('55555555-5555-4555-8555-555555555555.jsonl')
    second.write_bytes(titled('同一个会话') + record('assistant', 'branch two', requestSessionId=parent))
    os.utime(first, (time.time() - 600, time.time() - 600))
    board.sync(dbpath, home)
    items = board.list_items(dbpath, home)
    assert [item['id'] for item in items] == [second.stem]
    assert board.superseded_ids(dbpath) == {parent, first.stem}


def test_conversation_in_the_head_is_found_when_the_tail_is_attachments(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    filler = b''.join(record('attachment', 'x' * 900) for _ in range(200))   # pushes the message out of the tail window
    source.write_bytes(record('user', 'the only message') + filler)
    assert source.stat().st_size > 128 * 1024
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert [event['text'] for event in item['events']] == ['the only message']


def test_continuation_stays_visible_without_its_own_origin(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    parent = source.stem
    source.write_bytes(record('user', 'first question', entrypoint='claude-desktop-3p', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    # A rewound/compacted segment starts by replaying the old conversation, so its own first user
    # record carries no origin — it must still count as part of the same session.
    child = source.with_name('33333333-3333-4333-8333-333333333333.jsonl')
    child.write_bytes(record('user', 'This session is being continued from a previous conversation that ran out of context.',
                             entrypoint='claude-desktop-3p', requestSessionId=parent))
    board.sync(dbpath, home)
    item = next(i for i in board.list_items(dbpath, home) if i['id'] == child.stem)
    assert item['agent'] is False


def test_entrypoint_is_relearned_when_written_late(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'hello'))
    board.sync(dbpath, home)
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT ifnull(entrypoint,'') FROM items").fetchone()[0] == ''
    with source.open('ab') as stream:
        stream.write(record('assistant', 'hi', entrypoint='claude-desktop-3p'))
    with sqlite3.connect(dbpath) as db:   # let the slow retry run on the next sync
        db.execute("UPDATE meta SET value='0' WHERE key='reclassify_at'")
    board.sync(dbpath, home)
    with sqlite3.connect(dbpath) as db:
        assert db.execute("SELECT entrypoint FROM items").fetchone()[0] == 'claude-desktop-3p'


def test_agent_launched_briefs_are_workers_not_sessions(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    brief = ('<pasted_content id="1">' + chr(10) +
             'Human: <system-reminder>Codebase and user instructions are shown below' + chr(10) +
             '</pasted_content>')
    source.write_bytes(record('user', brief, entrypoint='cli', origin={'kind': 'human'}))
    other = source.with_name('22222222-2222-4222-8222-222222222222.jsonl')
    other.write_bytes(record('user', 'please fix the build', entrypoint='cli', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    items = {item['id']: item for item in board.list_items(dbpath, home)}
    assert items[source.stem]['agent'] is True    # another agent's brief, not the human opening a session
    assert items[other.stem]['agent'] is False


def test_tags_are_global_and_capped_per_session(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'go'))
    board.sync(dbpath, home)
    ident = board.list_items(dbpath, home)[0]['id']
    with sqlite3.connect(dbpath) as db:
        db.execute("DELETE FROM meta WHERE key='tags'")
        db.execute("UPDATE items SET group_name='旧分组' WHERE id=?", (ident,))
    board.open_db(dbpath).close()   # reopening migrates the old free-text group into a tag
    db = board.open_db(dbpath)
    migrated = board.tags_index(db)
    db.close()
    assert [(t['name'], t['count']) for t in migrated] == [('旧分组', 1)]
    tag = board.create_tag(dbpath, '测试', board.TAG_COLORS[3])
    for args in (('测试', board.TAG_COLORS[4]), ('颜色不对', '#123456')):
        try:
            board.create_tag(dbpath, *args)
            assert False, 'duplicate name or non-preset color'
        except ValueError:
            pass
    with sqlite3.connect(dbpath) as db:
        extra = [db.execute("INSERT INTO tags(name,color) VALUES(?,?)", (f't{i}', board.TAG_COLORS[i])).lastrowid
                 for i in range(4, 8)]
    try:
        board.update_item(dbpath, ident, {'tags': extra})
        assert False, 'per-session cap'
    except ValueError:
        pass
    board.update_item(dbpath, ident, {'tags': [tag['id'], migrated[0]['id']]})
    assert sorted(t['name'] for t in board.list_items(dbpath, home)[0]['tags']) == sorted(['测试', '旧分组'])
    board.delete_tag(dbpath, tag['id'])
    assert [t['name'] for t in board.list_items(dbpath, home)[0]['tags']] == ['旧分组']
    db = board.open_db(dbpath)
    assert '测试' not in {t['name'] for t in board.tags_index(db)}
    db.close()


def test_summary_ids_limited_to_running_lane(tmp_path, monkeypatch):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'go', entrypoint='claude-desktop', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    ident = board.list_items(dbpath, home)[0]['id']
    live = lambda status: (lambda _home, fresh=False: {ident: {'status': status, 'link': '', 'name': ''}})

    monkeypatch.setattr(board, 'live_sessions', live('运行中'))
    assert board.summary_ids(dbpath, home) == {ident}
    monkeypatch.setattr(board, 'live_sessions', live('空闲'))
    assert board.summary_ids(dbpath, home) == {ident}        # idle but active within 30 min
    with sqlite3.connect(dbpath) as db:
        db.execute("UPDATE items SET source_time=source_time-7200")   # quiet for two hours
    assert board.summary_ids(dbpath, home) == set()
    board.update_item(dbpath, ident, {'state': '进行中'})
    assert board.summary_ids(dbpath, home) == {ident}        # the user put it in progress

    source.write_bytes(titled('btw: 顺手看一眼') + record('user', 'go', entrypoint='claude-desktop', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    assert board.summary_ids(dbpath, home) == set()          # "btw" side questions are skipped


def test_background_sessions_are_not_summarised(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('assistant', 'worker chatter', entrypoint='sdk-cli'))
    board.sync(dbpath, home)
    session_board_summary.update_summaries(dbpath, [sys.executable, '-c', 'raise SystemExit("should not run")'])
    with sqlite3.connect(dbpath) as db:
        assert db.execute('SELECT COUNT(*) FROM summaries').fetchone()[0] == 0


def test_summary_failure_preserves_previous_text(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled() + record('assistant', 'first'))
    board.sync(dbpath, home)
    command = [sys.executable, '-c', 'print("{\\\"summary\\\":\\\"ok\\\"}")']
    session_board_summary.update_summaries(dbpath, command)
    with source.open('ab') as stream:
        stream.write(record('assistant', 'second'))
    board.sync(dbpath, home)
    session_board_summary.update_summaries(dbpath, [sys.executable, '-c', 'raise SystemExit(1)'], min_gap=0)
    summary = board.list_items(dbpath, home)[0]['summary']
    assert summary['summary'] == 'ok'
    assert summary['error'].startswith('摘要生成失败')
    assert summary['stale']


def test_live_status_uses_cli_even_if_metadata_is_stale(tmp_path, monkeypatch):
    home = tmp_path / '.claude'
    folder = home / 'sessions'
    folder.mkdir(parents=True)
    ident = '11111111-1111-4111-8111-111111111111'
    meta = folder / '1.json'
    meta.write_text(json.dumps({'sessionId': ident, 'hostSessionId': 'local_' + ident, 'status': 'idle'}), encoding='utf-8')
    old = time.time() - 3600
    os.utime(meta, (old, old))
    monkeypatch.setattr(board.Path, 'home', classmethod(lambda cls: tmp_path))
    monkeypatch.setattr(board.shutil, 'which', lambda _: 'fake-claude')
    class Result:
        stdout = json.dumps([{'sessionId': ident, 'status': 'busy'}])
    calls = []
    def fake_run(*args, **kwargs):
        calls.append(1)
        return Result()
    monkeypatch.setattr(board.subprocess, 'run', fake_run)
    live = board.live_sessions(home)[ident]
    board.live_sessions(home)
    assert len(calls) == 1
    assert live['status'] == '运行中'
    assert live['link'].endswith('local_' + ident)
    monkeypatch.setattr(board.shutil, 'which', lambda _: None)
    board.LIVE_CACHE.clear()
    assert ident not in board.live_sessions(home)


def test_server_allows_configured_origin(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'synthetic'))
    origin = 'https://board.example.ts.net'
    server = board.ThreadingHTTPServer(('127.0.0.1', 0), board.BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.RequestHandlerClass = board.make_handler(dbpath, home, 'known-test-token', port, None, origin)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = http.client.HTTPConnection('127.0.0.1', port)
        host = {'Host': 'board.example.ts.net'}
        client.request('GET', '/', headers=host)
        assert client.getresponse().status == 200
        client.request('GET', '/api/items', headers={**host, 'X-Board-Token': 'known-test-token'})
        assert client.getresponse().status == 200
        client.request('POST', '/api/sync', body='{}', headers={**host, 'Origin': origin, 'X-Board-Token': 'known-test-token'})
        assert client.getresponse().status == 200
        # a page on another origin still cannot write, and an unknown host stays blocked
        client.request('POST', '/api/sync', body='{}',
                       headers={**host, 'Origin': 'http://attacker.test', 'X-Board-Token': 'known-test-token'})
        assert client.getresponse().status == 403
        client.request('GET', '/api/items', headers={'Host': 'attacker.test', 'X-Board-Token': 'known-test-token'})
        assert client.getresponse().status == 403
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_tailscale_origin_reads_self_dnsname(monkeypatch):
    monkeypatch.setattr(board.shutil, 'which', lambda _: 'tailscale')

    class Result:
        stdout = '{"Self": {"DNSName": "xiao.tail1b6e93.ts.net."}}'

    monkeypatch.setattr(board.subprocess, 'run', lambda *a, **k: Result())
    assert board.tailscale_origin() == 'https://xiao.tail1b6e93.ts.net'
    Result.stdout = 'not json'
    assert board.tailscale_origin() is None


def test_server_rejects_foreign_origin_and_host(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'synthetic'))
    server = board.ThreadingHTTPServer(('127.0.0.1', 0), board.BaseHTTPRequestHandler)
    port = server.server_address[1]
    server.RequestHandlerClass = board.make_handler(dbpath, home, 'known-test-token', port)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        client = http.client.HTTPConnection('127.0.0.1', port)
        client.request('GET', '/api/items', headers={'Host': 'attacker.test'})
        assert client.getresponse().status == 403
        client.request('GET', '/api/items')
        assert client.getresponse().status == 403
        client.request('POST', '/api/sync', body='{}', headers={'Origin': 'http://attacker.test', 'X-Board-Token': 'known-test-token'})
        assert client.getresponse().status == 403
        headers = {'Origin': f'http://127.0.0.1:{port}', 'X-Board-Token': 'known-test-token'}
        client.request('POST', '/api/sync', body='{}', headers=headers)
        assert client.getresponse().status == 200
        client.request('GET', '/api/items', headers={'X-Board-Token': 'known-test-token'})
        payload = json.loads(client.getresponse().read())
        assert isinstance(payload['summary'], dict)   # the page needs the round state to know when a refresh ends
        item = payload['items'][0]
        client.request('POST', '/api/tags', body=json.dumps({'name': 'test', 'color': board.TAG_COLORS[1]}), headers=headers)
        tag = json.loads(client.getresponse().read())['tag']
        client.request('POST', '/api/items/' + item['id'], body=json.dumps({'state': '进行中', 'tags': [tag['id']]}), headers=headers)
        assert client.getresponse().status == 200
        client.request('GET', '/api/items', headers={'X-Board-Token': 'known-test-token'})
        payload = json.loads(client.getresponse().read())
        updated = payload['items'][0]
        assert (updated['state'], [t['name'] for t in updated['tags']]) == ('进行中', ['test'])
        assert [(t['name'], t['count']) for t in payload['tags']] == [('test', 1)]
        client.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

def test_rewound_session_merges_into_one_card(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    parent = source.stem
    source.write_bytes(titled('同一个会话') + record('user', 'first'))
    board.sync(dbpath, home)
    # a rewind writes a new file that points back at the original session
    child = source.with_name('22222222-2222-4222-8222-222222222222.jsonl')
    child.write_bytes(titled('同一个会话') + record('assistant', 'continued', requestSessionId=parent))
    board.sync(dbpath, home)
    items = board.list_items(dbpath, home)
    assert len(items) == 1
    assert items[0]['id'] == child.stem and items[0]['forks'] == 1
    assert board.superseded_ids(dbpath) == {parent}

def test_compacted_session_merges_into_one_card(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    parent = source.stem
    source.write_bytes(titled('同一个会话') + record('user', 'first'))
    board.sync(dbpath, home)
    # compaction replays the whole history into a new file and only then points back at the old one
    child = source.with_name('33333333-3333-4333-8333-333333333333.jsonl')
    filler = record('user', 'x' * 4000) * 80  # taller than the head window classify reads
    child.write_bytes(titled('同一个会话') + filler + record('assistant', 'continued', requestSessionId=parent))
    board.sync(dbpath, home)
    items = board.list_items(dbpath, home)
    assert len(items) == 1
    assert items[0]['id'] == child.stem
    assert board.superseded_ids(dbpath) == {parent}


def test_compacted_session_links_through_host_conversation(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    parent = source.stem
    source.write_bytes(record('user', 'first'))
    board.sync(dbpath, home)
    # compaction keeps the Desktop conversation id and starts a new transcript id
    child = source.with_name('44444444-4444-4444-8444-444444444444.jsonl')
    child.write_bytes(record('user', 'first') + record('assistant', 'continued'))
    (home / 'sessions').mkdir()
    (home / 'sessions' / '1.json').write_text(json.dumps(
        {'sessionId': child.stem, 'hostSessionId': 'local_' + parent, 'status': 'busy'}))
    tag = board.create_tag(dbpath, '工作台', board.TAG_COLORS[2])
    board.update_item(dbpath, parent, {'state': '进行中', 'tags': [tag['id']], 'note': 'keep me'})
    board.sync(dbpath, home)
    items = board.list_items(dbpath, home)
    assert [item['id'] for item in items] == [child.stem]
    assert board.superseded_ids(dbpath) == {parent}
    # the continuation inherits the triage the user did on the earlier card
    assert (items[0]['state'], items[0]['note']) == ('进行中', 'keep me')
    assert [t['name'] for t in items[0]['tags']] == ['工作台']


def test_temp_dir_workers_stay_off_the_board(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    temp = Path(tempfile.gettempdir()) / 'worker-run'
    source.write_bytes(record('user', 'hi', cwd=str(temp), entrypoint='cli', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert item['agent'] is True


def test_attention_flag_clears_once_acknowledged(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled('待办') + record('user', 'go'))
    board.sync(dbpath, home)
    ident = board.list_items(dbpath, home)[0]['id']
    db = board.open_db(dbpath)
    with db:
        db.execute("INSERT INTO summaries VALUES(?,?,0,'做到一半','需要拍板',?, '', 0)",
                   (ident, 2, time.time()))
    db.close()
    item = board.list_items(dbpath, home)[0]
    assert item['pending'] is True
    board.update_item(dbpath, ident, {'attention_generation': item['summary']['generation'],
                                      'attention_position': item['summary']['position']})
    assert board.list_items(dbpath, home)[0]['pending'] is False
    db = board.open_db(dbpath)
    with db:
        db.execute("UPDATE summaries SET generation=3 WHERE item_id=?", (ident,))
    db.close()
    assert board.list_items(dbpath, home)[0]['pending'] is True   # a newer summary raises it again


def test_summary_waits_for_the_refresh_gap(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(titled() + record('assistant', 'first'))
    board.sync(dbpath, home)
    first = [sys.executable, '-c', 'import json; print(json.dumps({"summary": "one", "attention": ""}))']
    second = [sys.executable, '-c', 'import json; print(json.dumps({"summary": "two", "attention": ""}))']
    session_board_summary.update_summaries(dbpath, first, min_gap=0)
    assert board.list_items(dbpath, home)[0]['summary']['summary'] == 'one'
    with source.open('ab') as stream:
        stream.write(record('assistant', 'second'))
    board.sync(dbpath, home)
    # a new message arrived, but the last call is inside the gap: keep the old text
    session_board_summary.update_summaries(dbpath, second, min_gap=300)
    assert board.list_items(dbpath, home)[0]['summary']['summary'] == 'one'
    # past the gap it refreshes
    session_board_summary.update_summaries(dbpath, second, min_gap=0)
    assert board.list_items(dbpath, home)[0]['summary']['summary'] == 'two'


def test_background_notifications_are_not_messages(tmp_path):
    home, source, dbpath = setup_source(tmp_path)
    note = '<pasted_content id="e1">' + chr(10) + '<system-reminder>' + chr(10) + '[SYSTEM NOTIFICATION - NOT USER INPUT]' + chr(10) + '<task-notification>job done</task-notification>'
    source.write_bytes(titled() + record('user', note))
    board.sync(dbpath, home)
    assert board.list_items(dbpath, home)[0]['events'] == []
    # a real paste keeps its text and loses the wrapper tag
    with source.open('ab') as stream:
        stream.write(record('user', '<pasted_content id="e2">' + chr(10) + '重做这一版'))
    board.sync(dbpath, home)
    item = board.list_items(dbpath, home)[0]
    assert [e['text'] for e in item['events']] == ['重做这一版']


def test_board_runs_on_any_host_adapter(tmp_path, monkeypatch):
    """The core must not care which host produced the transcripts."""
    from scripts import session_board_hosts as hosts
    home = tmp_path / 'host'
    source = home / 'sessions' / '11111111-1111-4111-8111-111111111111.jsonl'
    source.parent.mkdir(parents=True)
    source.write_bytes(record('assistant', 'hello from another host'))

    class FakeHost(hosts.HostAdapter):
        name = 'fake'
        def transcripts(self, _home): return [source]
        def classify(self, _path): return ('fake-entry', 1, '')
        def message(self, record): return (record['type'], record['message']['content'], '')
        def live(self, _home): return {source.stem: {'status': '运行中', 'link': '', 'name': 'fake session'}}

    monkeypatch.setattr(board, 'HOST', FakeHost())
    dbpath = tmp_path / 'board.db'
    assert board.sync(dbpath, home)['ok']
    item = board.list_items(dbpath, home)[0]
    assert item['entrypoint'] == 'fake-entry'
    assert item['runtime'] == '运行中' and item['events'][0]['text'] == 'hello from another host'
