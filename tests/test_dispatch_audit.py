import importlib.util
import json
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest


def _execution_rows(*, pending=False, review=True, receipt=True):
    delta = {"base": "a" * 40, "head": "b" * 40}
    candidates = [
        {"candidate_id": name, "subject": "ticket:TKT-01", "mode": "implement", "action_id": "implement", "resource_keys": [name]}
        for name in ("A", "B")
    ]
    rows = [{"kind": "fact", "key": "dispatch.candidates", "subject": "attempt", "seq": 1, "value": {"attempt": "initial", "head": "head", "state_sha256": "state", "candidates": candidates, "available_slots": 2}}]
    for name in ("A", "B"):
        rows.append({"kind": "dispatch", "dispatch_id": name, "subject": "ticket:TKT-01", "worker": name,
                     "outcome": "RUNNING", "returned": False, "receipt": name if receipt else None,
                     "candidate_id": name, "candidates_of": 1, "chosen": "implement", "mode": "implement",
                     "resource_keys": [name], "head": "head", "state_sha256": "state", "runnable_candidate_ids": ["A", "B"]})
    rows.append({"kind": "worker-return", "of": "A", "return_id": "return-A", "subject": "ticket:TKT-01",
                 "outcome": "INCOMPLETE", "code_delta": delta, "consumption_id": "consume-A"})
    if pending:
        rows.append({"kind": "fact", "key": "review.dispatch_pending", "subject": "ticket:TKT-01",
                     "value": {"return_id": "return-A", "code_delta": delta, "consumption_id": "consume-A", "capacity": 0, "reason": "all slots occupied"}})
    rows.append({"kind": "worker-return", "of": "B", "return_id": "return-B", "subject": "ticket:TKT-01", "outcome": "DONE"})
    if review:
        snapshot_seq = len(rows) + 1
        rows.append({"kind": "fact", "key": "dispatch.candidates", "subject": "attempt", "seq": snapshot_seq,
                     "value": {"attempt": "initial", "head": "head", "state_sha256": "state", "available_slots": 1,
                     "candidates": [{"candidate_id": "review-A", "subject": "ticket:TKT-01", "mode": "verify", "action_id": "delta-review", "resource_keys": ["snapshot:A"]}]}})
        rows.append({"kind": "dispatch", "dispatch_id": "review-A", "subject": "ticket:TKT-01", "worker": "reviewer",
                     "outcome": "RUNNING", "returned": False, "receipt": "review-receipt", "reviews": "return-A",
                     "code_delta": delta, "consumption_id": "consume-A", "resource_keys": ["snapshot:A"],
                     "candidate_id": "review-A", "candidates_of": snapshot_seq, "chosen": "delta-review", "mode": "verify",
                     "head": "head", "state_sha256": "state", "runnable_candidate_ids": ["review-A"]})
    return rows


def test_dispatch_audit_keeps_same_ticket_concurrency_and_per_return_review():
    rows = _execution_rows()
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["concurrent_dispatches"] == [{"dispatch_ids": ["A", "B"], "lines": [2, 3]}]
    assert report["parallel_opportunities"] == ["A", "B"]
    assert report["pending_reviews"] == []
    assert report["execution_issues"] == []


def test_last_code_return_is_pending_even_without_a_next_implementation():
    rows = _execution_rows(pending=True, review=False)
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["pending_reviews"][0]["return_id"] == "return-A"
    assert report["pending_reviews"][0]["recorded"] is True
    assert report["execution_issues"] == []
    assert any("capacity-restoration" in item["reason"] for item in report["execution_uncheckable"])


def test_missing_receipt_and_duplicate_return_cannot_count_as_execution():
    rows = _execution_rows(receipt=False)
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["concurrent_dispatches"] == []
    assert any("receipt" in item["reason"] for item in report["execution_issues"])
    rows = _execution_rows()
    rows.append(dict(rows[3]))
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any(item["reason"] == "duplicate return_id" for item in report["execution_issues"])


