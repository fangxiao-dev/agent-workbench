from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
import threading
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "codex_progress_dashboard" / "server.py"
THREAD_ID = "01a05966-5246-73e3-b46f-fd6af55fb661"


def load_module():
    spec = importlib.util.spec_from_file_location("codex_progress_dashboard_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def record(payload_type: str, *, role: str | None = None, text: str = "", phase: str | None = None, timestamp: str) -> dict:
    if payload_type == "message":
        payload = {
            "type": "message",
            "role": role,
            "phase": phase,
            "content": [{"type": "output_text", "text": text}],
        }
        kind = "response_item"
    else:
        payload = {"type": payload_type}
        kind = "event_msg"
    return {"type": kind, "timestamp": timestamp, "payload": payload}


def write_jsonl(path: Path, records: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(item) + "\n" for item in records), encoding="utf-8")


def package_binding_record(package: Path, workspace: Path, timestamp: str) -> dict:
    relative = package.relative_to(workspace).as_posix()
    return {
        "type": "response_item",
        "timestamp": timestamp,
        "payload": {
            "type": "custom_tool_call",
            "name": "exec",
            "input": f"python impl_package_state.py --package {relative} package validate",
        },
    }


def make_fixture(tmp_path: Path, *, task_name: str | None = "银行流水对账") -> tuple[Path, Path, Path, Path]:
    codex_home = tmp_path / ".codex"
    sessions = codex_home / "sessions" / "2026" / "08" / "31"
    rollout = sessions / f"rollout-{THREAD_ID}.jsonl"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    db_path = codex_home / "state_5.sqlite"
    codex_home.mkdir(exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        connection.execute(
            """
            CREATE TABLE threads (
                id TEXT PRIMARY KEY,
                name TEXT,
                title TEXT,
                updated_at INTEGER,
                updated_at_ms INTEGER,
                recency_at_ms INTEGER,
                cwd TEXT,
                rollout_path TEXT,
                git_branch TEXT,
                git_sha TEXT,
                archived INTEGER
            )
            """
        )
        connection.execute(
            """
            INSERT INTO threads
                (id, name, title, updated_at, updated_at_ms, recency_at_ms, cwd,
                 rollout_path, git_branch, git_sha, archived)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
            """,
            (
                THREAD_ID,
                task_name,
                "password=do-not-display",
                1788208868,
                1788208868000,
                1788208868000,
                str(workspace),
                str(rollout),
                "feat/test",
                "a" * 40,
            ),
        )
    return db_path, workspace, rollout, codex_home


def make_package(workspace: Path, states: dict[str, str] | None = None) -> Path:
    package = workspace / "docs" / "implementations" / "bank-reconciliation"
    state_dir = package / ".impl-package"
    ticket_dir = package / "tickets"
    state_dir.mkdir(parents=True)
    ticket_dir.mkdir()
    states = states or {"TKT-01": "PENDING"}
    state = {
        "formatVersion": "3.5",
        "attempt": {"id": "initial"},
        "attemptHistory": [{"id": "initial", "gate": None}],
        "tickets": {ticket_id: {"state": value} for ticket_id, value in states.items()},
        "activeCheckpoints": {
            "attempt": {"next": "完成预览面的独立审查。", "blocker": None}
        },
    }
    (state_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    (package / "plan.md").write_text("# 银行流水多对多对账\n", encoding="utf-8")
    (ticket_dir / "01-preview.md").write_text(
        """# 01 — 只读预览面

Ticket ID：TKT-01

## 验收标准

- **AC-1：** 页面展示 fixture 数据。
- **AC-2：** 不读取后端数据。

## 阻塞依赖

- implementation: TKT-00
""",
        encoding="utf-8",
    )
    return package


def test_task_list_excludes_unnamed_tasks_instead_of_exposing_prompt_title(tmp_path: Path) -> None:
    module = load_module()
    db_path, _, rollout, _ = make_fixture(tmp_path, task_name=None)
    write_jsonl(rollout, [])

    tasks = module.list_tasks(db_path)

    assert tasks == []
    assert "password" not in json.dumps(tasks)


def test_rollout_reader_waits_for_complete_jsonl_line(tmp_path: Path) -> None:
    module = load_module()
    _, _, rollout, _ = make_fixture(tmp_path)
    first = record(
        "message",
        role="assistant",
        phase="commentary",
        text="第一条进展",
        timestamp="2026-08-31T20:00:01Z",
    )
    second = record(
        "message",
        role="assistant",
        phase="commentary",
        text="第二条进展",
        timestamp="2026-08-31T20:00:02Z",
    )
    write_jsonl(rollout, [first])
    encoded = json.dumps(second).encode("utf-8")
    split = len(encoded) // 2
    with rollout.open("ab") as stream:
        stream.write(encoded[:split])

    reader = module.RolloutReader()
    initial = reader.read(rollout)
    assert [item["text"] for item in initial["activities"]] == ["第一条进展"]

    with rollout.open("ab") as stream:
        stream.write(encoded[split:] + b"\n")

    complete = reader.read(rollout)
    assert [item["text"] for item in complete["activities"]] == ["第二条进展", "第一条进展"]


def test_rollout_reader_keeps_only_the_latest_five_progress_items(tmp_path: Path) -> None:
    module = load_module()
    _, _, rollout, _ = make_fixture(tmp_path)
    write_jsonl(
        rollout,
        [
            record(
                "message",
                role="assistant",
                phase="commentary",
                text=f"进展 {index}",
                timestamp=f"2026-08-31T20:00:{index:02d}Z",
            )
            for index in range(7)
        ],
    )

    activities = module.RolloutReader().read(rollout)["activities"]

    assert [item["text"] for item in activities] == ["进展 6", "进展 5", "进展 4", "进展 3", "进展 2"]


def test_task_lifecycle_projects_running_waiting_and_complete(tmp_path: Path) -> None:
    module = load_module()
    _, _, rollout, _ = make_fixture(tmp_path)
    write_jsonl(
        rollout,
        [
            record("task_started", timestamp="2026-08-31T20:00:00Z"),
            record("message", role="assistant", phase="commentary", text="处理中", timestamp="2026-08-31T20:00:01Z"),
        ],
    )
    reader = module.RolloutReader()
    assert reader.read(rollout)["status"] == "进行中"

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record("message", role="user", text="继续", timestamp="2026-08-31T20:00:02Z")) + "\n")
    assert reader.read(rollout)["status"] == "等待回应"

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record("task_complete", timestamp="2026-08-31T20:00:03Z")) + "\n")
    assert reader.read(rollout)["status"] == "本轮已完成"


