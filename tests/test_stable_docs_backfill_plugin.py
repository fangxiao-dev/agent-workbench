from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
PLUGIN_ROOT = REPO_ROOT / "plugins" / "stable-docs-backfill"
VERIFY_SCRIPT = PLUGIN_ROOT / "scripts" / "verify_stable_docs.py"
CONFIG_SCRIPT = PLUGIN_ROOT / "scripts" / "validate_config.py"
ITEM_ID_SCRIPT = PLUGIN_ROOT / "scripts" / "make_item_id.py"


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def commit_all(root: Path, message: str) -> str:
    run_git(root, "add", ".")
    run_git(root, "commit", "-m", message)
    return run_git(root, "rev-parse", "HEAD")


class StableDocsBackfillPluginTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "project"
        self.project.mkdir()
        run_git(self.project, "init")
        run_git(self.project, "config", "user.email", "test@example.com")
        run_git(self.project, "config", "user.name", "Test User")
        (self.project / "README.md").write_text("baseline\n", encoding="utf-8")
        self.initial = commit_all(self.project, "initial")

        (self.project / "docs" / "canonical").mkdir(parents=True)
        (self.project / "docs" / "canonical" / "module.md").write_text(
            "# Module\n", encoding="utf-8"
        )
        (self.project / "docs" / "implementations" / "example").mkdir(parents=True)
        (self.project / "docs" / "implementations" / "example" / "spec.md").write_text(
            "# Example\n", encoding="utf-8"
        )
        (self.project / "docs" / "pending.md").write_text("# Pending\n", encoding="utf-8")
        (self.project / "docs" / "compaction").mkdir(parents=True)
        self.state_path = self.project / "docs" / "compaction" / "state.json"
        self.write_state(self.initial, [])
        self.audited_head = commit_all(self.project, "canonical baseline")

        self.config_path = self.root / "repository-config.json"
        config = {
            "schemaVersion": 1,
            "canonicalDocs": [
                {
                    "path": "docs/canonical",
                    "role": "module-spec",
                    "owner": "module-owner",
                }
            ],
            "pendingPath": "docs/pending.md",
            "compactionPath": "docs/compaction",
            "statePath": "docs/compaction/state.json",
            "implementationsPath": "docs/implementations",
            "excludePaths": [],
            "dangerRules": [],
        }
        config_bytes = (json.dumps(config, indent=2) + "\n").encode("utf-8")
        self.config_path.write_bytes(config_bytes)
        self.config_sha = hashlib.sha256(config_bytes).hexdigest()
        self.audit_path = self.root / "audit.json"

    def write_state(self, watermark: str, carry_forward: list[str]) -> None:
        self.state_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "method_activation": {
                        "plugin": "stable-docs-backfill",
                        "version": "0.1.0",
                    },
                    "project": {"source_watermark": watermark},
                    "carry_forward": carry_forward,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def write_audit(self, **overrides: object) -> dict[str, object]:
        payload: dict[str, object] = {
            "schemaVersion": 1,
            "mode": "audit",
            "methodActivation": {
                "plugin": "stable-docs-backfill",
                "version": "0.1.0",
            },
            "project": {
                "sourceHead": self.audited_head,
                "projectSourceWatermark": self.initial,
                "dirtyPaths": [],
            },
            "configSha256": self.config_sha,
            "moduleCoverage": [],
            "items": [],
            "pending": [],
            "carryForward": [],
            "removedPackages": [],
            "blockers": [],
        }
        payload.update(overrides)
        self.audit_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )
        return payload

    def run_verify(self, *extra: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [
                sys.executable,
                str(VERIFY_SCRIPT),
                "--project-root",
                str(self.project),
                "--config",
                str(self.config_path),
                "--audit-json",
                str(self.audit_path),
                *extra,
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )

    def make_item(self) -> dict[str, object]:
        source = "docs/implementations/example/spec.md"
        destination = "docs/canonical/module.md"
        statement = "The module exposes a durable contract."
        item_id = subprocess.run(
            [
                sys.executable,
                str(ITEM_ID_SCRIPT),
                "--source",
                source,
                "--destination",
                destination,
                "--statement",
                statement,
            ],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        return {
            "id": item_id,
            "source": source,
            "destination": destination,
            "statement": statement,
            "disposition": "candidate",
        }

    def test_verify_uses_audited_source_head_for_watermark_safety(self) -> None:
        self.write_audit()
        (self.project / "after-audit.md").write_text("new\n", encoding="utf-8")
        post_audit_head = commit_all(self.project, "after audit")
        self.write_state(post_audit_head, [])

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        state_check = next(
            check for check in payload["checks"] if check["check"] == "state-watermark"
        )
        self.assertEqual(state_check["result"], "failed")
        self.assertIn("not an ancestor", state_check["detail"])

    def test_verify_rejects_audit_from_different_config(self) -> None:
        self.write_audit(configSha256="0" * 64)

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        payload = json.loads(completed.stdout)
        audit_check = next(
            check for check in payload["checks"] if check["check"] == "audit-contract"
        )
        self.assertEqual(audit_check["result"], "failed")
        self.assertIn("configSha256", audit_check["detail"])

    def test_verify_requires_reconciliation_arrays_in_audit(self) -> None:
        payload = self.write_audit()
        del payload["carryForward"]
        self.audit_path.write_text(
            json.dumps(payload, indent=2) + "\n", encoding="utf-8"
        )

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        audit_check = next(
            check
            for check in json.loads(completed.stdout)["checks"]
            if check["check"] == "audit-contract"
        )
        self.assertIn("carryForward", audit_check["detail"])

    def test_verify_reconciles_items_with_module_coverage_references(self) -> None:
        item = self.make_item()
        self.write_audit(
            items=[item],
            moduleCoverage=[
                {
                    "module": "module",
                    "result": "candidate",
                    "itemIds": ["SDB-000000000000"],
                }
            ],
        )

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        audit_check = next(
            check
            for check in json.loads(completed.stdout)["checks"]
            if check["check"] == "audit-contract"
        )
        self.assertIn("unknown item ID", audit_check["detail"])

    def test_verify_reconciles_audit_and_state_carry_forward(self) -> None:
        self.write_audit(carryForward=["example"])

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        state_check = next(
            check
            for check in json.loads(completed.stdout)["checks"]
            if check["check"] == "state-watermark"
        )
        self.assertEqual(state_check["result"], "failed")
        self.assertIn("carry-forward mismatch", state_check["detail"])

    def test_verify_requires_audit_pending_ids_in_pending_register(self) -> None:
        self.write_audit(pending=["PEND-001"])

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        state_check = next(
            check
            for check in json.loads(completed.stdout)["checks"]
            if check["check"] == "state-watermark"
        )
        self.assertIn("PEND-001", state_check["detail"])

    def test_verify_rejects_unreferenced_audit_item(self) -> None:
        item = self.make_item()
        self.write_audit(
            items=[item],
            moduleCoverage=[
                {"module": "module", "result": "candidate", "itemIds": []}
            ],
        )

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 2)
        audit_check = next(
            check
            for check in json.loads(completed.stdout)["checks"]
            if check["check"] == "audit-contract"
        )
        self.assertIn("missing from moduleCoverage", audit_check["detail"])

    def test_verify_rejects_conflicting_explicit_source_head(self) -> None:
        self.write_audit()
        (self.project / "later.md").write_text("later\n", encoding="utf-8")
        later_head = commit_all(self.project, "later")

        completed = self.run_verify("--source-head", later_head)

        self.assertEqual(completed.returncode, 2)
        self.assertIn("conflicts", json.loads(completed.stdout)["error"])

    def test_matching_audit_state_and_pending_register_pass(self) -> None:
        (self.project / "docs" / "pending.md").write_text(
            "# Pending\n\n- PEND-001\n", encoding="utf-8"
        )
        self.write_state(self.initial, ["example"])
        self.write_audit(pending=["PEND-001"], carryForward=["example"])

        completed = self.run_verify()

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertTrue(json.loads(completed.stdout)["passed"])

    def test_config_validator_rejects_parent_path(self) -> None:
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["pendingPath"] = "../pending.md"
        self.config_path.write_text(
            json.dumps(config, indent=2) + "\n", encoding="utf-8"
        )

        completed = subprocess.run(
            [
                sys.executable,
                str(CONFIG_SCRIPT),
                "--project-root",
                str(self.project),
                "--config",
                str(self.config_path),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("parent segments", completed.stderr)

    def test_item_id_is_stable_across_whitespace(self) -> None:
        common = [
            sys.executable,
            str(ITEM_ID_SCRIPT),
            "--source",
            "docs/implementations/example/spec.md",
            "--destination",
            "docs/canonical/module.md",
        ]
        first = subprocess.run(
            [*common, "--statement", "A durable contract."],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()
        second = subprocess.run(
            [*common, "--statement", " A   durable contract. "],
            check=True,
            text=True,
            stdout=subprocess.PIPE,
        ).stdout.strip()

        self.assertEqual(first, second)
        self.assertRegex(first, r"^SDB-[0-9a-f]{12}$")


if __name__ == "__main__":
    unittest.main()
