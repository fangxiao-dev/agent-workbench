from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/situation.py"
FIXTURES = ROOT / "tests/fixtures/situations"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
import situation  # noqa: E402


def _fixture_dirs() -> list[Path]:
    return sorted(path for path in FIXTURES.iterdir() if path.is_dir())


def _primary_slugs(result: dict) -> list[str]:
    selected = result.get("selected")
    if selected:
        return [selected["slug"]]
    return [item["slug"] for item in result.get("parallel_matches", [])]


def _invoke_render(package: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(CLI), "render", "--package", str(package), *arguments],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )


def _run_render(package: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    state_path = package / ".impl-package" / "state.json"
    credential_path: Path | None = None
    credential_before: bytes | None = None
    credential_parent_existed = False
    credential_parent_empty_before = False
    if state_path.is_file():
        try:
            state = json.loads(state_path.read_text(encoding="utf-8"))
            attempt_id = state.get("attempt", {}).get("id")
            if isinstance(attempt_id, str):
                credential_path = package / "execution" / attempt_id / "situation-digest.json"
                credential_parent_existed = credential_path.parent.is_dir()
                credential_parent_empty_before = credential_parent_existed and not any(
                    credential_path.parent.iterdir()
                )
                if credential_path.is_file():
                    credential_before = credential_path.read_bytes()
        except (OSError, UnicodeError, json.JSONDecodeError):
            pass
    try:
        return _invoke_render(package, *arguments)
    finally:
        if credential_path is not None:
            if credential_before is None:
                if credential_path.is_file():
                    credential_path.unlink()
            else:
                credential_path.write_bytes(credential_before)
            if (
                (not credential_parent_existed or credential_parent_empty_before)
                and credential_path.parent.is_dir()
            ):
                try:
                    credential_path.parent.rmdir()
                except OSError:
                    pass


def _render_text(package: Path, *arguments: str) -> str:
    completed = _run_render(package, *arguments)
    assert completed.returncode == 0, (
        f"render failed\nstdout={completed.stdout}\nstderr={completed.stderr}"
    )
    return completed.stdout.rstrip("\r\n")


@pytest.mark.parametrize("package", _fixture_dirs(), ids=lambda path: path.name)
def test_situation_render(package: Path) -> None:
    expected = json.loads((package / "expected.json").read_text(encoding="utf-8"))
    completed = _run_render(package, "--json")
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

    # `unmatched` 只表示“一行都没命中”。它曾经按“有没有 P0”来填，导致每个
    # P1–P5 渲染都自称未匹配，而主控恰好只读 --json。
    if primary:
        assert rendered.get("unmatched") is None, (
            f"{package.name}: unmatched was populated while {primary} matched at "
            f"{rendered.get('highest_match_layer')}; scenario={expected['scenario']}"
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

    expected_undetermined_count = expected.get("expected_undetermined_count")
    if expected_undetermined_count is not None:
        assert len(rendered.get("undetermined", [])) == expected_undetermined_count, (
            f"{package.name}: undetermined count mismatch; "
            f"expected={expected_undetermined_count} "
            f"actual={len(rendered.get('undetermined', []))}; scenario={expected['scenario']}"
        )


def test_rotated_trail_uses_current_file_only() -> None:
    package = ROOT / "tests/fixtures/situations/p0-handoff-target-corrected-rotated"

    rendered = json.loads(_render_text(package, "--json"))

    assert rendered["selected"] is None
    assert rendered["sources"]["trail"]["path"] == "execution/fixture-attempt/trail.jsonl"
    assert "attempt.record.handoff-target-corrected" not in _primary_slugs(rendered)


def test_dispatch_outcomes_stay_bound_to_candidate_and_incomplete_is_recoverable() -> None:
    source = FIXTURES / "p1-multiple-ready"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        rows = [
            {"v": 1, "seq": 2, "subject": "ticket:TKT-01", "kind": "dispatch", "dispatch_id": "dispatch-A", "candidate_id": "A", "mode": "implement", "chosen": "implement", "resource_keys": ["worktree:A"], "receipt": "worker-A", "worker": "worker-A", "outcome": "RUNNING", "returned": False},
            {"v": 1, "seq": 3, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "dispatch-A", "return_id": "return-A", "outcome": "INCOMPLETE", "worker_mode": "implement"},
            {"v": 1, "seq": 4, "subject": "ticket:TKT-01", "kind": "dispatch", "dispatch_id": "dispatch-B", "candidate_id": "B", "mode": "implement", "chosen": "implement", "resource_keys": ["worktree:B"], "receipt": "worker-B", "worker": "worker-B", "outcome": "RUNNING", "returned": False},
            {"v": 1, "seq": 5, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "dispatch-B", "return_id": "return-B", "outcome": "DONE", "worker_mode": "implement"},
            {"v": 1, "seq": 6, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "dispatch-A", "return_id": "late-A", "outcome": "DONE", "worker_mode": "implement"},
            {"v": 1, "seq": 7, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "dispatch-B", "return_id": "return-B", "outcome": "DONE", "worker_mode": "implement"},
        ]
        trail = package / "execution/fixture-attempt/trail.jsonl"
        trail.parent.mkdir(parents=True, exist_ok=True)
        trail.write_text(json.dumps(rows[0]) + "\n", encoding="utf-8")
        running = json.loads(_render_text(package, "--json"))
        assert [item["dispatch_id"] for item in running["in_flight"]] == ["dispatch-A"]
        assert any(item.get("action_id") == "select-ready-ticket" for item in running["runnable"])
        trail.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

        rendered = json.loads(_render_text(package, "--json"))

        assert any(
            item["slug"] == "ticket.implement.worker-incomplete-first"
            and item["dispatch_id"] == "dispatch-A"
            for item in rendered["matches"]
        )
        assert rendered["in_flight"] == []
        rows.extend([
            {"seq": 8, "subject": "ticket:TKT-01", "kind": "dispatch", "dispatch_id": "resume-A", "candidate_id": "A", "mode": "implement", "resource_keys": ["worktree:A"], "receipt": "worker-A", "worker": "worker-A", "outcome": "RUNNING", "returned": False},
            {"seq": 9, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "resume-A", "return_id": "resumed-return-A", "outcome": "DONE"},
        ])
        trail.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
        resumed = json.loads(_render_text(package, "--json"))
        assert not any(item.get("candidate_id") in {"A", "B"} for item in resumed["runnable"])
        assert not any(item.get("slug") == "ticket.implement.worker-incomplete-first" for item in resumed["matches"])


def test_wrong_subject_return_does_not_close_an_in_flight_dispatch():
    rows = [
        {"kind": "dispatch", "dispatch_id": "A", "candidate_id": "A", "subject": "ticket:TKT-01", "mode": "verify", "resource_keys": [], "outcome": "RUNNING", "returned": False},
        {"kind": "worker-return", "of": "A", "return_id": "wrong", "subject": "ticket:TKT-02", "outcome": "DONE"},
        {"kind": "worker-return", "of": "A", "return_id": "partial", "subject": "ticket:TKT-01"},
        {"kind": "result", "of": "A", "subject": "ticket:TKT-01", "transition": "ticket-state", "outcome": "SATISFIED"},
    ]
    snapshot = _coverage_context(rows).snapshot
    assert situation._dispatch_returns(snapshot) == {}
    assert [item["dispatch_id"] for item in situation._open_dispatches(snapshot)] == ["A"]


def test_inflight_identity_distinguishes_independent_review_tracks():
    snapshot = _coverage_context([]).snapshot
    running = {"dispatch_id": "review-A", "candidate_id": "review-A", "subject": "ticket:TKT-01",
               "action_id": "dispatch-delta-review", "mode": "verify", "resource_keys": [],
               "review_phase": "initial", "review_track": "Track A"}
    candidate = {**running, "candidate_id": "review-B", "review_track": "Track B"}
    assert situation._dispatch_blockers(snapshot, candidate, [], [running]) == []
    candidate["review_track"] = "Track A"
    assert any("在途" in blocker["reason"] for blocker in situation._dispatch_blockers(snapshot, candidate, [], [running]))


def test_business_actions_are_runnable_without_registration():
    rendered = json.loads(_render_text(FIXTURES / "p4-acceptance-edge-held", "--json"))
    action = next(item for item in rendered["runnable"] if item.get("action_id") == "continue-implementation")
    assert "candidate_snapshot" not in rendered
    assert "declaration_status" not in action
    assert "blockers" not in action


def test_historical_registration_is_readable_but_not_projected():
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / "package"
        shutil.copytree(FIXTURES / "p4-acceptance-edge-held", package)
        trail = package / "execution/fixture-attempt/trail.jsonl"
        trail.parent.mkdir(parents=True, exist_ok=True)
        with trail.open("a", encoding="utf-8") as stream:
            stream.write("\n" + json.dumps({"kind": "fact", "subject": "attempt", "seq": 100,
                "key": "dispatch.candidates", "value": {"candidates": [{"candidate_id": "old-only-work"}], "available_slots": 0}}) + "\n")
        rendered = json.loads(_render_text(package, "--json"))
        assert "candidate_snapshot" not in rendered
        assert not any(item.get("candidate_id") == "old-only-work" for group in ("runnable", "withheld") for item in rendered[group])
        assert any(item.get("action_id") == "continue-implementation" for item in rendered["runnable"])
        assert not any("未知 fact key" in warning for warning in rendered.get("warnings", []))


def test_pending_delta_review_survives_rotation_without_capacity_gate() -> None:
    source = FIXTURES / "p1-multiple-ready"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        delta = {"base": "a" * 40, "head": "b" * 40}
        archive_rows = [
            {"v": 1, "seq": 1, "subject": "ticket:TKT-01", "kind": "dispatch", "dispatch_id": "dispatch-A", "candidate_id": "A", "mode": "implement", "chosen": "implement", "resource_keys": [], "receipt": "worker-A", "worker": "worker-A", "outcome": "RUNNING", "returned": False},
            {"v": 1, "seq": 2, "subject": "ticket:TKT-01", "kind": "worker-return", "of": "dispatch-A", "return_id": "return-A", "outcome": "DONE", "code_delta": delta, "consumption_id": "consume-A"},
            {"v": 1, "seq": 3, "ts": "2026-09-08T10:00:01Z", "subject": "ticket:TKT-01", "kind": "fact", "key": "review.dispatch_pending", "value": {"return_id": "return-A", "code_delta": delta, "consumption_id": "consume-A", "reason": "capacity", "capacity": 0}},
        ]
        active_rows = [
            {"v": 1, "seq": 4, "subject": "ticket:TKT-01", "kind": "dispatch", "dispatch_id": "review-wrong", "candidate_id": "review-A", "mode": "verify", "chosen": "dispatch-delta-review", "resource_keys": [], "receipt": "reviewer-wrong", "worker": "reviewer-wrong", "outcome": "RUNNING", "returned": False, "reviews": "return-A", "code_delta": {"base": "c" * 40, "head": "d" * 40}, "consumption_id": "consume-A"},
        ]
        directory = package / "execution/fixture-attempt"
        directory.mkdir(parents=True, exist_ok=True)
        (directory / "trail.001.jsonl").write_text("\n".join(json.dumps(row) for row in archive_rows) + "\n", encoding="utf-8")
        trail = directory / "trail.jsonl"
        trail.write_text("\n".join(json.dumps(row) for row in active_rows) + "\n", encoding="utf-8")

        waiting = json.loads(_render_text(package, "--json"))
        assert any(item.get("return_id") == "return-A" for item in waiting["runnable"])

        active_rows.append({**active_rows[0], "seq": 5, "dispatch_id": "review-correct", "candidate_id": "review-correct", "code_delta": delta})
        trail.write_text("\n".join(json.dumps(row) for row in active_rows) + "\n", encoding="utf-8")
        dispatched = json.loads(_render_text(package, "--json"))
        assert not any(item.get("return_id") == "return-A" for item in dispatched["runnable"])
        assert any(item.get("dispatch_id") == "review-correct" for item in dispatched["in_flight"])


def test_cli_written_trail_rows_are_renderable() -> None:
    source = FIXTURES / "p4-satisfiable-no-trail"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        trail = package / "execution/fixture-attempt/trail.jsonl"
        trail.parent.mkdir(parents=True)
        trail.write_text(
            "\n".join(
                json.dumps(row, separators=(",", ":"))
                for row in (
                    {"v": 1, "seq": 1, "subject": "attempt", "kind": "checkpoint", "checkpoint": True},
                    {"v": 1, "seq": 2, "subject": "ticket:TKT-01", "kind": "result", "transition": "ticket-state", "from": "PENDING", "to": "SATISFIED", "outcome": "SATISFIED"},
                )
            )
            + "\n",
            encoding="utf-8",
        )

        rendered = json.loads(_render_text(package, "--json"))

        assert rendered["sources"]["trail"]["path"] == "execution/fixture-attempt/trail.jsonl"
        assert "error" not in rendered
        assert set(_primary_slugs(rendered)) == {
            "attempt.record.trail-rotation-due",
        }
        assert rendered["highest_match_layer"] == "P1"


def test_escape_event_and_legacy_escape_decision_are_read() -> None:
    new_escape = {
        "subject": "attempt",
        "kind": "escape",
        "deviation": "attempt.record.unmatched -> manual recovery",
        "reason": "当前处境表没有覆盖该恢复窗口",
        "of": "dispatch-01",
    }
    legacy_escape = {
        "subject": "attempt",
        "kind": "decision",
        "seq": 2,
        "chosen": "escape: 先按人工判断恢复",
    }
    parsed = situation._parse_trail(
        situation.FileView(
            "execution/initial/trail.jsonl",
            "\n".join(json.dumps(row) for row in (new_escape, legacy_escape)) + "\n",
        )
    )

    assert parsed.error is None
    assert parsed.unknown_fact_keys == ()
    assert parsed.rows == [new_escape, legacy_escape]


def test_human_render_collapses_undetermined_and_supports_since() -> None:
    package = ROOT / "tests/fixtures/situations-a2/p0-evidence-unfiled"

    full = _render_text(package)
    assert "无法判定 12 行\n" in full
    assert "无法判定 23 行:" not in full
    assert "package.record.projection-drift" not in full
    digest_line = full.rsplit("\n", 1)[-1]
    assert digest_line.startswith("digest: ")
    digest = digest_line.removeprefix("digest: ")
    assert len(digest) == 12

    explained = _render_text(package, "--explain-undetermined")
    assert "无法判定 12 行: package.record.projection-drift (package)" in explained

    unchanged = _render_text(package, "--since", digest)
    assert unchanged == f"处境未变 (digest: {digest})"


def test_render_writes_situation_digest_credential() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        completed = _invoke_render(package, "--json")
        assert completed.returncode == 0, completed.stderr

        state_path = package / ".impl-package/state.json"
        attempt = json.loads(state_path.read_text(encoding="utf-8"))["attempt"]["id"]
        credential_path = package / "execution" / attempt / "situation-digest.json"
        credential_bytes = credential_path.read_bytes()
        credential = json.loads(credential_bytes.decode("utf-8"))
        rendered = json.loads(completed.stdout)
        assert set(credential) == {
            "digest",
            "legacy_digest",
            "ts",
            "state_sha256",
            "head",
            "trail_seq",
            "blocking_slugs",
        }
        assert credential["blocking_slugs"] == [item["slug"] for item in rendered["blocking"]]
        assert rendered["attempt"] == attempt
        assert credential["digest"] == rendered["digest"]
        assert credential["legacy_digest"] == rendered["legacy_digest"]

        assert len(credential["ts"]) > 10
        assert credential["state_sha256"] == hashlib.sha256(state_path.read_bytes()).hexdigest()
        assert not credential_bytes.startswith(b"\xef\xbb\xbf")


def test_render_can_skip_creating_situation_digest_credential() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        completed = _invoke_render(package, "--no-write-credential", "--json")
        assert completed.returncode == 0, completed.stderr

        state = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))
        credential_path = package / "execution" / state["attempt"]["id"] / "situation-digest.json"
        rendered = json.loads(completed.stdout)
        assert rendered["attempt"] == state["attempt"]["id"]
        assert not credential_path.exists()


