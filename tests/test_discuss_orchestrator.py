from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "discuss-ledger" / "scripts" / "discuss_orchestrator.py"
SRC = ROOT / "skills" / "discuss-ledger" / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def load_orchestrator():
    spec = importlib.util.spec_from_file_location("discuss_orchestrator_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_fake_orchestrator_runs_round_robin_without_real_agent_clis(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()

    exit_code = orchestrator.main(
        [
            "--root",
            str(tmp_path),
            "--topic",
            "MCP orchestration smoke",
            "--slug",
            "mcp-smoke",
            "--agents",
            "codex,claude",
            "--max-rounds",
            "2",
            "--fake",
        ]
    )

    assert exit_code == 0

    ledger_path = tmp_path / "docs" / "exchange" / "discuss" / "discuss-mcp-smoke.md"
    text = ledger_path.read_text(encoding="utf-8")
    assert "participants: [codex, claude]" in text
    assert "next: claude" in text or "next: codex" in text or "next: —" in text
    assert "Fake codex opening concern" in text
    assert "Fake claude convergence" in text


def test_agent_result_schema_accepts_orchestrator_payload_shape() -> None:
    schema_path = ROOT / "skills" / "discuss-ledger" / "schemas" / "agent-result.schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["type"] == "object"
    assert {"convergences", "contests", "new_points"}.issubset(schema["properties"])


def test_orchestrator_parser_defaults_match_interactive_use() -> None:
    orchestrator = load_orchestrator()

    args = orchestrator.build_parser().parse_args(["--topic", "docs/plan.md"])

    assert args.agents == "codex,claude"
    assert args.max_rounds == 5
    assert args.timeout_s == 300


def test_resolve_root_and_topic_detects_any_git_worktree_shape(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    project = tmp_path / "some-container" / "feature-checkout"
    target = project / "docs" / "impl-plans" / "plan.md"
    (project / ".git").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("# Plan\n", encoding="utf-8")

    root, topic = orchestrator.resolve_root_and_topic(str(tmp_path), str(target))

    assert root == project.resolve()
    assert topic == "docs/impl-plans/plan.md"


def test_resolve_root_and_topic_detects_dot_worktrees_relative_paths(tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    project = tmp_path / ".worktrees" / "raw-material-production-design"
    target = project / "docs" / "impl-plans" / "patch.md"
    (project / ".git").mkdir(parents=True)
    target.parent.mkdir(parents=True)
    target.write_text("# Patch\n", encoding="utf-8")

    root, topic = orchestrator.resolve_root_and_topic(str(tmp_path), ".worktrees/raw-material-production-design/docs/impl-plans/patch.md")

    assert root == project.resolve()
    assert topic == "docs/impl-plans/patch.md"


def test_parse_codex_jsonl_extracts_nested_final_result() -> None:
    orchestrator = load_orchestrator()
    final = {
        "convergences": [],
        "contests": [],
        "new_points": [{"summary": "S", "body": "B"}],
    }
    stream = "\n".join(
        [
            json.dumps({"type": "turn_started"}),
            json.dumps({"type": "message", "payload": {"content": json.dumps(final)}}),
        ]
    )

    assert orchestrator.parse_codex_jsonl(stream) == final


def test_normalize_result_rejects_missing_required_shape() -> None:
    orchestrator = load_orchestrator()

    try:
        orchestrator.normalize_result({"convergences": [], "contests": []})
    except orchestrator.AdapterError as exc:
        assert exc.code == "INVALID_JSON"
        assert "missing top-level keys" in exc.message
    else:
        raise AssertionError("expected AdapterError")


def test_run_claude_uses_target_root_for_process(monkeypatch, tmp_path: Path) -> None:
    orchestrator = load_orchestrator()
    calls = []

    def fake_run_process(command, *, stdin=None, timeout_s=900, cwd=None):
        del timeout_s
        calls.append((command, stdin, cwd))

        class Completed:
            returncode = 0
            stdout = json.dumps({"convergences": [], "contests": [], "new_points": []})
            stderr = ""

        return Completed()

    monkeypatch.setattr(orchestrator, "run_process", fake_run_process)

    assert orchestrator.run_claude("prompt", tmp_path, 10) == {
        "convergences": [],
        "contests": [],
        "new_points": [],
    }
    command, stdin, cwd = calls[0]
    assert command[:9] == [
        "claude",
        "-p",
        "--no-session-persistence",
        "--effort",
        "low",
        "--disable-slash-commands",
        "--tools",
        "",
        "--system-prompt",
    ]
    assert command[10] == "--output-format"
    assert command[11] == "json"
    assert "prompt" not in command
    assert stdin == "prompt"
    assert cwd == tmp_path


def test_run_process_wraps_windows_powershell_shims(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []

    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"C:/tools/{exe}.ps1")

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.pid = 123
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)

    orchestrator.run_process(["codex", "--version"])

    assert calls[0][0][:5] == [
        "powershell",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
    ]
    assert calls[0][0][5:] == ["C:/tools/codex.ps1", "--version"]


def test_run_process_wraps_windows_cmd_shims(monkeypatch) -> None:
    orchestrator = load_orchestrator()
    calls = []

    monkeypatch.setattr(orchestrator.shutil, "which", lambda exe: f"C:/tools/{exe}.CMD")

    class FakePopen:
        def __init__(self, command, **kwargs):
            calls.append((command, kwargs))
            self.pid = 123
            self.returncode = 0

        def communicate(self, input=None, timeout=None):
            del input, timeout
            return "", ""

    monkeypatch.setattr(orchestrator.subprocess, "Popen", FakePopen)

    orchestrator.run_process(["claude", "--version"])

    assert calls[0][0] == ["cmd", "/c", "C:/tools/claude.CMD", "--version"]
