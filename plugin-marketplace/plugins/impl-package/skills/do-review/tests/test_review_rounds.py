from __future__ import annotations

import importlib.util
import io
import json
import os
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def load_module():
    spec = importlib.util.spec_from_file_location("review_rounds", SCRIPTS / "review_rounds.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewRoundsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        patcher = mock.patch.dict(os.environ, {"TEMP": tmp.name, "TMP": tmp.name})
        patcher.start()
        self.addCleanup(patcher.stop)
        directory = Path(tmp.name).resolve() / "do-review"
        directory.mkdir()
        self.ledger = directory / "2611211200-demo-abc1234.md"
        self.ledger.write_text("# ledger\n", encoding="utf-8")

    def run_cli(self, *argv: str) -> tuple[int, dict | None, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = self.module.main([argv[0], "--ledger", str(self.ledger), *argv[1:]])
        return code, (json.loads(out.getvalue()) if out.getvalue() else None), err.getvalue()

    def open(self, group: str = "g1", *tracks: str):
        args = ["open", "--group", group, "--phase", "terminal-final"]
        for track in tracks or ("Track A", "Track C", "Safety"):
            args += ["--track", track]
        return self.run_cli(*args)

    def record(self, track: str, verdict: str = "PASS"):
        return self.run_cli("record", "--track", track, "--verdict", verdict, "--report", f"{track}.md")

    def test_close_refuses_until_every_track_returned_and_names_the_missing_ones(self) -> None:
        self.assertEqual(self.open()[0], 0)
        self.record("Track A")
        code, _, err = self.run_cli("close")
        self.assertEqual(code, 2)
        self.assertIn("missing tracks: Track C, Safety", err)
        self.record("Track C")
        self.record("Safety")
        code, result, _ = self.run_cli("close")
        self.assertEqual((code, result["overall"], result["needsTriage"]), (0, "PASS", []))

    def test_export_only_after_close_and_lists_reports_to_triage(self) -> None:
        self.open("g1", "Track A", "Track C=magpie-sol-high")
        self.record("Track A", "FAIL")
        self.record("Track C")
        code, _, err = self.run_cli("export")
        self.assertEqual(code, 2)
        self.assertIn("not closed", err)
        self.run_cli("close")
        code, result, _ = self.run_cli("export")
        self.assertEqual((code, result["overall"], result["needsTriage"]), (0, "FAIL", ["Track A"]))
        self.assertEqual(result["tracks"][1]["leaf"], "magpie-sol-high")

    def test_record_rejects_unregistered_duplicate_and_missing_round(self) -> None:
        self.assertEqual(self.record("Track A")[0], 2)
        self.open("g1", "Track A")
        self.assertEqual(self.record("Safety")[0], 2)
        self.assertEqual(self.record("Track A")[0], 0)
        self.assertEqual(self.record("Track A")[0], 2)

    def test_next_round_needs_closed_previous_and_group_stops_after_five_code_rounds(self) -> None:
        self.open("g1", "Track A")
        self.assertEqual(self.open("g1", "Track A")[0], 2)
        for round_number in (1, 2, 3, 4, 5):
            if round_number > 1:
                self.assertEqual(self.open("g1", "Track A")[0], 0)
            self.record("Track A", "UNCERTAIN" if round_number == 1 else "PASS")
            _, closed, _ = self.run_cli("close")
            self.assertEqual(closed["freshGroupRequired"], round_number == 5)
        self.assertEqual(self.run_cli("export", "--round", "1")[1]["overall"], "UNCERTAIN")
        code, _, err = self.open("g1", "Track A")
        self.assertEqual(code, 2)
        self.assertIn("fresh group", err)
        code, result, _ = self.open("g2", "Track A")
        self.assertEqual((code, result["round"], result["groupRound"]), (0, 6, 1))

    def test_group_count_continues_across_ledgers_and_groups_are_independent(self) -> None:
        first = self.ledger
        second = first.with_name("2611211300-demo-def5678.md")
        second.write_text("# ledger 2\n", encoding="utf-8")
        for number in (1, 2, 3, 4):
            self.open("g1", "Track A")
            self.record("Track A")
            self.run_cli("close")
        self.ledger = second
        code, opened, _ = self.open("g1", "Track A")
        self.assertEqual((code, opened["groupRound"]), (0, 5))
        self.record("Track A")
        _, closed, _ = self.run_cli("close")
        self.assertTrue(closed["freshGroupRequired"])
        code, _, err = self.open("g1", "Track A")
        self.assertEqual(code, 2)
        self.assertIn("fresh group", err)
        self.ledger = first
        self.assertEqual(self.open("g1", "Track A")[0], 2)
        code, opened, _ = self.open("g2", "Track A")
        self.assertEqual((code, opened["groupRound"]), (0, 1))

    def test_package_mode_counts_across_ledgers_in_the_attempt_reviews_folder(self) -> None:
        with TemporaryDirectory() as tmp:
            package = Path(tmp).resolve() / "package"
            (package / ".impl-package").mkdir(parents=True)
            (package / ".impl-package" / "state.json").write_text(json.dumps({"attempt": {"id": "initial"}}), encoding="utf-8")
            reviews = package / "execution" / "initial" / "reviews"
            reviews.mkdir(parents=True)
            codes = []
            for index in range(6):
                ledger = reviews / f"261121120{index}-demo-abc123{index}.md"
                ledger.write_text("# ledger\n", encoding="utf-8")
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    argv = ["open", "--package", str(package), "--ledger", str(ledger), "--group", "g1", "--phase", "terminal-final", "--track", "Track A"]
                    codes.append(self.module.main(argv))
                    if codes[-1] == 0:
                        self.module.main(["record", "--package", str(package), "--ledger", str(ledger), "--track", "Track A", "--verdict", "PASS", "--report", "a.md"])
                        self.module.main(["close", "--package", str(package), "--ledger", str(ledger)])
            self.assertEqual(codes, [0, 0, 0, 0, 0, 2])


    # --- group ownership: plan phase, triage, status ---

    def run_round(self, group: str, phase: str, verdict: str = "PASS", succeeds: str | None = None):
        args = ["open", "--group", group, "--phase", phase, "--track", "Track A"]
        if succeeds:
            args += ["--succeeds", succeeds]
        code, opened, err = self.run_cli(*args)
        if code != 0:
            return code, opened, err
        self.record("Track A", verdict)
        return self.run_cli("close")

    def triage(self, *argv: str):
        return self.run_cli("triage", *argv)

    def add(self, group: str, round_number: int, source: str = "impl-drift", klass: str = "design", severity: str = "P1"):
        return self.triage("add", "--group", group, "--round", str(round_number), "--source", source, "--class", klass, "--severity", severity, "--summary", "x")

    def test_plan_rounds_warn_from_the_third_round_but_never_block(self) -> None:
        for number in (1, 2, 3, 4, 5, 6, 7):
            code, opened, _ = self.run_cli("open", "--group", "g1", "--phase", "plan", "--track", "Track A")
            self.assertEqual(code, 0)
            self.assertEqual("warnings" in opened, number >= 3)
            self.record("Track A", "FAIL")
            self.run_cli("close")

    def test_code_is_refused_until_the_group_plan_passed(self) -> None:
        self.run_round("g1", "plan", "FAIL")
        code, _, err = self.open("g1", "Track A")
        self.assertEqual(code, 2)
        self.assertIn("plan must pass", err)
        self.run_round("g1", "plan", "PASS")
        self.assertEqual(self.open("g1", "Track A")[0], 0)

    def test_group_without_plan_rounds_is_not_gated(self) -> None:
        self.assertEqual(self.open("g1", "Track A")[0], 0)

    def test_plan_gap_is_verified_by_the_next_passing_plan_round(self) -> None:
        self.run_round("g1", "plan")
        self.run_round("g1", "initial")
        self.assertEqual(self.add("g1", 2, source="plan-gap")[1]["id"], "F1")
        code, _, err = self.open("g1", "Track A")
        self.assertEqual(code, 2)
        self.assertIn("plan gaps are still open", err)
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "abc")
        self.assertEqual(self.open("g1", "Track A")[0], 2)
        self.run_round("g1", "plan")
        self.assertEqual(self.run_cli("status", "--group", "g1")[1]["findings"]["verified"], 1)
        self.assertEqual(self.open("g1", "Track A")[0], 0)

    def test_plan_gap_fixed_after_the_plan_round_opened_is_not_verified_by_it(self) -> None:
        self.run_round("g1", "plan")
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 2, source="plan-gap")
        self.run_cli("open", "--group", "g1", "--phase", "plan", "--track", "Track A")
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "abc")
        self.record("Track A")
        self.run_cli("close")
        self.assertEqual(self.run_cli("status", "--group", "g1")[1]["findings"]["fixed"], 1)

    def test_triage_needs_a_closed_round_and_verify_needs_a_later_round(self) -> None:
        self.open("g1", "Track A")
        self.assertEqual(self.add("g1", 1)[0], 2)
        self.record("Track A", "FAIL")
        self.run_cli("close")
        self.assertEqual(self.add("g1", 1)[0], 0)
        self.assertEqual(self.triage("verify", "--group", "g1", "--id", "F1", "--round", "1")[0], 2)
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "abc")
        code, _, err = self.triage("verify", "--group", "g1", "--id", "F1", "--round", "1")
        self.assertEqual(code, 2)
        self.assertIn("later round", err)
        self.run_round("g1", "terminal-final")
        self.assertEqual(self.triage("verify", "--group", "g1", "--id", "F1", "--round", "2")[1]["status"], "verified")

    def test_second_reopen_needs_a_root_cut_sentence(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 1)
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "a")
        reopened = self.triage("reopen", "--group", "g1", "--id", "F1")[1]
        self.assertEqual((reopened["reopens"], reopened["status"]), (1, "open"))
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "b")
        code, _, err = self.triage("reopen", "--group", "g1", "--id", "F1")
        self.assertEqual(code, 2)
        self.assertIn("root", err)
        code, result, _ = self.triage("reopen", "--group", "g1", "--id", "F1", "--root-cut", "drop the cross-store path")
        self.assertEqual((code, result["reopens"], result["rootCut"]), (0, 2, "drop the cross-store path"))

    def test_downgrade_needs_a_reason_and_control_findings_can_self_verify(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 1)
        self.add("g1", 1, klass="control")
        self.assertEqual(self.triage("downgrade", "--group", "g1", "--id", "F1")[0], 2)
        self.assertEqual(self.triage("downgrade", "--group", "g1", "--id", "F1", "--reason", "rare")[1]["status"], "downgraded")
        self.assertEqual(self.triage("fixed", "--group", "g1", "--id", "F2", "--commit", "c", "--self-verified")[1]["status"], "verified")
        design = self.add("g1", 1)[1]["id"]
        self.assertEqual(self.triage("fixed", "--group", "g1", "--id", design, "--commit", "c", "--self-verified")[0], 2)

    def test_status_complete_only_when_findings_closed_and_last_round_has_no_new_design_finding(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 1)
        status = self.run_cli("status", "--group", "g1")[1]
        self.assertFalse(status["complete"])
        self.assertEqual(status["findings"]["open"], 1)
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "a")
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 2)
        self.triage("verify", "--group", "g1", "--id", "F1", "--round", "2")
        status = self.run_cli("status", "--group", "g1")[1]
        self.assertFalse(status["complete"])
        self.assertTrue(any("new design findings" in reason for reason in status["reasons"]))
        self.triage("fixed", "--group", "g1", "--id", "F2", "--commit", "b")
        self.run_round("g1", "initial", "PASS")
        self.triage("verify", "--group", "g1", "--id", "F2", "--round", "3")
        status = self.run_cli("status", "--group", "g1")[1]
        self.assertTrue(status["complete"])
        self.assertFalse(status["converged"])
        self.assertIn("fresh group", status["nextAction"])

    def test_fresh_group_that_completes_after_a_complete_group_converges(self) -> None:
        self.run_round("g1", "initial", "PASS")
        self.assertTrue(self.run_cli("status", "--group", "g1")[1]["complete"])
        self.run_round("g2", "initial", "PASS", succeeds="g1")
        status = self.run_cli("status", "--group", "g2")[1]
        self.assertEqual((status["complete"], status["converged"]), (True, True))

    def test_fresh_group_that_raised_design_findings_does_not_converge_until_the_next_fresh_group_is_clean(self) -> None:
        self.run_round("g1", "initial", "PASS")
        self.run_round("g2", "initial", "FAIL", succeeds="g1")
        self.assertEqual(self.triage("add", "--group", "g2", "--round", "2", "--source", "impl-drift", "--class", "design", "--severity", "P1", "--summary", "x")[0], 0)
        self.triage("fixed", "--group", "g2", "--id", "F1", "--commit", "a")
        self.run_round("g2", "initial", "PASS")
        self.triage("verify", "--group", "g2", "--id", "F1", "--round", "3")
        status = self.run_cli("status", "--group", "g2")[1]
        self.assertEqual((status["complete"], status["converged"]), (True, False))
        self.assertIn("another fresh group", status["nextAction"])
        self.run_round("g3", "initial", "PASS", succeeds="g2")
        self.assertTrue(self.run_cli("status", "--group", "g3")[1]["converged"])

    def test_chain_of_unconverged_fresh_groups_warns_without_blocking(self) -> None:
        self.run_round("g1", "initial", "PASS")
        code, opened, _ = self.run_cli("open", "--group", "g2", "--phase", "initial", "--track", "Track A", "--succeeds", "g1")
        self.assertEqual((code, "warnings" in opened), (0, False))
        self.record("Track A")
        self.run_cli("close")
        code, opened, _ = self.run_cli("open", "--group", "g3", "--phase", "initial", "--track", "Track A", "--succeeds", "g2")
        self.assertEqual((code, "warnings" in opened), (0, True))

    def state_of(self, group: str) -> str:
        return self.run_cli("status", "--group", group)[1]["state"]

    def test_state_follows_the_transition_table(self) -> None:
        self.run_round("g1", "plan", "FAIL")
        self.assertEqual(self.state_of("g1"), "plan-open")
        self.run_round("g1", "plan", "PASS")
        self.assertEqual(self.state_of("g1"), "plan-pass")
        self.run_cli("open", "--group", "g1", "--phase", "initial", "--track", "Track A")
        self.assertEqual(self.state_of("g1"), "code-open")
        self.record("Track A", "FAIL")
        self.run_cli("close")
        self.assertEqual(self.state_of("g1"), "code-closed")
        self.add("g1", 3, source="plan-gap")
        self.assertEqual(self.state_of("g1"), "plan-open")
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "a")
        self.run_round("g1", "plan")
        self.assertEqual(self.state_of("g1"), "code-closed")
        self.run_round("g2", "initial", "PASS", succeeds="g1")
        self.assertEqual(self.state_of("g2"), "converged")

    def test_cap_reached_flag_when_five_code_rounds_leave_findings_unresolved(self) -> None:
        for _ in range(5):
            self.run_round("g1", "initial", "FAIL")
        self.add("g1", 5)
        status = self.run_cli("status", "--group", "g1")[1]
        self.assertEqual((status["state"], status["capReached"]), ("code-closed", True))
        self.assertEqual(self.open("g1", "Track A")[0], 2)

    def test_fresh_group_takes_over_unresolved_findings_and_the_chain_can_converge(self) -> None:
        for _ in range(5):
            self.run_round("g1", "initial", "FAIL")
        self.add("g1", 5)
        self.add("g1", 5)
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "a")
        code, opened, _ = self.run_cli("open", "--group", "g2", "--phase", "initial", "--track", "Track A", "--succeeds", "g1")
        self.assertEqual((code, opened["takenOver"]), (0, ["F1", "F2"]))
        self.record("Track A", "PASS")
        self.run_cli("close")
        self.assertEqual(self.state_of("g1"), "code-closed")
        self.assertEqual(self.run_cli("status", "--group", "g2")[1]["findings"]["open"], 1)
        self.triage("verify", "--group", "g2", "--id", "F1")
        self.triage("fixed", "--group", "g2", "--id", "F2", "--commit", "b")
        self.run_round("g2", "initial", "PASS")
        self.triage("verify", "--group", "g2", "--id", "F2")
        self.assertEqual(self.add("g2", 7)[1]["id"], "F3")
        self.assertFalse(self.run_cli("status", "--group", "g2")[1]["converged"])
        self.triage("downgrade", "--group", "g2", "--id", "F3", "--reason", "rare")
        status = self.run_cli("status", "--group", "g2")[1]
        self.assertEqual((status["complete"], status["converged"]), (True, True))

    def test_fresh_group_needs_a_complete_or_capped_predecessor(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        self.add("g1", 1)
        code, _, err = self.run_cli("open", "--group", "g2", "--phase", "initial", "--track", "Track A", "--succeeds", "g1")
        self.assertEqual(code, 2)
        self.assertIn("predecessor", err)

    def test_triage_defaults_to_the_groups_latest_closed_round(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        code, finding, _ = self.triage("add", "--group", "g1", "--source", "impl-drift", "--class", "design", "--severity", "P1", "--summary", "x")
        self.assertEqual((code, finding["round"]), (0, 1))
        self.triage("fixed", "--group", "g1", "--id", "F1", "--commit", "a")
        self.run_round("g1", "initial", "PASS")
        self.assertEqual(self.triage("verify", "--group", "g1", "--id", "F1")[1]["status"], "verified")

    def test_severity_is_required_and_p2_is_not_downgraded_automatically(self) -> None:
        self.run_round("g1", "initial", "FAIL")
        code, _, err = self.triage("add", "--group", "g1", "--round", "1", "--source", "impl-drift", "--class", "design", "--summary", "x")
        self.assertEqual(code, 2)
        self.assertIn("--severity", err)
        self.assertEqual(self.add("g1", 1, severity="P2")[1]["status"], "open")
        self.assertFalse(self.run_cli("status", "--group", "g1")[1]["complete"])

    def test_plan_warning_counts_from_the_last_passed_plan_round(self) -> None:
        warned = []
        for verdict in ("FAIL", "FAIL", "PASS", "FAIL", "FAIL", "FAIL"):
            _, opened, _ = self.run_cli("open", "--group", "g1", "--phase", "plan", "--track", "Track A")
            warned.append("warnings" in opened)
            self.record("Track A", verdict)
            self.run_cli("close")
        self.assertEqual(warned, [False, False, True, False, False, True])

    def test_status_of_a_group_without_rounds_is_an_error(self) -> None:
        self.assertEqual(self.run_cli("status", "--group", "nobody")[0], 2)

    def test_old_state_without_findings_still_loads(self) -> None:
        self.open("g1", "Track A")
        path = self.ledger.with_suffix(".rounds.json")
        state = json.loads(path.read_text(encoding="utf-8"))
        state.pop("findings")
        state["schemaVersion"] = 1
        for r in state["rounds"]:
            r.pop("ledger", None)
        path.write_text(json.dumps(state), encoding="utf-8")
        self.record("Track A")
        self.assertEqual(self.run_cli("close")[0], 0)
        self.assertTrue(self.run_cli("status", "--group", "g1")[1]["complete"])


if __name__ == "__main__":
    unittest.main()