def test_capacity_restoration_prioritizes_pending_review_and_keeps_delta_fixed():
    rows = _execution_rows(pending=True, review=False)
    rows.append({"kind": "fact", "key": "dispatch.candidates", "subject": "attempt", "seq": 7,
                 "value": {"attempt": "initial", "available_slots": 1, "candidates": []}})
    next_dispatch = dict(rows[1], dispatch_id="C", worker="C")
    rows.append(next_dispatch)
    rows.extend(_execution_rows()[-1:])
    rows[-1]["consumption_id"] = "later-consume"
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any("available slot" in item["reason"] for item in report["execution_issues"])
    rows[-1]["code_delta"] = {"base": "a" * 40, "head": "c" * 40}
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any("fixed return delta" in item["reason"] for item in report["execution_issues"])


def test_new_action_allowlist_excludes_withheld_and_old_suppressed_matches():
    rendered = {"blocking": [], "runnable": [{"subject": "ticket:T", "action_ids": ["run"]}],
                "withheld": [{"subject": "ticket:T", "action_ids": ["held"]}],
                "suppressed_matches": [{"subject": "ticket:T", "action_ids": ["old"]}]}
    assert dispatch_audit._action_ids(rendered, "ticket:T") == {"run"}
    assert dispatch_audit._action_ids(rendered, "ticket:T", legacy=True) == {"old"}


def test_malformed_new_trail_is_uncheckable_instead_of_crashing():
    rows = _execution_rows(review=False)
    rows[0]["seq"] = []
    rows[1]["candidates_of"] = {}
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert report["concurrent_dispatches"] == []
    assert any("snapshot" in item["reason"] for item in report["execution_uncheckable"])


def test_done_candidate_cannot_be_dispatched_again_under_another_dispatch_id():
    rows = _execution_rows(review=False)
    rows.append(dict(rows[2], dispatch_id="B-again"))
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any(item["reason"] == "candidate already running or DONE" for item in report["execution_issues"])


def test_new_dispatch_uses_recorded_render_evidence_without_guessing_git_state(audit_tmp_path, monkeypatch):
    rows = _execution_rows(pending=True, review=False)
    for row in rows:
        if row["kind"] == "dispatch":
            row["situation_digest"] = "123456abcdef"
    monkeypatch.setattr(dispatch_audit, "replay_situation", lambda *_: pytest.fail("new dispatch should use its recorded credential evidence"))
    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert report["candidate_checked"] == 2
    assert report["deviations"] == []
    assert report["uncheckable"] == []


def test_second_return_identity_for_same_dispatch_is_not_consumed():
    rows = _execution_rows(review=False)
    rows.append(dict(rows[3], return_id="late-A", outcome="DONE"))
    report = dispatch_audit._execution_audit(list(enumerate(rows, 1)))
    assert any("late return" in item["reason"] for item in report["execution_issues"])
    assert [item["return_id"] for item in report["pending_reviews"]] == ["return-A"]


def test_replaced_snapshot_cannot_certify_a_dispatch(audit_tmp_path):
    rows = _execution_rows(review=False)
    rows.insert(1, {"kind": "fact", "key": "dispatch.candidates", "subject": "attempt", "seq": 2,
                    "value": {"attempt": "initial", "head": "head", "state_sha256": "state", "candidates": []}})
    for row in rows:
        if row["kind"] == "dispatch":
            row["situation_digest"] = "123456abcdef"
    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert report["candidate_checked"] == 0
    assert report["deviations"] == []
    assert len(report["uncheckable"]) == 2
    assert all(item["declaration_status"] == "stale" for item in report["uncheckable"])
    assert report["concurrent_dispatches"] == []


def test_new_dispatch_without_declaration_is_uncheckable_without_head_replay(audit_tmp_path, monkeypatch):
    row = dict(_execution_rows(review=False)[1])
    row.pop("candidates_of")
    row["declaration_status"] = "missing"
    row["situation_digest"] = "123456abcdef"
    monkeypatch.setattr(dispatch_audit, "replay_situation", lambda *_: pytest.fail("new dispatch must not replay old HEAD"))

    report = dispatch_audit.audit_package(_package(audit_tmp_path, [row]))

    assert report["deviations"] == []
    assert report["candidate_checked"] == 0
    assert report["uncheckable"][0]["declaration_status"] == "missing"
    assert report["execution_issues"] == []


