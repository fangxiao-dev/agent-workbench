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
