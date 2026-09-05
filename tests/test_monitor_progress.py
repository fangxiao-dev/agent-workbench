from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sqlite3
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "monitor_progress.py"
THREAD_A = "01a05c65-2eac-7d22-aba9-c2671b2cd03d"
THREAD_B = "01a061c1-2bd2-7982-a497-23ee67c5f62f"
THREAD_C = "01a06b92-3e4e-7b62-b921-da7d3493230b"


def load_module():
    spec = importlib.util.spec_from_file_location("monitor_progress", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_instance(tmp_path: Path):
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    instance = module.init_instance(root, "monitor-test", THREAD_A, THREAD_B, package)
    return module, root, package, instance


def evaluation_payload() -> dict:
    return {
        "targetThreadId": THREAD_B,
        "observedAt": "2026-09-02T20:00:00Z",
        "latestAssistantAt": None,
        "level": "attention",
        "summary": "正在收口；Owner 暂无待决事项。",
        "evaluation": {
            "progress": "实现已完成，正在独立复核。",
            "improvements": ["先消费复核结果。", "再进入真实验收。"],
            "next": "等待复核返回。",
            "owner": None,
        },
    }


def baseline() -> dict:
    return {
        "goal": "完成示例任务包。",
        "chosenDirection": ["沿用现有实现。"],
        "coreInvariants": ["保持原子写入。"],
        "nonGoals": ["不发布。"],
        "requiredEvidence": ["focused tests。"],
        "requiredReviews": ["implementation review。"],
        "manualAcceptance": ["Owner 浏览器验收。"],
        "ownerDecisionBoundary": "只有真实产品分叉需要 Owner。",
    }


def make_context(tmp_path: Path):
    module, root, package, instance = make_instance(tmp_path)
    context = module.init_context(
        root,
        "monitor-test",
        {"targetTitle": "示例任务", "targetBaseline": baseline()},
    )
    return module, root, package, instance, context


def write_package_state(package: Path, tickets: dict[str, dict], gate=None) -> None:
    state_dir = package / ".impl-package"
    state_dir.mkdir(exist_ok=True)
    (state_dir / "state.json").write_text(
        json.dumps(
            {
                "attempt": {"id": "initial"},
                "attemptHistory": [{"id": "initial", "gate": gate}],
                "tickets": tickets,
            }
        ),
        encoding="utf-8",
    )


def make_codex_store(tmp_path: Path) -> tuple[Path, dict[str, Path]]:
    codex = tmp_path / ".codex"
    sessions = codex / "sessions" / "2026" / "09" / "03"
    sessions.mkdir(parents=True)
    rollouts = {THREAD_A: sessions / "monitor.jsonl", THREAD_B: sessions / "target.jsonl"}
    for path in rollouts.values():
        path.write_text("", encoding="utf-8")
    database = codex / "state_5.sqlite"
    with sqlite3.connect(database) as connection:
        connection.execute(
            "CREATE TABLE threads (id TEXT PRIMARY KEY, rollout_path TEXT, archived INTEGER, title TEXT, name TEXT)"
        )
        connection.executemany(
            "INSERT INTO threads (id, rollout_path, archived, title, name) VALUES (?, ?, 0, ?, ?)",
            [
                (thread_id, str(path), "Preview", f"Task {thread_id[-4:]}")
                for thread_id, path in rollouts.items()
            ],
        )
    return database, rollouts


def rollout_user(message_id: str, turn_id: str, text: str, *, newline: bool = True) -> bytes:
    record = {
        "timestamp": "2026-09-03T07:38:04.657Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "user",
            "id": message_id,
            "content": [{"type": "input_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
        },
    }
    return json.dumps(record, ensure_ascii=False).encode("utf-8") + (b"\n" if newline else b"")


def rollout_assistant(message_id: str, turn_id: str, text: str) -> bytes:
    record = {
        "timestamp": "2026-09-03T07:39:04.657Z",
        "type": "response_item",
        "payload": {
            "type": "message",
            "role": "assistant",
            "id": message_id,
            "content": [{"type": "output_text", "text": text}],
            "internal_chat_message_metadata_passthrough": {"turn_id": turn_id},
        },
    }
    return json.dumps(record, ensure_ascii=False).encode("utf-8") + b"\n"


def observation(
    state: str = "candidate",
    confirmed_at=None,
    *,
    observation_id=None,
    topic: str = "容量边界与性能验收",
    content: str = "不要把容量边界误作硬性验收标准。",
    kind: str = "pattern",
) -> dict:
    return {
        "id": observation_id,
        "kind": kind,
        "topic": topic,
        "content": content,
        "scope": "task",
        "state": state,
        "sourceThreadId": THREAD_B,
        "sourceMessageId": "msg-1",
        "confirmedAt": confirmed_at,
        "response": "pending",
        "baselineConflict": False,
    }


def test_init_and_write_evaluation_use_v2_contract(tmp_path: Path) -> None:
    module, root, package, instance = make_instance(tmp_path)

    assert instance["monitor"]["version"] == 2
    assert instance["monitor"]["packagePath"] == str(package.resolve())
    assert instance["monitor"]["evaluation"] is None
    assert instance["observations"] == []
    observation_path = root / ".progress-record" / "codex-progress-dashboard" / "observations" / "monitor-test.json"
    assert json.loads(observation_path.read_text(encoding="utf-8"))["nextObservationNumber"] == 1

    updated = module.write_evaluation(root, "monitor-test", evaluation_payload())

    assert updated["evaluation"]["owner"] is None
    assert module.read_instance(root, "monitor-test")["monitor"] == updated


def test_contract_rejects_unknown_fields_and_v1(tmp_path: Path) -> None:
    module, root, _, _ = make_instance(tmp_path)
    payload = evaluation_payload()
    payload["extra"] = True

    with pytest.raises(module.MonitorProgressError, match="unknown"):
        module.write_evaluation(root, "monitor-test", payload)

    monitor_path = root / ".progress-record" / "codex-progress-dashboard" / "monitors" / "monitor-test.json"
    monitor = json.loads(monitor_path.read_text(encoding="utf-8"))
    monitor["version"] = 1
    monitor_path.write_text(json.dumps(monitor), encoding="utf-8")
    with pytest.raises(module.MonitorProgressError, match="version must be 2"):
        module.read_instance(root, "monitor-test")


def test_context_is_idempotent_and_read_returns_complete_snapshot(tmp_path: Path) -> None:
    module, root, _, _, created = make_context(tmp_path)

    repeated = module.init_context(
        root,
        "monitor-test",
        {"targetTitle": "示例任务", "targetBaseline": baseline()},
    )
    result = module.read_context(root, "monitor-test")

    assert repeated == created
    assert result["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V20"
    assert len(result["context"]["snapshotHash"]) == 64
    assert result["context"]["runtimeState"]["lastFallbackTurnId"] is None
    assert result["context"]["runtimeState"]["lastSimulationCorrection"] is None
    assert result["context"]["policySnapshot"]["visibility"].startswith("read_thread")
    assert "fallback" not in result["context"]["policySnapshot"]
    policy_text = json.dumps(result["context"]["policySnapshot"], ensure_ascii=False)
    assert "工具调试，不写入目标任务 sidecar" in policy_text
    assert "同批前序消息、当前完整 observations 与 task 状态" in policy_text
    assert "先消解 antecedent、主体、动作和范围" in policy_text
    assert "不得把上下文中的局部对象扩大为整个类别" in policy_text
    assert "指代无法确认时不覆盖 confirmed observation" in policy_text
    assert "observationDiff 非空时由 write-cycle 按 ID 稳定排序" in policy_text
    assert "write-cycle.notification 是用户可见报告格式的唯一来源" in policy_text
    assert "observations 归属于被监控 package" in policy_text
    assert "packageStatus" in policy_text
    assert "一个 observation topic 只承载一个" in policy_text
    assert "实例替换测试" in policy_text
    assert "先服从 Owner 明示范围" in policy_text
    assert "一次性决策时 kind=one-time" in policy_text
    assert "不得靠改写正文将其泛化" in policy_text
    assert "kind=pattern" in policy_text
    assert "模拟纠偏：无" in policy_text
    assert "Grok" not in policy_text
    assert "默认只写当前做到哪里" in policy_text
    assert "evaluation.progress 写 target 当前事实" in policy_text
    assert "必须处理的问题不得写入 improvements" in policy_text
    assert "不采纳也不影响当前 Ticket/Gate 收口" in policy_text
    assert "不创造当前问题等未定义栏目" in policy_text
    assert "独立监控健康告警" in policy_text
    assert "状态本身不证明 blocker" in policy_text
    assert "讨论、澄清、问答或等待 Owner 回复时不得发送" in policy_text
    assert result["observations"] == []
    stored_context = json.loads(
        (root / ".progress-record" / "codex-progress-dashboard" / "contexts" / "monitor-test.json").read_text(
            encoding="utf-8"
        )
    )
    assert "runtimeState" not in stored_context

    static = module.read_static(root, "monitor-test")
    cycle = module.read_cycle(root, "monitor-test")
    assert "runtimeState" not in static["staticContext"]
    assert "policySnapshot" not in cycle["staticRef"]
    assert "targetBaseline" not in cycle["staticRef"]
    assert cycle["runtimeState"] == result["context"]["runtimeState"]
    assert cycle["observations"] == []
    assert cycle["observationDiff"] == []
    assert cycle["staticRef"]["status"] == "current"


def test_contextual_observation_policy_is_generic_and_scope_preserving() -> None:
    module = load_module()
    policy_text = json.dumps(module.POLICY_SNAPSHOT, ensure_ascii=False)
    task_specific_example = (
        "standing subagent 监控 Grok",
        "让 subagent 完成一个上报一个",
    )

    for marker in (
        "按 source、turn 和时间顺序",
        "同批前序消息",
        "当前完整 observations",
        "antecedent、主体、动作和范围",
        "局部对象扩大为整个类别",
        "指代无法确认时不覆盖 confirmed observation",
    ):
        assert marker in policy_text
    assert all(example not in policy_text for example in task_specific_example)


def test_refresh_context_policy_preserves_dynamic_state(tmp_path: Path) -> None:
    module, root, _, _, created = make_context(tmp_path)
    confirmed = observation("confirmed", "2026-09-02T20:01:00Z")
    module.put_observation(root, "monitor-test", confirmed)
    module.write_cycle(
        root,
        "monitor-test",
        {**evaluation_payload(), "runtimeState": created["context"]["runtimeState"]},
    )
    before = module.read_context(root, "monitor-test")
    old_policy = {"fallback": {"localAuthorization": "旧任务级授权"}}
    stale = {
        **before["context"],
        "version": 1,
        "policyVersion": "STATIC_MONITOR_POLICY_V3",
        "policySnapshot": old_policy,
        "snapshotHash": module._snapshot_hash(
            before["context"]["targetBaseline"], "STATIC_MONITOR_POLICY_V3", old_policy
        ),
    }
    context_path = root / ".progress-record" / "codex-progress-dashboard" / "contexts" / "monitor-test.json"
    context_path.write_text(json.dumps(stale), encoding="utf-8")

    with pytest.raises(module.MonitorProgressError, match="fields mismatch|does not match"):
        module.read_context(root, "monitor-test")
    refreshed = module.refresh_context_policy(root, "monitor-test")
    repeated = module.refresh_context_policy(root, "monitor-test")

    assert refreshed == repeated
    assert refreshed["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V20"
    assert refreshed["context"]["targetBaseline"] == before["context"]["targetBaseline"]
    assert refreshed["context"]["runtimeState"] == before["context"]["runtimeState"]
    assert refreshed["monitor"] == before["monitor"]
    assert [item["id"] for item in refreshed["observations"]] == ["O001"]


def test_refresh_context_policy_migrates_v5_runtime(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    legacy["version"] = 5
    legacy["runtimeState"].pop("monitorHealthState")
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    refreshed = module.refresh_context_policy(root, "monitor-test")

    assert json.loads(runtime_path.read_text(encoding="utf-8"))["version"] == 7
    assert refreshed["context"]["runtimeState"]["monitorHealthState"] is None


def test_context_rejects_snapshot_conflict_unknown_field_and_hash_damage(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)

    changed = baseline()
    changed["goal"] = "另一个目标。"
    with pytest.raises(module.MonitorProgressError, match="does not match"):
        module.init_context(root, "monitor-test", {"targetTitle": "示例任务", "targetBaseline": changed})
    with pytest.raises(module.MonitorProgressError, match="unknown"):
        module.init_context(
            root,
            "monitor-test",
            {"targetTitle": "示例任务", "targetBaseline": baseline(), "extra": True},
        )

    context_path = root / ".progress-record" / "codex-progress-dashboard" / "contexts" / "monitor-test.json"
    damaged = json.loads(context_path.read_text(encoding="utf-8"))
    damaged["snapshotHash"] = "0" * 64
    context_path.write_text(json.dumps(damaged), encoding="utf-8")
    with pytest.raises(module.MonitorProgressError, match="hash mismatch"):
        module.read_context(root, "monitor-test")


def test_write_cycle_updates_runtime_and_evaluation(tmp_path: Path) -> None:
    module, root, _, _, created = make_context(tmp_path)
    context_path = root / ".progress-record" / "codex-progress-dashboard" / "contexts" / "monitor-test.json"
    fixed_before = context_path.read_bytes()
    runtime = created["context"]["runtimeState"]
    runtime = {
        **runtime,
        "lastTargetStatus": "idle",
        "lastTargetTurnId": THREAD_B,
        "lastFallbackTurnId": THREAD_B,
        "lastFallbackAt": "2026-09-02T20:02:00Z",
        "lastSimulationCorrection": {
            "reason": "目标因已授权的本地环境停住。",
            "message": "请使用已有本地授权继续。",
        },
    }

    updated = module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})

    assert updated["monitor"]["evaluation"]["next"] == "等待复核返回。"
    assert updated["context"]["runtimeState"]["lastFallbackTurnId"] == THREAD_B
    assert updated["context"]["runtimeState"]["lastSimulationCorrection"]["message"] == "请使用已有本地授权继续。"
    assert updated["notification"]["shouldNotify"] is True
    assert "**模拟纠偏：**触发（未发送）" in updated["notification"]["reportText"]
    assert context_path.read_bytes() == fixed_before
    assert module.read_context(root, "monitor-test") == {
        key: updated[key] for key in ("context", "monitor", "observations")
    }


def test_notification_has_one_deterministic_layout() -> None:
    module = load_module()
    evaluation = evaluation_payload()["evaluation"]
    cycle = {
        "packageDiff": None,
        "observationDiff": [],
        "rendererDiff": None,
        "monitorHealthDiff": None,
        "rendererStatus": module._missing_renderer_state(),
        "monitorHealthStatus": {
            "status": "healthy",
            "targetThreadId": THREAD_B,
            "successorThreadId": None,
            "rendererStatus": "alive",
        },
    }

    notification = module._notification(
        {"evaluation": None},
        {"evaluation": evaluation},
        {"lastSimulationCorrection": None},
        {"lastSimulationCorrection": None},
        cycle,
    )

    assert notification == {
        "shouldNotify": True,
        "reportText": (
            "**当前进展：**实现已完成，正在独立复核。\n\n"
            "**可改进：**\n"
            "- 先消费复核结果。\n"
            "- 再进入真实验收。\n\n"
            "**下一步：**等待复核返回。\n\n"
            "**需要 Owner：**无\n\n"
            "**模拟纠偏：**无"
        ),
    }

    quiet = module._notification(
        {"evaluation": evaluation},
        {"evaluation": evaluation},
        {"lastSimulationCorrection": None},
        {"lastSimulationCorrection": None},
        cycle,
    )
    assert quiet == {"shouldNotify": False, "reportText": "DONT_NOTIFY"}

    without_improvements = {**evaluation, "improvements": [], "owner": "确认是否接受风险。"}
    compact = module._notification(
        {"evaluation": evaluation},
        {"evaluation": without_improvements},
        {"lastSimulationCorrection": None},
        {"lastSimulationCorrection": None},
        cycle,
    )["reportText"]
    assert "可改进" not in compact
    assert "**需要 Owner：**确认是否接受风险。" in compact


def test_write_cycle_returns_dont_notify_after_all_changes_are_acknowledged(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    first = module.read_cycle(root, "monitor-test")
    runtime = json.loads(json.dumps(first["runtimeState"]))
    runtime["rendererState"] = first["rendererStatus"]
    runtime["monitorHealthState"] = first["monitorHealthStatus"]

    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})
    second = module.read_cycle(root, "monitor-test")
    runtime = json.loads(json.dumps(second["runtimeState"]))
    runtime["rendererState"] = second["rendererStatus"]
    runtime["monitorHealthState"] = second["monitorHealthStatus"]
    result = module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})

    assert result["notification"] == {"shouldNotify": False, "reportText": "DONT_NOTIFY"}


