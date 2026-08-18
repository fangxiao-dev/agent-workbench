from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compaction_pressure import build_report, pressure_report  # noqa: E402
from rollout_pulse import compaction_intervals, minutes_between  # noqa: E402


def test_cross_midnight_intervals_use_full_timestamps() -> None:
    compactions = [
        "2026-08-17T23:06:51.123Z",
        "2026-08-18T00:18:24.456Z",
        "2026-08-18T01:18:42.789Z",
        "2026-08-18T02:45:36.012Z",
        "2026-08-18T03:53:04.345Z",
        "2026-08-18T05:18:19.678Z",
    ]

    intervals = compaction_intervals(compactions)

    assert minutes_between(compactions[0], compactions[1]) > 0
    assert [f"{interval:.0f}m" for interval in intervals] == [
        "72m",
        "60m",
        "87m",
        "67m",
        "85m",
    ]


def test_invalid_compaction_timestamp_fails_closed() -> None:
    report = pressure_report(
        [
            "2026-08-17T23:06:51.123Z",
            "",
            "not-a-timestamp",
        ],
    )

    assert minutes_between("2026-08-17T23:06:51.123Z", "") is None
    assert minutes_between("2026-08-17T23:06:51.123Z", "not-a-timestamp") is None
    assert report["compactions"] == 3
    assert report["last_interval_min"] is None
    assert report["shrinking"] is False
    assert report["high"] is False
    assert "invalid" in str(report["explanation"])


def test_interval_worsening_is_high() -> None:
    report = pressure_report(
        [
            "2026-08-17T00:00:00Z",
            "2026-08-17T00:56:00Z",
            "2026-08-17T01:36:00Z",
            "2026-08-17T01:51:00Z",
            "2026-08-17T02:03:00Z",
        ],
    )

    assert report["compactions"] == 5
    assert report["last_interval_min"] == 12
    assert report["shrinking"] is True
    assert report["high"] is True


def test_many_compactions_with_stable_intervals_are_not_high() -> None:
    report = pressure_report(
        [
            "2026-08-17T00:00:00Z",
            "2026-08-17T00:50:00Z",
            "2026-08-17T01:40:00Z",
            "2026-08-17T02:30:00Z",
            "2026-08-17T03:20:00Z",
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
