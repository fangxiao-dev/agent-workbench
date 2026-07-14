#!/usr/bin/env python3
"""Load and validate Stable Docs Backfill repository configuration."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


CONFIG_NAME = ".stable-docs-backfill.json"
PORTABLE_REPOSITORY_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$"
)
DANGER_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]*$")


class ConfigError(RuntimeError):
    """Raised when repository configuration cannot be trusted."""


def _require_non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"{field} must be a non-empty string")
    return value.strip()


def normalize_project_path(value: Any, field: str) -> str:
    raw = _require_non_empty_string(value, field).replace("\\", "/")
    if re.match(r"^[A-Za-z]:", raw) or raw.startswith("/") or raw.startswith("//"):
        raise ConfigError(f"{field} must be project-relative: {value}")
    path = PurePosixPath(raw)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise ConfigError(f"{field} must not contain empty, dot, or parent segments: {value}")
    return path.as_posix()


def resolve_project_path(project_root: Path, relative_path: str) -> Path:
    root = project_root.resolve()
    candidate = (root / relative_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise ConfigError(f"configured path escapes project root: {relative_path}") from error
    return candidate


def _validate_string_list(value: Any, field: str, *, paths: bool = False) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError(f"{field} must be an array")
    result: list[str] = []
    for index, item in enumerate(value):
        normalized = (
            normalize_project_path(item, f"{field}[{index}]")
            if paths
            else _require_non_empty_string(item, f"{field}[{index}]")
        )
        if normalized in result:
            raise ConfigError(f"{field} contains duplicate value: {normalized}")
        result.append(normalized)
    return result


def validate_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigError("configuration must contain a JSON object")
    allowed = {
        "schemaVersion",
        "repository",
        "canonicalDocs",
        "pendingPath",
        "compactionPath",
        "statePath",
        "implementationsPath",
        "excludePaths",
        "dangerRules",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError("unknown configuration fields: " + ", ".join(unknown))
    if payload.get("schemaVersion") != 1:
        raise ConfigError("schemaVersion must equal 1")

    repository = payload.get("repository")
    if repository is not None:
        repository = _require_non_empty_string(repository, "repository").lower()
        if PORTABLE_REPOSITORY_RE.fullmatch(repository) is None:
            raise ConfigError("repository must use portable owner/repository form")

    raw_homes = payload.get("canonicalDocs")
    if not isinstance(raw_homes, list) or not raw_homes:
        raise ConfigError("canonicalDocs must be a non-empty array")
    homes: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for index, raw_home in enumerate(raw_homes):
        field = f"canonicalDocs[{index}]"
        if not isinstance(raw_home, dict):
            raise ConfigError(f"{field} must be an object")
        unknown_home = sorted(set(raw_home) - {"path", "role", "owner", "moduleInventory"})
        if unknown_home:
            raise ConfigError(f"{field} has unknown fields: " + ", ".join(unknown_home))
        path = normalize_project_path(raw_home.get("path"), f"{field}.path")
        if path in seen_paths:
            raise ConfigError(f"canonicalDocs contains duplicate path: {path}")
        seen_paths.add(path)
        module_inventory = raw_home.get("moduleInventory", False)
        if not isinstance(module_inventory, bool):
            raise ConfigError(f"{field}.moduleInventory must be a boolean")
        homes.append(
            {
                "path": path,
                "role": _require_non_empty_string(raw_home.get("role"), f"{field}.role"),
                "owner": _require_non_empty_string(raw_home.get("owner"), f"{field}.owner"),
                "moduleInventory": module_inventory,
            }
        )
    if sum(1 for home in homes if home["moduleInventory"]) > 1:
        raise ConfigError("at most one canonicalDocs entry may set moduleInventory")

    danger_rules = payload.get("dangerRules")
    if not isinstance(danger_rules, list):
        raise ConfigError("dangerRules must be an array")
    normalized_rules: list[dict[str, Any]] = []
    seen_rule_ids: set[str] = set()
    for index, raw_rule in enumerate(danger_rules):
        field = f"dangerRules[{index}]"
        if not isinstance(raw_rule, dict):
            raise ConfigError(f"{field} must be an object")
        unknown_rule = sorted(set(raw_rule) - {"id", "description", "literals", "paths"})
        if unknown_rule:
            raise ConfigError(f"{field} has unknown fields: " + ", ".join(unknown_rule))
        rule_id = _require_non_empty_string(raw_rule.get("id"), f"{field}.id")
        if DANGER_ID_RE.fullmatch(rule_id) is None:
            raise ConfigError(f"{field}.id must use lowercase kebab-case")
        if rule_id in seen_rule_ids:
            raise ConfigError(f"dangerRules contains duplicate id: {rule_id}")
        seen_rule_ids.add(rule_id)
        literals = _validate_string_list(raw_rule.get("literals"), f"{field}.literals")
        paths = _validate_string_list(raw_rule.get("paths"), f"{field}.paths", paths=True)
        if not literals or not paths:
            raise ConfigError(f"{field}.literals and {field}.paths must be non-empty")
        normalized_rules.append(
            {
                "id": rule_id,
                "description": _require_non_empty_string(
                    raw_rule.get("description"), f"{field}.description"
                ),
                "literals": literals,
                "paths": paths,
            }
        )

    return {
        "schemaVersion": 1,
        "repository": repository,
        "canonicalDocs": homes,
        "pendingPath": normalize_project_path(payload.get("pendingPath"), "pendingPath"),
        "compactionPath": normalize_project_path(
            payload.get("compactionPath"), "compactionPath"
        ),
        "statePath": normalize_project_path(payload.get("statePath"), "statePath"),
        "implementationsPath": normalize_project_path(
            payload.get("implementationsPath"), "implementationsPath"
        ),
        "excludePaths": _validate_string_list(
            payload.get("excludePaths", []), "excludePaths", paths=True
        ),
        "dangerRules": normalized_rules,
    }


def load_repository_config(
    project_root: Path | str, config_path: Path | str | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    project = Path(project_root).resolve()
    selected = (
        Path(config_path).expanduser().resolve()
        if config_path is not None
        else project / CONFIG_NAME
    )
    if not selected.is_file():
        source = "explicit --config" if config_path is not None else f"project-root {CONFIG_NAME}"
        raise ConfigError(f"missing configuration from {source}: {selected}")
    try:
        raw = selected.read_bytes()
        payload = json.loads(raw.decode("utf-8"))
    except OSError as error:
        raise ConfigError(f"unable to read configuration: {selected}") from error
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ConfigError(f"configuration must be valid UTF-8 JSON: {selected}") from error
    config = validate_config(payload)
    metadata = {
        "source": "explicit" if config_path is not None else "project-root",
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    return config, metadata


def load_plugin_identity(plugin_root: Path | str) -> dict[str, str]:
    root = Path(plugin_root).resolve()
    manifest_path = root / ".codex-plugin" / "plugin.json"
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ConfigError(f"unable to read Plugin manifest: {manifest_path}") from error
    if not isinstance(payload, dict):
        raise ConfigError("Plugin manifest must contain a JSON object")
    name = _require_non_empty_string(payload.get("name"), "plugin.json name")
    version = _require_non_empty_string(payload.get("version"), "plugin.json version")
    return {"plugin": name, "version": version}
