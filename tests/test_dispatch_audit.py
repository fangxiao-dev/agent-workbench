import importlib.util
import json
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest


def _execution_rows(*, pending=False, review=True, receipt=True):
    delta = {"base": "a" * 40, "head": "b" * 40}
    rows = []
    for name in ("A", "B"):
        rows.append({"kind": "dispatch", "dispatch_id": name, "subject": "ticket:TKT-01", "worker": name,
                     "outcome": "RUNNING", "returned": False, "receipt": name if receipt else None,
                     "candidate_id": name, "mode": "implement", "resource_keys": [name]})
    rows.append({"kind": "worker-return", "of": "A", "return_id": "return-A", "subject": "ticket:TKT-01",
                 "outcome": "INCOMPLETE", "code_delta": delta, "consumption_id": "consume-A"})
    if pending:
        rows.append({"kind": "fact", "key": "review.dispatch_pending", "subject": "ticket:TKT-01",
                     "ts": "2026-09-08T12:00:00Z",
                     "value": {"return_id": "return-A", "code_delta": delta, "consumption_id": "consume-A", "reason": "reviewer unavailable"}})
    rows.append({"kind": "worker-return", "of": "B", "return_id": "return-B", "subject": "ticket:TKT-01", "outcome": "DONE"})
    if review:
        rows.append({"kind": "dispatch", "dispatch_id": "review-A", "subject": "ticket:TKT-01", "worker": "reviewer",
                     "outcome": "RUNNING", "returned": False, "receipt": "review-receipt", "reviews": "return-A",
                     "code_delta": delta, "consumption_id": "consume-A", "resource_keys": ["snapshot:A"],
                     "candidate_id": "review-A", "mode": "verify"})
    return rows


def test_dispatch_audit_keeps_same_ticket_concurrency_and_per_return_review():
    rows = _execution_rows()
    rows[1]["resource_keys"] = ["A"]
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["concurrent_dispatches"] == [{
        "dispatch_ids": ["A", "B"], "lines": [1, 2], "resources": [["A"], ["A"]]
    }]
    assert report["pending_reviews"] == []
    assert report["execution_issues"] == []


def test_last_code_return_is_pending_even_without_a_next_implementation():
    rows = _execution_rows(pending=True, review=False)
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["pending_reviews"][0]["return_id"] == "return-A"
    assert report["pending_reviews"][0]["recorded"] is True
    assert report["execution_issues"] == []


def test_missing_receipt_and_duplicate_return_cannot_count_as_execution():
    rows = _execution_rows(receipt=False)
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["concurrent_dispatches"] == []
    assert any("receipt" in item["reason"] for item in report["execution_issues"])
    rows = _execution_rows()
    rows.append(dict(rows[3]))
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any(item["reason"] == "duplicate return_id" for item in report["execution_issues"])


def test_new_dispatch_does_not_replay_head(audit_tmp_path, monkeypatch):
    rows = _execution_rows(pending=True, review=False)
    for row in rows:
        if row["kind"] == "dispatch":
            row["situation_digest"] = "legacy-field-is-ignored"
    monkeypatch.setattr(dispatch_audit, "replay_situation", lambda *_: pytest.fail("new dispatch must not replay old HEAD"))
    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert report["deviations"] == []
    assert report["uncheckable"] == []
    assert report["schema_violations"] == []


def test_second_return_identity_for_same_dispatch_is_not_consumed():
    rows = _execution_rows(review=False)
    rows.append(dict(rows[3], return_id="late-A", outcome="DONE"))
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any("late return" in item["reason"] for item in report["execution_issues"])
    assert [item["return_id"] for item in report["pending_reviews"]] == ["return-A"]


def test_candidate_id_cannot_run_twice_and_invalid_resources_are_uncheckable():
    rows = _execution_rows(review=False)
    rows.append(dict(rows[1], dispatch_id="B-again", resource_keys=[""]))

    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))

    assert any(item["reason"] == "candidate already running or DONE" for item in report["execution_issues"])
    assert any("resource_keys" in item["reason"] for item in report["execution_uncheckable"])


