#!/usr/bin/env python3
"""Deterministic generic fixtures for automatic Impl-Package adaptation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from codex_harness_package import load_manifest
from codex_harness_prepare import prepare_adapter


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def state_cli(package: Path, *args: str) -> None:
    script = Path(__file__).resolve().parents[1] / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
    completed = subprocess.run([sys.executable, str(script), "--package", str(package), *args], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "fixture@example.test")
        git(root, "config", "user.name", "Fixture")
        package = root / "docs" / "implementations" / "fixture"
        write(package / "decision.md", "# Decision\n\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\n<!-- impl-package:projection revision-set end -->\n")
        write(package / "spec.md", "# Spec\n\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\nSpec Revision：S1\n<!-- impl-package:projection revision-set end -->\n")
        write(package / "plan.md", "# Plan\n\nAttempt ID：initial\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\nSpec Revision：S1\nPlan Revision：P1\n<!-- impl-package:projection revision-set end -->\nComposition：tickets=false, dag=true\n\n## Execution Record\n\n")
        write(package / "tickets" / "one.md", "# One\n\n**Ticket ID：** FIXTURE-01\n")
        write(package / "tickets" / "two.md", "# Two\n\n**Ticket ID：** FIXTURE-02\n")
        write(
            package / "dag.md",
            """# Fixture DAG

Attempt ID：initial

<!-- impl-package:projection runtime-state begin -->
<!-- impl-package:projection runtime-state end -->

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
        write(package / "gate.md", "# Gate Ledger\n\n<!-- impl-package:projection gate-status begin -->\n状态：尚无已定稿门禁记录\n<!-- impl-package:projection gate-status end -->\n")
        profile = root / "parent.toml"
        write(profile, 'name="fixture"\ndescription="fixture"\nexecution_profile="parent-sol-high"\ndeveloper_instructions="fixture"\n')
        git(root, "add", ".")
        git(root, "commit", "-m", "fixture")
        state_cli(package, "init", "--package-id", "260716-fixture")
        state_cli(package, "register-revision", "decision", "D1", "--artifact", "decision.md", "--evidence", "decision.md#revision-history")
        state_cli(package, "register-revision", "spec", "S1", "--artifact", "spec.md", "--evidence", "spec.md#revision-history")
        state_cli(package, "register-revision", "plan", "P1", "--artifact", "plan.md", "--attempt", "initial", "--evidence", "plan.md#plan-revision-history")
        state_cli(package, "init", "--package-id", "260716-fixture")
        state_cli(package, "refresh-projections")
        git(root, "add", ".")
        git(root, "commit", "-m", "fixture structured package state")

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
