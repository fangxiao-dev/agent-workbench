#!/usr/bin/env python3
"""Read-only Impl-Package adapter evidence using the canonical 3.2 CLI."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def _state_cli(root: Path) -> Path:
    return root / "plugin-marketplace" / "plugins" / "impl-package" / "scripts" / "impl_package_state.py"


def _run_state(root: Path, package: Path, *arguments: str) -> tuple[bool, dict | None, str]:
    completed = subprocess.run([sys.executable, str(_state_cli(root)), "--package", str(package), *arguments], capture_output=True, text=True)
    output = completed.stdout.strip()
    try:
        parsed = json.loads(output) if output else None
    except json.JSONDecodeError:
        parsed = None
    return completed.returncode == 0, parsed, completed.stderr.strip() or output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--package", type=Path, required=True, help="Repository-relative or absolute Impl-Package path.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--write-back", action="store_true", help="Retained for compatibility; direct plan/gate mutation is disabled.")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    package = args.package if args.package.is_absolute() else root / args.package
    package = package.resolve()
    try:
        package.relative_to(root)
    except ValueError as error:
        raise ValueError("--package must be inside --repository-root") from error
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    parent = summary.get("parent_result") or {}
    sidecar_path = package / ".impl-package" / "revision-bindings.json"
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.is_file() else {}
    current = sidecar.get("current", {}) if isinstance(sidecar, dict) else {}
    attempt = current.get("attempt", {}) if isinstance(current, dict) else {}
    plan_artifact = attempt.get("plan") if isinstance(attempt, dict) else None
    spec_text = (package / "spec.md").read_text(encoding="utf-8") if (package / "spec.md").is_file() else ""
    parent_text = " ".join([str(parent.get("summary", "")), *(str(item) for item in parent.get("findings", [])), *(str(item.get("claim", "")) for item in parent.get("verification", []) if isinstance(item, dict))]).lower()
    validation_ok, validation, validation_error = _run_state(root, package, "validate", "--working-tree")
    gate_ok, gate, gate_error = _run_state(root, package, "resolve-gate")
    checks = {
        "package_documents_present": all((package / name).is_file() for name in ("spec.md", ".impl-package/revision-bindings.json", ".impl-package/runtime-state.json")) and isinstance(plan_artifact, str) and (package / plan_artifact).is_file(),
        "current_spec_ac_count": len(re.findall(r"\| AC-\d+ \|", spec_text)) > 0,
        "binding_sidecar_current": validation_ok and isinstance(validation, dict) and validation.get("contractVersion") == "3.2",
        "gate_resolution_trusted": gate_ok and isinstance(gate, dict) and gate.get("kind") in {"indexed", None} and gate.get("needsManualGateReview") is False,
        "parent_result_valid": summary.get("status") == "passed" and summary.get("parent_result_valid") is True and parent.get("status") == "succeeded",
        "parent_only_finding": "parent-only" in parent_text and "child" in parent_text and "accept" in parent_text,
        "worktree_unchanged": summary.get("worktree_changed") is False or summary.get("worktree_status_before") == summary.get("worktree_status_after"),
    }
    passed = all(checks.values())
    write_back = {
        "requested": args.write_back,
        "applied": False,
        "reason": "direct plan/gate write-back is disabled; append Execution Record and gate entries through canonical Impl-Package CLI",
    }
    output_dir = root / ".codex" / "harness-runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{summary['run_id']}.impl-package-adapter.json"
    evidence = {
        "run_id": summary["run_id"],
        "status": "passed" if passed else "failed",
        "package": str(package),
        "current_attempt": attempt,
        "checks": checks,
        "canonical_validation": validation,
        "canonical_validation_error": validation_error if not validation_ok else None,
        "gate_resolution": gate,
        "gate_resolution_error": gate_error if not gate_ok else None,
        "parent_thread_id": summary.get("root_thread_id"),
        "parent_result": parent,
        "write_back": write_back,
    }
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(evidence, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