def test_concurrency_interval_closes_only_on_first_valid_attributable_return():
    dispatches = _execution_rows(review=False)[:2]
    rows = [
        dispatches[0],
        {"kind": "worker-return", "of": "A", "return_id": "partial", "subject": "ticket:TKT-01"},
        {"kind": "worker-return", "of": "A", "return_id": "wrong", "subject": "ticket:TKT-02", "outcome": "DONE"},
        dispatches[1],
        {"kind": "worker-return", "of": "A", "return_id": "valid", "subject": "ticket:TKT-01", "outcome": "DONE"},
        dict(dispatches[1], dispatch_id="C", candidate_id="C", worker="C"),
    ]

    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))

    assert [item["dispatch_ids"] for item in report["concurrent_dispatches"]] == [["A", "B"], ["B", "C"]]
    assert any("identity or outcome" in item["reason"] for item in report["execution_uncheckable"])
    assert any("no matching received dispatch" in item["reason"] for item in report["execution_issues"])


def test_wrong_consumption_review_leaves_original_delta_pending():
    rows = _execution_rows()
    rows[-1]["consumption_id"] = "wrong-consumption"
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any("fixed return delta" in item["reason"] for item in report["execution_issues"])
    assert [item["return_id"] for item in report["pending_reviews"]] == ["return-A"]


SCRIPT_DIR = Path(__file__).parents[1] / "plugin-marketplace/plugins/impl-package/scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
SPEC = importlib.util.spec_from_file_location("dispatch_audit", SCRIPT_DIR / "dispatch_audit.py")
assert SPEC and SPEC.loader
dispatch_audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(dispatch_audit)


def _package(tmp_path: Path, rows: list[dict]) -> Path:
    package = tmp_path / "package"
    (package / ".impl-package").mkdir(parents=True)
    (package / "execution" / "initial").mkdir(parents=True)
    (package / ".impl-package" / "state.json").write_text(
        json.dumps({"attempt": {"id": "initial"}}), encoding="utf-8"
    )
    (package / "execution" / "initial" / "trail.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8"
    )
    return package


def _dispatch(**overrides: object) -> dict:
    row = {
        "kind": "dispatch",
        "subject": "ticket:TKT-01",
        "id": "dispatch-01",
        "outcome": "RUNNING",
        "worker": "worker-01",
        "returned": False,
    }
    row.update(overrides)
    return row


@pytest.fixture
def audit_tmp_path():
    with tempfile.TemporaryDirectory(prefix=".dispatch-audit-", dir=Path(__file__).parents[1]) as directory:
        yield Path(directory)


def test_old_trail_without_digest_is_reported_as_no_digest(audit_tmp_path: Path) -> None:
    report = dispatch_audit.audit_package(
        _package(audit_tmp_path, [_dispatch(id="dispatch-01"), _dispatch(id="dispatch-02")])
    )

    assert report["dispatches"] == 2
    assert report["no_digest"] == [1, 2]
    assert report["stale"] == []
    assert report["deviations"] == []
    assert "no-digest: 2/2 (100.0%)" in dispatch_audit._format_report(report)


def test_audit_reads_numbered_archives_before_current_trail(audit_tmp_path: Path) -> None:
    package = _package(audit_tmp_path, [_dispatch(id="dispatch-current")])
    archive = package / "execution" / "initial" / "trail.001.jsonl"
    archive.write_text(json.dumps(_dispatch(id="dispatch-archived")) + "\n", encoding="utf-8")

    report = dispatch_audit.audit_package(package)

    assert report["dispatches"] == 2
    assert report["trails"] == [
        str(archive),
        str(package / "execution" / "initial" / "trail.jsonl"),
    ]
    assert report["trail"] == str(package / "execution" / "initial" / "trail.jsonl")


