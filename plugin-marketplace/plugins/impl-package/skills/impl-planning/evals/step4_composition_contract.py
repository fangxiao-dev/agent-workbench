#!/usr/bin/env python3
"""Static contract checks for the lightweight Impl-Package format."""

from __future__ import annotations

from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parents[2]
PLUGIN_ROOT = Path(__file__).resolve().parents[3]


def read(relative: str) -> str:
    root = PLUGIN_ROOT if relative.startswith("references/") else SKILLS_ROOT
    return (root / relative).read_text(encoding="utf-8")


def main() -> None:
    plan = read("impl-planning/assets/templates/plan.md")
    ticket = read("to-tickets/assets/templates/ticket.md")
    dag = read("dev-with-track/assets/templates/dag.md")
    gate = read("dev-with-track/assets/templates/gate.md")
    state = read("references/impl-package-current-state.md")

    for field in ("Attempt ID", "Composition"):
        assert field in plan, f"plan missing {field}"
    assert "tickets=true, dag=false" in plan
    assert "DAG" in plan and "旧 package" in plan
    assert ".impl-package/state.json" in ticket
    assert ".impl-package/state.json" in dag
    for field in ("Verdict", "Attempt", "Comparison commit", "Evidence", "Durable Deltas"):
        assert field in gate, f"gate missing {field}"
    for field in ('"attempt"', '"attemptHistory"', '"predecessors"', '"tickets"', '"evidenceIndex"', '"activeCheckpoints"'):
        assert field in state, f"current state reference missing {field}"
    assert '"tasks"' not in state and '"resume"' not in state


if __name__ == "__main__":
    main()
