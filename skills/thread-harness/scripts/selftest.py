"""独立核验 ledger.py：不看 codex 的自述，自己造 fixture 跑。

fixture 严格照真实 rollout 形态构造（取自 019fb7ad 主控的实际事件结构）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
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


def call_for(ids, timeout=180000):
    quoted = ",".join(json.dumps(item) for item in ids)
    return (
        f"const ids=[{quoted}];\n"
        "const r=await tools.codex_app__wait_threads({targets:ids.map(threadId=>({threadId})),"
        f"timeoutMs:{timeout}}});\n"
        "text(JSON.stringify({v:1,n:ids.length,wake:r.wake||null,polls:(r.polls||[]).map(p=>({"
        "id:p.thread?.id,status:p.thread?.status?.type,turn:p.latestTurn?.id,"
        "turnStatus:p.latestTurn?.status,txt:(p.latestAssistantMessage?.text||\"\").slice(0,500)})),"
        "timedOut:r.timedOut}));"
    )


CALL_OK = call_for([NODES["alpha"], NODES["beta"]])
CALL_BAD_TIMEOUT = call_for([NODES["alpha"], NODES["beta"]], timeout=1000)


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


def rollout_lines(call_args, printed_text, call_id):
    return [
        {"timestamp": "2026-08-01T06:00:00.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call", "call_id": call_id, "name": "exec",
                     "arguments": call_args}},
        {"timestamp": "2026-08-01T06:00:01.000Z", "type": "response_item",
         "payload": {"type": "custom_tool_call_output", "call_id": call_id,
                     "output": [
                         {"type": "input_text", "text": "Script completed\nWall time 0.3 seconds\nOutput:\n"},
                         {"type": "input_text", "text": printed_text},
                     ]}},
    ]


def append_wait(call_args, printed_text, call_id="c1", *, dispatch_calls=0):
    roll = rollout_path()
    roll.parent.mkdir(parents=True, exist_ok=True)
    with roll.open("a", encoding="utf-8") as fh:
        for index in range(dispatch_calls):
            dispatch_call_id = f"d{call_id}{index}"
            line = {"timestamp": "2026-08-01T06:00:00.000Z", "type": "response_item",
                    "payload": {"type": "custom_tool_call", "call_id": dispatch_call_id, "name": "exec",
                                "arguments": "await tools.codex_app__send_message_to_thread({});"}}
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
            line = {"timestamp": "2026-08-01T06:00:00.100Z", "type": "response_item",
                    "payload": {"type": "custom_tool_call_output", "call_id": dispatch_call_id,
                                "output": "ok"}}
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")
        for line in rollout_lines(call_args, printed_text, call_id):
            fh.write(json.dumps(line, ensure_ascii=False) + "\n")


def write_fixture(call_args, printed_text, *, git_worktrees=False):
    reset_fixture(git_worktrees=git_worktrees)
    append_wait(call_args, printed_text)


def env():
    e = dict(os.environ)
    e["THREAD_HARNESS_SESSIONS_ROOT"] = str(FAKE_SESSIONS)
    e["THREAD_HARNESS_BROKER_ROOT"] = str(BROKER)
    return e


def run(*args):
    p = subprocess.run([sys.executable, "-B", str(LEDGER), *args],
                       capture_output=True, text=True, encoding="utf-8", env=env())
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def ledger_rows(name):
    path = BROKER / CID / name
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


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
    ("timeoutMs 被调低必须被拦下", CALL_BAD_TIMEOUT, GOOD_PROJECTION, 1, "1000 < 180000"),
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
    ("解析不出 ids 数组必须被拦下", 'const targets=[]; await tools.codex_app__wait_threads({targets,timeoutMs:180000});',
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
append_wait(CALL_OK, projection(alpha_turn="t-101", beta_turn="t-201"), call_id="c2")
rc, out = run("sync", "--coordination-id", CID, "--round", "2")
fails += check("report 的 state/waiting_on 不被后续 sync 覆盖",
               rc == 0 and "seams_unowned:   2" in out and "never_reported:  beta" in out,
               out.strip())

rc, out = run("seam", "--coordination-id", CID, "--seam-id", "x", "--producer", "alpha",
              "--consumers", "beta", "controller")
fails += check("seam 支持 --consumers 空格分隔且允许 registry 中的 controller",
               rc == 0, out.strip())
rc, out = run("seam", "--coordination-id", CID, "--seam-id", "bad", "--producer", "typo",
              "--consumers", "beta")
fails += check("seam producer 拼错必须失败", rc == 1 and "unknown producer node: typo" in out, out.strip())
rc, out = run("seam", "--coordination-id", CID, "--seam-id", "bad", "--producer", "alpha",
              "--consumers", "typo")
fails += check("seam consumer 拼错必须失败", rc == 1 and "unknown consumer node: typo" in out, out.strip())

print("-" * 78)
write_fixture(CALL_OK, projection(alpha_turn="t-1", beta_turn="t-1"), git_worktrees=True)
run("init", "--coordination-id", CID)
for round_no in range(1, 5):
    if round_no > 1:
        append_wait(CALL_OK, projection(alpha_turn=f"t-{round_no}", beta_turn=f"t-{round_no}"),
                    call_id=f"stall{round_no}", dispatch_calls=1)
    run("sync", "--coordination-id", CID, "--round", str(round_no))
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("turn 变化但 git head 不变时 stall-check 连续 3 轮后退出 2",
               rc == 2 and "MUST_ACT stall_streak=3/3" in out and "dispatches_since_progress=3" in out,
               out.strip())

# --- 回归：git HEAD 真推进后必须归零（否则会常态误报 MUST_ACT）---
subprocess.run(["git", "-C", str(BASE / "git" / "alpha"), "commit", "--allow-empty", "-q",
                "-m", "real work"], check=True)
append_wait(CALL_OK, projection(alpha_turn="t-9", beta_turn="t-9"), call_id="prog9")
run("sync", "--coordination-id", CID, "--round", "9")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("git head 真推进后 stall_streak 必须归零",
               rc == 0 and "stall_streak=0/3" in out, out.strip())

# --- 回归：head 取不到时必须 fail-closed，继续累计停滞 ---
# 曾经的 bug：任一 head 为 None 就把 streak 清零，导致一条线的 worktree 路径写错
# 就永久关掉整组的停滞检测，而且完全无声。无法确认有推进 = 没有推进。
shutil.rmtree(BASE / "git" / "alpha", ignore_errors=True)
sync_out = ""
for round_no in range(10, 14):
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
fails += check("decide --answer 后无 pending 且未达阈值时退出 0", rc == 0 and out.startswith("OK "), out.strip())

print("-" * 78)
write_fixture(CALL_OK, GOOD_PROJECTION, git_worktrees=True)
run("init", "--coordination-id", CID)
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("stall-check 无停滞时退出 0", rc == 0 and out.startswith("OK "), out.strip())
rc, out = run("sync", "--coordination-id", CID, "--round", "1", "--no-such-arg")
fails += check("usage error 退出码 64", rc == 64, f"rc={rc} {out.strip()}")

print("-" * 78)
reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
for index in range(4):
    append_wait(CALL_OK, projection(alpha_turn=f"same-{index}", beta_turn=f"same-{index}"),
                call_id=f"sameround{index}", dispatch_calls=1 if index else 0)
    run("sync", "--coordination-id", CID, "--round", "7")
rc, out = run("stall-check", "--coordination-id", CID)
fails += check("同一个 --round 重复 4 次时 stall_streak 仍按 append 顺序累计到 3",
               rc == 2 and "MUST_ACT stall_streak=3/3" in out,
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
append_wait(CALL_OK, projection(alpha_turn="stale-a", beta_turn="stale-b"), call_id="stale")
rc, out = run("sync", "--coordination-id", CID, "--round", "8")
fails += check("report 之后 HEAD 变化必须暴露 stale_reports",
               rc == 0 and "stale_reports:" in out and "alpha" in out,
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
rc_act, out_act = run("act", "--coordination-id", CID, "--dispatch", "--seam-id", "s9",
                      "--producer", "alpha", "--deliverable", "x")
rc_after, out_after = run("status", "--coordination-id", CID)
seam_rows = ledger_rows("seams.jsonl")
fails += check("act --dispatch 同步形成 seam ownership，s9 不再无主",
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
append_wait(CALL_OK, projection(alpha_turn="r2b-a", beta_turn="r2b-b"), call_id="r2b")
rc, out = run("sync", "--coordination-id", CID, "--round", "1")
fails += check("stale awaiting_seam 的 waiting_on 不计入 seams_unowned 并计入 stale_waiting_on",
               rc == 0 and "stale_reports:" in out and "alpha" in out
               and "seams_unowned:   0" in out and "stale_waiting_on: 1" in out,
               out.strip())

reset_fixture(git_worktrees=True)
run("init", "--coordination-id", CID)
for index in range(4):
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
               rc == 0 and "corrupt_ledger_lines: 1" in out,
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
_, sync_out = run("sync", "--coordination-id", CID, "--round", "1")
_fields = {k.strip(): v.strip() for k, _, v in
           (line.partition(":") for line in sync_out.splitlines() if ":" in line)}
fails += check("省略 --head 的 report 不得立刻被判 stale，其 waiting_on 必须计入 seams_unowned",
               _fields.get("seams_unowned") == "1" and _fields.get("stale_reports") == "-",
               sync_out.strip()[:400])

shutil.rmtree(BASE, ignore_errors=True)
print("=" * 78)
print(f"FAILURES: {fails}")
sys.exit(1 if fails else 0)
