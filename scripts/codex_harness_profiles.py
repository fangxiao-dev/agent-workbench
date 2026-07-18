"""Canonical model/reasoning profile loading for Codex Harness/Crew."""

from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path
from typing import Any

try:
    from codex_harness_policy import PolicyError, _validate_schema
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_policy import PolicyError, _validate_schema


PROFILES_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-execution-profiles.v0.json")
SCHEMA_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-execution-profiles.schema.json")
PROFILES_VERSION = "codex-harness.execution-profiles.v0"
VALID_ROLES = {"parent", "worker"}
VALID_MODES = {"lite", "full"}


class ExecutionProfileError(RuntimeError):
    """Raised when a canonical execution profile cannot be consumed safely."""


class ParentProfileError(RuntimeError):
    """Raised when a TOML parent role cannot be bound to a canonical profile."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_execution_profiles(repository_root: Path, profiles_path: Path | None = None, schema_path: Path | None = None) -> dict[str, Any]:
    root = repository_root.resolve()
    profiles = (profiles_path or root / PROFILES_RELATIVE_PATH).resolve()
    schema = (schema_path or root / SCHEMA_RELATIVE_PATH).resolve()
    if not profiles.is_file() or not schema.is_file():
        raise ExecutionProfileError(f"canonical execution profiles/schema are missing: {profiles}, {schema}")
    try:
        profile_value = json.loads(profiles.read_text(encoding="utf-8"))
        schema_value = json.loads(schema.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExecutionProfileError(f"canonical execution profiles/schema cannot be parsed: {exc}") from exc
    try:
        _validate_schema(profile_value, schema_value, "$", schema_value)
    except PolicyError as exc:
        raise ExecutionProfileError(f"execution profiles failed schema validation: {exc}") from exc
    if profile_value.get("schema_version") != PROFILES_VERSION:
        raise ExecutionProfileError(f"unsupported execution profiles version: {profile_value.get('schema_version')!r}")

    indexed: dict[str, dict[str, str]] = {}
    for profile in profile_value["profiles"]:
        profile_id = profile["id"]
        if any(not isinstance(profile.get(key), str) or not profile[key].strip() for key in ("id", "role", "model", "reasoning_effort")):
            raise ExecutionProfileError("execution profile id, role, model, and reasoning_effort must be non-empty strings")
        if profile["role"] not in VALID_ROLES:
            raise ExecutionProfileError(f"unsupported execution profile role: {profile['role']}")
        if profile_id in indexed:
            raise ExecutionProfileError(f"duplicate execution profile id: {profile_id}")
        indexed[profile_id] = {
            "id": profile_id,
            "role": profile["role"],
            "model": profile["model"],
            "reasoning_effort": profile["reasoning_effort"],
        }
    for mode, profile_id in profile_value["worker_bindings"].items():
        if mode not in VALID_MODES:
            raise ExecutionProfileError(f"unsupported worker binding mode: {mode}")
        selected = indexed.get(profile_id)
        if selected is None:
            raise ExecutionProfileError(f"worker binding {mode!r} references an unknown profile: {profile_id}")
        if selected["role"] != "worker":
            raise ExecutionProfileError(f"worker binding {mode!r} references a non-worker profile: {profile_id}")
    try:
        relative_profiles = profiles.relative_to(root).as_posix()
        relative_schema = schema.relative_to(root).as_posix()
    except ValueError as exc:
        raise ExecutionProfileError("execution profiles and schema must remain inside repository root") from exc
    identity = {
        "profiles_path": relative_profiles,
        "schema_path": relative_schema,
        "profiles_sha256": _sha256(profiles),
        "schema_sha256": _sha256(schema),
        "schema_version": profile_value["schema_version"],
    }
    return {"profiles": indexed, "worker_bindings": profile_value["worker_bindings"], "identity": identity}


def resolve_execution_profile(bundle: dict[str, Any], profile_id: str, role: str) -> dict[str, str]:
    if role not in VALID_ROLES:
        raise ExecutionProfileError(f"unsupported execution profile role: {role}")
    selected = bundle.get("profiles", {}).get(profile_id)
    if selected is None:
        raise ExecutionProfileError(f"unknown execution profile: {profile_id}")
    if selected.get("role") != role:
        raise ExecutionProfileError(f"execution profile {profile_id!r} is not a {role} profile")
    return dict(selected)


def worker_profile_for_mode(bundle: dict[str, Any], mode: str) -> dict[str, str]:
    if mode not in VALID_MODES:
        raise ExecutionProfileError(f"unsupported worker mode: {mode}")
    profile_id = bundle["worker_bindings"].get(mode)
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise ExecutionProfileError(f"worker profile binding is missing for mode: {mode}")
    return resolve_execution_profile(bundle, profile_id, "worker")


def load_parent_profile(path: Path, execution_profiles_root: Path | None = None) -> dict[str, Any]:
    """Load a TOML role and resolve its model through canonical JSON profiles."""

    try:
        with path.open("rb") as stream:
            profile = tomllib.load(stream)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ParentProfileError(f"cannot read parent profile: {path}") from exc
    required = {"name", "description", "execution_profile", "developer_instructions"}
    missing = sorted(key for key in required if not isinstance(profile.get(key), str) or not profile[key].strip())
    if missing:
        raise ParentProfileError("Parent profile is missing required values: " + ", ".join(missing))
    root = (execution_profiles_root or Path(__file__).resolve().parents[1]).resolve()
    try:
        bundle = load_execution_profiles(root)
        resolved = resolve_execution_profile(bundle, profile["execution_profile"], "parent")
    except ExecutionProfileError as exc:
        raise ParentProfileError(f"parent execution profile is invalid: {exc}") from exc
    profile["model"] = resolved["model"]
    profile["model_reasoning_effort"] = resolved["reasoning_effort"]
    profile["execution_profile_identity"] = bundle["identity"]
    return profile