def test_render_can_skip_updating_existing_situation_digest_credential() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        first = _invoke_render(package, "--json")
        assert first.returncode == 0, first.stderr

        state = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))
        credential_path = package / "execution" / state["attempt"]["id"] / "situation-digest.json"
        before = credential_path.read_bytes()
        second = _invoke_render(package, "--no-write-credential", "--json")
        assert second.returncode == 0, second.stderr
        assert credential_path.read_bytes() == before


def test_render_since_writes_situation_digest_credential() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        first = json.loads(_invoke_render(package, "--json").stdout)
        second_run = _invoke_render(package, "--json", "--since", first["digest"])
        assert second_run.returncode == 0, second_run.stderr
        assert json.loads(second_run.stdout) == {
            "digest": first["digest"],
            "legacy_digest": first["legacy_digest"],
            "unchanged": True,
        }

        state = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))
        credential_path = package / "execution" / state["attempt"]["id"] / "situation-digest.json"
        credential = json.loads(credential_path.read_text(encoding="utf-8"))
        assert credential["digest"] == first["digest"]


def test_render_succeeds_when_situation_digest_credential_cannot_be_written() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        state = json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))
        credential_path = package / "execution" / state["attempt"]["id"] / "situation-digest.json"
        credential_path.mkdir(parents=True)

        completed = _invoke_render(package, "--json")
        assert completed.returncode == 0
        assert "warning: could not write situation-digest.json:" in completed.stderr