def test_notification_sorts_and_renders_observation_changes() -> None:
    module = load_module()
    evaluation = evaluation_payload()["evaluation"]
    before = observation(
        observation_id="O001",
        topic="旧规则",
        content="旧内容。",
        kind="one-time",
    )
    after = {**before, "topic": "新规则", "content": "新内容。", "kind": "pattern"}
    created = observation(observation_id="O002", topic="新增规则", content="新增内容。")
    removed = observation(observation_id="O003", topic="删除规则", content="删除内容。")
    cycle = {
        "packageDiff": None,
        "observationDiff": [
            {"change": "removed", "id": "O003", "before": removed, "after": None},
            {"change": "created", "before": None, "after": created, "observation": created},
            {"change": "updated", "before": before, "after": after, "observation": after},
        ],
        "rendererDiff": None,
        "monitorHealthDiff": None,
        "rendererStatus": module._missing_renderer_state(),
        "monitorHealthStatus": {
            "status": "healthy",
            "targetThreadId": THREAD_B,
            "successorThreadId": None,
            "rendererStatus": "alive",
        },
    }

    report = module._notification(
        {"evaluation": evaluation},
        {"evaluation": evaluation},
        {"lastSimulationCorrection": None},
        {"lastSimulationCorrection": None},
        cycle,
    )["reportText"]

    assert report.index("更新 O001") < report.index("新增 O002") < report.index("删除 O003")
    assert "之前：O001｜one-time｜旧规则：旧内容。" in report
    assert "之后：O001｜pattern｜新规则：新内容。" in report
    assert "当前全文：新内容。" in report
    assert report.endswith("**模拟纠偏：**无")


