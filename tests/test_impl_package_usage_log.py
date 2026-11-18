from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "plugin-marketplace/plugins/impl-package/scripts"
sys.path.insert(0, str(SCRIPTS))
import impl_package_state  # noqa: E402
import impl_package_usage_summary  # noqa: E402
from impl_package_runtime import usage_log  # noqa: E402


@pytest.fixture()
def log(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    return tmp_path / "impl-package" / "usage.jsonl"


@pytest.fixture()
def package(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    return repo


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def test_success_appends_one_line_without_arguments_or_paths(log: Path, package: Path, capsys) -> None:
    assert impl_package_state.main(["--package", str(package), "package", "status"]) == 0
    capsys.readouterr()
    [row] = _rows(log)
    assert set(row) == {"ts", "command", "ok", "error_type", "reason"}
    assert row["command"] == "package status" and row["ok"] is True
    assert row["error_type"] is None and row["reason"] is None
    assert row["ts"].endswith("Z")
    assert str(package) not in log.read_text(encoding="utf-8")


def test_failure_records_error_type_and_first_line_of_reason(log: Path, package: Path, capsys) -> None:
    code = impl_package_state.main(["--package", str(package), "package", "refresh-progress"])
    assert code == 1
    capsys.readouterr()
    [row] = _rows(log)
    assert row["command"] == "package refresh-progress" and row["ok"] is False
    assert row["error_type"] == "StateError"
    assert row["reason"] and "\n" not in row["reason"]
    assert ":\\" not in row["reason"] and "/Users/" not in row["reason"] and str(package) not in row["reason"]
    assert "<path>" in row["reason"]


SAMPLE_REASON = (
    "cannot read C:\\Users\\Xiao\\AppData\\Local\\Temp\\tmp.SRNwNeBHLI\\repo\\.impl-package\\state.json: "
    "[Errno 2] No such file or directory: 'C:\\\\Users\\\\Xiao\\\\AppData\\\\Local\\\\Temp\\\\tmp.SRNwNeBHLI\\\\repo'"
)


def test_sample_reason_is_redacted(log: Path) -> None:
    usage_log.begin()
    usage_log.note_error("StateError", SAMPLE_REASON)
    usage_log.record("package refresh-progress", 1)
    [row] = _rows(log)
    assert ":\\" not in row["reason"] and "/Users/" not in row["reason"] and "Xiao" not in row["reason"]
    assert row["reason"].startswith("cannot read <path>: [Errno 2] No such file or directory: ")


@pytest.mark.parametrize("raw, expected", [
    ("open C:/Users/x/a.txt failed", "open <path> failed"),
    ("open \\\\fileserver\\share\\dir\\a.txt failed", "open <path> failed"),
    ("open /Users/xiao/work/a.txt failed", "open <path> failed"),
    ("open /home/x/y failed", "open <path> failed"),
    ("open ~/work/a.txt and ~bob/q", "open <path> and <path>"),
    ("open '/var/tmp/x' failed", "open '<path>' failed"),
    ("keeps relative a/b, url https://example.com/x/y, single /tmp, time 12:30", None),
])
def test_redact_paths_forms(raw: str, expected: str | None) -> None:
    assert usage_log.redact_paths(raw) == (expected if expected is not None else raw)


@pytest.mark.parametrize("argv, label", [
    (["--package", "p", "package", "amendment", "add", "--id", "A-1"], "package amendment add"),
    (["--package", "p", "package", "amendment", "add", "extra"], "package amendment add"),
    (["--package", "p", "ticket", "satisfy", "TKT-01", "--expect", "PENDING"], "ticket satisfy"),
    (["--package", "p", "gate", "pass", "--reason", "x"], "gate pass"),
    (["--package", "p", "evidence", "carry-forward", "--key", "k"], "evidence carry-forward"),
    (["--package", "p", "gate", "--reason", "x", "pass"], "gate"),
    (["--package", "p", "evidence", "add", "--help"], "evidence --help"),
    (["--package", "p", "package", "amendment", "--help"], "package --help"),
    ([], "--help"),
])
def test_command_label_takes_up_to_two_subcommand_words(argv: list[str], label: str) -> None:
    assert usage_log.command_label(argv) == label


def test_reason_is_truncated_to_200_chars(log: Path) -> None:
    usage_log.begin()
    usage_log.note_error("StateError", "x" * 500 + "\nsecond line")
    usage_log.record("gate pass", 1)
    [row] = _rows(log)
    assert row["reason"] == "x" * 200


def test_argparse_error_and_help_labels(log: Path, package: Path, capsys) -> None:
    with pytest.raises(SystemExit) as bad:
        impl_package_state.main(["--package", str(package), "package", "bogus"])
    assert bad.value.code == 2
    with pytest.raises(SystemExit) as helped:
        impl_package_state.main(["--package", str(package), "evidence", "add", "--help"])
    assert helped.value.code == 0
    capsys.readouterr()
    bad_row, help_row = _rows(log)
    assert bad_row["error_type"] == "ArgparseError" and "invalid choice" in bad_row["reason"]
    assert help_row["command"] == "evidence --help" and help_row["ok"] is True


def test_unwritable_log_does_not_change_command_result(log: Path, package: Path, tmp_path: Path, monkeypatch, capsys) -> None:
    assert impl_package_state.main(["--package", str(package), "package", "status"]) == 0
    expected = capsys.readouterr()
    blocker = tmp_path / "blocker"
    blocker.write_text("a file, not a directory", encoding="utf-8")
    monkeypatch.setattr(usage_log, "log_path", lambda: str(blocker / "usage.jsonl"))
    assert impl_package_state.main(["--package", str(package), "package", "status"]) == 0
    actual = capsys.readouterr()
    assert (actual.out, actual.err) == (expected.out, expected.err)
    assert len(_rows(log)) == 1  # only the first, writable run


def test_summary_script_reports_counts_rates_and_top_three_causes(tmp_path: Path) -> None:
    rows = [
        {"ts": "t", "command": "evidence add", "ok": True, "error_type": None, "reason": None},
        {"ts": "t", "command": "evidence add", "ok": False, "error_type": "StateError", "reason": "bad artifact"},
        {"ts": "t", "command": "evidence add", "ok": False, "error_type": "StateError", "reason": "bad artifact"},
        {"ts": "t", "command": "evidence add", "ok": False, "error_type": "ArgparseError", "reason": "missing --file"},
        {"ts": "t", "command": "evidence add", "ok": False, "error_type": "exit:2", "reason": None},
        {"ts": "t", "command": "evidence add", "ok": False, "error_type": "OSError", "reason": "disk"},
        {"ts": "t", "command": "gate pass", "ok": True, "error_type": None, "reason": None},
    ]
    path = tmp_path / "usage.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\nnot json\n", encoding="utf-8")
    lines = impl_package_usage_summary.summarize(str(path)).splitlines()
    assert lines[1].split() == ["evidence", "add", "6", "5", "83%"]
    assert lines[2] == "    2x StateError: bad artifact"
    assert len([line for line in lines if line.startswith("    ")]) == 3
    assert lines[-1].split() == ["gate", "pass", "1", "0", "0%"]
