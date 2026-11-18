from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

CLI = Path(__file__).resolve().parents[1] / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"


def _help(tmp_path: Path, *args: str) -> str:
    env = {**os.environ, "TMPDIR": str(tmp_path), "TEMP": str(tmp_path), "TMP": str(tmp_path)}
    result = subprocess.run(
        [sys.executable, str(CLI), "--package", str(tmp_path), *args, "--help"],
        capture_output=True, text=True, encoding="utf-8", env=env, cwd=tmp_path,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout


@pytest.mark.parametrize("args, purpose, example", [
    (("package", "status"), "without writing anything", "package status"),
    (("evidence", "check"), "without recording anything", "evidence check --file"),
])
def test_help_explains_purpose_when_to_use_and_gives_an_example(tmp_path: Path, args, purpose, example) -> None:
    text = _help(tmp_path, *args)
    assert purpose in text
    assert "Use " in text
    assert "Example:" in text and example in text
