from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SITUATION_CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/situation.py"
STATE_CLI = ROOT / "plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py"
SOURCE_FIXTURE = ROOT / "tests/fixtures/impl-package-ticket-first"
sys.path.insert(0, str(ROOT / "plugin-marketplace/plugins/impl-package/scripts"))
from impl_package_runtime import engine  # noqa: E402


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
    return result.stdout.strip()


def _state_cli(
    repo: Path,
    package: Path,
    *args: str,
    ok: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        [sys.executable, str(STATE_CLI), "--package", str(package), "--no-situation", *args],
        cwd=repo,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if ok:
        assert result.returncode == 0, result.stderr or result.stdout
    return result


def _make_ready_package(tmp_path: Path) -> tuple[Path, Path]:
    repo = tmp_path / "repo"
    package = repo / "docs/implementations/20260821-live-reference-consumer"
    (package / "tickets").mkdir(parents=True)
    shutil.copy2(SOURCE_FIXTURE / "ticket-only-plan.md", package / "plan.md")
    shutil.copytree(SOURCE_FIXTURE / "evidence", repo / "evidence")
    for source in (SOURCE_FIXTURE / "tickets").glob("*.md"):
        shutil.copy2(source, package / "tickets" / source.name)
    (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
    (package / "spec.md").write_text(
        "# Spec\n\nReference: docs/implementations/260801-live-contract/\n",
        encoding="utf-8",
    )
    (repo / "docs/implementations/retired.json").write_text(
        '{"version":1,"packages":[]}\n',
        encoding="utf-8",
    )

    _git(repo, "init")
    _git(repo, "config", "user.email", "live-reference@example.com")
    _git(repo, "config", "user.name", "Live reference fixture")
    _git(repo, "add", ".")
    _git(repo, "commit", "-m", "live reference fixture")

    engine.command_init(
        package,
        "initial",
        "docs/implementations/20260821-live-reference-consumer/plan.md",
    )
    revision = _git(repo, "rev-parse", "HEAD")
    index = json.loads((SOURCE_FIXTURE / "evidence/index.json").read_text(encoding="utf-8"))
    evidence_index: dict[str, dict[str, list[dict[str, str]]]] = {}
    for source in index["records"]:
        record = dict(source)
        record.update({"revision": revision, "environment": "test", "artifact": source["artifact"]})
        evidence_index.setdefault(record["ticket"], {}).setdefault(record["claim"], []).append(record)
    state_path = package / ".impl-package/state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    state["evidenceIndex"] = evidence_index
    state["tickets"] = {
        ticket: {"state": "SATISFIED", "acceptance": {"revision": revision, "environment": "test"}}
        for ticket in state["tickets"]
    }
    state_path.write_text(json.dumps(state), encoding="utf-8")
    return repo, package


def test_live_reference_renders_and_rejects_pass_gate() -> None:
    with tempfile.TemporaryDirectory() as temporary:
        _test_live_reference_renders_and_rejects_pass_gate(Path(temporary))


def _test_live_reference_renders_and_rejects_pass_gate(tmp_path: Path) -> None:
    repo, package = _make_ready_package(tmp_path)

    rendered_process = subprocess.run(
        [sys.executable, str(SITUATION_CLI), "render", "--package", str(package), "--json"],
        cwd=repo,
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert rendered_process.returncode == 0, rendered_process.stderr
    rendered = json.loads(rendered_process.stdout)
    fact = rendered["selected"]["when"]["package.references.live_package"]
    assert rendered["selected"]["slug"] == "package.record.live-package-reference"
    assert fact["value"] is True
    assert fact["status"] == "known"
    assert "spec.md: docs/implementations/260801-live-contract/" in fact["reason"]
    print(
        "RENDER_OUTPUT="
        + json.dumps(
            {
                "digest": rendered["digest"],
                "selected": rendered["selected"]["slug"],
                "fact": fact,
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    head = _git(repo, "rev-parse", "HEAD")
    rejected = _state_cli(
        repo,
        package,
        "gate",
        "pass",
        "--comparison-commit",
        head,
        "--reason",
        "live reference fixture",
        "--no-durable-delta-reason",
        "fixture",
        "--environment",
        "test",
        ok=False,
    )
    assert rejected.returncode != 0
    assert "pass Gate rejected" in rejected.stderr
    assert "spec.md: docs/implementations/260801-live-contract/" in rejected.stderr
    assert "/impl-package:backfill-stable-docs" in rejected.stderr
    print("GATE_OUTPUT=" + rejected.stderr.strip())
