"""独立核验 ledger.py：不看 codex 的自述，自己造 fixture 跑。

fixture 严格照真实 rollout 形态构造（取自 019fb7ad 主控的实际事件结构）。
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path


LEDGER = Path(__file__).with_name("ledger.py")
sys.path.insert(0, str(LEDGER.parent))
from package_adapter import read_package_facts  # noqa: E402
CID = "harness-selftest"
# PID 后缀避免并发 selftest 运行互相清理对方的 fixture（曾造成假失败）。
BASE = Path(tempfile.gettempdir()) / f"thread-harness-selftest-{os.getpid()}"
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


@dataclass(frozen=True)
class ScenarioResult:
    name: str
    failures: int

    @property
    def returncode(self) -> int:
        return 1 if self.failures else 0


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
        "broker": {
            "profile": "swarm",
            "budget": {
                "smart_zone_tokens": 150000,
                "tail_requests": 20,
                "tail_p75_increment_tokens": 1720,
            },
        },
        "context": {"topic": "selftest", "repository": "none"},
        "controller": {"node_id": "controller", "topic": "t",
                       "current_session_id": NODES["controller"],
                       "previous_session_ids": [], "worktree": worktrees["controller"], "branch": "b",
                       "updated_at": "2026-08-01T06:00:00+02:00"},
        "children": {
        "alpha": {"topic": "t", "current_session_id": NODES["alpha"],
                      "node_type": "task",
                      "previous_session_ids": [], "worktree": worktrees["alpha"], "branch": "b",
                      "updated_at": "2026-08-01T06:00:00+02:00"},
        "beta": {"topic": "t", "current_session_id": NODES["beta"],
                     "node_type": "task",
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


def make_solo_fixture():
    registry = reset_fixture(git_worktrees=True)
    registry["broker"]["profile"] = "solo"
    registry["children"].pop("beta")
    run_process(["git", "branch", "-M", "controller-b"], cwd=BASE / "git" / "controller")
    run_process(["git", "branch", "-M", "task-b"], cwd=BASE / "git" / "alpha")

    package = BASE / "git" / "alpha" / "task-package"
    (package / ".impl-package").mkdir(parents=True, exist_ok=True)
    (package / "execution" / "initial").mkdir(parents=True, exist_ok=True)
    progress = package / "progress.md"
    state = package / ".impl-package" / "state.json"
    record = package / "execution" / "initial" / "execution-record.md"
    progress.write_text("# progress\n", encoding="utf-8")
    state.write_text(json.dumps({
        "formatVersion": "3.5",
        "attempt": {"id": "initial", "plan": "plan.md"},
        "attemptHistory": [{
            "id": "initial",
            "executionRecord": "execution/initial/execution-record.md",
        }],
        "activeCheckpoints": {"attempt": {"next": "bounded action"}},
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    record.write_text("# checkpoint\n", encoding="utf-8")
    registry["controller"]["branch"] = "controller-b"
    registry["children"]["alpha"]["branch"] = "task-b"
    registry["children"]["alpha"]["node_type"] = "task"
    registry["children"]["alpha"]["package_entry"] = str(progress.resolve())
    write_preflight_registry(registry)
    rollout_path().touch()
    child_rollout_path("alpha").touch()
    return registry, package, progress, state, record


def append_child_token(node, input_tokens, *, context=200000):
    path = child_rollout_path(node)
    path.parent.mkdir(parents=True, exist_ok=True)
    event = {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "last_token_usage": {"input_tokens": input_tokens},
                "model_context_window": context,
                "total_token_usage": {"input_tokens": input_tokens * 5},
            },
        },
    }
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, ensure_ascii=False) + "\n")


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
        "broker": {
            "profile": "swarm",
            "budget": {
                "smart_zone_tokens": 150000,
                "tail_requests": 20,
                "tail_p75_increment_tokens": 1720,
            },
        },
        "controller": {
            "node_id": "controller",
            "current_session_id": sessions["controller"],
            "worktree": worktrees["controller"],
            "branch": branches["controller"],
        },
        "children": {
            name: {
                "node_type": "platform",
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




__all__ = [name for name in globals() if not name.startswith("_")]