def test_normal_digest_is_checked_against_replayed_action(audit_tmp_path: Path, monkeypatch) -> None:
    digest = "a1b2c3d4e5f6"
    head = "0123456789abcdef0123456789abcdef01234567"
    package = _package(
        audit_tmp_path,
        [_dispatch(chosen="dispatch-investigate", situation_digest=digest, head=head)],
    )
    monkeypatch.setattr(
        dispatch_audit,
        "replay_situation",
        lambda _package_arg, _head_arg: (
            {
                "digest": digest,
                "at": head,
                "head": head,
                "selected": {"subject": "ticket:TKT-01", "action_ids": ["dispatch-investigate"]},
            },
            None,
        ),
    )

    report = dispatch_audit.audit_package(package)

    assert report["no_digest"] == []
    assert report["deviations"] == []
    assert report["uncheckable"] == []
    assert report["replayed"] == 1


def test_action_outside_replayed_situation_is_deviation(audit_tmp_path: Path, monkeypatch) -> None:
    digest = "a1b2c3d4e5f6"
    head = "0123456789abcdef0123456789abcdef01234567"
    package = _package(
        audit_tmp_path,
        [_dispatch(chosen="block-ticket", situation_digest=digest, head=head)],
    )
    monkeypatch.setattr(
        dispatch_audit,
        "replay_situation",
        lambda _package_arg, _head_arg: (
            {
                "digest": digest,
                "at": head,
                "head": head,
                "selected": {"subject": "ticket:TKT-01", "action_ids": ["dispatch-investigate"]},
            },
            None,
        ),
    )

    report = dispatch_audit.audit_package(package)

    assert report["deviations"] == [
        {
            "line": 1,
            "chosen": "block-ticket",
            "reason": "chosen action is absent from replayed situation actions",
        }
    ]


def test_replay_calls_situation_at_json(audit_tmp_path: Path, monkeypatch) -> None:
    head = "0123456789abcdef0123456789abcdef01234567"
    calls = []

    def fake_run(command, **_kwargs):
        calls.append(command)
        if command[0] == "git":
            return SimpleNamespace(returncode=0, stdout=f"{head}\n", stderr="")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"at": head, "head": head, "digest": "a1b2c3d4e5f6"}),
            stderr="",
        )

    monkeypatch.setattr(dispatch_audit.subprocess, "run", fake_run)

    rendered, error = dispatch_audit.replay_situation(audit_tmp_path, head)

    assert error is None
    assert rendered["digest"] == "a1b2c3d4e5f6"
    assert calls[1][-3:] == ["--at", head, "--json"]


def test_three_consecutive_same_digests_are_stale(audit_tmp_path: Path) -> None:
    digest = "a1b2c3d4e5f6"
    rows = [_dispatch(id=f"dispatch-{index}", situation_digest=digest) for index in range(1, 4)]

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert len(report["stale"]) == 1
    assert report["stale"][0] == {"digest": digest, "count": 3, "lines": [1, 2, 3]}


def test_fact_subject_key_and_missing_key_are_schema_violations(audit_tmp_path: Path) -> None:
    row = {
        "kind": "fact",
        "subject": "trail.reviewer_unavailable",
        "value": True,
        "ts": "2026-08-15T12:00:00Z",
    }

    report = dispatch_audit.audit_package(_package(audit_tmp_path, [row]))

    assert len(report["schema_violations"]) == 1
    assert set(report["schema_violations"][0]["issues"]) == {"missing-key", "subject-is-fact-key"}


def test_fact_schema_handles_non_scalar_subject(audit_tmp_path: Path) -> None:
    report = dispatch_audit.audit_package(
        _package(
            audit_tmp_path,
            [{"kind": "fact", "subject": ["not-a-scope"], "value": True, "ts": "2026-08-15T12:00:00Z"}],
        )
    )

    assert report["schema_violations"][0]["issues"] == ["missing-key"]


def test_legacy_candidate_snapshot_is_ignored_without_schema_violation(audit_tmp_path: Path) -> None:
    row = {"kind": "fact", "key": "dispatch.candidates", "subject": "dispatch.candidates"}

    report = dispatch_audit.audit_package(_package(audit_tmp_path, [row]))

    assert report["schema_violations"] == []