def test_compaction_pressure_is_high_low_or_unknown_without_fact_channel() -> None:
    package = ROOT / "tests/fixtures/situations/p4-satisfiable-no-trail"
    pressure = json.dumps(
        {
            "compactions": 5,
            "last_interval_min": 12,
            "shrinking": True,
            "high": True,
            "explanation": "fixture",
        },
        separators=(",", ":"),
    )

    missing = json.loads(_render_text(package, "--json"))
    missing_value = missing["when_values"]["attempt.compaction_pressure_high"][0]
    assert missing_value["status"] == "unknown"
    assert any(
        item["slug"] == "attempt.record.handoff-due"
        for item in missing["undetermined"]
    )

    high = json.loads(_render_text(package, "--compaction-pressure", pressure, "--json"))
    assert _primary_slugs(high) == ["attempt.record.handoff-due"]
    high_value = high["when_values"]["attempt.compaction_pressure_high"][0]
    assert high_value["status"] == "known"
    assert high_value["value"] is True

    low_pressure = pressure.replace('"high":true', '"high":false')
    low = json.loads(_render_text(package, "--compaction-pressure", low_pressure, "--json"))
    assert _primary_slugs(low) == ["ticket.accept.satisfiable"]
    low_value = low["when_values"]["attempt.compaction_pressure_high"][0]
    assert low_value["status"] == "known"
    assert low_value["value"] is False


