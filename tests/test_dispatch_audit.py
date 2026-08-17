import importlib.util
import json
import sys
import tempfile
from types import SimpleNamespace
from pathlib import Path

import pytest


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
