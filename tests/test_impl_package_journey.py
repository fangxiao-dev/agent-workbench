from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import engine  # noqa: E402
import situation  # noqa: E402
import review_track_stats  # noqa: E402


PLAN = """# Plan

Attempt ID: initial
Predecessors: None
Composition: tickets=true, dag=false
Acceptance: journey
Harness setup: python harness.py setup
Harness precheck: python harness.py precheck
Harness cleanup: python harness.py cleanup
Harness isolation: per-run
First visible step: J1-S1 @ TKT-01
"""

JOURNEY_FIXTURE = ROOT / "tests/fixtures/impl-package-journey"

SPEC = """# Spec

## 1. 核心目标

在账单更正后将稳定的判定结果用于下一张同类账单。

## 2. 业务规则

更正确认后，后续同类账单应读取门店记忆。

### 2.1 账单标识

后续账单通过账单 ID 关联到记忆。

## 3. 实施边界

该 Spec 不规定界面布局。

## 7. 验收

### Journeys

#### J1 纠正后下一张账单用新科目

准备：同一门店、三张同条件票据。

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” | Review 页记录 | 答案为 4982 | — |
| J1-S2 | 企业端用户 | 页面 | 科目 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” | 账单 ID |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §2 | S-resolver | 解析表每行来源与状态正确 |

- 无需验收的章节： §1, §3

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
    _write_trace(package)
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
    _write_trace(package)
    (repo / "docs/implementations/retired.json").write_text('{"packages": []}\n', encoding="utf-8")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "Journey fixture")
    return repo, package


def _cli(
    repo: Path, package: Path, *args: str, input_value: object | None = None, auto_setup: bool = True,
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["IMPL_PACKAGE_NO_SITUATION"] = "1"
    if auto_setup and args[:2] == ("evidence", "add") and input_value is not None:
        items = input_value if isinstance(input_value, list) else [input_value]
        if all(isinstance(item, dict) for item in items):
            state_path = package / ".impl-package/state.json"
            state = json.loads(state_path.read_text(encoding="utf-8")) if state_path.is_file() else {}
            existing_setup_ids = {
                record.get("runId")
                for key, records in state.get("evidenceIndex", {}).items()
                if key.startswith("run-setup:") and isinstance(records, list)
                for record in records if isinstance(record, dict) and record.get("kind") == "run-setup"
            }
            explicit_setup_ids = {item.get("runId") for item in items if item.get("kind") == "run-setup"}
            adjusted = []
            inserted: set[str] = set()
            for item in items:
                run_id = item.get("runId") if item.get("kind") == "journey-step" else None
                if (
                    isinstance(run_id, str) and run_id.strip()
                    and run_id not in existing_setup_ids
                    and run_id not in explicit_setup_ids
                    and run_id not in inserted
                    and all(isinstance(item.get(field), str) and item[field].strip() for field in ("revision", "environment"))
                ):
                    adjusted.append(_run_setup_record(item["revision"], run_id, item["environment"]))
                    inserted.add(run_id)
                adjusted.append(item)
            if len(adjusted) != len(items):
                input_value = adjusted
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


def _write_trace(package: Path, events: list[dict] | None = None, artifact: str = "artifacts/page-trace.zip") -> Path:
    path = package / artifact
    path.parent.mkdir(parents=True, exist_ok=True)
    events = events or [
        {"type": "before", "apiName": "locator.click", "method": "click", "params": {"selector": "getByRole('button', { name: '完成' })"}},
        {"type": "before", "apiName": "locator.click", "method": "click", "params": {"selector": "getByRole('textbox', { name: '科目' })"}},
    ]
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("trace.trace", "\n".join(json.dumps(event, ensure_ascii=False) for event in events) + "\n")
    return path


def _journey_record(
    revision: str,
    step_id: str,
    *,
    run_id: str = "run-1",
    environment: str = "local-test",
    surface: str = "page",
    artifact: str | None = None,
    manual_by: str | None = None,
    actor: str | None = None,
    entry: str | None = None,
) -> dict:
    step = engine._journey_spec_text(SPEC)["steps"][step_id]
    record = {
        "kind": "journey-step",
        "runId": run_id,
        "journeyId": "J1",
        "stepId": step_id,
        "actor": actor or step["role"],
        "entry": entry or step["operationEntry"],
        "surface": surface,
        "artifact": artifact or ("artifacts/page-trace.zip" if surface == "page" else "artifacts/evidence.md"),
        "revision": revision,
        "environment": environment,
        "conclusion": "supporting",
    }
    if manual_by is not None:
        record["manualBy"] = manual_by
    if step_id == "J1-S1":
        record["outputRef"] = "bill-123" if run_id == "run-1" else f"bill-{run_id}"
    elif step_id == "J1-S2":
        record["inputRef"] = "bill-123" if run_id == "run-1" else f"bill-{run_id}"
    return record


def _run_setup_record(revision: str, run_id: str = "run-1", environment: str = "local-test") -> dict:
    return {
        "kind": "run-setup",
        "runId": run_id,
        "artifact": "artifacts/evidence.md",
        "revision": revision,
        "environment": environment,
        "conclusion": "supporting",
    }


def _file_step_spec() -> str:
    return SPEC.replace(
        "| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” | Review 页记录 | 答案为 4982 | — |",
        "| J1-S1 | 税务师 | 文件 | — | 下载更正后的账单 | 更正账单下载文件 | 答案为 4982 | — |",
    )


def _log_step_spec(*, first_step: bool = False, all_steps: bool = False) -> str:
    first = "| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” | Review 页记录 | 答案为 4982 | — |"
    second = "| J1-S2 | 企业端用户 | 页面 | 科目 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” | 账单 ID |"
    first_record = "| J1-S1 | 验收执行者 | 记录 | — | 核对 AI 调用记录 | AI 运行记录 | 确实调用平台经验工具 | — |"
    second_record = "| J1-S2 | 验收执行者 | 记录 | — | 核对 AI 调用记录 | AI 运行记录 | 确实调用平台经验工具 | 账单 ID |"
    result = SPEC.replace(first, first_record) if first_step or all_steps else SPEC
    return result.replace(second, second_record) if not first_step or all_steps else result


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


def _append_spec_note(package: Path, note: str) -> None:
    spec = package / "spec.md"
    text = spec.read_text(encoding="utf-8")
    anchor = "该 Spec 不规定界面布局。"
    assert anchor in text
    spec.write_text(text.replace(anchor, f"{anchor}\n\n{note}", 1), encoding="utf-8")


def test_init_validate_and_status_use_v36_and_record_contract_baseline(tmp_path: Path) -> None:
    repo, package, _ = _init_v36(tmp_path)
    state = _state(package)

    assert state["acceptance"]["releaseOrder"] == "none"
    assert state["acceptance"]["amendments"] == []
    assert state["acceptance"]["harness"] == {
        "setup": "python harness.py setup",
        "precheck": "python harness.py precheck",
        "cleanup": "python harness.py cleanup",
        "isolation": "per-run",
        "firstVisibleStep": {"step": "J1-S1", "ticket": "TKT-01"},
    }
    assert set(state["acceptance"]["contractBaseline"]["files"]) == {"decision.md", "spec.md"}
    assert state["acceptance"]["contractBaseline"]["head"] == _git(repo, "rev-parse", "HEAD")
    assert state["tickets"] == {"TKT-01": {"state": "PENDING"}, "TKT-02": {"state": "PENDING"}}
    for command in ("validate", "status"):
        result = _cli(repo, package, "package", command)
        assert result.returncode == 0, result.stderr
        assert json.loads(result.stdout)["formatVersion"] == "3.6"


def test_check_spec_resolves_rule_and_no_acceptance_chapters_by_number_or_title(tmp_path: Path) -> None:
    spec = SPEC.replace("R1 | §2 |", "R1 | 业务规则 |")
    spec = spec.replace("- 无需验收的章节： §1, §3", "- 无需验收的章节： 核心目标, 实施边界")
    repo, package = _make_package(tmp_path, spec=spec)

    result = _cli(
        repo,
        package,
        "package",
        "check-spec",
        "--spec",
        package.joinpath("spec.md").relative_to(repo).as_posix(),
    )

    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["valid"] is True
    assert not (package / ".impl-package/state.json").exists()


def test_check_spec_accepts_none_when_rules_cover_every_chapter(tmp_path: Path) -> None:
    spec = SPEC.replace("R1 | §2 |", "R1 | §1, §2, §3 |")
    spec = spec.replace("- 无需验收的章节： §1, §3", "- 无需验收的章节： none")
    repo, package = _make_package(tmp_path, spec=spec)

    result = _cli(repo, package, "package", "check-spec", "--spec", package.joinpath("spec.md").relative_to(repo).as_posix())

    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    ("spec", "reference"),
    [
        (SPEC.replace("R1 | §2 |", "R1 | §99 |"), "§99"),
        (SPEC.replace("- 无需验收的章节： §1, §3", "- 无需验收的章节： 不存在章节"), "不存在章节"),
    ],
)
def test_check_spec_reports_unresolved_source_and_exemption_references(tmp_path: Path, spec: str, reference: str) -> None:
    repo, package = _make_package(tmp_path, spec=spec)

    result = _cli(repo, package, "package", "check-spec", "--spec", package.joinpath("spec.md").relative_to(repo).as_posix())

    assert result.returncode != 0
    assert reference in result.stderr
    assert "spec.md §7 Rule Matrix" in result.stderr


@pytest.mark.parametrize("command", ["check-spec", "init", "validate"])
def test_unclassified_spec_chapter_fails_check_spec_init_and_validate(tmp_path: Path, command: str) -> None:
    invalid_spec = SPEC.replace("## 7. 验收", "## 4. 新增业务约束\n\n需要给出独立验收。\n\n## 7. 验收")
    repo, package = _make_package(tmp_path)
    if command == "validate":
        _init(repo, package)
    (package / "spec.md").write_text(invalid_spec, encoding="utf-8")

    if command == "check-spec":
        result = _cli(repo, package, "package", "check-spec", "--spec", package.joinpath("spec.md").relative_to(repo).as_posix())
    elif command == "init":
        result = _init(repo, package, ok=False)
    else:
        result = _cli(repo, package, "package", "validate")

    assert result.returncode != 0
    assert "§4" in result.stderr
    assert "新增业务约束" in result.stderr
    assert "增加引用该章节的规则行" in result.stderr
    assert "无需验收的章节" in result.stderr
    if command == "check-spec":
        assert not (package / ".impl-package/state.json").exists()
    if command == "init":
        assert not (package / ".impl-package/state.json").exists()


@pytest.mark.parametrize("command", ["check-spec", "init", "validate"])
@pytest.mark.parametrize(
    "old_table",
    [
        "| Step | 操作入口 | 观察表面 | 预期 | 承接 |\n| --- | --- | --- | --- | --- |\n| J1-S1 | 税务端 Review 页确认账单 | 门店答案读取 API | 答案为 4982 | — |\n| J1-S2 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签‘本门店记忆’ | 账单 ID |",
        "| Step | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |\n| --- | --- | --- | --- | --- | --- | --- |\n| J1-S1 | 页面 | 完成 | 税务端 Review 页确认账单 | 门店答案读取 API | 答案为 4982 | — |\n| J1-S2 | 页面 | 科目 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签‘本门店记忆’ | 账单 ID |",
    ],
)
def test_old_journey_tables_are_rejected_by_check_spec_init_and_validate(tmp_path: Path, command: str, old_table: str) -> None:
    current_table = "| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |\n| --- | --- | --- | --- | --- | --- | --- | --- |\n| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” | Review 页记录 | 答案为 4982 | — |\n| J1-S2 | 企业端用户 | 页面 | 科目 | 企业端打开下一张同类账单 | 工作台科目控件 | 预填 4982，标签“本门店记忆” | 账单 ID |"
    old_spec = SPEC.replace(current_table, old_table)
    repo, package = _make_package(tmp_path, spec=SPEC)
    if command == "validate":
        _init(repo, package)
    (package / "spec.md").write_text(old_spec, encoding="utf-8")

    if command == "check-spec":
        result = _cli(repo, package, "package", "check-spec", "--spec", package.joinpath("spec.md").relative_to(repo).as_posix())
    elif command == "init":
        result = _init(repo, package, ok=False)
    else:
        result = _cli(repo, package, "package", "validate")

    assert result.returncode != 0
    assert "must use the 3.6 header" in result.stderr
    assert "Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接" in result.stderr


@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (SPEC.replace("| J1-S1 | 税务师 | 页面 | 完成 |", "| J1-S1 | 税务师 | API | 完成 |"), "入口类型必须是 页面、文件 或 记录"),
        (SPEC.replace("| J1-S1 | 税务师 | 页面 | 完成 |", "| J1-S1 | 税务师 | 页面 | — |"), "页面步必须填写控件可见名称"),
        (SPEC.replace("| J1-S1 | 税务师 | 页面 | 完成 |", "| J1-S1 | 税务师 | 文件 | 完成 |"), "文件或记录步的控件必须为 —"),
    ],
)
def test_spec_validates_entry_type_and_control(spec: str, message: str) -> None:
    with pytest.raises(engine.StateError, match=message):
        engine._journey_spec_text(spec)


@pytest.mark.parametrize("command", ["check-spec", "init", "validate"])
@pytest.mark.parametrize(
    ("spec", "message"),
    [
        (_log_step_spec(first_step=True), "第 1 步 J1-S1 不能是记录"),
        (_log_step_spec(all_steps=True), "cannot consist only of 记录 steps"),
    ],
)
def test_record_steps_cannot_start_or_make_up_a_whole_journey(
    tmp_path: Path, command: str, spec: str, message: str,
) -> None:
    repo, package = _make_package(tmp_path, spec=SPEC)
    if command == "validate":
        _init(repo, package)
    (package / "spec.md").write_text(spec, encoding="utf-8")

    if command == "check-spec":
        result = _cli(repo, package, "package", "check-spec", "--spec", package.joinpath("spec.md").relative_to(repo).as_posix())
    elif command == "init":
        result = _init(repo, package, ok=False)
    else:
        result = _cli(repo, package, "package", "validate")

    assert result.returncode != 0
    assert message in result.stderr
    if command == "init":
        assert not (package / ".impl-package/state.json").exists()


def test_situation_render_reports_unclassified_spec_chapter(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, package, _ = _init_v36(tmp_path)
    invalid_spec = SPEC.replace("## 7. 验收", "## 4. 新增业务约束\n\n需要给出独立验收。\n\n## 7. 验收")
    (package / "spec.md").write_text(invalid_spec, encoding="utf-8")

    code = situation.main(["render", "--package", str(package), "--json"])
    rendered = json.loads(capsys.readouterr().out)

    assert code == 0
    assert rendered["selected"]["slug"] == "package.record.state-missing"
    assert any("§4" in warning for warning in rendered["warnings"])


def test_journey_handoff_column_parses_and_first_step_must_not_handoff(tmp_path: Path) -> None:
    journey = engine._journey_spec_text(SPEC)["journeys"][0]
    assert journey["preparation"] == "同一门店、三张同条件票据。"
    assert [step["role"] for step in journey["steps"]] == ["税务师", "企业端用户"]
    assert [step["handoff"] for step in journey["steps"]] == ["—", "账单 ID"]

    repo, package = _make_package(tmp_path, spec=SPEC.replace("| — |\n| J1-S2", "| 账单 ID |\n| J1-S2"))
    result = _init(repo, package, ok=False)

    assert result.returncode != 0
    assert "第 1 步 J1-S1 的承接必须为 —" in result.stderr


def test_init_persists_required_release_order(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")

    result = _init(repo, package)

    assert result.returncode == 0, result.stderr
    assert _state(package)["acceptance"]["releaseOrder"] == "required"


@pytest.mark.parametrize(
    ("spec", "tickets", "message"),
    [
        (SPEC.replace("| 入口类型 |", "| 入口 |"), None, "must use the 3.6 header"),
        (SPEC.replace("| J1-S1 | 税务师 | 页面 | 完成 | 税务端 Review 页点击“完成” |", "| J1-S1 | 税务师 | 页面 | 完成 |  |"), None, "empty cell"),
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
    assert json.loads(added.stdout)["added"] == 5
    state = _state(package)
    assert set(state["evidenceIndex"]) == {"run-setup:run-1", "journey:run-1:J1-S1", "suite:S-resolver", "review:TKT-01", "release"}
    assert "evidenceKey" not in state["evidenceIndex"]["journey:run-1:J1-S1"][0]
    recorded_at = state["evidenceIndex"]["journey:run-1:J1-S1"][0]["recordedAt"]
    assert recorded_at.endswith("Z") and engine._validate_iso_timestamp(recorded_at, "recordedAt") == recorded_at

    duplicate = _cli(repo, package, "evidence", "add", input_value=records)
    assert duplicate.returncode == 0, duplicate.stderr
    assert json.loads(duplicate.stdout)["added"] == 0
    assert _state(package)["evidenceIndex"]["journey:run-1:J1-S1"][0]["recordedAt"] == recorded_at

    before = _state(package)
    invalid_batch = [
        _journey_record(revision, "J1-S1", run_id="atomic"),
        {**_journey_record(revision, "J1-S2", run_id="atomic"), "entry": "wrong entry"},
    ]
    failed = _cli(repo, package, "evidence", "add", input_value=invalid_batch)
    assert failed.returncode != 0
    assert "operation entry" in failed.stderr
    assert _state(package) == before


def test_journey_step_requires_run_setup_and_setup_is_ordered_in_batches(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    journey = _journey_record(revision, "J1-S1", run_id="missing-setup")
    rejected = _cli(repo, package, "evidence", "add", input_value=journey, auto_setup=False)
    assert rejected.returncode != 0
    assert "先运行 Plan 中的 Harness setup 与 Harness precheck 并登记 run-setup" in rejected.stderr
    assert _state(package)["evidenceIndex"] == {}

    setup = _run_setup_record(revision, "registered")
    added_setup = _cli(repo, package, "evidence", "add", input_value=setup, auto_setup=False)
    assert added_setup.returncode == 0, added_setup.stderr
    assert _state(package)["evidenceIndex"]["run-setup:registered"][0]["recordedAt"].endswith("Z")
    added_step = _cli(
        repo, package, "evidence", "add",
        input_value=_journey_record(revision, "J1-S1", run_id="registered"), auto_setup=False,
    )
    assert added_step.returncode == 0, added_step.stderr

    batch_repo, batch_package, batch_revision = _init_v36(tmp_path / "batch")
    batch = [
        _run_setup_record(batch_revision, "same-batch"),
        _journey_record(batch_revision, "J1-S1", run_id="same-batch"),
    ]
    batch_result = _cli(batch_repo, batch_package, "evidence", "add", input_value=batch, auto_setup=False)
    assert batch_result.returncode == 0, batch_result.stderr
    assert set(_state(batch_package)["evidenceIndex"]) == {"run-setup:same-batch", "journey:same-batch:J1-S1"}

    reverse_repo, reverse_package, reverse_revision = _init_v36(tmp_path / "reverse")
    reverse = [
        _journey_record(reverse_revision, "J1-S1", run_id="same-batch"),
        _run_setup_record(reverse_revision, "same-batch"),
    ]
    reverse_result = _cli(reverse_repo, reverse_package, "evidence", "add", input_value=reverse, auto_setup=False)
    assert reverse_result.returncode != 0
    assert "Harness setup" in reverse_result.stderr
    assert _state(reverse_package)["evidenceIndex"] == {}


def test_first_journey_step_cannot_reuse_an_object_from_another_run(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    first = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert first.returncode == 0, first.stderr
    reused = _journey_record(revision, "J1-S1", run_id="second-run")
    reused["outputRef"] = "bill-123"

    rejected = _cli(repo, package, "evidence", "add", input_value=reused)

    assert rejected.returncode != 0
    assert "第 1 步产出的对象已在 run run-1 中出现，每次 run 需新建业务对象" in rejected.stderr
    assert "journey:second-run:J1-S1" not in _state(package)["evidenceIndex"]


def test_walking_skeleton_overdue_follows_satisfied_ticket_and_valid_first_visible_evidence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    repo, package, revision = _init_v36(tmp_path)
    suite = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, "S-resolver"))
    assert suite.returncode == 0, suite.stderr
    satisfied = _satisfy(repo, package, "TKT-01", revision)
    assert satisfied.returncode == 0, satisfied.stderr

    state = _state(package)
    status = engine._v36_acceptance_status(
        package, state, engine._validate_state(package, state), revision, attempt_active=True,
    )
    snapshot = situation._build_snapshot(situation.PackageReader(package, None))
    fact = situation._when_attempt_walking_skeleton_overdue(situation.FactContext(snapshot, "attempt", "initial"))
    assert status["walkingSkeletonOverdue"] is True
    assert fact.known and fact.value is True
    assert situation.main(["render", "--package", str(package), "--json"]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert any(row["slug"] == "attempt.accept.walking-skeleton-overdue" for row in rendered["matches"])
    overdue_summary = "".join(engine._owner_summary(status, revision, "blocked", "walking skeleton pending"))
    assert "- walking skeleton：J1-S1 应在 TKT-01 合入后走通，尚未走通" in overdue_summary

    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert added.returncode == 0, added.stderr
    state = _state(package)
    status = engine._v36_acceptance_status(
        package, state, engine._validate_state(package, state), revision, attempt_active=True,
    )
    snapshot = situation._build_snapshot(situation.PackageReader(package, None))
    fact = situation._when_attempt_walking_skeleton_overdue(situation.FactContext(snapshot, "attempt", "initial"))
    assert status["walkingSkeletonOverdue"] is False
    assert fact.known and fact.value is False
    assert situation.main(["render", "--package", str(package), "--json"]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert not any(row["slug"] == "attempt.accept.walking-skeleton-overdue" for row in rendered["matches"])
    completed_summary = "".join(engine._owner_summary(status, revision, "blocked", "walking skeleton complete"))
    assert "walking skeleton：" not in completed_summary


def test_evidence_add_rejects_caller_recorded_at(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    record = {**_journey_record(revision, "J1-S1"), "recordedAt": "2026-10-01T10:00:00Z"}

    result = _cli(repo, package, "evidence", "add", input_value=record)

    assert result.returncode != 0
    assert "generated by the runtime" in result.stderr
    assert _state(package)["evidenceIndex"] == {}


@pytest.mark.parametrize(
    ("extra", "message"),
    [
        ({"endedAt": "2026-10-01T10:00:00"}, "endedAt must include a timezone"),
        ({"usage": {"input": True, "output": 1}}, "usage.input must be a non-negative integer"),
        ({"usage": {"input": 1, "output": 1, "costUsd": -0.1}}, "costUsd must be a non-negative number"),
        ({"failureClass": "unknown"}, "failureClass must be flaky|env|real"),
    ],
)
def test_worker_return_optional_metrics_fields_are_validated(extra: dict, message: str) -> None:
    event = {
        "kind": "worker-return", "subject": "ticket:TKT-01", "outcome": "DONE",
        "of": "dispatch-1", "return_id": "return-1", **extra,
    }

    with pytest.raises(engine.StateError, match=message):
        engine._validate_trail_event(event)


def test_worker_return_optional_metrics_fields_accept_valid_values() -> None:
    event = {
        "kind": "worker-return", "subject": "ticket:TKT-01", "outcome": "DONE",
        "of": "dispatch-1", "return_id": "return-1", "endedAt": "2026-10-01T10:00:00Z",
        "usage": {"input": 0, "output": 4, "costUsd": 0.0}, "failureClass": "flaky",
    }

    assert engine._validate_trail_event(event) == event


@pytest.mark.parametrize(
    ("case", "message"),
    [
        ("missing-input", "缺少 inputRef"),
        ("missing-output", "缺少 outputRef"),
        ("mismatch", "不一致"),
    ],
)
def test_journey_handoff_requires_matching_input_and_previous_output(
    tmp_path: Path, case: str, message: str
) -> None:
    repo, package, revision = _init_v36(tmp_path)
    first_record = _journey_record(revision, "J1-S1")
    if case == "missing-output":
        first_record.pop("outputRef")
    first = _cli(repo, package, "evidence", "add", input_value=first_record)
    assert first.returncode == 0, first.stderr

    next_record = _journey_record(revision, "J1-S2")
    if case == "missing-input":
        next_record.pop("inputRef")
    elif case == "mismatch":
        next_record["inputRef"] = "bill-999"
    result = _cli(repo, package, "evidence", "add", input_value=next_record)

    assert result.returncode != 0
    assert "Journey J1" in result.stderr
    assert "J1-S2" in result.stderr
    assert "账单 ID" in result.stderr
    assert message in result.stderr
    if case == "missing-input":
        assert "bill-123" in result.stderr
    if case == "missing-output":
        assert "evidence invalidate" in result.stderr
        assert "另起 run" in result.stderr
    assert set(_state(package)["evidenceIndex"]) == {"run-setup:run-1", "journey:run-1:J1-S1"}


def test_journey_handoff_mismatch_rejects_entire_batch(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    before = _state(package)
    records = [
        _journey_record(revision, "J1-S1", run_id="atomic-handoff"),
        {**_journey_record(revision, "J1-S2", run_id="atomic-handoff"), "inputRef": "different-bill"},
    ]

    result = _cli(repo, package, "evidence", "add", input_value=records)

    assert result.returncode != 0
    assert "账单 ID" in result.stderr
    assert _state(package) == before


def test_journey_handoff_is_checked_for_every_record_of_the_step(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    assert _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1")).returncode == 0
    assert _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2")).returncode == 0
    before = _state(package)
    duplicate_step = _journey_record(revision, "J1-S2")
    duplicate_step["inputRef"] = "another-bill"

    result = _cli(repo, package, "evidence", "add", input_value=duplicate_step)

    assert result.returncode != 0
    assert "账单 ID" in result.stderr
    assert "不一致" in result.stderr
    assert _state(package) == before


def test_journey_step_with_dash_handoff_does_not_compare_references(tmp_path: Path) -> None:
    spec = SPEC.replace("| 账单 ID |", "| — |")
    repo, package = _make_package(tmp_path, spec=spec)
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    first_record = _journey_record(revision, "J1-S1")
    first_record["outputRef"] = "bill-123"
    second_record = _journey_record(revision, "J1-S2")
    second_record["inputRef"] = "unrelated-bill"

    first = _cli(repo, package, "evidence", "add", input_value=first_record)
    second = _cli(repo, package, "evidence", "add", input_value=second_record)

    assert first.returncode == 0, first.stderr
    assert second.returncode == 0, second.stderr


@pytest.mark.parametrize(
    ("record", "message"),
    [
        ({"kind": "journey-step", "runId": "run", "journeyId": "J1", "stepId": "J1-S1", "entry": "税务端 Review 页点击“完成”", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "missing or unknown fields"),
        ({"kind": "journey-step", "runId": "run", "journeyId": "J1", "stepId": "J1-S1", "actor": "税务师", "entry": "wrong", "surface": "page", "artifact": "artifacts/evidence.md", "revision": "", "environment": "local-test", "conclusion": "supporting"}, "operation entry"),
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


def test_journey_evidence_actor_must_match_spec_role(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    record = _journey_record(revision, "J1-S1", actor="企业端用户")

    result = _cli(repo, package, "evidence", "add", input_value=record)

    assert result.returncode != 0
    assert "actor does not match the Spec role" in result.stderr
    assert _state(package)["evidenceIndex"] == {}


def test_page_evidence_accepts_playwright_trace_with_spec_control_click(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)

    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))

    assert added.returncode == 0, added.stderr
    stored = _state(package)["evidenceIndex"]["journey:run-1:J1-S1"][0]
    assert stored["surface"] == "page"
    assert stored["artifact"] == "artifacts/page-trace.zip"


@pytest.mark.parametrize(
    ("events", "message"),
    [
        ([{"type": "before", "method": "waitForTimeout", "params": {"timeout": 10}}], "actual actions: none"),
        ([{"type": "before", "apiName": "locator.click", "method": "click", "params": {"selector": "getByRole('button', { name: '取消' })"}}], "click"),
    ],
)
def test_page_evidence_rejects_missing_or_mismatched_control_action(tmp_path: Path, events: list[dict], message: str) -> None:
    repo, package, revision = _init_v36(tmp_path)
    _write_trace(package, events)

    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))

    assert added.returncode != 0
    assert "完成" in added.stderr
    assert message in added.stderr
    assert _state(package)["evidenceIndex"] == {}


def test_page_evidence_rejects_malformed_playwright_trace(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    with zipfile.ZipFile(package / "artifacts/page-trace.zip", "w") as archive:
        archive.writestr("trace.trace", "{not json\n")

    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))

    assert added.returncode != 0
    assert "Playwright trace JSONL 无法解析" in added.stderr
    assert _state(package)["evidenceIndex"] == {}


def test_page_trace_error_limits_action_summary_to_five_entries(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    events = [
        {"type": "before", "apiName": "locator.click", "method": "click", "params": {"selector": f"button:{index}"}}
        for index in range(6)
    ]
    _write_trace(package, events)

    added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))

    assert added.returncode != 0
    assert "actual actions:" in added.stderr
    actual = added.stderr.split("actual actions:", 1)[1]
    assert actual.count("click") == 5
    assert "button:4" in actual and "button:5" not in actual


def test_page_manual_walkthrough_requires_manual_by_and_package_image(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    image = package / "artifacts/manual.png"
    image.write_bytes(b"fixture image")
    record = _journey_record(revision, "J1-S1", artifact="artifacts/manual.png", manual_by=" 张三 ")

    added = _cli(repo, package, "evidence", "add", input_value=record)

    assert added.returncode == 0, added.stderr
    stored = _state(package)["evidenceIndex"]["journey:run-1:J1-S1"][0]
    assert stored["manualBy"] == "张三"
    assert engine._v36_acceptance_status(
        package, _state(package), engine._validate_state(package, _state(package)), revision, attempt_active=True,
    )["journeys"][0]["manualWalkthroughs"] == [{"stepId": "J1-S1", "manualBy": "张三"}]

    rejected = _cli(
        repo,
        package,
        "evidence",
        "add",
        input_value=_journey_record(revision, "J1-S2", artifact="artifacts/evidence.md", manual_by="张三"),
    )

    assert rejected.returncode != 0
    assert "package image" in rejected.stderr


def test_file_surface_rejects_markdown_and_records_artifact_sha256(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, spec=_file_step_spec())
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    markdown = _journey_record(revision, "J1-S1", surface="file", artifact="artifacts/evidence.md")
    markdown["entry"] = "下载更正后的账单"
    rejected = _cli(repo, package, "evidence", "add", input_value=markdown)
    assert rejected.returncode != 0
    assert "must not use .md, .txt, or .log" in rejected.stderr

    output = package / "artifacts/corrected-invoice.csv"
    output.write_bytes(b"invoice_id,account\n123,4982\n")
    record = _journey_record(revision, "J1-S1", surface="file", artifact="artifacts/corrected-invoice.csv")
    record["entry"] = "下载更正后的账单"

    added = _cli(repo, package, "evidence", "add", input_value=record)

    assert added.returncode == 0, added.stderr
    stored = _state(package)["evidenceIndex"]["journey:run-1:J1-S1"][0]
    assert stored["artifactSha256"] == hashlib.sha256(output.read_bytes()).hexdigest()


def test_api_records_count_as_rehearsal_and_mixed_surface_reach_is_contiguous(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    api_run = [
        _journey_record(revision, step_id, run_id="api-run", surface="api")
        for step_id in ("J1-S1", "J1-S2")
    ]
    added = _cli(repo, package, "evidence", "add", input_value=api_run)
    assert added.returncode == 0, added.stderr
    status = engine._v36_acceptance_status(package, _state(package), engine._validate_state(package, _state(package)), revision, attempt_active=True)
    assert status["journeys"][0]["reach"] == 0
    assert status["journeys"][0]["rehearsalReach"] == 2
    assert status["journeys"][0]["surfaceCounts"] == {"page": 0, "file": 0, "api": 2, "log": 0}
    assert "J1 有效步骤走通 0/2 · API 预演 2/2" in (package / "progress.md").read_text(encoding="utf-8")
    metrics_result = _cli(repo, package, "package", "metrics")
    assert metrics_result.returncode == 0, metrics_result.stderr
    metrics_journey = json.loads((package / "execution/initial/metrics.json").read_text(encoding="utf-8"))["journeys"]["value"][0]
    assert metrics_journey["pageReach"]["value"] == 0
    assert metrics_journey["rehearsalReach"]["value"] == 2
    assert metrics_journey["surfaceCounts"]["api"]["value"] == 2

    mixed_run = [
        _journey_record(revision, "J1-S1", run_id="mixed-run", surface="page"),
        _journey_record(revision, "J1-S2", run_id="mixed-run", surface="api"),
    ]
    mixed = _cli(repo, package, "evidence", "add", input_value=mixed_run)
    assert mixed.returncode == 0, mixed.stderr
    status = engine._v36_acceptance_status(package, _state(package), engine._validate_state(package, _state(package)), revision, attempt_active=True)
    mixed_status = next(run for run in status["journeys"][0]["runs"] if run["runId"] == "mixed-run")
    assert mixed_status["reach"] == 1
    assert mixed_status["rehearsalReach"] == 2
    assert mixed_status["surfaceCounts"] == {"page": 1, "file": 0, "api": 1, "log": 0}


def test_log_records_count_as_reach_and_preparation_is_metrics_only(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, spec=_log_step_spec())
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    log = package / "artifacts/runtime.log"
    log.write_text("platform experience tool called\n", encoding="utf-8")
    records = [
        _journey_record(revision, "J1-S1", run_id="log-run"),
        _journey_record(
            revision, "J1-S2", run_id="log-run", surface="log", artifact="artifacts/runtime.log",
            actor="验收执行者", entry="核对 AI 调用记录",
        ),
    ]

    added = _cli(repo, package, "evidence", "add", input_value=records)

    assert added.returncode == 0, added.stderr
    summary = engine._validate_state(package, _state(package))
    status = engine._v36_acceptance_status(package, _state(package), summary, revision, attempt_active=True)
    journey = status["journeys"][0]
    assert journey["reach"] == 2
    assert journey["rehearsalReach"] == 2
    assert journey["surfaceCounts"] == {"page": 1, "file": 0, "api": 0, "log": 1}
    progress = (package / "progress.md").read_text(encoding="utf-8")
    assert "J1 有效步骤走通 2/2 · API 预演 2/2" in progress
    assert "准备" not in progress and "三张同条件票据" not in progress
    owner_summary = "".join(engine._owner_summary(status, revision, "blocked", "still validating"))
    assert "准备" not in owner_summary and "三张同条件票据" not in owner_summary

    metrics_result = _cli(repo, package, "package", "metrics")
    assert metrics_result.returncode == 0, metrics_result.stderr
    metrics_journey = json.loads((package / "execution/initial/metrics.json").read_text(encoding="utf-8"))["journeys"]["value"][0]
    assert metrics_journey["pageReach"]["value"] == 2
    assert metrics_journey["rehearsalReach"]["value"] == 2
    assert metrics_journey["surfaceCounts"]["log"]["value"] == 1
    assert metrics_journey["preparation"]["value"] == "同一门店、三张同条件票据。"


@pytest.mark.parametrize("field", [
    "Harness setup", "Harness precheck", "Harness cleanup", "Harness isolation", "First visible step",
])
@pytest.mark.parametrize("command", ["init", "validate"])
def test_harness_plan_requires_all_fixed_rows(tmp_path: Path, field: str, command: str) -> None:
    line = next(line for line in PLAN.splitlines() if line.startswith(f"{field}:"))
    invalid_plan = PLAN.replace(line + "\n", "")
    repo, package = _make_package(tmp_path, plan=invalid_plan if command == "init" else PLAN)
    if command == "validate":
        _init(repo, package)
        (package / "plan.md").write_text(invalid_plan, encoding="utf-8")
        result = _cli(repo, package, "package", "validate")
    else:
        result = _init(repo, package, ok=False)

    assert result.returncode != 0
    assert field in result.stderr
    assert {
        "Harness setup": "Harness setup: <命令>",
        "Harness precheck": "Harness precheck: <命令>",
        "Harness cleanup": "Harness cleanup: <命令>",
        "Harness isolation": "Harness isolation: per-run",
        "First visible step": "First visible step: <StepId> @ <TicketId>",
    }[field] in result.stderr
    assert "正确格式" in result.stderr
    if command == "init":
        assert not (package / ".impl-package/state.json").exists()


@pytest.mark.parametrize(
    ("plan", "spec", "tickets", "message"),
    [
        (PLAN.replace("Harness isolation: per-run", "Harness isolation: shared"), SPEC, None, "Harness isolation: shared"),
        (PLAN.replace("J1-S1 @ TKT-01", "J1-S9 @ TKT-01"), SPEC, None, "J1-S9"),
        (PLAN.replace("J1-S1 @ TKT-01", "J1-S2 @ TKT-02"), _log_step_spec(), None, "页面 或 文件"),
        (PLAN.replace("J1-S1 @ TKT-01", "J1-S1 @ TKT-99"), SPEC, None, "TKT-99"),
    ],
)
def test_harness_plan_rejects_invalid_values_and_targets(
    tmp_path: Path, plan: str, spec: str, tickets: dict[str, str] | None, message: str,
) -> None:
    repo, package = _make_package(tmp_path, plan=plan, spec=spec, tickets=tickets)

    result = _init(repo, package, ok=False)

    assert result.returncode != 0
    assert message in result.stderr
    assert "First visible step:" in result.stderr or "Harness isolation:" in result.stderr


def test_record_surface_requires_a_record_entry_and_any_package_file(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, spec=_log_step_spec())
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    log = package / "artifacts/runtime.log"
    log.write_text("tool called\n", encoding="utf-8")

    wrong_step = _journey_record(revision, "J1-S1", surface="log", artifact="artifacts/runtime.log")
    wrong_step_result = _cli(repo, package, "evidence", "add", input_value=wrong_step)
    first_step_result = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    valid_step = _journey_record(
        revision, "J1-S2", surface="log", artifact="artifacts/runtime.log",
        actor="验收执行者", entry="核对 AI 调用记录",
    )
    valid_step["artifact"] = "artifacts/evidence.md"
    valid_step_result = _cli(repo, package, "evidence", "add", input_value=valid_step)

    assert wrong_step_result.returncode != 0
    assert "entry type 页面 requires surface=page" in wrong_step_result.stderr
    assert first_step_result.returncode == 0, first_step_result.stderr
    assert valid_step_result.returncode == 0, valid_step_result.stderr


def test_situation_prompts_page_or_file_after_full_api_rehearsal(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    repo, package, revision = _init_v36(tmp_path)
    records = [_journey_record(revision, step, surface="api") for step in ("J1-S1", "J1-S2")]
    added = _cli(repo, package, "evidence", "add", input_value=records)
    assert added.returncode == 0, added.stderr

    code = situation.main(["render", "--package", str(package), "--json"])
    rendered = json.loads(capsys.readouterr().out)

    assert code == 0
    journey = next(row for row in rendered["matches"] if row["slug"] == "attempt.accept.journey-incomplete")
    assert "API 预演已走通，仍需页面/文件/记录证据" in journey["protocol"]
    assert "API 预演已走通，仍需页面/文件/记录证据" in journey["actions"][0]["do"]


def test_journey_reach_is_contiguous_per_run_and_invalidation_uses_key(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    first = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S1"))
    assert first.returncode == 0, first.stderr
    assert "J1 有效步骤走通 1/2 · API 预演 1/2" in (package / "progress.md").read_text(encoding="utf-8")

    second = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2"))
    assert second.returncode == 0, second.stderr
    assert "J1 有效步骤走通 2/2 · API 预演 2/2" in (package / "progress.md").read_text(encoding="utf-8")
    assert "S-resolver" in (package / "progress.md").read_text(encoding="utf-8")
    assert "TKT-01 | PENDING" in (package / "progress.md").read_text(encoding="utf-8")

    invalidated = _cli(repo, package, "evidence", "invalidate", "--key", "journey:run-1:J1-S1", "--invalidated-by", "fixture")
    assert invalidated.returncode == 0, invalidated.stderr
    assert "J1 有效步骤走通 0/2 · API 预演 0/2" in (package / "progress.md").read_text(encoding="utf-8")
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
    assert "J1 有效步骤走通 0/2 · API 预演 0/2" in (package / "progress.md").read_text(encoding="utf-8")

    before = _state(package)
    mixed = [
        _journey_record(revision, "J1-S1", run_id="mixed", environment="local-test"),
        _journey_record(revision, "J1-S2", run_id="mixed", environment="other-test"),
    ]
    failed = _cli(repo, package, "evidence", "add", input_value=mixed)
    assert failed.returncode != 0
    assert "run-setup" in failed.stderr
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
    assert "J1 有效步骤走通 0/2 · API 预演 0/2" in (package / "progress.md").read_text(encoding="utf-8")
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

    assert "J1 有效步骤走通 2/2 · API 预演 2/2" in (package2 / "progress.md").read_text(encoding="utf-8")
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
    _append_spec_note(package, "Owner clarification: The accepted wording is unchanged.")
    before = _cli(repo, package, "package", "validate")
    assert before.returncode == 0, before.stderr
    assert any(row["code"] == "contract-amendment-unregistered" and row["path"] == "spec.md" for row in json.loads(before.stdout)["findings"])

    args = ("package", "amendment", "add", "--id", "A-1", "--summary", "补充时间锚点", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    added = _cli(repo, package, *args)
    assert added.returncode == 0, added.stderr
    state = _state(package)
    assert state["acceptance"]["amendments"][0]["createdAt"].endswith("Z")
    add_events = [row for row in engine._active_trail_rows(package, "initial") if row.get("transition") == "amendment"]
    assert [(row.get("from"), row.get("to"), row.get("id")) for row in add_events] == [(None, "PENDING", "A-1")]
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
    state = _state(package)
    assert state["acceptance"]["amendments"][0]["confirmedAt"].endswith("Z")
    amendment_events = [row for row in engine._active_trail_rows(package, "initial") if row.get("transition") == "amendment"]
    assert [(row.get("from"), row.get("to")) for row in amendment_events] == [(None, "PENDING"), ("PENDING", "CONFIRMED")]
    repeated_confirm = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision)
    assert repeated_confirm.returncode == 0 and json.loads(repeated_confirm.stdout)["idempotent"] is True
    different_confirm = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Another Owner", "--confirmed-revision", revision)
    assert different_confirm.returncode != 0 and "different confirmation" in different_confirm.stderr
    after = _cli(repo, package, "package", "validate")
    assert after.returncode == 0, after.stderr
    assert not any(row["code"] == "contract-amendment-unregistered" for row in json.loads(after.stdout)["findings"])


def test_amendment_without_registration_blob_does_not_cover_contract_change(tmp_path: Path) -> None:
    repo, package, _ = _init_v36(tmp_path)
    _append_spec_note(package, "Clarification: Wording is clarified.")
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
    assert "J1 有效步骤走通 1/2 · API 预演 1/2" in (package / "progress.md").read_text(encoding="utf-8")
    second_step = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, "J1-S2"))
    assert second_step.returncode == 0, second_step.stderr
    assert "J1 有效步骤走通 2/2 · API 预演 2/2" in (package / "progress.md").read_text(encoding="utf-8")
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

    _append_spec_note(package, "Owner clarification: First approved wording.")
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
    _append_spec_note(package, "Owner clarification: Second approved wording.")
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
    assert "- J1 纠正后下一张账单用新科目：有效步骤走通 2/2 · API 预演 2/2" in gate_text
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
    _append_spec_note(unregistered_package, "Unregistered change")
    unregistered_gate = _gate(unregistered_repo, unregistered_package, "pass", unregistered_revision)
    assert unregistered_gate.returncode != 0
    assert "spec.md" in unregistered_gate.stderr and "未登记 Amendment" in unregistered_gate.stderr


def test_gate_pass_rejects_each_acceptance_gap_and_gate_blocked_keeps_attempt_active(tmp_path: Path) -> None:
    repo, package = _make_package(tmp_path, plan=PLAN + "Release order: required\n")
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    _append_spec_note(package, "Owner clarification: Amended wording.")
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
    _append_spec_note(package, "Owner clarification: Approved wording.")
    added = _cli(repo, package, "package", "amendment", "add", "--id", "A-1", "--summary", "回填时间锚点", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    assert added.returncode == 0, added.stderr
    assert _gate(repo, package, "pass", revision).returncode != 0
    _gate(repo, package, "blocked", revision, reason="A-1 pending").check_returncode()
    gate_events = [row for row in engine._active_trail_rows(package, "initial") if row.get("transition") == "gate"]
    assert gate_events[-1]["verdict"] == "blocked" and gate_events[-1]["commit"] == revision
    _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision).check_returncode()

    for suite in ("S-resolver", "S-workflow", "S-safety"):
        added_suite = _cli(repo, package, "evidence", "add", input_value=_suite_record(revision, suite))
        assert added_suite.returncode == 0, added_suite.stderr
    for step in ("J1-S1", "J1-S2"):
        added_step = _cli(
            repo, package, "evidence", "add",
            input_value=_journey_record(revision, step, run_id="api-rehearsal", surface="api"),
        )
        assert added_step.returncode == 0, added_step.stderr
    _satisfy(repo, package, "TKT-01", revision)
    _satisfy(repo, package, "TKT-02", revision)
    release = _cli(repo, package, "evidence", "add", input_value={"kind": "release", "artifact": "artifacts/evidence.md", "revision": revision, "environment": "local-test", "conclusion": "supporting"})
    assert release.returncode == 0, release.stderr
    _add_terminal_summary(repo, package, revision)

    api_only = _gate(repo, package, "pass", revision, reason="API rehearsal only")
    assert api_only.returncode != 0
    assert "API 预演已走通，仍需页面/文件/记录证据" in api_only.stderr
    assert not engine._lifecycle(package, "initial", repo).frozen

    (package / "artifacts/manual.png").write_bytes(b"manual walkthrough image")
    page_records = [
        _journey_record(revision, "J1-S1", run_id="page-run", artifact="artifacts/manual.png", manual_by="张三"),
        _journey_record(revision, "J1-S2", run_id="page-run"),
    ]
    added_pages = _cli(repo, package, "evidence", "add", input_value=page_records)
    assert added_pages.returncode == 0, added_pages.stderr

    passed = _gate(repo, package, "pass", revision, reason="全部验收满足")
    assert passed.returncode == 0, passed.stderr or passed.stdout
    assert "metrics: execution/initial/metrics.json" in passed.stdout
    assert (package / "execution/initial/metrics.json").is_file()
    gate_events = [row for row in engine._active_trail_rows(package, "initial") if row.get("transition") == "gate"]
    assert gate_events[-1]["verdict"] == "pass" and gate_events[-1]["commit"] == revision
    text = (package / "gate.md").read_text(encoding="utf-8")
    assert "三张同条件票据" not in text
    assert "三张同条件票据" not in (package / "progress.md").read_text(encoding="utf-8")
    assert "- J1 纠正后下一张账单用新科目：有效步骤走通 2/2 · API 预演 2/2" in text
    assert "- 套件：3/3 通过" in text
    assert "- 合同修订：无待确认或漏登" in text
    assert "- 发布顺序：已记录" in text
    assert f"- 最终版本：{revision[:7]}" in text
    assert "- 结论：pass — 全部验收满足" in text
    assert "- 人工走查：J1-S1（张三）" in text
    assert engine._gate_info(package, repo) == {"verdict": "pass", "attempt": "initial", "commit": revision}
    assert engine._lifecycle(package, "initial", repo).frozen
    assert (package / ".impl-package/attempts/initial.json").is_file()


def test_review_record_requires_impact_for_v36_and_rejects_unknown_impact(tmp_path: Path) -> None:
    repo, package, revision = _init_v36(tmp_path)
    finding = {
        "findingKey": "broken-seam", "id": "F-001", "title": "Broken seam",
        "ticketIds": ["TKT-01"], "tracks": ["Track A"],
        "classification": "blocker", "lifecycle": "open",
    }
    canonical = {
        "schemaVersion": 1, "reviewRunId": "review-1", "phase": "initial",
        "resolvedHead": revision, "findings": [finding],
    }

    with pytest.raises(review_track_stats.ReviewStatsError, match="impact is required for formatVersion 3.6"):
        review_track_stats.record_summary(package, canonical)
    with pytest.raises(review_track_stats.ReviewStatsError, match="impact must be one of"):
        review_track_stats.record_summary(package, {**canonical, "findings": [{**finding, "impact": "wide"}]})

    recorded = review_track_stats.record_summary(package, {**canonical, "findings": [{**finding, "impact": "seam"}]})
    assert recorded["appended"] is True


def _metrics_row(seq: int, ts: str, kind: str, subject: str, **fields: object) -> dict[str, object]:
    return {"v": 1, "seq": seq, "ts": ts, "kind": kind, "subject": subject, "head": "a" * 40, **fields}


def _write_metrics_trail(package: Path, rows: list[dict[str, object]]) -> None:
    trail = package / "execution/initial/trail.jsonl"
    trail.parent.mkdir(parents=True, exist_ok=True)
    trail.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_package_metrics_reports_numeric_sections_and_keeps_situation_and_progress_clean(
    tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    tickets = {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow", dependencies="- implementation: TKT-01"),
    }
    repo, package = _make_package(tmp_path, tickets=tickets)
    _init(repo, package)
    revision = _git(repo, "rev-parse", "HEAD")
    for step_id in ("J1-S1", "J1-S2"):
        added = _cli(repo, package, "evidence", "add", input_value=_journey_record(revision, step_id))
        assert added.returncode == 0, added.stderr

    _append_spec_note(package, "Owner clarification: Keep the accepted wording.")
    added = _cli(repo, package, "package", "amendment", "add", "--id", "A-1", "--summary", "Clarify wording", "--affected", "spec.md", "--artifact", "artifacts/evidence.md")
    assert added.returncode == 0, added.stderr
    confirmed = _cli(repo, package, "package", "amendment", "confirm", "--id", "A-1", "--expect", "PENDING", "--confirmed-by", "Owner", "--confirmed-revision", revision)
    assert confirmed.returncode == 0, confirmed.stderr

    state = _state(package)
    state["evidenceIndex"]["run-setup:run-1"][0]["recordedAt"] = "2026-10-01T09:59:00Z"
    state["evidenceIndex"]["journey:run-1:J1-S1"][0]["recordedAt"] = "2026-10-01T10:00:00Z"
    state["evidenceIndex"]["journey:run-1:J1-S2"][0]["recordedAt"] = "2026-10-01T10:01:40Z"
    amendment = state["acceptance"]["amendments"][0]
    amendment["createdAt"] = "2026-10-01T10:00:00Z"
    amendment["confirmedAt"] = "2026-10-01T10:02:00Z"
    (package / ".impl-package/state.json").write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows = [
        _metrics_row(1, "2026-10-01T10:00:00Z", "dispatch", "ticket:TKT-01", dispatch_id="d1", mode="fix"),
        _metrics_row(2, "2026-10-01T10:00:10Z", "worker-return", "ticket:TKT-01", of="d1", return_id="r1", outcome="DONE", endedAt="2026-10-01T10:00:20Z", usage={"input": 10, "output": 5, "costUsd": 0.25}, failureClass="flaky"),
        _metrics_row(3, "2026-10-01T10:01:00Z", "dispatch", "ticket:TKT-01", dispatch_id="d2", mode="fix"),
        _metrics_row(4, "2026-10-01T10:01:10Z", "worker-return", "ticket:TKT-01", of="d2", return_id="r2", outcome="DONE", usage={"input": 3, "output": 4}, failureClass="real"),
        _metrics_row(5, "2026-10-01T10:02:00Z", "dispatch", "ticket:TKT-01", dispatch_id="d3", mode="verify"),
        _metrics_row(6, "2026-10-01T10:02:30Z", "worker-return", "ticket:TKT-01", of="d3", return_id="r3", outcome="DONE"),
        _metrics_row(7, "2026-10-01T10:03:00Z", "result", "ticket:TKT-01", transition="ticket-state", **{"from": "PENDING", "to": "SATISFIED", "outcome": "SATISFIED"}),
        _metrics_row(8, "2026-10-01T10:05:00Z", "dispatch", "ticket:TKT-02", dispatch_id="d4", mode="implement"),
        _metrics_row(9, "2026-10-01T10:07:00Z", "worker-return", "ticket:TKT-02", of="d4", return_id="r4", outcome="DONE", usage={"input": 7, "output": 1, "costUsd": 0.15}, failureClass="env"),
        _metrics_row(10, "2026-10-01T10:08:00Z", "result", "ticket:TKT-02", transition="ticket-state", **{"from": "PENDING", "to": "SATISFIED", "outcome": "SATISFIED"}),
        _metrics_row(11, "2026-10-01T10:09:00Z", "fact", "review:review-1", key="review.canonical_summary", value={
            "schemaVersion": 1, "reviewRunId": "review-1", "phase": "initial", "resolvedHead": revision,
            "findings": [{"findingKey": "seam-1", "id": "F-001", "title": "Broken seam", "ticketIds": ["TKT-01"], "tracks": ["Track A"], "impact": "seam", "classification": "blocker", "lifecycle": "open"}],
        }),
        _metrics_row(12, "2026-10-01T10:10:00Z", "fact", "attempt", key="review.terminal_summary", value={"reviewRunId": "terminal-1", "comparisonHead": revision, "safetyApplicable": False, "results": []}),
    ]
    _write_metrics_trail(package, rows)
    progress_before = (package / "progress.md").read_bytes()
    state_before = (package / ".impl-package/state.json").read_bytes()

    result = _cli(repo, package, "package", "metrics")
    assert result.returncode == 0, result.stderr
    assert len(result.stdout.splitlines()) <= 30
    assert "[处境]" not in result.stdout
    report = json.loads((package / "execution/initial/metrics.json").read_text(encoding="utf-8"))

    assert report["dispatch"]["total"]["value"] == 4
    assert {mode: report["dispatch"]["byMode"][mode]["value"] for mode in ("fix", "verify", "implement")} == {"fix": 2, "verify": 1, "implement": 1}
    assert [row["seconds"]["value"] for row in report["dispatch"]["durations"]] == [20.0, 10.0, 30.0, 120.0]
    assert report["dispatch"]["ticketCounts"]["TKT-01"]["repeatedFix"]["value"] == 1
    assert report["tickets"]["TKT-01"]["wallClockSeconds"]["value"] == 180.0
    edge = report["criticalPathWait"]["edges"]["value"][0]
    assert edge["waitSeconds"]["value"] == 120.0
    assert edge["upstreamDispatchesBeforeSatisfied"]["value"] == 3
    assert report["criticalPathWait"]["dispatchesBeforeFirstDownstreamImplement"]["value"] == 3
    assert report["findings"]["byTrack"]["Track A"]["value"] == 1
    assert report["findings"]["byTicket"]["TKT-01"]["value"] == 1
    assert report["findings"]["byImpact"]["seam"]["value"] == 1
    assert report["findings"]["upstreamSeamSafetyRatio"]["value"] == {"numerator": 1, "denominator": 1, "ratio": 1.0}
    journey = report["journeys"]["value"][0]
    assert report["journeys"]["firstVisibleStep"]["declared"]["value"] == {"step": "J1-S1", "ticket": "TKT-01"}
    assert report["journeys"]["firstVisibleStep"]["firstRecordedAt"]["value"] == "2026-10-01T10:00:00Z"
    assert report["journeys"]["firstVisibleStep"]["secondsFromFirstDispatch"]["value"] == 0.0
    assert journey["runCount"]["value"] == 1
    assert journey["runs"]["value"][0]["firstLastRecordedAtSeconds"]["value"] == 100.0
    assert journey["runs"]["value"][0]["setupAt"]["value"] == "2026-10-01T09:59:00Z"
    assert journey["runs"]["value"][0]["setupToFirstStepSeconds"]["value"] == 60.0
    assert journey["pageReach"]["value"] == 2
    assert journey["rehearsalReach"]["value"] == 2
    assert journey["surfaceCounts"]["page"]["value"] == 2
    assert journey["surfaceCounts"]["file"]["value"] == 0
    assert journey["surfaceCounts"]["api"]["value"] == 0
    assert journey["surfaceCounts"]["log"]["value"] == 0
    assert journey["runs"]["value"][0]["pageReach"]["value"] == 2
    assert journey["complete"]["value"] is True
    assert report["amendments"]["value"][0]["elapsedSeconds"]["value"] == 120.0
    assert report["usage"]["input"]["value"] == 20
    assert report["usage"]["output"]["value"] == 10
    assert report["usage"]["costUsd"]["value"] == 0.4
    assert report["failures"]["counts"]["flaky"]["value"] == 1
    assert report["coverage"]["endedAt"]["value"] == {"filled": 1, "records": 4, "rate": 0.25}
    assert report["coverage"]["recordedAt"]["value"] == {"filled": 3, "records": 3, "rate": 1.0}
    assert (package / "progress.md").read_bytes() == progress_before
    assert (package / ".impl-package/state.json").read_bytes() == state_before

    assert situation.main(["render", "--package", str(package), "--json"]) == 0
    rendered = capsys.readouterr().out
    rendered_value = json.loads(rendered)

    def keys(value: object) -> set[str]:
        if isinstance(value, dict):
            return {str(key) for key in value} | set().union(*(keys(item) for item in value.values()))
        if isinstance(value, list):
            return set().union(*(keys(item) for item in value)) if value else set()
        return set()

    assert "metrics.json" not in rendered.lower()
    assert "metrics" not in {key.lower() for key in keys(rendered_value)}


def test_package_metrics_keeps_unavailable_values_null_with_reasons(tmp_path: Path) -> None:
    tickets = {
        "01.md": _ticket("TKT-01", "J1-S1", "S-resolver"),
        "02.md": _ticket("TKT-02", "J1-S2", "S-workflow", dependencies="- implementation: TKT-01"),
    }
    repo, package = _make_package(tmp_path, tickets=tickets)
    _init(repo, package)
    _write_metrics_trail(package, [
        _metrics_row(1, "2026-10-01T10:00:00Z", "dispatch", "ticket:TKT-01", dispatch_id="d1", mode="fix"),
        _metrics_row(2, "2026-10-01T10:01:00Z", "dispatch", "ticket:TKT-02", dispatch_id="d2", mode="implement"),
    ])
    out = tmp_path / "metrics.json"

    result = _cli(repo, package, "package", "metrics", "--out", str(out))

    assert result.returncode == 0, result.stderr
    report = json.loads(out.read_text(encoding="utf-8"))
    assert report["dispatch"]["durations"][0]["seconds"]["value"] is None
    assert report["dispatch"]["durations"][0]["seconds"]["missingReason"] == "no matching worker-return"
    assert report["criticalPathWait"]["edges"]["value"][0]["waitSeconds"]["value"] is None
    assert report["criticalPathWait"]["edges"]["value"][0]["waitSeconds"]["missingReason"] == "upstream Ticket has no SATISFIED result"
    assert report["usage"]["input"]["value"] is None
    assert "no worker-return usage.input" in report["usage"]["input"]["missingReason"]
    assert report["journeys"]["value"][0]["runCount"]["value"] == 0
    assert report["coverage"]["recordedAt"]["value"] is None
    assert report["coverage"]["recordedAt"]["missingReason"] == "no evidence records"


def test_package_metrics_runs_on_35_and_marks_journey_sections_unavailable(tmp_path: Path) -> None:
    plan = PLAN.replace("Acceptance: journey\n", "")
    tickets = {
        "01.md": "# TKT-01\n\nTicket ID: TKT-01\nPublication Status: Draft\nAttempt ID: initial\n\n## Claims\n\n- Stable claim ID: `AC-1`\n  - Evidence timing: `remaining-completion`\n",
    }
    repo, package = _make_package(tmp_path, plan=plan, tickets=tickets)
    initialized = _init(repo, package)
    assert json.loads(initialized.stdout)["formatVersion"] == "3.5"

    result = _cli(repo, package, "package", "metrics")

    assert result.returncode == 0, result.stderr
    report = json.loads((package / "execution/initial/metrics.json").read_text(encoding="utf-8"))
    assert report["formatVersion"]["value"] == "3.5"
    assert report["journeys"]["value"] is None
    assert "require formatVersion 3.6" in report["journeys"]["missingReason"]
    assert report["amendments"]["value"] is None
    assert report["coverage"]["recordedAt"]["value"] is None
    assert "3.5" in report["coverage"]["recordedAt"]["missingReason"]


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
    _append_spec_note(package, "Owner clarification: Changed.")

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
