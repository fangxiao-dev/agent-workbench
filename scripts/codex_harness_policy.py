"""Canonical runtime-policy loading for Codex Harness entrypoints.

The policy JSON is the only configurable strategy surface.  This module uses
the adjacent schema as data and implements the small JSON-Schema subset used by
the checked-in policy, keeping the exploratory runtime on the Python standard
library without introducing a second policy vocabulary.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


POLICY_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-runtime-policy.v0.json")
SCHEMA_RELATIVE_PATH = Path("skills/codex-harness/assets/codex-harness-runtime-policy.schema.json")
POLICY_VERSION = "codex-harness.runtime-policy.v0"
MATURITIES = {"design_baseline", "runtime_enforced"}


class PolicyError(RuntimeError):
    """Raised when the canonical policy cannot be proven safe to consume."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "null":
        return value is None
    raise PolicyError(f"unsupported JSON Schema type: {expected!r}")


def _validate_schema(value: Any, schema: dict[str, Any], path: str = "$", root: dict[str, Any] | None = None) -> None:
    if not isinstance(schema, dict):
        raise PolicyError(f"schema node is not an object at {path}")
    if "$ref" in schema:
        ref = schema["$ref"]
        if ref != "#":
            raise PolicyError(f"unsupported schema reference at {path}: {ref!r}")
        if root is None:
            raise PolicyError(f"schema root is unavailable at {path}")
        _validate_schema(value, root, path, root)
        return
    if "const" in schema and value != schema["const"]:
        raise PolicyError(f"policy value at {path} must equal {schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise PolicyError(f"policy value at {path} is not an allowed enum")
    expected_type = schema.get("type")
    if expected_type is not None:
        expected_types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_type_matches(value, item) for item in expected_types):
            raise PolicyError(f"policy value at {path} has the wrong type")
    if isinstance(value, dict):
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise PolicyError(f"schema properties are invalid at {path}")
        required = schema.get("required", [])
        if not isinstance(required, list) or any(not isinstance(item, str) for item in required):
            raise PolicyError(f"schema required list is invalid at {path}")
        missing = [item for item in required if item not in value]
        if missing:
            raise PolicyError(f"policy object at {path} is missing: {', '.join(missing)}")
        if schema.get("additionalProperties") is False:
            unknown = sorted(set(value) - set(properties))
            if unknown:
                raise PolicyError(f"policy object at {path} has unknown fields: {', '.join(unknown)}")
        for key, child_schema in properties.items():
            if key in value:
                _validate_schema(value[key], child_schema, f"{path}.{key}", root or schema)
    if isinstance(value, list):
        minimum = schema.get("minItems")
        if minimum is not None and len(value) < minimum:
            raise PolicyError(f"policy array at {path} has fewer than {minimum} items")
        if schema.get("uniqueItems") and len(value) != len({json.dumps(item, sort_keys=True) for item in value}):
            raise PolicyError(f"policy array at {path} must contain unique items")
        item_schema = schema.get("items")
        if item_schema is not None:
            for index, item in enumerate(value):
                _validate_schema(item, item_schema, f"{path}[{index}]", root or schema)


def load_runtime_policy(repository_root: Path, policy_path: Path | None = None, schema_path: Path | None = None) -> dict[str, Any]:
    root = repository_root.resolve()
    policy = (policy_path or root / POLICY_RELATIVE_PATH).resolve()
    schema = (schema_path or root / SCHEMA_RELATIVE_PATH).resolve()
    if not policy.is_file() or not schema.is_file():
        raise PolicyError(f"canonical runtime policy/schema is missing: {policy}, {schema}")
    try:
        policy_value = json.loads(policy.read_text(encoding="utf-8"))
        schema_value = json.loads(schema.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise PolicyError(f"canonical runtime policy/schema cannot be parsed: {exc}") from exc
    _validate_schema(policy_value, schema_value, "$", schema_value)
    if policy_value.get("schema_version") != POLICY_VERSION:
        raise PolicyError(f"unsupported runtime policy version: {policy_value.get('schema_version')!r}")
    if policy_value.get("maturity") not in MATURITIES:
        raise PolicyError(f"unsupported runtime policy maturity: {policy_value.get('maturity')!r}")
    try:
        relative_policy = policy.relative_to(root).as_posix()
        relative_schema = schema.relative_to(root).as_posix()
    except ValueError as exc:
        raise PolicyError("runtime policy and schema must remain inside repository root") from exc
    identity = {
        "policy_path": relative_policy,
        "schema_path": relative_schema,
        "policy_sha256": _sha256(policy),
        "schema_sha256": _sha256(schema),
        "schema_version": policy_value["schema_version"],
        "maturity": policy_value["maturity"],
    }
    return {"policy": policy_value, "schema": schema_value, "identity": identity}


def decision_audience(policy_bundle: dict[str, Any], category: str) -> str:
    policy = policy_bundle["policy"]
    if category == "same_task_correction" and policy["decision_routing"]["harness_resolvable"] == "continue_same_task":
        return "harness"
    if category in policy["decision_routing"]["owner_required"]:
        return "owner"
    raise PolicyError(f"unknown decision category: {category}")
