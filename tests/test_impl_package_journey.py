from __future__ import annotations

import json
import os
import shutil
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

JOURNEY_FIXTURE = ROOT / "tests/fixtures/impl-package-journey"

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


def _ticket(ticket_id: str, journey_steps: str, suites: str, *, required_review: str = "none", dependencies: str = "- none") -> str:
    return f"""# {ticket_id}

Ticket ID: {ticket_id}
Publication Status: Draft
Attempt ID: initial

## Coverage

- Journey steps: {journey_steps}
- Suites: {suites}
- Required review: {required_review}

## Blocking Dependencies

{dependencies}
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
    (repo / "docs/implementations/retired.json").write_text('{"packages": []}\n', encoding="utf-8")
    ticket_docs = tickets or {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow"),
    }
    for name, text in ticket_docs.items():
        (package / "tickets" / name).write_text(text, encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Journey fixture")
    return repo, package


def _make_fixture_package(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "journey@example.com")
    _git(repo, "config", "user.name", "Journey Fixture")
    package = repo / "docs/implementations/20261028-journey-phase1"
    package.parent.mkdir(parents=True)
    shutil.copytree(JOURNEY_FIXTURE, package)
    (repo / "docs/implementations/retired.json").write_text('{"packages": []}\n', encoding="utf-8")
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


def _suite_record(revision: str, suite_id: str, *, conclusion: str = "supporting", environment: str | None = None) -> dict:
    return {
        "kind": "suite",
        "suiteId": suite_id,
        "artifact": "artifacts/evidence.md",
        "revision": revision,
        "environment": environment or ("local-pg" if suite_id == "S-safety" else "local-test"),
        "conclusion": conclusion,
    }


def _review_record(revision: str, ticket: str, *, conclusion: str = "supporting") -> dict:
    return {
        "kind": "review",
        "ticket": ticket,
        "artifact": "artifacts/evidence.md",
        "revision": revision,
        "environment": "local-test",
        "conclusion": conclusion,
    }


def _satisfy(
    repo: Path,
    package: Path,
    ticket: str,
    revision: str,
    *,
    environment: str | None = "local-test",
    ok: bool = True,
) -> subprocess.CompletedProcess[str]:
    args = ["ticket", "satisfy", ticket, "--expect", "PENDING", "--revision", revision]
    if environment is not None:
        args.extend(["--environment", environment])
    result = _cli(repo, package, *args)
    if ok:
        assert result.returncode == 0, result.stderr or result.stdout
    return result


def _gate(repo: Path, package: Path, verdict: str, revision: str, *, reason: str = "fixture reason") -> subprocess.CompletedProcess[str]:
    return _cli(
        repo,
        package,
        "gate",
        verdict,
        "--comparison-commit",
        revision,
        "--reason",
        reason,
        "--no-durable-delta-reason",
        "No durable delta in fixture",
    )


def _add_terminal_summary(repo: Path, package: Path, revision: str) -> None:
    results = []
    for track, suffix in (("Track A", "a"), ("Track C", "c")):
        artifact = f"artifacts/terminal-{suffix}.md"
        (package / artifact).write_text(
            f"verdict: PASS\nreviewed-head: {revision}\nreview-run: terminal-1\nreview-track: {track}\n\n",
            encoding="utf-8",
        )
        results.append({"track": track, "verdict": "PASS", "reviewedHead": revision, "artifact": artifact})
    added = _cli(
        repo,
        package,
        "trail",
        "append",
        input_value={
            "kind": "fact",
            "subject": "attempt",
            "key": "review.terminal_summary",
            "value": {"reviewRunId": "terminal-1", "comparisonHead": revision, "safetyApplicable": False, "results": results},
        },
    )
    assert added.returncode == 0, added.stderr or added.stdout


def _commit_path(repo: Path, path: Path, message: str) -> str:
    relative = path.relative_to(repo).as_posix()
    _git(repo, "add", "--", relative)
    _git(repo, "commit", "-m", message)
    return _git(repo, "rev-parse", "HEAD")


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
    assert "Suite S-resolver" in failed_satisfy.stderr

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
    missing_environment = _cli(
        old_repo,
        old_package,
        "ticket",
        "satisfy",
        "TKT-01",
        "--expect",
        "PENDING",
        "--revision",
        _git(old_repo, "rev-parse", "HEAD"),
    )
    assert missing_environment.returncode != 0
    assert "--revision and --environment" in missing_environment.stderr
    old_state["acceptance"] = {"contractBaseline": {}, "releaseOrder": "none", "amendments": []}
    (old_package / ".impl-package/state.json").write_text(json.dumps(old_state), encoding="utf-8")
    rejected = _cli(old_repo, old_package, "package", "status")
    assert rejected.returncode != 0
    assert "formatVersion 3.5" in rejected.stderr
    assert "activeCheckpoints" in rejected.stderr


def test_ticket_satisfy_uses_suite_and_required_review_without_journey_steps(tmp_path: Path) -> None:
    tickets = {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver", required_review="terminal-final"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow"),
    }
    repo, package = _make_package(tmp_path, tickets=tickets)
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")

    missing_suite = _satisfy(repo, package, "TKT-01", revision, ok=False)
    assert "Suite S-resolver" in missing_suite.stderr
    added_suite = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, "S-resolver"))
    assert added_suite.returncode == 0, added_suite.stderr
    unrelated = _git(repo, "commit-tree", f"{revision}^{{tree}}", "-m", "unrelated root")
    wrong_revision = _satisfy(repo, package, "TKT-01", unrelated, ok=False)
    assert "ancestor of current HEAD" in wrong_revision.stderr
    missing_review = _satisfy(repo, package, "TKT-01", revision, ok=False)
    assert "supporting review" in missing_review.stderr

    inconclusive = _cli(repo, package, "evidence", "add", input_value=_review_record(revision, "TKT-01", conclusion="inconclusive"))
    assert inconclusive.returncode == 0, inconclusive.stderr
    failed_review = _satisfy(repo, package, "TKT-01", revision, ok=False)
    assert "supporting review" in failed_review.stderr
    added_review = _cli(repo, package, "evidence", "add", input_value=_review_record(revision, "TKT-01"))
    assert added_review.returncode == 0, added_review.stderr
    satisfied = _satisfy(repo, package, "TKT-01", revision)

    assert json.loads(satisfied.stdout)["state"] == "SATISFIED"
    assert not any(record["kind"] == "journey-step" for records in _state(package)["evidenceIndex"].values() for record in records)


def test_ticket_satisfy_keeps_implementation_and_acceptance_edges(tmp_path: Path) -> None:
    tickets = {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver", dependencies="- implementation: TKT-02\n- acceptance: TKT-02"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow"),
    }
    repo, package = _make_package(tmp_path, tickets=tickets)
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    for suite in ("S-resolver", "S-workflow"):
        added = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, suite))
        assert added.returncode == 0, added.stderr

    held = _satisfy(repo, package, "TKT-01", revision, ok=False)
    assert "dependencies are not released" in held.stderr
    _satisfy(repo, package, "TKT-02", revision)
    _satisfy(repo, package, "TKT-01", revision)


def test_evidence_freshness_rejects_external_diff_and_accepts_package_only_diff(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path / "external")
    for step in ("J1-S1", "J1-S2"):
        added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, step))
        assert added.returncode == 0, added.stderr
    added = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, "S-resolver"))
    assert added.returncode == 0, added.stderr

    source = repo / "src/app.py"
    source.parent.mkdir()
    source.write_text("value = 1\n", encoding="utf-8")
    external_head = _commit_path(repo, source, "external code change")
    refreshed = _cli(repo, package, "package", "refresh-progress")
    assert refreshed.returncode == 0, refreshed.stderr
    assert "J1 走通 0/2" in (package / "progress.md").read_text(encoding="utf-8")
    stale_gate = _gate(repo, package, "pass", external_head)
    assert stale_gate.returncode != 0
    assert "Evidence journey:run-1:J1-S1 的 supporting 记录待复验" in stale_gate.stderr
    assert "Evidence suite:S-resolver 的 supporting 记录待复验" in stale_gate.stderr
    stale = _satisfy(repo, package, "TKT-01", external_head, ok=False)
    assert "Suite S-resolver" in stale.stderr
    assert not situation.evidence_record_valid(
        _suite_record(revision, "S-resolver"), external_head, repo=repo, package=package,
        expected_environment="local-test", attempt_active=True,
    )

    repo2, package2, revision2 = _init_v36(tmp_path / "package-only")
    for step in ("J1-S1", "J1-S2"):
        added = _cli(repo2, package2, "evidence", "add", input_value=_journey_record(revision2, step))
        assert added.returncode == 0, added.stderr
    added = _cli(repo2, package2, "evidence", "add", input_value=_suite_record(revision2, "S-resolver"))
    assert added.returncode == 0, added.stderr
    note = package2 / "implementation-note.md"
    note.write_text("package-local document change\n", encoding="utf-8")
    package_head = _commit_path(repo2, note, "package documentation change")

    assert "J1 走通 2/2" in (package2 / "progress.md").read_text(encoding="utf-8")
    _satisfy(repo2, package2, "TKT-01", package_head)


def test_evidence_artifact_is_required_only_while_attempt_is_active(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    added = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, "S-resolver"))
    assert added.returncode == 0, added.stderr
    failed = _gate(repo, package, "fail", revision, reason="fixture terminal failure")
    assert failed.returncode == 0, failed.stderr

    (package / "artifacts/evidence.md").unlink()
    validated = _cli(repo, package, "package", "validate")
    assert validated.returncode == 0, validated.stderr


def test_amendment_add_confirm_cas_idempotence_and_unregistered_contract_finding(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    spec = package / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## Owner clarification\nThe accepted wording is unchanged.\n", encoding="utf-8")
    before = _cli(repo, package, "package", "validate")
    assert before.returncode == 0, before.stderr
    assert any(row["code"] == "contract-amendment-unregistered" and row["path"] == "spec.md" for row in json.loads(before.stdout)["findings"])

    args = ("package", "amendment", "add", "--id", "A-1", "--summary", "补充时间锚点", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    added = _cli(repo, package, *args)
    assert added.returncode == 0, added.stderr
    state = _state(package)
    assert state["acceptance"]["amendments"][0]["affectedBlobs"]["spec.md"] == _git(
        repo, "hash-object", "--", package.relative_to(repo).as_posix() + "/spec.md"
    )
    repeated = _cli(repo, package, *args)
    assert repeated.returncode == 0 and json.loads(repeated.stdout)["idempotent"] is True
    changed = _cli(repo, package, "package", "amendment", "add", "--id", "A-1", "--summary", "different", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    assert changed.returncode != 0 and "use a new id" in changed.stderr
    missing = _cli(repo, package, "package", "amendment", "confirm", "--id", "missing", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision)
    assert missing.returncode != 0 and "unknown amendment" in missing.stderr

    confirmed = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision)
    assert confirmed.returncode == 0, confirmed.stderr
    repeated_confirm = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision)
    assert repeated_confirm.returncode == 0 and json.loads(repeated_confirm.stdout)["idempotent"] is True
    different_confirm = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Another Owner", "--confirmed-revision", revision)
    assert different_confirm.returncode != 0 and "different confirmation" in different_confirm.stderr
    after = _cli(repo, package, "package", "validate")
    assert after.returncode == 0, after.stderr
    assert not any(row["code"] == "contract-amendment-unregistered" for row in json.loads(after.stdout)["findings"])


def test_amendment_without_registration_blob_does_not_cover_contract_change(tmp_path: Path) -> None:
    repo, package, _ = _init_v36(tmp_path)
    spec = package / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## Clarification\n", encoding="utf-8")
    added = _cli(
        repo,
        package,
        "package",
        "amendment",
        "add",
        "--id",
        "A-legacy",
        "--summary",
        "legacy amendment",
        "--affected",
        "spec.md",
        "--artifact",
        "artifacts/evidence.md",
    )
    assert added.returncode == 0, added.stderr
    state = _state(package)
    del state["acceptance"]["amendments"][0]["affectedBlobs"]
    (package / ".impl-package/state.json").write_text(json.dumps(state), encoding="utf-8")

    validated = _cli(repo, package, "package", "validate")

    assert validated.returncode == 0, validated.stderr
    assert any(
        row["code"] == "contract-amendment-unregistered" and row["path"] == "spec.md"
        for row in json.loads(validated.stdout)["findings"]
    )


def test_journey_phase1_fixture_runs_end_to_end_with_fresh_amendment_blobs(tmp_path: Path) -> None:
    repo, package = _make_fixture_package(tmp_path / "e2e")
    initialized = _init(repo, package)
    assert json.loads(initialized.stdout)["formatVersion"] == "3.6"
    state = _state(package)
    assert state["tickets"] == {"TKT-01": {"state": "PENDING"}, "TKT-02": {"state": "PENDING"}}
    assert state["evidenceIndex"] == {}

    revision = _git(repo, "rev-parse", "HEAD")
    setup_evidence = [
        {**_suite_record(revision, "S-resolver"), "artifact": "artifacts/evidence.md"},
        {**_suite_record(revision, "S-workflow"), "artifact": "artifacts/evidence.md"},
        {**_suite_record(revision, "S-safety"), "artifact": "artifacts/evidence.md"},
        {**_review_record(revision, "TKT-01"), "artifact": "artifacts/review-receipt.md"},
    ]
    added = _cli(repo, package, "evidence", "add", input_value=setup_evidence)
    assert added.returncode == 0, added.stderr

    first_step = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert first_step.returncode == 0, first_step.stderr
    assert "J1 走通 1/2" in (package / "progress.md").read_text(encoding="utf-8")
    second_step = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2"))
    assert second_step.returncode == 0, second_step.stderr
    assert "J1 走通 2/2" in (package / "progress.md").read_text(encoding="utf-8")
    for command in ("validate", "status"):
        result = _cli(repo, package, "package", command)
        assert result.returncode == 0, result.stderr

    blocked_by_edge = _satisfy(repo, package, "TKT-01", revision, environment=None, ok=False)
    assert "dependencies are not released" in blocked_by_edge.stderr
    _satisfy(repo, package, "TKT-02", revision, environment="local-test")
    assert _state(package)["tickets"]["TKT-02"]["acceptance"] == {"revision": revision, "environment": "local-test"}
    _satisfy(repo, package, "TKT-01", revision, environment=None)
    assert _state(package)["tickets"]["TKT-01"]["acceptance"] == {"revision": revision}
    assert not any(
        record["kind"] == "claim"
        for records in _state(package)["evidenceIndex"].values()
        for record in records
    )

    spec = package / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## Owner clarification\nFirst approved wording.\n", encoding="utf-8")
    amendment_args = (
        "package",
        "amendment",
        "add",
        "--summary",
        "clarify Journey wording",
        "--affected",
        "spec.md",
        "--artifact",
        "artifacts/amendment.md",
    )
    first_amendment = _cli(repo, package, *amendment_args, "--id", "A-1")
    assert first_amendment.returncode == 0, first_amendment.stderr
    pending_gate = _gate(repo, package, "pass", revision)
    assert pending_gate.returncode != 0 and "待 Owner 确认" in pending_gate.stderr
    blocked = _gate(repo, package, "blocked", revision, reason="A-1 needs Owner confirmation")
    assert blocked.returncode == 0, blocked.stderr
    assert not engine._lifecycle(package, "initial", repo).frozen

    confirm_a1 = _cli(
        repo,
        package,
        "package",
        "amendment",
        "confirm",
        "--id",
        "A-1",
        "--expect",
        "PENDING",
        "--confirmed-by",
        "Owner",
        "--confirmed-revision",
        revision,
    )
    assert confirm_a1.returncode == 0, confirm_a1.stderr
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## Owner clarification\nSecond approved wording.\n", encoding="utf-8")
    stale_amendment_confirm = _cli(
        repo,
        package,
        "package",
        "amendment",
        "confirm",
        "--id",
        "A-1",
        "--expect",
        "PENDING",
        "--confirmed-by",
        "Owner",
        "--confirmed-revision",
        revision,
    )
    assert stale_amendment_confirm.returncode != 0 and "no longer matches affected file contents" in stale_amendment_confirm.stderr
    stale_contract_gate = _gate(repo, package, "pass", revision)
    assert stale_contract_gate.returncode != 0 and "spec.md" in stale_contract_gate.stderr and "未登记 Amendment" in stale_contract_gate.stderr

    second_amendment = _cli(repo, package, *amendment_args, "--id", "A-2")
    assert second_amendment.returncode == 0, second_amendment.stderr
    confirm_a2 = _cli(
        repo,
        package,
        "package",
        "amendment",
        "confirm",
        "--id",
        "A-2",
        "--expect",
        "PENDING",
        "--confirmed-by",
        "Owner",
        "--confirmed-revision",
        revision,
    )
    assert confirm_a2.returncode == 0, confirm_a2.stderr

    release = _cli(
        repo,
        package,
        "evidence",
        "add",
        input_value={
            "kind": "release",
            "artifact": "artifacts/release-order.md",
            "revision": revision,
            "environment": "local-test",
            "conclusion": "supporting",
        },
    )
    assert release.returncode == 0, release.stderr
    _add_terminal_summary(repo, package, revision)
    passed = _gate(repo, package, "pass", revision, reason="all phase 1 checks satisfied")
    assert passed.returncode == 0, passed.stderr or passed.stdout
    gate_text = (package / "gate.md").read_text(encoding="utf-8")
    assert "- J1 纠正后下一张账单用新科目：走通 2/2" in gate_text
    assert "- 套件：3/3 通过" in gate_text
    assert "- 合同修订：无待确认或漏登" in gate_text
    assert "- 发布顺序：已记录" in gate_text
    assert engine._lifecycle(package, "initial", repo).frozen
    assert (package / ".impl-package/attempts/initial.json").is_file()

    outside_repo, outside_package = _make_fixture_package(tmp_path / "outside")
    _init(outside_repo, outside_package)
    outside_revision = _git(outside_repo, "rev-parse", "HEAD")
    outside_record = _journey_record(outside_revision, "J1-S1")
    outside_added = _cli(outside_repo, outside_package, "evidence", "add", input_value=outside_record)
    assert outside_added.returncode == 0, outside_added.stderr
    outside_source = outside_repo / "src/app.py"
    outside_source.parent.mkdir()
    outside_source.write_text("value = 1\n", encoding="utf-8")
    outside_head = _commit_path(outside_repo, outside_source, "outside package change")
    outside_gate = _gate(outside_repo, outside_package, "pass", outside_head)
    assert outside_gate.returncode != 0 and "Evidence journey:run-1:J1-S1 的 supporting 记录待复验" in outside_gate.stderr

    local_repo, local_package = _make_fixture_package(tmp_path / "package-doc")
    _init(local_repo, local_package)
    local_revision = _git(local_repo, "rev-parse", "HEAD")
    local_record = _suite_record(local_revision, "S-resolver")
    local_added = _cli(local_repo, local_package, "evidence", "add", input_value=local_record)
    assert local_added.returncode == 0, local_added.stderr
    package_note = local_package / "implementation-note.md"
    package_note.write_text("package-local documentation change\n", encoding="utf-8")
    local_head = _commit_path(local_repo, package_note, "package documentation change")
    assert engine._v36_record_valid(
        local_package,
        local_record,
        local_head,
        expected_environment="local-test",
        attempt_active=True,
    )

    unregistered_repo, unregistered_package = _make_fixture_package(tmp_path / "unregistered-spec")
    _init(unregistered_repo, unregistered_package)
    unregistered_revision = _git(unregistered_repo, "rev-parse", "HEAD")
    unregistered_spec = unregistered_package / "spec.md"
    unregistered_spec.write_text(unregistered_spec.read_text(encoding="utf-8") + "\n## Unregistered change\n", encoding="utf-8")
    unregistered_gate = _gate(unregistered_repo, unregistered_package, "pass", unregistered_revision)
    assert unregistered_gate.returncode != 0
    assert "spec.md" in unregistered_gate.stderr and "未登记 Amendment" in unregistered_gate.stderr


def test_gate_pass_rejects_each_acceptance_gap_and_gate_blocked_keeps_attempt_active(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    (package / "spec.md").write_text((package / "spec.md").read_text(encoding="utf-8") + "\n## Owner clarification\nAmended wording.\n", encoding="utf-8")
    unregistered = _gate(repo, package, "pass", revision)
    assert unregistered.returncode != 0 and "未登记 Amendment" in unregistered.stderr
    add_amendment = _cli(repo, package, "package", "amendment", "add", "--id", "A-1", "--summary", "补充规则", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    assert add_amendment.returncode == 0, add_amendment.stderr

    rejected = _gate(repo, package, "pass", revision)
    assert rejected.returncode != 0
    for gap in ("Journey J1", "Required Suite S-resolver", "Required Ticket TKT-01", "待 Owner 确认", "发布顺序", "terminal review coverage"):
        assert gap in rejected.stderr
    blocked = _gate(repo, package, "blocked", revision, reason="A-1 needs Owner confirmation")
    assert blocked.returncode == 0, blocked.stderr
    gate_text = (package / "gate.md").read_text(encoding="utf-8")
    assert "## Owner Summary" in gate_text
    assert "合同修订：1 条待 Owner 确认（A-1 补充规则）" in gate_text
    owner_summary = gate_text.split("## Owner Summary", 1)[1].split("## Evidence", 1)[0]
    assert not any(line.startswith(("- Verdict:", "- Attempt:", "- Comparison commit:")) for line in owner_summary.splitlines())
    assert engine._gate_info(package, repo) == {"verdict": "blocked", "attempt": "initial", "commit": revision}
    assert not engine._lifecycle(package, "initial", repo).frozen


def test_journey_gate_pass_confirms_amendment_requires_release_and_freezes_archive(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    (package / "spec.md").write_text((package / "spec.md").read_text(encoding="utf-8") + "\n## Owner clarification\nApproved wording.\n", encoding="utf-8")
    added = _cli(repo, package, "package", "amendment", "add", "--id", "A-1", "--summary", "回填时间锚点", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    assert added.returncode == 0, added.stderr
    assert _gate(repo, package, "pass", revision).returncode != 0
    _gate(repo, package, "blocked", revision, reason="A-1 pending").check_returncode()
    _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision).check_returncode()

    for suite in ("S-resolver", "S-workflow", "S-safety"):
        added_suite = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, suite))
        assert added_suite.returncode == 0, added_suite.stderr
    for step in ("J1-S1", "J1-S2"):
        added_step = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, step))
        assert added_step.returncode == 0, added_step.stderr
    _satisfy(repo, package, "TKT-01", revision)
    _satisfy(repo, package, "TKT-02", revision)
    release = _cli(repo, package, "evidence", "add", input_value={"kind": "release", "artifact": "artifacts/evidence.md", "revision": revision, "environment": "local-test", "conclusion": "supporting"})
    assert release.returncode == 0, release.stderr
    _add_terminal_summary(repo, package, revision)

    passed = _gate(repo, package, "pass", revision, reason="全部验收满足")
    assert passed.returncode == 0, passed.stderr or passed.stdout
    text = (package / "gate.md").read_text(encoding="utf-8")
    assert "- J1 纠正后下一张账单用新科目：走通 2/2" in text
    assert "- 套件：3/3 通过" in text
    assert "- 合同修订：无待确认或漏登" in text
    assert "- 发布顺序：已记录" in text
    assert f"- 最终版本：{revision[:7]}" in text
    assert "- 结论：pass — 全部验收满足" in text
    assert engine._gate_info(package, repo) == {"verdict": "pass", "attempt": "initial", "commit": revision}
    assert engine._lifecycle(package, "initial", repo).frozen
    assert (package / ".impl-package/attempts/initial.json").is_file()


def test_situation_renders_new_v36_acceptance_rows_without_changing_global_blocking(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    added = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, "S-resolver"))
    assert added.returncode == 0, added.stderr
    outside = repo / "src/change.py"
    outside.parent.mkdir()
    outside.write_text("changed = True\n", encoding="utf-8")
    _commit_path(repo, outside, "change outside package")
    spec = package / "spec.md"
    spec.write_text(spec.read_text(encoding="utf-8") + "\n## Owner clarification\nChanged.\n", encoding="utf-8")

    result = subprocess.run(
        [sys.executable, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts/situation.py"), "render", "--package", str(package), "--json"],
        cwd=repo,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr
    rendered = json.loads(result.stdout)
    slugs = {row["slug"] for row in rendered["matches"]}
    assert {
        "attempt.accept.journey-incomplete",
        "attempt.accept.required-suite-missing",
        "attempt.accept.evidence-revalidation-pending",
        "attempt.accept.amendment-owner-confirmation",
        "attempt.accept.release-order-missing",
    } <= slugs
    assert "attempt.accept.amendment-owner-confirmation" not in situation.GLOBAL_BLOCKING_SLUGS
