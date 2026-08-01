"""独立核验 ledger.py：不看 codex 的自述，自己造 fixture 跑。

fixture 严格照真实 rollout 形态构造（取自 019fb7ad 主控的实际事件结构）。
"""
import json, os, subprocess, sys, shutil, tempfile
from pathlib import Path

LEDGER = r"D:\CodeSpace\agent-workbench\skills\thread-harness\scripts\ledger.py"
CID = "harness-selftest"
TMP = Path(os.environ["TEMP"])
BROKER = TMP / "thread-harness-selftest" / "codex-thread-broker"  # 隔离，绝不碰生产运行时
FAKE_SESSIONS = TMP / "thread-harness-selftest" / "sessions"
SESSIONS = FAKE_SESSIONS / "2026" / "08" / "01"
CTRL = "019fbccc-1111-7000-8000-000000000001"
NODES = {
    "controller": CTRL,
    "alpha": "019fbccc-2222-7000-8000-000000000002",
    "beta": "019fbccc-3333-7000-8000-000000000003",
}

CALL_OK = ('const ids=["%s","%s","%s"];\n'
           'const r=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),timeoutMs:180000});\n'
           'text(JSON.stringify({v:1,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({...}))}));'
           % (NODES["controller"], NODES["alpha"], NODES["beta"]))
CALL_BAD_TIMEOUT = CALL_OK.replace("timeoutMs:180000", "timeoutMs:1000")


def rollout_lines(call_args, printed_text):
    """一次 exec 调用 + 其输出，照真实形态。"""
    return [
        {"timestamp": "2026-08-01T06:00:00.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call", "call_id": "c1", "name": "exec",
                     "arguments": call_args}},
        {"timestamp": "2026-08-01T06:00:01.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call_output", "call_id": "c1",
                     "output": [
                         {"type": "input_text", "text": "Script completed\nWall time 0.3 seconds\nOutput:\n"},
                         {"type": "input_text", "text": printed_text},
                     ]}},
    ]


def write_fixture(call_args, printed_text):
    shutil.rmtree(BROKER / CID, ignore_errors=True)
    (BROKER / f"{CID}.json").unlink(missing_ok=True)
    shutil.rmtree(FAKE_SESSIONS, ignore_errors=True)
    SESSIONS.mkdir(parents=True, exist_ok=True)
    BROKER.mkdir(parents=True, exist_ok=True)

    registry = {
        "schema_version": 1, "coordination_id": CID,
        "context": {"topic": "selftest", "repository": "none"},
        "controller": {"node_id": "controller", "topic": "t",
                       "current_session_id": NODES["controller"],
                       "previous_session_ids": [], "worktree": "C:\\x", "branch": "b",
                       "updated_at": "2026-08-01T06:00:00+02:00"},
        "children": {
            "alpha": {"topic": "t", "current_session_id": NODES["alpha"],
                      "previous_session_ids": [], "worktree": "C:\\x", "branch": "b",
                      "updated_at": "2026-08-01T06:00:00+02:00"},
            "beta": {"topic": "t", "current_session_id": NODES["beta"],
                     "previous_session_ids": [], "worktree": "C:\\x", "branch": "b",
                     "updated_at": "2026-08-01T06:00:00+02:00"},
        },
    }
    (BROKER / f"{CID}.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")

    roll = SESSIONS / f"rollout-2026-08-01T06-00-00-{CTRL}.jsonl"
    with roll.open("w", encoding="utf-8") as fh:
        for line in rollout_lines(call_args, printed_text):
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def run(*args):
    env = dict(os.environ)
    env["THREAD_HARNESS_SESSIONS_ROOT"] = str(FAKE_SESSIONS)
    env["THREAD_HARNESS_BROKER_ROOT"] = str(BROKER)
    p = subprocess.run([sys.executable, "-B", LEDGER, *args],
                       capture_output=True, text=True, encoding="utf-8", env=env)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


GOOD_PROJECTION = json.dumps({
    "v": 1, "n": 2,
    "wake": {"reason": "inactiveStatus", "threadId": NODES["beta"], "hostId": "local"},
    "polls": [
        {"id": NODES["alpha"], "status": "notLoaded", "turn": "t-100",
         "turnStatus": "completed", "txt": "alpha 已提交 abc1234"},
        {"id": NODES["beta"], "status": "notLoaded", "turn": "t-200",
         "turnStatus": "completed", "txt": "beta 待命"},
    ],
}, ensure_ascii=False)

CASES = [
    ("正常投影应通过", CALL_OK, GOOD_PROJECTION, 0, None),
    ("退化输出 text({pollCount:0}) 必须被拦下", CALL_OK, '{"pollCount":0}', 1, "projection missing or wrong version"),
    ("timeoutMs 被调低必须被拦下", CALL_BAD_TIMEOUT, GOOD_PROJECTION, 1, "1000 < 180000"),
    ("缺 polls 键必须被拦下", CALL_OK, '{"v":1,"n":2}', 1, "shape altered"),
    ("n 含了 controller（多算一个）必须被拦下", CALL_OK, json.dumps({"v": 1, "n": 3, "wake": None, "polls": []}), 1, "!= registry children 2"),
    ("poll 元素缺 status 必须被拦下", CALL_OK,
     json.dumps({"v": 1, "n": 2, "wake": None, "polls": [{"id": NODES["alpha"]}]}), 1, "poll entry shape altered"),
]

print("=" * 78)
fails = 0
for i, (name, call, printed, want_rc, want_sub) in enumerate(CASES, 1):
    write_fixture(call, printed)
    run("init", "--coordination-id", CID)
    rc, out = run("sync", "--coordination-id", CID, "--round", str(i))
    first = out.strip().splitlines()[0] if out.strip() else "(no output)"
    ok = (rc == want_rc) and (want_sub is None or want_sub in out)
    if not ok:
        fails += 1
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    print(f"        rc={rc} (want {want_rc})   {first[:110]}")
    if not ok and want_sub:
        print(f"        期待包含: {want_sub!r}")
        print(f"        实际全文: {out.strip()[:400]}")

# SYNC STALE：rollout 里没有任何 wait_threads 调用
print("-" * 78)
write_fixture('const x=1; text("hello");', '"hello"')
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "99")
need = ["path=", "bytes=", "mtime=", "scanned_lines="]
missing = [k for k in need if k not in out]
ok = rc == 1 and "SYNC STALE" in out and not missing
if not ok:
    fails += 1
print(f"[{'PASS' if ok else 'FAIL'}] SYNC STALE 必须带 path/bytes/mtime/scanned_lines")
print(f"        rc={rc}  {out.strip()[:220]}")
if missing:
    print(f"        缺字段: {missing}")

print("=" * 78)
print(f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
