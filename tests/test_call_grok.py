from __future__ import annotations

import importlib.util
import io
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "call-grok" / "scripts" / "grok_task.py"
SKILL = ROOT / "skills" / "call-grok" / "SKILL.md"
CONTRACT = ROOT / "skills" / "call-grok" / "references" / "caller-contract.md"


def load_executor():
    spec = importlib.util.spec_from_file_location("call_grok_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_build_command_passes_only_explicit_caller_configuration(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.parse_args(
        [
            "--cwd", str(tmp_path), "--prompt", "caller-owned prompt", "--model", "grok-test",
            "--effort", "high", "--tools", "read_file,grep", "--allow", "Bash(git *)",
            "--allow", "Read(*)", "--deny", "Bash(git push*)", "--always-approve",
            "--no-subagents", "--worktree", "isolated", "--rules", "stay scoped",
        ]
    )

    assert executor.build_cmd("grok", args, prompt="caller-owned prompt") == [
        "grok", "-p", "caller-owned prompt", "--max-turns", "100", "--output-format",
        "streaming-json", "--cwd", str(tmp_path), "-m", "grok-test", "--effort", "high",
        "--worktree", "isolated", "--tools", "read_file,grep", "--allow", "Bash(git *)",
        "--allow", "Read(*)", "--deny", "Bash(git push*)", "--always-approve",
        "--no-subagents", "--rules", "stay scoped",
    ]


