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
            "attempt.record.ticket-boundary-handoff",
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
    assert "无法判定 31 行\n" in full
    assert "无法判定 30 行:" not in full
    assert "package.record.projection-drift" not in full
    digest_line = full.rsplit("\n", 1)[-1]
    assert digest_line.startswith("digest: ")
    digest = digest_line.removeprefix("digest: ")
    assert len(digest) == 12

    explained = _render_text(package, "--explain-undetermined")
    assert "无法判定 31 行: package.record.projection-drift (package)" in explained

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
        assert set(credential) == {"digest", "ts", "state_sha256"}
        assert credential["digest"] == rendered["digest"]
        assert len(credential["ts"]) > 10
        assert credential["state_sha256"] == hashlib.sha256(state_path.read_bytes()).hexdigest()
        assert not credential_bytes.startswith(b"\xef\xbb\xbf")


def test_render_since_writes_situation_digest_credential() -> None:
    source = FIXTURES / "p0-evidence-unfiled"
    with tempfile.TemporaryDirectory(dir=ROOT) as temporary:
        package = Path(temporary) / source.name
        shutil.copytree(source, package)
        first = json.loads(_invoke_render(package, "--json").stdout)
        second_run = _invoke_render(package, "--json", "--since", first["digest"])
        assert second_run.returncode == 0, second_run.stderr
        assert json.loads(second_run.stdout) == {"digest": first["digest"], "unchanged": True}

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


def test_json_render_exposes_digest_and_short_circuits_since() -> None:
    package = ROOT / "tests/fixtures/situations-a2/p0-evidence-unfiled"
    rendered = json.loads(_render_text(package, "--json"))
    assert rendered["unchanged"] is False
    assert len(rendered["digest"]) == 12

    unchanged = json.loads(_render_text(package, "--json", "--since", rendered["digest"]))
    assert unchanged == {
        "digest": rendered["digest"],
        "unchanged": True,
    }
