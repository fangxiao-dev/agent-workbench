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

    assert executor.build_cmd("grok", "caller-owned prompt", args) == [
        "grok", "-p", "caller-owned prompt", "--max-turns", "120", "--output-format",
        "streaming-json", "--cwd", str(tmp_path), "-m", "grok-test", "--effort", "high",
        "--worktree", "isolated", "--tools", "read_file,grep", "--allow", "Bash(git *)",
        "--allow", "Read(*)", "--deny", "Bash(git push*)", "--always-approve",
        "--no-subagents", "--rules", "stay scoped",
    ]


def test_default_command_has_no_injected_policy_or_prompt(tmp_path: Path) -> None:
    executor = load_executor()
    args = executor.parse_args(["--cwd", str(tmp_path), "--prompt", "use exactly this prompt"])

    assert executor.build_cmd("grok", args.prompt, args) == [
        "grok", "-p", "use exactly this prompt", "--max-turns", "120", "--output-format",
        "streaming-json", "--cwd", str(tmp_path),
    ]
    help_text = executor.build_parser().format_help()
    for removed in ("--role", "--resume", "--plan-file", "--context-file"):
        assert removed not in help_text


def test_grok_executable_prefers_explicit_then_new_and_legacy_environment(monkeypatch) -> None:
    executor = load_executor()
    monkeypatch.setenv("GROK_EXECUTABLE", "env-grok")
    monkeypatch.setenv("GROK_BIN", "legacy-grok")

    assert executor.resolve_grok_bin("explicit-grok") == "explicit-grok"
    assert executor.resolve_grok_bin() == "env-grok"

    monkeypatch.delenv("GROK_EXECUTABLE")
    assert executor.resolve_grok_bin() == "legacy-grok"


def test_prompt_file_is_used_without_injection(tmp_path: Path) -> None:
    executor = load_executor()
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text("from caller file", encoding="utf-8")
    args = executor.parse_args(["--prompt-file", str(prompt_file)])

    assert executor.read_prompt(args) == "from caller file"


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