def test_t9_removes_declaration_only_fact_keys() -> None:
    removed = {
        "attempt.handoff_or_long_task",
        "attempt.integration_carrier_available",
        "attempt.integration_evidence_available",
        "attempt.manual_verification_owner",
        "attempt.manual_verification_result_present",
        "attempt.completion_claim_pending",
        "ticket.no_longer_needed",
        "ticket.review_required",
        "ticket.review_trigger",
        "ticket.post_fix_regression_pending",
        "evidence.sources_uniquely_decide",
        "git.comparison_head_fixed",
        "trail.bookkeeper_partial_write",
        "trail.handoff_in_flight",
        "trail.checkpoint_refresh_needed",
        "trail.judgment_unfiled",
        "finding.closure_review_pending",
    }
    computed = {
        "package.validate.projection_drift",
        "attempt.session_resumed",
        "attempt.in_flight",
        "attempt.terminal_coverage_complete",
        "git.accepted_seam_changed",
    }

    assert removed.isdisjoint(situation.FACT_KEYS)
    assert computed.isdisjoint(situation.FACT_KEYS)
    assert computed <= situation.WHEN_PARSERS.keys()


def test_projection_drift_requires_structured_validation_result() -> None:
    package = ROOT / "tests/fixtures/situations/p4-satisfiable-no-trail"

    rendered = json.loads(
        _render_text(
            package,
            "--validation-result",
            '{"projection_drift":true}',
            "--json",
        )
    )

    assert _primary_slugs(rendered) == ["package.record.projection-drift"]
    assert rendered["when_values"]["package.validate.projection_drift"][0]["value"] is True


