"""Focused tests for the dev-loop package pipeline CLI and status projection."""

from __future__ import annotations

import importlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
SKILL_DIR = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_DIR / "scripts" / "dev_loop.py"

_SPEC = importlib.util.spec_from_file_location("dev_loop_test_entry", SCRIPT)
dev_loop = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = dev_loop
_SPEC.loader.exec_module(dev_loop)
_PREFIX = dev_loop._PACKAGE_NAME
engine = importlib.import_module(f"{_PREFIX}.engine")
facts = importlib.import_module(f"{_PREFIX}.facts")
store = importlib.import_module(f"{_PREFIX}.store")
agents = importlib.import_module(f"{_PREFIX}.agents")
batches = importlib.import_module(f"{_PREFIX}.batches")
render = importlib.import_module(f"{_PREFIX}.render")

STAGES = ["intake", "tickets", "final-review", "final-verify", "gate", "closeout"]

SPEC_MD = """# Spec

## 1. 核心目标

fixture 的验收合同。

## 7. 验收

### Journeys

#### J1 fixture journey

| Step | 角色 | 入口类型 | 控件 | 操作入口 | 观察表面 | 预期 | 承接 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| J1-S1 | 操作员 | 页面 | 完成 | fixture 页面 | fixture 页面 | 看到结果 | — |

### Rule Matrix

| Rule | Source | Suite | Oracle |
| --- | --- | --- | --- |
| R1 | §1 | S-fixture | fixture 规则成立 |

- 无需验收的章节： none

### Required Suites

| Suite | Kind | Scope | Entry | Environment |
| --- | --- | --- | --- | --- |
| S-fixture | rule | package | fixture test | local-test |
"""


def _state(tickets: dict[str, str], attempt: str = "attempt-1") -> dict:
    rows = {}
    for ticket, state in tickets.items():
        row = {"state": state}
        if state == "BLOCKED":
            row["evidence"] = "tickets/01.md"
        if state in {"SATISFIED", "RETIRED"}:
            row["acceptance"] = {"revision": "5f299f3", "environment": "fixture-local"}
        rows[ticket] = row
    return {
        "formatVersion": "3.6",
        "predecessors": None,
        "attempt": {"id": attempt, "plan": "plan.md"},
        "attemptHistory": [],
        "tickets": rows,
        "evidenceIndex": {},
        "activeCheckpoints": {},
        "acceptance": {
            "contractBaseline": {"head": "0" * 40, "files": {"spec.md": "1" * 40}},
            "releaseOrder": "none",
            "amendments": [],
            "harness": {
                "setup": "python harness.py setup",
                "precheck": "python harness.py precheck",
                "cleanup": "python harness.py cleanup",
                "isolation": "per-run",
                "firstVisibleStep": {"step": "J1-S1", "ticket": next(iter(tickets))},
            },
        },
    }


def _ticket_md(ticket: str) -> str:
    return (
        f"# {ticket}\n\n"
        f"**Ticket ID:** {ticket}\n"
        "**Attempt ID:** attempt-1\n\n"
        "## Coverage\n\n"
        "- Journey steps: J1-S1\n"
        "- Suites: S-fixture\n"
        "- Required review: none\n"
    )


def _return_events(ticket: str, number: int) -> list[dict]:
    return [
        {
            "subject": f"ticket:{ticket}",
            "kind": "dispatch",
            "seq": number * 2 - 1,
            "dispatch_id": f"dispatch-{number}",
            "candidate_id": f"candidate-{number}",
            "mode": "implement",
            "chosen": f"impl-{number}",
            "resource_keys": [],
            "receipt": f"impl-{number}",
            "outcome": "RUNNING",
            "worker": f"impl-{number}",
            "returned": False,
        },
        {
            "subject": f"ticket:{ticket}",
            "kind": "worker-return",
            "seq": number * 2,
            "of": f"dispatch-{number}",
            "return_id": f"return-{number:02d}",
            "outcome": "DONE",
            "code_delta": {"head": f"head-{number}"},
            "worker_mode": "implement",
            "envelope_valid": True,
        },
    ]


def _rounds(rounds: list[dict], findings: list[dict] | None = None) -> dict:
    return {"schemaVersion": 2, "rounds": rounds, "findings": list(findings or [])}


def _closed_round(group: str, verdicts: dict, *, phase: str = "terminal-final",
                  number: int = 1, open_seq: int = 1, succeeds: str | None = None) -> dict:
    row = {
        "group": group,
        "round": number,
        "phase": phase,
        "openSeq": open_seq,
        "closeSeq": open_seq + 1,
        "closed": True,
        "tracks": {name: {"verdict": verdict} for name, verdict in verdicts.items()},
    }
    if succeeds is not None:
        row["succeeds"] = succeeds
    return row


