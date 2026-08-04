from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "thread-harness" / "scripts" / "rollout_compaction.py"


def load_module():
    spec = importlib.util.spec_from_file_location("rollout_compaction_under_test", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_thread_id_resolves_only_its_creation_day(tmp_path: Path) -> None:
    module = load_module()
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    created = datetime.fromtimestamp(
        int(thread_id.replace("-", "")[:12], 16) / 1000,
        timezone.utc,
    ).astimezone()
    day = tmp_path / created.strftime("%Y/%m/%d")
    day.mkdir(parents=True)
    expected = day / f"rollout-2026-08-04T16-19-53-{thread_id}.jsonl"
    expected.write_text("", encoding="utf-8")

    decoy = tmp_path / "2099" / "01" / "01"
    decoy.mkdir(parents=True)
    (decoy / f"rollout-decoy-{thread_id}.jsonl").write_text("", encoding="utf-8")

    assert module.rollout_path_for_thread(thread_id, tmp_path) == expected


def test_observer_baselines_at_eof_then_counts_only_new_compactions(tmp_path: Path) -> None:
    module = load_module()
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    created = datetime.fromtimestamp(
        int(thread_id.replace("-", "")[:12], 16) / 1000,
        timezone.utc,
    ).astimezone()
    day = tmp_path / created.strftime("%Y/%m/%d")
    day.mkdir(parents=True)
    rollout = day / f"rollout-current-{thread_id}.jsonl"
    historical = {
        "type": "compacted",
        "payload": {"window_number": 1, "window_id": "window-1"},
    }
    rollout.write_text(json.dumps(historical) + "\n", encoding="utf-8")

    state = module.observe_compactions(thread_id, None, tmp_path)
    assert state["observed_count"] == 0
    assert state["offset"] == rollout.stat().st_size

    new_event = {
        "type": "compacted",
        "payload": {"window_number": 2, "window_id": "window-2"},
    }
    notification = {"type": "event_msg", "payload": {"type": "context_compacted"}}
    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(new_event) + "\n")
        stream.write(json.dumps(notification) + "\n")

    state = module.observe_compactions(thread_id, state, tmp_path)
    assert state["observed_count"] == 1
    assert state["last_window_number"] == 2
    assert state["last_window_id"] == "window-2"

    assert module.observe_compactions(thread_id, state, tmp_path) == state


def test_observer_does_not_advance_past_an_incomplete_jsonl_line(tmp_path: Path) -> None:
    module = load_module()
    thread_id = "019fcd25-2e8d-7141-937f-95505c436a17"
    created = datetime.fromtimestamp(
        int(thread_id.replace("-", "")[:12], 16) / 1000,
        timezone.utc,
    ).astimezone()
    day = tmp_path / created.strftime("%Y/%m/%d")
    day.mkdir(parents=True)
    rollout = day / f"rollout-partial-{thread_id}.jsonl"
    rollout.touch()
    state = module.observe_compactions(thread_id, None, tmp_path)

    event = json.dumps(
        {
            "type": "compacted",
            "payload": {"window_number": 1, "window_id": "window-1"},
        }
    )
    split = len(event) // 2
    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(event[:split])

    still_at_baseline = module.observe_compactions(thread_id, state, tmp_path)
    assert still_at_baseline["offset"] == state["offset"]
    assert still_at_baseline["observed_count"] == 0

    with rollout.open("a", encoding="utf-8") as stream:
        stream.write(event[split:] + "\n")

    observed = module.observe_compactions(thread_id, still_at_baseline, tmp_path)
    assert observed["observed_count"] == 1
    assert observed["offset"] == rollout.stat().st_size
