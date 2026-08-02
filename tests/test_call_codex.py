from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "call-codex" / "scripts" / "call_codex.py"


def load_executor():
    spec = importlib.util.spec_from_file_location("call_codex_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_command_transparently_maps_explicit_caller_configuration(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.build_parser().parse_args(
        [
            "--cwd", str(tmp_path), "--prompt", "do work", "--timeout-s", "12", "--model", "gpt-test",
            "--config", 'service_tier="fast"', "--config", 'model_reasoning_effort="high"',
            "--sandbox", "read-only", "--ephemeral", "--output-schema", str(tmp_path / "schema.json"),
        ]
    )

    command = executor.build_command(args)

    assert command == [
        "codex", "exec", "--json", "-m", "gpt-test", "-c", 'service_tier="fast"', "-c",
        'model_reasoning_effort="high"', "--sandbox", "read-only", "--ephemeral", "--output-schema",
        str(tmp_path / "schema.json"), "--cd", str(tmp_path.resolve()), "-",
    ]
    assert "--role" not in executor.build_parser().format_help()


def test_run_returns_final_jsonl_text_and_usage(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    calls = []
    monkeypatch.setattr(executor, "resolve_codex_executable", lambda _explicit: "codex")

    def fake_run_process(command, *, stdin, timeout_s, cwd):
        calls.append((command, stdin, timeout_s, cwd))
        return type("Completed", (), {
            "returncode": 0,
            "stdout": "\n".join([
                json.dumps({"type": "turn.started"}),
                json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "final answer"}}),
                json.dumps({"type": "turn.completed", "usage": {"input_tokens": 7, "output_tokens": 3}}),
            ]),
            "stderr": "",
        })()

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "prompt", "--timeout-s", "5"])

    result = executor.run(args)

    assert result == {
        "ok": True, "status": "completed", "text": "final answer",
        "usage": {"input_tokens": 7, "output_tokens": 3}, "exit_code": 0, "error": None,
    }
    assert calls == [(
        [
            "codex", "exec", "--json", "-m", "gpt-5.6-luna", "-c",
            'model_reasoning_effort="max"', "--cd", str(tmp_path.resolve()), "-",
        ],
        "prompt",
        5,
        tmp_path.resolve(),
    )]


def test_parse_jsonl_accepts_codex_message_payload_shape() -> None:
    executor = load_executor()
    text, usage = executor.parse_codex_jsonl(
        json.dumps({"type": "message", "payload": {"content": "payload final"}})
    )

    assert text == "payload final"
    assert usage is None


def test_run_retries_config_error_once_with_ignore_user_config(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    calls = []
    monkeypatch.setattr(executor, "resolve_codex_executable", lambda _explicit: "codex")

    def fake_run_process(command, *, stdin, timeout_s, cwd):
        del stdin, timeout_s, cwd
        calls.append(command)
        if len(calls) == 1:
            return type("Completed", (), {
                "returncode": 1, "stdout": "",
                "stderr": "Error loading config.toml: service_tier unknown variant",
            })()
        return type("Completed", (), {
            "returncode": 0,
            "stdout": json.dumps({"item": {"type": "agent_message", "text": "recovered"}}), "stderr": "",
        })()

    monkeypatch.setattr(executor, "run_process", fake_run_process)
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "prompt", "--config", 'service_tier="fast"'])

    result = executor.run(args)

    assert result["ok"] is True
    assert result["text"] == "recovered"
    assert "--ignore-user-config" not in calls[0]
    assert "--ignore-user-config" in calls[1]


def test_run_reports_timeout_and_invalid_output_as_error_envelopes(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    monkeypatch.setattr(executor, "resolve_codex_executable", lambda _explicit: "codex")
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "prompt"])

    monkeypatch.setattr(executor, "run_process", lambda *args, **kwargs: (_ for _ in ()).throw(executor.ExecutorError("TIMEOUT", "codex timed out after 1s")))
    timeout = executor.run(args)
    assert timeout["ok"] is False
    assert timeout["status"] == "timeout"
    assert timeout["error"]["code"] == "TIMEOUT"

    monkeypatch.setattr(executor, "run_process", lambda *args, **kwargs: type("Completed", (), {"returncode": 0, "stdout": '{"type":"turn.completed"}', "stderr": ""})())
    invalid = executor.run(args)
    assert invalid["ok"] is False
    assert invalid["status"] == "invalid_output"
    assert invalid["error"]["code"] == "INVALID_OUTPUT"


def test_run_classifies_nonzero_auth_failure(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    monkeypatch.setattr(executor, "resolve_codex_executable", lambda _explicit: "codex")
    monkeypatch.setattr(
        executor,
        "run_process",
        lambda *args, **kwargs: type("Completed", (), {
            "returncode": 17, "stdout": "", "stderr": "not authenticated; please login",
        })(),
    )
    args = executor.build_parser().parse_args(["--cwd", str(tmp_path), "--prompt", "prompt"])

    result = executor.run(args)

    assert result == {
        "ok": False,
        "status": "auth",
        "text": None,
        "usage": None,
        "exit_code": 17,
        "error": {"code": "AUTH", "message": "codex requires CLI login/authentication"},
    }


def test_run_process_wraps_powershell_shim(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    calls = []
    monkeypatch.setattr(executor.shutil, "which", lambda _: "C:/tools/codex.ps1")

    class FakePopen:
        pid = 1
        returncode = 0

        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(executor.subprocess, "Popen", FakePopen)
    executor.run_process(["codex", "exec"], stdin="prompt", timeout_s=1, cwd=tmp_path)

    assert calls[0][0] == ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "C:/tools/codex.ps1", "exec"]


def test_resolve_codex_executable_skips_windowsapps_and_uses_user_desktop_cli(monkeypatch, tmp_path: Path) -> None:
    executor = load_executor()
    stale_cli = tmp_path / "OpenAI" / "Codex" / "bin" / "codex.exe"
    desktop_cli = stale_cli.parent / "current" / "codex.exe"
    stale_cli.parent.mkdir(parents=True)
    stale_cli.touch()
    desktop_cli.parent.mkdir()
    desktop_cli.touch()
    os.utime(stale_cli, (1, 1))
    os.utime(desktop_cli, (2, 2))
    monkeypatch.delenv("CODEX_EXECUTABLE", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setattr(executor.shutil, "which", lambda _name: "C:/Program Files/WindowsApps/codex.exe")

    assert executor.resolve_codex_executable(None) == str(desktop_cli)


def test_explicit_executable_takes_precedence_over_discovery(tmp_path: Path) -> None:
    executor = load_executor()

    assert executor.resolve_codex_executable(str(tmp_path / "codex.exe")) == str(tmp_path / "codex.exe")
