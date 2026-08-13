#!/usr/bin/env python3
"""Read-only adapter from an Impl-Package entry to broker facts."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


class PackageAdapterError(Exception):
    pass


FACT_FIELDS = (
    "package_entry",
    "active_checkpoint",
    "next_action",
    "worktree",
    "branch",
    "head",
    "current_session_id",
    "revision",
)


def _git(worktree: Path, arguments: list[str]) -> str:
    try:
        result = subprocess.run(
            ["git", "-C", str(worktree), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=5,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise PackageAdapterError(f"git unavailable for package: {worktree}") from exc
    value = (result.stdout or "").strip()
    if result.returncode != 0 or not value:
        raise PackageAdapterError(f"git command failed for package: {worktree}")
    return value


def _schema_warning(detail: str) -> tuple[str, str]:
    return ("package_schema_warning", detail)


def _read_package_state(package_root: Path) -> tuple[dict | None, list[tuple[str, str]]]:
    state_path = package_root / ".impl-package" / "state.json"
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None, [_schema_warning(f"package state missing: {state_path}")]
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return None, [_schema_warning(f"package state unreadable: {state_path} ({exc})")]
    if not isinstance(state, dict):
        return None, [_schema_warning("package state root is not an object")]
    if state.get("formatVersion") != "3.5":
        return None, [_schema_warning(
            f"package format is {state.get('formatVersion')!r}; expected 3.5"
        )]
    return state, []


def _active_checkpoint(
    package_root: Path,
    state: dict,
) -> tuple[str | None, str | None, list[tuple[str, str]]]:
    warnings: list[tuple[str, str]] = []
    attempt = state.get("attempt")
    attempt_id = attempt.get("id") if isinstance(attempt, dict) else None
    if not isinstance(attempt_id, str) or not attempt_id.strip():
        warnings.append(_schema_warning("package state missing attempt.id"))
        attempt_id = None
    else:
        attempt_id = attempt_id.strip()

    checkpoints = state.get("activeCheckpoints")
    if not isinstance(checkpoints, dict):
        warnings.append(_schema_warning("activeCheckpoints is unavailable"))
        return None, None, warnings
    checkpoint = checkpoints.get("attempt")
    if checkpoint is None:
        warnings.append(_schema_warning("activeCheckpoints.attempt is unavailable"))
        return None, None, warnings
    if not isinstance(checkpoint, dict):
        warnings.append(_schema_warning("activeCheckpoints.attempt is unavailable"))
        return None, None, warnings

    next_action = checkpoint.get("next")
    if not isinstance(next_action, str) or not next_action.strip():
        warnings.append(_schema_warning("activeCheckpoints.attempt.next is unavailable"))
        next_action = None
    else:
        next_action = next_action.strip()

    record_value = None
    history = state.get("attemptHistory")
    if isinstance(history, list) and attempt_id is not None:
        for row in reversed(history):
            if (
                isinstance(row, dict)
                and row.get("id") == attempt_id
                and isinstance(row.get("executionRecord"), str)
            ):
                record_value = row["executionRecord"]
                break
    if not isinstance(record_value, str) or not record_value.strip():
        warnings.append(_schema_warning("active checkpoint execution record is unavailable"))
        return None, next_action, warnings

    record = Path(record_value)
    if record.is_absolute():
        warnings.append(_schema_warning("active checkpoint execution record must be package-relative"))
        return None, next_action, warnings
    package_root = package_root.resolve(strict=False)
    candidate = (package_root / record).resolve(strict=False)
    try:
        candidate.relative_to(package_root)
    except ValueError:
        warnings.append(_schema_warning("active checkpoint execution record leaves package root"))
        return None, next_action, warnings
    if not candidate.is_file():
        warnings.append(_schema_warning(f"active checkpoint missing: {candidate}"))
        return None, next_action, warnings
    return str(candidate), next_action, warnings


def read_package_observation(
    package_entry: str,
    *,
    current_session_id: str | None = None,
) -> tuple[dict, list[tuple[str, str]]]:
    """Read broker facts and non-blocking package schema warnings."""
    if not isinstance(package_entry, str) or not package_entry.strip():
        raise PackageAdapterError("package_entry must be a non-empty absolute path")
    entry = Path(package_entry).expanduser()
    if not entry.is_absolute():
        raise PackageAdapterError("package_entry must be an absolute path")
    entry = entry.resolve(strict=False)
    if entry.name != "progress.md" or not entry.is_file():
        raise PackageAdapterError(f"package_entry must be an existing progress.md: {entry}")

    package_root = entry.parent
    worktree = Path(_git(package_root, ["rev-parse", "--show-toplevel"])).resolve(strict=False)
    branch_result = subprocess.run(
        ["git", "-C", str(worktree), "symbolic-ref", "--quiet", "--short", "HEAD"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=5,
        check=False,
    )
    branch = (branch_result.stdout or "").strip() if branch_result.returncode == 0 else "<detached>"
    head = _git(worktree, ["rev-parse", "HEAD"])
    if not re.fullmatch(r"[0-9a-fA-F]{40}", head):
        raise PackageAdapterError(f"git HEAD is not a full revision: {head}")

    facts = {
        "package_entry": str(entry),
        "active_checkpoint": None,
        "next_action": None,
        "worktree": str(worktree),
        "branch": branch,
        "head": head.lower(),
        "current_session_id": current_session_id,
        "revision": head.lower(),
    }
    state, warnings = _read_package_state(package_root)
    if state is not None:
        checkpoint, next_action, checkpoint_warnings = _active_checkpoint(package_root, state)
        facts["active_checkpoint"] = checkpoint
        facts["next_action"] = next_action
        warnings.extend(checkpoint_warnings)
    return facts, warnings


def read_package_facts(package_entry: str, *, current_session_id: str | None = None) -> dict:
    """Read the fixed v1 fact set without mutating or copying package state."""
    facts, _warnings = read_package_observation(
        package_entry,
        current_session_id=current_session_id,
    )
    return facts
