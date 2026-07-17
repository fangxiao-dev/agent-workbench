#!/usr/bin/env python3
"""Deterministic validation fixtures for the package runner; no Codex or target repo required."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from codex_harness_package import build_work_package, load_manifest, plan_summary, validate_manifest


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "fixture@example.test")
        git(root, "config", "user.name", "Fixture")
        package = root / "docs" / "implementations" / "fixture"
        write(package / "decision.md", "# Decision\n")
        write(package / "spec.md", "# Spec\n")
        write(package / "plan.md", "# Plan\n")
        write(package / "dag.md", "# DAG\n")
        write(package / "tickets" / "one.md", "# One\n")
        write(package / "tickets" / "two.md", "# Two\n")
        blobs = {name: subprocess.run(["git", "hash-object", str(package / name)], check=True, capture_output=True, text=True).stdout.strip() for name in ("decision.md", "spec.md", "plan.md")}
        sidecar = {
            "contractVersion": "3.2",
            "purpose": "internal-machine-sidecar",
            "ownerFacing": False,
            "current": {
                "decision": {"artifact": "decision.md", "revision": "D1"},
                "spec": {"artifact": "spec.md", "revision": "S1"},
                "attempt": {"id": "initial", "plan": "plan.md", "revision": "P1"},
            },
            "bindings": [
                {"id": f"D1@{blobs['decision.md']}", "artifact": "decision.md", "revision": "D1", "mode": "exact-blob", "blob": blobs["decision.md"], "supersedes": None, "evidence": "decision.md#revision-history"},
                {"id": f"S1@{blobs['spec.md']}", "artifact": "spec.md", "revision": "S1", "mode": "exact-blob", "blob": blobs["spec.md"], "supersedes": None, "evidence": "spec.md#revision-history"},
                {"id": f"initial:P1@{blobs['plan.md']}", "artifact": "plan.md", "attempt": "initial", "revision": "P1", "mode": "plan-contract-v1", "blob": blobs["plan.md"], "supersedes": None, "evidence": "plan.md#plan-revision-history"},
            ],
        }
        write(package / ".impl-package" / "revision-bindings.json", json.dumps(sidecar))
        profile = root / "parent.toml"
        write(profile, 'name="fixture"\ndescription="fixture"\nmodel="test"\nmodel_reasoning_effort="low"\ndeveloper_instructions="fixture"\n')
        git(root, "add", ".")
        git(root, "commit", "-m", "fixture")
        manifest_path = root / "fixture.toml"
        write(manifest_path, f'''schema_version = 1
[package]
repository_root = "{root.as_posix()}"
source_ref = "HEAD"
path = "docs/implementations/fixture"
attempt_id = "initial"
[runtime]
parent_profile = "parent.toml"
timeout_seconds = 60
max_parallel_parents = 2
network_access = false
[[stage]]
id = "T1"
cohort = "C1"
ticket = "ONE"
ticket_path = "tickets/one.md"
parent_role = "implementer"
objective = "Implement the fixture contract."
depends_on = []
allowed_paths = ["src"]
skills = ["impl-package"]
verification_commands = []
sandbox = "workspace_write"
sensitive_originals = "forbidden"
[[stage]]
id = "T2"
cohort = "C2"
ticket = "TWO"
ticket_path = "tickets/two.md"
parent_role = "reviewer"
objective = "Review the fixture contract."
depends_on = ["T1"]
allowed_paths = ["src"]
skills = ["impl-package/dev-with-track"]
verification_commands = []
sandbox = "read_only"
sensitive_originals = "on_demand"
''')
        manifest = load_manifest(manifest_path)
        validation = validate_manifest(manifest)
        assert validation["valid"], validation
        initial = plan_summary(manifest, set())
        assert [stage["id"] for stage in initial["ready_stages"]] == ["T1"]
        second = plan_summary(manifest, {"T1"}, ("secure",))
        assert [stage["id"] for stage in second["ready_stages"]] == ["T2"]
        package_payload = build_work_package(manifest, manifest.stages[1], ("secure",))
        assert package_payload["boundary"]["sensitive_originals"]["roots"] == ["secure"]
    print("package runner fixtures: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