@pytest.mark.parametrize(
    ("first", "second", "expected_status"),
    [
        (situation.Fact(False), situation.Fact.unknown("missing"), "false"),
        (situation.Fact.unknown("missing"), situation.Fact(False), "false"),
        (situation.Fact(True), situation.Fact.unknown("missing"), "unknown"),
        (situation.Fact(True), situation.Fact(True), "true"),
    ],
)
def test_evaluate_row_uses_false_dominance_for_and_conditions(
    monkeypatch: pytest.MonkeyPatch,
    first: situation.Fact,
    second: situation.Fact,
    expected_status: str,
) -> None:
    monkeypatch.setitem(situation.WHEN_PARSERS, "test.first", lambda _context: first)
    monkeypatch.setitem(situation.WHEN_PARSERS, "test.second", lambda _context: second)

    status, values, reasons = situation._evaluate_row(
        {"when": {"test.first": True, "test.second": True}},
        SimpleNamespace(),
    )

    assert status == expected_status
    assert list(values) == ["test.first", "test.second"]
    assert bool(reasons) is (expected_status == "unknown")


def _seam_context(
    diff_names: list[str] | None,
    *,
    resolved_revision: str | None = "resolved-acceptance",
) -> situation.FactContext:
    reader = SimpleNamespace(
        package_rel=None,
        resolve_commit=lambda revision: resolved_revision,
        diff_names=lambda base: diff_names,
    )
    state = situation.StateView(
        raw={
            "tickets": {
                "TKT-01": {
                    "state": "SATISFIED",
                    "acceptance": {"revision": "accepted"},
                }
            }
        },
        valid=True,
        error=None,
        attempt_id="fixture-attempt",
        ticket_ids=["TKT-01"],
    )
    snapshot = situation.Snapshot(
        package=Path("."),
        reader=reader,
        state=state,
        tickets={},
        trail=situation.TrailView(True, []),
        gate=situation.GateView(False, None, None),
        findings=situation.FindingsView(False, "", []),
        intake=situation.IntakeView(False, None),
        validation_result=None,
        compaction_pressure=None,
        head="current-head",
    )
    return situation.FactContext(snapshot, "ticket", "TKT-01")


