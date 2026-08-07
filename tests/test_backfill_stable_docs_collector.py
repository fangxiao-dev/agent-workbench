from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "impl-package" / "backfill-stable-docs" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import collect_sources  # noqa: E402
import make_item_id  # noqa: E402
import stable_docs_config  # noqa: E402


def git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True)
    return result.stdout.strip()


class CollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.project = Path(self.temp.name)
        git(self.project, "init")
        git(self.project, "config", "user.email", "test@example.com")
        git(self.project, "config", "user.name", "Test")
        for value in ("docs/implementations/example", "docs/system-knowledge", "docs/module-knowledge"):
            (self.project / value).mkdir(parents=True, exist_ok=True)
        (self.project / "docs/system-knowledge/index.md").write_text("# System\n", encoding="utf-8")
        (self.project / "docs/module-knowledge/example.md").write_text("# Module\n", encoding="utf-8")
        self.config = {
            "targetBranch": "HEAD",
            "implementations": ["docs/implementations"],
            "stableDocs": {
                "systemKnowledge": ["docs/system-knowledge"],
                "contextKnowledge": [],
                "moduleKnowledge": ["docs/module-knowledge"],
            },
            "ignore": [],
            "records": {"pending": [], "done": "docs/done.json"},
        }
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(self.config), encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", "fixture")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write_gate(self, *, head: str | None = None, deltas: list[str] | None = None, none: bool = False) -> str:
        commit = head or git(self.project, "rev-parse", "HEAD")
        lines = [
            "# Gate\n",
            "\n",
            "- Verdict: pass\n",
            "- Attempt: initial\n",
            f"- Comparison commit: {commit}\n",
            "\n",
            "## Durable Deltas\n",
            "\n",
        ]
        if none:
            lines.extend(["- none\n", "- Reason: no durable project knowledge\n"])
        else:
            for delta in deltas or ["DD-1: Example durable fact"]:
                lines.append(f"- {delta}\n")
        (self.project / "docs/implementations/example/gate.md").write_text("".join(lines), encoding="utf-8")
        return commit

    def _write_done(self, items: list[dict]) -> None:
        (self.project / "docs/done.json").write_text(json.dumps({"items": items}), encoding="utf-8")

    def test_config_uses_explicit_repository_relative_paths(self) -> None:
        validated = stable_docs_config.validate_config(self.config)
        self.assertEqual(validated["records"]["pending"], [])
        self.assertNotIn("reports", validated["records"])
        for invalid in ("C:/outside", "../outside", "docs/*"):
            changed = json.loads(json.dumps(self.config))
            changed["implementations"] = [invalid]
            with self.assertRaises(stable_docs_config.ConfigError):
                stable_docs_config.validate_config(changed)
        changed = json.loads(json.dumps(self.config))
        changed["ignore"] = [{"path": "docs/implementations/example", "owner": "repo-wide"}]
        with self.assertRaisesRegex(stable_docs_config.ConfigError, "owner, and reason"):
            stable_docs_config.validate_config(changed)
        changed["ignore"] = [{"path": "docs/implementations/example", "owner": "repo-wide", "reason": "fixture"}]
        validated = stable_docs_config.validate_config(changed)
        self.assertEqual(validated["ignore"][0]["owner"], "repo-wide")

    def test_pending_is_optional_and_reports_is_not_a_config_field(self) -> None:
        minimal = json.loads(json.dumps(self.config))
        del minimal["records"]["pending"]
        validated = stable_docs_config.validate_config(minimal)
        self.assertEqual(validated["records"]["pending"], [])
        with_reports = json.loads(json.dumps(self.config))
        with_reports["records"]["reports"] = "docs/reports"
        with self.assertRaisesRegex(stable_docs_config.ConfigError, "unknown records fields"):
            stable_docs_config.validate_config(with_reports)

    def test_inventory_enumerates_gap_catching_items_with_delta_ids(self) -> None:
        head = self._write_gate(deltas=["DD-1: Example durable fact"])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["packageCount"], 1)
        row = inventory["packages"][0]
        self.assertEqual(row["gateRecognition"], "current")
        self.assertTrue(row["durableDeltaCandidate"])
        self.assertTrue(row["targetReachable"])
        self.assertEqual(row["origin"], "gap-catching")
        self.assertEqual(inventory["gapCatchingCandidates"], ["docs/implementations/example::DD-1"])
        self.assertEqual(inventory["items"][0]["origin"], "gap-catching")
        self.assertEqual(inventory["items"][0]["status"], "candidate")
        self.assertEqual(inventory["items"][0]["comparisonCommit"], head)
        self.assertEqual(inventory["sourceWorktree"]["head"], head)
        self.assertEqual(inventory["config"]["source"], ".stable-docs-backfill.json")
        self.assertEqual(inventory["done"]["status"], "missing")

    def test_gate_none_produces_no_candidates(self) -> None:
        self._write_gate(none=True)
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], [])
        self.assertEqual(inventory["durableDeltaCandidates"], [])
        self.assertEqual(inventory["packages"][0]["durableDeltaStatus"], "none")
        self.assertFalse(inventory["packages"][0]["gapCatchingCandidate"])

    def test_pending_registry_is_optional_supplement_even_without_terminal_gate(self) -> None:
        (self.project / "docs/_pending.md").write_text("- docs/implementations/example::DD-1\n", encoding="utf-8")
        self.config["records"]["pending"] = ["docs/_pending.md"]
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(self.config), encoding="utf-8")
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["pendingRegistryCandidates"], ["docs/implementations/example::DD-1"])
        self.assertEqual(inventory["items"][0]["origin"], "pending-registry")
        self.assertTrue(inventory["packages"][0]["pendingRegistered"])
        self.assertFalse(inventory["packages"][0]["gapCatchingCandidate"])

    def test_empty_pending_does_not_block_gap_catching(self) -> None:
        self._write_gate(deltas=["DD-1: Fact"])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["pending"], [])
        self.assertEqual(inventory["gapCatchingCandidates"], ["docs/implementations/example::DD-1"])

    def test_done_filters_gap_catching_and_does_not_repeat(self) -> None:
        head = self._write_gate(deltas=["DD-1: Fact", "DD-2: Other"])
        self._write_done([
            {
                "id": "docs/implementations/example::DD-1",
                "packagePath": "docs/implementations/example",
                "deltaId": "DD-1",
                "comparisonCommit": head,
                "disposition": "applied",
            }
        ])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], ["docs/implementations/example::DD-2"])
        self.assertEqual(len(inventory["doneFilteredItems"]), 1)
        self.assertEqual(inventory["doneFilteredItems"][0]["id"], "docs/implementations/example::DD-1")
        self.assertIn("records.done", inventory["doneFilteredItems"][0]["doneFilterReason"])
        # Deleting pending (or having none) must not reintroduce the done item.
        self.assertNotIn("docs/implementations/example::DD-1", inventory["durableDeltaCandidates"])

    def test_done_filters_after_pending_removed(self) -> None:
        head = self._write_gate(deltas=["DD-1: Fact"])
        self._write_done([
            {
                "id": "docs/implementations/example::DD-1",
                "packagePath": "docs/implementations/example",
                "deltaId": "DD-1",
                "comparisonCommit": head,
                "disposition": "applied",
            }
        ])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], [])
        self.assertEqual(inventory["doneFilteredItems"][0]["id"], "docs/implementations/example::DD-1")

    def test_done_without_comparison_commit_does_not_suppress_new_gate(self) -> None:
        head = self._write_gate(deltas=["DD-1: Fact"])
        self._write_done([{"id": "docs/implementations/example::DD-1", "disposition": "applied"}])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], ["docs/implementations/example::DD-1"])
        self.assertEqual(inventory["items"][0]["comparisonCommit"], head)

    def test_new_comparison_commit_reopens_candidate(self) -> None:
        first = self._write_gate(deltas=["DD-1: Fact"])
        self._write_done([
            {
                "id": "docs/implementations/example::DD-1",
                "packagePath": "docs/implementations/example",
                "deltaId": "DD-1",
                "comparisonCommit": first,
                "disposition": "applied",
            }
        ])
        (self.project / "docs/module-knowledge/example.md").write_text("# Module\nupdated\n", encoding="utf-8")
        git(self.project, "add", ".")
        git(self.project, "commit", "-m", "patch")
        second = git(self.project, "rev-parse", "HEAD")
        self._write_gate(head=second, deltas=["DD-1: Fact revised"])
        inventory = collect_sources.collect_inventory(self.project)
        self.assertEqual(inventory["gapCatchingCandidates"], ["docs/implementations/example::DD-1"])
        self.assertEqual(inventory["items"][0]["comparisonCommit"], second)
        self.assertEqual(inventory["items"][0]["status"], "candidate")

    def test_pending_does_not_suppress_gap_catching(self) -> None:
        self._write_gate(deltas=["DD-1: Fact"])
        (self.project / "docs/_pending.md").write_text("- docs/implementations/example::DD-2\n", encoding="utf-8")
        self.config["records"]["pending"] = ["docs/_pending.md"]
        (self.project / ".stable-docs-backfill.json").write_text(json.dumps(self.config), encoding="utf-8")
        inventory = collect_sources.collect_inventory(self.project)
        self.assertIn("docs/implementations/example::DD-1", inventory["gapCatchingCandidates"])
        self.assertIn("docs/implementations/example::DD-2", inventory["pendingRegistryCandidates"])

    def test_readable_item_id_uses_source_and_delta(self) -> None:
        self.assertEqual(make_item_id.make_item_id("docs/implementations/example", "DD-1"), "docs/implementations/example::DD-1")
        with self.assertRaises(ValueError):
            make_item_id.make_item_id("../outside", "DD-1")

    def test_parse_durable_deltas_none_and_ids(self) -> None:
        none = collect_sources.parse_durable_deltas("## Durable Deltas\n\n- none\n- Reason: empty\n")
        self.assertEqual(none["status"], "none")
        self.assertEqual(none["deltas"], [])
        parsed = collect_sources.parse_durable_deltas("## Durable Deltas\n\n- DD-1: Hello world\n- DD-2: Second\n")
        self.assertEqual(parsed["status"], "ok")
        self.assertEqual([row["deltaId"] for row in parsed["deltas"]], ["DD-1", "DD-2"])


if __name__ == "__main__":
    unittest.main()