def test_notification_renders_new_simulation_and_health_change() -> None:
    module = load_module()
    evaluation = evaluation_payload()["evaluation"]
    simulation = {"reason": "目标被授权问题阻塞。", "message": "使用已有授权继续。"}
    renderer = {
        "status": "dead",
        "pid": 2468,
        "port": 43187,
        "instanceId": "renderer-test",
        "startedAt": "2026-09-05T08:00:00Z",
        "health": False,
    }
    cycle = {
        "packageDiff": None,
        "observationDiff": [],
        "rendererDiff": {"previous": module._missing_renderer_state(), "current": renderer},
        "monitorHealthDiff": {
            "previous": None,
            "current": {
                "status": "renderer-abnormal",
                "targetThreadId": THREAD_B,
                "successorThreadId": None,
                "rendererStatus": "dead",
            },
        },
        "rendererStatus": renderer,
        "monitorHealthStatus": {
            "status": "renderer-abnormal",
            "targetThreadId": THREAD_B,
            "successorThreadId": None,
            "rendererStatus": "dead",
        },
    }

    report = module._notification(
        {"evaluation": evaluation},
        {"evaluation": evaluation},
        {"lastSimulationCorrection": None},
        {"lastSimulationCorrection": simulation},
        cycle,
    )["reportText"]

    assert "**模拟纠偏：**触发（未发送）\n- 原因：目标被授权问题阻塞。\n- 拟发送：使用已有授权继续。" in report
    assert report.endswith(
        "**监控健康：**Renderer 已停止（PID 2468，127.0.0.1:43187），进度页面不可用；未自动重启。"
    )


