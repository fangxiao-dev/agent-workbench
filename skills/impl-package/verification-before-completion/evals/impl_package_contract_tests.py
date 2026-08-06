#!/usr/bin/env python3
"""Completion contract smoke checks."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    skill = (ROOT / "verification-before-completion/SKILL.md").read_text(encoding="utf-8")
    gate = (ROOT / "dev-with-track/assets/templates/gate.md").read_text(encoding="utf-8")
    state = (ROOT / "references/impl-package-current-state.md").read_text(encoding="utf-8")
    assert "implemented, not verified" in skill
    assert "Comparison commit" in gate
    assert "pass|fail|blocked|defer" in gate
    assert '"formatVersion": "3.4"' in state


if __name__ == "__main__":
    main()
