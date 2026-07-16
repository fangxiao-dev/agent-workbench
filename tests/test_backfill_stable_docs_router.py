from __future__ import annotations

import unittest
from pathlib import Path


SKILL = Path(__file__).resolve().parents[1] / "skills" / "backfill-stable-docs" / "SKILL.md"


class RouterContractTest(unittest.TestCase):
    def test_default_audit_is_read_only(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("默认执行 audit", text)
        self.assertIn("只允许配置 `records.reports` 目录下的新报告", text)

    def test_apply_requires_report_and_item_ids(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("apply 必须同时给出 report 路径和 owner 批准的精确 item ID", text)
        self.assertIn("“全部处理”不是批准清单", text)

    def test_verify_cannot_implicitly_apply(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("不补写内容、不隐式 apply", text)

    def test_pending_registry_is_primary_source(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("`_pending.md` 登记队列，不是重新发现", text)
        self.assertIn("gap-catching", text)

    def test_package_retirement_is_routed_and_destructive(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("package-retirement-runbook.md", text)
        self.assertIn("Package Retirement", text)
        self.assertIn("destructive-apply", text)

    def test_three_layer_contract_keeps_context_optional(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("`stableDocs.systemKnowledge`", text)
        self.assertIn("`stableDocs.contextKnowledge` 可选", text)
        self.assertIn("`stableDocs.moduleKnowledge`", text)
        self.assertIn("保留 `module-knowledge/`", text)

    def test_target_branch_and_cold_start_have_distinct_contracts(self) -> None:
        text = SKILL.read_text(encoding="utf-8")
        self.assertIn("`targetBranch` 与主工作区基准承担不同职责", text)
        self.assertIn("不自动 fetch", text)
        self.assertIn("非阻塞 `cold-start` owner decision", text)


if __name__ == "__main__":
    unittest.main()
