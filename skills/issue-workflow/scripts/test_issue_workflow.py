import json
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts" / "issue_workflow.py"
CONTRACT = ROOT / "references" / "issue-contract.yaml"
FIXTURES = ROOT / "scripts" / "fixtures"


def run(*args):
    result = subprocess.run(["python", str(CLI), "--contract", str(CONTRACT), *args], capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout else {}


class IssueWorkflowTests(unittest.TestCase):
    def test_contract_and_six_scenarios_without_gh_write(self):
        contract = run("contract-check", "--initiative-template", str(ROOT / "templates" / "initiative.md"), "--identity", str(FIXTURES / "identity.yaml"))
        self.assertTrue(contract["ok"])
        self.assertEqual(contract["contractVersion"], 2)
        self.assertEqual(contract["aliases"]["@同事"], "haisapan")
        with tempfile.TemporaryDirectory() as temp_dir:
            snapshot_path = Path(temp_dir) / "snapshot.json"
            run("snapshot", "--input", str(FIXTURES / "six-scenarios.json"), "--output", str(snapshot_path))
            snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
            audit = run("validate", "--snapshot", str(snapshot_path))
            self.assertEqual([item["issue"] for item in audit["hardViolations"]], [106])
            portfolio = run("report", "--snapshot", str(snapshot_path), "--mode", "portfolio")
            self.assertEqual(portfolio["counts"]["initiatives"], 1)
            self.assertEqual(portfolio["counts"]["blocked"], 1)
            intent = {"snapshotContractVersion": snapshot["contractVersion"], "changes": [{"issue": 103, "labels": ["doc", "ready-for-agent"], "people": [{"kind": "issueAssignee", "alias": "@同事"}]}]}
            intent_path = Path(temp_dir) / "intent.json"
            intent_path.write_text(json.dumps(intent), encoding="utf-8")
            planned = run("plan", "--snapshot", str(snapshot_path), "--intent", str(intent_path), "--identity", str(FIXTURES / "identity.yaml"))
            self.assertEqual(planned["operations"][0]["status"], "ready-for-confirmation")
            self.assertEqual(planned["operations"][1]["login"], "haisapan")
            self.assertIn("not applied", planned["writeBoundary"])


if __name__ == "__main__":
    unittest.main()
