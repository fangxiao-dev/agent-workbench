"""Canonical model/reasoning profile loading for Codex Harness/Crew."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
import tomllib
from pathlib import Path
from typing import Any

try:
    from codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from codex_harness_policy import PolicyError, _validate_schema
except ModuleNotFoundError:  # pragma: no cover - supports package-style imports
    from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params
    from scripts.codex_harness_policy import PolicyError, _validate_schema


PROFILES_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-execution-profiles.v0.2.json")
SCHEMA_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-execution-profiles.v0.2.schema.json")
PROFILES_VERSION = "codex-harness.execution-profiles.v0.2"
VALID_ROLES = {"parent", "worker", "verifier"}
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
    bindings: dict[str, list[str]] = {}
    for mode, profile_ids in profile_value["worker_bindings"].items():
        if mode not in VALID_MODES:
            raise ExecutionProfileError(f"unsupported worker binding mode: {mode}")
        if not isinstance(profile_ids, list) or not profile_ids:
            raise ExecutionProfileError(f"worker binding {mode!r} must declare at least one candidate")
        normalized: list[str] = []
        for profile_id in profile_ids:
            if not isinstance(profile_id, str) or not profile_id.strip():
                raise ExecutionProfileError(f"worker binding {mode!r} has an invalid candidate")
            selected = indexed.get(profile_id)
            if selected is None:
                raise ExecutionProfileError(f"worker binding {mode!r} references an unknown profile: {profile_id}")
            if selected["role"] != "worker":
                raise ExecutionProfileError(f"worker binding {mode!r} references a non-worker profile: {profile_id}")
            normalized.append(profile_id)
        if len(set(normalized)) != len(normalized):
            raise ExecutionProfileError(f"worker binding {mode!r} repeats a candidate")
        bindings[mode] = normalized
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
    verifier_bindings: dict[str, list[str]] = {}
    for mode, profile_ids in profile_value["verifier_bindings"].items():
        if mode != "full" or not isinstance(profile_ids, list) or not profile_ids:
            raise ExecutionProfileError("verifier binding must declare at least one Full candidate")
        normalized = []
        for profile_id in profile_ids:
            selected = indexed.get(profile_id)
            if selected is None or selected["role"] != "verifier":
                raise ExecutionProfileError(f"verifier binding references an invalid profile: {profile_id}")
            normalized.append(profile_id)
        if len(set(normalized)) != len(normalized):
            raise ExecutionProfileError("verifier binding repeats a candidate")
        verifier_bindings[mode] = normalized
    return {"profiles": indexed, "worker_bindings": bindings, "verifier_bindings": verifier_bindings, "identity": identity}


def resolve_execution_profile(bundle: dict[str, Any], profile_id: str, role: str) -> dict[str, str]:
    if role not in VALID_ROLES:
        raise ExecutionProfileError(f"unsupported execution profile role: {role}")
    selected = bundle.get("profiles", {}).get(profile_id)
    if selected is None:
        raise ExecutionProfileError(f"unknown execution profile: {profile_id}")
    if selected.get("role") != role:
        raise ExecutionProfileError(f"execution profile {profile_id!r} is not a {role} profile")
    return dict(selected)


def worker_profile_candidates_for_mode(bundle: dict[str, Any], mode: str) -> list[dict[str, str]]:
    if mode not in VALID_MODES:
        raise ExecutionProfileError(f"unsupported worker mode: {mode}")
    profile_ids = bundle["worker_bindings"].get(mode)
    if not isinstance(profile_ids, list) or not profile_ids:
        raise ExecutionProfileError(f"worker profile binding is missing for mode: {mode}")
    return [resolve_execution_profile(bundle, profile_id, "worker") for profile_id in profile_ids]


def worker_profile_for_mode(bundle: dict[str, Any], mode: str) -> dict[str, str]:
    """Return the canonical first-choice Worker profile for a mode.

    This is deliberately not a runtime availability decision. Call
    :func:`select_available_worker_profile` before creating a worktree or
    starting a Worker to select from this ordered candidate list.
    """

    return worker_profile_candidates_for_mode(bundle, mode)[0]


def verifier_profile_candidates_for_mode(bundle: dict[str, Any], mode: str) -> list[dict[str, str]]:
    if mode != "full":
        raise ExecutionProfileError("independent verifier profiles are only defined for Full assurance")
    profile_ids = bundle["verifier_bindings"].get(mode)
    if not isinstance(profile_ids, list) or not profile_ids:
        raise ExecutionProfileError("verifier profile binding is missing for Full assurance")
    return [resolve_execution_profile(bundle, profile_id, "verifier") for profile_id in profile_ids]


def model_catalog_digest(catalog: dict[str, Any]) -> str:
    """Return the stable digest recorded with an App Server model/list observation."""

    try:
        serialized = json.dumps(catalog, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except (TypeError, ValueError) as exc:
        raise ExecutionProfileError(f"model catalog cannot be serialized: {exc}") from exc
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def fetch_model_catalog(*, timeout_seconds: float = 30) -> dict[str, Any]:
    """Fetch App Server ``model/list`` without creating a Worker worktree.

    The temporary stderr artifact is intentionally outside a caller's
    repository. This low-level capability is shared by dispatch callers; it
    has no policy, topology, or scheduler semantics.
    """

    if timeout_seconds <= 0:
        raise ExecutionProfileError("model catalog request timeout must be positive")
    artifact_root = Path(tempfile.gettempdir()) / "codex-harness-runs" / "profile-preflight"
    stderr_path = artifact_root / f"model-list-{os.getpid()}-{time.monotonic_ns()}.stderr.log"
    try:
        with JsonRpcSession(app_server_command(approval_policy="never"), stderr_path) as session:
            session.request(1, "initialize", initialize_params("codex-harness-profile-preflight"), timeout_seconds)
            catalog, _ = session.request(2, "model/list", {}, timeout_seconds)
    except (OSError, RuntimeError, TimeoutError) as exc:
        raise ExecutionProfileError(f"App Server model catalog is unavailable: {exc}") from exc
    if not isinstance(catalog, dict):
        raise ExecutionProfileError("App Server model catalog must be an object")
    return catalog


def _available_model_efforts(catalog: dict[str, Any]) -> dict[str, set[str]]:
    data = catalog.get("data")
    if not isinstance(data, list):
        raise ExecutionProfileError("App Server model catalog does not contain a data array")
    available: dict[str, set[str]] = {}
    for model in data:
        if not isinstance(model, dict) or model.get("hidden") is True:
            continue
        identifiers = {value for key in ("id", "model") if isinstance((value := model.get(key)), str) and value.strip()}
        efforts_value = model.get("supportedReasoningEfforts")
        if not identifiers or not isinstance(efforts_value, list):
            continue
        efforts = {
            effort
            for item in efforts_value
            for effort in (
                item if isinstance(item, str) else item.get("reasoningEffort") if isinstance(item, dict) else None,
            )
            if isinstance(effort, str) and effort.strip()
        }
        for identifier in identifiers:
            available.setdefault(identifier, set()).update(efforts)
    return available


def _select_available_profile(candidates: list[dict[str, str]], catalog: dict[str, Any], *, subject: str, observed_at: float | None = None) -> dict[str, Any]:
    """Select the first supported candidate and return controller-owned evidence."""

    available = _available_model_efforts(catalog)
    for index, candidate in enumerate(candidates):
        if candidate["reasoning_effort"] in available.get(candidate["model"], set()):
            return {
                "requested_candidates": candidates,
                "selected_profile": candidate,
                "catalog_digest": model_catalog_digest(catalog),
                "observed_at": time.time() if observed_at is None else observed_at,
                "reason": "first_available_candidate" if index == 0 else "fallback_after_unavailable_prior_candidates",
            }
    requested = ", ".join(f"{candidate['model']}/{candidate['reasoning_effort']}" for candidate in candidates)
    raise ExecutionProfileError(f"App Server model catalog has no usable {subject} candidate: {requested}")


def select_available_worker_profile(bundle: dict[str, Any], mode: str, catalog: dict[str, Any], *, observed_at: float | None = None) -> dict[str, Any]:
    """Select the first canonical Worker candidate supported by ``model/list``.

    The returned evidence is intended to be persisted verbatim in dispatcher
    state. Missing catalogs and unavailable candidates are errors rather than
    invitations for callers to silently substitute a model.
    """

    return _select_available_profile(worker_profile_candidates_for_mode(bundle, mode), catalog, subject=f"Worker for {mode}", observed_at=observed_at)


def select_available_verifier_profile(bundle: dict[str, Any], mode: str, catalog: dict[str, Any], *, observed_at: float | None = None) -> dict[str, Any]:
    """Select the canonical Full verifier or fail closed when Sol/high is unavailable."""

    return _select_available_profile(verifier_profile_candidates_for_mode(bundle, mode), catalog, subject="Full verifier", observed_at=observed_at)


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
