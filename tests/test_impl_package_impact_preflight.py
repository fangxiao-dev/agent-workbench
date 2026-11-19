from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_impl_package_journey import (  # noqa: E402
    _template_cache, _cli, _commit_file, _commit_path, _init_v36, _journey_record, _review_record, _run_setup_record, _suite_record,
)
from impl_package_runtime import impact  # noqa: E402

_ = _template_cache


def test_suite_cover_paths() -> None:
    assert impact.suite_cover_paths("pnpm vitest --spec tests/a/x.test.ts") == ["tests/a"]
    assert impact.suite_cover_paths("run --spec=./tests/a/x.ts --spec tests/b/y.ts") == ["tests/a", "tests/b"]
    assert impact.suite_cover_paths("pnpm vitest --spec tests/a/x.ts # covers: lib/x/, app/y") == ["lib/x", "app/y"]
    assert impact.suite_cover_paths("pnpm test resolver") is None  # nothing derivable -> conservative
    assert impact.suite_cover_paths("pnpm test --spec x.test.ts") is None  # bare file has no directory


def test_journey_cover_tokens() -> None:
    step = lambda op, obs: {"operationEntry": op, "observationSurface": obs}  # noqa: E731
    assert impact.journey_cover_tokens([step("打开 /employees/new", "app/employees/page.tsx")]) == ["/employees/new", "app/employees/page.tsx"]
    assert impact.journey_cover_tokens([step("点击“完成”", "Review 页记录")]) is None
    assert impact.journey_cover_tokens([step("点击 covers: app/billing", "页面")]) == ["app/billing"]


def _seed(tmp_path: Path):
    repo, package, rev = _init_v36(tmp_path)
    spec = package / "spec.md"
    text = spec.read_text(encoding="utf-8")
    text = text.replace("| pnpm test resolver |", "| pnpm test --spec tests/resolver/a.test.ts |")
    text = text.replace("| pnpm test workflow |", "| pnpm test workflow # covers: lib/workflow |")
    text = text.replace("税务端 Review 页点击“完成”", "税务端 Review 页点击“完成” covers: app/billing").replace("企业端打开下一张同类账单", "企业端打开下一张同类账单 covers: app/billing")
    spec.write_text(text, encoding="utf-8")
    rev = _commit_path(repo, spec, "spec coverage")
    records = [
        _run_setup_record(rev), _journey_record(rev, "J1-S1", entry="税务端 Review 页点击“完成” covers: app/billing"),
        _journey_record(rev, "J1-S2", entry="企业端打开下一张同类账单 covers: app/billing"),
        _suite_record(rev, "S-resolver"), _suite_record(rev, "S-workflow"), _review_record(rev, "TKT-01"),
    ]
    assert _cli(repo, package, "evidence", "add", input_value=records).returncode == 0
    return repo, package, rev


def _impact(repo, package, to, *extra):
    result = _cli(repo, package, "evidence", "impact", "--to", to, "--json", "--judged-by", "me", *extra)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_impact_splits_rerun_and_carry_and_emits_batch_command(tmp_path: Path) -> None:
    repo, package, _rev = _seed(tmp_path)
    _commit_file(repo, "docs/guide.md", "d\n")  # non-runtime: never counts
    head = _commit_file(repo, "lib/workflow/engine.py", "x = 1\n")
    before = (package / ".impl-package/state.json").read_bytes()
    result = _impact(repo, package, head)
    assert [u["key"] for u in result["rerun"]] == ["suite:S-workflow"]
    assert {u["key"] for u in result["carry"]} == {"suite:S-resolver", "run:run-1"}
    command = result["carryCommand"]
    assert f"--to {head}" in command and "--judged-by me" in command
    assert "--select key:suite:S-resolver" in command and "--select run:run-1" in command
    assert "lib/workflow/engine.py" in command  # reason carries the changed-file summary
    assert result["rerun"][0]["command"] == "pnpm test workflow"
    assert (package / ".impl-package/state.json").read_bytes() == before  # read-only


def test_impact_journey_hit_and_unknown_coverage_are_rerun(tmp_path: Path) -> None:
    repo, package, _rev = _seed(tmp_path)
    head = _commit_file(repo, "app/billing/page.tsx", "x\n")
    result = _impact(repo, package, head)
    assert "run:run-1" in {u["key"] for u in result["rerun"]}
    assert {u["key"] for u in result["carry"]} == {"suite:S-resolver", "suite:S-workflow"}


def test_impact_unknown_coverage_is_conservative(tmp_path: Path) -> None:
    repo, package, rev = _init_v36(tmp_path)  # default fixture suites have no --spec / covers
    assert _cli(repo, package, "evidence", "add", input_value=[_suite_record(rev, "S-resolver")]).returncode == 0
    head = _commit_file(repo, "src/app.py", "v = 1\n")
    result = _impact(repo, package, head)
    assert [u["key"] for u in result["rerun"]] == ["suite:S-resolver"]
    assert result["carry"] == [] and result["carryCommand"] is None


def test_impact_human_output_and_current_evidence_skipped(tmp_path: Path) -> None:
    repo, package, rev = _seed(tmp_path)
    head = _commit_file(repo, "docs/only.md", "d\n")
    result = _impact(repo, package, head)
    assert result["rerun"] == [] and result["carry"] == [] and result["current"] >= 3
    head = _commit_file(repo, "lib/workflow/e.py", "x\n")
    text = _cli(repo, package, "evidence", "impact", "--to", head).stdout
    assert "需重跑 (1)" in text and "可沿用 (2)" in text and "evidence carry-forward" in text