def _converged_rounds() -> dict:
    return _rounds([
        _closed_round("g1", {"code": "PASS"}, phase="initial"),
        _closed_round("g2", {"code": "PASS"}, open_seq=3, succeeds="g1"),
    ])


def _finding(**overrides) -> dict:
    row = {"id": "F1", "group": "g", "status": "open", "source": "impl-drift",
           "class": "design", "severity": "P1", "ledger": "r1", "round": 1}
    row.update(overrides)
    return row


def _stage(view: dict, name: str) -> dict:
    return next(stage for stage in view["pipeline"] if stage["id"] == name)


def _body_names(view: dict) -> list[str]:
    return [item["return_id"] for item in view["uncovered_returns"]]


def _pipeline_facts(*, slugs: tuple[str, ...] = (), verdict: str | None = None,
                    projection_status: str = "confirmed", rounds: list[dict] | None = None) -> dict:
    return {"state": _state({"TKT-1": "SATISFIED"}), "state_status": "confirmed",
            "projection_status": projection_status,
            "projection": {"matches": [{"slug": slug} for slug in slugs],
                           "sources": {"gate": {"verdict": verdict, "error": None}}},
            "rounds": list(rounds or []), "uncovered_returns": [], "warnings": []}


def _terminal_summary(path: str, *, converged: bool = True, open_seq: int = 1,
                      closed: bool = True, tracks: list[dict] | None = None,
                      open_findings_count: int = 0) -> dict:
    return {"path": path, "phase": "terminal-final", "open_seq": open_seq,
            "converged": converged, "closed": closed,
            "tracks": tracks if tracks is not None else [{"track": "code", "verdict": "PASS"}],
            "open_findings_count": open_findings_count, "reasons": []}


