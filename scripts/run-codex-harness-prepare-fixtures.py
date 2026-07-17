#!/usr/bin/env python3
"""Deterministic generic fixtures for automatic Impl-Package adaptation."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from codex_harness_package import load_manifest
from codex_harness_prepare import prepare_adapter


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
        for artifact in ("decision.md", "spec.md", "plan.md"):
            write(package / artifact, f"# {artifact}\n")
        write(package / "tickets" / "one.md", "# One\n\n**Ticket ID：** FIXTURE-01\n")
        write(package / "tickets" / "two.md", "# Two\n\n**Ticket ID：** FIXTURE-02\n")
        write(
            package / "dag.md",
            """# Fixture DAG

## Task Contracts

### T1：Feature implementation

- Depends on：none
- Primary owned files/modules：`src/feature/`
- contributes-to：FIXTURE-01:AC-1
- Done when：The feature contract is stable

### T2：真实OCR convergence

- Depends on：T1
- Primary owned files/modules：`src/ocr/`
- contributes-to：FIXTURE-02:AC-1
- Done when：The protected OCR input is fail closed

### T3：主线集成与正式review

- Depends on：T2
- Primary owned files/modules：`src/integration/`
- enables：FIXTURE-01:AC-1, FIXTURE-02:AC-1
- Done when：The comparison point is fixed

## Parallel Cohorts

- Cohort 1：T1先行。
- Cohort 2：T2执行OCR conformance。
- Cohort 3：T3集成，且与已完成的T2证据核对。

## Integration Seams
""",
        )
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

        manifest_text, readiness = prepare_adapter(root, "HEAD", "docs/implementations/fixture", "parent.toml")
        manifest_path = root / "generated.fixture.toml"
        write(manifest_path, manifest_text)
        manifest = load_manifest(manifest_path)
        stages = {stage.id: stage for stage in manifest.stages}
        assert readiness["initial_ready_stages"] == ["T1"], readiness
        assert stages["T1"].ticket == "FIXTURE-01"
        assert stages["T2"].ticket == "FIXTURE-02"
        assert stages["T2"].cohort == "C2"
        assert stages["T2"].sensitive_originals == "on_demand"
        assert stages["T3"].ticket == "integration-gate"
        assert stages["T3"].parent_role == "impl_package_integration_reviewer"
    print("prepare adapter fixtures: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