def test_write_cycle_rolls_back_when_monitor_write_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, _, _, created = make_context(tmp_path)
    monitor_path = root / ".progress-record" / "codex-progress-dashboard" / "monitors" / "monitor-test.json"
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    monitor_before = monitor_path.read_bytes()
    runtime_before = runtime_path.read_bytes()
    original_write = module._atomic_write
    calls = 0

    def fail_second(path: Path, value: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("replace failed")
        original_write(path, value)

    monkeypatch.setattr(module, "_atomic_write", fail_second)

    with pytest.raises(OSError, match="replace failed"):
        module.write_cycle(
            root,
            "monitor-test",
            {**evaluation_payload(), "runtimeState": created["context"]["runtimeState"]},
        )

    assert monitor_path.read_bytes() == monitor_before
    assert runtime_path.read_bytes() == runtime_before


def test_read_cycle_recovers_canonical_owner_inputs_and_commits_cursor(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    child = rollouts[THREAD_B].with_name("child.jsonl")
    child.write_bytes(rollout_user("msg-child", THREAD_B, "继承副本不应出现"))
    seeded = module.seed_rollout_cursors(root, "monitor-test", database)
    assert seeded["ownerInputs"] == {"monitor": [], "target": []}

    with rollouts[THREAD_B].open("ab") as stream:
        stream.write(rollout_user("msg-owner", THREAD_B, "新小 fix 去独立 worktree，不要阻塞。"))
        stream.write(rollout_assistant("msg-progress", THREAD_B, "TKT-12 已正式 SATISFIED。"))
        stream.write(rollout_user("msg-heartbeat", THREAD_B, "<heartbeat>scheduled input</heartbeat>"))

    first = module.read_cycle(root, "monitor-test", database)
    assert [item["messageId"] for item in first["ownerInputs"]["target"]] == ["msg-owner"]
    assert first["ownerInputs"]["target"][0]["text"].startswith("新小 fix")
    assert [item["messageId"] for item in first["targetUpdates"]] == ["msg-progress"]
    assert first["targetUpdates"][0]["text"] == "TKT-12 已正式 SATISFIED。"
    assert module.read_cycle(root, "monitor-test", database)["ownerInputs"] == first["ownerInputs"]

    runtime = first["runtimeState"]
    for source, cursor in first["nextRolloutCursors"].items():
        runtime["sourceScanState"][source].update(
            {"rolloutOffset": cursor["rolloutOffset"], "rolloutPathHash": cursor["rolloutPathHash"]}
        )
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})
    assert module.read_cycle(root, "monitor-test", database)["ownerInputs"] == {"monitor": [], "target": []}
    assert module.read_cycle(root, "monitor-test", database)["targetUpdates"] == []


def test_package_status_is_authoritative_and_diff_is_acknowledged_once(tmp_path: Path) -> None:
    module, root, package, _ = make_instance(tmp_path)
    write_package_state(package, {"TKT-09": {"state": "PENDING"}, "TKT-12": {"state": "PENDING"}})
    module.init_context(root, "monitor-test", {"targetTitle": "示例任务", "targetBaseline": baseline()})
    database, rollouts = make_codex_store(tmp_path)
    module.seed_rollout_cursors(root, "monitor-test", database)
    with rollouts[THREAD_B].open("ab") as stream:
        stream.write(rollout_assistant("msg-reviewing", THREAD_B, "TKT-12 仍在审查。"))
    write_package_state(
        package,
        {
            "TKT-09": {"state": "PENDING"},
            "TKT-12": {"state": "SATISFIED", "acceptance": {"revision": "abc123"}},
        },
    )

    cycle = module.read_cycle(root, "monitor-test", database)

    assert cycle["targetUpdates"][0]["text"] == "TKT-12 仍在审查。"
    assert cycle["packageStatus"]["tickets"]["TKT-12"] == {
        "state": "SATISFIED",
        "acceptanceRevision": "abc123",
    }
    assert cycle["packageDiff"]["ticketChanges"] == [
        {
            "id": "TKT-12",
            "before": {"state": "PENDING", "acceptanceRevision": None},
            "after": {"state": "SATISFIED", "acceptanceRevision": "abc123"},
        }
    ]

    runtime = cycle["runtimeState"]
    for source, cursor in cycle["nextRolloutCursors"].items():
        runtime["sourceScanState"][source].update(
            {"rolloutOffset": cursor["rolloutOffset"], "rolloutPathHash": cursor["rolloutPathHash"]}
        )
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})
    repeated = module.read_cycle(root, "monitor-test", database)
    assert repeated["packageDiff"] is None
    assert repeated["targetUpdates"] == []


def test_read_cycle_exposes_renderer_ticket_presentation(tmp_path: Path) -> None:
    module, root, package, _, _ = make_context(tmp_path)
    write_package_state(package, {"TKT-13": {"state": "PENDING"}})
    trail = package / "execution" / "initial" / "trail.jsonl"
    trail.parent.mkdir(parents=True)
    trail.write_text(
        json.dumps(
            {
                "kind": "dispatch",
                "outcome": "RUNNING",
                "returned": False,
                "seq": 1,
                "subject": "ticket:TKT-13",
                "worker": "tkt13_backend",
            }
        )
        + "\n",
        encoding="utf-8",
    )
    database, _ = make_codex_store(tmp_path)
    module.seed_rollout_cursors(root, "monitor-test", database)

    cycle = module.read_cycle(root, "monitor-test", database)

    assert cycle["ticketPresentation"] == {
        "status": "current",
        "readyTicketIds": ["TKT-13"],
        "runningTicketIds": ["TKT-13"],
        "tickets": {
            "TKT-13": {
                "formalState": "PENDING",
                "runtimeState": "DEVELOPING",
                "label": "开发中",
            }
        },
    }


