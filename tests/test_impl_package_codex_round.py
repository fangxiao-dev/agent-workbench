from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "plugin-marketplace/plugins/impl-package/scripts/review"))
import codex_round  # noqa: E402

HEAD = "a" * 40


def _report(verdict="PASS", head=HEAD, run="r1", track="Track A"):
    return f"verdict: {verdict}\nreviewed-head: {head}\nreview-run: {run}\nreview-track: {track}\n\nbody\n"


def test_extract_report_takes_last_verdict_block_and_stops_at_token_footer() -> None:
    log = "noise\nverdict: FAIL\nold\n" + _report() + "tokens used\n123\n"
    assert codex_round.extract_report(log) == _report().strip() + "\n"
    with pytest.raises(ValueError):
        codex_round.extract_report("no report here")


def test_validate_header_checks_head_run_track_and_verdict() -> None:
    assert codex_round.validate_header(_report(), HEAD, "r1", "Track A") == "PASS"
    for bad in (_report(head="b" * 40), _report(run="r2"), _report(track="Track C"), _report(verdict="MAYBE")):
        with pytest.raises(ValueError):
            codex_round.validate_header(bad, HEAD, "r1", "Track A")
