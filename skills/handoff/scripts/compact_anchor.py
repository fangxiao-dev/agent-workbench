from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


COMMAND_TIMEOUT_SECONDS = 60
PACKAGE_TRANSACTION_JOURNALS = (
    Path(".impl-package/registration-transaction.json"),
    Path(".impl-package/publish-plan-transaction.json"),
)


def run_git(worktree: Path, *args: str) -> bytes:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    try:
        result = subprocess.run(
            ["git", "-C", str(worktree), *args],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
            env=environment,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"git {' '.join(args)} timed out") from error
    if result.returncode != 0:
        error = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"git {' '.join(args)} failed: {error}")
    return result.stdout


def decode_scalar(value: bytes) -> str:
    return value.decode("utf-8", errors="replace").strip()


def summarize_dirty(worktree: Path) -> dict[str, Any]:
    raw_status = run_git(
        worktree,
        "status",
        "--porcelain=v2",
        "-z",
        "--untracked-files=all",
    )
    chunks = raw_status.split(b"\0")
    staged = 0
    worktree_changed = 0
    untracked = 0
    conflicts = 0
    total = 0
    index = 0

    while index < len(chunks):
        record = chunks[index]
        index += 1
        if not record:
            continue
        kind = record[:1]
        total += 1
        if kind == b"?":
            untracked += 1
            continue
        if kind == b"2":
            if index >= len(chunks) or not chunks[index]:
                raise ValueError("malformed porcelain v2 rename record")
            index += 1
        if kind not in {b"1", b"2", b"u"}:
            raise ValueError(f"unsupported porcelain v2 record: {kind!r}")
        parts = record.split(b" ", 2)
        if len(parts) < 2 or len(parts[1]) != 2:
            raise ValueError("malformed porcelain v2 status record")
        code = parts[1]
        if kind == b"u":
            conflicts += 1
        if code[:1] != b".":
            staged += 1
        if code[1:2] != b".":
            worktree_changed += 1

    return {
        "total": total,
        "tracked": total - untracked,
        "staged": staged,
        "worktree": worktree_changed,
        "untracked": untracked,
        "conflicts": conflicts,
        "porcelainDigest": hashlib.sha256(raw_status).hexdigest(),
    }


def read_json_with_digest(path: Path) -> tuple[dict[str, Any], str]:
    raw = path.read_bytes()
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value, hashlib.sha256(raw).hexdigest()


def run_json_command(command: list[str]) -> tuple[int, dict[str, Any]]:
    try:
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=COMMAND_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return 124, {"ok": False, "status": "error", "reason": "timeout"}
    output = result.stdout.decode("utf-8", errors="replace").strip()
    if not output:
        return result.returncode, {
            "ok": False,
            "status": "error",
            "reason": "no-json-output",
        }
    try:
        value = json.loads(output)
    except json.JSONDecodeError:
        return result.returncode, {
            "ok": False,
            "status": "error",
            "reason": "invalid-json-output",
        }
    if not isinstance(value, dict):
        return result.returncode, {
            "ok": False,
            "status": "error",
            "reason": "non-object-json-output",
        }
    return result.returncode, value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ensure_no_active_package_transaction(package: Path) -> None:
    if any((package / journal).exists() for journal in PACKAGE_TRANSACTION_JOURNALS):
        raise RuntimeError("package transaction is active; retry after it finishes")


