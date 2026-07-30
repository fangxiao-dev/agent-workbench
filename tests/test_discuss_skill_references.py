from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "discuss-ledger" / "SKILL.md"
REFERENCES = ROOT / "skills" / "discuss-ledger" / "references"


def test_discuss_ledger_skill_routes_modes_to_references() -> None:
    text = SKILL.read_text(encoding="utf-8")

    assert "Discuss Ledger Router" in text
    assert "Blind Opening" in text
    assert "Blind Opening + Ledger" in text
    assert "references/blind-opening.md" in text
    assert "references/ledger-discussion.md" in text
    assert "references/blind-opening-plus-ledger.md" in text
    assert "references/router.md" in text
    assert "--claude-effort" in text
    assert "大计划" in text and "小计划" in text

    assert (REFERENCES / "blind-opening.md").is_file()
    assert (REFERENCES / "ledger-discussion.md").is_file()
    assert (REFERENCES / "blind-opening-plus-ledger.md").is_file()
    assert (REFERENCES / "orchestrator.md").is_file()
    assert (REFERENCES / "claude-code-noninteractive.md").is_file()
    assert (REFERENCES / "ledger-cli.md").is_file()
    assert (REFERENCES / "ledger-participant-prompt.md").is_file()
    assert (REFERENCES / "router.md").is_file()


def test_normal_ledger_reference_preserves_deterministic_writer_boundary() -> None:
    text = SKILL.read_text(encoding="utf-8")
    normal = (REFERENCES / "ledger-discussion.md").read_text(encoding="utf-8")

    assert "Existing Discuss Ledger triggers default to normal Ledger" in text
    assert "Do not hand-edit those structures" in normal
    assert "promote genuinely settled points first" in normal
    assert "ledger-participant-prompt.md" in normal
