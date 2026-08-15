from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/situation.py"
FIXTURES = ROOT / "tests/fixtures/situations"


def _fixture_dirs() -> list[Path]:
    return sorted(path for path in FIXTURES.iterdir() if path.is_dir())


def _primary_slugs(result: dict) -> list[str]:
    selected = result.get("selected")
    if selected:
        return [selected["slug"]]
    return [item["slug"] for item in result.get("parallel_matches", [])]


@pytest.mark.parametrize("package", _fixture_dirs(), ids=lambda path: path.name)
def test_situation_render(package: Path) -> None:
    expected = json.loads((package / "expected.json").read_text(encoding="utf-8"))
    completed = subprocess.run(
        [sys.executable, str(CLI), "render", "--package", str(package), "--json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert completed.returncode == 0, (
        f"{package.name}: render failed\nstdout={completed.stdout}\nstderr={completed.stderr}\n"
        f"source={expected['source']}\nscenario={expected['scenario']}"
    )
    try:
        rendered = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        pytest.fail(
            f"{package.name}: render did not return JSON: {exc}\n"
            f"stdout={completed.stdout}\nstderr={completed.stderr}"
        )

    primary = _primary_slugs(rendered)
    assert set(primary) == set(expected["expected_primary"]), (
        f"{package.name}: primary mismatch; expected={expected['expected_primary']} "
        f"actual={primary}; source={expected['source']}; scenario={expected['scenario']}"
    )
    assert rendered.get("highest_match_layer") == expected["expected_layer"], (
        f"{package.name}: layer mismatch; expected={expected['expected_layer']} "
        f"actual={rendered.get('highest_match_layer')}; scenario={expected['scenario']}"
    )

    secondary = [item["slug"] for item in rendered.get("other_matches", [])]
    assert secondary == expected.get("expected_secondary", []), (
        f"{package.name}: secondary mismatch; expected={expected.get('expected_secondary', [])} "
        f"actual={secondary}; scenario={expected['scenario']}"
    )

    suppressed = {item["slug"] for item in rendered.get("suppressed_matches", [])}
    missing_suppressed = set(expected.get("expected_suppressed", [])) - suppressed
    assert not missing_suppressed, (
        f"{package.name}: expected suppressed rows were not exercised: {sorted(missing_suppressed)}; "
        f"actual={sorted(suppressed)}; scenario={expected['scenario']}"
    )

    visible = set(primary + secondary)
    forbidden = visible.intersection(expected.get("must_not_hit", []))
    assert not forbidden, (
        f"{package.name}: must_not_hit appeared in active render: {sorted(forbidden)}; "
        f"source={expected['source']}; scenario={expected['scenario']}"
    )
