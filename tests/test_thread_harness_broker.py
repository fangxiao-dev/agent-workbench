from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "thread-harness" / "scripts"


def load_module(name: str, path: Path):
    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def rollout_path(root: Path, thread_id: str) -> Path:
    path = root / "2026" / "08" / "04"
    path.mkdir(parents=True, exist_ok=True)
    return path / f"rollout-{thread_id}.jsonl"


def token_event(input_tokens, *, context=200000, total=900000):
    return {
        "type": "event_msg",
        "payload": {
            "type": "token_count",
            "info": {
                "total_token_usage": {"input_tokens": total},
                "last_token_usage": {"input_tokens": input_tokens},
                "model_context_window": context,
            },
        },
    }


def test_token_observer_uses_latest_input_and_preserves_partial_offset(tmp_path: Path) -> None:
    module = load_module("rollout_budget_under_test", SCRIPTS / "rollout_compaction.py")
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    rollout = rollout_path(tmp_path, thread_id)
    rollout.write_text(json.dumps({"type": "event_msg", "payload": {"type": "old"}}) + "\n", encoding="utf-8")

    state = module.observe_rollout(thread_id, None, tmp_path)
    assert state["offset"] == rollout.stat().st_size
    assert state["token_usage_available"] is False

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(token_event(115599)) + "\n")
        stream.write(json.dumps(token_event(115600))[:20])
    observed = module.observe_rollout(thread_id, state, tmp_path)
    assert observed["last_token_usage"] == {"input_tokens": 115599}
    assert observed["token_usage_available"] is True
    assert observed["offset"] < rollout.stat().st_size

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(token_event(115600))[20:] + "\n")
    observed = module.observe_rollout(thread_id, observed, tmp_path)
    assert observed["last_token_usage"] == {"input_tokens": 115600}
    assert observed["offset"] == rollout.stat().st_size


def test_token_observer_invalid_usage_falls_back_without_using_total(tmp_path: Path) -> None:
    module = load_module("rollout_budget_invalid_under_test", SCRIPTS / "rollout_compaction.py")
    contract = load_module("broker_contract_under_test", SCRIPTS / "broker_contract.py")
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    rollout = rollout_path(tmp_path, thread_id)
    rollout.touch()
    state = module.observe_rollout(thread_id, None, tmp_path)

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(token_event(100000, total=900000)) + "\n")
        stream.write(json.dumps({
            "type": "event_msg",
            "payload": {
                "type": "token_count",
                "info": {"last_token_usage": {"input_tokens": "bad"}, "model_context_window": 200000},
            },
        }) + "\n")
    observed = module.observe_rollout(thread_id, state, tmp_path)
    config, issues = contract.validate_broker_config({
        "broker": {
            "profile": "solo",
            "budget": {"smart_zone_tokens": 150000, "tail_requests": 20, "tail_p75_increment_tokens": 1720},
        }
    })
    assert not issues and config["budget"]["handoff_at"] == 115600
    assert observed["token_usage_available"] is False
    assert observed["last_token_usage"] is None
    stage, source = contract.budget_stage(observed, config, compaction_count=None)
    assert (stage, source) == ("tracking", "compaction_fallback")

    valid = {"last_token_usage": {"input_tokens": 100000}, "model_context_window": 200000, "token_usage_available": True}
    assert contract.budget_stage(valid, config, compaction_count=99) == ("tracking", "token")
    assert contract.budget_stage(observed, config, compaction_count=4) == ("handoff_due", "compaction_fallback")
    assert contract.budget_stage(
        {"last_token_usage": {"input_tokens": 115600}, "model_context_window": 200000, "token_usage_available": True},
        config,
    ) == ("handoff_due", "token")
    assert contract.budget_stage(
        {"last_token_usage": {"input_tokens": 1000}, "model_context_window": 200000, "token_usage_available": True},
        config,
        previous_stage="handoff_due",
    )[0] == "handoff_due"


def test_token_observer_ignores_non_token_events_and_rejects_small_context(tmp_path: Path) -> None:
    module = load_module("rollout_budget_event_type_under_test", SCRIPTS / "rollout_compaction.py")
    contract = load_module("broker_contract_context_under_test", SCRIPTS / "broker_contract.py")
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    rollout = rollout_path(tmp_path, thread_id)
    rollout.touch()
    state = module.observe_rollout(thread_id, None, tmp_path)
    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps({
            "type": "event_msg",
            "payload": {"info": {"last_token_usage": {"input_tokens": 200000}}},
        }) + "\n")
        stream.write(json.dumps(token_event(115600, context=100000)) + "\n")
    observed = module.observe_rollout(thread_id, state, tmp_path)
    config, issues = contract.validate_broker_config({
        "broker": {
            "profile": "solo",
            "budget": {"smart_zone_tokens": 150000, "tail_requests": 20, "tail_p75_increment_tokens": 1720},
        }
    })
    assert not issues
    stage, source = contract.budget_stage(observed, config)
    assert observed["last_token_usage"] == {"input_tokens": 115600}
    assert (stage, source) == ("tracking", "compaction_fallback")


