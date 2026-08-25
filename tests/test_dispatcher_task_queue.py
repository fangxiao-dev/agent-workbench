from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "dispatcher" / "scripts" / "task_queue.py"


def run_cli(queue: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--path", str(queue), *args],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )


def assert_json_output(result: subprocess.CompletedProcess[str], expected: object) -> None:
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert json.loads(result.stdout) == expected
    assert result.stdout.endswith("\n")


def init_queue(queue: Path) -> None:
    assert_json_output(run_cli(queue, "init"), [])


def test_init_creates_empty_queue_and_never_overwrites(tmp_path: Path) -> None:
    queue = tmp_path / "task-queue.json"

    init_queue(queue)
    assert queue.read_bytes() == b"[]\n"

    original = queue.read_bytes()
    result = run_cli(queue, "init")
    assert result.returncode == 1
    assert result.stdout == ""
    assert "already exists" in result.stderr
    assert "Traceback" not in result.stderr
    assert queue.read_bytes() == original

    missing_parent = tmp_path / "missing" / "task-queue.json"
    result = run_cli(missing_parent, "init")
    assert result.returncode == 1
    assert "parent directory does not exist" in result.stderr
    assert not missing_parent.exists()


def test_crud_queries_and_status_transitions_preserve_order(tmp_path: Path) -> None:
    queue = tmp_path / "task-queue.json"
    init_queue(queue)

    assert_json_output(
        run_cli(queue, "add", "--id", "T001", "--summary", "Implement the seam"),
        [{"id": "T001", "summary": "Implement the seam", "status": "planned", "depOn": []}],
    )
    assert_json_output(
        run_cli(
            queue,
            "add",
            "--id",
            "T002",
            "--summary",
            "Verify the seam",
            "--dep-on",
            "T001",
        ),
        [
            {"id": "T001", "summary": "Implement the seam", "status": "planned", "depOn": []},
            {"id": "T002", "summary": "Verify the seam", "status": "planned", "depOn": ["T001"]},
        ],
    )
    assert_json_output(
        run_cli(queue, "add", "--id", "T003", "--summary", "Prepare fixtures"),
        [
            {"id": "T001", "summary": "Implement the seam", "status": "planned", "depOn": []},
            {"id": "T002", "summary": "Verify the seam", "status": "planned", "depOn": ["T001"]},
            {"id": "T003", "summary": "Prepare fixtures", "status": "planned", "depOn": []},
        ],
    )

    assert_json_output(
        run_cli(queue, "update-summary", "--id", "T003", "--summary", "Prepare browser fixtures"),
        [
            {"id": "T001", "summary": "Implement the seam", "status": "planned", "depOn": []},
            {"id": "T002", "summary": "Verify the seam", "status": "planned", "depOn": ["T001"]},
            {"id": "T003", "summary": "Prepare browser fixtures", "status": "planned", "depOn": []},
        ],
    )
    assert run_cli(queue, "update-status", "--id", "T001", "--status", "in-progress").returncode == 0
    assert run_cli(queue, "update-status", "--id", "T001", "--status", "planned").returncode == 0
    assert run_cli(queue, "update-deps", "--id", "T003", "--add", "T002").returncode == 0
    assert run_cli(queue, "update-deps", "--id", "T003", "--remove", "T002").returncode == 0

    assert_json_output(
        run_cli(queue, "list", "--id", "T003"),
        {"id": "T003", "summary": "Prepare browser fixtures", "status": "planned", "depOn": []},
    )
    assert_json_output(
        run_cli(queue, "get-next-tasks"),
        [
            {"id": "T001", "summary": "Implement the seam", "status": "planned", "depOn": []},
            {"id": "T003", "summary": "Prepare browser fixtures", "status": "planned", "depOn": []},
        ],
    )
    assert [task["id"] for task in json.loads(run_cli(queue, "list").stdout)] == ["T001", "T002", "T003"]


def test_delete_releases_all_dependencies_atomically(tmp_path: Path) -> None:
    queue = tmp_path / "task-queue.json"
    queue.write_text(
        json.dumps(
            [
                {"id": "T001", "summary": "Foundation", "status": "in-progress", "depOn": []},
                {"id": "T002", "summary": "Consumer A", "status": "planned", "depOn": ["T001"]},
                {"id": "T003", "summary": "Consumer B", "status": "planned", "depOn": ["T001", "T002"]},
            ]
        ),
        encoding="utf-8",
    )

    expected = [
        {"id": "T002", "summary": "Consumer A", "status": "planned", "depOn": []},
        {"id": "T003", "summary": "Consumer B", "status": "planned", "depOn": ["T002"]},
    ]
    assert_json_output(run_cli(queue, "delete", "--id", "T001"), expected)
    assert json.loads(queue.read_text(encoding="utf-8")) == expected


@pytest.mark.parametrize(
    "payload,error",
    [
        ({}, "top-level JSON value must be an array"),
        (["T001"], "must be an object"),
        ([{"id": "T001", "summary": "x", "status": "planned", "depOn": [], "extra": True}], "exactly"),
        (
            [
                {"id": "T001", "summary": "x", "status": "planned", "depOn": []},
                {"id": "T001", "summary": "y", "status": "planned", "depOn": []},
            ],
            "duplicate task id",
        ),
        ([{"id": " ", "summary": "x", "status": "planned", "depOn": []}], "non-empty string"),
        ([{"id": "T001", "summary": " ", "status": "planned", "depOn": []}], "summary"),
        ([{"id": "T001", "summary": "x", "status": "done", "depOn": []}], "status"),
        ([{"id": "T001", "summary": "x", "status": [], "depOn": []}], "status"),
        ([{"id": "T001", "summary": "x", "status": "planned", "depOn": "T000"}], "depOn"),
        ([{"id": "T001", "summary": "x", "status": "planned", "depOn": [1]}], "dependency ids"),
        ([{"id": "T001", "summary": "x", "status": "planned", "depOn": ["T999"]}], "unknown dependency"),
        (
            [
                {"id": "T001", "summary": "x", "status": "planned", "depOn": []},
                {"id": "T002", "summary": "y", "status": "planned", "depOn": ["T001", "T001"]},
            ],
            "duplicate dependency",
        ),
        ([{"id": "T001", "summary": "x", "status": "planned", "depOn": ["T001"]}], "depend on itself"),
        (
            [
                {"id": "T001", "summary": "x", "status": "planned", "depOn": ["T002"]},
                {"id": "T002", "summary": "y", "status": "planned", "depOn": ["T001"]},
            ],
            "cycle",
        ),
    ],
)
def test_invalid_queue_is_rejected_without_rewrite(tmp_path: Path, payload: object, error: str) -> None:
    queue = tmp_path / "task-queue.json"
    queue.write_text(json.dumps(payload), encoding="utf-8")
    original = queue.read_bytes()

    result = run_cli(queue, "list")

    assert result.returncode == 1
    assert result.stdout == ""
    assert error in result.stderr
    assert "Traceback" not in result.stderr
    assert queue.read_bytes() == original


def test_duplicate_json_key_is_rejected_without_traceback_or_rewrite(tmp_path: Path) -> None:
    queue = tmp_path / "task-queue.json"
    queue.write_text(
        '[{"id":"T001","id":"T002","summary":"x","status":"planned","depOn":[]}]',
        encoding="utf-8",
    )
    original = queue.read_bytes()

    result = run_cli(queue, "list")

    assert result.returncode == 1
    assert result.stdout == ""
    assert "duplicate JSON key: id" in result.stderr
    assert "Traceback" not in result.stderr
    assert queue.read_bytes() == original


def test_failed_mutations_and_usage_errors_do_not_rewrite(tmp_path: Path) -> None:
    queue = tmp_path / "task-queue.json"
    init_queue(queue)
    assert run_cli(queue, "add", "--id", "T001", "--summary", "One").returncode == 0
    assert run_cli(queue, "add", "--id", "T002", "--summary", "Two", "--dep-on", "T001").returncode == 0

    failures = [
        (("add", "--id", "T001", "--summary", "Duplicate"), 1, "already exists"),
        (("add", "--id", "T003", "--summary", "Unknown", "--dep-on", "T999"), 1, "unknown dependency"),
        (("delete", "--id", "T999"), 1, "not found"),
        (("update-summary", "--id", "T999", "--summary", "Missing"), 1, "not found"),
        (("update-status", "--id", "T001", "--status", "done"), 2, "invalid choice"),
        (("update-deps", "--id", "T002", "--add", "T001"), 1, "already depends"),
        (("update-deps", "--id", "T002", "--remove", "T999"), 1, "does not depend"),
        (("update-deps", "--id", "T001", "--add", "T002"), 1, "cycle"),
        (("update-deps", "--id", "T002", "--add", "T001", "--remove", "T001"), 2, "not allowed"),
        (("list", "--id", "T999"), 1, "not found"),
    ]

    for args, code, error in failures:
        original = queue.read_bytes()
        result = run_cli(queue, *args)
        assert result.returncode == code, (args, result.stderr)
        assert result.stdout == ""
        assert error in result.stderr
        assert "Traceback" not in result.stderr
        assert queue.read_bytes() == original


def test_atomic_replace_failure_keeps_original_and_cleans_temp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    queue = tmp_path / "task-queue.json"
    queue.write_bytes(b"[]\n")
    spec = importlib.util.spec_from_file_location("dispatcher_task_queue", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    def fail_replace(source: str | bytes | Path, target: str | bytes | Path) -> None:
        raise OSError("replace denied")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(module.QueueError, match="replace denied"):
        module.write_queue(
            queue,
            [{"id": "T001", "summary": "One", "status": "planned", "depOn": []}],
        )

    assert queue.read_bytes() == b"[]\n"
    assert list(tmp_path.iterdir()) == [queue]
