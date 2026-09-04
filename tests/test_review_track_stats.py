from __future__ import annotations

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "review_track_stats.py"
STATE_CLI = ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_state.py"
PACKAGE_FIXTURE = ROOT / "tests" / "fixtures" / "impl-package-ticket-first"


def load_module():
    spec = importlib.util.spec_from_file_location("review_track_stats", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def make_package(tmp_path: Path, attempts: tuple[str, ...] = ("initial",)) -> Path:
    package = tmp_path / "package"
    (package / ".impl-package").mkdir(parents=True)
    history = [
        {
            "id": attempt,
            "plan": "plan.md",
            "lifecycle": "active" if index == len(attempts) - 1 else "frozen",
            "gate": None,
            "executionRecord": f"execution/{attempt}/execution-record.md",
        }
        for index, attempt in enumerate(attempts)
    ]
    state = {
        "formatVersion": "3.5",
        "attempt": {"id": attempts[-1], "plan": "plan.md"},
        "attemptHistory": history,
        "tickets": {"TKT-01": {"state": "PENDING"}, "TKT-02": {"state": "PENDING"}},
        "predecessors": None,
        "evidenceIndex": {},
        "activeCheckpoints": {},
    }
    (package / ".impl-package" / "state.json").write_text(
        json.dumps(state), encoding="utf-8"
    )
    for attempt in attempts:
        attempt_dir = package / "execution" / attempt
        attempt_dir.mkdir(parents=True)
        (attempt_dir / "execution-record.md").write_text("", encoding="utf-8")
    return package


def make_runtime_package(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    package = repo / "docs" / "implementations" / "20260813-example"
    (package / "tickets").mkdir(parents=True)
    shutil.copy2(PACKAGE_FIXTURE / "ticket-only-plan.md", package / "plan.md")
    (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
    (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
    for source in (PACKAGE_FIXTURE / "tickets").glob("*.md"):
        shutil.copy2(source, package / "tickets" / source.name)
    for command in (
        ("git", "init"),
        ("git", "config", "user.email", "test@example.com"),
        ("git", "config", "user.name", "Review stats fixture"),
        ("git", "add", "."),
        ("git", "commit", "-m", "fixture"),
    ):
        result = subprocess.run(command, cwd=repo, capture_output=True, text=True, check=False)
        assert result.returncode == 0, result.stderr
    result = subprocess.run(
        [
            sys.executable,
            str(STATE_CLI),
            "--package",
            str(package),
            "package",
            "init",
            "--attempt",
            "initial",
            "--plan",
            "docs/implementations/20260813-example/plan.md",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return package


def finding(
    key: str,
    *,
    tracks: list[str] | None = None,
    lifecycle: str = "open",
    tickets: list[str] | None = None,
    classification: str = "blocker",
) -> dict[str, object]:
    return {
        "findingKey": key,
        "id": f"F-{key}",
        "title": f"Title {key}",
        "ticketIds": ["TKT-01"] if tickets is None else tickets,
        "tracks": ["Track A"] if tracks is None else tracks,
        "classification": classification,
        "lifecycle": lifecycle,
    }


def summary(
    run: str,
    findings: list[dict[str, object]],
    *,
    phase: str = "initial",
    head: str = "a" * 40,
) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "reviewRunId": run,
        "phase": phase,
        "resolvedHead": head,
        "findings": findings,
    }


def row(value: object, *, seq: int, ts: str, **extra: object) -> dict[str, object]:
    return {
        "v": 1,
        "seq": seq,
        "ts": ts,
        "kind": "fact",
        "subject": "review:run-1",
        "key": "review.canonical_summary",
        "value": value,
        "head": "a" * 40,
        **extra,
    }


def write_trail(package: Path, attempt: str, filename: str, rows: list[dict[str, object]]) -> None:
    path = package / "execution" / attempt / filename
    path.write_text("\n".join(json.dumps(item) for item in rows) + "\n", encoding="utf-8")


def test_calculate_deduplicates_latest_finding_and_counts_multiple_tracks(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    first = summary(
        "run-1",
        [
            finding("same", tracks=["Track A", "Track C"]),
            finding("closed", tracks=["Track B"], lifecycle="closed", classification="follow-up"),
        ],
    )
    latest = summary("run-2", [finding("same", tracks=["Track D"], lifecycle="closed")])
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [row(first, seq=1, ts="2026-09-01T10:00:00Z"), row(latest, seq=2, ts="2026-09-01T11:00:00Z")],
    )

    result = module.calculate_review_stats(package)

    assert result["totals"] == {
        "unique": 2,
        "open": 0,
        "closed": 2,
        "trackContributions": 2,
        "unattributed": 0,
    }
    assert result["tracks"]["Track D"] == {"caught": 1, "open": 0, "closed": 1}
    assert result["tracks"]["Track A"] == {"caught": 0, "open": 0, "closed": 0}
    assert result["tickets"]["TKT-01"]["unique"] == 2


def test_latest_complete_summary_replaces_earlier_run_contents(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [
            row(
                summary("run-1", [finding("kept"), finding("removed")]),
                seq=1,
                ts="2026-09-01T10:00:00Z",
            ),
            row(
                summary("run-1", [finding("kept", lifecycle="closed")], phase="finding-closure"),
                seq=2,
                ts="2026-09-01T11:00:00Z",
            ),
        ],
    )

    result = module.calculate_review_stats(package)

    assert result["totals"]["unique"] == 1
    assert result["totals"]["closed"] == 1
    assert result["tickets"]["TKT-01"]["unique"] == 1


def test_calculate_reads_archives_and_all_attempts_with_ticket_filter(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path, ("initial", "rework"))
    write_trail(
        package,
        "initial",
        "trail.001.jsonl",
        [row(summary("old", [finding("old", tickets=["TKT-02"])]), seq=1, ts="2026-08-01T10:00:00Z")],
    )
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [row(summary("initial", [finding("same", tickets=["TKT-01"])]), seq=2, ts="2026-08-02T10:00:00Z")],
    )
    write_trail(
        package,
        "rework",
        "trail.jsonl",
        [row(summary("rework", [finding("same", tickets=["TKT-01"], lifecycle="closed")]), seq=1, ts="2026-08-03T10:00:00Z")],
    )

    all_results = module.calculate_review_stats(package)
    filtered = module.calculate_review_stats(package, attempt="initial", ticket="TKT-02")

    assert all_results["totals"]["unique"] == 2
    assert all_results["totals"]["closed"] == 1
    assert all_results["coverage"]["attempts"] == 2
    assert all_results["coverage"]["trails"] == 3
    assert filtered["totals"]["unique"] == 1
    assert set(filtered["tickets"]) == {"TKT-02"}
    assert filtered["tickets"]["TKT-02"]["open"] == 1


def test_empty_tracks_count_as_unattributed_and_invalid_summary_is_warned(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    valid_legacy = summary("legacy", [finding("legacy", tracks=[])])
    invalid = {"schemaVersion": 1, "reviewRunId": "bad", "phase": "initial", "findings": []}
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [
            row(valid_legacy, seq=1, ts="2026-09-01T10:00:00Z"),
            row(invalid, seq=2, ts="2026-09-01T11:00:00Z"),
        ],
    )

    result = module.calculate_review_stats(package)

    assert result["totals"]["unattributed"] == 1
    assert result["totals"]["trackContributions"] == 0
    assert result["coverage"]["summaries"] == 1
    assert any("invalid canonical summary" in warning for warning in result["coverage"]["warnings"])
    assert str(package) not in json.dumps(result["coverage"]["warnings"])


def test_review_activity_without_canonical_summary_is_reported_as_incomplete(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [{
            "v": 1,
            "seq": 1,
            "ts": "2026-09-01T10:00:00Z",
            "kind": "worker-return",
            "subject": "ticket:TKT-01",
            "review_track": "Track A",
            "review_phase": "initial",
            "outcome": "FAIL",
        }],
    )

    result = module.calculate_review_stats(package)

    assert result["totals"]["unique"] == 0
    assert result["coverage"]["reviewActivityRows"] == 1
    assert any("bug counts are incomplete" in warning for warning in result["coverage"]["warnings"])


def test_corrupt_state_and_trail_warnings_do_not_expose_absolute_paths(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    trail = package / "execution" / "initial" / "trail.jsonl"
    trail.write_text("{broken\n", encoding="utf-8")

    trail_result = module.calculate_review_stats(package)

    assert any("execution/initial/trail.jsonl:1" in warning for warning in trail_result["coverage"]["warnings"])
    assert str(tmp_path) not in json.dumps(trail_result["coverage"]["warnings"])

    (package / ".impl-package" / "state.json").write_text("{broken", encoding="utf-8")
    state_result = module.calculate_review_stats(package)

    assert any(".impl-package/state.json" in warning for warning in state_result["coverage"]["warnings"])
    assert str(tmp_path) not in json.dumps(state_result["coverage"]["warnings"])


def test_path_like_finding_key_is_never_reflected_in_warnings(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    path_like_key = str(tmp_path / "private" / "finding")
    legacy = summary("legacy", [finding(path_like_key, tracks=[])])
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [row(legacy, seq=1, ts="2026-09-01T10:00:00Z")],
    )

    result = module.calculate_review_stats(package)

    assert result["totals"]["unattributed"] == 1
    assert path_like_key not in json.dumps(result["coverage"]["warnings"])


def test_record_validation_rejects_empty_tracks_before_append(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    called = False

    def unexpected(*_args: object, **_kwargs: object) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(module, "_append_via_state_cli", unexpected)
    with pytest.raises(module.ReviewStatsError, match="has no tracks"):
        module.record_summary(tmp_path / "package", summary("run-1", [finding("one", tracks=[])]))
    assert called is False


def test_record_validation_rejects_missing_ticket_owner(tmp_path: Path) -> None:
    module = load_module()

    with pytest.raises(module.ReviewStatsError, match="no ticketIds"):
        module.validate_canonical_summary(summary("run-1", [finding("one", tickets=[])]))


def test_record_uses_existing_state_cli_and_subject(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    captured: dict[str, object] = {}

    class Result:
        returncode = 0
        stdout = json.dumps({"attempt": "initial", "kind": "fact", "appended": True})
        stderr = ""

    def fake_run(command: list[str], **kwargs: object) -> Result:
        captured["command"] = command
        captured["event"] = json.loads(str(kwargs["input"]))
        return Result()

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    result = module.record_summary(tmp_path / "package", summary("run-1", [finding("one")]))

    assert result["appended"] is True
    assert captured["command"][-2:] == ["trail", "append"]
    assert captured["event"]["subject"] == "review:run-1"
    assert captured["event"]["key"] == "review.canonical_summary"


def test_backfill_dry_run_and_apply_are_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_module()
    package = make_package(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    legacy = summary("legacy", [finding("one", tracks=[])])
    manifest_path.write_text(
        json.dumps({"importId": "legacy-import-1", "summaries": [legacy]}), encoding="utf-8"
    )
    appended: list[dict[str, object]] = []

    def fake_append(
        _package: Path,
        value: dict[str, object],
        *,
        import_id: str | None = None,
        import_index: int | None = None,
        import_count: int | None = None,
    ) -> dict[str, object]:
        appended.append({"value": value, "importId": import_id, "importIndex": import_index, "importCount": import_count})
        return {"appended": True, "attempt": "initial"}

    monkeypatch.setattr(module, "_append_via_state_cli", fake_append)
    dry_run = module.backfill_manifest(package, manifest_path, apply=False)
    first = module.backfill_manifest(package, manifest_path, apply=True)

    write_trail(package, "initial", "trail.jsonl", [row(legacy, seq=1, ts="2026-09-01T10:00:00Z", importId="legacy-import-1", importIndex=0, importCount=1)])
    second = module.backfill_manifest(package, manifest_path, apply=True)

    assert dry_run["dryRun"] is True
    assert dry_run["wouldAppend"] == 1
    assert first["appended"] == 1
    assert second["alreadyApplied"] is True
    assert second["wouldAppend"] == 0
    assert len(appended) == 1


def test_backfill_cli_applies_through_real_state_runtime_idempotently(tmp_path: Path) -> None:
    package = make_runtime_package(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "importId": "legacy-real-runtime-1",
                "summaries": [summary("legacy", [finding("one", tracks=[])])],
            }
        ),
        encoding="utf-8",
    )

    def run(*mode: str) -> dict[str, object]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "backfill",
                "--package",
                str(package),
                "--manifest",
                str(manifest_path),
                *mode,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        return json.loads(result.stdout)

    dry_run = run("--dry-run")
    first = run("--apply")
    second = run("--apply")
    stats_result = subprocess.run(
        [sys.executable, str(SCRIPT), "show", "--package", str(package)],
        capture_output=True,
        text=True,
        check=False,
    )

    assert dry_run["wouldAppend"] == 1
    assert first["appended"] == 1
    assert second["alreadyApplied"] is True
    assert json.loads(stats_result.stdout)["totals"]["unattributed"] == 1


def test_cli_show_json_and_text(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    write_trail(package, "initial", "trail.jsonl", [row(summary("run-1", [finding("one")]), seq=1, ts="2026-09-01T10:00:00Z")])

    json_result = subprocess.run(
        [sys.executable, str(SCRIPT), "show", "--package", str(package), "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    text_result = subprocess.run(
        [sys.executable, str(SCRIPT), "show", "--package", str(package), "--format", "text"],
        capture_output=True,
        text=True,
        check=False,
    )

    assert json_result.returncode == 0, json_result.stderr
    assert json.loads(json_result.stdout)["totals"]["unique"] == 1
    assert text_result.returncode == 0, text_result.stderr
    assert "Track A: 1" in text_result.stdout


def test_invalid_manifest_and_unknown_attempt_fail_closed(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"importId": "x", "summaries": []}), encoding="utf-8")

    with pytest.raises(module.ReviewStatsError, match="non-empty list"):
        module.backfill_manifest(package, manifest_path, apply=False)
    result = module.calculate_review_stats(package, attempt="missing")
    assert result["totals"]["unique"] == 0
    assert any("not present" in warning for warning in result["coverage"]["warnings"])


def test_backfill_rejects_reused_import_id_with_different_summary(tmp_path: Path) -> None:
    module = load_module()
    package = make_package(tmp_path)
    manifest_path = tmp_path / "manifest.json"
    expected = summary("legacy", [finding("expected", tracks=[])])
    conflicting = summary("legacy", [finding("conflicting", tracks=[])])
    manifest_path.write_text(
        json.dumps({"importId": "legacy-import-1", "summaries": [expected]}),
        encoding="utf-8",
    )
    write_trail(
        package,
        "initial",
        "trail.jsonl",
        [
            row(
                conflicting,
                seq=1,
                ts="2026-09-01T10:00:00Z",
                importId="legacy-import-1",
                importIndex=0,
                importCount=1,
            )
        ],
    )

    with pytest.raises(module.ReviewStatsError, match="conflicting summary"):
        module.backfill_manifest(package, manifest_path, apply=False)
