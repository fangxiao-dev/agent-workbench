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

    def test_next_round_needs_closed_previous_and_group_stops_after_three(self) -> None:
        self.open("g1", "Track A")
        self.assertEqual(self.open("g1", "Track A")[0], 2)
        for round_number in (1, 2, 3):
            if round_number > 1:
                self.assertEqual(self.open("g1", "Track A")[0], 0)
            self.record("Track A", "UNCERTAIN" if round_number == 1 else "PASS")
            _, closed, _ = self.run_cli("close")
            self.assertEqual(closed["freshGroupRequired"], round_number == 3)
        self.assertEqual(self.run_cli("export", "--round", "1")[1]["overall"], "UNCERTAIN")
        code, _, err = self.open("g1", "Track A")
        self.assertEqual(code, 2)
        self.assertIn("fresh group", err)
        code, result, _ = self.open("g2", "Track A")
        self.assertEqual((code, result["round"], result["groupRound"]), (0, 4, 1))

    def test_group_count_continues_across_ledgers_and_groups_are_independent(self) -> None:
        first = self.ledger
        second = first.with_name("2611211300-demo-def5678.md")
        second.write_text("# ledger 2\n", encoding="utf-8")
        for number in (1, 2):
            self.open("g1", "Track A")
            self.record("Track A")
            self.run_cli("close")
        self.ledger = second
        code, opened, _ = self.open("g1", "Track A")
        self.assertEqual((code, opened["groupRound"]), (0, 3))
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
            for index in range(4):
                ledger = reviews / f"261121120{index}-demo-abc123{index}.md"
                ledger.write_text("# ledger\n", encoding="utf-8")
                out, err = io.StringIO(), io.StringIO()
                with redirect_stdout(out), redirect_stderr(err):
                    argv = ["open", "--package", str(package), "--ledger", str(ledger), "--group", "g1", "--phase", "terminal-final", "--track", "Track A"]
                    codes.append(self.module.main(argv))
                    if codes[-1] == 0:
                        self.module.main(["record", "--package", str(package), "--ledger", str(ledger), "--track", "Track A", "--verdict", "PASS", "--report", "a.md"])
                        self.module.main(["close", "--package", str(package), "--ledger", str(ledger)])
            self.assertEqual(codes, [0, 0, 0, 2])


if __name__ == "__main__":
    unittest.main()