def test_git_accepted_seam_changed_is_false_for_docs_only_diff() -> None:
    context = _seam_context(["docs/usage.txt", "notes.md"])

    fact = situation._when_git_accepted_seam_changed(context)

    assert fact.known is True
    assert fact.value is False


def test_git_accepted_seam_changed_is_true_for_source_diff() -> None:
    context = _seam_context(["docs/usage.txt", "src/engine.py"])

    fact = situation._when_git_accepted_seam_changed(context)

    assert fact.known is True
    assert fact.value is True


def test_git_accepted_seam_changed_is_unknown_when_acceptance_revision_cannot_resolve() -> None:
    context = _seam_context(["src/engine.py"], resolved_revision=None)

    fact = situation._when_git_accepted_seam_changed(context)

    assert fact.known is False
    assert "acceptance revision" in (fact.reason or "")


def test_in_flight_ignores_removed_fact_override() -> None:
    context = _coverage_context(
        [
            {
                "subject": "attempt",
                "kind": "fact",
                "key": "attempt.in_flight",
                "value": True,
                "ts": "2026-09-07T12:00:00Z",
            }
        ]
    )

    fact = situation._when_attempt_in_flight(context)

    assert fact.known is True
    assert fact.value is False


def _coverage_context(
    rows: list[dict],
    *,
    head: str | None = "current-head",
    ticket_state: str = "SATISFIED",
    diff_names: dict[str, list[str] | None] | None = None,
    state_valid: bool = True,
    gate_verdict: str | None = None,
    gate_attempt: str | None = "fixture-attempt",
    gate_text: str = "",
    attempt_id: str = "fixture-attempt",
    reports: dict[str, str] | None = None,
) -> situation.FactContext:
    diff_names = diff_names or {}
    reader = SimpleNamespace(
        package_rel=None,
        diff_names=lambda base: diff_names.get(base),
        read=lambda path: situation.FileView(path, (reports or {}).get(path)),
    )
    state = situation.StateView(
        raw={"tickets": {"TKT-01": {"state": ticket_state}}} if state_valid else None,
        valid=state_valid,
        error=None if state_valid else "state.json 无法判定",
        attempt_id=attempt_id,
        ticket_ids=["TKT-01"],
    )
    snapshot = situation.Snapshot(
        package=Path("."),
        reader=reader,
        state=state,
        tickets={},
        trail=situation._parse_trail(situation.FileView("trail.jsonl", "\n".join(json.dumps(row) for row in rows))),
        gate=situation.GateView(gate_verdict is not None, gate_verdict, None, gate_attempt, gate_text),
        findings=situation.FindingsView(False, "", []),
        intake=situation.IntakeView(False, None),
        validation_result=None,
        compaction_pressure=None,
        head=head,
    )
    return situation.FactContext(snapshot, "attempt", attempt_id)


