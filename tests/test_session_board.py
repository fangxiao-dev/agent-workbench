import io
import json
import os
import sqlite3
import sys
import time
import threading
import http.client
from pathlib import Path

from scripts import session_board as board
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
    board.update_item(dbpath, item['id'], {'state': '已完成', 'group_name': 'alpha', 'note': 'keep'})
    with source.open('ab') as f:
        f.write(b'"assistant","message":{"role":"assistant","content":"done"}}\n')
    assert board.sync(dbpath, home)['ok']
    item = board.list_items(dbpath, home)[0]
    assert {e['text'] for e in item['events']} == {'start', 'done'}
    assert (item['state'], item['group_name'], item['note']) == ('已完成', 'alpha', 'keep')
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
    for text in ('<task-notification>x</task-notification>', '<system-reminder>x</system-reminder>', '<command-name>/model</command-name>'):
        assert board.visible_text({'type': 'user', 'message': {'role': 'user', 'content': text}}) is None
    assert board.visible_text({'type': 'user', 'message': {'role': 'user', 'content': '<pasted_content id="1">hi</pasted_content>'}})


def test_boilerplate_reply_is_not_an_event():
    assert board.visible_text({'type': 'assistant', 'message': {'role': 'assistant', 'content': 'No response requested.'}}) is None


def test_untrusted_tool_content_filtered():
    assert board.visible_text({'type': 'user', 'message': {'role': 'user', 'content': [{'type': 'tool_result', 'content': 'secret'}]}}) is None
    assert board.visible_text({'type': 'assistant', 'message': {'role': 'assistant', 'content': [{'type': 'thinking', 'thinking': 'hidden'}, {'type': 'text', 'text': '<b>plain</b>'}]}}) == ('assistant', '<b>plain</b>')


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
    assert result == {'summary': 'synthetic', 'attention': ''}


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


def test_summary_ids_limited_to_running_lane(tmp_path, monkeypatch):
    home, source, dbpath = setup_source(tmp_path)
    source.write_bytes(record('user', 'go', entrypoint='claude-desktop', origin={'kind': 'human'}))
    board.sync(dbpath, home)
    ident = board.list_items(dbpath, home)[0]['id']
    live = lambda status: (lambda _home: {ident: {'status': status, 'link': '', 'name': ''}})

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
    session_board_summary.update_summaries(dbpath, [sys.executable, '-c', 'raise SystemExit(1)'])
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
        item = payload['items'][0]
        client.request('POST', '/api/items/' + item['id'], body=json.dumps({'state': '进行中', 'group_name': 'test'}), headers=headers)
        assert client.getresponse().status == 200
        client.request('GET', '/api/items', headers={'X-Board-Token': 'known-test-token'})
        updated = json.loads(client.getresponse().read())['items'][0]
        assert (updated['state'], updated['group_name']) == ('进行中', 'test')
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
        def live(self, _home): return {source.stem: {'status': '运行中', 'link': '', 'name': 'fake session'}}

    monkeypatch.setattr(board, 'HOST', FakeHost())
    dbpath = tmp_path / 'board.db'
    assert board.sync(dbpath, home)['ok']
    item = board.list_items(dbpath, home)[0]
    assert item['entrypoint'] == 'fake-entry'
    assert item['runtime'] == '运行中' and item['events'][0]['text'] == 'hello from another host'