def test_package_adapter_is_read_only_and_returns_fixed_facts(tmp_path: Path) -> None:
    adapter = load_module("package_adapter_under_test", SCRIPTS / "package_adapter.py")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "initial"], cwd=repo, check=True)

    package = repo / "package"
    (package / ".impl-package").mkdir(parents=True)
    (package / "execution" / "initial").mkdir(parents=True)
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
        "activeCheckpoints": {"attempt": {"next": "run the next bounded action"}},
    }, indent=2) + "\n", encoding="utf-8")
    record.write_text("# execution checkpoint\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in (progress, state, record)}

    facts = adapter.read_package_facts(str(progress), current_session_id="task-session")
    assert tuple(facts) == adapter.FACT_FIELDS
    assert facts["package_entry"] == str(progress.resolve())
    assert facts["active_checkpoint"] == str(record.resolve())
    assert facts["next_action"] == "run the next bounded action"
    assert facts["current_session_id"] == "task-session"
    assert facts["worktree"] == str(repo.resolve())
    assert facts["head"] == facts["revision"] and len(facts["revision"]) == 40
    assert {path: path.read_bytes() for path in (progress, state, record)} == before


def test_package_adapter_schema_warnings_are_non_blocking_and_clear_unknown_facts(tmp_path: Path) -> None:
    adapter = load_module("package_adapter_warning_under_test", SCRIPTS / "package_adapter.py")
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "--allow-empty", "-qm", "initial"], cwd=repo, check=True)

    package = repo / "package"
    (package / ".impl-package").mkdir(parents=True)
    progress = package / "progress.md"
    state = package / ".impl-package" / "state.json"
    progress.write_text("# progress\n", encoding="utf-8")

    state.write_text(json.dumps({"formatVersion": "3.4"}) + "\n", encoding="utf-8")
    facts, warnings = adapter.read_package_observation(str(progress), current_session_id="task-session")
    assert facts["active_checkpoint"] is None and facts["next_action"] is None
    assert any(tag == "package_schema_warning" for tag, _detail in warnings)

    state.write_text(json.dumps({
        "formatVersion": "3.5",
        "attempt": {"id": "initial"},
        "activeCheckpoints": {"attempt": {"next": 17}},
    }) + "\n", encoding="utf-8")
    facts, warnings = adapter.read_package_observation(str(progress), current_session_id="task-session")
    assert facts["active_checkpoint"] is None and facts["next_action"] is None
    assert any(tag == "package_schema_warning" for tag, _detail in warnings)

    state.write_text(json.dumps({
        "formatVersion": "3.5",
        "attempt": {"id": "initial"},
        "activeCheckpoints": {},
    }) + "\n", encoding="utf-8")
    facts, warnings = adapter.read_package_observation(str(progress), current_session_id="task-session")
    assert facts["active_checkpoint"] is None and facts["next_action"] is None
    assert any(tag == "package_schema_warning" for tag, _detail in warnings)

    state.unlink()
    facts, warnings = adapter.read_package_observation(str(progress), current_session_id="task-session")
    assert facts["active_checkpoint"] is None and facts["next_action"] is None
    assert any(tag == "package_schema_warning" for tag, _detail in warnings)


def sync_state_fixture() -> dict:
    return {
        "rollout_path": "controller-rollout.jsonl",
        "offset": 91,
        "compaction_observers": {},
        "budget_states": {
            "task-session": {"stage": "handoff_due", "source": "token"},
        },
        "next_poll_seq": 17,
        "next_act_seq": 9,
        "next_ledger_seq": 26,
        "dispatches_since_progress": 2,
        "docs_only_advances": 1,
        "last_must_act_seq": 8,
        "invalid_rounds": 3,
        "stall_reset_seq": 12,
    }


def test_sync_state_crash_is_fail_closed_and_preserves_sticky_state(tmp_path: Path, monkeypatch) -> None:
    runtime = load_module("ledger_runtime_state_under_test", SCRIPTS / "ledger_runtime.py")
    runtime.ACTIVE_REGISTRY_PATH = tmp_path / "coordination.json"
    coordination_id = "state-crash"
    state_path = runtime.runtime_dir(coordination_id) / "sync-state.json"
    state = sync_state_fixture()
    runtime.save_state(coordination_id, state)
    original_bytes = state_path.read_bytes()

    real_replace = runtime.os.replace

    def fail_replace(source, target):
        assert Path(source).read_bytes().startswith(b"{")
        raise OSError("simulated crash before replace")

    monkeypatch.setattr(runtime.os, "replace", fail_replace)
    with pytest.raises(runtime.LedgerError, match="unable to durably save sync-state"):
        runtime.save_state(coordination_id, {**state, "next_poll_seq": 18})
    assert state_path.read_bytes() == original_bytes
    monkeypatch.setattr(runtime.os, "replace", real_replace)
    assert runtime.load_state(coordination_id)["budget_states"]["task-session"]["stage"] == "handoff_due"
    assert runtime.load_state(coordination_id)["next_poll_seq"] == 17
    assert runtime.load_state(coordination_id)["next_act_seq"] == 9

    for corrupted in (b'{"next_poll_seq": 18\n', b'{"next_poll_seq": 18,'):
        state_path.write_bytes(corrupted)
        with pytest.raises(runtime.LedgerError, match="sync-state invalid"):
            runtime.load_state(coordination_id)
        state_path.write_bytes(original_bytes)

    staged = state_path.parent / ".sync-state.json.crash.tmp"
    staged.write_bytes(b'{"next_poll_seq": 18,')
    loaded = runtime.load_state(coordination_id)
    assert loaded["next_poll_seq"] == 17
    assert loaded["next_act_seq"] == 9
    assert loaded["budget_states"]["task-session"]["stage"] == "handoff_due"


