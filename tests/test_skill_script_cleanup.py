from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CALL_DS = ROOT / "skills" / "call-ds-in-claude" / "scripts" / "call_ds.py"
HITL_TEMPLATE = (
    ROOT / "skills" / "diagnosing-bugs" / "scripts" / "hitl_loop_template.py"
)


def load_call_ds():
    spec = importlib.util.spec_from_file_location("call_ds_under_test", CALL_DS)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_retired_planning_skill_is_removed() -> None:
    assert not (ROOT / "skills" / "planning-with-files").exists()
    assert not (ROOT / "tests" / "test_planning_with_files_contract.py").exists()


def test_target_skills_have_no_windows_shell_scripts() -> None:
    for skill_name in ("call-ds-in-claude", "diagnosing-bugs"):
        scripts = ROOT / "skills" / skill_name / "scripts"
        assert scripts.is_dir()
        assert not list(scripts.glob("*.ps1"))
        assert not list(scripts.glob("*.sh"))


def test_skill_docs_reference_python_replacements() -> None:
    call_ds_doc = (ROOT / "skills" / "call-ds-in-claude" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    diagnosing_doc = (ROOT / "skills" / "diagnosing-bugs" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert "call_ds.py" in call_ds_doc
    assert "call-ds.ps1" not in call_ds_doc
    assert "pwsh -NoProfile -File" not in call_ds_doc
    assert "hitl_loop_template.py" in diagnosing_doc
    assert "hitl-loop.template.ps1" not in diagnosing_doc
    assert "hitl-loop.template.sh" not in diagnosing_doc


def test_call_ds_scopes_claude_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    call_ds = load_call_ds()
    monkeypatch.setenv("CLAUDE_CODE_PARENT_ONLY", "leak")
    monkeypatch.setenv("CLAUDECODE", "leak")

    environment = call_ds.build_child_environment("test-model", "test-key")

    assert "CLAUDE_CODE_PARENT_ONLY" not in environment
    assert "CLAUDECODE" not in environment
    assert environment["ANTHROPIC_BASE_URL"] == "https://api.deepseek.com/anthropic"
    assert environment["ANTHROPIC_MODEL"] == "test-model"
    assert "ANTHROPIC_API_KEY" not in environment


def test_call_ds_parses_python_cli_options() -> None:
    call_ds = load_call_ds()

    args = call_ds.parse_args(
        [
            "--prompt",
            "inspect code",
            "--cwd",
            str(ROOT),
        ]
    )

    assert args.prompt == "inspect code"
    assert args.cwd == ROOT
    assert args.clip_chars == 400
    assert args.idle_timeout_sec == 900
    assert args.heartbeat_sec == 60


def test_hitl_template_runs_cross_platform() -> None:
    result = subprocess.run(
        [sys.executable, str(HITL_TEMPLATE)],
        input="\ny\nboom\n",
        text=True,
        capture_output=True,
        check=True,
        timeout=10,
    )

    assert "ERRORED=y" in result.stdout
    assert "ERROR_MSG=boom" in result.stdout
