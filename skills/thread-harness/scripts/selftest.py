"""独立核验 ledger.py：不看 codex 的自述，自己造 fixture 跑。

fixture 严格照真实 rollout 形态构造（取自 019fb7ad 主控的实际事件结构）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path


LEDGER = Path(__file__).with_name("ledger.py")
CID = "harness-selftest"
BASE = Path(tempfile.gettempdir()) / "thread-harness-selftest"
BROKER = BASE / "codex-thread-broker"
FAKE_SESSIONS = BASE / "sessions"
SESSIONS = FAKE_SESSIONS / "2026" / "08" / "01"
CTRL = "019fbccc-1111-7000-8000-000000000001"
NODES = {
    "controller": CTRL,
    "alpha": "019fbccc-2222-7000-8000-000000000002",
    "beta": "019fbccc-3333-7000-8000-000000000003",
}
UNKNOWN = "019fbccc-9999-7000-8000-000000000009"


def call_for(ids, timeout=120000):
    quoted = ",".join(json.dumps(item) for item in ids)
    return (
        f"const ids=[{quoted}];\n"
        "const raw=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),"
        f"timeoutMs:{timeout}}});\n"
        "const r=typeof raw===\"string\"?JSON.parse(raw):raw;\n"
        "text(JSON.stringify({v:1,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({"
        "id:p.thread?.id,status:p.thread?.status?.type,turn:p.latestTurn?.id,"
        "turnStatus:p.latestTurn?.status,txt:(p.latestAssistantMessage?.text||\"\").slice(0,500)})),"
        "timedOut:r.timedOut}));"
    )


CALL_OK = call_for([NODES["alpha"], NODES["beta"]])
CALL_ALPHA = call_for([NODES["alpha"]])
CALL_BETA = call_for([NODES["beta"]])
CALL_BAD_TIMEOUT = call_for([NODES["alpha"], NODES["beta"]], timeout=1000)
CALL_HIGH_TIMEOUT = call_for([NODES["alpha"], NODES["beta"]], timeout=180000)


def projection(n=2, alpha_turn="t-100", beta_turn="t-200", wake=None, polls=None):
    if polls is None:
        polls = [
            {"id": NODES["alpha"], "status": "notLoaded", "turn": alpha_turn,
             "turnStatus": "completed", "txt": "alpha"},
            {"id": NODES["beta"], "status": "notLoaded", "turn": beta_turn,
             "turnStatus": "completed", "txt": "beta"},
        ]
    return json.dumps({"v": 1, "n": n, "wake": wake, "polls": polls, "timedOut": False}, ensure_ascii=False)


GOOD_PROJECTION = projection(
    wake={"reason": "inactiveStatus", "threadId": NODES["beta"], "hostId": "local"}
)


def one_projection(node, turn, *, status="notLoaded", turn_status="completed", text=None):
    return projection(
        n=1,
        polls=[
            {
                "id": NODES[node],
                "status": status,
                "turn": turn,
                "turnStatus": turn_status,
                "txt": text or node,
            }
        ],
    )


def run_process(argv, *, cwd=None, env=None):
    p = subprocess.run(argv, cwd=cwd, capture_output=True, text=True, encoding="utf-8", env=env)
    if p.returncode != 0:
        raise RuntimeError(f"{argv} failed rc={p.returncode}\n{p.stdout}{p.stderr}")
    return (p.stdout or "") + (p.stderr or "")


def make_git_repo(path: Path) -> str:
    path.mkdir(parents=True, exist_ok=True)
    run_process(["git", "init"], cwd=path)
    run_process(["git", "config", "user.email", "selftest@example.test"], cwd=path)
    run_process(["git", "config", "user.name", "Thread Harness Selftest"], cwd=path)
    run_process(["git", "commit", "--allow-empty", "-m", "initial"], cwd=path)
    return run_process(["git", "rev-parse", "HEAD"], cwd=path).strip()


def git_head(path: Path) -> str:
    return run_process(["git", "rev-parse", "HEAD"], cwd=path).strip()


def commit_file(path: Path, rel: str, text: str, message: str) -> str:
    target = path / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    run_process(["git", "add", rel], cwd=path)
    run_process(["git", "commit", "-m", message], cwd=path)
    return git_head(path)


def reset_fixture(*, git_worktrees=False):
    shutil.rmtree(BROKER / CID, ignore_errors=True)
    (BROKER / f"{CID}.json").unlink(missing_ok=True)
    shutil.rmtree(FAKE_SESSIONS, ignore_errors=True)
    SESSIONS.mkdir(parents=True, exist_ok=True)
    BROKER.mkdir(parents=True, exist_ok=True)

    if git_worktrees:
        git_root = BASE / "git"
        shutil.rmtree(git_root, ignore_errors=True)
        worktrees = {
            "controller": str(git_root / "controller"),
            "alpha": str(git_root / "alpha"),
            "beta": str(git_root / "beta"),
        }
        for path in worktrees.values():
            make_git_repo(Path(path))
    else:
        worktrees = {"controller": str(BASE / "not-git-controller"),
                     "alpha": str(BASE / "not-git-alpha"),
                     "beta": str(BASE / "not-git-beta")}

    registry = {
        "schema_version": 1,
        "coordination_id": CID,
        "context": {"topic": "selftest", "repository": "none"},
        "controller": {"node_id": "controller", "topic": "t",
                       "current_session_id": NODES["controller"],
                       "previous_session_ids": [], "worktree": worktrees["controller"], "branch": "b",
                       "updated_at": "2026-08-01T06:00:00+02:00"},
        "children": {
            "alpha": {"topic": "t", "current_session_id": NODES["alpha"],
                      "previous_session_ids": [], "worktree": worktrees["alpha"], "branch": "b",
                      "updated_at": "2026-08-01T06:00:00+02:00"},
            "beta": {"topic": "t", "current_session_id": NODES["beta"],
                     "previous_session_ids": [], "worktree": worktrees["beta"], "branch": "b",
                     "updated_at": "2026-08-01T06:00:00+02:00"},
        },
    }
    (BROKER / f"{CID}.json").write_text(json.dumps(registry, ensure_ascii=False), encoding="utf-8")
    return registry


def rollout_path():
    return SESSIONS / f"rollout-2026-08-01T06-00-00-{CTRL}.jsonl"


def child_rollout_path(node):
    return SESSIONS / f"rollout-2026-08-01T06-00-00-{NODES[node]}.jsonl"


def append_child_compaction(node, window_number):
    path = child_rollout_path(node)
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "timestamp": "2026-08-01T06:00:00.000Z",
            "type": "compacted",
            "payload": {
                "window_number": window_number,
                "window_id": f"{node}-window-{window_number}",
            },
        },
        {
            "timestamp": "2026-08-01T06:00:01.000Z",
            "type": "event_msg",
            "payload": {"type": "context_compacted"},
        },
    ]
    with path.open("a", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, ensure_ascii=False) + "\n")


def rollout_lines(call_args, printed_text, call_id, *, source_field="arguments"):
    call_payload = {"type": "custom_tool_call", "call_id": call_id, "name": "exec",
                    source_field: call_args}
    return [
        {"timestamp": "2026-08-01T06:00:00.000Z", "type": "response_item",
         "payload": call_payload},
        {"timestamp": "2026-08-01T06:00:01.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call_output", "call_id": call_id,
                     "output": [
                         {"type": "input_text", "text": "Script completed\nWall time 0.3 seconds\nOutput:\n"},
                         {"type": "input_text", "text": printed_text},
                     ]}},
    ]


def append_wait(call_args, printed_text, call_id="c1", *, dispatch_calls=0,
                source_field="arguments"):
    roll = rollout_path()
    roll.parent.mkdir(parents=True, exist_ok=True)
    with roll.open("a", encoding="utf-8") as fh:
        for index in range(dispatch_calls):
            dispatch_call_id = f"d{call_id}{index}"
            line = {"timestamp": "2026-08-01T06:00:00.000Z", "type": "response_item",
                    "payload": {"type": "custom_tool_call", "call_id": dispatch_call_id, "name": "exec",
                                source_field: "await tools.codex_app__send_message_to_thread({});"}}
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            line = {"timestamp": "2026-08-01T06:00:00.100Z", "type": "response_item",
                    "payload": {"type": "custom_tool_call_output", "call_id": dispatch_call_id,
                                "output": "ok"}}
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        for line in rollout_lines(call_args, printed_text, call_id, source_field=source_field):
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_fixture(call_args, printed_text, *, git_worktrees=False, source_field="arguments"):
    reset_fixture(git_worktrees=git_worktrees)
    append_wait(call_args, printed_text, source_field=source_field)


def write_preflight_registry(registry):
    (BROKER / f"{CID}.json").write_text(
        json.dumps(registry, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
    )


def fixture_local_timestamp(hours_ago):
    return (datetime.now().astimezone() - timedelta(hours=hours_ago)).isoformat(timespec="seconds")


def make_session_age_fixture():
    """独立构造 session_age_h 数据；不调用 ledger.py 的解析或写入函数。"""
    registry = reset_fixture()
    registry["controller"]["updated_at"] = fixture_local_timestamp(30)
    registry["children"]["alpha"]["updated_at"] = fixture_local_timestamp(7.2)
    registry["children"]["beta"]["updated_at"] = fixture_local_timestamp(2.1)
    registry["children"]["historical"] = {
        "active": False,
        "topic": "retained history",
        "current_session_id": "inactive-history-session",
        "updated_at": fixture_local_timestamp(20),
    }
    registry["children"]["gamma"] = {
        "active": True,
        "topic": "missing timestamp",
        "current_session_id": "019fbccc-4444-7000-8000-000000000004",
    }
    write_preflight_registry(registry)
    age_polls = [
        {"id": NODES["alpha"], "status": "notLoaded", "turn": "age-alpha",
         "turnStatus": "completed", "txt": "alpha"},
        {"id": NODES["beta"], "status": "notLoaded", "turn": "age-beta",
         "turnStatus": "completed", "txt": "beta"},
        {"id": registry["children"]["gamma"]["current_session_id"], "status": "notLoaded",
         "turn": "age-gamma", "turnStatus": "completed", "txt": "gamma"},
    ]
    age_projection = json.dumps(
        {"v": 1, "n": 3, "wake": None, "polls": age_polls, "timedOut": False},
        ensure_ascii=False,
    )
    return call_for([NODES["alpha"], NODES["beta"], age_polls[2]["id"]]), age_projection


def make_route_fixture():
    """独立构造 route 数据；不调用 ledger.py 的解析或写入函数。"""
    registry = reset_fixture()
    registry["context"]["unknown_context_field"] = {"keep": ["context", 7]}
    registry["controller"]["unknown_controller_field"] = {"keep": True}
    registry["children"]["alpha"]["unknown_child_field"] = ["preserve", {"x": 1}]
    registry["children"]["alpha"]["updated_at"] = fixture_local_timestamp(6)
    registry["children"]["beta"]["unknown_sibling_field"] = "untouched"
    write_preflight_registry(registry)

    runtime = BROKER / CID
    runtime.mkdir(parents=True, exist_ok=True)
    for name, content in {
        "progress.jsonl": b"progress sentinel\n",
        "seams.jsonl": b"seams sentinel\n",
        "decisions.jsonl": b"decisions sentinel\n",
        "acts.jsonl": b"acts sentinel\n",
        "sync-state.json": b"{\"sentinel\":true}\n",
    }.items():
        (runtime / name).write_bytes(content)
    return (BROKER / f"{CID}.json").resolve()


def route_other_registry_bytes(registry):
    """序列化除目标 alpha node 外的 registry 部分，独立于 ledger.py 实现。"""
    other = json.loads(json.dumps(registry, ensure_ascii=False))
    del other["children"]["alpha"]
    return json.dumps(other, ensure_ascii=False, separators=(",", ":"), sort_keys=False).encode("utf-8")


def route_runtime_snapshot():
    runtime = BROKER / CID
    return {
        name: (runtime / name).read_bytes() if (runtime / name).exists() else None
        for name in ("progress.jsonl", "seams.jsonl", "decisions.jsonl", "acts.jsonl", "sync-state.json")
    }


def make_preflight_fixture(child_count=2):
    """独立构造 preflight 数据；不调用 ledger.py 的解析或写入函数。"""
    shutil.rmtree(BROKER / CID, ignore_errors=True)
    (BROKER / f"{CID}.json").unlink(missing_ok=True)
    shutil.rmtree(FAKE_SESSIONS, ignore_errors=True)
    preflight_root = BASE / "preflight-git"
    shutil.rmtree(preflight_root, ignore_errors=True)
    preflight_root.mkdir(parents=True, exist_ok=True)
    BROKER.mkdir(parents=True, exist_ok=True)
    SESSIONS.mkdir(parents=True, exist_ok=True)

    if child_count == 2:
        child_names = ["foundation_catalog", "foundation_customer_runtime"]
    else:
        child_names = [f"child_{index}" for index in range(1, child_count + 1)]
    node_names = ["controller", *child_names]
    sessions = {
        name: f"preflight-{index:02d}-session"
        for index, name in enumerate(node_names, 1)
    }
    worktrees = {}
    branches = {}
    for name in node_names:
        path = preflight_root / name
        branch = f"preflight/{name.replace('_', '-')}"
        make_git_repo(path)
        run_process(["git", "branch", "-M", branch], cwd=path)
        worktrees[name] = str(path)
        branches[name] = branch
        (SESSIONS / f"rollout-{sessions[name]}.jsonl").write_text("", encoding="utf-8")

    registry = {
        "schema_version": 1,
        "coordination_id": CID,
        "controller": {
            "node_id": "controller",
            "current_session_id": sessions["controller"],
            "worktree": worktrees["controller"],
            "branch": branches["controller"],
        },
        "children": {
            name: {
                "current_session_id": sessions[name],
                "worktree": worktrees[name],
                "branch": branches[name],
            }
            for name in child_names
        },
    }
    write_preflight_registry(registry)
    return {
        "registry": registry,
        "sessions": sessions,
        "worktrees": worktrees,
        "branches": branches,
        "children": child_names,
    }


def env():
    e = dict(os.environ)
    e["THREAD_HARNESS_SESSIONS_ROOT"] = str(FAKE_SESSIONS)
    e["THREAD_HARNESS_BROKER_ROOT"] = str(BROKER)
    return e


def run(*args):
    p = subprocess.run([sys.executable, "-B", str(LEDGER), *args],
                       capture_output=True, text=True, encoding="utf-8", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def run_registry(*args):
    return run(*args, "--registry", str((BROKER / f"{CID}.json").resolve()))


def ledger_rows(name):
    path = BROKER / CID / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_ledger_row(name, row):
    path = BROKER / CID / name
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def append_progress_round(seq):
    for node, head in (("alpha", "a" * 40), ("beta", "b" * 40)):
        append_ledger_row("progress.jsonl", {
            "ts": f"2026-08-01T06:{seq:02d}:00+02:00",
            "src": "poll",
            "seq": seq,
            "round": seq,
            "node": node,
            "head": head,
            "turn": f"manual-{node}-{seq}",
            "status": "notLoaded",
            "turn_status": "completed",
            "state": "working",
            "note": "manual fixture",
        })


def append_progress_streak(streak):
    for seq in range(1, streak + 2):
        append_progress_round(seq)


def append_decision(decision_id, ts, status="pending", *, by="alpha", answer=None, instance=None):
    row = {
        "ts": ts,
        "decision_id": decision_id,
        "raised_by": by if status == "pending" else None,
        "blocks": ["alpha"] if status == "pending" else [],
        "question": f"{decision_id}?" if status == "pending" else None,
        "status": status,
        "answer": answer,
    }
    if instance:
        row["decision_instance_id"] = instance
    append_ledger_row("decisions.jsonl", row)


def append_escalate(decision_id, ts, seq=1, instance=None):
    row = {
        "ts": ts,
        "seq": seq,
        "kind": "escalate",
        "seam_id": None,
        "producer": None,
        "deliverable": None,
        "decision_id": decision_id,
    }
    if instance:
        row["decision_instance_id"] = instance
    append_ledger_row("acts.jsonl", row)


def check(name, ok, detail=""):
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if detail:
        print(f"        {detail[:500]}")
    return 0 if ok else 1


print("=" * 78)
fails = 0

CASES = [
    ("正常投影应通过", CALL_OK, GOOD_PROJECTION, 0, None),
    ("退化输出 text({pollCount:0}) 必须被拦下", CALL_OK, '{"pollCount":0}', 1, "projection missing or wrong version"),
    ("timeoutMs 被调低必须被拦下", CALL_BAD_TIMEOUT, GOOD_PROJECTION, 1, "1000 != 120000"),
    ("timeoutMs 超过平台上限必须被拦下", CALL_HIGH_TIMEOUT, GOOD_PROJECTION, 1, "180000 != 120000"),
    ("缺 polls 键必须被拦下", CALL_OK, '{"v":1,"n":2}', 1, "shape altered"),
    ("缺 timedOut 键必须被拦下", CALL_OK,
     json.dumps({"v": 1, "n": 2, "wake": None, "polls": []}), 1, "missing timedOut"),
    ("poll 元素缺 status 必须被拦下", CALL_OK,
     json.dumps({"v": 1, "n": 2, "wake": None,
                 "polls": [{"id": NODES["alpha"], "turn": "t", "turnStatus": "completed", "txt": ""}],
                 "timedOut": False}),
     1, "poll entry shape altered"),
    ("ids 混入 controller 必须被拦下", call_for([NODES["controller"], NODES["alpha"], NODES["beta"]]),
     projection(n=3), 1, "targets mismatch"),
    ("ids 少一个 child 必须被拦下", call_for([NODES["alpha"]]), projection(n=1), 1, "targets mismatch"),
    ("ids 换成陌生 id 必须被拦下", call_for([NODES["alpha"], UNKNOWN]), projection(n=2), 1, "targets mismatch"),
    ("投影 n 与实际 ids 数量不符必须被拦下", CALL_OK, projection(n=3), 1,
     "projection n=3 != actual targets 2"),
    ("解析不出 ids 数组必须被拦下", 'const targets=[]; await tools.codex_app__wait_threads({targets,timeoutMs:120000});',
     GOOD_PROJECTION, 1, "cannot parse ids array"),
]

for i, (name, call, printed, want_rc, want_sub) in enumerate(CASES, 1):
    write_fixture(call, printed)
    run("init", "--coordination-id", CID)
    rc, out = run("sync", "--coordination-id", CID, "--round", str(i))
    ok = (rc == want_rc) and (want_sub is None or want_sub in out)
    first = out.strip().splitlines()[0] if out.strip() else "(no output)"
    fails += check(name, ok, f"rc={rc} (want {want_rc}) {first}")

print("-" * 78)
write_fixture(CALL_OK, GOOD_PROJECTION, source_field="input")
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "101")
fails += check("modern input wait call 必须被识别并同步",
               rc == 0 and "valid=yes" in out,
               f"rc={rc} {out.strip().splitlines()[0] if out.strip() else '(no output)'}")

write_fixture(CALL_HIGH_TIMEOUT, GOOD_PROJECTION, source_field="input")
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "102")
fails += check("modern input wait call 仍须执行 timeout 自检",
               rc == 1 and "180000 != 120000" in out,
               f"rc={rc} {out.strip().splitlines()[0] if out.strip() else '(no output)'}")

reset_fixture()
append_wait(CALL_OK, GOOD_PROJECTION, call_id="modern-dispatch", dispatch_calls=1,
            source_field="input")
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "103")
fails += check("modern input dispatch call 必须计数",
               rc == 0 and "dispatches_since_progress: 1" in out,
               f"rc={rc} {out.strip().splitlines()[0] if out.strip() else '(no output)'}")

print("-" * 78)
write_fixture('const x=1; text("hello");', '"hello"')
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "99")
missing = [k for k in ["path=", "bytes=", "mtime=", "scanned_lines="] if k not in out]
fails += check("SYNC STALE 必须带 path/bytes/mtime/scanned_lines",
               rc == 1 and "SYNC STALE" in out and not missing,
               f"rc={rc} {out.strip()}")

print("-" * 78)
write_fixture(CALL_OK, GOOD_PROJECTION, git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("sync 摘要包含 head_unavailable/never_reported/dispatches_since_progress",
               rc == 0 and "head_unavailable: -" in out and "never_reported:  alpha, beta" in out
               and "dispatches_since_progress: 0" in out,
               out.strip())

append_wait(CALL_OK, projection(alpha_turn="t-idle-only", beta_turn="t-idle-old", polls=[
    {"id": NODES["alpha"], "status": "notLoaded", "turn": "t-idle-only",
     "turnStatus": "completed", "txt": "alpha only"},
]), call_id="idle-missing")
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
progress_rows = [row for row in ledger_rows("progress.jsonl") if row.get("round") == 2]
beta_rows = [row for row in progress_rows if row.get("node") == "beta"]
fails += check("polls[] 缺 child 时仍写 progress 行并读取 head",
               rc == 0 and len(progress_rows) == 2 and beta_rows and beta_rows[0].get("head"),
               out.strip())

rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam",
              "--waiting-on", "seam:x", "seam:y", "--head", git_head(BASE / "git" / "alpha"))
fails += check("report 支持 --waiting-on 空格分隔并写 src=report", rc == 0, out.strip())
append_wait(CALL_BETA, one_projection("beta", "t-201"), call_id="c2")
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
fails += check("report 的 state/waiting_on 不被后续 sync 覆盖",
               rc == 0 and "poll_targets:    beta" in out and "seams_unowned:   2" in out
               and "never_reported:  beta" in out,
               out.strip())

rc, out = run("seam", "--coordination-id", CID, "--seam-id", "x", "--producer", "alpha",
              "--consumers", "beta", "controller")
fails += check("seam 支持 --consumers 空格分隔且允许 registry 中的 controller",
                rc == 0, out.strip())
rc, out = run("seam", "--coordination-id", CID, "--seam-id", "seam:prefixed-x",
              "--producer", "alpha", "--consumers", "beta")
prefixed_seam_rows = ledger_rows("seams.jsonl")
fails += check("seam 接受 seam:<id> 并以裸 ID 写入账本",
               rc == 0 and "seam prefixed-x status=assigned" in out
               and prefixed_seam_rows[-1].get("seam_id") == "prefixed-x",
               out.strip())
rc, out = run("seam", "--coordination-id", CID, "--seam-id", "bad", "--producer", "typo",
              "--consumers", "beta")
fails += check("seam producer 拼错必须退出 64", rc == 64 and "unknown producer node: typo" in out, out.strip())
rc, out = run("seam", "--coordination-id", CID, "--seam-id", "bad", "--producer", "alpha",
              "--consumers", "typo")
fails += check("seam consumer 拼错必须退出 64", rc == 64 and "unknown consumer node: typo" in out, out.strip())

print("-" * 78)
write_fixture(CALL_OK, projection(alpha_turn="t-1", beta_turn="t-1"), git_worktrees=True)
run("init", "--coordination-id", CID)
for round_no in range(1, 7):
    if round_no > 1:
        append_wait(CALL_OK, projection(alpha_turn=f"t-{round_no}", beta_turn=f"t-{round_no}"),
                    call_id=f"stall{round_no}", dispatch_calls=1)
    run("sync", "--coordination-id", CID, "--round", str(round_no))
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("turn 变化但 git head 不变时 stall-check 连续 5 轮后退出 2",
               rc == 2 and "MUST_ACT stall_streak=5/5" in out and "dispatches_since_progress=5" in out,
               out.strip())
rc, out = run("heartbeat", "--coordination-id", CID, "--node", "alpha",
              "--evidence", "new focused test is running")
fails += check("达到 5/5 后不得用 heartbeat 绕过 MUST_ACT",
               rc == 64 and "requires 3/5 <= stall_streak < 5/5" in out,
               f"rc={rc} {out.strip()}")

# --- 回归：git HEAD 真推进后必须归零（否则会常态误报 MUST_ACT）---
subprocess.run(["git", "-C", str(BASE / "git" / "alpha"), "commit", "--allow-empty", "-q",
                "-m", "real work"], check=True)
append_wait(CALL_OK, projection(alpha_turn="t-9", beta_turn="t-9"), call_id="prog9")
run("sync", "--coordination-id", CID, "--round", "9")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("git head 真推进后 stall_streak 必须归零",
               rc == 0 and "stall_streak=0/5" in out, out.strip())

# --- 回归：3/5 起由 controller 读 thread；具体新进展只重置运行时 streak ---
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_wait(CALL_OK, projection(alpha_turn="hb-1", beta_turn="hb-1"), call_id="hb1")
run("sync", "--coordination-id", CID, "--round", "1")
rc, out = run("heartbeat", "--coordination-id", CID, "--node", "alpha",
              "--evidence", "new focused test is running")
fails += check("3/5 之前不得用 heartbeat 绕过 HEAD 停滞",
               rc == 64 and "requires 3/5 <= stall_streak < 5/5" in out,
               f"rc={rc} {out.strip()}")
for round_no in range(2, 5):
    append_wait(CALL_OK, projection(alpha_turn=f"hb-{round_no}", beta_turn=f"hb-{round_no}"),
                call_id=f"hb{round_no}")
    run("sync", "--coordination-id", CID, "--round", str(round_no))
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("3/5 时 stall-check 提示 controller 直接 read_thread",
               rc == 0 and "CHECK_HEARTBEAT stall_streak=3/5" in out,
               out.strip())
rc, out = run("heartbeat", "--coordination-id", CID, "--node", "typo",
              "--evidence", "new focused test is running")
fails += check("heartbeat node 必须是 registry child",
               rc == 64 and "unknown child node: typo" in out,
               f"rc={rc} {out.strip()}")
ledger_dir = BROKER / CID
jsonl_before = {
    name: (ledger_dir / name).read_bytes()
    for name in ("progress.jsonl", "seams.jsonl", "decisions.jsonl", "acts.jsonl")
}
rc, out = run("heartbeat", "--coordination-id", CID, "--node", "alpha",
              "--evidence", "new focused test is running")
rc_after, out_after = run("stall-check", "--coordination-id", CID)
jsonl_after = {
    name: (ledger_dir / name).read_bytes()
    for name in ("progress.jsonl", "seams.jsonl", "decisions.jsonl", "acts.jsonl")
}
runtime_state = json.loads((ledger_dir / "sync-state.json").read_text(encoding="utf-8"))
fails += check("read_thread 确认 concrete heartbeat 后 streak 归零且不改 JSONL",
               rc == 0 and "heartbeat reset" in out and rc_after == 0
               and "stall_streak=0/5" in out_after and jsonl_after == jsonl_before
               and runtime_state.get("stall_reset_seq") == 4
               and not any(key.startswith("last_heartbeat_") for key in runtime_state),
               f"heartbeat={out.strip()} after={out_after.strip()}")

# --- 回归：head 取不到时必须 fail-closed，继续累计停滞 ---
# 曾经的 bug：任一 head 为 None 就把 streak 清零，导致一条线的 worktree 路径写错
# 就永久关掉整组的停滞检测，而且完全无声。无法确认有推进 = 没有推进。
shutil.rmtree(BASE / "git" / "alpha", ignore_errors=True)
sync_out = ""
for round_no in range(10, 15):
    append_wait(CALL_OK, projection(alpha_turn=f"t-{round_no}", beta_turn=f"t-{round_no}"),
                call_id=f"gone{round_no}")
    # 注意：sync 必须先有新的 rollout 内容才不会判 SYNC STALE，所以复用本轮输出，
    # 不要事后再补跑一次空的 sync。
    _, sync_out = run("sync", "--coordination-id", CID, "--round", str(round_no))
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("worktree 消失导致 head 取不到时仍须累计停滞（fail-closed）",
               rc == 2 and "MUST_ACT" in out, out.strip())
fails += check("head 取不到的 node 必须出现在 head_unavailable",
               any("head_unavailable" in l and "alpha" in l for l in sync_out.splitlines()),
               sync_out.strip()[:200])

rc, out = run("decide", "--coordination-id", CID, "--raise", "d1", "--by", "alpha",
              "--blocks", "alpha", "beta", "--question", "approve?")
fails += check("decide --raise 支持 --blocks 空格分隔", rc == 0, out.strip())
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("pending decision 优先于停滞并退出 3", rc == 3 and "MUST_ESCALATE" in out, out.strip())
rc, out = run("decide", "--coordination-id", CID, "--answer", "d1", "--text", "yes")
fails += check("decide --answer 可清掉 pending decision", rc == 0, out.strip())
rc, out = run("stall-check", "--coordination-id", CID, "--streak", "99")
fails += check("stall-check 不再接受调用方覆盖阈值",
               rc == 64 and "unrecognized arguments: --streak 99" in out,
               out.strip())
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("移除 --streak 后停滞阈值固定为 5",
               rc == 2 and "MUST_ACT stall_streak=5/5" in out,
               out.strip())

print("-" * 78)
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(0)
append_decision("pending-new", "2026-08-01T06:00:00+02:00")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("pending decision 尚未有对应 escalate 行时 stall-check 退出 3",
               rc == 3 and "MUST_ESCALATE" in out and "pending-new" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(0)
append_decision("pending-seen", "2026-08-01T06:00:00+02:00")
append_escalate("pending-seen", "2026-08-01T06:00:05+02:00")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("pending decision 已上报且 streak 未达阈值时不再退出 3",
               rc == 0 and ("OK " in out or "CHECK_HEARTBEAT" in out)
               and "MUST_ESCALATE" not in out and "pending_escalated: pending-seen" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(5)
append_decision("pending-seen-act", "2026-08-01T06:00:00+02:00")
append_escalate("pending-seen-act", "2026-08-01T06:00:05+02:00")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("pending decision 已上报且 streak 达阈值时必须产出 MUST_ACT",
               rc == 2 and "MUST_ACT" in out and "pending_escalated: pending-seen-act" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(0)
append_decision("pending-reported", "2026-08-01T06:00:00+02:00")
append_decision("pending-unreported", "2026-08-01T06:00:01+02:00")
append_escalate("pending-reported", "2026-08-01T06:00:05+02:00")
rc, out = run("stall-check", "--coordination-id", CID)
first_line = out.strip().splitlines()[0] if out.strip() else ""
fails += check("部分 pending 已上报时只升级未上报项并列 already_escalated",
               rc == 3 and "pending-unreported" in first_line and "pending-reported" not in first_line
               and "already_escalated: pending-reported" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(0)
append_decision("pending-reraised", "2026-08-01T06:00:00+02:00")
append_escalate("pending-reraised", "2026-08-01T06:00:05+02:00")
append_decision("pending-reraised", "2026-08-01T06:00:10+02:00", status="answered", answer="yes")
append_decision("pending-reraised", "2026-08-01T06:00:20+02:00")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("decision answered 后同 id 重新 raise 必须重新升级",
               rc == 3 and "MUST_ESCALATE" in out and "pending-reraised" in out,
               out.strip())

# --- decision instance：同秒 raise -> answer -> raise 不能被旧 escalate 遮蔽 ---
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
rc_raise1, out_raise1 = run("decide", "--coordination-id", CID, "--raise", "same-second", "--by", "alpha")
first_decision = ledger_rows("decisions.jsonl")[-1]
first_instance = first_decision.get("decision_instance_id")
rc_escalate1, out_escalate1 = run(
    "act", "--coordination-id", CID, "--escalate", "--decision-id", "same-second"
)
rc_answer, out_answer = run(
    "decide", "--coordination-id", CID, "--answer", "same-second", "--text", "yes"
)
rc_raise2, out_raise2 = run("decide", "--coordination-id", CID, "--raise", "same-second", "--by", "alpha")
decision_rows = ledger_rows("decisions.jsonl")
second_decision = decision_rows[-1]
second_instance = second_decision.get("decision_instance_id")
rc_instance_stall, out_instance_stall = run("stall-check", "--coordination-id", CID)
rc_escalate2, out_escalate2 = run(
    "act", "--coordination-id", CID, "--escalate", "--decision-id", "same-second"
)
act_rows = ledger_rows("acts.jsonl")
fails += check(
    "decision instance 精确区分同秒重开并只升级新 instance",
    rc_raise1 == 0 and rc_escalate1 == 0 and rc_answer == 0 and rc_raise2 == 0
    and rc_instance_stall == 3 and "MUST_ESCALATE" in out_instance_stall
    and rc_escalate2 == 0 and first_instance and second_instance and first_instance != second_instance
    and decision_rows[1].get("decision_instance_id") == first_instance
    and act_rows[-1].get("decision_instance_id") == second_instance,
    f"raise1={out_raise1.strip()} answer={out_answer.strip()} stall={out_instance_stall.strip()} "
    f"raise2={out_raise2.strip()} escalate2={out_escalate2.strip()}",
)

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
halt_before = route_runtime_snapshot()
rc, out = run("act", "--coordination-id", CID, "--halt", "--reason", "missing caller identity")
fails += check("act --halt 缺 source-session 必须退出 64 且不写账本",
               rc == 64 and "act --halt requires --source-session" in out
               and route_runtime_snapshot() == halt_before,
               f"rc={rc} {out.strip()}")
rc, out = run("act", "--coordination-id", CID, "--halt", "--source-session", NODES["controller"])
fails += check("act --halt 缺 reason 必须退出 64",
               rc == 64 and "act --halt requires --reason" in out
               and route_runtime_snapshot() == halt_before,
               f"rc={rc} {out.strip()}")

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
halt_before = route_runtime_snapshot()
rc, out = run("act", "--coordination-id", CID, "--halt", "--source-session", NODES["alpha"],
              "--reason", "child must not stop coordination")
fails += check("非 controller 调用 act --halt 必须拒绝且不新增账本行",
               rc == 64 and "source session must match controller current_session_id" in out
               and route_runtime_snapshot() == halt_before,
               f"rc={rc} {out.strip()}")

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_decision("halt-d1", "2026-08-01T06:00:00+02:00")
append_decision("halt-d2", "2026-08-01T06:00:01+02:00")
rc_halt, out_halt = run("act", "--coordination-id", CID, "--halt",
                        "--source-session", NODES["controller"], "--reason", "owner stopped loop")
halt_rows = ledger_rows("acts.jsonl")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("halt 后 stall-check 只输出 HALTED 且不输出业务动作标记",
               rc_halt == 0 and halt_rows and halt_rows[-1].get("kind") == "halt"
               and halt_rows[-1].get("reason") == "owner stopped loop"
               and halt_rows[-1].get("pending_decision_ids") == ["halt-d1", "halt-d2"]
               and rc == 4 and "HALTED" in out
               and "MUST_ACT" not in out and "MUST_ESCALATE" not in out and "CHECK_HEARTBEAT" not in out,
               f"act={out_halt.strip()} stall={out.strip()}")
rc, out = run("status", "--coordination-id", CID)
status_lines = out.splitlines()[:5]
fails += check("halt 后 status 顶部暴露 halted、reason 与 pending ids",
               rc == 0 and status_lines[:2] == ["STATUS", "halted: yes"]
               and any("owner stopped loop" in line for line in status_lines)
               and any("halt-d1" in line and "halt-d2" in line for line in status_lines),
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_progress_streak(5)
run("act", "--coordination-id", CID, "--halt", "--source-session", NODES["controller"],
    "--reason", "temporary stop")
rc_halted, out_halted = run("stall-check", "--coordination-id", CID)
rc_dispatch, out_dispatch = run("act", "--coordination-id", CID, "--dispatch", "--seam-id", "resume-seam",
                                "--producer", "alpha", "--deliverable", "resume concrete work")
rc_still_halted, out_still_halted = run("stall-check", "--coordination-id", CID)
append_wait(CALL_OK, projection(alpha_turn="owner-resume", beta_turn="owner-resume"), call_id="owner-resume")
rc_sync_resume, out_sync_resume = run("sync", "--coordination-id", CID, "--round", "8")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("halt 只阻止当前 loop，dispatch 不得隐式 resume；新 valid poll 才解除",
               rc_halted == 4 and "HALTED" in out_halted
               and rc_dispatch == 0 and rc_still_halted == 4 and "HALTED" in out_still_halted
               and rc_sync_resume == 0 and rc == 0 and "HALTED" not in out,
               f"halted={out_halted.strip()} dispatch={out_dispatch.strip()} "
               f"still={out_still_halted.strip()} sync={out_sync_resume.strip()} after={out.strip()}")

print("-" * 78)
write_fixture(CALL_OK, GOOD_PROJECTION, git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("stall-check 无停滞时退出 0", rc == 0 and out.startswith("OK "), out.strip())
rc, out = run("sync", "--coordination-id", CID, "--round", "1", "--no-such-arg")
fails += check("usage error 退出码 64", rc == 64, f"rc={rc} {out.strip()}")
rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "not-a-state")
fails += check("非法 report state 退出码 64", rc == 64 and "invalid state" in out, out.strip())
rc, out = run("decide", "--coordination-id", CID)
fails += check("decide 缺 raise/answer 退出码 64", rc == 64 and "decide requires" in out, out.strip())

print("-" * 78)
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
for index in range(6):
    append_wait(CALL_OK, projection(alpha_turn=f"same-{index}", beta_turn=f"same-{index}"),
                call_id=f"sameround{index}", dispatch_calls=1 if index else 0)
    run("sync", "--coordination-id", CID, "--round", "7")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("同一个 --round 重复 6 次时 stall_streak 仍按 append 顺序累计到 5",
               rc == 2 and "MUST_ACT stall_streak=5/5" in out,
               out.strip())

rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam")
fails += check("awaiting_seam 缺 waiting_on 必须退出 64",
               rc == 64 and "requires --waiting-on seam:<id>" in out,
               f"rc={rc} {out.strip()}")
rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam",
              "--waiting-on", "free text")
fails += check("awaiting_seam 使用自由文本 waiting_on 必须退出 64",
               rc == 64 and "requires --waiting-on seam:<id>" in out,
               f"rc={rc} {out.strip()}")

alpha_repo = BASE / "git" / "alpha"
old_head = git_head(alpha_repo)
rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam",
              "--waiting-on", "seam:x", "--head", old_head)
commit_file(alpha_repo, "work.py", "print('stale')\n", "code after report")
append_wait(CALL_BETA, one_projection("beta", "stale-b"), call_id="stale")
rc, out = run("sync", "--coordination-id", CID, "--round", "8")
fails += check("report 之后 HEAD 变化必须暴露 stale_reports",
               rc == 0 and "poll_targets:    beta" in out and "stale_reports:" in out and "alpha" in out,
               out.strip())

print("-" * 78)
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_wait(CALL_OK, projection(alpha_turn="m4-0", beta_turn="m4-0"), call_id="m40")
run("sync", "--coordination-id", CID, "--round", "1")
commit_file(BASE / "git" / "alpha", "feature.py", "print('code')\n", "code first")
commit_file(BASE / "git" / "alpha", "docs/progress.md", "docs gate\n", "docs gate")
append_wait(CALL_OK, projection(alpha_turn="m4-code-docs", beta_turn="m4-code-docs"),
            call_id="m4-code-docs", dispatch_calls=1)
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
fails += check("区间内先 code 后 docs 必须判 code 并清零 dispatches_since_progress",
               rc == 0 and "advance_kinds:   alpha=code" in out
               and "dispatches_since_progress: 0" in out and "docs_only_advances: 0" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_wait(CALL_OK, projection(alpha_turn="m4-docs-0", beta_turn="m4-docs-0"), call_id="m4-docs-0")
run("sync", "--coordination-id", CID, "--round", "1")
commit_file(BASE / "git" / "alpha", "docs/progress.md", "docs only 1\n", "docs only 1")
commit_file(BASE / "git" / "alpha", "notes.md", "docs only 2\n", "docs only 2")
append_wait(CALL_OK, projection(alpha_turn="m4-docs-2", beta_turn="m4-docs-2"),
            call_id="m4-docs-2", dispatch_calls=1)
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
fails += check("区间内两个 docs commit 必须判 docs 且 dispatch 计数不归零",
               rc == 0 and "advance_kinds:   alpha=docs" in out
               and "dispatches_since_progress: 1" in out and "docs_only_advances: 1" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
commit_file(BASE / "git" / "alpha", "docs/first.md", "first docs\n", "first docs")
commit_file(BASE / "git" / "beta", "docs/first.md", "first docs\n", "first docs")
append_wait(CALL_OK, projection(alpha_turn="m4-first", beta_turn="m4-first"),
            call_id="m4-first", dispatch_calls=1)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("首次观测仍按单 commit 逻辑识别 docs-only",
               rc == 0 and "alpha=docs" in out and "beta=docs" in out
               and "dispatches_since_progress: 1" in out and "docs_only_advances: 2" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
append_wait(CALL_OK, projection(alpha_turn="m4-0", beta_turn="m4-0"), call_id="m40")
run("sync", "--coordination-id", CID, "--round", "1")
commit_file(BASE / "git" / "alpha", "docs/progress.md", "docs only\n", "docs only")
append_wait(CALL_OK, projection(alpha_turn="m4-1", beta_turn="m4-1"), call_id="m41", dispatch_calls=1)
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
fails += check("docs-only commit 不清零 dispatches_since_progress 且 docs_only_advances 加 1",
               rc == 0 and "dispatches_since_progress: 1" in out and "docs_only_advances: 1" in out,
               out.strip())
commit_file(BASE / "git" / "alpha", "feature.py", "print('code')\n", "code work")
append_wait(CALL_OK, projection(alpha_turn="m4-2", beta_turn="m4-2"), call_id="m42", dispatch_calls=1)
rc, out = run("sync", "--coordination-id", CID, "--round", "3")
fails += check(".py commit 作为 code 推进会清零 dispatches_since_progress",
               rc == 0 and "dispatches_since_progress: 0" in out and "docs_only_advances: 0" in out,
               out.strip())

print("-" * 78)
rc, out = run("act", "--coordination-id", CID, "--dispatch", "--seam-id", "x", "--producer", "alpha")
fails += check("act --dispatch 缺 deliverable 必须退出 64",
               rc == 64 and "requires --deliverable" in out,
               f"rc={rc} {out.strip()}")

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("report", "--coordination-id", CID, "--node", "beta", "--state", "awaiting_seam",
              "--waiting-on", "seam:s9")
rc_before, out_before = run("status", "--coordination-id", CID)
rc_act, out_act = run("act", "--coordination-id", CID, "--dispatch", "--seam-id", "seam:s9",
                      "--producer", "alpha", "--deliverable", "x")
rc_after, out_after = run("status", "--coordination-id", CID)
seam_rows = ledger_rows("seams.jsonl")
fails += check("act --dispatch 接受 seam:<id>、裸 ID 入账并形成 ownership",
               rc == 0 and rc_before == 0 and "seams_unowned:   1" in out_before
               and rc_act == 0 and rc_after == 0 and "seams_unowned:   0" in out_after
               and any(row.get("seam_id") == "s9" and row.get("producer") == "alpha"
                       and row.get("status") == "assigned" and row.get("artifact") is None
                       for row in seam_rows),
               f"before={out_before.strip()} act={out_act.strip()} after={out_after.strip()}")

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
alpha_head = git_head(BASE / "git" / "alpha")
rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam",
              "--waiting-on", "seam:stale", "--head", alpha_head)
commit_file(BASE / "git" / "alpha", "work.py", "print('fresh')\n", "fresh code")
append_wait(CALL_BETA, one_projection("beta", "r2b-b"), call_id="r2b")
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("stale awaiting_seam 的 waiting_on 不计入 seams_unowned 并计入 stale_waiting_on",
               rc == 0 and "stale_reports:" in out and "alpha" in out
               and "seams_unowned:   0" in out and "stale_waiting_on: 1" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
for index in range(6):
    append_wait(CALL_OK, projection(alpha_turn=f"act-{index}", beta_turn=f"act-{index}"),
                call_id=f"act{index}")
    run("sync", "--coordination-id", CID, "--round", "1")
rc, out = run("stall-check", "--coordination-id", CID)
before_ok = rc == 2 and "last_must_act_answered: no" in out
rc_act, out_act = run("act", "--coordination-id", CID, "--dispatch", "--seam-id", "x",
                      "--producer", "alpha", "--deliverable", "one sentence")
rc_after, out_after = run("stall-check", "--coordination-id", CID)
fails += check("stall-check 的 last_must_act_answered 在 act 前后分别为 no/yes",
               before_ok and rc_act == 0 and rc_after == 2 and "last_must_act_answered: yes" in out_after,
               f"before={out.strip()} act={out_act.strip()} after={out_after.strip()}")

print("-" * 78)
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("status", "--coordination-id", CID)
fails += check("status 在从未 sync 的新账本上也能输出",
               rc == 0 and out.startswith("STATUS") and "stall_streak:" in out,
               out.strip())

(BROKER / CID / "progress.jsonl").write_text("{bad json\n", encoding="utf-8")
rc, out = run("status", "--coordination-id", CID)
fails += check("status 摘要必须暴露 corrupt_ledger_lines",
               rc == 6 and out.startswith("LEDGER INTEGRITY FAILED: progress.jsonl:1 invalid_json")
               and "ledger_integrity: FAILED" in out and "corrupt_ledger_lines: 1" in out,
               out.strip())

invalid_ledger_seq = {"ts": "2026-08-01T06:00:00+02:00", "ledger_seq": "2", "src": "report",
                      "round": 0, "node": "alpha", "head": None, "state": "working",
                      "waiting_on": [], "last_report_ts": "2026-08-01T06:00:00+02:00", "note": "bad seq"}
(BROKER / CID / "progress.jsonl").write_text(
    json.dumps(invalid_ledger_seq, ensure_ascii=False) + "\n", encoding="utf-8"
)
rc, out = run("status", "--coordination-id", CID)
fails += check("status 摘要必须拒绝非法 ledger_seq 类型",
               rc == 6 and "LEDGER INTEGRITY FAILED: progress.jsonl:1 invalid_ledger_seq" in out,
               out.strip())

bad_waiting = {"ts": "2026-08-01T06:00:00+02:00", "src": "report", "round": 0,
               "node": "alpha", "head": None, "state": "awaiting_seam",
               "waiting_on": ["free text", "seam:"], "last_report_ts": "2026-08-01T06:00:00+02:00",
               "note": "legacy bad row"}
(BROKER / CID / "progress.jsonl").write_text(json.dumps(bad_waiting, ensure_ascii=False) + "\n",
                                             encoding="utf-8")
rc, out = run("status", "--coordination-id", CID)
fails += check("status 摘要必须暴露 malformed_waiting_on",
               rc == 0 and "malformed_waiting_on: 2" in out,
               out.strip())

# --- ledger integrity：任何会推进状态的命令遇到坏行都 fail-closed 且不写新事实 ---
write_fixture(CALL_OK, GOOD_PROJECTION, git_worktrees=True)
run("init", "--coordination-id", CID)
(BROKER / CID / "decisions.jsonl").write_text("{truncated\n", encoding="utf-8")
integrity_before = route_runtime_snapshot()
integrity_commands = [
    ("sync", "--coordination-id", CID, "--round", "1"),
    ("stall-check", "--coordination-id", CID),
    ("report", "--coordination-id", CID, "--node", "alpha", "--state", "working"),
    ("seam", "--coordination-id", CID, "--seam-id", "integrity", "--producer", "alpha"),
    ("decide", "--coordination-id", CID, "--raise", "integrity"),
    ("act", "--coordination-id", CID, "--halt", "--source-session", NODES["controller"],
     "--reason", "integrity"),
    ("heartbeat", "--coordination-id", CID, "--node", "alpha", "--evidence", "integrity"),
    ("preflight", "--coordination-id", CID),
]
integrity_results = []
for command in integrity_commands:
    rc, out = run(*command)
    integrity_results.append(rc == 6 and "LEDGER INTEGRITY FAILED: decisions.jsonl:1 invalid_json" in out)
fails += check("所有状态推进命令遇坏行统一 rc=6 且不追加事实",
               all(integrity_results) and route_runtime_snapshot() == integrity_before,
               str(integrity_results))

# --- coordination 写锁：并发 report 追加不能丢行、交错或留下非法 JSON ---
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
concurrent = []
for index in range(24):
    concurrent.append(subprocess.Popen(
        [sys.executable, "-B", str(LEDGER), "report", "--coordination-id", CID,
         "--node", "alpha", "--state", "working", "--note", f"concurrent-{index}"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8", env=env(),
    ))
concurrent_results = [process.wait() for process in concurrent]
concurrent_rows = ledger_rows("progress.jsonl")
try:
    parsed_concurrent = [json.loads(line) for line in
                         (BROKER / CID / "progress.jsonl").read_text(encoding="utf-8").splitlines()]
except (OSError, json.JSONDecodeError):
    parsed_concurrent = []
fails += check("多进程并发追加行数精确且每行 JSON 可解析",
               all(rc == 0 for rc in concurrent_results) and len(concurrent_rows) == 24
               and len(parsed_concurrent) == 24,
               f"rcs={concurrent_results} rows={len(concurrent_rows)} parsed={len(parsed_concurrent)}")

timed_out_projection = json.dumps({"v": 1, "n": 2, "wake": None, "polls": [], "timedOut": True},
                                  ensure_ascii=False)
write_fixture(CALL_OK, timed_out_projection, git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("timedOut true 且 polls 为空时摘要标注 timeout no change",
               rc == 0 and "timedOut:        true (timeout, no change)" in out,
               out.strip())

write_fixture(CALL_OK, projection(polls=[
    {"id": UNKNOWN, "status": "notLoaded", "turn": "u", "turnStatus": "completed", "txt": "unknown"},
    {"id": NODES["beta"], "status": "notLoaded", "turn": "b", "turnStatus": "completed", "txt": "beta"},
]), git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("陌生 poll id 必须 INVALID",
               rc == 1 and "ROUND INVALID: poll id not in registry" in out,
               out.strip())

write_fixture(CALL_OK, projection(polls=[
    {"id": NODES["alpha"], "status": "notLoaded", "turn": "a1", "turnStatus": "completed", "txt": "alpha"},
    {"id": NODES["alpha"], "status": "notLoaded", "turn": "a2", "turnStatus": "completed", "txt": "alpha again"},
]), git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("重复 poll id 必须 INVALID",
               rc == 1 and "ROUND INVALID: duplicate poll id" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("decide", "--coordination-id", CID, "--answer", "missing", "--text", "no")
fails += check("decide --answer 不存在的 id 必须退出 64",
               rc == 64 and "decision is not pending: missing" in out,
               f"rc={rc} {out.strip()}")

print("-" * 78)
# --- 回归：report 不带 --head 时必须自己从 worktree 读，不得立刻被判 stale ---
# 曾经的 bug：head 缺省 -> 报告立刻 stale -> 其 waiting_on 永不计入 seams_unowned，
# 读数 5 会不管实际情况一律接近 0。head 有客观来源，不该退回"子线记得传参"的纪律。
write_fixture(CALL_OK, GOOD_PROJECTION, git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("report", "--coordination-id", CID, "--node", "alpha", "--state", "awaiting_seam",
              "--waiting-on", "seam:auto-head")
fails += check("report 省略 --head 时应自行从 worktree 读到 head",
               rc == 0 and "(worktree)" in out, out.strip())
append_wait(CALL_BETA, one_projection("beta", "auto-head-beta"), call_id="auto-head-sync")
_, sync_out = run("sync", "--coordination-id", CID, "--round", "1")
_fields = {k.strip(): v.strip() for k, _, v in
           (line.partition(":") for line in sync_out.splitlines() if ":" in line)}
fails += check("省略 --head 的 report 不得立刻被判 stale，其 waiting_on 必须计入 seams_unowned",
               _fields.get("seams_unowned") == "1" and _fields.get("stale_reports") == "-",
               sync_out.strip()[:400])

# --- 新契约：显式 registry、active child、controller H1 写入与只读 status ---
reset_fixture(git_worktrees=True)
runtime_path = BROKER / CID
before_status = {str(path.relative_to(BROKER)) for path in BROKER.rglob("*")}
rc, out = run_registry("status")
after_status = {str(path.relative_to(BROKER)) for path in BROKER.rglob("*")}
fails += check("显式 --registry 的 status 在 runtime 缺失时只读且不建目录/JSONL",
               rc == 0 and "runtime: missing" in out and before_status == after_status
               and not runtime_path.exists(), out.strip())

rc, out = run_registry("init")
fails += check("显式 --registry 的 runtime 位于 registry sibling/coordination_id",
               rc == 0 and runtime_path.is_dir() and "initialized" in out, out.strip())

registry = json.loads((BROKER / f"{CID}.json").read_text(encoding="utf-8"))
registry["children"]["historical"] = {
    "active": False,
    "topic": "retained history",
    "current_session_id": "inactive-history-session",
    "worktree": registry["children"]["alpha"]["worktree"],
    "branch": registry["children"]["alpha"]["branch"],
}
write_preflight_registry(registry)
append_wait(CALL_OK, GOOD_PROJECTION, call_id="active-only-poll")
rc, out = run_registry("sync", "--round", "1")
fails += check("poll targets 只包含 active children，inactive 历史 child 保留但不入 poll",
               rc == 0 and "valid=yes" in out and "historical" not in out,
               out.strip())

beta_head = git_head(BASE / "git" / "beta")
rc_ready, out_ready = run_registry(
    "report", "--node", "beta", "--source-session", NODES["beta"],
    "--state", "ready_for_assignment", "--head", beta_head,
)
append_wait(CALL_ALPHA, one_projection("alpha", "t-100"), call_id="ready-needs-reassignment")
rc_ready_sync, out_ready_sync = run_registry("sync", "--round", "2")
fails += check("active assignment 完成进入 reassignment_required 而不是静默终态",
               rc_ready == 0 and rc_ready_sync == 0 and "poll_targets:    alpha" in out_ready_sync
               and "reassignment_required: beta" in out_ready_sync
               and "idle_nodes:      alpha" in out_ready_sync
               and "idle_nodes:      beta" not in out_ready_sync
               and "historical" not in out_ready_sync,
               f"report={out_ready.strip()} sync={out_ready_sync.strip()}")

rc_done, out_done = run_registry(
    "report", "--node", "beta", "--source-session", NODES["beta"],
    "--state", "done", "--head", beta_head,
)
append_wait(CALL_ALPHA, one_projection("alpha", "t-101"), call_id="legacy-done-needs-reassignment")
rc_done_sync, out_done_sync = run_registry("sync", "--round", "2")
fails += check("legacy done 对 active node 兼容映射为 reassignment signal",
               rc_done == 0 and rc_done_sync == 0 and "poll_targets:    alpha" in out_done_sync
               and "reassignment_required: beta" in out_done_sync
               and "idle_nodes:      beta" not in out_done_sync,
               f"report={out_done.strip()} sync={out_done_sync.strip()}")

rc_waiting_alpha, out_waiting_alpha = run(
    "report", "--coordination-id", CID, "--node", "alpha",
    "--state", "awaiting_seam", "--waiting-on", "seam:all-waiting"
)
rc_waiting_beta, out_waiting_beta = run(
    "report", "--coordination-id", CID, "--node", "beta", "--state", "awaiting_owner"
)
append_wait(CALL_OK, GOOD_PROJECTION, call_id="all-waiting-full-poll")
rc_all_waiting, out_all_waiting = run_registry("sync", "--round", "3")
fails += check(
    "全部 child 已在 awaiting 状态时回退到全 active poll",
    rc_waiting_alpha == 0 and rc_waiting_beta == 0 and rc_all_waiting == 0
    and "poll_targets:    alpha, beta" in out_all_waiting,
    f"alpha={out_waiting_alpha.strip()} beta={out_waiting_beta.strip()} sync={out_all_waiting.strip()}",
)
rc_dispatch_waiting, out_dispatch_waiting = run_registry(
    "act", "--dispatch", "--seam-id", "all-waiting", "--producer", "alpha",
    "--deliverable", "resume alpha",
)
append_wait(CALL_ALPHA, one_projection("alpha", "resume-alpha"), call_id="resume-awaiting")
rc_resume_sync, out_resume_sync = run_registry("sync", "--round", "4")
fails += check(
    "controller dispatch 后 producer 从 awaiting_seam 回到 runnable watch-set",
    rc_dispatch_waiting == 0 and rc_resume_sync == 0 and "poll_targets:    alpha" in out_resume_sync,
    f"dispatch={out_dispatch_waiting.strip()} sync={out_resume_sync.strip()}",
)

reset_fixture(git_worktrees=True)
run_registry("init")
same_second = "2026-08-03T19:00:00+02:00"
append_ledger_row(
    "progress.jsonl",
    {
        "ts": same_second,
        "src": "report",
        "ledger_seq": 2,
        "round": 1,
        "node": "alpha",
        "head": git_head(BASE / "git" / "alpha"),
        "head_source": "worktree",
        "state": "awaiting_seam",
        "waiting_on": ["seam:same-second-order"],
        "last_report_ts": same_second,
        "note": "reported after the dispatch in the same second",
    },
)
append_ledger_row(
    "acts.jsonl",
    {
        "ts": same_second,
        "ledger_seq": 1,
        "seq": 1,
        "kind": "dispatch",
        "seam_id": "same-second-order",
        "producer": "alpha",
        "deliverable": "same-second ordering fixture",
        "decision_id": None,
    },
)
append_wait(
    call_for([NODES["beta"]]), one_projection("beta", "same-second-beta"),
    call_id="same-second-reported-after-dispatch",
)
rc_same_second, out_same_second = run_registry("sync", "--round", "1")
same_second_poll_line = next(
    (line for line in out_same_second.splitlines() if line.startswith("poll_targets:")), ""
)
same_second_poll_rows = [
    row for row in ledger_rows("progress.jsonl") if row.get("src") == "poll"
]
fails += check(
    "同秒 dispatch 早于 report 时已重新 waiting 的 producer 不进入 watch-set",
    rc_same_second == 0 and same_second_poll_line == "poll_targets:    beta"
    and same_second_poll_rows and all(row.get("ledger_seq") == 3 for row in same_second_poll_rows),
    out_same_second.strip(),
)

reset_fixture(git_worktrees=True)
run_registry("init")
idle_without_inactive_wake = projection(
    wake={"reason": "turnCompleted", "threadId": NODES["beta"], "hostId": "local"},
    polls=[
        {"id": NODES["alpha"], "status": "idle", "turn": "idle-turn",
         "turnStatus": "completed", "txt": "alpha idle"},
        {"id": NODES["beta"], "status": "running", "turn": "running-turn",
         "turnStatus": "inProgress", "txt": "beta running"},
    ],
)
append_wait(CALL_OK, idle_without_inactive_wake, call_id="idle-status-with-turn-completed")
rc, out = run_registry("sync", "--round", "1")
fails += check("poll status=idle 在非 inactiveStatus wake 下仍进入 idle_nodes",
               rc == 0 and "idle_nodes:      alpha" in out and "idle_nodes:      beta" not in out,
               out.strip())

controller_head = git_head(BASE / "git" / "controller")
rc, out = run_registry("report", "--node", "controller", "--state", "working", "--head", controller_head)
fails += check("显式 registry 允许 controller 登记自身状态且不伪装 child H1",
               rc == 0 and "reported controller state=working" in out,
               out.strip())

registry = json.loads((BROKER / f"{CID}.json").read_text(encoding="utf-8"))
registry["children"]["alpha"]["active"] = True
registry["children"]["beta"]["active"] = True
write_preflight_registry(registry)
rc, out = run_registry("report", "--node", "alpha", "--source-session", NODES["beta"],
                       "--state", "working", "--head", git_head(BASE / "git" / "alpha"))
fails += check("H1 source session 不匹配时 controller 不得写 ledger",
               rc == 64 and "source session mismatch" in out, out.strip())

alpha_head = git_head(BASE / "git" / "alpha")
rc, out = run_registry("report", "--node", "alpha", "--source-session", NODES["alpha"],
                       "--state", "working", "--head", alpha_head)
commit_file(BASE / "git" / "alpha", "h1.py", "print('h1')\n", "h1 child progress")
alpha_child_head = git_head(BASE / "git" / "alpha")
rc_descendant, out_descendant = run_registry(
    "report", "--node", "alpha", "--source-session", NODES["alpha"],
    "--state", "working", "--head", alpha_child_head,
)
rc_non_descendant, out_non_descendant = run_registry(
    "report", "--node", "alpha", "--source-session", NODES["alpha"],
    "--state", "working", "--head", "f" * 40,
)
fails += check("controller 只接受 source HEAD 的后代 H1",
               rc == 0 and rc_descendant == 0 and rc_non_descendant == 64
               and "not a descendant" in out_non_descendant,
               f"first={out.strip()} descendant={out_descendant.strip()} non_descendant={out_non_descendant.strip()}")

reset_fixture(git_worktrees=True)
rc, out = run_registry("status")
fails += check("status 显式 registry 不存在时不创建任何 runtime 文件",
               rc == 0 and "runtime_uninitialized: yes" in out
               and "runtime: missing" in out
               and not (BROKER / CID).joinpath("progress.jsonl").exists(),
               out.strip())
missing_registry = (BROKER / "missing-registry.json").resolve()
before_missing = {str(path.relative_to(BROKER)) for path in BROKER.rglob("*")}
rc, out = run("status", "--registry", str(missing_registry))
after_missing = {str(path.relative_to(BROKER)) for path in BROKER.rglob("*")}
fails += check("status registry 不存在时只报清晰错误且不创建父目录",
               rc == 1 and "registry not found" in out and before_missing == after_missing,
               out.strip())

print("-" * 78)
# --- compaction_count：controller/child rollout 首次只建基线，之后按顶层 compacted 增量计数 ---
write_fixture(CALL_OK, GOOD_PROJECTION)
append_child_compaction("controller", 1)
for node in ("alpha", "beta"):
    child_rollout_path(node).touch()
run("init", "--coordination-id", CID)
rc1, out1 = run("sync", "--coordination-id", CID, "--round", "1")
append_child_compaction("controller", 2)
append_child_compaction("alpha", 1)
append_wait(CALL_OK, GOOD_PROJECTION, call_id="compaction-round-2")
rc2, out2 = run("sync", "--coordination-id", CID, "--round", "2")
compaction_line = next(
    (line for line in out2.splitlines() if line.startswith("compaction_count:")),
    "",
)
fails += check(
    "sync 摘要同时输出 controller 与 current child 增量 compaction_count",
    rc1 == 0 and rc2 == 0 and "controller=1" in compaction_line
    and "alpha=1" in compaction_line and "beta=0" in compaction_line,
    f"round1={out1.strip()} round2={out2.strip()}",
)
state_after_compaction = json.loads(
    (BROKER / CID / "sync-state.json").read_text(encoding="utf-8")
)
alpha_observer = state_after_compaction.get("compaction_observers", {}).get(NODES["alpha"], {})
fails += check(
    "sync-state 按 session id 持久化 compaction observer",
    alpha_observer.get("observed_count") == 1
    and alpha_observer.get("last_window_id") == "alpha-window-1",
    json.dumps(alpha_observer, ensure_ascii=False),
)
rc_status, out_status = run("status", "--coordination-id", CID)
fails += check(
    "status 暴露 controller 与 current child 已持久化的 compaction_count",
    rc_status == 0 and "controller_compaction_count: 1" in out_status
    and "alpha:" in out_status and "compaction_count=1" in out_status,
    out_status.strip(),
)

print("-" * 78)
# --- session_age_h：独立构造时间、active/inactive/controller fixture ---
age_call, age_projection = make_session_age_fixture()
append_wait(age_call, age_projection, call_id="session-age")
run("init", "--coordination-id", CID)
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
age_line = next((line for line in out.splitlines() if line.startswith("session_age_h:")), "")
age_fields = {}
if age_line:
    for item in age_line.split(":", 1)[1].split(","):
        if "=" in item:
            name, value = item.split("=", 1)
            age_fields[name.strip()] = value.strip()
try:
    numeric_age_ok = (
        abs(float(age_fields["alpha"]) - 7.2) <= 0.2
        and abs(float(age_fields["beta"]) - 2.1) <= 0.2
    )
except (KeyError, TypeError, ValueError):
    numeric_age_ok = False
fails += check(
    "sync 摘要 session_age_h 数值与 updated_at 相符并按小时倒序",
    rc == 0 and list(age_fields)[:3] == ["alpha", "beta", "gamma"] and numeric_age_ok,
    out.strip(),
)
fails += check(
    "updated_at 缺失显示 ? 且 sync 正常退出",
    rc == 0 and age_fields.get("gamma") == "?",
    out.strip(),
)
fails += check(
    "session_age_h 排除 inactive child 与 controller",
    rc == 0 and "historical" not in age_fields and "controller" not in age_fields,
    age_line or out.strip(),
)

print("-" * 78)
# --- route：独立构造 registry/runtime，验证 optimistic lock、collision 与只改一个 node ---
route_path = make_route_fixture()
before_route_bytes = route_path.read_bytes()
rc, out = run(
    "route", "--registry", str(route_path), "--node", "alpha",
    "--new-session", "alpha-new-session", "--expect-current", "stale-session",
)
fails += check(
    "route --expect-current 不符退 64 且 registry 一字未改",
    rc == 64 and route_path.read_bytes() == before_route_bytes,
    f"rc={rc} {out.strip()}",
)

route_path = make_route_fixture()
before_route_bytes = route_path.read_bytes()
rc, out = run(
    "route", "--registry", str(route_path), "--node", "alpha",
    "--new-session", NODES["beta"],
)
fails += check(
    "route --new-session 撞当前 session 退 64 且 registry 一字未改",
    rc == 64 and route_path.read_bytes() == before_route_bytes,
    f"rc={rc} {out.strip()}",
)

route_path = make_route_fixture()
before_registry = json.loads(route_path.read_text(encoding="utf-8"))
before_other_bytes = route_other_registry_bytes(before_registry)
before_runtime = route_runtime_snapshot()
old_session = before_registry["children"]["alpha"]["current_session_id"]
new_session = "alpha-routed-session"
rc, out = run(
    "route", "--registry", str(route_path), "--node", "alpha",
    "--new-session", new_session, "--expect-current", old_session,
)
after_registry = json.loads(route_path.read_text(encoding="utf-8"))
alpha_after = after_registry["children"]["alpha"]
try:
    refreshed_at = datetime.fromisoformat(alpha_after["updated_at"])
    refreshed_ok = (
        refreshed_at.tzinfo is not None
        and abs((datetime.now().astimezone() - refreshed_at.astimezone()).total_seconds()) < 60
    )
except (KeyError, TypeError, ValueError):
    refreshed_ok = False
route_normal_ok = (
    rc == 0
    and out.strip() == f"ROUTED alpha {old_session} -> {new_session}"
    and alpha_after["current_session_id"] == new_session
    and old_session in alpha_after["previous_session_ids"]
    and refreshed_ok
)
fails += check(
    "route 正常路径更新 current、追加 previous 并刷新 updated_at",
    route_normal_ok,
    f"rc={rc} {out.strip()} {alpha_after}",
)
fails += check(
    "route 之后其他 node 对象逐字节序列化未变",
    route_other_registry_bytes(after_registry) == before_other_bytes,
    route_path.read_text(encoding="utf-8"),
)
fails += check(
    "route 保留 registry 未知字段",
    after_registry["context"].get("unknown_context_field") == {"keep": ["context", 7]}
    and after_registry["controller"].get("unknown_controller_field") == {"keep": True}
    and after_registry["children"]["alpha"].get("unknown_child_field") == ["preserve", {"x": 1}],
    route_path.read_text(encoding="utf-8"),
)
fails += check(
    "route 不创建也不修改 JSONL 与 sync-state.json",
    route_runtime_snapshot() == before_runtime,
    str(route_runtime_snapshot()),
)

shutil.rmtree(BASE, ignore_errors=True)
print("=" * 78)
print(f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