def test_preflight_reports_categories_with_fixes_and_exit_code(tmp_path: Path) -> None:
    repo, package, _rev = _seed(tmp_path)
    _commit_file(repo, "lib/workflow/engine.py", "x = 1\n")
    result = _cli(repo, package, "gate", "preflight", "--json")
    assert result.returncode == 1
    report = json.loads(result.stdout)
    assert not report["ok"]
    categories = report["counts"]
    assert categories["stale"] >= 1 and categories["ticket"] >= 1 and categories["review"] == 1 and categories["durable"] == 1
    stale = [g for g in report["gaps"] if g["category"] == "stale"]
    assert any("evidence carry-forward" in g["fix"] and "--select" in g["fix"] for g in stale)  # impact-derived batch
    order = [g["category"] for g in report["gaps"]]
    assert order == sorted(order, key=lambda c: ("amendment", "suite", "journey", "stale", "review", "ticket", "release", "references", "durable", "state").index(c))
    assert all(g["fix"] or g["category"] in {"references", "state"} for g in report["gaps"])


def test_preflight_quiet_summary_and_read_only(tmp_path: Path) -> None:
    repo, package, _rev = _seed(tmp_path)
    before = sorted(p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file())
    state_before = (package / ".impl-package/state.json").read_bytes()
    quiet = _cli(repo, package, "gate", "preflight", "--quiet")
    assert quiet.returncode == 1 and quiet.stdout == ""
    line = _cli(repo, package, "gate", "preflight", "--quiet", "--summary")
    assert line.returncode == 1 and line.stdout.startswith("gate preflight: ") and line.stdout.count("\n") == 1
    human = _cli(repo, package, "gate", "preflight").stdout
    assert "[ticket]" in human and "修复：" in human
    assert state_before == (package / ".impl-package/state.json").read_bytes()
    assert before == sorted(p.relative_to(package).as_posix() for p in package.rglob("*") if p.is_file())


def test_preflight_message_set_matches_gate_pass(tmp_path: Path) -> None:
    repo, package, _rev = _seed(tmp_path)
    head = _commit_file(repo, "lib/workflow/engine.py", "x = 1\n")
    gaps = json.loads(_cli(repo, package, "gate", "preflight", "--json").stdout)["gaps"]
    rejected = _cli(repo, package, "gate", "pass", "--comparison-commit", head, "--reason", "r").stderr
    assert all(g["message"] in rejected for g in gaps if g["category"] != "durable")


def _terminal_ready(tmp_path: Path):
    from test_impl_package_journey import _add_terminal_summary, _satisfy

    repo, package, rev = _init_v36(tmp_path)
    for suite in ("S-resolver", "S-workflow", "S-safety"):
        assert _cli(repo, package, "evidence", "add", input_value=_suite_record(rev, suite)).returncode == 0
    (package / "artifacts/manual.png").write_bytes(b"manual walkthrough image")
    pages = [_journey_record(rev, "J1-S1", run_id="page-run", artifact="artifacts/manual.png", manual_by="张三"), _journey_record(rev, "J1-S2", run_id="page-run")]
    assert _cli(repo, package, "evidence", "add", input_value=pages).returncode == 0
    _satisfy(repo, package, "TKT-01", rev)
    _satisfy(repo, package, "TKT-02", rev)
    _add_terminal_summary(repo, package, rev)
    return repo, package


def test_terminal_review_survives_docs_only_commits_but_not_runtime_ones(tmp_path: Path, monkeypatch) -> None:
    from situation import terminal_coverage_fact

    repo, package = _terminal_ready(tmp_path)
    assert terminal_coverage_fact(package).value is True
    _commit_file(repo, "docs/notes.md", "n\n")
    (package / "artifacts/extra.md").write_text("e\n", encoding="utf-8")
    _commit_path(repo, package / "artifacts/extra.md", "package only")
    assert terminal_coverage_fact(package).value is True  # Track A reviewedHead is behind HEAD, drift is non-runtime
    _commit_file(repo, "ops/deploy.yaml", "x: 1\n")
    assert terminal_coverage_fact(package).value is not True  # ops/ is runtime by default
    monkeypatch.setenv("IMPL_PACKAGE_NON_RUNTIME_PREFIXES", "ops/")
    assert terminal_coverage_fact(package).value is True  # configurable
    _commit_file(repo, "src/app.py", "v = 1\n")
    fact = terminal_coverage_fact(package)
    assert fact.value is not True


def test_gate_pass_commit_flag_commits_only_the_package_without_attribution(tmp_path: Path) -> None:
    import subprocess

    repo, package = _terminal_ready(tmp_path)
    (repo / "unrelated.txt").write_text("keep out\n", encoding="utf-8")
    rev = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True).stdout.strip()
    result = _cli(repo, package, "gate", "pass", "--comparison-commit", rev, "--reason", "ok", "--no-durable-delta-reason", "none", "--commit")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout.splitlines()[0])["packageCommit"]
    files = subprocess.run(["git", "show", "--name-only", "--format=%B", "HEAD"], cwd=repo, capture_output=True, text=True).stdout
    assert "gate.md" in files and "unrelated.txt" not in files
    assert "Co-Authored-By" not in files and "Claude" not in files
    status = subprocess.run(["git", "status", "--porcelain"], cwd=repo, capture_output=True, text=True).stdout
    assert status.strip() == "?? unrelated.txt"
    again = _cli(repo, package, "gate", "preflight")
    assert again.returncode == 0 and "已 pass" in again.stdout
