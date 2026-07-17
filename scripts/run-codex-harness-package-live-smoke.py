#!/usr/bin/env python3
"""Run one disposable read-only parent stage through the package runner."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from codex_harness_package import execute_stage, load_manifest


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]


def git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout.strip()


def write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="codex-harness-package-") as temporary:
        root = Path(temporary) / "repo"
        root.mkdir()
        git(root, "init")
        git(root, "config", "user.email", "smoke@example.test")
        git(root, "config", "user.name", "Package smoke")
        package = root / "docs" / "implementations" / "smoke"
        write(package / "design.md", "# Design\n")
        write(package / "spec.md", "# Spec\n")
        write(package / "plan.md", "# Plan\n")
        write(package / "dag.md", "# DAG\n")
        write(package / "tickets" / "smoke.md", "# Smoke\nRead this package and return the requested result.\n")
        blobs = {name: subprocess.run(["git", "hash-object", str(package / name)], check=True, capture_output=True, text=True).stdout.strip() for name in ("design.md", "spec.md", "plan.md")}
        sidecar = {"current": {"design": {"revision": "D1"}, "spec": {"revision": "S1"}, "attempt": {"id": "initial", "revision": "P1"}}, "bindings": [{"artifact": "design.md", "revision": "D1", "blob": blobs["design.md"]}, {"artifact": "spec.md", "revision": "S1", "blob": blobs["spec.md"]}, {"artifact": "plan.md", "revision": "P1", "blob": blobs["plan.md"]}]}
        write(package / ".impl-package" / "revision-bindings.json", json.dumps(sidecar))
        git(root, "add", ".")
        git(root, "commit", "-m", "package smoke fixture")
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
skills = ["impl-package"]
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
