from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "discuss-ledger" / "SKILL.md"
REFERENCES = ROOT / "skills" / "discuss-ledger" / "references"


def test_discuss_ledger_skill_routes_large_details_to_references() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "## References" in text
    assert "references/orchestrator.md" in text
    assert "references/claude-code-noninteractive.md" in text
    assert "references/ledger-cli.md" in text

    assert (REFERENCES / "orchestrator.md").is_file()
    assert (REFERENCES / "claude-code-noninteractive.md").is_file()
    assert (REFERENCES / "ledger-cli.md").is_file()


def test_discuss_ledger_core_instructions_stay_in_skill_body() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "Do not hand-edit the ledger's YAML, table, or section structure" in text
    assert "read → promote settled points → respond with disagreements → end the turn" in text
    assert "Only create/modify the single `discuss-<slug>.md` ledger" in text
