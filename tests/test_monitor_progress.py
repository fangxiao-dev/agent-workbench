from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "monitor_progress.py"
THREAD_A = "01a05c65-2eac-7d22-aba9-c2671b2cd03d"
THREAD_B = "01a061c1-2bd2-7982-a497-23ee67c5f62f"


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


def observation(
    state: str = "candidate",
    confirmed_at=None,
    *,
    observation_id=None,
    topic: str = "容量边界与性能验收",
    content: str = "不要把容量边界误作硬性验收标准。",
) -> dict:
    return {
        "id": observation_id,
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
    assert result["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V5"
    assert len(result["context"]["snapshotHash"]) == 64
    assert result["context"]["runtimeState"]["lastFallbackTurnId"] is None
    assert result["context"]["policySnapshot"]["visibility"].startswith("read_thread")
    assert "fallback" not in result["context"]["policySnapshot"]
    policy_text = json.dumps(result["context"]["policySnapshot"], ensure_ascii=False)
    assert "工具调试，不写入目标任务 sidecar" in policy_text
    assert "默认只写当前做到哪里" in policy_text
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
    assert cycle["staticRef"]["status"] == "current"


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
    assert refreshed["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V5"
    assert refreshed["context"]["targetBaseline"] == before["context"]["targetBaseline"]
    assert refreshed["context"]["runtimeState"] == before["context"]["runtimeState"]
    assert refreshed["monitor"] == before["monitor"]
    assert [item["id"] for item in refreshed["observations"]] == ["O001"]


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
    }

    updated = module.write_cycle(root, "monitor-test", {**evaluation_payload(), "runtimeState": runtime})

    assert updated["monitor"]["evaluation"]["next"] == "等待复核返回。"
    assert updated["context"]["runtimeState"]["lastFallbackTurnId"] == THREAD_B
    assert context_path.read_bytes() == fixed_before
    assert module.read_context(root, "monitor-test") == updated


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


def test_latest_for_package_returns_latest_monitor_and_five_confirmed(tmp_path: Path) -> None:
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
    ]


def test_open_reuses_v2_server_and_builds_deep_link(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    opened: list[str] = []
    monkeypatch.setattr(module, "_health", lambda port: port == 43187)
    monkeypatch.setattr(module, "_target_packages", lambda port, target: [{"path": "docs/implementations/example"}])
    monkeypatch.setattr(module.webbrowser, "open", lambda url: opened.append(url) or True)

    result = module.open_dashboard(THREAD_B, package)

    assert result["reused"] is True
    assert "task=01a061c1-2bd2-7982-a497-23ee67c5f62f" in result["url"]
    assert "package=docs%2Fimplementations%2Fexample" in result["url"]
    assert opened == [result["url"]]


def test_open_uses_next_available_port_without_opening_browser(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
    (root / ".git").write_text("gitdir: elsewhere", encoding="utf-8")
    started: list[int] = []
    monkeypatch.setattr(module, "_health", lambda port: False)
    monkeypatch.setattr(module, "_port_available", lambda port: port == 43188)
    monkeypatch.setattr(module, "_start_server", lambda port, db: started.append(port))
    monkeypatch.setattr(module, "_wait_for_server", lambda port: None)
    monkeypatch.setattr(module, "_target_packages", lambda port, target: [{"path": "docs/implementations/example"}])

    result = module.open_dashboard(THREAD_B, package, no_browser=True)

    assert result["port"] == 43188
    assert result["reused"] is False
    assert started == [43188]


def test_schema_reports_v2_enums() -> None:
    module = load_module()
    schema = module.schema_contract()

    assert schema["protocolVersion"] == 2
    assert schema["contextVersion"] == 2
    assert schema["runtimeVersion"] == 1
    assert schema["policyVersion"] == "STATIC_MONITOR_POLICY_V5"
    assert schema["monitor"]["levels"] == ["abnormal", "attention", "normal"]
    assert schema["observation"]["states"] == ["candidate", "confirmed"]


def test_cli_writes_evaluation_from_one_stdin_line(tmp_path: Path) -> None:
    root = tmp_path / "workspace"
    package = root / "docs" / "implementations" / "example"
    package.mkdir(parents=True)
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

    read_cycle = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "read-cycle",
            "--root",
            str(root),
            "--automation-id",
            "monitor-test",
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
    assert json.loads(refresh_context.stdout)["context"]["policyVersion"] == "STATIC_MONITOR_POLICY_V5"

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
    assert json.loads(cycle.stdout)["monitor"]["evaluation"]["next"] == "等待复核返回。"

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