class _PackageMixin:
    def build(self, tickets: dict[str, str], *, gate: str | None = None,
              trail: list[dict] | tuple = (), rounds: dict[str, object] | None = None,
              profile: object | None = None) -> Path:
        root = Path(tempfile.mkdtemp(prefix="dev-loop-pkg-"))
        self.addCleanup(shutil.rmtree, root, ignore_errors=True)
        package_dir = root / ".impl-package"
        package_dir.mkdir(parents=True, exist_ok=True)
        (package_dir / "state.json").write_text(
            json.dumps(_state(tickets), ensure_ascii=False, indent=2), encoding="utf-8")
        (root / "spec.md").write_text(SPEC_MD, encoding="utf-8")
        (root / "tickets").mkdir()
        for index, ticket in enumerate(tickets, start=1):
            (root / "tickets" / f"{index:02d}.md").write_text(_ticket_md(ticket), encoding="utf-8")
        if gate is not None:
            (root / "gate.md").write_text(
                f"# Gate\n- Attempt: attempt-1\n- Verdict: {gate}\n", encoding="utf-8")
        trail = list(trail)
        if trail:
            execution = root / "execution" / "attempt-1"
            execution.mkdir(parents=True)
            (execution / "trail.jsonl").write_text(
                "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in trail), encoding="utf-8")
        for name, content in (rounds or {}).items():
            path = root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            text = content if isinstance(content, str) else json.dumps(content, ensure_ascii=False, indent=2)
            path.write_text(text, encoding="utf-8")
        if profile is not None:
            text = profile if isinstance(profile, str) else json.dumps(profile, ensure_ascii=False, indent=2)
            (package_dir / store.PROFILE_NAME).write_text(text, encoding="utf-8")
        return root

    def view(self, root: Path) -> dict:
        return engine.status_view(root)


class MainlineTest(_PackageMixin, unittest.TestCase):
    def test_new_single_ticket_starts_at_intake(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        view = self.view(root)

        self.assertEqual([stage["id"] for stage in view["pipeline"]], STAGES)
        self.assertEqual([stage["id"] for stage in view["pipeline"]], list(engine.PIPELINE_STAGES))
        self.assertEqual(_stage(view, "intake")["status"], "done")
        self.assertEqual(_stage(view, "tickets")["status"], "active")
        self.assertEqual(_stage(view, "final-review")["status"], "pending")
        self.assertEqual(_stage(view, "final-verify")["status"], "pending")
        self.assertEqual(_stage(view, "gate")["status"], "pending")
        self.assertEqual(_stage(view, "closeout")["status"], "pending")
        self.assertEqual(view["state_status"], "confirmed")
        self.assertEqual(view["projection_status"], "confirmed")
        self.assertEqual(view["tickets"]["counts"]["PENDING"], 1)
        self.assertEqual(view["warnings"], [])
        self.assertFalse((root / ".impl-package" / store.PROFILE_NAME).exists())

    def test_in_progress_package_without_profile_is_read_only(self) -> None:
        trail = [{
            "subject": "ticket:TKT-1", "kind": "dispatch", "seq": 1,
            "dispatch_id": "dispatch-1", "candidate_id": "candidate-1", "mode": "implement",
            "chosen": "impl-1", "resource_keys": [], "receipt": "impl-1",
            "outcome": "RUNNING", "worker": "impl-1", "returned": False,
        }]
        root = self.build({"TKT-1": "PENDING", "TKT-2": "BLOCKED"}, trail=trail)
        before = sorted(path.relative_to(root) for path in root.rglob("*"))

        view = self.view(root)

        self.assertEqual(_stage(view, "intake")["status"], "done")
        self.assertEqual(_stage(view, "tickets")["status"], "active")
        self.assertEqual(view["tickets"]["counts"], {
            "PENDING": 1, "BLOCKED": 1, "NEEDS-REVALIDATION": 0, "SATISFIED": 0, "RETIRED": 0})
        self.assertEqual(view["routing"], {})
        self.assertEqual(view["agents"]["items"], [])
        self.assertEqual(view["batches"], [])
        self.assertEqual(sorted(path.relative_to(root) for path in root.rglob("*")), before)
        self.assertEqual(engine.config_show(root)["status"], "confirmed")

    def test_root_state_json_fallback_adapter(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        state = root / ".impl-package" / "state.json"
        root.joinpath("state.json").write_text(state.read_text(encoding="utf-8"), encoding="utf-8")
        state.unlink()
        (root / ".impl-package").rmdir()

        value, error, status = facts.read_package_state(root)

        self.assertEqual(status, "confirmed")
        self.assertIsNone(error)
        self.assertEqual(value["tickets"]["TKT-1"]["state"], "PENDING")

    def test_status_keeps_confirmed_root_state_despite_situation_warning(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        canonical = root / ".impl-package" / "state.json"
        (root / "state.json").write_text(canonical.read_text(encoding="utf-8"), encoding="utf-8")
        canonical.unlink()
        (root / ".impl-package").rmdir()

        projection, error = facts.read_situation(root)
        view = self.view(root)

        self.assertIsNone(error)
        self.assertEqual(view["state_status"], "confirmed")
        reason = projection["sources"]["state"]["reason"]
        self.assertTrue(reason)
        self.assertIn(reason, view["warnings"])

    def test_complete_package_walks_all_stages(self) -> None:
        # 最小 fixture 未写入 terminal-final coverage trail 时，Gate pass 与缺口冲突，不得误判 done
        root = self.build(
            {"TKT-1": "SATISFIED"}, gate="pass",
            rounds={"execution/attempt-1/reviews/r1.rounds.json": _converged_rounds()})
        view = self.view(root)

        statuses = {stage["id"]: stage["status"] for stage in view["pipeline"]}
        self.assertEqual(statuses, {
            "intake": "done", "tickets": "done", "final-review": "active",
            "final-verify": "attention", "gate": "attention", "closeout": "pending"})
        self.assertIn("补齐 terminal-final coverage", _stage(view, "final-review")["reason"])
        self.assertTrue(view["review_rounds"][0]["converged"])
        self.assertEqual(view["next_step"]["command"], "/impl-package:do-review phase=terminal-final")

        # 无冲突的完整通关事实下，主线全部推进至 closeout
        clean_facts = _pipeline_facts(
            rounds=[_terminal_summary("execution/attempt-1/reviews/r1.rounds.json")],
            verdict="pass")
        clean_statuses = {stage["id"]: stage["status"] for stage in engine.derive_pipeline(clean_facts)}
        self.assertEqual(clean_statuses, {
            "intake": "done", "tickets": "done", "final-review": "done",
            "final-verify": "done", "gate": "done", "closeout": "attention"})


class TerminalReviewPriorityTest(unittest.TestCase):
    def test_situation_terminal_coverage_incomplete_overrides_converged_round(self) -> None:
        summary = _terminal_summary("reviews/final.rounds.json")

        stage = _stage({"pipeline": engine.derive_pipeline(_pipeline_facts(
            slugs=("attempt.review.terminal-coverage-incomplete",), rounds=[summary]))}, "final-review")

        self.assertEqual(stage["status"], "active")
        self.assertIn("Situation 要求补齐", stage["reason"])

    def test_multiple_terminal_final_files_require_unique_batch_source(self) -> None:
        rounds = [_terminal_summary("reviews/one.rounds.json", open_seq=2),
                  _terminal_summary("reviews/two.rounds.json", open_seq=99)]

        stage = _stage({"pipeline": engine.derive_pipeline(_pipeline_facts(rounds=rounds))}, "final-review")

        self.assertEqual(stage["status"], "attention")
        self.assertIn("来源冲突或不明", stage["reason"])
        self.assertIn("对应终审文件", stage["reason"])

    def test_superseded_batch_round_is_removed_from_terminal_candidates(self) -> None:
        path = "reviews/superseded.rounds.json"
        summary = _terminal_summary(path)
        batch = {"status": "superseded", "rounds_file": path,
                 "rounds_summary": {"path": path}}

        stage = _stage({"pipeline": engine.derive_pipeline(
            _pipeline_facts(rounds=[summary]), [batch])}, "final-review")

        self.assertEqual(stage["status"], "attention")
        self.assertIn("缺少已确认", stage["reason"])

    def test_gate_missing_alone_keeps_final_verify_active(self) -> None:
        facts_ = _pipeline_facts(slugs=("attempt.gate.missing",), rounds=[
            _terminal_summary("reviews/final.rounds.json")])

        stages = engine.derive_pipeline(facts_)
        verify = next(row for row in stages if row["id"] == "final-verify")

        self.assertEqual(verify["status"], "active")
        self.assertIn("准备 Gate", verify["reason"])

    def test_unconfirmed_projection_cannot_claim_gate_pass(self) -> None:
        facts_ = _pipeline_facts(verdict="pass", projection_status="undetermined",
                                 rounds=[_terminal_summary("reviews/final.rounds.json")])

        stages = engine.derive_pipeline(facts_)

        self.assertEqual(next(row for row in stages if row["id"] == "final-verify")["status"], "attention")
        self.assertEqual(next(row for row in stages if row["id"] == "gate")["status"], "attention")

    def test_gate_pass_conflicts_with_pending_acceptance(self) -> None:
        facts_ = _pipeline_facts(slugs=("attempt.accept.ticket-evidence-incomplete",), verdict="pass",
                                 rounds=[_terminal_summary("reviews/final.rounds.json")])

        stages = engine.derive_pipeline(facts_)

        self.assertEqual(next(row for row in stages if row["id"] == "final-verify")["status"], "attention")
        self.assertEqual(next(row for row in stages if row["id"] == "gate")["status"], "attention")

    def test_terminal_review_plus_gate_decision_marks_final_verify_done(self) -> None:
        facts_ = _pipeline_facts(slugs=("attempt.gate.verdict-undecided",),
                                 rounds=[_terminal_summary("reviews/final.rounds.json")])

        verify = next(row for row in engine.derive_pipeline(facts_) if row["id"] == "final-verify")

        self.assertEqual(verify["status"], "done")


class BatchCoverageTest(_PackageMixin, unittest.TestCase):
    def _two_returns(self) -> Path:
        trail = _return_events("TKT-1", 1) + _return_events("TKT-2", 2)
        return self.build({"TKT-1": "PENDING", "TKT-2": "PENDING"}, trail=trail)

    def test_batch_registration_covers_only_registered_returns(self) -> None:
        root = self._two_returns()
        before = self.view(root)
        self.assertEqual(_body_names(before), ["return-01", "return-02"])
        self.assertIn("2 个", _stage(before, "final-review")["reason"])

        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1", "TKT-2"], "returns": ["return-01"],
            "status": "open", "snapshot_kind": "integrated"})

        after = self.view(root)
        self.assertEqual(_body_names(after), ["return-02"])
        self.assertEqual(after["return_assignments"], [{"return_id": "return-01", "batch_id": "b1"}])
        self.assertEqual(after["batches"][0]["covered_returns"], ["return-01"])
        self.assertIn("1 个", _stage(after, "final-review")["reason"])
        self.assertEqual(after["next_step"]["command"], "/impl-package:do-review")

    def test_superseded_batch_stops_covering_returns(self) -> None:
        root = self._two_returns()
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1", "TKT-2"],
            "returns": ["return-01", "return-02"], "status": "open"})
        self.assertEqual(_body_names(self.view(root)), [])

        engine.batch_update(root, "b1", {"status": "superseded"})

        after = self.view(root)
        self.assertEqual(_body_names(after), ["return-01", "return-02"])
        self.assertEqual(after["return_assignments"], [])
        self.assertIn("2 个", _stage(after, "final-review")["reason"])

    def test_closed_batch_with_open_findings_prompts_triage(self) -> None:
        root = self.build({"TKT-1": "PENDING"}, rounds={
            "execution/attempt-1/reviews/r1.rounds.json": _rounds(
                [_closed_round("g", {"code": "PASS"})], [_finding()])})
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1"], "status": "open",
            "rounds_file": "execution/attempt-1/reviews/r1.rounds.json"})

        view = self.view(root)

        summary = view["batches"][0]["rounds_summary"]
        self.assertEqual(summary["open_findings_count"], 1)
        self.assertFalse(summary["converged"])
        self.assertEqual(_stage(view, "final-review")["status"], "attention")
        self.assertEqual(_stage(view, "final-review")["reason"], "审阅批次仍有 open findings，待主控分诊")

    def test_open_batch_with_findings_waits_for_unreturned_track_before_triage(self) -> None:
        root = self.build({"TKT-1": "PENDING"}, rounds={
            "execution/attempt-1/reviews/r1.rounds.json": _rounds([{
                "group": "g", "round": 1, "phase": "initial", "openSeq": 1,
                "closed": False, "tracks": {"code": {"verdict": "PASS"}, "safety": {"verdict": None}},
            }], [_finding()])})
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1"], "status": "open",
            "rounds_file": "execution/attempt-1/reviews/r1.rounds.json"})

        view = self.view(root)

        self.assertGreater(view["batches"][0]["rounds_summary"]["open_findings_count"], 0)
        self.assertEqual(_stage(view, "final-review")["status"], "active")
        self.assertIn("等待审阅轨收齐并关闭轮次", _stage(view, "final-review")["reason"])
        self.assertNotIn("待主控分诊", _stage(view, "final-review")["reason"])

    def test_covered_pending_review_candidates_are_not_recommended_again(self) -> None:
        root = self._two_returns()
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1", "TKT-2"],
            "returns": ["return-01", "return-02"], "status": "open"})

        view = self.view(root)

        self.assertFalse(any(row.get("source") == "pending-review" for row in view["situation"]["runnable"]))
        self.assertNotIn("review:return-01", view["next_step"]["reason"])
        self.assertNotIn("review:return-02", view["next_step"]["reason"])

    def test_status_view_passes_situation_queues_and_ticket_dependencies(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        state = _state({"TKT-1": "PENDING"})
        state["tickets"]["TKT-1"].update({"depends_on": ["TKT-0"], "dependencies": {"implementation": ["TKT-0"]}})
        projection = {
            "blocking": [{"slug": "attempt.ticket.blocked"}],
            "runnable": [
                {"source": "pending-review", "return_id": "return-covered", "actions": [{"do": "hidden"}]},
                {"source": "pending-review", "return_id": "return-open", "candidate_id": "review:return-open",
                 "reason": "pending review", "actions": [{"do": "dispatch uncovered"}]},
            ],
            "withheld": [{"candidate_id": "withheld-1"}],
            "in_flight": [{"dispatch_id": "dispatch-1"}],
            "manual": [{"slug": "attempt.gate.manual"}],
            "undetermined": [{"slug": "attempt.file.unknown"}],
            "sources": {"gate": {"verdict": None}},
        }
        source_facts = {"projection": projection, "projection_status": "confirmed", "state": state,
                        "state_status": "confirmed", "rounds": [], "pending_returns": [],
                        "uncovered_returns": [], "warnings": []}
        batch_view = {"items": [], "return_assignments": [{"return_id": "return-covered", "batch_id": "b1"}],
                      "uncovered_returns": [], "current_head": None}
        with mock.patch.object(engine, "read_facts", return_value=source_facts), \
                mock.patch.object(batches, "status_view", return_value=batch_view):
            view = self.view(root)

        self.assertEqual(view["situation"]["blocking"], projection["blocking"])
        self.assertEqual([row["return_id"] for row in view["situation"]["runnable"]], ["return-open"])
        self.assertEqual(view["tickets"]["items"][0]["depends_on"], ["TKT-0"])
        self.assertEqual(view["tickets"]["items"][0]["dependencies"], {"implementation": ["TKT-0"]})
        self.assertEqual(view["next_step"]["command"], "dispatch uncovered")
        text = render.status_text(view)
        self.assertIn("Situation 队列:", text)
        self.assertIn("blocking=1", text)
        self.assertIn("undetermined=1", text)


class RoundsReadingTest(_PackageMixin, unittest.TestCase):
    def _with_round(self, rounds: dict) -> dict:
        root = self.build({"TKT-1": "PENDING"}, rounds={
            "execution/attempt-1/reviews/r1.rounds.json": rounds})
        return self.view(root)

    def test_unclosed_round_reports_waiting_tracks(self) -> None:
        view = self._with_round(_rounds([{
            "group": "g", "round": 1, "phase": "terminal-final", "openSeq": 1,
            "closed": False, "tracks": {"code": {"verdict": "PASS"}, "safety": {"verdict": None}},
        }]))

        summary = view["review_rounds"][0]
        self.assertFalse(summary["converged"])
        self.assertEqual(summary["status"], "unconfirmed")
        self.assertIn("当前轮次尚未关闭", summary["reasons"])
        self.assertIn("safety 尚未返回", summary["reasons"])
        self.assertEqual(_stage(view, "final-review")["status"], "active")
        self.assertIn("尚未关闭", _stage(view, "final-review")["reason"])
        self.assertIn("未收敛", render.status_text(view))

    def test_closed_round_with_open_findings_is_not_converged(self) -> None:
        view = self._with_round(_rounds(
            [_closed_round("g", {"code": "PASS"})], [_finding()]))

        summary = view["review_rounds"][0]
        self.assertFalse(summary["converged"])
        self.assertEqual(summary["open_findings_count"], 1)
        self.assertIn("仍有 1 个 open/fixed finding", summary["reasons"])
        self.assertEqual(_stage(view, "final-review")["status"], "attention")
        self.assertEqual(_stage(view, "final-review")["reason"], "仍有未闭合 findings")

    def test_uncertain_or_incomplete_without_findings_is_not_pass(self) -> None:
        for verdict in ("UNCERTAIN", "INCOMPLETE"):
            with self.subTest(verdict=verdict):
                rounds = _rounds([_closed_round("g", {"code": "PASS", "safety": verdict})])
                view = self._with_round(rounds)

                summary = view["review_rounds"][0]
                self.assertFalse(summary["converged"])
                self.assertEqual(summary["status"], "unconfirmed")
                self.assertIn(f"safety verdict 为 {verdict}", summary["reasons"])
                self.assertEqual(_stage(view, "final-review")["status"], "attention")
                self.assertNotIn("terminal-final 收齐 PASS", _stage(view, "final-review")["reason"])
                self.assertIn("未收敛", render.status_text(view))


class SnapshotAlertTest(_PackageMixin, unittest.TestCase):
    def test_isolated_snapshot_alert_requires_evidence_add(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1"], "status": "open", "snapshot_kind": "isolated"})

        view = self.view(root)

        alerts = view["batches"][0]["alerts"]
        self.assertTrue(any("隔离快照审阅" in alert and "evidence add" in alert for alert in alerts))
        self.assertEqual(view["next_step"]["command"], "按票执行 evidence add")

    def test_reviewed_head_drift_alert(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1"], "status": "open",
            "reviewed_head": "a" * 40})

        with mock.patch.object(batches, "_current_head", return_value="b" * 40):
            view = self.view(root)

        row = view["batches"][0]
        self.assertTrue(row["head_drift"])
        self.assertTrue(any("审阅 HEAD " + "a" * 40 in alert and "evidence add" in alert
                            for alert in row["alerts"]))
        self.assertEqual(view["next_step"]["command"], "按票执行 evidence add")


class AgentRoutingTest(_PackageMixin, unittest.TestCase):
    def test_route_update_keeps_existing_agents_and_stays_per_package(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.agent_register(root, {"id": "impl-1", "role": "implementer",
                                     "scope": "TKT-1", "host": "claude", "model": "sonnet"})
        before = store.load_profile(root)[0]["agents"]

        engine.config_set_route(root, "reviewer", "magpie-sol-high", "high")

        profile, warning = store.load_profile(root)
        self.assertIsNone(warning)
        self.assertEqual(profile["agents"], before)
        self.assertEqual(profile["routing"]["reviewer"], {"model": "magpie-sol-high", "effort": "high"})
        self.assertEqual(_stage(self.view(root), "tickets")["status"], "active")

        other = self.build({"TKT-1": "PENDING"})
        self.assertEqual(self.view(other)["routing"], {})

    def test_loose_agent_registration_shows_unconfirmed_and_reuse(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.agent_register(root, {"role": "implementer", "scope": "TKT-1", "host": "claude"})

        view = self.view(root)

        item = view["agents"]["items"][0]
        self.assertEqual(item["agent_id"], "unconfirmed")
        self.assertEqual(item["status"], "active")
        recommendation = view["agents"]["reuse_recommendations"][0]
        self.assertEqual((recommendation["scope"], recommendation["role"]), ("TKT-1", "implementer"))
        self.assertEqual(recommendation["agents"][0]["agent_id"], "unconfirmed")
        self.assertIn("unconfirmed", render.agent_text(engine.agent_list(root)))

    def test_replace_creates_successor_and_handoff(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.agent_register(root, {"id": "impl-1", "role": "implementer",
                                     "scope": "TKT-1", "host": "claude", "agent_id": "host-1"})

        result = engine.agent_replace(root, "impl-1", {"agent_id": "host-2"}, None, "交接上下文")

        self.assertTrue(result["created"])
        successor = result["replacement"]["id"]
        self.assertNotEqual(successor, "impl-1")
        self.assertEqual(result["replacement"]["agent_id"], "host-2")
        self.assertEqual(result["replacement"]["role"], "implementer")
        view = self.view(root)
        old = next(row for row in view["agents"]["items"] if row["id"] == "impl-1")
        self.assertEqual(old["status"], "replaced")
        self.assertEqual(old["replaced_by"], successor)
        self.assertEqual(old["handoff_note"], "交接上下文")
        self.assertEqual(len(view["agents"]["active"]), 1)

    def test_replace_can_associate_existing_successor(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.agent_register(root, {"id": "impl-1", "role": "implementer",
                                     "scope": "TKT-1", "host": "claude"})
        engine.agent_register(root, {"id": "impl-2", "role": "implementer",
                                     "scope": "TKT-1", "host": "claude"})

        result = engine.agent_replace(root, "impl-1", {"model": "sonnet"}, "impl-2", "换人")

        self.assertFalse(result["created"])
        self.assertEqual(result["replacement"]["id"], "impl-2")
        self.assertEqual(result["replacement"]["model"], "sonnet")
        view = self.view(root)
        self.assertEqual(len(view["agents"]["items"]), 2)
        old = next(row for row in view["agents"]["items"] if row["id"] == "impl-1")
        self.assertEqual(old["replaced_by"], "impl-2")

    def test_previous_reviewers_keep_independence_reminder(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.agent_register(root, {"id": "rev-1", "role": "reviewer",
                                     "scope": "TKT-1", "host": "codex", "agent_id": "r-1"})
        engine.agent_replace(root, "rev-1", {"agent_id": "r-2"}, None, "独立性换人")

        view = self.view(root)

        reviewers = view["agents"]["previous_reviewers"]
        self.assertEqual([row["status"] for row in reviewers], ["replaced", "active"])
        self.assertEqual([row["agent_id"] for row in reviewers], ["r-1", "r-2"])
        self.assertIn("前驱审阅者（组织新审阅组时提醒保持独立性）", render.status_text(view))


class DegradedStateTest(_PackageMixin, unittest.TestCase):
    def test_missing_rounds_file_degrades_only_that_batch(self) -> None:
        root = self.build({"TKT-1": "PENDING"})
        engine.batch_register(root, {
            "batch_id": "b1", "tickets": ["TKT-1"], "status": "open",
            "rounds_file": "execution/attempt-1/reviews/missing.rounds.json"})

        view = self.view(root)

        summary = view["batches"][0]["rounds_summary"]
        self.assertEqual(summary["status"], "unconfirmed")
        self.assertIn("rounds 文件不存在", summary["reasons"])
        self.assertEqual(_stage(view, "tickets")["status"], "active")
        self.assertEqual(_stage(view, "intake")["status"], "done")

    def test_broken_rounds_file_does_not_block_other_tickets(self) -> None:
        root = self.build(
            {"TKT-1": "SATISFIED"}, gate="pass",
            rounds={
                "execution/attempt-1/reviews/r1.rounds.json": _converged_rounds(),
                "execution/other/broken.rounds.json": "{not json",
            })

        view = self.view(root)

        statuses = {round_["status"] for round_ in view["review_rounds"]}
        self.assertEqual(statuses, {"confirmed", "undetermined"})
        broken = next(round_ for round_ in view["review_rounds"] if round_["status"] == "undetermined")
        self.assertIn("rounds JSON 无法读取", broken["reasons"][0])
        self.assertEqual(_stage(view, "tickets")["status"], "done")
        self.assertEqual(_stage(view, "final-review")["status"], "active")
        self.assertIn("补齐 terminal-final coverage", _stage(view, "final-review")["reason"])

    def test_corrupt_profile_marks_undetermined_and_refuses_writes(self) -> None:
        root = self.build({"TKT-1": "PENDING"}, profile="{broken")
        profile_path = root / ".impl-package" / store.PROFILE_NAME

        view = self.view(root)

        self.assertTrue(any("undetermined" in warning for warning in view["warnings"]))
        self.assertEqual(view["routing"], {})
        self.assertEqual(engine.config_show(root)["status"], "undetermined")
        agent_result = engine.agent_list(root)
        batch_result = engine.batch_list(root)
        self.assertEqual(agent_result["status"], "undetermined")
        self.assertEqual(batch_result["status"], "undetermined")
        self.assertTrue(agent_result["warning"])
        self.assertTrue(batch_result["warning"])
        self.assertIn("读取提示:", render.agent_text(agent_result))
        self.assertIn("读取提示:", render.batch_text(batch_result))
        with self.assertRaises(ValueError):
            engine.config_set_route(root, "reviewer", "magpie-sol-high")
        with self.assertRaises(ValueError):
            engine.agent_register(root, {"role": "implementer", "scope": "TKT-1", "host": "claude"})
        with self.assertRaises(ValueError):
            engine.batch_register(root, {"batch_id": "b1", "tickets": ["TKT-1"]})
        self.assertEqual(profile_path.read_text(encoding="utf-8"), "{broken")

    def test_symlink_paths_are_rejected(self) -> None:
        root = self.build({"TKT-1": "PENDING"})

        def _profile_symlink(self) -> bool:
            return self.name == store.PROFILE_NAME

        with mock.patch.object(Path, "is_symlink", _profile_symlink):
            profile, warning = store.load_profile(root)
            self.assertEqual(profile, store.default_profile())
            self.assertEqual(warning, "拒绝 symlink profile 路径")
            self.assertEqual(engine.config_show(root)["status"], "undetermined")
            with self.assertRaises(ValueError):
                engine.config_set_route(root, "reviewer", "magpie-sol-high")

        with mock.patch.object(Path, "is_symlink", lambda self: self.name == "state.json"):
            value, error, status = facts.read_package_state(root)
            self.assertIsNone(value)
            self.assertEqual(status, "undetermined")
            self.assertIn("symlink state", error)

        rounds_path = root / "execution" / "attempt-1" / "reviews" / "r1.rounds.json"
        with mock.patch.object(Path, "is_symlink",
                               lambda self: self.name.endswith(".rounds.json")):
            summary = facts.read_rounds_summary(rounds_path)
            self.assertEqual(summary["status"], "undetermined")
            self.assertIn("symlink rounds", summary["reasons"][0])


class CliTest(_PackageMixin, unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
        return subprocess.run(
            [sys.executable, str(SCRIPT), *args], capture_output=True, text=True,
            encoding="utf-8", env=env, check=False)

    def test_status_json_and_text_output(self) -> None:
        root = self.build({"TKT-1": "PENDING"})

        as_json = self._run("status", "--package", str(root), "--json")
        self.assertEqual(as_json.returncode, 0, as_json.stderr)
        payload = json.loads(as_json.stdout)
        self.assertEqual([stage["id"] for stage in payload["pipeline"]], STAGES)
        self.assertEqual(payload["package"], str(root.absolute()))

        as_text = self._run("status", "--package", str(root))
        self.assertEqual(as_text.returncode, 0, as_text.stderr)
        self.assertIn("Pipeline:", as_text.stdout)
        self.assertIn("下一步:", as_text.stdout)

    def test_main_reconfigures_console_streams_to_replace_unsupported_text(self) -> None:
        class ReconfigurableStream(io.StringIO):
            def __init__(self) -> None:
                super().__init__()
                self.error_mode = None

            def reconfigure(self, *, errors: str) -> None:
                self.error_mode = errors

        root = self.build({"TKT-1": "PENDING"})
        stdout, stderr = ReconfigurableStream(), ReconfigurableStream()

        with mock.patch.object(sys, "stdout", stdout), mock.patch.object(sys, "stderr", stderr):
            result = dev_loop.main(["status", "--package", str(root)])

        self.assertEqual(result, 0)
        self.assertEqual(stdout.error_mode, "replace")
        self.assertEqual(stderr.error_mode, "replace")
        self.assertIn("下一步:", stdout.getvalue())

    def test_write_commands_print_refreshed_status(self) -> None:
        root = self.build({"TKT-1": "PENDING"})

        routed = self._run("config", "set-route", "--package", str(root),
                           "--role", "reviewer", "--model", "magpie-sol-high",
                           "--effort", "high", "--json")
        self.assertEqual(routed.returncode, 0, routed.stderr)
        payload = json.loads(routed.stdout)
        self.assertIn("pipeline", payload)
        self.assertEqual(payload["routing"]["reviewer"],
                         {"model": "magpie-sol-high", "effort": "high"})
        self.assertTrue((root / ".impl-package" / store.PROFILE_NAME).is_file())

        registered = self._run("agent", "register", "--package", str(root),
                               "--role", "implementer", "--scope", "TKT-1",
                               "--host", "claude", "--json")
        self.assertEqual(registered.returncode, 0, registered.stderr)
        payload = json.loads(registered.stdout)
        self.assertEqual(payload["agents"]["items"][0]["role"], "implementer")
        self.assertEqual(payload["agents"]["items"][0]["scope"], "TKT-1")

    def test_write_error_returns_exit_code_two(self) -> None:
        root = self.build({"TKT-1": "PENDING"}, profile="{broken")

        result = self._run("config", "set-route", "--package", str(root),
                           "--role", "reviewer", "--model", "magpie-sol-high")

        self.assertEqual(result.returncode, 2)
        self.assertIn("dev-loop: profile 未确认", result.stderr)

    def test_gate_pass_conflicts_with_gate_missing_or_incomplete_coverage(self) -> None:
        for slug in ("attempt.gate.missing", "attempt.review.terminal-coverage-incomplete"):
            with self.subTest(slug=slug):
                fake_facts = {
                    "projection": {
                        "sources": {"gate": {"verdict": "pass", "error": None}},
                        "blocking": [{"slug": slug}],
                        "runnable": [],
                        "withheld": [],
                        "matches": [],
                    },
                    "projection_status": "confirmed",
                    "state": {"attempt": {"id": "attempt-1"}, "tickets": {"TKT-1": {"state": "SATISFIED"}}},
                    "state_status": "confirmed",
                    "rounds": [],
                    "pending_returns": [],
                    "warnings": [],
                }
                stages = {row["id"]: row for row in engine.derive_pipeline(fake_facts)}
                self.assertEqual(stages["final-verify"]["status"], "attention")
                self.assertEqual(stages["gate"]["status"], "attention")
                self.assertEqual(stages["closeout"]["status"], "pending")


if __name__ == "__main__":
    unittest.main()
