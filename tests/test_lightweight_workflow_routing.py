from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(relative_path: str) -> str:
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_tdd_reuses_approved_contract_before_tracer_bullet() -> None:
    text = read("skills/tdd/SKILL.md")

    assert "Reuse the interface and prioritized behaviors from a current approved spec" in text
    assert "do not ask for a second approval before the first tracer bullet" in text
    assert "materially changed test contract" in text


def test_discuss_ledger_skips_single_pass_reviews_and_handoffs() -> None:
    text = read("skills/discuss-ledger/SKILL.md")

    assert "## Trigger boundary" in text
    assert "ordinary one-pass review" in text
    assert "one-way subagent handoff" in text
    assert "do not create a ledger" in text