def require_dict(value: Any, description: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ValueError(f"expected object: {description}")
    return value


def require_list(value: Any, description: str) -> list[Any]:
    if not isinstance(value, list):
        raise ValueError(f"expected array: {description}")
    return value


def summarize_package(
    worktree: Path,
    package_path: str,
) -> dict[str, Any]:
    package = Path(package_path)
    if package.is_absolute():
        raise ValueError("package path must be relative to worktree")
    if ".." in package.parts:
        raise ValueError("package path must not contain '..'")
    package = (worktree / package).resolve(strict=True)
    try:
        package.relative_to(worktree)
    except ValueError as error:
        raise ValueError("package path escapes worktree") from error

    runtime_path = package / ".impl-package" / "runtime-state.json"
    binding_path = package / ".impl-package" / "revision-bindings.json"
    ensure_no_active_package_transaction(package)
    pre_read_digests = {
        "runtimeState": sha256_file(runtime_path),
        "revisionBindings": sha256_file(binding_path),
    }
    runtime, runtime_digest = read_json_with_digest(runtime_path)
    bindings, binding_digest = read_json_with_digest(binding_path)
    sidecar_digests = {
        "runtimeState": runtime_digest,
        "revisionBindings": binding_digest,
    }
    if pre_read_digests != sidecar_digests:
        raise RuntimeError("package sidecars changed during anchor capture; retry")
    ensure_no_active_package_transaction(package)

    if runtime.get("contractVersion") != bindings.get("contractVersion"):
        raise ValueError("runtime and revision binding contract versions differ")
    tickets = require_list(runtime.get("tickets"), f"{runtime_path}:tickets")
    ticket_states = Counter(
        str(ticket.get("state"))
        for ticket in tickets
        if isinstance(ticket, dict) and ticket.get("state") is not None
    )

    current = require_dict(bindings.get("current"), f"{binding_path}:current")
    decision_value = current.get("decision")
    decision = None if decision_value is None else require_dict(
        decision_value, f"{binding_path}:current.decision"
    )
    spec_value = current.get("spec")
    spec = None if spec_value is None else require_dict(
        spec_value, f"{binding_path}:current.spec"
    )
    attempt_value = current.get("attempt")
    attempt = None if attempt_value is None else require_dict(
        attempt_value, f"{binding_path}:current.attempt"
    )
    gate = require_dict(runtime.get("gate"), f"{runtime_path}:gate")
    tasks = require_list(runtime.get("tasks"), f"{runtime_path}:tasks")
    artifacts = require_list(runtime.get("artifacts"), f"{runtime_path}:artifacts")
    allocations = require_list(gate.get("allocations"), f"{runtime_path}:gate.allocations")
    entries = require_list(gate.get("entries"), f"{runtime_path}:gate.entries")

    workbench_root = Path(__file__).resolve().parents[3]
    validator = workbench_root / "skills" / "impl-package" / "scripts" / "impl_package_state.py"
    if not validator.is_file():
        raise ValueError(f"canonical package validator not found: {validator}")
    contract_exit, contract_status = run_json_command(
        [sys.executable, str(validator), "--package", str(package), "contract-status"]
    )
    if (
        contract_exit != 0
        or contract_status.get("ok") is not True
        or contract_status.get("status") != "current"
    ):
        raise RuntimeError(
            "canonical contract-status failed: "
            f"exit={contract_exit}, status={contract_status.get('status')}, "
            f"reason={contract_status.get('reason')}"
        )
    if sidecar_digests != {
        "runtimeState": sha256_file(runtime_path),
        "revisionBindings": sha256_file(binding_path),
    }:
        raise RuntimeError("package sidecars changed during anchor capture; retry")
    ensure_no_active_package_transaction(package)
    return {
        "path": str(package),
        "id": runtime.get("packageId"),
        "contractVersion": runtime.get("contractVersion"),
        "sidecarDigests": sidecar_digests,
        "binding": {
            "attempt": None if attempt is None else attempt.get("id"),
            "decision": None if decision is None else decision.get("revision"),
            "spec": None if spec is None else spec.get("revision"),
            "plan": None if attempt is None else attempt.get("revision"),
        },
        "runtime": {
            "tickets": len(tickets),
            "ticketStates": dict(sorted(ticket_states.items())),
            "tasks": len(tasks),
            "artifacts": len(artifacts),
            "gateAllocations": len(allocations),
            "gateEntries": len(entries),
        },
        "canonical": {
            "contractStatus": {
                "exitCode": contract_exit,
                "ok": contract_status.get("ok"),
                "status": contract_status.get("status"),
                "contractVersion": contract_status.get("contractVersion"),
            },
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit a compact, file-name-free state summary for handoff anchoring."
    )
    parser.add_argument("--worktree", required=True)
    parser.add_argument("--expected-head")
    parser.add_argument("--package-path")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    worktree = Path(args.worktree).resolve(strict=True)
    head = decode_scalar(run_git(worktree, "rev-parse", "HEAD"))
    branch = decode_scalar(run_git(worktree, "rev-parse", "--abbrev-ref", "HEAD"))
    expected_head = args.expected_head.lower() if args.expected_head else None

    dirty = summarize_dirty(worktree)
    result: dict[str, Any] = {
        "schemaVersion": 1,
        "worktree": str(worktree),
        "branch": branch,
        "detached": branch == "HEAD",
        "head": head,
        "headMatchesExpected": None if expected_head is None else head.lower() == expected_head,
        "dirty": dirty,
    }
    if args.package_path:
        result["package"] = summarize_package(
            worktree,
            args.package_path,
        )

    final_head = decode_scalar(run_git(worktree, "rev-parse", "HEAD"))
    final_branch = decode_scalar(run_git(worktree, "rev-parse", "--abbrev-ref", "HEAD"))
    final_dirty = summarize_dirty(worktree)
    if (head, branch, dirty) != (final_head, final_branch, final_dirty):
        raise RuntimeError("Git state changed during anchor capture; retry")
    if args.package_path:
        package = Path(result["package"]["path"])
        ensure_no_active_package_transaction(package)
        final_sidecar_digests = {
            "runtimeState": sha256_file(package / ".impl-package" / "runtime-state.json"),
            "revisionBindings": sha256_file(
                package / ".impl-package" / "revision-bindings.json"
            ),
        }
        if result["package"]["sidecarDigests"] != final_sidecar_digests:
            raise RuntimeError("package sidecars changed during anchor capture; retry")
        ensure_no_active_package_transaction(package)

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"compact-anchor: {error}", file=sys.stderr)
        raise SystemExit(2) from error