def test_package_discovery_prefers_paths_referenced_by_the_task(tmp_path: Path) -> None:
    module = load_module()
    _, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    other = workspace / "docs" / "implementations" / "other"
    (other / ".impl-package").mkdir(parents=True)
    (other / ".impl-package" / "state.json").write_text("{}", encoding="utf-8")
    write_jsonl(
        rollout,
        [package_binding_record(package, workspace, "2026-08-31T20:00:01Z")],
    )

    packages = module.find_packages(workspace, rollout)

    assert packages[0]["path"] == package.relative_to(workspace).as_posix()
    assert packages[0]["referenced"] is True
    assert packages[1]["referenced"] is False


def test_snapshot_separates_observed_work_from_formal_acceptance(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    relative = package.relative_to(workspace).as_posix()
    write_jsonl(
        rollout,
        [
            record("task_started", timestamp="2026-08-31T20:00:00Z"),
            record("message", role="assistant", phase="commentary", text="TKT-01 已实现，四路独立 review 进行中。", timestamp="2026-08-31T20:00:01Z"),
        ],
    )
    module.ROLLOUT_READER = module.RolloutReader()

    snapshot = module.build_snapshot(THREAD_ID, relative, db_path)

    assert snapshot["actualProgress"]["summary"] == "TKT-01 已实现，四路独立 review 进行中。"
    assert snapshot["package"]["formalSummary"] == "0/1 已正式验收"
    assert snapshot["package"]["gateLabel"] == "尚未关闭"
    assert "正式验收状态仍未关闭" in snapshot["package"]["discrepancy"]
    assert snapshot["package"]["tickets"][0]["dependencies"] == ["TKT-00"]


def test_sensitive_and_internal_rollout_payloads_never_reach_snapshot(tmp_path: Path) -> None:
    module = load_module()
    db_path, _, rollout, _ = make_fixture(tmp_path)
    records = [
        record("task_started", timestamp="2026-08-31T20:00:00Z"),
        {
            "type": "response_item",
            "timestamp": "2026-08-31T20:00:01Z",
            "payload": {"type": "function_call_output", "output": "provider payload secret=raw-value"},
        },
        record(
            "message",
            role="assistant",
            phase="commentary",
            text=r"token=raw-value at C:\Customers\private.pdf, D:/Customers/other.pdf, user@example.com and DE89370400440532013000",
            timestamp="2026-08-31T20:00:02Z",
        ),
    ]
    write_jsonl(rollout, records)
    module.ROLLOUT_READER = module.RolloutReader()

    encoded = json.dumps(module.build_snapshot(THREAD_ID, None, db_path), ensure_ascii=False)

    assert "raw-value" not in encoded
    assert "provider payload" not in encoded
    assert "private.pdf" not in encoded
    assert "other.pdf" not in encoded
    assert "user@example.com" not in encoded
    assert "DE89370400440532013000" not in encoded
    assert "已隐藏" in encoded


def test_snapshot_reflects_package_state_changes_without_restart(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    relative = package.relative_to(workspace).as_posix()
    write_jsonl(rollout, [])
    module.ROLLOUT_READER = module.RolloutReader()
    assert module.build_snapshot(THREAD_ID, relative, db_path)["package"]["formalSummary"] == "0/1 已正式验收"

    state_path = package / ".impl-package" / "state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["tickets"]["TKT-01"]["state"] = "SATISFIED"
    state_path.write_text(json.dumps(state), encoding="utf-8")

    assert module.build_snapshot(THREAD_ID, relative, db_path)["package"]["formalSummary"] == "1/1 已正式验收"


def test_snapshot_follows_latest_monitor_record_across_task_handoff(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    relative = package.relative_to(workspace).as_posix()
    write_jsonl(rollout, [])
    successor = "01a05dd3-4dd7-7032-939a-9e702ab93095"
    monitor_id = "01a05c65-2eac-7d22-aba9-c2671b2cd03d"
    other_package = workspace / "other"
    other_package.mkdir()
    for automation_id, target, bound_package, observed_at, summary in (
        ("older", THREAD_ID, package, "2026-08-31T20:00:00Z", "旧结论"),
        ("latest", successor, package, "2026-08-31T20:01:00Z", r"正常，路径 C:\private\file.txt 已隐藏"),
        ("other-task", "01a05973-673e-7102-bcb3-c40c1e3fc424", other_package, "2026-08-31T20:02:00Z", "错误任务包"),
    ):
        module.monitor_progress.init_instance(workspace, automation_id, monitor_id, target, bound_package)
        module.monitor_progress.write_evaluation(
            workspace,
            automation_id,
            {
                "targetThreadId": target,
                "observedAt": observed_at,
                "latestAssistantAt": None,
                "level": "normal",
                "summary": summary,
                "evaluation": None,
            },
        )

    monitor = module.build_snapshot(THREAD_ID, relative, db_path)["monitor"]

    assert set(monitor) == {"observedAt", "level", "summary", "monitorThreadId", "observations"}
    assert monitor["observedAt"] == "2026-08-31T20:01:00Z"
    assert "private" not in monitor["summary"]
    assert "[本地路径]" in monitor["summary"]
    assert monitor["observations"] == []


def test_snapshot_projects_monitor_evaluation_and_latest_confirmed_observations(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    relative = package.relative_to(workspace).as_posix()
    write_jsonl(rollout, [])
    automation_id = "monitor-test"
    module.monitor_progress.init_instance(
        workspace,
        automation_id,
        "01a05c65-2eac-7d22-aba9-c2671b2cd03d",
        THREAD_ID,
        package,
    )
    module.monitor_progress.write_evaluation(
        workspace,
        automation_id,
        {
            "targetThreadId": THREAD_ID,
            "observedAt": "2026-09-02T20:10:00Z",
            "latestAssistantAt": None,
            "level": "attention",
            "summary": "旧摘要",
            "evaluation": {
                "progress": r"正在核验 C:\private\review.md",
                "improvements": ["先消费独立结果", "再进入真实验收"],
                "next": "等待审查返回。",
                "owner": None,
            },
        },
    )
    for index in range(1, 7):
        module.monitor_progress.put_observation(
            workspace,
            automation_id,
            {
                "id": None,
                "topic": f"纠偏事项 {index}",
                "content": f"纠偏 {index}",
                "scope": "task",
                "state": "confirmed",
                "sourceThreadId": THREAD_ID,
                "sourceMessageId": f"msg-{index}",
                "confirmedAt": f"2026-09-02T20:0{index}:00Z",
                "response": "accepted",
                "baselineConflict": False,
            },
        )
    module.monitor_progress.put_observation(
        workspace,
        automation_id,
        {
            "id": None,
            "topic": "待确认事项",
            "content": "候选",
            "scope": "task",
            "state": "candidate",
            "sourceThreadId": THREAD_ID,
            "sourceMessageId": "candidate",
            "confirmedAt": None,
            "response": "pending",
            "baselineConflict": False,
        },
    )
    module.monitor_progress.put_observation(
        workspace,
        automation_id,
        {
            "id": None,
            "topic": "敏感内容",
            "content": r"联系 user@example.com，读取 C:\private\note.md",
            "scope": "task",
            "state": "confirmed",
            "sourceThreadId": THREAD_ID,
            "sourceMessageId": "sensitive",
            "confirmedAt": "2026-09-02T20:07:00Z",
            "response": "accepted",
            "baselineConflict": False,
        },
    )

    monitor = module.build_snapshot(THREAD_ID, relative, db_path)["monitor"]

    assert monitor["evaluation"] == {
        "progress": "正在核验 [本地路径]",
        "improvements": ["先消费独立结果", "再进入真实验收"],
        "next": "等待审查返回。",
        "owner": None,
    }
    assert len(monitor["observations"]) == 5
    assert [item["observedAt"] for item in monitor["observations"]] == [
        "2026-09-02T20:07:00Z",
        "2026-09-02T20:06:00Z",
        "2026-09-02T20:05:00Z",
        "2026-09-02T20:04:00Z",
        "2026-09-02T20:03:00Z",
    ]
    assert monitor["observations"][0]["id"] == "O008"
    assert monitor["observations"][0]["topic"] == "敏感内容"
    assert monitor["observations"][0]["content"] == "联系 [邮箱已隐藏]，读取 [本地路径]"


def test_snapshot_projects_ready_and_running_tickets_from_state_and_trail(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(
        workspace,
        {"TKT-01": "SATISFIED", "TKT-03": "PENDING", "TKT-05": "PENDING"},
    )
    ticket_dir = package / "tickets"
    for ticket_id in ("TKT-03", "TKT-05"):
        (ticket_dir / f"{ticket_id}.md").write_text(
            f"# {ticket_id}\n\nTicket ID：{ticket_id}\n\n## 阻塞依赖\n\n- implementation: TKT-01\n",
            encoding="utf-8",
        )
    trail = package / "execution" / "initial" / "trail.jsonl"
    dispatch = {
        "seq": 309,
        "kind": "dispatch",
        "subject": "ticket:TKT-03",
        "outcome": "RUNNING",
        "returned": False,
        "worker": "/root/tkt03-foundation",
    }
    write_jsonl(trail, [dispatch])
    write_jsonl(rollout, [])
    relative = package.relative_to(workspace).as_posix()

    package_snapshot = module.build_snapshot(THREAD_ID, relative, db_path)["package"]
    tickets = {ticket["id"]: ticket for ticket in package_snapshot["tickets"]}

    assert package_snapshot["readyTicketIds"] == ["TKT-03", "TKT-05"]
    assert package_snapshot["runningTicketIds"] == ["TKT-03"]
    assert package_snapshot["currentTicketId"] == "TKT-03"
    assert tickets["TKT-03"]["runtimeState"] == "RUNNING"
    assert tickets["TKT-05"]["runtimeState"] == "READY"

    write_jsonl(
        trail,
        [dispatch, {"kind": "worker-return", "subject": "ticket:TKT-03", "of": 309, "outcome": "DONE"}],
    )
    after_return = module.build_snapshot(THREAD_ID, relative, db_path)["package"]

    assert after_return["runningTicketIds"] == []
    assert after_return["currentTicketId"] == "TKT-03"


def test_snapshot_matches_slug_ticket_ids_case_insensitively(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    ticket_id = "TKT-04-canonical-runtime-real-ui"
    package = make_package(workspace, {ticket_id: "PENDING"})
    (package / "tickets" / "01-preview.md").write_text(
        f"# Canonical runtime real UI\n\nTicket ID: {ticket_id}\n",
        encoding="utf-8",
    )
    write_jsonl(rollout, [])
    relative = package.relative_to(workspace).as_posix()

    package_snapshot = module.build_snapshot(THREAD_ID, relative, db_path)["package"]
    ticket = package_snapshot["tickets"][0]

    assert package_snapshot["readyTicketIds"] == [ticket_id]
    assert ticket["runtimeState"] == "READY"
    assert ticket["name"] == "Canonical runtime real UI"


def test_http_endpoints_serve_tasks_snapshot_and_strict_csp(tmp_path: Path) -> None:
    module = load_module()
    db_path, workspace, rollout, _ = make_fixture(tmp_path)
    package = make_package(workspace)
    write_jsonl(
        rollout,
        [
            record("task_started", timestamp="2026-08-31T20:00:00Z"),
            package_binding_record(package, workspace, "2026-08-31T20:00:01Z"),
        ],
    )
    module.ROLLOUT_READER = module.RolloutReader()
    server = module.create_server(db_path, 0)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urlopen(f"{base}/api/health") as response:
            health = json.load(response)
            assert health["rendererVersion"] == 2
            assert health["monitorProgressProtocol"] == 2
            assert health["instanceId"] == "embedded"
            assert isinstance(health["pid"], int)
            assert health["startedAt"]
        with urlopen(f"{base}/api/tasks") as response:
            assert json.load(response)["tasks"][0]["id"] == THREAD_ID
        with urlopen(f"{base}/api/tasks/{THREAD_ID}/snapshot") as response:
            assert json.load(response)["task"]["status"] == "进行中"
        with urlopen(f"{base}/") as response:
            assert "default-src 'none'" in response.headers["Content-Security-Policy"]
            assert b"Codex" in response.read()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)
