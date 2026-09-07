from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PLUGIN = ROOT / "plugin-marketplace/plugins/impl-package"


def read(relative: str) -> str:
    return (PLUGIN / relative).read_text(encoding="utf-8")


def test_execution_boundaries_keeps_auth_completion_and_thin_exception_path() -> None:
    boundaries = read("skills/execution-boundaries/SKILL.md")
    authorization = read("skills/execution-boundaries/references/authorization-contract.md")

    assert "异常对账" in boundaries
    assert "主控直接核对" in boundaries
    assert "progressive-system-evidence.md" in boundaries
    assert "parallel-work-admission.md" in boundaries
    assert "references/authorization-contract.md" in boundaries
    assert "渐进读取常见误判" in authorization
    for retired in ("standing bookkeeper", "bookkeeper", "Ticket 首次激活", "slow path", "bookkeeper-receipts.jsonl"):
        assert retired not in boundaries
    assert not (PLUGIN / "skills/execution-boundaries/references/role.md").exists()
    assert not (PLUGIN / "skills/standing-bookkeeper/evals/evals.json").exists()


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
    for retired in ("standing-bookkeeper", "Ticket 激活 preflight", "ticket.readiness.evidence-lane-preflight", "记账回执"):
        assert retired not in texts

    protocols = json.loads(read("scripts/impl_package_runtime/protocols.json"))
    assert "ticket.readiness.evidence-lane-preflight" not in protocols
