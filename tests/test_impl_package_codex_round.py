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


def test_extract_session_id_takes_last_session_line_and_tolerates_absence() -> None:
    log = "codex exec\nsession id: 019a\n\nsession id: 019b\n"
    assert codex_round.extract_session_id(log) == "019b"
    assert codex_round.extract_session_id("no session line\n") is None


def test_report_paths_pairs_report_with_raw_backup(tmp_path) -> None:
    report, raw = codex_round.report_paths(tmp_path, "r1", "c")
    assert report.name == "r1-track-c.md"
    assert raw.name == "r1-track-c.raw.md" and raw.parent == report.parent


PROMPT = """公共要求
所有轨都看这里。

## Track A
A 职责
## Track C
C 职责
## Track D
D 职责
"""


def test_split_prompt_separates_common_and_track_sections() -> None:
    common, sections = codex_round.split_prompt(PROMPT)
    assert "公共要求" in common and "## Track" not in common
    assert list(sections) == ["A", "C", "D"]
    assert "A 职责" in sections["A"]
    assert "C 职责" not in sections["A"]


def test_track_prompt_only_carries_common_and_own_section() -> None:
    common, sections = codex_round.split_prompt(PROMPT)
    prompt = codex_round.track_prompt(common, sections, "C", "abc123")
    assert "公共要求" in prompt and "C 职责" in prompt and "对比基线：abc123" in prompt
    assert "A 职责" not in prompt and "D 职责" not in prompt


def test_split_prompt_requires_track_markers() -> None:
    with pytest.raises(ValueError, match="## Track"):
        codex_round.split_prompt("只有公共部分，没有任何段标记\n")


def test_main_rejects_empty_model_or_effort_before_launching(tmp_path, monkeypatch) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("公共\n\n## Track A\nA 职责\n", encoding="utf-8")
    for flag, args in (("model", ["--model", " ", "--effort", "e"]), ("effort", ["--model", "m", "--effort", ""])):
        monkeypatch.setattr(sys, "argv", [
            "codex_round.py", "--package", "p", "--run", "r", "--base", "b",
            "--prompt-file", str(prompt), "--tracks", "A", "--new", *args,
        ])
        monkeypatch.setattr(codex_round.shutil, "which", lambda _: pytest.fail("不应启动 codex"))
        with pytest.raises(SystemExit) as exc:
            codex_round.main()
        assert exc.value.code == 2


def test_main_rejects_missing_selected_track_before_launching(tmp_path, monkeypatch) -> None:
    prompt = tmp_path / "prompt.md"
    prompt.write_text("公共\n\n## Track A\nA 职责\n", encoding="utf-8")
    monkeypatch.setattr(sys, "argv", [
        "codex_round.py", "--package", "p", "--run", "r", "--base", "b",
        "--prompt-file", str(prompt), "--tracks", "A,C", "--new", "--model", "m", "--effort", "e",
    ])
    monkeypatch.setattr(codex_round.shutil, "which", lambda _: pytest.fail("不应启动 codex"))
    with pytest.raises(SystemExit) as exc:
        codex_round.main()
    assert exc.value.code == 2