def test_stale_binding_is_uncheckable_but_current_field_conflict_is_an_issue(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[1]["declaration_status"] = "stale"
    rows[1]["state_sha256"] = "new-state"
    rows[1]["situation_digest"] = "123456abcdef"
    stale = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert stale["deviations"] == []
    assert stale["execution_issues"] == []
    assert stale["uncheckable"][0]["declaration_status"] == "stale"

    rows[1]["declaration_status"] = "current"
    rows[1]["state_sha256"] = "state"
    rows[1]["mode"] = "verify"
    current = dispatch_audit.audit_package(_package(audit_tmp_path / "current", rows))
    assert any("candidate" in item["reason"] for item in current["deviations"])
    assert any("candidate snapshot" in item["reason"] for item in current["execution_issues"])


def test_declaration_status_label_cannot_hide_a_current_field_conflict(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[1].update(declaration_status="stale", mode="verify", situation_digest="123456abcdef")

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert any("candidate" in item["reason"] for item in report["deviations"])
    assert any("candidate snapshot" in item["reason"] for item in report["execution_issues"])


def test_missing_or_stale_reference_does_not_bypass_latest_explicit_blocker(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[0]["value"]["candidates"][0]["blockers"] = [
        {"type": "resource", "resource_key": "A", "reason": "caller confirmed conflict"}
    ]
    rows[1].update(candidate_id="renamed-A", declaration_status="missing", situation_digest="123456abcdef")
    rows[1].pop("candidates_of")
    rows.insert(1, {"kind": "fact", "key": "dispatch.candidates", "seq": None, "value": {"candidates": "invalid"}})

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert any("known declaration blockers" in item["reason"] for item in report["deviations"])
    assert any("known declaration blockers" in item["reason"] for item in report["execution_issues"])

    rows[0]["value"]["candidates"] = []
    cleared = dispatch_audit.audit_package(_package(audit_tmp_path / "cleared", rows))
    assert cleared["deviations"] == []
    assert cleared["execution_issues"] == []


def test_explicit_resource_blocker_applies_across_candidates_only_to_its_resource(audit_tmp_path):
    rows = _execution_rows(review=False)[:1]
    rows[0]["value"]["candidates"][0]["blockers"] = [
        {"type": "resource", "resource_key": "shared", "reason": "caller confirmed conflict"}
    ]
    rows[0]["value"]["candidates"][0]["resource_keys"] = ["shared"]
    blocked = dict(_execution_rows(review=False)[1], candidate_id="other", subject="ticket:TKT-02",
                   chosen="other-action", resource_keys=["shared"], declaration_status="missing",
                   situation_digest="123456abcdef")
    blocked.pop("candidates_of")
    rows.append(blocked)

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert any("known declaration blockers" in item["reason"] for item in report["execution_issues"])

    rows[-1].update(subject="ticket:TKT-01", resource_keys=["other"])
    allowed = dispatch_audit.audit_package(_package(audit_tmp_path / "allowed", rows))
    assert allowed["execution_issues"] == []


def test_unique_subject_action_keeps_authorization_after_candidate_and_resource_rename(audit_tmp_path):
    rows = _execution_rows(review=False)[:1]
    rows[0]["value"]["candidates"] = [{
        "candidate_id": "old", "subject": "ticket:TKT-01", "mode": "implement",
        "action_id": "implement", "resource_keys": ["old-resource"],
        "blockers": [{"type": "authorization", "subject": "ticket:TKT-01", "reason": "approval missing"}],
    }]
    dispatch = dict(_execution_rows(review=False)[1], candidate_id="renamed", resource_keys=["new-resource"],
                    declaration_status="missing", situation_digest="123456abcdef")
    dispatch.pop("candidates_of")
    rows.append(dispatch)

    blocked = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert any("known declaration blockers" in item["reason"] for item in blocked["execution_issues"])

    rows[0]["value"]["candidates"].append({
        "candidate_id": "independent", "subject": "ticket:TKT-01", "mode": "implement",
        "action_id": "implement", "resource_keys": ["independent-resource"],
    })
    ambiguous = dispatch_audit.audit_package(_package(audit_tmp_path / "ambiguous", rows))
    assert ambiguous["execution_issues"] == []


def test_snapshot_from_another_or_unknown_attempt_cannot_supply_blockers(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[0]["value"]["candidates"][0]["blockers"] = [
        {"type": "authorization", "subject": "ticket:TKT-01", "reason": "owner approval missing"}
    ]
    rows[1].update(declaration_status="missing", situation_digest="123456abcdef")
    rows[1].pop("candidates_of")

    rows[0]["value"]["attempt"] = "other"
    other = dispatch_audit.audit_package(_package(audit_tmp_path, rows))
    assert other["execution_issues"] == []
    assert any("Attempt binding" in item["reason"] for item in other["execution_uncheckable"])

    rows[0]["value"].pop("attempt")
    unknown = dispatch_audit.audit_package(_package(audit_tmp_path / "unknown", rows))
    assert unknown["execution_issues"] == []
    assert any("Attempt binding" in item["reason"] for item in unknown["execution_uncheckable"])


@pytest.mark.parametrize("malformed_candidates", [
    [{}],
    [{"candidate_id": "new", "subject": "ticket:TKT-01", "mode": "review",
      "action_id": "implement", "resource_keys": []}],
    [{"candidate_id": "new", "subject": "ticket:TKT-01", "mode": "implement",
      "action_id": "implement", "resource_keys": [""]}],
    [{"candidate_id": "new", "subject": "ticket:TKT-01", "mode": "implement",
      "action_id": "implement", "resource_keys": [],
      "blockers": [{"type": "unknown", "subject": "ticket:TKT-01", "reason": "bad"}]}],
])
def test_malformed_snapshot_cannot_clear_latest_valid_blocker_or_certify_dispatch(
    audit_tmp_path, malformed_candidates
):
    rows = _execution_rows(review=False)[:1]
    rows[0]["value"]["candidates"][0]["blockers"] = [
        {"type": "authorization", "subject": "ticket:TKT-01", "reason": "approval missing"}
    ]
    rows.append({"kind": "fact", "key": "dispatch.candidates", "subject": "attempt", "seq": 2,
                 "value": {"attempt": "initial", "head": "head", "state_sha256": "state",
                           "candidates": malformed_candidates}})
    dispatch = dict(_execution_rows(review=False)[1], candidates_of=2, declaration_status="current",
                    situation_digest="123456abcdef")
    rows.append(dispatch)

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert report["candidate_checked"] == 0
    assert any("known declaration blockers" in item["reason"] for item in report["execution_issues"])
    assert any("invalid candidate snapshot shape" in item["reason"] for item in report["execution_uncheckable"])


def test_current_snapshot_may_omit_a_business_legal_dispatch_but_cannot_certify_it(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[0]["value"]["candidates"] = []
    rows[1]["declaration_status"] = "current"
    rows[1]["situation_digest"] = "123456abcdef"

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert report["deviations"] == []
    assert report["execution_issues"] == []
    assert report["candidate_checked"] == 0
    assert any("absent" in item["reason"] for item in report["uncheckable"])
    assert any("absent" in item["reason"] for item in report["execution_uncheckable"])


def test_current_candidate_without_runnable_membership_is_uncheckable_not_illegal(audit_tmp_path):
    rows = _execution_rows(review=False)[:2]
    rows[1]["declaration_status"] = "current"
    rows[1]["runnable_candidate_ids"] = []
    rows[1]["situation_digest"] = "123456abcdef"

    report = dispatch_audit.audit_package(_package(audit_tmp_path, rows))

    assert report["deviations"] == []
    assert report["execution_issues"] == []
    assert report["candidate_checked"] == 0
    assert any("runnable candidate evidence" in item["reason"] for item in report["uncheckable"])
    assert any("runnable candidate evidence" in item["reason"] for item in report["execution_uncheckable"])


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
