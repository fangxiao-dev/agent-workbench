from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
FIXTURE = ROOT / "tests/fixtures/impl-package-journey"
PACKAGE = "docs/implementations/20261031-frozen-contract"
PACKAGE_PATH = ROOT / PACKAGE
PYTHON_CACHE = Path(tempfile.gettempdir()) / f"impl-package-frozen-contract-{os.getpid()}"
SCRIPT_DIR = ROOT / "plugin-marketplace/plugins/impl-package/scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from impl_package_runtime import engine  # noqa: E402


PLAN = """# Plan

Attempt ID: initial
Predecessors: None
Composition: tickets=true, dag=false
Acceptance: journey
Harness setup: python harness.py setup
Harness precheck: python harness.py precheck
Harness cleanup: python harness.py cleanup
Harness isolation: per-run
First visible step: J18-S1 @ TKT-18
"""


SPEC_TEMPLATE = """# Spec

## 1. 核心目标

验证冻结 Attempt 使用其 Gate comparison 合同。

## 2. 业务规则

历史合同与当前合同可以独立演进。

## 3. 实施边界

运行时不改写历史 Gate。

## 7. 验收

### Journeys

#### {journey} 冻结合同路径

准备：准备历史验收资料。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| {step} | 验收者 | 文件 | — | 打开冻结验收文件 | 文件内容 | 历史合同成立 | — |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §2 | S-contract | 历史合同成立 |

- 无需验收的章节： §1, §3

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-contract | rule | ticket | python -m pytest contract | local-test |
"""


def _spec(journey: str, step: str) -> str:
    return SPEC_TEMPLATE.format(journey=journey, step=step)


def _ticket(ticket: str, attempt: str, step: str) -> str:
    return f"""# {ticket}

Ticket ID: {ticket}
Publication Status: Draft
Attempt ID: {attempt}

## Coverage

- Journey steps: {step}
- Suites: S-contract
- Required review: none

## Blocking Dependencies

- none
"""


