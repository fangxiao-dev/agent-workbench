from __future__ import annotations

import os
from pathlib import Path

from scripts.executor_env import load_executor_env


def test_load_executor_env_sets_only_missing_nonempty_values(monkeypatch, tmp_path: Path) -> None:
    (tmp_path / ".env").write_text(
        "# local executables\nCODEX_EXECUTABLE=codex-local\nCLAUDE_EXECUTABLE='claude local'\nGROK_EXECUTABLE=\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("CODEX_EXECUTABLE", raising=False)
    monkeypatch.setenv("CLAUDE_EXECUTABLE", "process-claude")
    monkeypatch.delenv("GROK_EXECUTABLE", raising=False)

    load_executor_env(tmp_path)

    assert os.environ["CODEX_EXECUTABLE"] == "codex-local"
    assert os.environ["CLAUDE_EXECUTABLE"] == "process-claude"
    assert "GROK_EXECUTABLE" not in os.environ
