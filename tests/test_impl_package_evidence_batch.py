from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_impl_package_journey import (  # noqa: E402
    CLI, _template_cache, _cli, _commit_file, _init_v36, _journey_record, _review_record, _run_setup_record, _state, _suite_record,
    engine, situation,
)
from impl_package_runtime import validate_state  # noqa: E402

_ = _template_cache  # autouse session fixture that primes the repo template cache
REASON_FLAGS = ("--judged-by", "controller")


def _seed(tmp_path: Path):
    """run-1 (setup + 2 journey steps) plus a suite and a review key, then a runtime commit."""
    repo, package, rev = _init_v36(tmp_path)
    records = [
        _run_setup_record(rev), _journey_record(rev, "J1-S1"), _journey_record(rev, "J1-S2"),
        _suite_record(rev, "S-resolver"), _suite_record(rev, "S-workflow"), _review_record(rev, "TKT-01"),
    ]
    assert _cli(repo, package, "evidence", "add", input_value=records).returncode == 0
    head = _commit_file(repo, "src/app.py", "value = 1\n")
    assert _cli(repo, package, "package", "refresh-progress").returncode == 0
    return repo, package, rev, head


def _carry(repo, package, head, *pairs, extra=()):
    args = ["evidence", "carry-forward", "--to", head, *REASON_FLAGS, *extra]
    for select, reason in pairs:
        args += ["--select", select, "--reason", reason]
    return _cli(repo, package, *args)


def _carried(package, key):
    return _state(package)["evidenceIndex"][key][-1].get("carriedForward")


def _coverage(repo, package, key, head):
    record = _state(package)["evidenceIndex"][key][-1]
    return situation.evidence_revision_coverage(record, head, repo=repo, package=package)


RUN_KEYS = ["run-setup:run-1", "journey:run-1:J1-S1", "journey:run-1:J1-S2"]


