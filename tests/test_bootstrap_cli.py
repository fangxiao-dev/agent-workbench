"""Integration tests for the simplified standalone agent-workbench bootstrap CLI."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args: str, cwd: Path | None = None, env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run the bootstrap CLI against the local source tree."""
    merged_env = os.environ.copy()
    existing = merged_env.get("PYTHONPATH", "")
    merged_env["PYTHONPATH"] = str(REPO_ROOT / "src") + (os.pathsep + existing if existing else "")
    if env:
        merged_env.update(env)
    return subprocess.run(
        [sys.executable, "-m", "agent_workbench.cli", *args],
        cwd=str(cwd or REPO_ROOT),
        env=merged_env,
        capture_output=True,
        text=True,
        check=False,
    )


def create_source_repo(root: Path) -> Path:
    """Create a minimal agent-workbench source repository for sync tests."""
    (root / "skills" / "first_party" / "demo-skill").mkdir(parents=True)
    (root / "skills" / "first_party" / "demo-skill" / "SKILL.md").write_text("---\nname: demo-skill\n---\n", encoding="utf-8")
    (root / "skills" / "first_party" / "agent-workbench-manager").mkdir(parents=True)
    (root / "skills" / "first_party" / "agent-workbench-manager" / "SKILL.md").write_text("---\nname: agent-workbench-manager\n---\n", encoding="utf-8")
    (root / "core" / "scripts").mkdir(parents=True)
    (root / "core" / "scripts" / "plan_tracker.py").write_text(
        '"""Minimal plan tracker smoke target."""\nimport sys\nif __name__ == "__main__":\n    cmd = sys.argv[1] if len(sys.argv) > 1 else ""\n    if cmd == "list":\n        print("list ok")\n    elif cmd == "quick-plan":\n        print("quick-plan ok")\n    else:\n        print("unknown")\n',
        encoding="utf-8",
    )
    return root


def write_manifest(target: Path, source_repo: Path) -> Path:
    """Write a minimal consumer manifest using defaults for project/sync."""
    manifest = {
        "project_name": "demo-app",
        "source_repo": str(source_repo),
        "agents": ["codex", "claude"],
        "skills": [
            "agent-workbench-manager",
            "demo-skill",
            {"name": "demo-skill", "scope": "global"},
        ],
        "templates": ["codex", "claude"],
        "verify": ["templates", "project_skills", "global_skills", "plan_tracker"],
    }
    path = target / "agent_assets.yaml"
    path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return path


def test_apply_installs_project_and_global_assets_and_updates_gitignore(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    write_manifest(business_repo, source_repo)
    fake_home = tmp_path / "home"

    result = run_cli("apply", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    assert result.returncode == 0, result.stderr
    assert (business_repo / ".agents" / "skills" / "agent-workbench-manager" / "SKILL.md").exists()
    assert (business_repo / ".agents" / "skills" / "demo-skill" / "SKILL.md").exists()
    assert (business_repo / ".claude" / "skills" / "demo-skill" / "SKILL.md").exists()
    assert (fake_home / ".claude" / "skills" / "demo-skill" / "SKILL.md").exists()
    assert (fake_home / ".codex" / "skills" / "demo-skill" / "SKILL.md").exists()
    gitignore = (business_repo / ".gitignore").read_text(encoding="utf-8")
    assert ".agent-workbench/" in gitignore
    assert "AGENTS.md" in gitignore


def test_verify_reports_pass_for_installed_assets_and_plan_tracker(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    write_manifest(business_repo, source_repo)
    fake_home = tmp_path / "home"
    apply_result = run_cli("apply", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})
    assert apply_result.returncode == 0, apply_result.stderr

    result = run_cli("verify", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    assert result.returncode == 0, result.stderr
    assert "PASS template:AGENTS.md" in result.stdout
    assert "PASS template:CLAUDE.md" in result.stdout
    assert "PASS plan_tracker:list" in result.stdout
    assert "PASS global_skill:claude:demo-skill" in result.stdout


def test_pull_refreshes_business_repo_from_source_repo(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    write_manifest(business_repo, source_repo)
    fake_home = tmp_path / "home"
    run_cli("apply", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    source_skill = source_repo / "skills" / "first_party" / "demo-skill" / "SKILL.md"
    source_skill.write_text("updated from source\\n", encoding="utf-8")

    result = run_cli("pull", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    assert result.returncode == 0, result.stderr
    assert "updated from source" in (business_repo / ".agents" / "skills" / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")


def test_push_syncs_selected_project_skill_back_to_source_repo(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    write_manifest(business_repo, source_repo)
    fake_home = tmp_path / "home"
    run_cli("apply", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    business_skill = business_repo / ".agents" / "skills" / "demo-skill" / "SKILL.md"
    business_skill.write_text("changed in project\\n", encoding="utf-8")

    result = run_cli("push", "--target", str(business_repo), "--skill", "demo-skill", env={"AGENT_ASSETS_HOME": str(fake_home)})

    assert result.returncode == 0, result.stderr
    assert "changed in project" in (source_repo / "skills" / "first_party" / "demo-skill" / "SKILL.md").read_text(encoding="utf-8")


def test_verify_fails_when_required_global_skill_is_missing(tmp_path: Path) -> None:
    source_repo = create_source_repo(tmp_path / "source-repo")
    business_repo = tmp_path / "business-repo"
    business_repo.mkdir()
    write_manifest(business_repo, source_repo)
    fake_home = tmp_path / "home"
    run_cli("apply", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})
    missing_global = fake_home / ".claude" / "skills" / "demo-skill"
    for child in sorted(missing_global.rglob("*"), reverse=True):
        if child.is_file():
            child.unlink()
    if missing_global.exists():
        missing_global.rmdir()

    result = run_cli("verify", "--target", str(business_repo), env={"AGENT_ASSETS_HOME": str(fake_home)})

    assert result.returncode != 0
    assert "FAIL global_skill:claude:demo-skill" in result.stdout
