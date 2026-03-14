"""Manifest loading and validation helpers for simplified personal bootstrap flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


SUPPORTED_AGENTS = ("codex", "claude", "gemini")
SUPPORTED_SCOPES = ("project", "global")
SUPPORTED_MODES = ("sync", "link")
DEFAULT_VERIFY_CHECKS = ["templates", "project_skills", "global_skills", "shared_assets", "plan_tracker"]


@dataclass
class SkillConfig:
    """A single skill installation rule from the consumer manifest."""

    name: str
    scope: str = "project"
    mode: str = "sync"


@dataclass
class AgentAssetsManifest:
    """Structured manifest used to apply, verify, pull, and push personal assets."""

    source_repo: Path
    agents: list[str]
    skills: list[SkillConfig]
    templates: list[str] = field(default_factory=list)
    verify: list[str] = field(default_factory=lambda: list(DEFAULT_VERIFY_CHECKS))
    task_prefix: str | None = None


def load_manifest(path: Path) -> AgentAssetsManifest:
    """Load and validate a consumer manifest from YAML."""
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return manifest_from_data(data, base_dir=path.parent)


def manifest_from_data(data: dict[str, Any], base_dir: Path) -> AgentAssetsManifest:
    """Validate raw YAML data and return a normalized manifest."""
    source_repo_raw = str(data.get("source_repo", "")).strip()
    if not source_repo_raw:
        raise ValueError("Missing required manifest field: source_repo")
    if source_repo_raw.startswith(("http://", "https://", "git@")):
        raise ValueError("source_repo URL support is not implemented yet; use a local path for now")
    source_repo = (base_dir / source_repo_raw).resolve() if not Path(source_repo_raw).is_absolute() else Path(source_repo_raw)
    if not source_repo.exists():
        raise ValueError(f"source_repo does not exist: {source_repo}")

    agents = _normalize_agent_list(data.get("agents"), field_name="agents")
    templates = _normalize_agent_list(data.get("templates"), field_name="templates", default=agents)
    verify = _normalize_string_list(data.get("verify"), field_name="verify", default=list(DEFAULT_VERIFY_CHECKS))
    if "third_party_skills" in data:
        raise ValueError("Manifest field third_party_skills is no longer supported; use a separate open-skills list file and script instead")
    task_prefix_raw = str(data.get("task_prefix", "")).strip()
    task_prefix = task_prefix_raw or None

    raw_skills = data.get("skills")
    if not isinstance(raw_skills, list) or not raw_skills:
        raise ValueError("Missing required manifest field: skills")

    skills: list[SkillConfig] = []
    for item in raw_skills:
        if isinstance(item, str):
            name = item.strip()
            if not name:
                raise ValueError("Skill names must not be empty")
            skills.append(SkillConfig(name=name))
            continue
        if not isinstance(item, dict):
            raise ValueError("Each item in skills must be either a string or an object")
        name = str(item.get("name", "")).strip()
        if not name:
            raise ValueError("Each skill must define a name")
        scope = str(item.get("scope", "project")).strip().lower() or "project"
        if scope not in SUPPORTED_SCOPES:
            raise ValueError(f"Unsupported scope '{scope}' for skill '{name}'")
        mode = str(item.get("mode", "sync")).strip().lower() or "sync"
        if mode not in SUPPORTED_MODES:
            raise ValueError(f"Unsupported mode '{mode}' for skill '{name}'")
        skills.append(SkillConfig(name=name, scope=scope, mode=mode))

    return AgentAssetsManifest(
        source_repo=source_repo,
        agents=agents,
        skills=skills,
        templates=templates,
        verify=verify,
        task_prefix=task_prefix,
    )


def _normalize_agent_list(value: Any, field_name: str, default: list[str] | None = None) -> list[str]:
    """Normalize an agent list and enforce supported values."""
    if value is None:
        agents = list(default or [])
    elif isinstance(value, list):
        agents = [str(item).strip().lower() for item in value if str(item).strip()]
    else:
        raise ValueError(f"Manifest field {field_name} must be a list when provided")
    if not agents:
        raise ValueError(f"Missing required manifest field: {field_name}")
    unsupported = [agent for agent in agents if agent not in SUPPORTED_AGENTS]
    if unsupported:
        raise ValueError(f"Unsupported agent(s) in {field_name}: {', '.join(unsupported)}")
    return agents


def _normalize_string_list(value: Any, field_name: str, default: list[str]) -> list[str]:
    """Normalize a generic string list with a default fallback."""
    if value is None:
        return list(default)
    if not isinstance(value, list):
        raise ValueError(f"Manifest field {field_name} must be a list when provided")
    return [str(item).strip() for item in value if str(item).strip()]