def test_rollout_partial_line_and_reset_are_explicit(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    module.seed_rollout_cursors(root, "monitor-test", database)
    partial = rollout_user("msg-partial", THREAD_B, "尚未写完", newline=False)
    rollouts[THREAD_B].write_bytes(partial)

    partial_cycle = module.read_cycle(root, "monitor-test", database)
    assert partial_cycle["ownerInputs"]["target"] == []
    assert partial_cycle["nextRolloutCursors"]["target"]["rolloutOffset"] == 0

    with rollouts[THREAD_B].open("ab") as stream:
        stream.write(b"\n")
    complete = module.read_cycle(root, "monitor-test", database)
    assert complete["ownerInputs"]["target"][0]["messageId"] == "msg-partial"

    module.seed_rollout_cursors(root, "monitor-test", database)
    rollouts[THREAD_B].write_bytes(b"")
    reset = module.read_cycle(root, "monitor-test", database)["nextRolloutCursors"]["target"]
    assert reset["reset"] is True
    assert reset["rolloutOffset"] == 0

    switched = rollouts[THREAD_B].with_name("target-switched.jsonl")
    switched.write_bytes(rollout_user("msg-switched", THREAD_B, "切换后的新消息"))
    with sqlite3.connect(database) as connection:
        connection.execute("UPDATE threads SET rollout_path = ? WHERE id = ?", (str(switched), THREAD_B))
    switched_cycle = module.read_cycle(root, "monitor-test", database)
    assert switched_cycle["nextRolloutCursors"]["target"]["reset"] is True
    assert switched_cycle["ownerInputs"]["target"][0]["messageId"] == "msg-switched"


def test_read_cycle_reports_explicit_handoff_as_monitor_health_diff(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    module.seed_rollout_cursors(root, "monitor-test", database)
    with rollouts[THREAD_B].open("ab") as stream:
        stream.write(
            rollout_assistant(
                "msg-handoff",
                THREAD_B,
                f'继续由新任务处理。\n\n::created-thread{{threadId="{THREAD_C}"}}',
            )
        )

    cycle = module.read_cycle(root, "monitor-test", database)

    assert cycle["monitorHealthStatus"] == {
        "status": "retarget-required",
        "targetThreadId": THREAD_B,
        "successorThreadId": THREAD_C,
        "rendererStatus": "missing",
    }
    assert cycle["monitorHealthDiff"]["current"] == cycle["monitorHealthStatus"]

    runtime = cycle["runtimeState"]
    for source, cursor in cycle["nextRolloutCursors"].items():
        runtime["sourceScanState"][source].update(
            {"rolloutOffset": cursor["rolloutOffset"], "rolloutPathHash": cursor["rolloutPathHash"]}
        )
    runtime["rendererState"] = cycle["rendererStatus"]
    runtime["monitorHealthState"] = cycle["monitorHealthStatus"]
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})

    repeated = module.read_cycle(root, "monitor-test", database)
    assert repeated["monitorHealthStatus"]["status"] == "retarget-required"
    assert repeated["monitorHealthDiff"] is None


def test_read_cycle_reports_unavailable_target_without_failing(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    module.seed_rollout_cursors(root, "monitor-test", database)
    rollouts[THREAD_B].unlink()

    cycle = module.read_cycle(root, "monitor-test", database)

    assert cycle["ownerInputs"]["target"] == []
    assert cycle["nextRolloutCursors"]["target"]["status"] == "unavailable"
    assert cycle["monitorHealthStatus"]["status"] == "target-unavailable"


def test_retarget_seeds_successor_cursor_and_preserves_state(tmp_path: Path) -> None:
    module, root, _, _, created = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    successor = rollouts[THREAD_B].with_name("successor.jsonl")
    successor.write_bytes(rollout_user("msg-existing", THREAD_C, "历史消息不应重放"))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO threads (id, rollout_path, archived, title, name) VALUES (?, ?, 0, ?, ?)",
            (THREAD_C, str(successor), "Successor preview", "Successor task"),
        )
    module.put_observation(root, "monitor-test", observation("confirmed", "2026-09-02T20:01:00Z"))
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": created["context"]["runtimeState"]})
    before = module.read_context(root, "monitor-test")

    result = module.retarget(root, "monitor-test", THREAD_C, database)
    cycle = module.read_cycle(root, "monitor-test", database)

    assert result["retargeted"] is True
    assert result["monitor"]["targetThreadId"] == THREAD_C
    assert result["context"]["targetTitle"] == "Successor task"
    assert result["monitor"]["evaluation"] == before["monitor"]["evaluation"]
    assert result["observations"] == before["observations"]
    assert cycle["ownerInputs"]["target"] == []
    assert cycle["monitorHealthStatus"]["status"] == "renderer-abnormal"
    assert cycle["monitorHealthDiff"] is None
    assert module.retarget(root, "monitor-test", THREAD_C, database)["retargeted"] is False

    with pytest.raises(module.MonitorProgressError, match="retarget command"):
        module.write_evaluation(root, "monitor-test", {**evaluation_payload(), "targetThreadId": THREAD_B})