def test_carry_forward_by_run_covers_all_keys(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    assert all(_coverage(repo, package, k, head) is None for k in RUN_KEYS)
    done = _carry(repo, package, head, ("run:run-1", "x"))
    assert done.returncode == 0, done.stderr
    for key in RUN_KEYS:
        assert _carried(package, key) == {"to": head, "reason": "x", "judgedBy": "controller"}
        assert _coverage(repo, package, key, head) == "carried"
    assert json.loads(done.stdout)["carriedKeys"] == 3


def test_multiple_groups_keep_their_own_reasons(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    assert _carry(repo, package, head, ("run:run-1", "a"), ("kind:suite", "b")).returncode == 0
    assert _carried(package, "journey:run-1:J1-S1")["reason"] == "a"
    assert _carried(package, "suite:S-resolver")["reason"] == "b"
    assert _carried(package, "suite:S-workflow")["reason"] == "b"
    assert _carried(package, "review:TKT-01") is None
    assert _carry(repo, package, head, ("ticket:TKT-01", "c")).returncode == 0
    assert _carried(package, "review:TKT-01")["reason"] == "c"


def test_atomic_rollback_when_a_revision_is_not_an_ancestor(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    # a key whose revision lives on a side branch, not an ancestor of head
    subprocess.run(["git", "checkout", "-q", "-b", "side"], cwd=repo, check=True)
    side = _commit_file(repo, "src/side.py", "x = 1\n")
    subprocess.run(["git", "checkout", "-q", "-"], cwd=repo, check=True)
    assert _cli(repo, package, "evidence", "add", input_value=_suite_record(side, "S-safety")).returncode == 0
    before = (package / ".impl-package/state.json").read_bytes()
    result = _carry(repo, package, head, ("run:run-1", "a"), ("key:suite:S-safety", "b"))
    assert result.returncode != 0
    assert "suite:S-safety" in result.stderr
    assert (package / ".impl-package/state.json").read_bytes() == before
    assert _carried(package, "journey:run-1:J1-S1") is None


def test_empty_selector_fails_without_writing(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    before = (package / ".impl-package/state.json").read_bytes()
    result = _carry(repo, package, head, ("run:run-1", "a"), ("run:nope", "b"))
    assert result.returncode != 0 and "run:nope" in result.stderr
    assert (package / ".impl-package/state.json").read_bytes() == before


def test_select_reason_count_mismatch_fails(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    result = _cli(
        repo, package, "evidence", "carry-forward", "--to", head, *REASON_FLAGS,
        "--select", "run:run-1", "--select", "kind:suite", "--reason", "only one",
    )
    assert result.returncode != 0 and "--reason per --select" in result.stderr
    assert _carried(package, "journey:run-1:J1-S1") is None


def test_dry_run_reports_groups_and_runtime_files_only(tmp_path: Path) -> None:
    repo, package, _rev, _head = _seed(tmp_path)
    _commit_file(repo, "docs/guide.md", "d\n")
    _commit_file(repo, "notes/readme.md", "n\n")
    head = _commit_file(repo, "src/other.py", "y = 1\n")
    before = (package / ".impl-package/state.json").read_bytes()
    result = _carry(repo, package, head, ("run:run-1", "a"), ("kind:suite", "b"), extra=("--dry-run",))
    assert result.returncode == 0, result.stderr
    report = json.loads(result.stdout)
    assert [g["select"] for g in report["groups"]] == ["run:run-1", "kind:suite"]
    assert sorted(report["groups"][0]["keys"]) == sorted(RUN_KEYS)
    assert report["groups"][1]["keys"] == ["suite:S-resolver", "suite:S-workflow"]
    for group in report["groups"]:
        assert group["runtimeChangedFiles"] == ["src/app.py", "src/other.py"]
    assert (package / ".impl-package/state.json").read_bytes() == before


def test_legacy_key_form_is_compatible_and_idempotent(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)
    args = ("evidence", "carry-forward", "--key", "suite:S-resolver", "--to", head, "--reason", "r", *REASON_FLAGS)
    first = json.loads(_cli(repo, package, *args).stdout)
    assert first == {
        "evidenceKey": "suite:S-resolver", "carriedForward": {"to": head, "reason": "r", "judgedBy": "controller"},
        "idempotent": False,
    }
    assert json.loads(_cli(repo, package, *args).stdout)["idempotent"] is True


def test_validate_state_call_count_is_constant(tmp_path: Path) -> None:
    repo, package, _rev, head = _seed(tmp_path)

    def calls(*pairs) -> int:
        # _refresh_projections 在 validate_state 模块内调用自己的 _validate_state，用同一个 spy 一并计数
        with patch.object(engine, "_validate_state", wraps=engine._validate_state) as spy, patch.object(
            validate_state, "_validate_state", spy
        ):
            engine.command_evidence_carry_forward(
                package, None, head, [r for _, r in pairs], "controller", [s for s, _ in pairs],
            )
        return spy.call_count

    small = calls(("key:suite:S-resolver", "a"))
    large = calls(("run:run-1", "b"), ("kind:suite", "c"), ("ticket:TKT-01", "d"))
    assert small == large and small <= 3


def _jsonl(records) -> str:
    return "\n".join(json.dumps(r) for r in records) + "\n"


def _add_raw(repo, package, text):
    return subprocess.run(
        [sys.executable, str(CLI), "--package", str(package), "evidence", "add"],
        cwd=repo, input=text, capture_output=True, text=True, encoding="utf-8",
        env={**__import__("os").environ, "IMPL_PACKAGE_NO_SITUATION": "1"},
    )


def test_evidence_add_jsonl_batch_and_atomic_failure(tmp_path: Path) -> None:
    repo, package, rev = _init_v36(tmp_path)
    good = [_suite_record(rev, "S-resolver"), _suite_record(rev, "S-workflow"), _review_record(rev, "TKT-01")]
    bad = [dict(good[0]), dict(good[1], artifact="artifacts/missing.md"), dict(good[2])]
    before = (package / ".impl-package/state.json").read_bytes()
    failed = _add_raw(repo, package, _jsonl(bad))
    assert failed.returncode != 0 and "line 2" in failed.stderr
    assert (package / ".impl-package/state.json").read_bytes() == before
    ok = _add_raw(repo, package, _jsonl(good))
    assert ok.returncode == 0, ok.stderr
    assert json.loads(ok.stdout)["added"] == 3
    assert set(_state(package)["evidenceIndex"]) >= {"suite:S-resolver", "suite:S-workflow", "review:TKT-01"}


def test_evidence_check_accepts_jsonl_file(tmp_path: Path) -> None:
    repo, package, rev = _init_v36(tmp_path)
    path = tmp_path / "batch.jsonl"
    path.write_text(_jsonl([_suite_record(rev, "S-resolver"), _suite_record(rev, "S-workflow")]), encoding="utf-8")
    before = (package / ".impl-package/state.json").read_bytes()
    result = _cli(repo, package, "evidence", "check", "--file", str(path))
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["wouldAdd"] == 2
    assert (package / ".impl-package/state.json").read_bytes() == before


def test_evidence_add_array_and_single_object(tmp_path: Path) -> None:
    repo, package, rev = _init_v36(tmp_path)
    assert _cli(repo, package, "evidence", "add", input_value=[_suite_record(rev, "S-resolver")]).returncode == 0
    single = _cli(repo, package, "evidence", "add", input_value=_suite_record(rev, "S-workflow"))
    assert single.returncode == 0 and json.loads(single.stdout)["evidenceKey"] == "suite:S-workflow"


def test_ten_keys_batch_vs_loop_timing(tmp_path: Path, capsys) -> None:
    timings = {}
    for mode in ("batch", "loop"):
        repo, package, rev = _init_v36(tmp_path / mode)
        runs = [f"r{index}" for index in range(10)]
        assert _cli(repo, package, "evidence", "add", input_value=[_run_setup_record(rev, run) for run in runs]).returncode == 0
        head = _commit_file(repo, "src/app.py", "value = 1\n")
        start = time.perf_counter()
        if mode == "batch":
            engine.command_evidence_carry_forward(
                package, None, head, ["same"] * 10, "controller", [f"run:{run}" for run in runs],
            )
        else:
            for run in runs:
                engine.command_evidence_carry_forward(package, f"run-setup:{run}", head, "same", "controller")
        timings[mode] = time.perf_counter() - start
    with capsys.disabled():
        print(f"\n10 keys: batch={timings['batch']:.2f}s loop={timings['loop']:.2f}s")
    assert timings["batch"] < timings["loop"]
