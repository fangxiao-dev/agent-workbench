#!/usr/bin/env python3
"""Load Stable Docs Backfill configuration with explicit repository-relative paths."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


CONFIG_NAME = ".stable-docs-backfill.json"
PORTABLE_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


class ConfigError(RuntimeError):
    pass


def _text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string")
    return value.strip()


def normalize_project_path(value: Any, field: str) -> str:
    raw = _text(value, field).replace("\\", "/")
    path = PurePosixPath(raw)
    if path.is_absolute() or re.match(r"^[A-Za-z]:", raw) or ".." in path.parts or str(path) in {"", "."}:
        raise ConfigError(f"{field} must be a repository-relative path: {value}")
    if any(character in raw for character in "*?["):
        raise ConfigError(f"{field} must be explicit, not a wildcard: {value}")
    return path.as_posix()


def resolve_project_path(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / Path(*PurePosixPath(relative_path).parts)).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ConfigError(f"configured path escapes repository: {relative_path}") from error
    return candidate


def _paths(value: Any, field: str, *, allow_empty: bool = False) -> list[str]:
    if not isinstance(value, list) or (not allow_empty and not value):
        raise ConfigError(f"{field} must be {'an' if allow_empty else 'a non-empty'} array")
    result = [normalize_project_path(item, f"{field}[{index}]") for index, item in enumerate(value)]
    if len(result) != len(set(result)):
        raise ConfigError(f"{field} contains duplicate paths")
    return result


def _ignore_entries(value: Any) -> list[dict[str, str]]:
    if not isinstance(value, list):
        raise ConfigError("ignore must be an array")
    result: list[dict[str, str]] = []
    for index, item in enumerate(value):
        if not isinstance(item, dict) or set(item) != {"path", "owner", "reason"}:
            raise ConfigError(f"ignore[{index}] must contain path, owner, and reason")
        row = {
            "path": normalize_project_path(item["path"], f"ignore[{index}].path"),
            "owner": _text(item["owner"], f"ignore[{index}].owner"),
            "reason": _text(item["reason"], f"ignore[{index}].reason"),
        }
        if any(existing["path"] == row["path"] for existing in result):
            raise ConfigError("ignore contains duplicate paths")
        result.append(row)
    return result


def validate_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigError("configuration must contain a JSON object")
    allowed = {"repository", "targetBranch", "implementations", "stableDocs", "ignore", "records"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError("unknown configuration fields: " + ", ".join(unknown))
    repository = _text(payload.get("repository"), "repository").lower()
    if PORTABLE_REPOSITORY_RE.fullmatch(repository) is None:
        raise ConfigError("repository must use owner/repository form")
    target = _text(payload.get("targetBranch"), "targetBranch")
    if target.startswith("-") or any(character.isspace() for character in target):
        raise ConfigError("targetBranch must be a local Git revision")
    stable = payload.get("stableDocs")
    if not isinstance(stable, dict) or set(stable) - {"systemKnowledge", "contextKnowledge", "moduleKnowledge"}:
        raise ConfigError("stableDocs has invalid fields")
    records = payload.get("records")
    if not isinstance(records, dict) or set(records) != {"pending", "done", "reports"}:
        raise ConfigError("records must contain pending, done, and reports")
    ignore = payload.get("ignore", [])
    return {
        "repository": repository,
        "targetBranch": target,
        "implementations": _paths(payload.get("implementations"), "implementations"),
        "stableDocs": {
            "systemKnowledge": _paths(stable.get("systemKnowledge"), "stableDocs.systemKnowledge"),
            "contextKnowledge": _paths(stable.get("contextKnowledge", []), "stableDocs.contextKnowledge", allow_empty=True),
            "moduleKnowledge": _paths(stable.get("moduleKnowledge"), "stableDocs.moduleKnowledge"),
        },
        "ignore": _ignore_entries(ignore),
        "records": {
            "pending": _paths(records.get("pending"), "records.pending", allow_empty=True),
            "done": normalize_project_path(records.get("done"), "records.done"),
            "reports": normalize_project_path(records.get("reports"), "records.reports"),
        },
    }


def load_repository_config(project_root: Path | str, config_path: Path | str | None = None) -> tuple[dict[str, Any], dict[str, str]]:
    project = Path(project_root).resolve()
    selected = (project / CONFIG_NAME) if config_path is None else Path(config_path)
    if not selected.is_absolute():
        selected = project / selected
    selected = selected.resolve()
    try:
        relative = selected.relative_to(project).as_posix()
    except ValueError as error:
        raise ConfigError("configuration must be inside the repository") from error
    try:
        payload = json.loads(selected.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError) as error:
        raise ConfigError(f"configuration must be readable UTF-8 JSON: {relative}") from error
    return validate_config(payload), {"source": relative}


def resolve_target_branch(project_root: Path, target_branch: str) -> str:
    result = subprocess.run(["git", "rev-parse", "--verify", f"{target_branch}^{{commit}}"], cwd=project_root, capture_output=True, text=True, check=False)
    if result.returncode:
        raise ConfigError(f"targetBranch is not a local Git commit: {target_branch}")
    return result.stdout.strip()


def expand_roots(project_root: Path, paths: list[str]) -> list[Path]:
    return [resolve_project_path(project_root, value) for value in paths if resolve_project_path(project_root, value).is_dir()]


def expand_targets(project_root: Path, paths: list[str]) -> list[Path]:
    return [resolve_project_path(project_root, value) for value in paths if resolve_project_path(project_root, value).exists()]


def path_matches_ignore(relative_path: str, ignored: list[dict[str, str]]) -> dict[str, str] | None:
    candidate = relative_path.replace("\\", "/")
    return next((item for item in ignored if candidate == item["path"] or candidate.startswith(item["path"].rstrip("/") + "/")), None)


def discover_pending_paths(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    result = []
    for value in config["records"]["pending"]:
        result.append({"pendingPath": value, "status": "ok" if resolve_project_path(project_root, value).is_file() else "missing"})
    return result
