#!/usr/bin/env python3
"""Load and validate Stable Docs Backfill repository configuration (contract 3.1)."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


CONFIG_NAME = ".stable-docs-backfill.json"
CONTRACT_VERSION = "3.1"
PORTABLE_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*/[A-Za-z0-9][A-Za-z0-9._-]*$")


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


def resolve_target_branch(project_root: Path, target_branch: str) -> str:
    """Resolve the configured target branch/revision to a commit without fetching."""
    completed = subprocess.run(
        [
            "git",
            "rev-parse",
            "--verify",
            "--end-of-options",
            target_branch,
        ],
        cwd=project_root.resolve(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if completed.returncode != 0:
        raise ConfigError(f"targetBranch does not resolve to a local Git revision: {target_branch}")
    return completed.stdout.strip()


def _validate_path_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list):
        raise ConfigError(f"{field} must be an array")
    if not allow_empty and not value:
        raise ConfigError(f"{field} must be a non-empty array")
    result: list[str] = []
    for index, item in enumerate(value):
        normalized = normalize_project_path(item, f"{field}[{index}]")
        if normalized in result:
            raise ConfigError(f"{field} contains duplicate value: {normalized}")
        result.append(normalized)
    return result


def _validate_ignore(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ConfigError("ignore must be an array")
    groups: list[dict[str, Any]] = []
    for index, raw_group in enumerate(value):
        field = f"ignore[{index}]"
        if not isinstance(raw_group, dict):
            raise ConfigError(f"{field} must be an object")
        unknown = sorted(set(raw_group) - {"paths", "owner", "reason"})
        if unknown:
            raise ConfigError(f"{field} has unknown fields: " + ", ".join(unknown))
        paths = _validate_path_list(raw_group.get("paths"), f"{field}.paths", allow_empty=False)
        owner = _require_non_empty_string(raw_group.get("owner"), f"{field}.owner")
        reason = _require_non_empty_string(raw_group.get("reason"), f"{field}.reason")
        groups.append({"paths": paths, "owner": owner, "reason": reason})
    return groups


def validate_config(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConfigError("configuration must contain a JSON object")
    allowed = {
        "contractVersion",
        "repository",
        "targetBranch",
        "implementations",
        "stableDocs",
        "ignore",
        "records",
    }
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError("unknown configuration fields: " + ", ".join(unknown))
    if payload.get("contractVersion") != CONTRACT_VERSION:
        raise ConfigError(f"contractVersion must equal {CONTRACT_VERSION!r}")

    repository = _require_non_empty_string(payload.get("repository"), "repository").lower()
    if PORTABLE_REPOSITORY_RE.fullmatch(repository) is None:
        raise ConfigError("repository must use portable owner/repository form, not a local folder name")
    target_branch = _require_non_empty_string(payload.get("targetBranch"), "targetBranch")
    if target_branch.startswith("-") or any(character.isspace() for character in target_branch):
        raise ConfigError("targetBranch must be a Git revision without whitespace or leading dash")

    implementations = _validate_path_list(
        payload.get("implementations"), "implementations", allow_empty=False
    )

    raw_stable_docs = payload.get("stableDocs")
    if not isinstance(raw_stable_docs, dict):
        raise ConfigError("stableDocs must be an object")
    unknown_stable = sorted(
        set(raw_stable_docs) - {"systemKnowledge", "contextKnowledge", "moduleKnowledge"}
    )
    if unknown_stable:
        raise ConfigError("stableDocs has unknown fields: " + ", ".join(unknown_stable))
    stable_docs = {
        "systemKnowledge": _validate_path_list(
            raw_stable_docs.get("systemKnowledge"),
            "stableDocs.systemKnowledge",
            allow_empty=False,
        ),
        "contextKnowledge": (
            _validate_path_list(
                raw_stable_docs["contextKnowledge"],
                "stableDocs.contextKnowledge",
                allow_empty=False,
            )
            if "contextKnowledge" in raw_stable_docs
            else []
        ),
        "moduleKnowledge": _validate_path_list(
            raw_stable_docs.get("moduleKnowledge"), "stableDocs.moduleKnowledge", allow_empty=False
        ),
    }

    ignore = _validate_ignore(payload.get("ignore"))

    raw_records = payload.get("records")
    if not isinstance(raw_records, dict):
        raise ConfigError("records must be an object")
    unknown_records = sorted(set(raw_records) - {"pending", "pendingOverrides", "done", "reports"})
    if unknown_records:
        raise ConfigError("records has unknown fields: " + ", ".join(unknown_records))
    if raw_records.get("pending") != "auto":
        raise ConfigError('records.pending must equal "auto"')
    raw_overrides = raw_records.get("pendingOverrides", {})
    if not isinstance(raw_overrides, dict):
        raise ConfigError("records.pendingOverrides must be an object")
    pending_overrides = {
        normalize_project_path(key, "records.pendingOverrides key"): normalize_project_path(
            value, f"records.pendingOverrides[{key}]"
        )
        for key, value in raw_overrides.items()
    }
    records = {
        "pending": "auto",
        "pendingOverrides": pending_overrides,
        "done": normalize_project_path(raw_records.get("done"), "records.done"),
        "reports": normalize_project_path(raw_records.get("reports"), "records.reports"),
    }

    return {
        "contractVersion": CONTRACT_VERSION,
        "repository": repository,
        "targetBranch": target_branch,
        "implementations": implementations,
        "stableDocs": stable_docs,
        "ignore": ignore,
        "records": records,
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


def expand_roots(project_root: Path, patterns: list[str]) -> list[Path]:
    """Expand glob patterns (relative to project_root) into existing directories, de-duplicated."""
    root = project_root.resolve()
    matches: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        candidates = root.glob(pattern) if any(ch in pattern for ch in "*?[") else [root / pattern]
        for candidate in candidates:
            if not candidate.is_dir():
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                matches.append(resolved)
    return sorted(matches)


def expand_targets(project_root: Path, patterns: list[str]) -> list[Path]:
    """Expand stable-doc patterns into existing files or directories, de-duplicated."""
    root = project_root.resolve()
    matches: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        candidates = root.glob(pattern) if any(ch in pattern for ch in "*?[") else [root / pattern]
        for candidate in candidates:
            if not candidate.exists():
                continue
            resolved = candidate.resolve()
            if resolved not in seen:
                seen.add(resolved)
                matches.append(resolved)
    return sorted(matches)


def path_matches_ignore(
    relative_path: str, ignore_groups: list[dict[str, Any]]
) -> dict[str, Any] | None:
    """Return the ignore group excluding relative_path, or None if not excluded."""
    candidate = relative_path.replace("\\", "/")
    for group in ignore_groups:
        for pattern in group["paths"]:
            if any(ch in pattern for ch in "*?["):
                if fnmatch.fnmatch(candidate, pattern):
                    return group
            elif candidate == pattern or candidate.startswith(pattern.rstrip("/") + "/"):
                return group
    return None


def discover_pending_paths(project_root: Path, config: dict[str, Any]) -> list[dict[str, Any]]:
    """Discover pending registers for configured stable-authority layers.

    System knowledge is one repo-wide owner and has a distinct ``cold-start`` status when
    its expected ``docs/_pending.md`` does not exist. Context and module roots retain the
    fail-closed ``missing``/``ambiguous`` behavior.
    """
    root = project_root.resolve()
    overrides = config["records"]["pendingOverrides"]
    entries: list[dict[str, Any]] = []

    system_patterns = config["stableDocs"]["systemKnowledge"]
    system_targets = expand_targets(root, system_patterns)
    system_root_keys = {
        target.relative_to(root).as_posix() for target in system_targets
    } | {pattern for pattern in system_patterns if not any(ch in pattern for ch in "*?[")}
    system_override_values = {overrides[key] for key in system_root_keys if key in overrides}
    expected_system_pending = "docs/_pending.md"
    if len(system_override_values) > 1:
        entries.append(
            {
                "stableDocsLayer": "systemKnowledge",
                "stableDocsRoots": system_patterns,
                "pendingPath": None,
                "expectedPendingPath": None,
                "status": "ambiguous",
            }
        )
    else:
        system_candidates: set[Path] = set()
        system_has_noncanonical_candidate = False
        if system_override_values:
            expected_system_pending = next(iter(system_override_values))
            override_path = resolve_project_path(root, expected_system_pending)
            if override_path.is_file():
                system_candidates.add(override_path)
        else:
            conventional = resolve_project_path(root, expected_system_pending)
            if conventional.is_file():
                system_candidates.add(conventional)
            for target in system_targets:
                base = target if target.is_dir() else target.parent
                for candidate in (base / "_pending.md", base.parent / "_pending.md"):
                    try:
                        candidate.resolve().relative_to(root)
                    except ValueError:
                        continue
                    if candidate.is_file():
                        resolved_candidate = candidate.resolve()
                        system_candidates.add(resolved_candidate)
                        if resolved_candidate != conventional:
                            system_has_noncanonical_candidate = True
        if len(system_candidates) == 1 and not system_has_noncanonical_candidate:
            pending_path = next(iter(system_candidates)).relative_to(root).as_posix()
            entries.append(
                {
                    "stableDocsLayer": "systemKnowledge",
                    "stableDocsRoots": system_patterns,
                    "pendingPath": pending_path,
                    "expectedPendingPath": pending_path,
                    "status": "ok",
                }
            )
        elif len(system_candidates) == 0:
            entries.append(
                {
                    "stableDocsLayer": "systemKnowledge",
                    "stableDocsRoots": system_patterns,
                    "pendingPath": None,
                    "expectedPendingPath": expected_system_pending,
                    "status": "cold-start",
                }
            )
        else:
            entries.append(
                {
                    "stableDocsLayer": "systemKnowledge",
                    "stableDocsRoots": system_patterns,
                    "pendingPath": None,
                    "expectedPendingPath": expected_system_pending,
                    "status": "ambiguous",
                }
            )

    for layer in ("contextKnowledge", "moduleKnowledge"):
        for stable_root in expand_roots(root, config["stableDocs"][layer]):
            relative_stable_root = stable_root.relative_to(root).as_posix()
            if relative_stable_root in overrides:
                override_relative = overrides[relative_stable_root]
                override_path = resolve_project_path(root, override_relative)
                entries.append(
                    {
                        "stableDocsLayer": layer,
                        "stableDocsRoots": [relative_stable_root],
                        "pendingPath": override_relative if override_path.is_file() else None,
                        "expectedPendingPath": override_relative,
                        "status": "ok" if override_path.is_file() else "missing",
                    }
                )
                continue
            same_level = stable_root / "_pending.md"
            parent_level = stable_root.parent / "_pending.md"
            candidates = [path for path in (same_level, parent_level) if path.is_file()]
            if len(candidates) == 1:
                pending_path = candidates[0].relative_to(root).as_posix()
                entries.append(
                    {
                        "stableDocsLayer": layer,
                        "stableDocsRoots": [relative_stable_root],
                        "pendingPath": pending_path,
                        "expectedPendingPath": pending_path,
                        "status": "ok",
                    }
                )
            else:
                entries.append(
                    {
                        "stableDocsLayer": layer,
                        "stableDocsRoots": [relative_stable_root],
                        "pendingPath": None,
                        "expectedPendingPath": None,
                        "status": "missing" if not candidates else "ambiguous",
                    }
                )
    return entries
