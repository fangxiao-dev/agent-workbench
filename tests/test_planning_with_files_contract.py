from __future__ import annotations

import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "skills" / "planning-with-files" / "SKILL.md"


class PlanningWithFilesContractTest(unittest.TestCase):
    def test_existing_state_owner_prevents_second_ledger(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("## Ledger Owner Selection", text)
        self.assertIn("Do not create a second `task_plan.md`/`findings.md`/`progress.md` ledger beside it.", text)
        self.assertIn("only when the task is expected to cross sessions and no existing state owner can carry the task", text)

    def test_persistence_rules_only_apply_to_active_ledger_owner(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("When this Skill owns a complex task", text)
        self.assertIn("when this Skill is the active ledger owner", text)
        self.assertNotIn("After ANY discovery", text)


if __name__ == "__main__":
    unittest.main()