def test_retarget_rolls_back_when_second_replace_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    successor = rollouts[THREAD_B].with_name("successor.jsonl")
    successor.write_text("", encoding="utf-8")
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO threads (id, rollout_path, archived, title, name) VALUES (?, ?, 0, ?, ?)",
            (THREAD_C, str(successor), "Successor preview", "Successor task"),
        )
    monitor_path = root / ".progress-record" / "codex-progress-dashboard" / "monitors" / "monitor-test.json"
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    monitor_before = monitor_path.read_bytes()
    runtime_before = runtime_path.read_bytes()
    original_write = module._atomic_write
    calls = 0

    def fail_second(path: Path, value: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("replace failed")
        original_write(path, value)

    monkeypatch.setattr(module, "_atomic_write", fail_second)

    with pytest.raises(OSError, match="replace failed"):
        module.retarget(root, "monitor-test", THREAD_C, database)

    assert monitor_path.read_bytes() == monitor_before
    assert runtime_path.read_bytes() == runtime_before


def test_rebind_monitor_seeds_new_cursor_and_preserves_target_state(tmp_path: Path) -> None:
    module, root, _, _, created = make_context(tmp_path)
    database, rollouts = make_codex_store(tmp_path)
    new_monitor = rollouts[THREAD_B].with_name("new-monitor.jsonl")
    new_monitor.write_bytes(rollout_user("msg-existing", THREAD_C, "历史监控消息不应重放"))
    with sqlite3.connect(database) as connection:
        connection.execute(
            "INSERT INTO threads (id, rollout_path, archived, title, name) VALUES (?, ?, 0, ?, ?)",
            (THREAD_C, str(new_monitor), "Monitor preview", "New monitor"),
        )
    module.put_observation(root, "monitor-test", observation("confirmed", "2026-09-02T20:01:00Z"))
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": created["context"]["runtimeState"]})
    before = module.read_context(root, "monitor-test")

    result = module.rebind_monitor(root, "monitor-test", THREAD_C, database)
    cycle = module.read_cycle(root, "monitor-test", database)

    assert result["rebound"] is True
    assert result["monitor"]["monitorThreadId"] == THREAD_C
    assert result["monitor"]["targetThreadId"] == THREAD_B
    assert result["monitor"]["evaluation"] == before["monitor"]["evaluation"]
    assert result["observations"] == before["observations"]
    assert cycle["ownerInputs"]["monitor"] == []
    assert result["context"]["runtimeState"]["sourceScanState"]["target"] == before["context"]["runtimeState"]["sourceScanState"]["target"]
    assert module.rebind_monitor(root, "monitor-test", THREAD_C, database)["rebound"] is False


def test_seed_migrates_v2_runtime_without_replaying_existing_observations(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    module.put_observation(root, "monitor-test", observation())
    database, _ = make_codex_store(tmp_path)
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    legacy["version"] = 2
    legacy["runtimeState"].pop("reportedObservationDigests")
    legacy["runtimeState"].pop("lastSimulationCorrection")
    legacy["runtimeState"].pop("rendererState")
    legacy["runtimeState"].pop("monitorHealthState")
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = module.seed_rollout_cursors(root, "monitor-test", database)

    assert json.loads(runtime_path.read_text(encoding="utf-8"))["version"] == 7
    assert migrated["observationDiff"] == []
    assert list(migrated["runtimeState"]["reportedObservationDigests"]) == ["O001"]


def test_seed_migrates_v3_runtime_with_empty_simulation_state(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, _ = make_codex_store(tmp_path)
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    original_scan = legacy["runtimeState"]["sourceScanState"]
    legacy["version"] = 3
    legacy["runtimeState"].pop("lastSimulationCorrection")
    legacy["runtimeState"].pop("rendererState")
    legacy["runtimeState"].pop("monitorHealthState")
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = module.seed_rollout_cursors(root, "monitor-test", database)

    assert migrated["runtimeState"]["lastSimulationCorrection"] is None
    assert migrated["runtimeState"]["sourceScanState"]["monitor"]["lastSeenTurnId"] == original_scan["monitor"]["lastSeenTurnId"]
    assert migrated["observations"] == []


def test_seed_migrates_v4_runtime_and_binds_renderer_state(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, _ = make_codex_store(tmp_path)
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    legacy["version"] = 4
    legacy["runtimeState"].pop("rendererState")
    legacy["runtimeState"].pop("monitorHealthState")
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = module.seed_rollout_cursors(root, "monitor-test", database)

    assert json.loads(runtime_path.read_text(encoding="utf-8"))["version"] == 7
    assert migrated["runtimeState"]["rendererState"]["status"] == "missing"
    assert migrated["rendererDiff"] is None


def test_seed_migrates_v5_runtime_with_empty_monitor_health(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    database, _ = make_codex_store(tmp_path)
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    legacy["version"] = 5
    legacy["runtimeState"].pop("monitorHealthState")
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    migrated = module.seed_rollout_cursors(root, "monitor-test", database)

    assert json.loads(runtime_path.read_text(encoding="utf-8"))["version"] == 7
    assert migrated["runtimeState"]["monitorHealthState"] == migrated["monitorHealthStatus"]
    assert migrated["monitorHealthDiff"] is None


def test_refresh_migrates_v6_without_acknowledging_pending_observation_diff(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    created = module.put_observation(root, "monitor-test", observation())["observation"]
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    legacy = json.loads(runtime_path.read_text(encoding="utf-8"))
    legacy["version"] = 6
    legacy["runtimeState"].pop("reportedObservationSnapshots")
    legacy["runtimeState"].pop("packageState")
    runtime_path.write_text(json.dumps(legacy), encoding="utf-8")

    module.refresh_context_policy(root, "monitor-test")
    diff = module.read_cycle(root, "monitor-test")["observationDiff"]

    assert diff == [{"change": "created", "before": None, "after": created, "observation": created}]
    assert json.loads(runtime_path.read_text(encoding="utf-8"))["version"] == 7


def test_failed_runtime_replace_preserves_fixed_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module, root, _, _, created = make_context(tmp_path)
    context_path = root / ".progress-record" / "codex-progress-dashboard" / "contexts" / "monitor-test.json"
    runtime_path = root / ".progress-record" / "codex-progress-dashboard" / "runtime" / "monitor-test.json"
    fixed_before = context_path.read_text(encoding="utf-8")
    runtime_before = runtime_path.read_text(encoding="utf-8")
    monkeypatch.setattr(module.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises(OSError, match="replace failed"):
        module.write_cycle(
            root,
            "monitor-test",
            {**evaluation_payload(), "runtimeState": created["context"]["runtimeState"]},
        )

    assert context_path.read_text(encoding="utf-8") == fixed_before
    assert runtime_path.read_text(encoding="utf-8") == runtime_before
    assert not list(runtime_path.parent.glob("*.tmp"))


def test_failed_atomic_replace_preserves_previous_monitor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module, root, _, instance = make_instance(tmp_path)
    monitor_path = root / ".progress-record" / "codex-progress-dashboard" / "monitors" / "monitor-test.json"
    before = monitor_path.read_text(encoding="utf-8")
    monkeypatch.setattr(module.os, "replace", lambda source, target: (_ for _ in ()).throw(OSError("replace failed")))

    with pytest.raises(OSError, match="replace failed"):
        module.write_evaluation(root, "monitor-test", evaluation_payload())

    assert monitor_path.read_text(encoding="utf-8") == before
    assert not list(monitor_path.parent.glob("*.tmp"))
    assert instance["monitor"]["evaluation"] is None


def test_observation_create_and_update_keep_one_short_id(tmp_path: Path) -> None:
    module, root, _, _ = make_instance(tmp_path)
    candidate = observation()

    created = module.put_observation(root, "monitor-test", candidate)
    assert created["observation"]["id"] == "O001"
    context = module.init_context(
        root,
        "monitor-test",
        {"targetTitle": "示例任务", "targetBaseline": baseline()},
    )
    assert context["context"]["runtimeState"]["observationFingerprint"] == "confirmed:0|candidate:1"
    assert context["context"]["runtimeState"]["pendingCandidateIds"] == ["O001"]

    confirmed = {
        **candidate,
        "id": "O001",
        "content": "8,000 成员只作为容量观察，不是强制 5 秒 Gate。",
        "state": "confirmed",
        "confirmedAt": "2026-09-02T20:01:00Z",
        "sourceThreadId": THREAD_A,
        "sourceMessageId": "msg-2",
    }
    updated = module.put_observation(root, "monitor-test", confirmed)

    assert len(updated["observations"]) == 1
    assert updated["observation"]["id"] == "O001"
    assert updated["observation"]["sourceThreadId"] == THREAD_A
    assert [item["id"] for item in module.read_cycle(root, "monitor-test")["observations"]] == ["O001"]
    with pytest.raises(module.MonitorProgressError, match="invalid observation transition"):
        module.put_observation(root, "monitor-test", {**candidate, "id": "O001"})


def test_legacy_observation_defaults_to_one_time_and_new_writes_require_kind(tmp_path: Path) -> None:
    module, root, _, _ = make_instance(tmp_path)
    observation_path = root / ".progress-record" / "codex-progress-dashboard" / "observations" / "monitor-test.json"
    store = json.loads(observation_path.read_text(encoding="utf-8"))
    legacy = observation(observation_id="O001")
    legacy.pop("kind")
    old_specific = observation(
        observation_id="O002",
        topic="旧 specific 值",
        kind="specific",
    )
    store["nextObservationNumber"] = 3
    store["observations"] = [legacy, old_specific]
    observation_path.write_text(json.dumps(store), encoding="utf-8")

    loaded = module.read_instance(root, "monitor-test")["observations"]

    assert [item["kind"] for item in loaded] == ["one-time", "one-time"]
    with pytest.raises(module.MonitorProgressError, match="fields mismatch"):
        module.put_observation(root, "monitor-test", {**legacy, "id": "O001"})
    with pytest.raises(module.MonitorProgressError, match="kind must be one of"):
        module.put_observation(root, "monitor-test", {**old_specific, "id": "O002"})


def test_observation_diff_reports_create_update_and_remove_once(tmp_path: Path) -> None:
    module, root, _, _, _ = make_context(tmp_path)
    created = module.put_observation(root, "monitor-test", observation())["observation"]

    first = module.read_cycle(root, "monitor-test")
    assert first["observationDiff"] == [
        {"change": "created", "before": None, "after": created, "observation": created}
    ]
    assert module.read_cycle(root, "monitor-test")["observationDiff"] == first["observationDiff"]
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": first["runtimeState"]})
    assert module.read_cycle(root, "monitor-test")["observationDiff"] == []

    updated = {
        **created,
        "content": "完整更新后的纠偏内容。",
        "state": "confirmed",
        "confirmedAt": "2026-09-02T20:01:00Z",
    }
    module.put_observation(root, "monitor-test", updated)
    second = module.read_cycle(root, "monitor-test")
    assert second["observationDiff"][0]["change"] == "updated"
    assert second["observationDiff"][0]["before"] == created
    assert second["observationDiff"][0]["after"] == updated
    assert second["observationDiff"][0]["observation"]["content"] == "完整更新后的纠偏内容。"
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": second["runtimeState"]})

    module.remove_observation(root, "monitor-test", "O001")
    removed = module.read_cycle(root, "monitor-test")
    assert removed["observationDiff"] == [
        {"change": "removed", "id": "O001", "before": updated, "after": None}
    ]
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": removed["runtimeState"]})
    assert module.read_cycle(root, "monitor-test")["observationDiff"] == []


def test_duplicate_topic_returns_existing_id_and_unknown_update_fails(tmp_path: Path) -> None:
    module, root, _, _ = make_instance(tmp_path)
    module.put_observation(root, "monitor-test", observation())

    with pytest.raises(module.MonitorProgressError, match="topic already exists: O001"):
        module.put_observation(root, "monitor-test", observation(topic="  容量边界与性能验收  "))
    with pytest.raises(module.MonitorProgressError, match="unknown observation id: O999"):
        module.put_observation(root, "monitor-test", observation(observation_id="O999"))


def test_removed_ids_are_not_reused(tmp_path: Path) -> None:
    module, root, _, _ = make_instance(tmp_path)
    first = module.put_observation(root, "monitor-test", observation(topic="事项一"))["observation"]
    second = module.put_observation(root, "monitor-test", observation(topic="事项二"))["observation"]
    module.remove_observation(root, "monitor-test", first["id"])
    module.remove_observation(root, "monitor-test", second["id"])
    third = module.put_observation(root, "monitor-test", observation(topic="事项三"))["observation"]

    assert [first["id"], second["id"], third["id"]] == ["O001", "O002", "O003"]
    assert module._next_observation_id(1000) == "O1000"


def test_latest_for_package_returns_latest_monitor_and_all_confirmed(tmp_path: Path) -> None:
    module, root, package, _ = make_instance(tmp_path)
    module.write_evaluation(root, "monitor-test", evaluation_payload())
    for index in range(6):
        item = observation(
            "confirmed",
            f"2026-09-02T20:0{index}:00Z",
            topic=f"事项 {index}",
            content=f"观察 {index}",
        )
        item["sourceMessageId"] = f"msg-{index}"
        module.put_observation(root, "monitor-test", item)
    candidate = observation(topic="待确认事项")
    candidate["sourceMessageId"] = "candidate"
    module.put_observation(root, "monitor-test", candidate)

    projected = module.latest_for_package(root, package)

    assert projected is not None
    assert projected["monitor"]["evaluation"]["progress"] == "实现已完成，正在独立复核。"
    assert [item["content"] for item in projected["observations"]] == [
        "观察 5",
        "观察 4",
        "观察 3",
        "观察 2",
        "观察 1",
        "观察 0",
    ]


def test_open_reuses_v2_server_and_builds_deep_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    opened: list[str] = []
    health = {
        "rendererVersion": 2,
        "monitorProgressProtocol": 2,
        "instanceId": "renderer-1",
        "pid": 1234,
        "startedAt": "2026-09-04T08:00:00Z",
    }
    monkeypatch.setattr(module, "_health_payload", lambda port: health)
    monkeypatch.setattr(module, "_process_alive", lambda pid: pid == 1234)
    monkeypatch.setattr(module, "_target_packages", lambda port, target: [{"path": "docs/implementations/example"}])
    monkeypatch.setattr(module.webbrowser, "open", lambda url: opened.append(url) or True)

    result = module.open_dashboard(THREAD_B, package)

    assert result["reused"] is True
    assert result["pid"] == 1234
    assert "task=01a061c1-2bd2-7982-a497-23ee67c5f62f" in result["url"]
    assert "package=docs%2Fimplementations%2Fexample" in result["url"]
    assert opened == [result["url"]]


def test_open_starts_only_fixed_port_without_opening_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    started: list[int] = []
    renderer = {
        "version": 1,
        "pid": 4321,
        "port": 43187,
        "instanceId": "renderer-2",
        "startedAt": "2026-09-04T08:00:00Z",
    }
    monkeypatch.setattr(module, "_health_payload", lambda port: None)
    monkeypatch.setattr(module, "_port_available", lambda port: port == 43187)
    monkeypatch.setattr(module, "_start_server", lambda port, db: started.append(port) or renderer)
    monkeypatch.setattr(module, "_target_packages", lambda port, target: [{"path": "docs/implementations/example"}])

    result = module.open_dashboard(THREAD_B, package, no_browser=True)

    assert result["port"] == 43187
    assert result["pid"] == 4321
    assert result["reused"] is False
    assert started == [43187]


def test_open_rejects_foreign_process_on_fixed_port(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    monkeypatch.setattr(module, "_health_payload", lambda port: None)
    monkeypatch.setattr(module, "_port_available", lambda port: False)

    with pytest.raises(module.MonitorProgressError, match="43187 is occupied"):
        module.open_dashboard(THREAD_B, package, no_browser=True)


def test_renderer_status_and_diff_detect_death_and_ack_per_automation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, root, package, _, _ = make_context(tmp_path)
    module.init_instance(root, "monitor-two", THREAD_A, THREAD_B, package)
    module.init_context(root, "monitor-two", {"targetTitle": "示例二", "targetBaseline": baseline()})
    renderer = {
        "version": 1,
        "pid": 2468,
        "port": 43187,
        "instanceId": "renderer-shared",
        "startedAt": "2026-09-04T08:00:00Z",
    }
    module._atomic_write(module._renderer_path(root), renderer)
    health = {
        "rendererVersion": 2,
        "monitorProgressProtocol": 2,
        "instanceId": "renderer-shared",
        "pid": 2468,
        "startedAt": "2026-09-04T08:00:00Z",
    }
    monkeypatch.setattr(module, "_process_alive", lambda pid: True)
    monkeypatch.setattr(module, "_health_payload", lambda port: health)

    first = module.read_cycle(root, "monitor-test")
    second = module.read_cycle(root, "monitor-two")
    assert first["rendererStatus"]["status"] == "alive"
    assert first["rendererDiff"]["previous"]["status"] == "missing"
    assert second["rendererDiff"] is not None
    first["runtimeState"]["rendererState"] = first["rendererStatus"]
    module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": first["runtimeState"]})
    assert module.read_cycle(root, "monitor-test")["rendererDiff"] is None
    assert module.read_cycle(root, "monitor-two")["rendererDiff"] is not None

    health["instanceId"] = "reused-pid"
    mismatch = module.read_cycle(root, "monitor-test")
    assert mismatch["rendererStatus"]["status"] == "mismatch"
    health["instanceId"] = "renderer-shared"
    monkeypatch.setattr(module, "_process_alive", lambda pid: False)
    dead = module.read_cycle(root, "monitor-test")
    assert dead["rendererStatus"]["status"] == "dead"
    assert dead["rendererDiff"]["current"]["pid"] == 2468
    module._renderer_path(root).unlink()
    assert module.read_cycle(root, "monitor-test")["rendererStatus"]["status"] == "missing"


def test_schema_reports_v2_enums() -> None:
    module = load_module()
    schema = module.schema_contract()

    assert schema["protocolVersion"] == 2
    assert schema["contextVersion"] == 2
    assert schema["runtimeVersion"] == 7
    assert schema["policyVersion"] == "STATIC_MONITOR_POLICY_V20"
    assert schema["monitor"]["levels"] == ["abnormal", "attention", "normal"]
    assert schema["observation"]["states"] == ["candidate", "confirmed"]
    assert schema["observation"]["kinds"] == ["one-time", "pattern"]
    assert schema["targetUpdate"]["required"] == ["messageId", "turnId", "createdAt", "phase", "text"]
    assert schema["packageStatus"]["states"] == ["current", "invalid", "missing"]
    assert schema["observationDiff"]["fields"] == ["before", "after"]
    assert schema["writeCycleOutput"]["quietText"] == "DONT_NOTIFY"
    assert schema["monitorHealthStatus"]["states"] == [
        "healthy",
        "renderer-abnormal",
        "retarget-required",
        "target-unavailable",
    ]
    assert schema["retarget"]["seedsTargetCursorAt"] == "current complete-line end"
    assert schema["rebindMonitor"]["seedsMonitorCursorAt"] == "current complete-line end"


def test_cli_writes_evaluation_from_one_stdin_line(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    database, _ = make_codex_store(tmp_path)
    init = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "init",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
            "--monitor-thread",
            THREAD_A,
            "--target-thread",
            THREAD_B,
            "--package",
            str(package),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert init.returncode == 0, init.stderr

    init_context = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "init-context",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        input=json.dumps({"targetTitle": "示例任务", "targetBaseline": baseline()}) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert init_context.returncode == 0, init_context.stderr

    read_context = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "read-context",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert read_context.returncode == 0, read_context.stderr
    assert json.loads(read_context.stdout)["context"]["targetBaseline"] == baseline()

    read_static = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "read-static",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert read_static.returncode == 0, read_static.stderr
    assert json.loads(read_static.stdout)["staticContext"]["targetBaseline"] == baseline()

    seed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "seed-rollout-cursors",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
            "--db",
            str(database),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert seed.returncode == 0, seed.stderr
    assert json.loads(seed.stdout)["nextRolloutCursors"]["target"]["status"] == "current"

    read_cycle = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "read-cycle",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
            "--db",
            str(database),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert read_cycle.returncode == 0, read_cycle.stderr
    cycle_payload = json.loads(read_cycle.stdout)
    assert cycle_payload["staticRef"]["status"] == "current"
    assert "targetBaseline" not in cycle_payload
    assert "policySnapshot" not in cycle_payload

    refresh_context = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "refresh-context-policy",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert refresh_context.returncode == 0, refresh_context.stderr
    assert json.loads(refresh_context.stdout)["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V20"

    write = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "write-evaluation",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        input=json.dumps(evaluation_payload()) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )

    assert write.returncode == 0, write.stderr
    assert json.loads(write.stdout)["evaluation"]["next"] == "等待复核返回。"

    context_payload = json.loads(read_context.stdout)
    runtime = context_payload["context"]["runtimeState"]
    cycle = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "write-cycle",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        input=json.dumps({**evaluation_payload(), "runtimeState": runtime}) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert cycle.returncode == 0, cycle.stderr
    cycle_output = json.loads(cycle.stdout)
    assert cycle_output["monitor"]["evaluation"]["next"] == "等待复核返回。"
    assert set(cycle_output["notification"]) == {"shouldNotify", "reportText"}

    put = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "put-observation",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
        ],
        input=json.dumps(observation()) + "\n",
        capture_output=True,
        text=True,
        check=False,
    )
    assert put.returncode == 0, put.stderr
    assert json.loads(put.stdout)["observation"]["id"] == "O001"

    remove = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "remove-observation",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
            "--id",
            "O001",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert remove.returncode == 0, remove.stderr
    assert json.loads(remove.stdout)["observations"] == []
