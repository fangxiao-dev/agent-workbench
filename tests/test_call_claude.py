from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "call-claude" / "scripts" / "call_claude.py"


def load_executor():
    spec = importlib.util.spec_from_file_location("call_claude_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_command_passes_only_explicit_caller_configuration(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.build_parser().parse_args(
        [
            "--cwd",
            str(tmp_path),
            "--prompt",
            "review this",
            "--model",
            "claude-test",
            "--effort",
            "high",
            "--tools",
            "",
            "--system-prompt",
            "Return a result.",
            "--json-schema",
            '{"type":"object"}',
            "--disable-slash-commands",
            "--no-session-persistence",
        ]
    )

    assert executor.build_command(args) == [
        "claude",
        "-p",
        "--output-format",
        "json",
        "--no-session-persistence",
        "--disable-slash-commands",
        "--model",
        "claude-test",
        "--effort",
        "high",
        "--tools",
        "",
        "--system-prompt",
        "Return a result.",
        "--json-schema",
        '{"type":"object"}',
    ]


def test_execute_returns_claude_result_text_and_usage(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    calls = []
    monkeypatch.setattr(executor, "resolve_claude_executable", lambda _explicit: "claude")

    def fake_run_process(command, *, prompt, cwd, timeout_s):
        calls.append((command, prompt, cwd, timeout_s))
        return subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"type": "result", "result": "final answer", "usage": {"input_tokens": 3}}),
            "",
        )

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "task", "--timeout-s", "12"])

    assert executor.execute(args) == {
        "ok": True,
        "status": "completed",
        "text": "final answer",
        "usage": {"input_tokens": 3},
        "exit_code": 0,
        "error": None,
    }
    assert calls == [(["claude", "-p", "--output-format", "json"], "task", tmp_path, 12)]


def test_volta_shim_resolves_to_direct_claude_executable(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    resolved = tmp_path / "Volta" / "bin" / "claude.cmd"
    volta_shim = tmp_path / "Volta" / "tools" / "image" / "packages" / "claude"
    direct = volta_shim.parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    resolved.parent.mkdir(parents=True)
    resolved.touch()
    direct.parent.mkdir(parents=True)
    direct.touch()
    monkeypatch.setattr(executor.os, "name", "nt")
    monkeypatch.setattr(executor.shutil, "which", lambda name: "C:/tools/volta.exe" if name == "volta" else None)
    monkeypatch.setattr(
        executor.subprocess,
        "run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess([], 0, str(volta_shim), ""),
    )

    assert executor.resolve_volta_claude_executable(str(resolved)) == str(direct)


def test_explicit_and_environment_claude_executables_take_precedence(monkeypatch) -> None:
    executor = load_executor()
    monkeypatch.setenv("CLAUDE_EXECUTABLE", "env-claude")
    monkeypatch.setattr(executor.shutil, "which", lambda _name: "path-claude")

    assert executor.resolve_claude_executable("explicit-claude") == "explicit-claude"
    assert executor.resolve_claude_executable(None) == "env-claude"


def test_execute_reads_prompt_file(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from file", encoding="utf-8")
    monkeypatch.setattr(executor, "resolve_claude_executable", lambda _explicit: "claude")

    def fake_run_process(command, *, prompt, cwd, timeout_s):
        del command, cwd, timeout_s
        assert prompt == "from file"
        return subprocess.CompletedProcess([], 0, json.dumps({"result": "ok"}), "")

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt-file", str(prompt_file)])

    assert executor.execute(args)["text"] == "ok"


def test_execute_classifies_auth_failure(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    monkeypatch.setattr(executor, "resolve_claude_executable", lambda _explicit: "claude")

    def fake_run_process(command, *, prompt, cwd, timeout_s):
        del command, prompt, cwd, timeout_s
        return subprocess.CompletedProcess([], 9, "", "Please login to continue")

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "task"])

    envelope = executor.execute(args)
    assert envelope["ok"] is False
    assert envelope["exit_code"] == 9
    assert envelope["error"]["code"] == "AUTH"


def test_execute_retries_structured_output_failure_without_schema(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    calls = []
    monkeypatch.setattr(executor, "resolve_claude_executable", lambda _explicit: "claude")

    def fake_run_process(command, *, prompt, cwd, timeout_s):
        calls.append((command, prompt, cwd, timeout_s))
        if len(calls) == 1:
            return subprocess.CompletedProcess(
                command,
                1,
                "error_max_structured_output_retries",
                "",
            )
        return subprocess.CompletedProcess(command, 0, json.dumps({"result": "fallback result"}), "")

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(
        [
            "--cwd",
            str(tmp_path),
            "--prompt",
            "task",
            "--tools",
            "",
            "--json-schema",
            '{"type":"object"}',
            "--no-session-persistence",
        ]
    )

    result = executor.execute(args)

    assert result["ok"] is True
    assert result["text"] == "fallback result"
    assert len(calls) == 2
    assert "--json-schema" in calls[0][0]
    assert "--json-schema" not in calls[1][0]
    assert calls[0][1:] == calls[1][1:]
    assert "--tools" in calls[1][0]
    assert "--no-session-persistence" in calls[1][0]


def test_execute_returns_timeout_and_invalid_output_envelopes(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "task"])
    monkeypatch.setattr(executor, "resolve_claude_executable", lambda _explicit: "claude")

    def timeout(*_args, **_kwargs):
        raise executor.ExecutorError("TIMEOUT", "claude timed out after 900s")

    monkeypatch.setattr(executor, "run_process", timeout)
    timeout_result = executor.execute(args)
    assert timeout_result["error"]["code"] == "TIMEOUT"

    def invalid_output(command, *, prompt, cwd, timeout_s):
        del command, prompt, cwd, timeout_s
        return subprocess.CompletedProcess([], 0, "not json", "")

    monkeypatch.setattr(executor, "run_process", invalid_output)
    invalid_result = executor.execute(args)
    assert invalid_result["error"]["code"] == "INVALID_OUTPUT"


def test_main_writes_single_json_envelope(monkeypatch, capsys, tmp_path: Path) -> None:
    executor = load_executor()

    def fake_execute(_args):
        return {"ok": True, "status": "completed", "text": "ok", "usage": {}, "exit_code": 0, "error": None}

    monkeypatch.setattr(executor, "execute", fake_execute)
    assert executor.main(["--cwd", str(tmp_path), "--prompt", "task"]) == 0
    assert json.loads(capsys.readouterr().out) == {
        "ok": True,
        "status": "completed",
        "text": "ok",
        "usage": {},
        "exit_code": 0,
        "error": None,
    }
