#!/usr/bin/env python3
"""Deterministic false-PASS and Parent Result validator fixtures."""

from __future__ import annotations

import json
import importlib.util
import sys
from pathlib import Path
from typing import Any

RUNNER_PATH = Path(__file__).with_name("run-codex-app-server-pilot.py")
SPEC = importlib.util.spec_from_file_location("codex_harness_runner", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
RUNNER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(RUNNER)
parse_parent_result = RUNNER.parse_parent_result


def classify(raw: str, expected_run_id: str, repository_root: Path, expected_revision: str) -> str:
    try:
        result = parse_parent_result(raw, expected_run_id)
    except (TypeError, ValueError):
        return "failed"
    if result is None:
        return "failed"
    if result.get("status") == "needs_owner":
        return "needs_owner"
    revision = result.get("revision")
    if revision is not None and revision != expected_revision:
        return "failed"
    for artifact in result["artifacts"]:
        path = Path(artifact["path"])
        if path.is_absolute() or ".." in path.parts:
            return "failed"
        resolved = (repository_root / path).resolve()
        if repository_root not in resolved.parents and resolved != repository_root:
            return "failed"
        if not resolved.exists():
            return "failed"
    if any(item["exit_code"] != 0 for item in result["verification"]):
        return "failed"
    if result["status"] != "succeeded" or result["boundary_violations"]:
        return "failed"
    return "passed"


def base(run_id: str, **overrides: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": "codex-harness.parent-result.v0",
        "run_id": run_id,
        "stage": "validator-fixture",
        "status": "succeeded",
        "summary": "fixture",
        "artifacts": [],
        "verification": [{"command": "fixture", "exit_code": 0, "claim": "fixture"}],
        "findings": [],
        "owner_decisions": [],
        "retry_hint": "none",
        "boundary_violations": [],
    }
    result.update(overrides)
    return result


def main() -> int:
    repository_root = Path(__file__).resolve().parents[1]
    run_id = "validator-fixture-run"
    revision = "rev-current"
    existing = "AGENTS.md"
    fixtures = {
        "valid": (json.dumps(base(run_id)), "passed"),
        "malformed_json": ("{not-json", "failed"),
        "wrong_run_id": (json.dumps(base("other-run")), "failed"),
        "missing_artifact": (json.dumps(base(run_id, artifacts=[{"path": "missing.file", "purpose": "fixture"}])), "failed"),
        "failed_command": (json.dumps(base(run_id, verification=[{"command": "false", "exit_code": 1, "claim": "fixture"}])), "failed"),
        "stale_revision": (json.dumps(base(run_id, revision="rev-old")), "failed"),
        "needs_owner": (json.dumps(base(run_id, status="needs_owner")), "needs_owner"),
        "boundary_violation": (json.dumps(base(run_id, boundary_violations=["write denied"])), "failed"),
    }
    # Make the valid fixture prove an in-repository artifact path as well.
    valid = base(run_id, artifacts=[{"path": existing, "purpose": "fixture"}])
    fixtures["valid"] = (json.dumps(valid), "passed")
    results = {name: {"actual": classify(raw, run_id, repository_root, revision), "expected": expected} for name, (raw, expected) in fixtures.items()}
    passed = all(item["actual"] == item["expected"] for item in results.values())
    summary = {"run_id": run_id, "status": "passed" if passed else "failed", "false_pass_count": sum(item["actual"] == "passed" and item["expected"] != "passed" for item in results.values()), "fixtures": results}
    output_dir = repository_root / ".codex" / "harness-runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{run_id}.summary.json"
    output.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
