from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import sys


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
