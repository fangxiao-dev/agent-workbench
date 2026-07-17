from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "skills" / "impl-package" / "backfill-stable-docs" / "scripts"
VERIFY = SCRIPTS / "verify_stable_docs.py"


def git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, text=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    ).stdout.strip()


def base_config(**overrides: object) -> dict[str, object]:
    config: dict[str, object] = {
        "contractVersion": "3.1",
        "repository": "example/project",
        "targetBranch": "HEAD",
        "implementations": ["docs/implementations"],
        "stableDocs": {
            "systemKnowledge": ["docs/system-knowledge"],
            "moduleKnowledge": ["docs/module-knowledge"],
        },
        "ignore": [],
        "records": {
            "pending": "auto",
            "pendingOverrides": {},
            "done": "docs/_backfill/done.json",
            "reports": "docs/_backfill/reports",
        },
    }
    config.update(overrides)
    return config


def build_healthy_repo(project: Path) -> None:
    project.mkdir(parents=True, exist_ok=True)
    git(project, "init")
    git(project, "config", "user.email", "test@example.com")
    git(project, "config", "user.name", "Test")
    git(project, "remote", "add", "origin", "https://github.com/example/project.git")
    (project / "docs/system-knowledge").mkdir(parents=True)
    (project / "docs/system-knowledge/README.md").write_text("# System knowledge\n", encoding="utf-8")
    (project / "docs/module-knowledge").mkdir(parents=True)
    (project / "docs/module-knowledge/_pending.md").write_text("# Pending\n", encoding="utf-8")
    (project / "docs/implementations/alpha").mkdir(parents=True)
    (project / "docs/implementations/alpha/spec.md").write_text("# alpha\n", encoding="utf-8")
    (project / "docs/implementations/alpha/.impl-package").mkdir()
    (project / "docs/implementations/alpha/.impl-package/runtime-state.json").write_text(
        json.dumps({
            "contractVersion": "3.1",
            "purpose": "internal-machine-sidecar",
            "ownerFacing": False,
            "packageId": "alpha",
            "tasks": [],
            "tickets": [],
            "artifacts": [],
            "gate": {"allocations": [], "entries": []},
        }),
        encoding="utf-8",
    )
    (project / "docs/implementations/alpha/.impl-package/revision-bindings.json").write_text(
        json.dumps({
            "contractVersion": "3.1",
            "purpose": "internal-machine-sidecar",
            "ownerFacing": False,
            "current": {},
            "bindings": [],
        }),
        encoding="utf-8",
    )
    (project / ".stable-docs-backfill.json").write_text(json.dumps(base_config()), encoding="utf-8")
    git(project, "add", ".")
    git(project, "commit", "-m", "baseline")


def run_verify(project: Path, *extra: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        ["python", str(VERIFY), "--project-root", str(project), *extra],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.returncode, json.loads(completed.stdout)


class HealthyRepoTest(unittest.TestCase):
    def test_all_checks_pass_on_a_healthy_repo(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            build_healthy_repo(project)
            returncode, payload = run_verify(project)
            self.assertEqual(returncode, 0)
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["contractVersion"], "3.1")
            self.assertEqual(payload["summary"]["failed"], 0)
            names = {check["check"] for check in payload["checks"]}
            self.assertEqual(
                names,
                {
                    "contract-preflight",
                    "configured-paths",
                    "target-branch",
                    "pending-discovery",
                    "canonical-links",
                    "audit-contract",
                    "inventory-candidates",
                },
            )
            pending_check = next(c for c in payload["checks"] if c["check"] == "pending-discovery")
            self.assertIn("1 cold-start", pending_check["detail"])
            inventory_check = next(c for c in payload["checks"] if c["check"] == "inventory-candidates")
            self.assertIn("indexed=0", inventory_check["detail"])
            self.assertIn("mismatch=0", inventory_check["detail"])
            self.assertIn("manual=0", inventory_check["detail"])


class PendingDiscoveryAmbiguityTest(unittest.TestCase):
    def test_ambiguous_pending_md_fails_pending_discovery_check(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            build_healthy_repo(project)
            # Add a second _pending.md one level up from module-knowledge -> ambiguous.
            (project / "docs/_pending.md").write_text("# also pending\n", encoding="utf-8")
            git(project, "add", ".")
            git(project, "commit", "-m", "introduce ambiguity")
            returncode, payload = run_verify(project)
            self.assertEqual(returncode, 2)
            self.assertFalse(payload["passed"])
            pending_check = next(c for c in payload["checks"] if c["check"] == "pending-discovery")
            self.assertEqual(pending_check["result"], "failed")
            self.assertIn("ambiguous", pending_check["detail"])


class TargetBranchResolutionTest(unittest.TestCase):
    def test_unresolvable_target_branch_fails_as_config_gap(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            build_healthy_repo(project)
            config_path = project / ".stable-docs-backfill.json"
            config = json.loads(config_path.read_text(encoding="utf-8"))
            config["targetBranch"] = "origin/does-not-exist"
            config_path.write_text(json.dumps(config), encoding="utf-8")

            returncode, payload = run_verify(project)
            self.assertEqual(returncode, 2)
            target_check = next(c for c in payload["checks"] if c["check"] == "target-branch")
            self.assertEqual(target_check["result"], "failed")
            self.assertIn("does not resolve", target_check["detail"])


class AuditContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        build_healthy_repo(self.project)
        self.audit_path = self.project / "audit.json"

    def _run(self) -> tuple[int, dict[str, object]]:
        return run_verify(self.project, "--audit-json", str(self.audit_path))

    def test_legacy_schema_version_is_rejected(self) -> None:
        self.audit_path.write_text(json.dumps({"contractVersion": "3.0", "mode": "audit", "items": []}), encoding="utf-8")
        returncode, payload = self._run()
        self.assertEqual(returncode, 2)
        audit_check = next(c for c in payload["checks"] if c["check"] == "audit-contract")
        self.assertEqual(audit_check["result"], "failed")
        self.assertIn("contractVersion", audit_check["detail"])

    def test_pending_registry_item_without_pending_ref_is_rejected(self) -> None:
        audit = {
            "contractVersion": "3.1",
            "mode": "audit",
            "items": [
                {
                    "id": "SDB-abc123abc123",
                    "origin": "pending-registry",
                    "source": "docs/implementations/alpha/spec.md",
                    "statement": "some delta",
                    "disposition": "candidate",
                }
            ],
            "pendingClosures": [],
            "gapCatchingCandidates": [],
            "retirementCandidates": [],
            "blockers": [],
        }
        self.audit_path.write_text(json.dumps(audit), encoding="utf-8")
        returncode, payload = self._run()
        self.assertEqual(returncode, 2)
        audit_check = next(c for c in payload["checks"] if c["check"] == "audit-contract")
        self.assertEqual(audit_check["result"], "failed")
        self.assertIn("pendingRef", audit_check["detail"])

    def test_valid_current_contract_audit_passes(self) -> None:
        audit = {
            "contractVersion": "3.1",
            "mode": "audit",
            "items": [
                {
                    "id": "SDB-abc123abc123",
                    "origin": "gap-catching",
                    "source": "docs/implementations/alpha/spec.md",
                    "statement": "some delta",
                    "disposition": "candidate",
                }
            ],
            "pendingClosures": [],
            "gapCatchingCandidates": ["alpha"],
            "retirementCandidates": [],
            "blockers": [],
        }
        self.audit_path.write_text(json.dumps(audit), encoding="utf-8")
        returncode, payload = self._run()
        self.assertEqual(returncode, 0)
        self.assertTrue(payload["passed"])


if __name__ == "__main__":
    unittest.main()
