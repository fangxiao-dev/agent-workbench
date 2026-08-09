#!/usr/bin/env python3
"""Run one disposable read-only parent stage through the package runner."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from codex_harness_package import execute_stage, load_manifest


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def state_cli(package: Path, *args: str) -> None:
    script = WORKBENCH_ROOT / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_state.py"
    completed = subprocess.run([sys.executable, str(script), "--package", str(package), *args], capture_output=True, text=True)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or completed.stdout.strip())


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codex-harness-package-") as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "smoke@example.test")
        git(root, "config", "user.name", "Package smoke")
        package = root / "docs" / "implementations" / "smoke"
        write(package / "decision.md", "# Decision\n\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\n<!-- impl-package:projection revision-set end -->\n")
        write(package / "spec.md", "# Spec\n\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\nSpec Revision：S1\n<!-- impl-package:projection revision-set end -->\n")
        write(package / "plan.md", "# Plan\n\nAttempt ID：initial\n<!-- impl-package:projection revision-set begin -->\nDecision Revision：D1\nSpec Revision：S1\nPlan Revision：P1\n<!-- impl-package:projection revision-set end -->\nComposition：tickets=false, dag=true\n\n## Execution Record\n\n")
        write(package / "dag.md", "# DAG\n\nAttempt ID：initial\n\n<!-- impl-package:projection runtime-state begin -->\n<!-- impl-package:projection runtime-state end -->\n\n## Task Contracts\n\n### T1：Read-only smoke\n\n- Depends on：none\n- Primary owned files/modules：`src/`\n- contributes-to：spec:AC-1\n- Done when：the package is read\n")
        write(package / "tickets" / "smoke.md", "# Smoke\nRead this package and return the requested result.\n")
        write(package / "gate.md", "# Gate Ledger\n\n<!-- impl-package:projection gate-status begin -->\n状态：尚无已定稿门禁记录\n<!-- impl-package:projection gate-status end -->\n")
        git(root, "add", ".")
        git(root, "commit", "-m", "package smoke fixture")
        state_cli(package, "init", "--package-id", "260716-smoke")
        state_cli(package, "register-revision", "decision", "D1", "--artifact", "decision.md", "--evidence", "decision.md#revision-history")
        state_cli(package, "register-revision", "spec", "S1", "--artifact", "spec.md", "--evidence", "spec.md#revision-history")
        state_cli(package, "register-revision", "plan", "P1", "--artifact", "plan.md", "--attempt", "initial", "--evidence", "plan.md#plan-revision-history")
        state_cli(package, "init", "--package-id", "260716-smoke")
        state_cli(package, "refresh-projections")
        git(root, "add", ".")
        git(root, "commit", "-m", "package smoke structured state")
        manifest_path = Path(temporary) / "manifest.toml"
        profile = (WORKBENCH_ROOT / ".codex" / "harness" / "parent.toml").as_posix()
        write(manifest_path, f'''schema_version = 1
[package]
repository_root = "{root.as_posix()}"
source_ref = "HEAD"
path = "docs/implementations/smoke"
attempt_id = "initial"
[runtime]
parent_profile = "{profile}"
timeout_seconds = 180
max_parallel_parents = 1
network_access = false
[[stage]]
id = "SMOKE"
cohort = "smoke"
ticket = "SMOKE-01"
ticket_path = "tickets/smoke.md"
parent_role = "read_only_smoke"
objective = "Read the pinned package and confirm its four core package documents are available. Do not modify files."
depends_on = []
allowed_paths = ["src"]
skills = ["impl-package:impl-package"]
verification_commands = ["python -c \\\"print('external verifier passed')\\\""]
sandbox = "read_only"
sensitive_originals = "forbidden"
''')
        manifest = load_manifest(manifest_path)
        result = execute_stage(manifest, manifest.stages[0], root, 180)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result["status"] == "passed" else 2


if __name__ == "__main__":
    raise SystemExit(main())
