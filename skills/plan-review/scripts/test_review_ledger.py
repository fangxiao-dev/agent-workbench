from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest import mock


MODULE_PATH = Path(__file__).with_name("review_ledger.py")
SPEC = importlib.util.spec_from_file_location("review_ledger", MODULE_PATH)
assert SPEC and SPEC.loader
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class ReviewLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.target = self.root / "plan.md"
        self.target.write_text("# Plan\n", encoding="utf-8")
        self.evidence_a = self.root / "a.py"
        self.evidence_b = self.root / "b.py"
        self.evidence_a.write_text("A = 1\n", encoding="utf-8")
        self.evidence_b.write_text("B = 1\n", encoding="utf-8")
        self.ledger_path = ledger.init_ledger(
            [str(self.target)], temp_root=self.root / "runtime"
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def materiality(self, findings: dict[str, list[str]] | None = None) -> None:
        findings = findings or {}
        for dimension in ledger.DIMENSIONS:
            finding_ids = findings.get(dimension, [])
            record = {
                "type": "materiality",
                "dimension": dimension,
                "status": "finding" if finding_ids else "reviewed",
                "reason": f"checked {dimension}",
            }
            if finding_ids:
                record["finding_ids"] = finding_ids
            ledger.record_ledger(
                self.ledger_path,
                record,
            )
        ledger.record_ledger(
            self.ledger_path,
            {"type": "review_state", "outside_voice": "complete"},
        )

    def finding(
        self,
        finding_id: str = "ENG-T1",
        dependency: Path | None = None,
        *,
        owner_gate: str = "not_required",
        resolution: dict | None = None,
        severity: str = "P1",
        kind: str = "file",
    ) -> dict:
        return {
            "type": "finding",
            "id": finding_id,
            "section": "tests",
            "claim": "missing failure test",
            "risk": "failure can escape",
            "severity": severity,
            "confidence": "high — direct repository evidence",
            "evidence": [{"kind": "repository-fact", "summary": "no assertion"}],
            "evidence_dependencies": [
                {"path": str(dependency or self.evidence_a), "kind": kind}
            ],
            "recommendation": "add the failure test",
            "owner_gate": owner_gate,
            "resolution": resolution,
        }

    @staticmethod
    def owner_source(reference: str = "turn-1") -> dict:
        return {
            "actor": "owner",
            "channel": "chat",
            "reference": reference,
            "statement": "apply this manifest",
        }

    def authorization_source(self, manifest_hash: str, reference: str = "turn-1") -> dict:
        return {
            **self.owner_source(reference),
            "action": "apply",
            "manifest_hash": manifest_hash,
            "statement": f"apply {manifest_hash}",
        }

    def abandonment_source(self, run_id: str, reference: str = "turn-abandon") -> dict:
        return {
            **self.owner_source(reference),
            "action": "abandon",
            "run_id": run_id,
            "statement": f"abandon {run_id}",
        }

    def test_init_reuses_the_current_candidate_run(self) -> None:
        second = ledger.init_ledger([str(self.target)], temp_root=self.root / "runtime")
        self.assertEqual(self.ledger_path, second)
        state = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.assertTrue(state["run"]["run_id"].startswith("epr-"))
        self.assertEqual(state["run"]["status"], "active")
        self.assertEqual(state["baseline"]["targets"][0]["sha256"], ledger._sha256_file(self.target))

    def test_required_skill_resources_exist_and_are_readable(self) -> None:
        skill_root = MODULE_PATH.parent.parent
        required = [
            "references/scope-review.md",
            "references/architecture-review.md",
            "references/code-quality-review.md",
            "references/test-review.md",
            "references/performance-review.md",
            "references/decision-policy.md",
            "references/ledger-records.md",
            "references/final-report.md",
            "references/subagent-prompts.md",
        ]
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        for relative in required:
            with self.subTest(relative=relative):
                resource = skill_root / relative
                self.assertTrue(resource.is_file(), f"missing required skill resource: {relative}")
                self.assertTrue(resource.read_text(encoding="utf-8").strip())
                self.assertIn(relative, skill_text)
        for contract in [
            "user-invocable: true",
            "**Invocation gate：**",
            "不得因为请求包含",
            "## 工程判断基线",
            "blast radius",
            "成熟、简单、仓库已有的方案",
            "可重复机制与证据",
            "构建、测试、调试、发布和长期维护成本",
        ]:
            with self.subTest(contract=contract):
                self.assertIn(contract, skill_text)

    def test_skill_is_explicit_or_orchestrated_only(self) -> None:
        skill_root = MODULE_PATH.parent.parent
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        openai_text = (skill_root / "agents" / "openai.yaml").read_text(encoding="utf-8")
        evals = json.loads((skill_root / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]
        self.assertIn("user-invocable: true", skill_text)
        self.assertNotIn("disable-model-invocation: true", skill_text)
        self.assertIn("allow_implicit_invocation: false", openai_text)
        self.assertIn("仅当用户明确点名", skill_text)
        self.assertIn("上游编排合同", skill_text)
        negative = next(item for item in evals if item["id"] == 12)
        self.assertNotIn("$plan-review", negative["prompt"])
        for item in evals:
            if item["id"] != 12:
                with self.subTest(eval_id=item["id"]):
                    self.assertIn("$plan-review", item["prompt"])

    def test_bundle_admission_is_explicit_and_nonpersistent(self) -> None:
        skill_root = MODULE_PATH.parent.parent
        skill_text = (skill_root / "SKILL.md").read_text(encoding="utf-8")
        prompt_text = (skill_root / "references" / "subagent-prompts.md").read_text(
            encoding="utf-8"
        )
        report_text = (skill_root / "references" / "final-report.md").read_text(
            encoding="utf-8"
        )
        evals = json.loads((skill_root / "evals" / "evals.json").read_text(encoding="utf-8"))["evals"]
        for contract in [
            "## Bundle-admission mode（仅由明确编排选择）",
            "mode=bundle-admission",
            "用户直接调用 `$plan-review` 时一律走下方既有完整 workflow",
            "admission mode 不创建 ledger、manifest、receipt 或跨 session state",
            "不能把 `full review`、`revise` 或 `unavailable` 降级为 `ready`",
            "它们描述计划所处理问题的固有风险性质",
            "必须把 `ready` 升级为 `full review`",
        ]:
            with self.subTest(contract=contract):
                self.assertIn(contract, skill_text)
        self.assertIn("## Bundle admission：由 `impl-planning` 启动的 fresh reviewer", prompt_text)
        self.assertIn("Additional Outside Voice=no", prompt_text)
        self.assertIn("Signal 描述固有风险", prompt_text)
        self.assertIn("## Bundle admission 输出", report_text)
        self.assertIn("即使不阻塞也不能省略", report_text)
        by_id = {item["id"]: item for item in evals}
        for eval_id in (14, 15, 16, 17, 18):
            with self.subTest(eval_id=eval_id):
                self.assertIn(eval_id, by_id)
                self.assertIn("$plan-review mode=bundle-admission", by_id[eval_id]["prompt"])

    def test_authorization_contexts_keep_one_bundle_checkpoint(self) -> None:
        workbench = MODULE_PATH.parents[3]
        contract = (
            workbench / "skills" / "impl-package" / "references" / "impl-package-composition-contract.md"
        ).read_text(encoding="utf-8")
        planning = (
            workbench / "skills" / "impl-package" / "impl-planning" / "SKILL.md"
        ).read_text(encoding="utf-8")
        dev_with_track = (
            workbench / "skills" / "impl-package" / "dev-with-track" / "SKILL.md"
        ).read_text(encoding="utf-8")
        do_review = (workbench / "skills" / "do-review" / "SKILL.md").read_text(encoding="utf-8")
        plan_review = (workbench / "skills" / "plan-review" / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("### 计划拆解 bundle 的唯一 owner checkpoint", contract)
        self.assertIn("一次 approval 覆盖 Attempt、P revision 及全部 earned Ticket/DAG", contract)
        self.assertIn("candidate → 一次适用 review → 一次完整 bundle approval → 自动 register/route", planning)
        self.assertIn("ledger、manifest、reviewer 调度、旧 run、机械 projection 与验证命令不得进入 wave", plan_review)
        self.assertIn("## 执行授权后的自动收口（不得二次请示）", dev_with_track)
        self.assertIn("Do not create, request, or infer owner approval", do_review)

    def test_discover_lists_only_matching_active_runs(self) -> None:
        second = ledger.init_ledger([str(self.target)], temp_root=self.root / "runtime")
        other_target = self.root / "other.md"
        other_target.write_text("# Other\n", encoding="utf-8")
        ledger.init_ledger([str(other_target)], temp_root=self.root / "runtime")
        result = ledger.discover_ledgers(self.target, temp_root=self.root / "runtime")
        self.assertEqual(
            {item["run_id"] for item in result["runs"]},
            {ledger.status_ledger(self.ledger_path)["run_id"], ledger.status_ledger(second)["run_id"]},
        )
        self.assertEqual(result["invalid"], [])
        self.assertTrue(all(item["run_status"] == "active" for item in result["runs"]))

    def test_resume_supersedes_a_changed_candidate_without_owner_input(self) -> None:
        other_target = self.root / "other.md"
        other_target.write_text("# Other\n", encoding="utf-8")
        with self.assertRaisesRegex(ledger.LedgerError, "does not match"):
            ledger.resume_ledger(self.ledger_path, other_target)
        self.target.write_text("# Changed\n", encoding="utf-8")
        status = ledger.resume_ledger(self.ledger_path, self.target)
        self.assertEqual(status["run_status"], "superseded")
        self.assertTrue(status["baseline_stale"])
        self.assertEqual(status["supersession"]["reason"], "candidate-or-baseline-changed")

    def test_init_supersedes_changed_baselines_and_preserves_audit_history(self) -> None:
        self.materiality()
        ledger.finalize_clearance(self.ledger_path)
        ledger.present_candidate(self.ledger_path)
        manifest_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            manifest_hash,
            self.authorization_source(manifest_hash),
        )
        self.target.write_text("# Revised candidate\n", encoding="utf-8")

        replacement = ledger.init_ledger([str(self.target)], temp_root=self.root / "runtime")
        old_status = ledger.status_ledger(self.ledger_path)
        self.assertEqual(old_status["run_status"], "superseded")
        self.assertFalse(old_status["authorized"])
        self.assertTrue(old_status["clearance"]["stale"])
        self.assertEqual(old_status["supersession"]["replacement_run_id"], ledger.status_ledger(replacement)["run_id"])
        self.assertEqual(
            [item["run_id"] for item in ledger.discover_ledgers(self.target, temp_root=self.root / "runtime")["runs"]],
            [ledger.status_ledger(replacement)["run_id"]],
        )
        closed = ledger.discover_ledgers(
            self.target, temp_root=self.root / "runtime", include_closed=True
        )["runs"]
        self.assertIn("superseded", [item["run_status"] for item in closed])
        with self.assertRaisesRegex(ledger.LedgerError, "superseded review run"):
            ledger.verify_clearance(self.ledger_path)

    def test_init_supersedes_when_a_reference_baseline_changes(self) -> None:
        reference_run = ledger.init_ledger(
            [str(self.target)],
            [str(self.evidence_a)],
            temp_root=self.root / "runtime",
        )
        self.evidence_a.write_text("A = 2\n", encoding="utf-8")

        replacement = ledger.init_ledger(
            [str(self.target)],
            [str(self.evidence_a)],
            temp_root=self.root / "runtime",
        )
        status = ledger.status_ledger(reference_run)
        self.assertEqual(status["run_status"], "superseded")
        self.assertEqual(status["supersession"]["reason"], "candidate-or-baseline-changed")
        self.assertEqual(status["supersession"]["replacement_run_id"], ledger.status_ledger(replacement)["run_id"])

    def test_init_does_not_reuse_a_candidate_that_changes_during_reconciliation(self) -> None:
        original_verify = ledger._verify_in_place
        changed = False

        def change_before_verify(state: dict[str, object]) -> bool:
            nonlocal changed
            if not changed:
                self.target.write_text("# Changed during reconcile\n", encoding="utf-8")
                changed = True
            return original_verify(state)

        with mock.patch.object(ledger, "_verify_in_place", side_effect=change_before_verify):
            replacement = ledger.init_ledger([str(self.target)], temp_root=self.root / "runtime")
        old_status = ledger.status_ledger(self.ledger_path)
        self.assertEqual(old_status["run_status"], "superseded")
        self.assertNotEqual(replacement, self.ledger_path)
        self.assertEqual(
            ledger.status_ledger(replacement)["baseline_stale"],
            False,
        )
        self.assertEqual(
            json.loads(replacement.read_text(encoding="utf-8"))["baseline"]["targets"][0]["sha256"],
            ledger._sha256_file(self.target),
        )

    def test_supersession_points_to_a_reused_current_run(self) -> None:
        self.target.write_text("# New candidate\n", encoding="utf-8")
        current_directory = self.root / "runtime" / "current-run"
        current_directory.mkdir()
        current_path = current_directory / "ledger.json"
        current = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        current["run"]["run_id"] = "epr-current"
        current["run"]["created_at"] = "2099-01-01T00:00:00+00:00"
        current["baseline"]["targets"][0]["sha256"] = ledger._sha256_file(self.target)
        current_path.write_text(json.dumps(current), encoding="utf-8")

        reused = ledger.init_ledger([str(self.target)], temp_root=self.root / "runtime")
        self.assertEqual(reused, current_path.resolve())
        supersession = ledger.status_ledger(self.ledger_path)["supersession"]
        self.assertEqual(supersession["replacement_run_id"], "epr-current")

    def test_abandon_preserves_ledger_and_removes_it_from_unfinished_discovery(self) -> None:
        before_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        run_id = ledger.status_ledger(self.ledger_path)["run_id"]
        status = ledger.abandon_ledger(
            self.ledger_path,
            self.abandonment_source(run_id),
        )
        self.assertEqual(status["run_status"], "abandoned")
        self.assertEqual(status["manifest_hash"], before_hash)
        self.assertTrue(self.ledger_path.exists())
        self.assertEqual(
            ledger.discover_ledgers(self.target, temp_root=self.root / "runtime")["runs"],
            [],
        )
        closed = ledger.discover_ledgers(
            self.target,
            temp_root=self.root / "runtime",
            include_closed=True,
        )["runs"]
        self.assertEqual([item["run_status"] for item in closed], ["abandoned"])
        with self.assertRaisesRegex(ledger.LedgerError, "abandoned review run"):
            ledger.resume_ledger(self.ledger_path, self.target)

    def test_abandon_requires_exact_owner_bound_run_id(self) -> None:
        run_id = ledger.status_ledger(self.ledger_path)["run_id"]
        source = self.abandonment_source("wrong-run")
        with self.assertRaisesRegex(ledger.LedgerError, "exact run id"):
            ledger.abandon_ledger(self.ledger_path, source)
        source = self.abandonment_source(run_id)
        source["action"] = "apply"
        with self.assertRaisesRegex(ledger.LedgerError, "action=abandon"):
            ledger.abandon_ledger(self.ledger_path, source)

    def test_candidate_is_not_a_ledger_record(self) -> None:
        with self.assertRaisesRegex(ledger.LedgerError, "cannot be recorded"):
            ledger.record_ledger(self.ledger_path, {"type": "candidate", "claim": "maybe"})

    def test_all_materiality_dimensions_are_required_for_authorization(self) -> None:
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "materiality scan"):
            ledger.authorize_ledger(
                self.ledger_path,
                current_hash,
                self.authorization_source(current_hash),
            )
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        status = ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))
        self.assertTrue(status["authorized"])

    def test_formal_finding_requires_evidence_dependency(self) -> None:
        record = self.finding()
        record["evidence_dependencies"] = []
        with self.assertRaisesRegex(ledger.LedgerError, "evidence_dependencies|evidence dependencies"):
            ledger.record_ledger(self.ledger_path, record)

    def test_formal_finding_requires_comparable_confidence(self) -> None:
        record = self.finding()
        del record["confidence"]
        with self.assertRaisesRegex(ledger.LedgerError, "confidence"):
            ledger.record_ledger(self.ledger_path, record)

    def test_owner_gate_rejects_agent_resolution(self) -> None:
        record = self.finding(
            owner_gate="required",
            resolution={"state": "accepted", "authority": "agent"},
        )
        with self.assertRaisesRegex(ledger.LedgerError, "owner-gated"):
            ledger.record_ledger(self.ledger_path, record)
        record["resolution"] = {
            "state": "accepted",
            "authority": "owner",
            "source": self.owner_source(),
        }
        state = ledger.record_ledger(self.ledger_path, record)
        self.assertEqual(state["findings"]["ENG-T1"]["resolution"]["authority"], "owner")

    def test_authorization_rejects_unresolved_owner_gate(self) -> None:
        ledger.record_ledger(
            self.ledger_path,
            self.finding(owner_gate="required"),
        )
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "unresolved owner-gated"):
            ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))

    def test_authorization_rejects_deferred_p0_finding(self) -> None:
        ledger.record_ledger(
            self.ledger_path,
            self.finding(
                severity="P0",
                resolution={"state": "deferred", "authority": "agent"},
            ),
        )
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "unresolved P0"):
            ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))

    def test_authorization_rejects_pending_p0_finding(self) -> None:
        ledger.record_ledger(self.ledger_path, self.finding(severity="P0"))
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "unresolved P0"):
            ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))

    def test_authorization_rejects_rejected_p0_finding(self) -> None:
        ledger.record_ledger(
            self.ledger_path,
            self.finding(
                severity="P0",
                resolution={"state": "rejected", "authority": "agent"},
            ),
        )
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "unresolved P0"):
            ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))

    def test_authorization_accepts_resolved_p0_finding(self) -> None:
        ledger.record_ledger(
            self.ledger_path,
            self.finding(
                severity="P0",
                resolution={"state": "accepted", "authority": "agent"},
            ),
        )
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        status = ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        self.assertTrue(status["authorized"])

    def test_authorization_preserves_non_owner_pending_finding_freedom(self) -> None:
        ledger.record_ledger(self.ledger_path, self.finding(severity="P1"))
        self.materiality({"tests": ["ENG-T1"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        status = ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        self.assertTrue(status["authorized"])
        self.assertEqual(status["pending"], ["ENG-T1"])

    def test_finalize_and_verify_clearance_for_a_complete_full_review(self) -> None:
        self.materiality()
        finalized = ledger.finalize_clearance(self.ledger_path)
        self.assertEqual(finalized["clearance"]["verdict"], "cleared")
        self.assertFalse(finalized["clearance"]["stale"])
        verified = ledger.verify_clearance(self.ledger_path)
        self.assertTrue(verified["ok"])
        self.assertEqual(verified["clearance_blockers"], [])

    def test_contextual_apply_binds_plain_owner_reply_to_one_unchanged_candidate(self) -> None:
        self.materiality()
        ledger.present_candidate(self.ledger_path)
        source = {**self.owner_source("turn-apply"), "action": "apply"}
        status = ledger.authorize_contextual(self.ledger_path, source)
        self.assertTrue(status["authorized"])
        source = json.loads(self.ledger_path.read_text(encoding="utf-8"))["authorization"]["source"]
        self.assertEqual(source["reference"], "turn-apply")
        self.assertEqual(source["manifest_hash"], status["manifest_hash"])

    def test_contextual_apply_rejects_a_message_without_host_verified_apply_intent(self) -> None:
        self.materiality()
        ledger.present_candidate(self.ledger_path)
        with self.assertRaisesRegex(ledger.LedgerError, "action=apply"):
            ledger.authorize_contextual(self.ledger_path, self.owner_source("turn-not-apply"))

    def test_contextual_apply_fails_when_the_shown_candidate_changed(self) -> None:
        self.materiality()
        ledger.present_candidate(self.ledger_path)
        ledger.record_ledger(
            self.ledger_path,
            {"type": "materiality", "dimension": "scope", "status": "reviewed", "reason": "narrowed scope"},
        )
        with self.assertRaisesRegex(ledger.LedgerError, "unchanged candidate"):
            ledger.authorize_contextual(self.ledger_path, {**self.owner_source("turn-apply"), "action": "apply"})

    def test_applied_evidence_reuses_clearance_authorization_and_receipt_without_re_review(self) -> None:
        self.materiality()
        ledger.finalize_clearance(self.ledger_path)
        ledger.present_candidate(self.ledger_path)
        ledger.authorize_contextual(self.ledger_path, {**self.owner_source("turn-apply"), "action": "apply"})
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        ledger.apply_verified_output(self.ledger_path, proposed)
        verified = ledger.verify_applied_evidence(self.ledger_path)
        self.assertTrue(verified["ok"])
        self.target.write_text("# Drifted plan\n", encoding="utf-8")
        self.assertFalse(ledger.verify_applied_evidence(self.ledger_path)["ok"])

    def test_applied_evidence_rejects_drift_in_a_non_target_bundle_reference(self) -> None:
        bundle = self.root / "dag.md"
        bundle.write_text("# DAG\n", encoding="utf-8")
        self.ledger_path = ledger.init_ledger([str(self.target)], [str(bundle)], temp_root=self.root / "bundle-runtime")
        self.materiality()
        ledger.finalize_clearance(self.ledger_path)
        ledger.present_candidate(self.ledger_path)
        ledger.authorize_contextual(self.ledger_path, {**self.owner_source("turn-apply"), "action": "apply"})
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        ledger.apply_verified_output(self.ledger_path, proposed)
        bundle.write_text("# Drifted DAG\n", encoding="utf-8")
        verified = ledger.verify_applied_evidence(self.ledger_path)
        self.assertFalse(verified["ok"])
        self.assertTrue(any("review baseline changed" in item for item in verified["applied_evidence_blockers"]))

    def test_finalize_clearance_rejects_degraded_or_pending_review(self) -> None:
        self.materiality()
        ledger.record_ledger(
            self.ledger_path,
            {
                "type": "review_state",
                "outside_voice": "unavailable",
                "reason": "fresh context is unavailable",
            },
        )
        with self.assertRaisesRegex(ledger.LedgerError, "Outside Voice is not complete"):
            ledger.finalize_clearance(self.ledger_path)

        pending_ledger = ledger.init_ledger([str(self.target)], temp_root=self.root / "pending-runtime")
        original_ledger = self.ledger_path
        self.ledger_path = pending_ledger
        try:
            ledger.record_ledger(self.ledger_path, self.finding())
            self.materiality({"tests": ["ENG-T1"]})
            with self.assertRaisesRegex(ledger.LedgerError, "unresolved findings"):
                ledger.finalize_clearance(self.ledger_path)
        finally:
            self.ledger_path = original_ledger

    def test_bundle_target_change_stales_clearance(self) -> None:
        tickets = self.root / "tickets"
        tickets.mkdir()
        ticket = tickets / "01-review.md"
        ticket.write_text("# Ticket\n", encoding="utf-8")
        self.ledger_path = ledger.init_ledger(
            [str(self.target), str(tickets)], temp_root=self.root / "bundle-runtime"
        )
        self.materiality()
        ledger.finalize_clearance(self.ledger_path)
        ticket.write_text("# Changed ticket\n", encoding="utf-8")
        verified = ledger.verify_clearance(self.ledger_path)
        self.assertFalse(verified["ok"])
        self.assertTrue(verified["baseline_stale"])
        self.assertTrue(verified["clearance"]["stale"])
        self.assertEqual(verified["clearance"]["stale_reason"], "bundle-baseline-changed")
        with self.assertRaisesRegex(ledger.LedgerError, "existing clearance is stale"):
            ledger.finalize_clearance(self.ledger_path)

    def test_evidence_change_stales_clearance(self) -> None:
        ledger.record_ledger(
            self.ledger_path,
            self.finding(resolution={"state": "accepted", "authority": "agent"}),
        )
        self.materiality({"tests": ["ENG-T1"]})
        ledger.finalize_clearance(self.ledger_path)
        self.evidence_a.write_text("A = 2\n", encoding="utf-8")
        verified = ledger.verify_clearance(self.ledger_path)
        self.assertFalse(verified["ok"])
        self.assertTrue(verified["clearance"]["stale"])
        self.assertEqual(verified["clearance"]["stale_reason"], "evidence-dependency-changed")

    def test_outside_voice_degradation_is_bound_to_manifest(self) -> None:
        self.materiality()
        first_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.record_ledger(
            self.ledger_path,
            {
                "type": "review_state",
                "outside_voice": "unavailable",
                "reason": "host has no independent agent support",
            },
        )
        status = ledger.status_ledger(self.ledger_path)
        self.assertTrue(status["degraded"])
        self.assertEqual(status["outside_voice"], "unavailable")
        self.assertNotEqual(first_hash, status["manifest_hash"])
        authorized = ledger.authorize_ledger(
            self.ledger_path,
            status["manifest_hash"],
            self.authorization_source(status["manifest_hash"]),
        )
        self.assertTrue(authorized["authorized"])
        self.assertTrue(authorized["degraded"])

    def test_manifest_hash_is_canonical_and_mutation_invalidates_authorization(self) -> None:
        ledger.record_ledger(self.ledger_path, self.finding())
        self.materiality({"tests": ["ENG-T1"]})
        first = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        state = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        self.assertEqual(first, ledger.manifest_hash(state))
        ledger.authorize_ledger(self.ledger_path, first, self.authorization_source(first))
        changed = self.finding()
        changed["recommendation"] = "add two failure tests"
        ledger.record_ledger(self.ledger_path, changed)
        status = ledger.status_ledger(self.ledger_path)
        self.assertFalse(status["authorized"])
        self.assertNotEqual(first, status["manifest_hash"])

    def test_wrong_manifest_hash_cannot_be_authorized(self) -> None:
        self.materiality()
        with self.assertRaisesRegex(ledger.LedgerError, "does not match"):
            ledger.authorize_ledger(self.ledger_path, "0" * 64, self.authorization_source("0" * 64))

    def test_authorization_source_binds_apply_and_manifest_hash(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        rejected = self.authorization_source(current_hash)
        rejected["action"] = "reject"
        rejected["statement"] = "Do not apply this manifest."
        with self.assertRaisesRegex(ledger.LedgerError, "action=apply"):
            ledger.authorize_ledger(self.ledger_path, current_hash, rejected)
        wrong = self.authorization_source("0" * 64)
        with self.assertRaisesRegex(ledger.LedgerError, "exact manifest hash"):
            ledger.authorize_ledger(self.ledger_path, current_hash, wrong)

    def test_evidence_stale_is_local_to_dependent_finding(self) -> None:
        ledger.record_ledger(self.ledger_path, self.finding("ENG-A", self.evidence_a))
        ledger.record_ledger(self.ledger_path, self.finding("ENG-B", self.evidence_b))
        self.materiality({"tests": ["ENG-A", "ENG-B"]})
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))
        self.evidence_a.write_text("A = 2\n", encoding="utf-8")
        status = ledger.verify_ledger(self.ledger_path)
        self.assertEqual(status["stale_findings"], ["ENG-A"])
        self.assertFalse(status["baseline_stale"])
        self.assertFalse(status["authorized"])

    def test_tree_dependency_detects_new_file(self) -> None:
        evidence_tree = self.root / "evidence"
        evidence_tree.mkdir()
        (evidence_tree / "one.txt").write_text("one", encoding="utf-8")
        ledger.record_ledger(
            self.ledger_path,
            self.finding("ENG-TREE", evidence_tree, kind="tree"),
        )
        self.materiality({"tests": ["ENG-TREE"]})
        (evidence_tree / "two.txt").write_text("two", encoding="utf-8")
        status = ledger.verify_ledger(self.ledger_path)
        self.assertEqual(status["stale_findings"], ["ENG-TREE"])

    def test_target_change_is_baseline_stale(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(self.ledger_path, current_hash, self.authorization_source(current_hash))
        self.target.write_text("# Changed plan\n", encoding="utf-8")
        status = ledger.verify_ledger(self.ledger_path)
        self.assertTrue(status["baseline_stale"])
        self.assertFalse(status["ok"])

    def test_atomic_write_failure_preserves_previous_ledger(self) -> None:
        before = self.ledger_path.read_bytes()
        record = {
            "type": "materiality",
            "dimension": "scope",
            "status": "reviewed",
            "reason": "checked",
        }
        with mock.patch.object(ledger.os, "replace", side_effect=OSError("simulated")):
            with self.assertRaises(OSError):
                ledger.record_ledger(self.ledger_path, record)
        self.assertEqual(before, self.ledger_path.read_bytes())

    def test_concurrent_records_do_not_lose_updates(self) -> None:
        failures = []

        def worker(dimension: str) -> None:
            try:
                ledger.record_ledger(
                    self.ledger_path,
                    {
                        "type": "materiality",
                        "dimension": dimension,
                        "status": "reviewed",
                        "reason": dimension,
                    },
                )
            except Exception as exc:  # pragma: no cover - assertion reports details
                failures.append(exc)

        threads = [threading.Thread(target=worker, args=(dimension,)) for dimension in ledger.DIMENSIONS]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(ledger.status_ledger(self.ledger_path)["missing_materiality"], [])

    def test_materiality_must_match_formal_findings(self) -> None:
        ledger.record_ledger(self.ledger_path, self.finding())
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        with self.assertRaisesRegex(ledger.LedgerError, "conflicts with formal findings"):
            ledger.authorize_ledger(
                self.ledger_path,
                current_hash,
                self.authorization_source(current_hash),
            )

    def test_dead_process_lock_is_recovered(self) -> None:
        lock_path = self.ledger_path.with_name(f"{self.ledger_path.name}.lock")
        lock_path.write_text(
            json.dumps({"pid": 99999999, "created": 0, "token": "dead"}),
            encoding="utf-8",
        )
        ledger.record_ledger(
            self.ledger_path,
            {
                "type": "materiality",
                "dimension": "scope",
                "status": "reviewed",
                "reason": "checked",
            },
        )
        self.assertFalse(lock_path.exists())

    def test_old_empty_lock_is_recovered(self) -> None:
        lock_path = self.ledger_path.with_name(f"{self.ledger_path.name}.lock")
        lock_path.write_bytes(b"")
        os.utime(lock_path, (0, 0))
        ledger.record_ledger(
            self.ledger_path,
            {
                "type": "materiality",
                "dimension": "scope",
                "status": "reviewed",
                "reason": "checked",
            },
        )
        self.assertFalse(lock_path.exists())

    def test_guarded_apply_replaces_only_current_authorized_baseline(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        result = ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertTrue(result["applied"])
        self.assertEqual(result["run_status"], "applied")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Revised plan\n")
        self.assertEqual(Path(result["preimage_backup"]).read_text(encoding="utf-8"), "# Plan\n")
        self.assertEqual(
            ledger.discover_ledgers(self.target, temp_root=self.root / "runtime")["runs"],
            [],
        )

    def test_statusless_v1_ledger_preserves_existing_authorization(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        state = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        state["run"].pop("status")
        self.ledger_path.write_text(json.dumps(state), encoding="utf-8")
        status = ledger.status_ledger(self.ledger_path)
        self.assertEqual(status["run_status"], "active")
        self.assertEqual(status["manifest_hash"], current_hash)
        self.assertTrue(status["authorized"])

    def test_interrupted_apply_is_recoverable_after_final_ledger_write_failure(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        original_write = ledger._atomic_write
        calls = 0

        def fail_final_write(path: Path, state: dict[str, object]) -> None:
            nonlocal calls
            calls += 1
            if calls == 2:
                raise OSError("simulated final ledger failure")
            original_write(path, state)

        with mock.patch.object(ledger, "_atomic_write", side_effect=fail_final_write):
            with self.assertRaisesRegex(OSError, "simulated final ledger failure"):
                ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Revised plan\n")
        interrupted = ledger.status_ledger(self.ledger_path)
        self.assertEqual(interrupted["run_status"], "applying")
        self.assertEqual(
            ledger.discover_ledgers(self.target, temp_root=self.root / "runtime")["runs"][0]["run_status"],
            "applying",
        )
        resumed = ledger.resume_ledger(self.ledger_path, self.target)
        self.assertEqual(resumed["run_status"], "applied")

    def test_resume_restores_missing_target_from_adjacent_preimage_backup(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        with mock.patch.object(ledger.os, "link", side_effect=OSError("simulated crash window")):
            with self.assertRaisesRegex(OSError, "simulated crash window"):
                ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertFalse(self.target.exists())
        interrupted = json.loads(self.ledger_path.read_text(encoding="utf-8"))
        backup = Path(interrupted["run"]["apply_receipt"]["preimage_backup"])
        self.assertEqual(backup.read_text(encoding="utf-8"), "# Plan\n")
        resumed = ledger.resume_ledger(self.ledger_path, self.target)
        self.assertEqual(resumed["run_status"], "active")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Plan\n")
        self.assertEqual(resumed["apply_backups"], [str(backup)])
        retried = ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertEqual(retried["run_status"], "applied")
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Revised plan\n")
        self.assertEqual(len(retried["apply_backups"]), 2)
        self.assertEqual(retried["apply_backups"][0], str(backup))

    def test_final_replacement_does_not_overwrite_racing_writer(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        original_replace = ledger.os.replace

        def race_before_displace(source: Path, destination: Path) -> None:
            if Path(source) == self.target and str(destination).endswith(".bak"):
                self.target.write_text("# Concurrent edit\n", encoding="utf-8")
            original_replace(source, destination)

        with mock.patch.object(ledger.os, "replace", side_effect=race_before_displace):
            with self.assertRaisesRegex(ledger.LedgerError, "changed during final replacement"):
                ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Concurrent edit\n")

    def test_open_handle_style_write_after_displace_remains_in_reported_backup(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        original_link = ledger.os.link
        injected = False

        def race_after_displace(source: Path, destination: Path) -> None:
            nonlocal injected
            if Path(destination) == self.target and not injected:
                backup = next(self.target.parent.glob(f".{self.target.name}.plan-review-*.bak"))
                backup.write_text("# Concurrent edit through open handle\n", encoding="utf-8")
                injected = True
            original_link(source, destination)

        with mock.patch.object(ledger.os, "link", side_effect=race_after_displace):
            result = ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertTrue(result["applied"])
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Revised plan\n")
        self.assertEqual(
            Path(result["preimage_backup"]).read_text(encoding="utf-8"),
            "# Concurrent edit through open handle\n",
        )

    def test_guarded_apply_rejects_changed_target(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        self.target.write_text("# Concurrent edit\n", encoding="utf-8")
        with self.assertRaisesRegex(ledger.LedgerError, "baseline is stale"):
            ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Concurrent edit\n")

    def test_guarded_apply_writes_nothing_when_target_changes_after_initial_verify(self) -> None:
        self.materiality()
        current_hash = ledger.status_ledger(self.ledger_path)["manifest_hash"]
        ledger.authorize_ledger(
            self.ledger_path,
            current_hash,
            self.authorization_source(current_hash),
        )
        proposed = self.root / "proposed.md"
        proposed.write_text("# Revised plan\n", encoding="utf-8")
        original_verify = ledger._verify_in_place

        def mutate_after_verify(state: dict[str, object]) -> bool:
            changed = original_verify(state)
            self.target.write_text("# Concurrent edit\n", encoding="utf-8")
            return changed

        with mock.patch.object(ledger, "_verify_in_place", side_effect=mutate_after_verify):
            with self.assertRaisesRegex(ledger.LedgerError, "target changed after verification"):
                ledger.apply_verified_output(self.ledger_path, proposed)
        self.assertEqual(self.target.read_text(encoding="utf-8"), "# Concurrent edit\n")
        self.assertEqual(
            list(self.target.parent.glob(f".{self.target.name}.plan-review-*.bak")),
            [],
        )


if __name__ == "__main__":
    unittest.main()
