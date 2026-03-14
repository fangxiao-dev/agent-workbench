"""Filesystem install, verify, pull, and push logic for personal agent-workbench usage."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from agent_workbench.manifest import AgentAssetsManifest, SkillConfig
from agent_workbench.rendering import render_agent_entry


PROJECT_SKILL_ROOTS = {
    "codex": [Path(".agents") / "skills"],
    "claude": [Path(".claude") / "skills"],
    "gemini": [Path(".gemini") / "skills"],
}
GLOBAL_SKILL_ROOTS = {
    "codex": ".codex/skills",
    "claude": ".claude/skills",
    "gemini": ".gemini/skills",
}
GITIGNORE_BLOCK = [
    "# agent-workbench",
    ".agent-workbench/",
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".agents/",
    ".claude/",
    ".codex/",
    ".gemini/",
]


@dataclass
class VerifyResult:
    """A single smoke-check result emitted by `bootstrap verify`."""

    status: str
    name: str
    detail: str = ""

    def render(self) -> str:
        """Return a human-readable verification line."""
        suffix = f" {self.detail}" if self.detail else ""
        return f"{self.status} {self.name}{suffix}"


def apply_manifest(target: Path, manifest: AgentAssetsManifest) -> list[str]:
    """Install project and global assets for a business repository."""
    actions: list[str] = []
    target.mkdir(parents=True, exist_ok=True)
    _ensure_gitignore(target)
    actions.append("updated .gitignore")

    _install_templates(target, manifest)
    actions.extend(f"rendered {name}" for name in manifest.templates)

    _install_plan_tracker(target, manifest)
    actions.append("synced scripts/plan_tracker.py")

    for skill in manifest.skills:
        destinations = _destinations_for_skill(skill, manifest, target, _home_dir())
        source = _source_skill_path(manifest, skill)
        for destination in destinations:
            _install_path(source, destination, mode=skill.mode)
            actions.append(f"installed {skill.scope}:{destination}")
    return actions


def pull_manifest(target: Path, manifest: AgentAssetsManifest) -> list[str]:
    """Refresh installed assets from the source repository."""
    return apply_manifest(target, manifest)


def push_manifest(target: Path, manifest: AgentAssetsManifest, skill_names: list[str] | None = None) -> list[str]:
    """Push selected skill changes back to the personal tool repository."""
    selected = {name.strip() for name in (skill_names or []) if name.strip()}
    actions: list[str] = []
    chosen_skills: dict[str, SkillConfig] = {}
    for skill in manifest.skills:
        if selected and skill.name not in selected:
            continue
        current = chosen_skills.get(skill.name)
        if current is None or (current.scope == "global" and skill.scope == "project"):
            chosen_skills[skill.name] = skill
    for skill in chosen_skills.values():
        source_candidate = _editable_skill_source(skill, manifest, target, _home_dir())
        if source_candidate is None or not source_candidate.exists():
            continue
        destination = _source_skill_path(manifest, skill)
        _copy_tree(source_candidate, destination)
        actions.append(f"pushed {skill.name} -> {destination}")
    return actions


def verify_manifest(target: Path, manifest: AgentAssetsManifest) -> list[VerifyResult]:
    """Run bootstrap smoke checks and collect PASS/FAIL/SKIP results."""
    results: list[VerifyResult] = []
    home = _home_dir()

    if "templates" in manifest.verify:
        for agent in manifest.templates:
            entry_path, _ = render_agent_entry(agent, manifest)
            exists = (target / entry_path).exists()
            results.append(VerifyResult(status="PASS" if exists else "FAIL", name=f"template:{entry_path.name}"))

    if "project_skills" in manifest.verify:
        for skill in manifest.skills:
            if skill.scope != "project":
                continue
            for agent, roots in PROJECT_SKILL_ROOTS.items():
                if agent not in manifest.agents:
                    continue
                for root in roots:
                    destination = target / root / skill.name
                    results.append(VerifyResult(status="PASS" if destination.exists() else "FAIL", name=f"project_skill:{agent}:{skill.name}"))

    if "global_skills" in manifest.verify:
        for skill in manifest.skills:
            if skill.scope != "global":
                continue
            for agent in manifest.agents:
                destination = home / GLOBAL_SKILL_ROOTS[agent] / skill.name
                results.append(VerifyResult(status="PASS" if destination.exists() else "FAIL", name=f"global_skill:{agent}:{skill.name}"))

    if "plan_tracker" in manifest.verify:
        tracker = target / "scripts" / "plan_tracker.py"
        if tracker.exists():
            command = [sys.executable, str(tracker), "list"]
            completed = subprocess.run(command, cwd=str(target), capture_output=True, text=True, check=False)
            results.append(VerifyResult(status="PASS" if completed.returncode == 0 else "FAIL", name="plan_tracker:list", detail=completed.stdout.strip() or completed.stderr.strip()))
        else:
            results.append(VerifyResult(status="FAIL", name="plan_tracker:list", detail="missing scripts/plan_tracker.py"))

    return results


def _install_templates(target: Path, manifest: AgentAssetsManifest) -> None:
    """Render selected agent entry files into the business repository."""
    for agent in manifest.templates:
        relative_path, content = render_agent_entry(agent, manifest)
        destination = target / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(content, encoding="utf-8")


def _install_plan_tracker(target: Path, manifest: AgentAssetsManifest) -> None:
    """Sync the shared plan tracker script into the business repository."""
    source = manifest.source_repo / "core" / "scripts" / "plan_tracker.py"
    destination = target / "scripts" / "plan_tracker.py"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if source.exists():
        destination.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")


def _ensure_gitignore(target: Path) -> None:
    """Ensure the business repository ignores personal agent-workbench artifacts."""
    gitignore = target / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8") if gitignore.exists() else ""
    lines = existing.splitlines()
    updated = False
    for entry in GITIGNORE_BLOCK:
        if entry not in lines:
            lines.append(entry)
            updated = True
    if updated or not gitignore.exists():
        gitignore.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def _destinations_for_skill(skill: SkillConfig, manifest: AgentAssetsManifest, target: Path, home: Path) -> list[Path]:
    """Return all install destinations for a skill based on scope and agents."""
    destinations: list[Path] = []
    if skill.scope == "project":
        for agent in manifest.agents:
            for root in PROJECT_SKILL_ROOTS[agent]:
                destinations.append(target / root / skill.name)
    else:
        for agent in manifest.agents:
            destinations.append(home / GLOBAL_SKILL_ROOTS[agent] / skill.name)
    return destinations


def _editable_skill_source(skill: SkillConfig, manifest: AgentAssetsManifest, target: Path, home: Path) -> Path | None:
    """Pick the editable business-side location to push back into the source repo."""
    if skill.scope == "project":
        for agent in manifest.agents:
            for root in PROJECT_SKILL_ROOTS[agent]:
                candidate = target / root / skill.name
                if candidate.exists():
                    return candidate
        return None
    for agent in manifest.agents:
        candidate = home / GLOBAL_SKILL_ROOTS[agent] / skill.name
        if candidate.exists():
            return candidate
    return None


def _source_skill_path(manifest: AgentAssetsManifest, skill: SkillConfig) -> Path:
    """Resolve the canonical source-repo location for a first-party skill."""
    path = manifest.source_repo / "skills" / "first_party" / skill.name
    if not path.exists():
        raise ValueError(f"Missing skill in source_repo: {path}")
    return path


def _install_path(source: Path, destination: Path, mode: str) -> None:
    """Install a file or directory using sync or best-effort link mode."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if mode == "link":
        try:
            os.symlink(source, destination, target_is_directory=source.is_dir())
            return
        except OSError:
            pass
    _copy_tree(source, destination)


def _copy_tree(source: Path, destination: Path) -> None:
    """Copy a file or directory tree, replacing the previous destination."""
    if destination.exists() or destination.is_symlink():
        if destination.is_dir() and not destination.is_symlink():
            shutil.rmtree(destination)
        else:
            destination.unlink()
    if source.is_dir():
        shutil.copytree(source, destination)
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def _home_dir() -> Path:
    """Resolve the per-user global install root, allowing test overrides."""
    override = os.environ.get("AGENT_ASSETS_HOME")
    return Path(override).expanduser() if override else Path.home()