def make_ledger_registry(tmp_path: Path) -> tuple[Path, str]:
    broker = tmp_path / "broker"
    broker.mkdir()
    coordination_id = "decision-retire"
    registry_path = broker / f"{coordination_id}.json"
    registry_path.write_text(
        json.dumps(
            {
                "coordination_id": coordination_id,
                "broker": {
                    "profile": "swarm",
                    "budget": {
                        "smart_zone_tokens": 150000,
                        "tail_requests": 20,
                        "tail_p75_increment_tokens": 1720,
                    },
                },
                "controller": {"current_session_id": "controller-session"},
                "children": {
                    "child": {"current_session_id": "child-session", "active": True},
                },
            }
        ),
        encoding="utf-8",
    )
    return registry_path, coordination_id


def run_ledger(env: dict, *args: str) -> tuple[int, str]:
    result = subprocess.run(
        [sys.executable, "-B", str(SCRIPTS / "ledger.py"), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )
    return result.returncode, (result.stdout or "") + (result.stderr or "")


def test_owner_decision_binding_and_terminal_retirement(tmp_path: Path, monkeypatch) -> None:
    registry_path, coordination_id = make_ledger_registry(tmp_path)
    env = dict(os.environ)
    env["THREAD_HARNESS_BROKER_ROOT"] = str(registry_path.parent)
    run_ledger(env, "init", "--coordination-id", coordination_id)
    progress_path = registry_path.parent / coordination_id / "progress.jsonl"

    rc, output = run_ledger(
        env, "report", "--coordination-id", coordination_id,
        "--node", "child", "--state", "awaiting_owner",
    )
    assert rc == 64 and "requires --decision-id" in output
    assert not progress_path.read_text(encoding="utf-8").strip()

    rc, output = run_ledger(
        env, "report", "--coordination-id", coordination_id,
        "--node", "child", "--state", "awaiting_owner", "--decision-id", "missing",
    )
    assert rc == 64 and "decision is not pending: missing" in output
    assert not progress_path.read_text(encoding="utf-8").strip()

    rc, _ = run_ledger(
        env, "decide", "--coordination-id", coordination_id,
        "--raise", "owner-choice", "--by", "child", "--blocks", "child",
        "--question", "choose",
    )
    assert rc == 0
    rc, output = run_ledger(
        env, "report", "--coordination-id", coordination_id,
        "--node", "child", "--state", "awaiting_owner", "--decision-id", "owner-choice",
    )
    assert rc == 0 and "state=awaiting_owner" in output

    if str(SCRIPTS) not in sys.path:
        sys.path.insert(0, str(SCRIPTS))
    import ledger_coordination
    import ledger_registry
    import ledger_runtime

    monkeypatch.setattr(ledger_runtime, "ACTIVE_REGISTRY_PATH", registry_path)
    registry = ledger_registry.load_registry(coordination_id)
    active_children = [
        node for node in ledger_registry.registry_nodes(registry)
        if node["role"] == "child" and node.get("active", True)
    ]
    assert ledger_coordination.runnable_watch_nodes(coordination_id, active_children) == []

    rc, _ = run_ledger(
        env, "decide", "--coordination-id", coordination_id,
        "--answer", "owner-choice", "--text", "done",
    )
    assert rc == 0
    assert [
        node["name"]
        for node in ledger_coordination.runnable_watch_nodes(coordination_id, active_children)
    ] == ["child"]

    before_retire = registry_path.read_bytes()
    rc, output = run_ledger(
        env, "retire", "--registry", str(registry_path),
        "--node", "child", "--expect-current", "child-session",
    )
    assert rc == 64 and "not terminal" in output
    assert registry_path.read_bytes() == before_retire

    rc, _ = run_ledger(
        env, "report", "--coordination-id", coordination_id,
        "--node", "child", "--state", "ready_for_assignment",
    )
    assert rc == 0
    rc, output = run_ledger(
        env, "retire", "--registry", str(registry_path),
        "--node", "child", "--expect-current", "stale-session",
    )
    assert rc == 64 and "current session mismatch" in output

    rc, output = run_ledger(
        env, "retire", "--registry", str(registry_path),
        "--node", "child", "--expect-current", "child-session",
    )
    assert rc == 0 and "RETIRED child" in output
    retired = json.loads(registry_path.read_text(encoding="utf-8"))
    assert retired["children"]["child"]["active"] is False
