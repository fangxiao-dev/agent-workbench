#!/usr/bin/env python3
"""Deterministic AC-11..AC-15 fixtures for policy, lease, ledger and routing seams."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from codex_harness_policy import PolicyError, decision_audience, load_runtime_policy
from codex_harness_runtime import LedgerIntegrityError, LeaseConflict, ResourceLedger, ThreadLease, route_decision


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    bundle = load_runtime_policy(root)
    policy_checks = {"normal": bundle["identity"]["schema_version"] == "codex-harness.runtime-policy.v1.3", "maturity": bundle["identity"]["maturity"] == "design_baseline"}
    with tempfile.TemporaryDirectory(prefix="codex-harness-runtime-fixture-") as temporary:
        temporary_root = Path(temporary)
        malformed = temporary_root / "malformed.json"
        malformed.write_text("{\"schema_version\": \"codex-harness.runtime-policy.v1.3\"}\n", encoding="utf-8")
        try:
            load_runtime_policy(root, policy_path=malformed)
        except PolicyError:
            policy_checks["malformed_rejected"] = True
        else:
            policy_checks["malformed_rejected"] = False
        unknown_maturity = json.loads((root / "skills/codex-harness/assets/codex-harness-runtime-policy.v1.3.json").read_text(encoding="utf-8"))
        unknown_maturity["maturity"] = "future_runtime"
        unknown_path = temporary_root / "unknown-maturity.json"
        unknown_path.write_text(json.dumps(unknown_maturity), encoding="utf-8")
        try:
            load_runtime_policy(root, policy_path=unknown_path)
        except PolicyError:
            policy_checks["unknown_maturity_rejected"] = True
        else:
            policy_checks["unknown_maturity_rejected"] = False

        artifacts = temporary_root / "artifacts"
        first = ThreadLease(artifacts, "thread-1", "run-1", ttl_seconds=60)
        first.acquire()
        second = ThreadLease(artifacts, "thread-1", "run-2", ttl_seconds=60)
        try:
            second.acquire()
        except LeaseConflict:
            lease_checks = {"contention_rejected": True}
        else:
            lease_checks = {"contention_rejected": False}
        try:
            second.release()
        except LeaseConflict:
            lease_checks["wrong_token_rejected"] = True
        else:
            lease_checks["wrong_token_rejected"] = False
        first.heartbeat()
        first.release()
        lease_checks["released"] = not first.path.exists()
        stale = ThreadLease(artifacts, "thread-stale", "run-stale", ttl_seconds=1)
        stale_payload = stale._payload()
        stale_payload["expires_at"] = 0
        stale.path.parent.mkdir(parents=True, exist_ok=True)
        stale.path.write_text(json.dumps(stale_payload), encoding="utf-8")
        try:
            ThreadLease(artifacts, "thread-stale", "run-new").acquire()
        except LeaseConflict as exc:
            lease_checks["expired_reclaim_fails_closed"] = "reconcile" in str(exc)
        else:
            lease_checks["expired_reclaim_fails_closed"] = False
        lease_checks["orphan_reconcile"] = any(item.get("reason") == "expired" for item in ThreadLease.reconcile(artifacts))

        ledger_path = artifacts / "run-1.resource-ledger.jsonl"
        ledger = ResourceLedger(ledger_path, "run-1")
        ledger.append("thread", "thread-1", "started", "fixture")
        ledger.append("turn", "turn-1", "started", "fixture")
        disposition = ledger.terminal_disposition("promote", "fixture")
        replay = ledger.terminal_disposition("promote", "fixture")
        try:
            ledger.append("process", "process-1", "closed", "post-terminal fixture")
        except LedgerIntegrityError:
            terminal_frozen = True
        else:
            terminal_frozen = False
        ledger_checks = {"chain_valid": ledger.verify(), "disposition_replay_idempotent": disposition["event_id"] == replay["event_id"], "terminal_is_final": terminal_frozen}
        lines = ledger_path.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[1])
        tampered["operation"] = "tampered"
        lines[1] = json.dumps(tampered, sort_keys=True)
        ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        try:
            ledger.terminal_disposition("promote", "fixture")
        except LedgerIntegrityError:
            ledger_checks["tampered_replay_rejected"] = True
        else:
            ledger_checks["tampered_replay_rejected"] = False
        try:
            ResourceLedger(ledger_path, "run-1")
        except LedgerIntegrityError:
            ledger_checks["tamper_rejected"] = True
        else:
            ledger_checks["tamper_rejected"] = False

    routing_checks = {
        "same_task_harness": decision_audience(bundle, "same_task_correction") == "harness",
        "scope_owner": decision_audience(bundle, "scope_change") == "owner",
        "typed_request": route_decision(bundle, "authority_expansion", request_id="req-1")["audience"] == "owner",
    }
    checks = {**policy_checks, **lease_checks, **ledger_checks, **routing_checks}
    passed = all(checks.values())
    print(json.dumps({"status": "passed" if passed else "failed", "policy_identity": bundle["identity"], "checks": checks}, ensure_ascii=False, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
