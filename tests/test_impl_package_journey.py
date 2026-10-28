from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import engine  # noqa: E402
import situation  # noqa: E402


PLAN = """# Plan

Attempt ID: initial
Predecessors: None
Composition: tickets=true, dag=false
Acceptance: journey
"""

SPEC = """# Spec

### Journeys

#### J1 纠正后下一张账单用新科目

| Step | 操作入口 | 观察表面 | 预期 |
| --- | --- | --- | --- |
| J1-S1 | 税务端 Review 页确认账单 | 门店答案读取 API | 答案为 4982 |
| J1-S2 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” |

### Rule Matrix

| Rule | Suite | Oracle |
| --- | --- | --- |
| R1 | S-resolver | 解析表每行来源与状态正确 |

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-resolver | rule | ticket | pnpm test resolver | local-test |
| S-workflow | rule | ticket | pnpm test workflow | local-test |
| S-safety | safety | package | pnpm test:integration tenant | local-pg |
"""


def _ticket(ticket_id: str, journey_steps: str, suites: str) -> str:
    return f"""# {ticket_id}

Ticket ID: {ticket_id}
Publication Status: Draft
Attempt ID: initial

## Coverage

- Journey steps: {journey_steps}
- Suites: {suites}
- Required review: none

## Blocking Dependencies

- none
"""


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def _make_package(
    root: Path,
    *,
    plan: str = PLAN,
    spec: str = SPEC,
    tickets: dict[str, str] | None = None,
) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "journey@example.com")
    _git(repo, "config", "user.name", "Journey Fixture")
    package = repo / "docs/implementations/20261028-journey-phase1"
    (package / "tickets").mkdir(parents=True)
    (package / "artifacts").mkdir()
    (package / "execution").mkdir()
    (package / "plan.md").write_text(plan, encoding="utf-8")
    (package / "spec.md").write_text(spec, encoding="utf-8")
    (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
    (package / "artifacts/evidence.md").write_text("fixture evidence\n", encoding="utf-8")
    ticket_docs = tickets or {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow"),
    }
    for name, text in ticket_docs.items():
        (package / "tickets" / name).write_text(text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Journey fixture")
    return repo, package


def _cli(repo: Path, package: Path, *args: str, input_value: object | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["IMPL_PACKAGE_NO_SITUATION"] = "1"
    input_text = None if input_value is None else json.dumps(input_value, ensure_ascii=False)
    return subprocess.run(
        [sys.executable, str(CLI), "--package", str(package), *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _init(repo: Path, package: Path, *, ok: bool = True) -> subprocess.CompletedProcess[str]:
    result = _cli(
        repo,
        package,
        "package",
        "init",
        "--attempt",
        "initial",
        "--plan",
        "docs/implementations/20261028-journey-phase1/plan.md",
    )
    if ok:
        assert result.returncode == 0, result.stderr or result.stdout
    return result


def _state(package: Path) -> dict:
    return json.loads((package / ".impl-package/state.json").read_text(encoding="utf-8"))


def _init_v36(root: Path) -> tuple[Path, Path, str]:
    repo, package = _make_package(root)
    result = _init(repo, package)
    state = json.loads(result.stdout)
    assert state["formatVersion"] == "3.6"
    return repo, package, _git(repo, "rev-parse", "HEAD")


def _journey_record(revision: str, step_id: str, *, run_id: str = "run-1", environment: str = "local-test") -> dict:
    entries = {
        "J1-S1": "税务端 Review 页确认账单",
        "J1-S2": "企业端打开下一张同类账单",
    }
    return {
        "kind": "journey-step",
        "runId": run_id,
        "journeyId": "J1",
        "stepId": step_id,
        "entry": entries[step_id],
        "artifact": "artifacts/evidence.md",
        "revision": revision,
        "environment": environment,
        "conclusion": "supporting",
    }


def test_init_validate_and_status_use_v36_and_record_contract_baseline(tmp_path: Path) -> None:
    repo, package, _ = _init_v36(tmp_path)
    state = _state(package)

    assert state["acceptance"]["releaseOrder"] == "none"
    assert state["acceptance"]["amendments"] == []
    assert set(state["acceptance"]["contractBaseline"]["files"]) == {"decision.md", "spec.md"}
    assert state["acceptance"]["contractBaseline"]["head"] == _git(repo, "rev-parse", "HEAD")
    assert state["tickets"] == {"TKT-01": {"state": "PENDING"}, "TKT-02": {"state": "PENDING"}}
    for command in ("validate", "status"):
        result = _cli(repo, package, "package", command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["formatVersion"] == "3.6"


def test_init_persists_required_release_order(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")

    result = _init(repo, package)

    assert result.returncode == 0, result.stderr
    assert _state(package)["acceptance"]["releaseOrder"] == "required"


@pytest.mark.parametrize(
    ("spec", "tickets", "message"),
    [
        (SPEC.replace("| 操作入口 |", "| 入口 |"), None, "columns must be"),
        (SPEC.replace("| J1-S1 | 税务端 Review 页确认账单 |", "| J1-S1 |  |"), None, "empty cell"),
        (SPEC, {"01.md": _ticket("TKT-01", "J1-S9", "S-resolver"), "02.md": _ticket("TKT-02", "J1-S2", "S-workflow")}, "unknown Journey step"),
        (SPEC, {"01.md": _ticket("TKT-01", "J1-S1", "S-unknown"), "02.md": _ticket("TKT-02", "J1-S2", "S-workflow")}, "unknown suite"),
        (SPEC, {"01.md": _ticket("TKT-01", "J1-S1", "S-resolver"), "02.md": _ticket("TKT-02", "none", "S-workflow")}, "no Ticket Coverage"),
        (SPEC, {"01.md": _ticket("TKT-01", "J1-S1", "none"), "02.md": _ticket("TKT-02", "J1-S2", "S-workflow")}, "ticket-scope suites have no Ticket Coverage"),
        (SPEC, {"01.md": _ticket("TKT-01", "none", "none"), "02.md": _ticket("TKT-02", "J1-S2", "S-workflow")}, "cannot both be none"),
    ],
)
def test_init_rejects_invalid_journey_contracts(
    tmp_path: Path, spec: str, tickets: dict[str, str] | None, message: str
) -> None:
    repo, package = _make_package(tmp_path, spec=spec, tickets=tickets)

    result = _init(repo, package, ok=False)

    assert result.returncode != 0
    assert message in result.stderr
    assert not (package / ".impl-package/state.json").exists()


def test_validate_still_reports_ticket_ids_named_in_spec(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, spec=SPEC + "\nThis contract mentions TKT-01.\n")
    _init(repo, package)

    result = _cli(repo, package, "package", "validate")

    assert result.returncode == 0, result.stderr
    findings = json.loads(result.stdout)["findings"]
    assert any(item["code"] == "contract-doc-names-ticket" and item["path"] == "spec.md" for item in findings)


def test_evidence_add_supports_all_kinds_idempotence_and_atomic_batch(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    journey = _journey_record(revision, "J1-S1")
    journey["evidenceKey"] = "journey:run-1:J1-S1"
    records = [
        journey,
        {"kind": "suite", "suiteId": "S-resolver", "artifact": "artifacts/evidence.md", "revision": revision, "environment": "local-test", "conclusion": "supporting"},
        {"kind": "review", "ticket": "TKT-01", "artifact": "artifacts/evidence.md", "revision": revision, "environment": "local-test", "conclusion": "supporting"},
        {"kind": "release", "artifact": "artifacts/evidence.md", "revision": revision, "environment": "local-test", "conclusion": "supporting"},
    ]

    added = _cli(repo, package, "evidence", "add", input_value=records)
    assert added.returncode == 0, added.stderr
    assert json.loads(added.stdout)["added"] == 4
    state = _state(package)
    assert set(state["evidenceIndex"]) == {"journey:run-1:J1-S1", "suite:S-resolver", "review:TKT-01", "release"}
    assert "evidenceKey" not in state["evidenceIndex"]["journey:run-1:J1-S1"][0]

    duplicate = _cli(repo, package, "evidence", "add", input_value=records)
    assert duplicate.returncode == 0, duplicate.stderr
    assert json.loads(duplicate.stdout)["added"] == 0

    before = _state(package)
    invalid_batch = [
        _journey_record(revision, "J1-S1", run_id="atomic"),
        {**_journey_record(revision, "J1-S2", run_id="atomic"), "entry": "wrong entry"},
    ]
    failed = _cli(repo, package, "evidence", "add", input_value=invalid_batch)
    assert failed.returncode != 0
    assert "operation entry" in failed.stderr
    assert _state(package) == before


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"kind": "journey-step", "runId": "run", "journeyId": "J1", "stepId": "J1-S1", "entry": "wrong", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "operation entry"),
        ({"kind": "suite", "suiteId": "S-unknown", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "unknown required suite"),
        ({"kind": "review", "ticket": "TKT-unknown", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "known Ticket or package"),
        ({"kind": "release", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting", "ticket": "TKT-01"}, "missing or unknown fields"),
        ({"kind": "release", "artifact": "../external.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "package-relative"),
    ],
)
def test_evidence_add_rejects_entry_unknown_suite_and_external_artifact(tmp_path: Path, record: dict, message: str) -> None:
    repo, package, revision = _init_v36(tmp_path)
    record = {**record, "revision": revision}

    result = _cli(repo, package, "evidence", "add", input_value=record)

    assert result.returncode != 0
    assert message in result.stderr
    assert _state(package)["evidenceIndex"] == {}


def test_journey_reach_is_contiguous_per_run_and_invalidation_uses_key(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    first = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert first.returncode == 0, first.stderr
    assert "J1 走通 1/2" in (package / "progress.md").read_text(encoding="utf-8")

    second = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2"))
    assert second.returncode == 0, second.stderr
    assert "J1 走通 2/2" in (package / "progress.md").read_text(encoding="utf-8")
    assert "S-resolver" in (package / "progress.md").read_text(encoding="utf-8")
    assert "TKT-01 | PENDING" in (package / "progress.md").read_text(encoding="utf-8")

    invalidated = _cli(repo, package, "evidence", "invalidate", "--key", "journey:run-1:J1-S1", "--invalidated-by", "fixture")
    assert invalidated.returncode == 0, invalidated.stderr
    assert "J1 走通 0/2" in (package / "progress.md").read_text(encoding="utf-8")
    repeated = _cli(repo, package, "evidence", "invalidate", "--key", "journey:run-1:J1-S1", "--invalidated-by", "fixture")
    assert repeated.returncode == 0, repeated.stderr
    assert json.loads(repeated.stdout)["idempotent"] is True


def test_skipping_first_step_has_zero_reach_and_mixed_run_environment_is_atomic(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    skipped = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2", run_id="skip-first"))
    assert skipped.returncode != 0
    assert "must start at J1-S1" in skipped.stderr
    assert _state(package)["evidenceIndex"] == {}

    complete_run = [
        _journey_record(revision, "J1-S1", run_id="run-to-invalidate"),
        _journey_record(revision, "J1-S2", run_id="run-to-invalidate"),
    ]
    added = _cli(repo, package, "evidence", "add", input_value=complete_run)
    assert added.returncode == 0, added.stderr
    invalidated = _cli(repo, package, "evidence", "invalidate", "--key", "journey:run-to-invalidate:J1-S1", "--invalidated-by", "fixture")
    assert invalidated.returncode == 0, invalidated.stderr
    assert "J1 走通 0/2" in (package / "progress.md").read_text(encoding="utf-8")

    before = _state(package)
    mixed = [
        _journey_record(revision, "J1-S1", run_id="mixed", environment="local-test"),
        _journey_record(revision, "J1-S2", run_id="mixed", environment="other-test"),
    ]
    failed = _cli(repo, package, "evidence", "add", input_value=mixed)
    assert failed.returncode != 0
    assert "one Journey and environment" in failed.stderr
    assert _state(package) == before


def test_v36_situation_parser_reads_state_and_terminal_fact_without_format_error(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert added.returncode == 0, added.stderr
    state = _state(package)
    parsed = situation._parse_state(situation.FileView("state.json", json.dumps(state)))

    assert parsed.valid, parsed.error
    tickets = {}
    for path in (package / "tickets").glob("*.md"):
        ticket_id = "TKT-01" if path.name == "01.md" else "TKT-02"
        tickets[ticket_id] = situation._parse_ticket(
            ticket_id,
            path.relative_to(package).as_posix(),
            path.read_text(encoding="utf-8"),
            "initial",
        )
    assert situation._state_ticket_errors(parsed, tickets) == []
    fact = situation.terminal_coverage_fact(package)
    assert isinstance(fact, situation.Fact)
    assert "3.5 schema" not in (fact.reason or "")


def test_v36_is_not_claim_validated_while_v35_rejects_v36_fields(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    state = _state(package)
    summary = engine._validate_state(package, state, projections=False)
    assert summary["_claims"] == {"TKT-01": set(), "TKT-02": set()}
    state["tickets"]["TKT-01"] = {"state": "SATISFIED", "acceptance": {"revision": revision, "environment": "local-test"}}
    engine._validate_state(package, state, projections=False)
    failed_satisfy = _cli(repo, package, "ticket", "satisfy", "TKT-01", "--expect", "PENDING", "--revision", revision, "--environment", "local-test")
    assert failed_satisfy.returncode != 0
    assert "phase 1a" in failed_satisfy.stderr

    old_plan = PLAN.replace("Acceptance: journey\n", "")
    old_ticket = """# TKT-01

Ticket ID: TKT-01
Publication Status: Draft
Attempt ID: initial

## Acceptance Criteria
- Stable claim ID: `AC-1`
- Evidence timing: `remaining-completion`

## Blocking Dependencies
- none
"""
    old_repo, old_package = _make_package(tmp_path / "legacy", plan=old_plan, tickets={"01.md": old_ticket})
    _init(old_repo, old_package)
    old_state = _state(old_package)
    assert old_state["formatVersion"] == "3.5"
    old_state["acceptance"] = {"contractBaseline": {}, "releaseOrder": "none", "amendments": []}
    (old_package / ".impl-package/state.json").write_text(json.dumps(old_state), encoding="utf-8")
    rejected = _cli(old_repo, old_package, "package", "status")
    assert rejected.returncode != 0
    assert "formatVersion 3.5" in rejected.stderr
    assert "activeCheckpoints" in rejected.stderr