def test_default_command_omits_tools_keeps_always_approve(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.parse_args(["--cwd", str(tmp_path), "--prompt", "use exactly this prompt"])

    assert args.stall_timeout_sec == 900
    assert args.overall_timeout_sec == 900
    assert args.no_subagents is False
    cmd = executor.build_cmd("grok", args, prompt=args.prompt)
    assert cmd == [
        "grok", "-p", "use exactly this prompt", "--max-turns", "100", "--output-format",
        "streaming-json", "--cwd", str(tmp_path), "--always-approve",
    ]
    assert "--tools" not in cmd
    assert "--no-subagents" not in cmd
    help_text = executor.build_parser().format_help()
    for removed in ("--role", "--resume", "--plan-file", "--context-file"):
        assert removed not in help_text


def test_tools_empty_string_is_passed_through(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.parse_args(["--cwd", str(tmp_path), "--prompt", "task", "--tools", ""])
    cmd = executor.build_cmd("grok", args, prompt="task")
    assert "--tools" in cmd
    assert cmd[cmd.index("--tools") + 1] == ""


def test_always_approve_is_default_and_can_be_disabled(tmp_path: Path) -> None:
    executor = load_executor()
    default_args = executor.parse_args(["--cwd", str(tmp_path), "--prompt", "task"])
    disabled_args = executor.parse_args(
        ["--cwd", str(tmp_path), "--prompt", "task", "--no-always-approve"]
    )

    assert default_args.always_approve is True
    assert "--always-approve" in executor.build_cmd("grok", default_args, prompt="task")
    assert disabled_args.always_approve is False
    assert "--always-approve" not in executor.build_cmd("grok", disabled_args, prompt="task")


def test_grok_executable_prefers_explicit_then_new_and_legacy_environment(monkeypatch) -> None:
    executor = load_executor()
    monkeypatch.setenv("GROK_EXECUTABLE", "env-grok")
    monkeypatch.setenv("GROK_BIN", "legacy-grok")

    assert executor.resolve_grok_bin("explicit-grok") == "explicit-grok"
    assert executor.resolve_grok_bin() == "env-grok"

    monkeypatch.delenv("GROK_EXECUTABLE")
    assert executor.resolve_grok_bin() == "legacy-grok"


def test_resolve_grok_bin_missing_path_like_returns_none(tmp_path: Path) -> None:
    executor = load_executor()
    missing = tmp_path / "no-such" / "grok.exe"
    assert executor.resolve_grok_bin(str(missing)) is None


def test_prompt_file_passes_through_to_grok(tmp_path: Path) -> None:
    executor = load_executor()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from caller file", encoding="utf-8")
    args = executor.parse_args(["--prompt-file", str(prompt_file), "--cwd", str(tmp_path)])

    resolved = executor.resolve_prompt_file(prompt_file)
    cmd = executor.build_cmd("grok", args, prompt_file=resolved)
    assert "-p" not in cmd
    assert cmd[0:3] == ["grok", "--prompt-file", str(resolved)]
    assert "from caller file" not in cmd


def test_run_with_liveness_parses_stream_and_nonzero_exit(monkeypatch) -> None:
    executor = load_executor()

    class FakePopen:
        pid = 1

        def __init__(self, _command, **_kwargs):
            self.stdout = io.StringIO(
                "\n".join([
                    json.dumps({"type": "text", "data": "final answer"}),
                    json.dumps({"type": "end", "usage": {"input_tokens": 3}}),
                ])
            )
            self.stderr = io.StringIO("")
            self.returncode = 0

        def wait(self):
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(executor.subprocess, "Popen", FakePopen)
    success = executor.run_with_liveness(["grok"], 10, 10, 0)

    assert success["status"] == "completed"
    assert success["text"] == "final answer"
    assert success["usage"] == {"input_tokens": 3}

    class FailingPopen(FakePopen):
        def __init__(self, command, **kwargs):
            super().__init__(command, **kwargs)
            self.returncode = 9

    monkeypatch.setattr(executor.subprocess, "Popen", FailingPopen)
    failure = executor.run_with_liveness(["grok"], 10, 10, 0)

    assert failure["status"] == "error"
    assert failure["error_message"] == "grok exited with code 9"


def test_non_json_stdout_does_not_pollute_text(monkeypatch) -> None:
    executor = load_executor()

    class FakePopen:
        pid = 1

        def __init__(self, _command, **_kwargs):
            self.stdout = io.StringIO(
                "\n".join([
                    "not-json-progress",
                    json.dumps({"type": "text", "data": "only this"}),
                    json.dumps({"type": "end"}),
                ])
            )
            self.stderr = io.StringIO("")
            self.returncode = 0

        def wait(self):
            return self.returncode

        def poll(self):
            return self.returncode

    monkeypatch.setattr(executor.subprocess, "Popen", FakePopen)
    result = executor.run_with_liveness(["grok"], 10, 10, 0)
    assert result["status"] == "completed"
    assert result["text"] == "only this"
    assert "not-json-progress" not in result["text"]


def test_liveness_terminal_status_is_not_overwritten_by_late_events() -> None:
    executor = load_executor()
    text_parts: list[str] = []
    status, *_rest, last = executor.apply_stream_event(
        {"type": "error", "message": "late failure"},
        status="stalled",
        text_parts=text_parts,
        session_id=None,
        stop_reason=None,
        num_turns=None,
        usage=None,
        max_turns_seen=False,
        error_message="stalled: no events",
    )
    assert status == "stalled"
    assert last == "error"

    status2, *_rest2, last2 = executor.apply_stream_event(
        {"type": "end", "stopReason": "cancelled"},
        status="timeout",
        text_parts=text_parts,
        session_id=None,
        stop_reason=None,
        num_turns=None,
        usage=None,
        max_turns_seen=False,
        error_message="overall timeout",
    )
    assert status2 == "timeout"
    assert last2 == "end"


def test_main_writes_canonical_envelopes(monkeypatch, capsys, tmp_path: Path) -> None:
    executor = load_executor()
    monkeypatch.setattr(executor, "resolve_grok_bin", lambda _explicit=None: "grok")
    monkeypatch.setattr(executor, "preflight", lambda *_args, **_kwargs: (True, "ok", {}))
    monkeypatch.setattr(
        executor,
        "run_with_liveness",
        lambda **_kwargs: {"status": "max_turns", "text": "partial", "usage": {}, "error_message": None},
    )

    assert executor.main(["--cwd", str(tmp_path), "--prompt", "task"]) == 2
    assert json.loads(capsys.readouterr().out) == {
        "ok": False,
        "status": "max_turns",
        "text": "partial",
        "usage": {},
        "exit_code": 2,
        "error": {"code": "MAX_TURNS", "message": "max turns"},
    }

    monkeypatch.setattr(executor, "resolve_grok_bin", lambda _explicit=None: None)
    assert executor.main(["--prompt", "task"]) == 1
    preflight = json.loads(capsys.readouterr().out)
    assert preflight["status"] == "preflight_failed"
    assert preflight["error"]["code"] == "PREFLIGHT_FAILED"
    assert set(preflight) == {"ok", "status", "text", "usage", "exit_code", "error"}


def test_main_prompt_file_builds_without_inline_prompt(monkeypatch, capsys, tmp_path: Path) -> None:
    executor = load_executor()
    prompt_file = tmp_path / "p.txt"
    prompt_file.write_text("file body", encoding="utf-8")
    captured: dict = {}

    def fake_run(**kwargs):
        captured["cmd"] = kwargs["cmd"]
        return {"status": "completed", "text": "ok", "usage": {}, "error_message": None}

    monkeypatch.setattr(executor, "resolve_grok_bin", lambda _explicit=None: "grok")
    monkeypatch.setattr(executor, "preflight", lambda *_a, **_k: (True, "ok", {}))
    monkeypatch.setattr(executor, "run_with_liveness", fake_run)

    assert executor.main(["--prompt-file", str(prompt_file), "--cwd", str(tmp_path)]) == 0
    cmd = captured["cmd"]
    assert "--prompt-file" in cmd
    assert "-p" not in cmd
    assert "file body" not in cmd


def test_main_spills_long_prompt_to_temp_file(monkeypatch, capsys, tmp_path: Path) -> None:
    executor = load_executor()
    long_prompt = "x" * (executor.MAX_INLINE_PROMPT_CHARS + 1)
    captured: dict = {}

    def fake_run(**kwargs):
        captured["cmd"] = kwargs["cmd"]
        return {"status": "completed", "text": "ok", "usage": {}, "error_message": None}

    monkeypatch.setattr(executor, "resolve_grok_bin", lambda _explicit=None: "grok")
    monkeypatch.setattr(executor, "preflight", lambda *_a, **_k: (True, "ok", {}))
    monkeypatch.setattr(executor, "run_with_liveness", fake_run)

    assert executor.main(["--prompt", long_prompt, "--cwd", str(tmp_path)]) == 0
    cmd = captured["cmd"]
    assert "--prompt-file" in cmd
    assert "-p" not in cmd
    assert long_prompt not in cmd


def test_partial_and_liveness_statuses_have_stable_error_codes() -> None:
    executor = load_executor()

    for status, code in (
        ("max_turns", "MAX_TURNS"),
        ("stalled", "STALLED"),
        ("timeout", "TIMEOUT"),
        ("cancelled", "CANCELLED"),
        ("error", "EXECUTION_FAILED"),
    ):
        result = executor.envelope(status, text="partial", usage=None, exit_code=1)
        assert result["ok"] is False
        assert result["error"] == {"code": code, "message": status.replace("_", " ")}
        assert set(result) == {"ok", "status", "text", "usage", "exit_code", "error"}


def test_docs_and_help_do_not_expose_presets() -> None:
    executor = load_executor()
    text = "\n".join([SKILL.read_text(encoding="utf-8"), CONTRACT.read_text(encoding="utf-8")]).lower()

    for removed in ("--role", "reviewer", "explore", "implement", "--resume", "--plan-file"):
        assert removed not in text
    assert "--role" not in executor.build_parser().format_help()
    assert "unset (not passed)" in CONTRACT.read_text(encoding="utf-8")