def _terminal_dispatch(track: str, *, head: str = "current-head", recheck: bool = False) -> dict:
    return {
        "subject": "attempt",
        "kind": "dispatch",
        "review_phase": "terminal-final",
        "review_track": track,
        "review_recheck": recheck,
        "head": head,
    }


def test_terminal_coverage_is_unknown_before_near_terminal_gate() -> None:
    context = _coverage_context([], state_valid=False)

    fact = situation._when_attempt_terminal_coverage_complete(context)

    assert fact.known is False


def test_gate_terminal_is_false_when_verdict_belongs_to_a_prior_attempt() -> None:
    # E1: an old initial/defer patch's terminal `gate.md` must not be read as
    # terminal for a newer, still-active Attempt (mirrors engine.py `_lifecycle`,
    # which already checks `gate["attempt"] == attempt`).
    context = _coverage_context(
        [],
        gate_verdict="pass",
        gate_attempt="old-attempt",
        attempt_id="current-attempt",
    )

    fact = situation._when_gate_terminal(context)

    assert fact.known is True
    assert fact.value is False


def test_gate_terminal_is_true_when_verdict_belongs_to_the_current_attempt() -> None:
    context = _coverage_context(
        [],
        gate_verdict="pass",
        gate_attempt="current-attempt",
        attempt_id="current-attempt",
    )

    fact = situation._when_gate_terminal(context)

    assert fact.known is True
    assert fact.value is True


def test_gate_without_attempt_is_unknown_for_all_current_gate_facts() -> None:
    context = _coverage_context([], gate_verdict="pass", gate_attempt=None)
    context.snapshot.gate = situation._parse_gate(
        situation.FileView("gate.md", "# Gate\n- Verdict: pass\n## Durable Deltas\n- old.md\n")
    )
    assert context.snapshot.gate.error == "gate.md 缺少 Attempt"
    assert context.snapshot.gate.verdict is None
    for parser in (
        situation._when_gate_terminal,
        situation._when_gate_present,
        situation._when_gate_verdict,
        situation._when_gate_stage7_complete,
    ):
        assert parser(context).known is False


def test_gate_present_is_false_when_only_a_prior_attempts_gate_exists() -> None:
    # A leftover gate.md from an earlier Attempt must not read as "Gate
    # present" for a newer Attempt that hasn't written its own Gate yet,
    # otherwise `attempt.gate.missing` never fires.
    context = _coverage_context(
        [],
        gate_verdict="blocked",
        gate_attempt="old-attempt",
        attempt_id="current-attempt",
    )

    fact = situation._when_gate_present(context)

    assert fact.known is True
    assert fact.value is False


def test_gate_verdict_is_unknown_when_only_a_prior_attempts_gate_exists() -> None:
    context = _coverage_context(
        [],
        gate_verdict="blocked",
        gate_attempt="old-attempt",
        attempt_id="current-attempt",
    )

    fact = situation._when_gate_verdict(context)

    assert fact.known is False


def test_gate_stage7_complete_is_false_when_only_a_prior_attempts_gate_exists() -> None:
    # Even though the stale gate.md's own Durable Deltas section is filled in,
    # it belongs to a prior Attempt, so the current Attempt has not completed
    # Stage 7 and `attempt.gate.durable-delta-missing` must still be able to fire.
    context = _coverage_context(
        [],
        gate_verdict="blocked",
        gate_attempt="old-attempt",
        gate_text="## Durable Deltas\n- some/path.md\n",
        attempt_id="current-attempt",
    )

    fact = situation._when_gate_stage7_complete(context)

    assert fact.known is True
    assert fact.value is False


def test_near_terminal_gate_is_false_when_only_a_prior_attempts_gate_exists() -> None:
    # Tickets are not all terminal, so `near_terminal_gate` must fall through to
    # the Gate check; a stale prior-Attempt Gate must not count, otherwise
    # `attempt.disposition.findings-triage-pending` could fire on the wrong basis.
    context = _coverage_context(
        [],
        ticket_state="PENDING",
        gate_verdict="pass",
        gate_attempt="old-attempt",
        attempt_id="current-attempt",
    )

    fact = situation._when_attempt_near_terminal_gate(context)

    assert fact.known is True
    assert fact.value is False


