#!/usr/bin/env python3
"""Load Stable Docs Backfill configuration with explicit repository-relative paths."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any


CONFIG_NAME = ".stable-docs-backfill.json"


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
    if value is None and allow_empty:
        return []
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
    allowed = {"targetBranch", "implementations", "stableDocs", "ignore", "records"}
    unknown = sorted(set(payload) - allowed)
    if unknown:
        raise ConfigError("unknown configuration fields: " + ", ".join(unknown))
    target = _text(payload.get("targetBranch"), "targetBranch")
    if target.startswith("-") or any(character.isspace() for character in target):
        raise ConfigError("targetBranch must be a local Git revision")
    stable = payload.get("stableDocs")
    if not isinstance(stable, dict) or set(stable) - {"systemKnowledge", "contextKnowledge", "moduleKnowledge"}:
        raise ConfigError("stableDocs has invalid fields")
    records = payload.get("records")
    if not isinstance(records, dict):
        raise ConfigError("records must be an object")
    allowed_records = {"pending", "done"}
    unknown_records = sorted(set(records) - allowed_records)
    if unknown_records:
        raise ConfigError("unknown records fields: " + ", ".join(unknown_records))
    if "done" not in records:
        raise ConfigError("records must contain done")
    ignore = payload.get("ignore", [])
    result = {
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
        },
    }
    return result


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


def _normalize_commit(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text or any(character.isspace() for character in text):
        return None
    return text


def commits_match(left: str | None, right: str | None) -> bool:
    a = _normalize_commit(left)
    b = _normalize_commit(right)
    if a is None or b is None:
        return False
    return a == b or a.startswith(b) or b.startswith(a)


def load_done_records(project_root: Path, config: dict[str, Any]) -> dict[str, Any]:
    """Load records.done as the sole disposition ledger for already-handled deltas.

    Minimal item fields used for gap-catching dedup:
    - id (preferred) or packagePath + deltaId
    - comparisonCommit (required for commit-scoped dedup)
    Extra fields are preserved for human audit but ignored by matching.
    """
    relative = config["records"]["done"]
    path = resolve_project_path(project_root, relative)
    if not path.is_file():
        return {"path": relative, "status": "missing", "items": [], "itemCount": 0}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {"path": relative, "status": "invalid", "items": [], "itemCount": 0, "reason": "done record is not readable UTF-8 JSON"}

    raw_items: list[Any]
    if isinstance(payload, list):
        raw_items = payload
    elif isinstance(payload, dict) and isinstance(payload.get("items"), list):
        raw_items = payload["items"]
    else:
        return {"path": relative, "status": "invalid", "items": [], "itemCount": 0, "reason": "done record must be an array or an object with items[]"}

    items: list[dict[str, Any]] = []
    for index, row in enumerate(raw_items):
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        package_path = row.get("packagePath") or row.get("package")
        delta_id = row.get("deltaId") or row.get("delta")
        comparison = _normalize_commit(row.get("comparisonCommit") or row.get("commit"))
        if isinstance(item_id, str) and "::" in item_id and (not package_path or not delta_id):
            source, _, delta = item_id.partition("::")
            package_path = package_path or source
            delta_id = delta_id or delta
        if not isinstance(item_id, str) and isinstance(package_path, str) and isinstance(delta_id, str):
            item_id = f"{package_path.replace(chr(92), '/')}::{delta_id.strip()}"
        if not isinstance(item_id, str) or not item_id.strip():
            continue
        items.append({
            "id": item_id.strip().replace("\\", "/"),
            "packagePath": package_path.replace("\\", "/").strip() if isinstance(package_path, str) else None,
            "deltaId": delta_id.strip() if isinstance(delta_id, str) else None,
            "comparisonCommit": comparison,
            "disposition": row.get("disposition"),
            "index": index,
        })
    return {"path": relative, "status": "ok", "items": items, "itemCount": len(items)}


def find_done_match(
    done: dict[str, Any],
    *,
    item_id: str,
    package_path: str | None = None,
    delta_id: str | None = None,
    comparison_commit: str | None = None,
) -> dict[str, Any] | None:
    """Return the first done item that matches id/package+delta.

    A Gate-backed query is commit-scoped: a done row without a comparisonCommit
    cannot suppress it, because it cannot prove that the disposition applies to
    the current Gate. A pending-only query has no comparison point and may still
    match by item id.
    """
    for row in done.get("items", []):
        row_commit = row.get("comparisonCommit")
        if comparison_commit is not None:
            if row_commit is None or not commits_match(row_commit, comparison_commit):
                continue
        if row.get("id") == item_id:
            return row
        if (
            package_path
            and delta_id
            and row.get("packagePath") == package_path
            and row.get("deltaId") == delta_id
        ):
            return row
    return None
