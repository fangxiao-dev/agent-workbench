from __future__ import annotations

import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "skills" / "backfill-stable-docs" / "SKILL.md"


class RouterContractTest(unittest.TestCase):
    def test_default_audit_is_read_only(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("默认执行 audit", text)
        self.assertIn("只允许 `_compaction/` 下的新报告", text)

    def test_apply_requires_report_and_item_ids(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("apply 必须同时给出 audit/report 路径和 owner 批准的精确 item ID", text)
        self.assertIn("“全部处理”不是批准清单", text)

    def test_verify_cannot_implicitly_apply(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("不补写内容、不隐式 apply", text)


if __name__ == "__main__":
    unittest.main()