def _terminal_summary(*, safety=False, old_tracks=()):
    results = []
    reports = {}
    for track in ("Track A", "Track B", "Track C", *(("Track D",) if safety else ())):
        reviewed_head = "old-head" if track in old_tracks else "current-head"
        artifact = f"execution/{track}.md"
        reports[artifact] = f"verdict: PASS\nreviewed-head: {reviewed_head}\nreview-run: run-1\nreview-track: {track}\n"
        result = {"track": track, "verdict": "PASS", "reviewedHead": reviewed_head, "artifact": artifact}
        if track in old_tracks:
            result.update(reused=True, reuseEvidence="execution/reuse.md")
            reports["execution/reuse.md"] = "run-1: old-head -> current-head; inputs unchanged"
        results.append(result)
    row = {"subject": "attempt", "kind": "fact", "ts": "2026-09-05T12:00:00Z", "key": "review.terminal_summary", "value": {
        "reviewRunId": "run-1", "comparisonHead": "current-head", "safetyApplicable": safety, "results": results,
    }}
    return row, reports


def test_terminal_coverage_accepts_three_results_without_safety():
    row, reports = _terminal_summary()
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is True


def test_terminal_coverage_requires_applicable_safety_result():
    row, reports = _terminal_summary(safety=True)
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is True
    row["value"]["results"].pop()
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False


def test_terminal_coverage_does_not_accept_dispatch_or_legacy_boolean():
    rows = [_terminal_dispatch(track) for track in situation.REVIEW_TRACK_VALUES]
    rows.append({"subject": "attempt", "kind": "fact", "ts": "2026-09-05T12:00:00Z", "key": "attempt.terminal_coverage_complete", "value": True})
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context(rows)).value is False


def test_terminal_coverage_accepts_b_c_safety_reuse_with_same_run_evidence():
    row, reports = _terminal_summary(safety=True, old_tracks=("Track B", "Track C", "Track D"))
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is True
    del reports["execution/reuse.md"]
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False


def test_terminal_coverage_rejects_old_a_and_changed_comparison_head():
    row, reports = _terminal_summary(old_tracks=("Track A",))
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False
    row, reports = _terminal_summary()
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], head="new-head", reports=reports)).value is False


def test_terminal_coverage_rejects_missing_failed_or_wrong_run_report():
    row, reports = _terminal_summary()
    report = reports["execution/Track B.md"]
    for invalid in ("", report.replace("PASS", "FAIL"), report.replace("run-1", "other-run"), report.replace("current-head", "other-head")):
        reports["execution/Track B.md"] = invalid
        assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False


def test_terminal_gate_does_not_substitute_for_review_results():
    for verdict in ("pass", "fail", "defer"):
        assert situation._when_attempt_terminal_coverage_complete(_coverage_context([], gate_verdict=verdict)).value is False


def test_terminal_coverage_requires_distinct_track_reports():
    row, reports = _terminal_summary()
    row["value"]["results"][1]["artifact"] = row["value"]["results"][0]["artifact"]
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False
    row, reports = _terminal_summary()
    reports["execution/Track B.md"] = reports["execution/Track A.md"]
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False


def test_terminal_coverage_rejects_uncertain_duplicate_or_malformed_results():
    for value in ("UNCERTAIN", "FAIL"):
        row, reports = _terminal_summary()
        row["value"]["results"][0]["verdict"] = value
        assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False
    row, reports = _terminal_summary()
    row["value"]["results"].append(row["value"]["results"][0])
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False
    row["value"]["results"] = [{"track": []}]
    assert situation._when_attempt_terminal_coverage_complete(_coverage_context([row], reports=reports)).value is False


def test_json_render_exposes_digest_and_short_circuits_since() -> None:
    package = ROOT / "tests/fixtures/situations-a2/p0-evidence-unfiled"
    rendered = json.loads(_render_text(package, "--json"))
    assert rendered["unchanged"] is False
    assert len(rendered["digest"]) == 12

    unchanged = json.loads(_render_text(package, "--json", "--since", rendered["digest"]))
    assert unchanged == {
        "digest": rendered["digest"],
        "legacy_digest": rendered["legacy_digest"],
        "unchanged": True,
    }
