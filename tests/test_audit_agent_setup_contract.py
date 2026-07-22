from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_audit_defaults_to_targeted_scope_and_requires_explicit_expansion() -> None:
    skill = read("skills/audit-agent-setup/SKILL.md")
    agent = read("agents/audit-agent-setup/agent.md")
    command = read("commands/audit.md")

    for text in (skill, agent, command):
        assert "--full" in text
        assert "--include-global" in text
        assert "Do not read user-level host state by default" in text or "Never inspect them by default" in text or "Never inspect user-level host state without `--include-global`" in text

    assert "Targeted audit (default)" in skill
    assert "Do not use it to write or repair setup files" in skill
    assert "limit host-specific project surfaces to the same hosts" in skill
    assert "never modify files" in agent


def test_audit_evals_cover_scope_and_trigger_boundaries() -> None:
    evals = json.loads(read("skills/audit-agent-setup/evals/evals.json"))

    assert len(evals["evals"]) == 7
    assert len(evals["trigger_evals"]) == 20
    assert sum(item["should_trigger"] for item in evals["trigger_evals"]) == 10
    assert sum(not item["should_trigger"] for item in evals["trigger_evals"]) == 10
    assert "--full --include-global" in evals["evals"][-1]["prompt"]
