from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import quote

import pytest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from compaction_pressure import build_report, pressure_report  # noqa: E402
from rollout_pulse import compaction_intervals, minutes_between  # noqa: E402


SCRIPT = ROOT / "scripts/compaction_pressure.py"


def _write_grok_session(
    root: Path,
    cwd: Path,
    *,
    signals: dict[str, object],
    session_id: str = "session-1",
    updated_at: str = "2026-08-18T10:00:00Z",
) -> Path:
    session = root / quote(str(cwd.resolve()), safe="") / session_id
    session.mkdir(parents=True)
    (session / "summary.json").write_text(
        json.dumps(
            {
                "cwd": str(cwd.resolve()),
                "created_at": "2026-08-18T09:00:00Z",
                "updated_at": updated_at,
                "current_model_id": "grok-test",
            }
        ),
        encoding="utf-8",
    )
    (session / "signals.json").write_text(json.dumps(signals), encoding="utf-8")
    return session


def _write_codex_rollout(root: Path, cwd: Path, *, mtime: float | None = None) -> Path:
    path = root / "2026" / "08" / "rollout-test.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {
            "type": "session_meta",
            "timestamp": "2026-08-18T09:00:00Z",
            "payload": {"cwd": str(cwd.resolve())},
        },
        {"type": "compacted", "timestamp": "2026-08-18T09:10:00Z"},
        {"type": "compacted", "timestamp": "2026-08-18T10:00:00Z"},
    ]
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    if mtime is not None:
        import os

        os.utime(path, (mtime, mtime))
    return path


@pytest.fixture
def fixture_root() -> Path:
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        yield Path(temporary)


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


@pytest.mark.parametrize(
    ("signals", "expected_high"),
    [
        (
            {"turnCount": 9, "compactionCount": 1, "totalTokensBeforeCompaction": 364733,
             "contextWindowUsage": 80, "contextTokensUsed": 400000,
             "contextWindowTokens": 500000, "sessionDurationSeconds": 10809,
             "toolCallCount": 557},
            True,
        ),
        (
            {"turnCount": 9, "compactionCount": 2, "contextWindowUsage": 66,
             "contextTokensUsed": 331760, "contextWindowTokens": 500000,
             "sessionDurationSeconds": 3600, "toolCallCount": 557},
            True,
        ),
        (
            {"turnCount": 9, "compactionCount": 2, "contextWindowUsage": 79,
             "contextTokensUsed": 395000, "contextWindowTokens": 500000,
             "sessionDurationSeconds": 3602, "toolCallCount": 557},
            False,
        ),
    ],
    ids=["usage-threshold", "average-cadence-threshold", "below-both-thresholds"],
)
def test_grok_fixture_uses_only_available_pressure_signals(
    fixture_root: Path,
    signals: dict[str, object],
    expected_high: bool,
) -> None:
    cwd = fixture_root / "worktree"
    cwd.mkdir()
    grok_root = fixture_root / "grok" / "sessions"
    _write_grok_session(grok_root, cwd, signals=signals)

    report = build_report(
        fixture_root / "codex" / "sessions",
        cwd,
        grok_sessions_root=grok_root,
        host="grok",
    )

    assert set(report) == {
        "compactions",
        "last_interval_min",
        "shrinking",
        "high",
        "explanation",
    }
    assert report["compactions"] == signals["compactionCount"]
    assert report["last_interval_min"] is None
    assert report["shrinking"] is False
    assert report["high"] is expected_high
    assert "grok" in str(report["explanation"])
    assert "contextWindowUsage" in str(report["explanation"])
    assert "compaction timestamps" in str(report["explanation"])


def test_codex_fixture_path_keeps_timestamp_interval_behavior(fixture_root: Path) -> None:
    cwd = fixture_root / "worktree"
    cwd.mkdir()
    codex_root = fixture_root / "codex" / "sessions"
    _write_codex_rollout(codex_root, cwd)

    report = build_report(codex_root, cwd, grok_sessions_root=fixture_root / "missing-grok", host="codex")

    assert report["compactions"] == 2
    assert report["last_interval_min"] == 50
    assert report["shrinking"] is False
    assert report["high"] is False
    assert str(report["explanation"]).startswith("codex:")


def test_auto_chooses_the_newer_matching_host(fixture_root: Path) -> None:
    cwd = fixture_root / "worktree"
    cwd.mkdir()
    codex_root = fixture_root / "codex" / "sessions"
    grok_root = fixture_root / "grok" / "sessions"
    _write_codex_rollout(codex_root, cwd, mtime=1_700_000_000)
    _write_grok_session(
        grok_root,
        cwd,
        signals={"compactionCount": 1, "contextWindowUsage": 80, "sessionDurationSeconds": 60},
        updated_at="2026-08-18T10:00:00Z",
    )

    report = build_report(codex_root, cwd, grok_sessions_root=grok_root)

    assert report["high"] is True
    assert str(report["explanation"]).startswith("grok:")


def test_host_flag_explicitly_selects_one_source(fixture_root: Path) -> None:
    cwd = fixture_root / "worktree"
    cwd.mkdir()
    codex_root = fixture_root / "codex" / "sessions"
    grok_root = fixture_root / "grok" / "sessions"
    _write_codex_rollout(codex_root, cwd, mtime=1_700_000_000)
    _write_grok_session(
        grok_root,
        cwd,
        signals={"compactionCount": 1, "contextWindowUsage": 80, "sessionDurationSeconds": 60},
    )

    for host, expected_prefix, expected_compactions in (("codex", "codex:", 2), ("grok", "grok:", 1)):
        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--host",
                host,
                "--sessions-root",
                str(codex_root),
                "--grok-sessions-root",
                str(grok_root),
                "--cwd",
                str(cwd),
            ],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        report = json.loads(completed.stdout)
        assert str(report["explanation"]).startswith(expected_prefix)
        assert report["compactions"] == expected_compactions


def test_missing_grok_root_degrades_to_safe_false(fixture_root: Path) -> None:
    report = build_report(
        fixture_root / "unused-codex",
        fixture_root / "worktree",
        grok_sessions_root=fixture_root / "missing-grok",
        host="grok",
    )

    assert report["compactions"] == 0
    assert report["last_interval_min"] is None
    assert report["high"] is False
    assert "grok" in str(report["explanation"])
    assert "does not exist" in str(report["explanation"])
