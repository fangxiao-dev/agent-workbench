from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compaction_pressure import build_report, pressure_report  # noqa: E402


def test_interval_worsening_is_high() -> None:
    report = pressure_report(
        [
            "00:00:00",
            "00:56:00",
            "01:36:00",
            "01:51:00",
            "02:03:00",
        ],
    )

    assert report["compactions"] == 5
    assert report["last_interval_min"] == 12
    assert report["shrinking"] is True
    assert report["high"] is True


def test_many_compactions_with_stable_intervals_are_not_high() -> None:
    report = pressure_report(
        [
            "00:00:00",
            "00:50:00",
            "01:40:00",
            "02:30:00",
            "03:20:00",
        ],
    )

    assert report["compactions"] == 5
    assert report["shrinking"] is False
    assert report["high"] is False


def test_zero_compactions_returns_safe_false() -> None:
    report = pressure_report([])

    assert report["compactions"] == 0
    assert report["last_interval_min"] is None
    assert report["high"] is False
    assert "zero compactions" in str(report["explanation"])


def test_missing_matching_rollout_returns_safe_false() -> None:
    report = build_report(ROOT / "scripts", ROOT / "never-current-worktree")

    assert report["compactions"] == 0
    assert report["high"] is False
    assert "no rollout" in str(report["explanation"])