def _git(repo: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def _cli(
    repo: Path,
    *args: str,
    input_value: object | None = None,
) -> subprocess.CompletedProcess[str]:
    PYTHON_CACHE.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["IMPL_PACKAGE_NO_SITUATION"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(PYTHON_CACHE)
    return subprocess.run(
        [sys.executable, str(CLI), "--package", str(_package(repo)), *args],
        cwd=repo,
        input=None if input_value is None else json.dumps(input_value, ensure_ascii=False),
        text=True,
        capture_output=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


def _package(repo: Path) -> Path:
    return repo / PACKAGE


def _state(repo: Path) -> dict:
    return json.loads((_package(repo) / ".impl-package/state.json").read_text(encoding="utf-8"))


def _write_state(repo: Path, state: dict) -> None:
    (_package(repo) / ".impl-package/state.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _init(repo: Path) -> subprocess.CompletedProcess[str]:
    result = _cli(repo, "package", "init", "--attempt", "initial", "--plan", f"{PACKAGE}/plan.md")
    assert result.returncode == 0, result.stderr or result.stdout
    return result


def _make_repo(root: Path) -> Path:
    repo = root / "repo"
    repo.mkdir()
    _git(repo, "init")
    _git(repo, "config", "user.email", "frozen@example.com")
    _git(repo, "config", "user.name", "Frozen Contract Fixture")

    package = _package(repo)
    package.parent.mkdir(parents=True)
    shutil.copytree(FIXTURE, package)
    (package / "plan.md").write_text(PLAN, encoding="utf-8")
    (package / "spec.md").write_text(_spec("J18", "J18-S1"), encoding="utf-8")
    for path in (package / "tickets").glob("*.md"):
        path.unlink()
    (package / "tickets/18.md").write_text(
        _ticket("TKT-18", "initial", "J18-S1"),
        encoding="utf-8",
    )
    (package / "artifacts/frozen.bin").write_bytes(b"frozen contract evidence\n")
    (repo / "docs/implementations/retired.json").write_text('{"packages": []}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "J18 fixture")
    return repo


def _prepare_pass_evidence(
    repo: Path,
    revision: str,
    *,
    journeys: list[tuple[str, str]] | None = None,
    ticket: str = "TKT-18",
) -> None:
    artifact = "artifacts/frozen.bin"
    journeys = journeys or [("J18", "J18-S1")]
    journey_records = [
        {
            "kind": "journey-step",
            "runId": f"frozen-run-{journey}",
            "journeyId": journey,
            "stepId": step,
            "actor": "验收者",
            "entry": "打开冻结验收文件",
            "surface": "file",
            "artifact": artifact,
            "revision": revision,
            "environment": "local-test",
            "conclusion": "supporting",
        }
        for journey, step in journeys
    ]
    evidence = [
        {
            "kind": "run-setup",
            "runId": f"frozen-run-{journey}",
            "artifact": artifact,
            "revision": revision,
            "environment": "local-test",
            "conclusion": "supporting",
        }
        for journey, _step in journeys
    ] + [
        *journey_records,
        {
            "kind": "suite",
            "suiteId": "S-contract",
            "artifact": artifact,
            "revision": revision,
            "environment": "local-test",
            "conclusion": "supporting",
        },
    ]
    added = _cli(repo, "evidence", "add", input_value=evidence)
    assert added.returncode == 0, added.stderr or added.stdout
    satisfied = _cli(
        repo,
        "ticket",
        "satisfy",
        ticket,
        "--expect",
        "PENDING",
        "--revision",
        revision,
    )
    assert satisfied.returncode == 0, satisfied.stderr or satisfied.stdout

    results = []
    for track, suffix in (("Track A", "a"), ("Track C", "c")):
        path = f"artifacts/terminal-{suffix}.md"
        (_package(repo) / path).write_text(
            f"verdict: PASS\nreviewed-head: {revision}\nreview-run: terminal-1\nreview-track: {track}\n",
            encoding="utf-8",
        )
        results.append({"track": track, "verdict": "PASS", "reviewedHead": revision, "artifact": path})
    terminal = _cli(
        repo,
        "trail",
        "append",
        input_value={
            "kind": "fact",
            "subject": "attempt",
            "key": "review.terminal_summary",
            "value": {
                "reviewRunId": "terminal-1",
                "comparisonHead": revision,
                "safetyApplicable": False,
                "results": results,
            },
        },
    )
    assert terminal.returncode == 0, terminal.stderr or terminal.stdout


def _freeze_pass(repo: Path) -> str:
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    _prepare_pass_evidence(repo, revision)
    passed = _cli(
        repo,
        "gate",
        "pass",
        "--comparison-commit",
        revision,
        "--reason",
        "frozen contract fixture",
        "--no-durable-delta-reason",
        "fixture",
    )
    assert passed.returncode == 0, passed.stderr or passed.stdout
    return revision


def _runtime_snapshot(repo: Path) -> tuple[bytes | None, bytes | None, bytes, bytes | None]:
    package = _package(repo)
    gate = package / "gate.md"
    record = package / "execution/initial/execution-record.md"
    state = package / ".impl-package/state.json"
    archive = package / ".impl-package/attempts/initial.json"
    return (
        gate.read_bytes() if gate.is_file() else None,
        record.read_bytes() if record.is_file() else None,
        state.read_bytes(),
        archive.read_bytes() if archive.is_file() else None,
    )


def _seed_archive(repo: Path) -> None:
    archive = _package(repo) / ".impl-package/attempts/initial.json"
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_bytes(b'{"sentinel": "unchanged"}\n')


def _use_workspace_j20(repo: Path, *, add_to_j18: bool = False) -> None:
    package = _package(repo)
    old_spec = _spec("J18", "J18-S1")
    if add_to_j18:
        j20 = """#### J20 工作区新增路径

准备：准备新增验收资料。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J20-S1 | 验收者 | 文件 | — | 打开冻结验收文件 | 文件内容 | 工作区合同成立 | — |

"""
        (package / "spec.md").write_text(
            old_spec.replace("### Rule Matrix", j20 + "### Rule Matrix"),
            encoding="utf-8",
        )
        coverage = "J18-S1, J20-S1"
    else:
        (package / "spec.md").write_text(_spec("J20", "J20-S1"), encoding="utf-8")
        (package / "plan.md").write_text(
            PLAN.replace("J18-S1 @ TKT-18", "J20-S1 @ TKT-18"),
            encoding="utf-8",
        )
        coverage = "J20-S1"
    (package / "tickets/18.md").write_text(
        _ticket("TKT-18", "initial", coverage),
        encoding="utf-8",
    )


def _prepare_j20(repo: Path, *, new_step: str = "J20-S1") -> None:
    package = _package(repo)
    (package / "spec.md").write_text(_spec("J20", "J20-S1"), encoding="utf-8")
    (package / "plan-j20.md").write_text(
        PLAN.replace("Attempt ID: initial", "Attempt ID: j20")
        .replace("J18-S1 @ TKT-18", "J20-S1 @ TKT-20"),
        encoding="utf-8",
    )
    (package / "tickets/20.md").write_text(
        _ticket("TKT-20", "j20", new_step),
        encoding="utf-8",
    )


def _confirm_workspace_amendment(repo: Path, revision: str) -> None:
    added = _cli(
        repo,
        "package",
        "amendment",
        "add",
        "--id",
        "A-j20",
        "--summary",
        "uncommitted J20 contract",
        "--affected",
        "spec.md",
        "--artifact",
        "artifacts/frozen.bin",
    )
    assert added.returncode == 0, added.stderr or added.stdout
    confirmed = _cli(
        repo,
        "package",
        "amendment",
        "confirm",
        "--id",
        "A-j20",
        "--expect",
        "PENDING",
        "--confirmed-by",
        "Owner",
        "--confirmed-revision",
        revision,
    )
    assert confirmed.returncode == 0, confirmed.stderr or confirmed.stdout


def _init_j20(repo: Path) -> subprocess.CompletedProcess[str]:
    return _cli(
        repo,
        "package",
        "init",
        "--attempt",
        "j20",
        "--plan",
        f"{PACKAGE}/plan-j20.md",
    )


def test_frozen_attempt_uses_gate_contract_for_next_attempt(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    old_head = _freeze_pass(repo)
    old_gate = (_package(repo) / "gate.md").read_bytes()
    old_state = _state(repo)
    assert old_state["evidenceIndex"]
    assert old_state["tickets"]["TKT-18"]["state"] == "SATISFIED"

    _prepare_j20(repo)
    result = _init_j20(repo)

    assert result.returncode == 0, result.stderr or result.stdout
    new_state = _state(repo)
    archived = json.loads(
        (_package(repo) / ".impl-package/attempts/initial.json").read_text(encoding="utf-8")
    )
    assert archived["tickets"] == old_state["tickets"]
    assert new_state["tickets"] == {"TKT-20": {"state": "PENDING"}}
    assert new_state["attemptHistory"][0] == old_state["attemptHistory"][0]
    assert old_state["attemptHistory"][0]["gate"]["commit"] == old_head
    assert (_package(repo) / "gate.md").read_bytes() == old_gate


def test_frozen_validation_is_independent_of_later_workspace_spec(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _freeze_pass(repo)
    (_package(repo) / "spec.md").write_text(_spec("J20", "J20-S1"), encoding="utf-8")

    result = _cli(repo, "package", "validate")

    assert result.returncode == 0, result.stderr or result.stdout


def test_active_attempt_still_rejects_unknown_workspace_coverage(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _init(repo)
    (_package(repo) / "spec.md").write_text(_spec("J20", "J20-S1"), encoding="utf-8")

    result = _cli(repo, "package", "validate")

    assert result.returncode != 0
    assert "TKT-18 Coverage references unknown Journey step: J18-S1" in result.stderr


def test_frozen_contract_blob_mismatch_fails_closed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _freeze_pass(repo)
    (_package(repo) / "spec.md").write_text(_spec("J20", "J20-S1"), encoding="utf-8")
    state = _state(repo)
    state["acceptance"]["contractBaseline"]["files"]["spec.md"] = "0" * 40
    _write_state(repo, state)

    result = _cli(repo, "package", "validate")

    assert result.returncode != 0
    assert "frozen contract" in result.stderr
    assert "spec.md" in result.stderr


def test_missing_frozen_contract_revision_content_fails_closed(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _freeze_pass(repo)
    spec_path = _package(repo) / "spec.md"
    spec_path.unlink()
    _git(repo, "add", "--", spec_path.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "remove contract")
    empty_commit = _git(repo, "rev-parse", "HEAD")
    spec_path.write_text(_spec("J20", "J20-S1"), encoding="utf-8")

    gate_path = _package(repo) / "gate.md"
    gate_text = gate_path.read_text(encoding="utf-8")
    gate_path.write_text(
        gate_text.replace(
            next(line for line in gate_text.splitlines() if line.startswith("- Comparison commit:")),
            f"- Comparison commit: {empty_commit}",
        ),
        encoding="utf-8",
    )
    state = _state(repo)
    state["attemptHistory"][0]["gate"]["commit"] = empty_commit
    _write_state(repo, state)

    result = _cli(repo, "package", "validate")

    assert result.returncode != 0
    assert "frozen contract" in result.stderr
    assert empty_commit[:7] in result.stderr


def test_bad_new_attempt_is_rejected_without_changing_frozen_runtime(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _freeze_pass(repo)
    state_before = (_package(repo) / ".impl-package/state.json").read_bytes()
    gate_before = (_package(repo) / "gate.md").read_bytes()
    _prepare_j20(repo, new_step="J20-S99")

    result = _init_j20(repo)

    assert result.returncode != 0
    assert "TKT-20 Coverage references unknown Journey step: J20-S99" in result.stderr
    assert "J18-S1" not in result.stderr
    assert (_package(repo) / ".impl-package/state.json").read_bytes() == state_before
    assert (_package(repo) / "gate.md").read_bytes() == gate_before
    assert _cli(repo, "package", "validate").returncode == 0


def test_current_suite_support_replaces_stale_suite_key(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    state = _state(repo)
    summary = engine._validate_state(_package(repo), state, projections=False)
    valid = {
        "kind": "suite",
        "suiteId": "S-contract",
        "artifact": "artifacts/frozen.bin",
        "revision": revision,
        "environment": "local-test",
        "conclusion": "supporting",
    }
    state["evidenceIndex"]["suite:S-contract"] = [
        {**valid, "artifact": "artifacts/missing.bin"},
        valid,
    ]

    status = engine._v36_acceptance_status(
        _package(repo), state, summary, revision, attempt_active=True,
    )

    assert "suite:S-contract" not in status["staleEvidence"]
    assert status["suites"][0]["valid"] is True


def test_complete_new_journey_run_replaces_stale_old_run(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    state = _state(repo)
    summary = engine._validate_state(_package(repo), state, projections=False)
    setup = {
        "kind": "run-setup",
        "artifact": "artifacts/frozen.bin",
        "revision": revision,
        "environment": "local-test",
        "conclusion": "supporting",
    }
    step = {
        "kind": "journey-step",
        "journeyId": "J18",
        "stepId": "J18-S1",
        "actor": "验收者",
        "entry": "打开冻结验收文件",
        "surface": "file",
        "artifact": "artifacts/frozen.bin",
        "revision": revision,
        "environment": "local-test",
        "conclusion": "supporting",
    }
    state["evidenceIndex"] = {
        "run-setup:old": [{**setup, "runId": "old", "artifact": "artifacts/missing.bin"}],
        "journey:old:J18-S1": [{**step, "runId": "old", "artifact": "artifacts/missing.bin"}],
        "run-setup:new": [{**setup, "runId": "new"}],
        "journey:new:J18-S1": [{**step, "runId": "new"}],
    }

    status = engine._v36_acceptance_status(
        _package(repo), state, summary, revision, attempt_active=True,
    )

    assert status["staleEvidence"] == []
    assert status["journeys"][0]["reach"] == 1


def test_stale_evidence_without_valid_replacement_remains_blocking(tmp_path: Path) -> None:
    repo = _make_repo(tmp_path)
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    state = _state(repo)
    summary = engine._validate_state(_package(repo), state, projections=False)
    stale = {
        "kind": "suite",
        "suiteId": "S-contract",
        "artifact": "artifacts/missing.bin",
        "revision": revision,
        "environment": "local-test",
        "conclusion": "supporting",
    }
    invalidated = {
        **stale,
        "artifact": "artifacts/frozen.bin",
        "invalidatedBy": "superseded",
    }
    state["evidenceIndex"]["suite:S-contract"] = [stale, invalidated]

    status = engine._v36_acceptance_status(
        _package(repo), state, summary, revision, attempt_active=True,
    )

    assert status["staleEvidence"] == ["suite:S-contract"]
    assert status["suites"][0]["valid"] is False


@pytest.mark.parametrize("verdict", sorted(engine.TERMINAL_VERDICTS))
def test_uncommitted_contract_with_current_ticket_mismatch_is_atomic(
    tmp_path: Path, verdict: str,
) -> None:
    repo = _make_repo(tmp_path)
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    _use_workspace_j20(repo, add_to_j18=True)
    _init(repo)
    _prepare_pass_evidence(
        repo,
        revision,
        journeys=[("J18", "J18-S1"), ("J20", "J20-S1")],
    )
    _confirm_workspace_amendment(repo, revision)
    _seed_archive(repo)
    before = _runtime_snapshot(repo)

    result = _cli(
        repo,
        "gate",
        verdict,
        "--comparison-commit",
        revision,
        "--reason",
        "uncommitted contract",
        "--no-durable-delta-reason",
        "fixture",
    )

    assert result.returncode != 0
    assert "TKT-18 Coverage references unknown Journey step: J20-S1" in result.stderr
    assert _runtime_snapshot(repo) == before


@pytest.mark.parametrize("verdict", sorted(engine.TERMINAL_VERDICTS))
def test_missing_historical_spec_terminal_gate_is_atomic(
    tmp_path: Path, verdict: str,
) -> None:
    repo = _make_repo(tmp_path)
    spec_path = _package(repo) / "spec.md"
    spec_path.unlink()
    _git(repo, "add", "--", spec_path.relative_to(repo).as_posix())
    _git(repo, "commit", "-m", "remove historical contract")
    spec_path.write_text(_spec("J18", "J18-S1"), encoding="utf-8")
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    _prepare_pass_evidence(repo, revision)
    _seed_archive(repo)
    before = _runtime_snapshot(repo)

    result = _cli(
        repo,
        "gate",
        verdict,
        "--comparison-commit",
        revision,
        "--reason",
        "missing historical contract",
        "--no-durable-delta-reason",
        "fixture",
    )

    assert result.returncode != 0
    assert "frozen contract" in result.stderr
    assert _runtime_snapshot(repo) == before


@pytest.mark.parametrize("verdict", sorted(engine.TERMINAL_VERDICTS))
def test_mismatched_historical_spec_blob_terminal_gate_is_atomic(
    tmp_path: Path, verdict: str,
) -> None:
    repo = _make_repo(tmp_path)
    _use_workspace_j20(repo)
    _init(repo)
    revision = _git(repo, "rev-parse", "HEAD")
    _prepare_pass_evidence(repo, revision, journeys=[("J20", "J20-S1")])
    _seed_archive(repo)
    before = _runtime_snapshot(repo)

    result = _cli(
        repo,
        "gate",
        verdict,
        "--comparison-commit",
        revision,
        "--reason",
        "mismatched historical contract",
        "--no-durable-delta-reason",
        "fixture",
    )

    assert result.returncode != 0
    assert "frozen contract spec.md blob" in result.stderr
    assert _runtime_snapshot(repo) == before
