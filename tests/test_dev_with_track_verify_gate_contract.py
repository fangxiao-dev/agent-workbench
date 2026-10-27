from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace/plugins/impl-package"


def read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_verify_and_gate_owns_claim_evidence_rules_and_execution_boundaries_is_gone() -> None:
    dev = read("skills/dev-with-track/SKILL.md")
    gate = dev.split("## Verify and Gate", 1)[1]

    assert not (PLUGIN / "skills/execution-boundaries").exists()
    for marker in (
        "不能宽于 evidence",
        "子切片",
        "Integrated, gate open",
        "gate-before-merge",
        "process violation",
        "implemented, not verified",
        "lint≠build",
        "unit≠integration",
        "mock 不是真实 browser/provider/E2E",
        "重审 delta",
        "patch Attempt",
        "对照实际 diff",
    ):
        assert marker in gate, marker
    for marker in ("push、merge、发布", "独立授权", "rollback", "可观察结果"):
        assert marker in dev, marker
    assert "Preflight: READY" not in dev
    assert "Wave 1" not in dev
    assert not (PLUGIN / "skills/dev-with-track/references/authorization-contract.md").exists()
    assert any(
        e["prompt"].startswith("Feature worktree") for e in json.loads(read("skills/dev-with-track/evals/evals.json"))["evals"]
    )


def test_direct_callers_drop_retired_d1_d2_routes() -> None:
    texts = "\n".join(
        (
            read("skills/dev-with-track/SKILL.md"),
            read("skills/dev-with-track/references/runtime-protocol.md"),
            read("skills/impl-planning/SKILL.md"),
            read("skills/plan-review/SKILL.md"),
            read("skills/impl-package/SKILL.md"),
            read("skills/dev-with-track/situations.yaml"),
            read("scripts/impl_package_runtime/protocols.json"),
        )
    )
    for retired in ("execution-boundaries", "standing-bookkeeper", "Ticket 激活 preflight", "ticket.readiness.evidence-lane-preflight", "记账回执"):
        assert retired not in texts

    protocols = json.loads(read("scripts/impl_package_runtime/protocols.json"))
    assert "ticket.readiness.evidence-lane-preflight" not in protocols
