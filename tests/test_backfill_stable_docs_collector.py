from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PLUGIN_ROOT = (
    Path(__file__).resolve().parents[1] / "plugins" / "stable-docs-backfill"
)
SCRIPT = PLUGIN_ROOT / "scripts" / "collect_sources.py"


def load_module():
    scripts_path = str(SCRIPT.parent)
    if scripts_path not in sys.path:
        sys.path.insert(0, scripts_path)
    spec = importlib.util.spec_from_file_location("backfill_collect_sources", SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def run_git(root: Path, *args: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        env=env,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return completed.stdout.strip()


def commit_all(root: Path, message: str, timestamp: str) -> str:
    env = os.environ.copy()
    env["GIT_AUTHOR_DATE"] = timestamp
    env["GIT_COMMITTER_DATE"] = timestamp
    run_git(root, "add", ".", env=env)
    run_git(root, "commit", "-m", message, env=env)
    return run_git(root, "rev-parse", "HEAD")


class CollectorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project.mkdir()
        run_git(self.project, "init")
        run_git(self.project, "config", "user.email", "test@example.com")
        run_git(self.project, "config", "user.name", "Test User")
        run_git(
            self.project,
            "remote",
            "add",
            "origin",
            "https://github.com/example/project.git",
        )

        self.config = Path(self.temp.name) / "repository-config.json"
        self.config.write_text(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "repository": "example/project",
                    "canonicalDocs": [
                        {
                            "path": "README.md",
                            "role": "project-knowledge",
                            "owner": "test-owner",
                        }
                    ],
                    "pendingPath": "docs/module-knowledge/_pending.md",
                    "compactionPath": "docs/module-knowledge/_compaction",
                    "statePath": "docs/module-knowledge/_compaction/state.json",
                    "implementationsPath": "docs/implementations",
                    "excludePaths": [],
                    "dangerRules": [],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (self.project / "README.md").write_text("baseline\n", encoding="utf-8")
        self.watermark = commit_all(
            self.project, "baseline", "2026-07-01T00:00:00+00:00"
        )

        self.package_names = ["alpha", "bravo", "charlie", "delta", "echo", "foxtrot"]
        for index, package in enumerate(self.package_names, start=1):
            package_root = self.project / "docs" / "implementations" / package
            package_root.mkdir(parents=True)
            (package_root / "spec.md").write_text(f"# {package}\n", encoding="utf-8")
            if package in {"bravo", "echo"}:
                (package_root / "design.md").write_text("# design\n", encoding="utf-8")
            (package_root / "plan.md").write_text("# process only\n", encoding="utf-8")
            if package in {"charlie", "echo"}:
                (package_root / "findings.md").write_text(
                    "# supplemental\n", encoding="utf-8"
                )
            commit_all(
                self.project,
                f"add {package}",
                f"2026-07-0{index + 1}T00:00:00+00:00",
            )
        self.source_head = run_git(self.project, "rev-parse", "HEAD")
        self.module = load_module()

    def collect(self, **overrides):
        arguments = {
            "mode": "steady-state",
            "project_root": self.project,
            "config_path": self.config,
            "source_head": self.source_head,
            "project_watermark": self.watermark,
            "fixture_count": 0,
            "carry_forward": (),
        }
        arguments.update(overrides)
        return self.module.collect_inventory(**arguments)

    def test_collects_deterministic_fixture_and_source_inventory(self) -> None:
        first = self.collect(mode="bootstrap", fixture_count=2)
        second = self.collect(mode="bootstrap", fixture_count=2)

        self.assertEqual(first, second)
        self.assertEqual(first["method_activation"], {"plugin": "stable-docs-backfill", "version": "0.1.0"})
        self.assertEqual(first["package_count"], 6)
        self.assertEqual(first["protected_fixtures"], ["foxtrot", "echo"])
        self.assertEqual(len(first["bootstrap_targets"]), 4)

        echo = next(row for row in first["packages"] if row["package_id"] == "echo")
        self.assertEqual(
            echo["semantic_sources"],
            [
                "docs/implementations/echo/design.md",
                "docs/implementations/echo/spec.md",
            ],
        )
        self.assertEqual(
            echo["supplemental_findings"],
            ["docs/implementations/echo/findings.md"],
        )
        self.assertEqual(
            echo["supplemental_evidence"],
            [
                {
                    "path": "docs/implementations/echo/findings.md",
                    "blob": run_git(
                        self.project,
                        "rev-parse",
                        f"{self.source_head}:docs/implementations/echo/findings.md",
                    ),
                }
            ],
        )
        self.assertNotIn("docs/implementations/echo/plan.md", echo["semantic_sources"])

    def test_carry_forward_is_unioned_with_watermark_new_packages(self) -> None:
        inventory = self.collect(
            project_watermark=self.source_head,
            carry_forward=("echo", "foxtrot"),
        )

        self.assertEqual(inventory["watermark_new_packages"], [])
        self.assertEqual(inventory["eligible_packages"], ["echo", "foxtrot"])
        self.assertEqual(inventory["carry_forward"], ["echo", "foxtrot"])
        self.assertEqual(inventory["bootstrap_targets"], [])

    def test_rejects_non_ancestor_watermark(self) -> None:
        run_git(self.project, "checkout", "--orphan", "unrelated")
        run_git(self.project, "rm", "-rf", ".")
        (self.project / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
        unrelated = commit_all(
            self.project, "unrelated", "2026-07-10T00:00:00+00:00"
        )

        with self.assertRaisesRegex(self.module.CollectorError, "not an ancestor"):
            self.collect(source_head=unrelated)

    def test_rejects_missing_or_machine_local_project_repository_identity(self) -> None:
        run_git(self.project, "remote", "remove", "origin")
        with self.assertRaisesRegex(self.module.CollectorError, "project origin"):
            self.collect()

        run_git(self.project, "remote", "add", "origin", "C:/local/project")
        with self.assertRaisesRegex(self.module.CollectorError, "project origin"):
            self.collect()

    def test_rejects_configured_repository_mismatch(self) -> None:
        payload = json.loads(self.config.read_text(encoding="utf-8"))
        payload["repository"] = "other/project"
        self.config.write_text(json.dumps(payload), encoding="utf-8")

        with self.assertRaisesRegex(self.module.CollectorError, "configured repository mismatch"):
            self.collect()

    def test_reports_package_deleted_after_watermark(self) -> None:
        gone = self.project / "docs" / "implementations" / "gone"
        gone.mkdir(parents=True)
        (gone / "spec.md").write_text("# gone\n", encoding="utf-8")
        deletion_watermark = commit_all(
            self.project, "add gone", "2026-07-10T00:00:00+00:00"
        )
        (gone / "spec.md").unlink()
        gone.rmdir()
        deletion_head = commit_all(
            self.project, "remove gone", "2026-07-11T00:00:00+00:00"
        )

        inventory = self.collect(
            source_head=deletion_head,
            project_watermark=deletion_watermark,
        )

        self.assertEqual(inventory["removed_packages"], ["gone"])
        self.assertEqual(inventory["eligible_removed_packages"], ["gone"])

    def test_cli_defaults_to_read_only_json_stdout(self) -> None:
        before = sorted(path.relative_to(self.project) for path in self.project.rglob("*"))
        command = [
            sys.executable,
            str(SCRIPT),
            "--project-root",
            str(self.project),
            "--config",
            str(self.config),
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
            "--mode",
            "bootstrap",
            "--fixture-count",
            "2",
        ]
        completed = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        payload = json.loads(completed.stdout.decode("utf-8"))
        repeated = subprocess.run(
            command,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        after = sorted(path.relative_to(self.project) for path in self.project.rglob("*"))
        self.assertEqual(payload["protected_fixtures"], ["foxtrot", "echo"])
        self.assertEqual(completed.stdout, repeated.stdout)
        self.assertEqual(before, after)
        self.assertEqual(completed.stderr, b"")

        markdown = subprocess.run(
            [*command, "--format", "markdown"],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout.decode("utf-8")
        self.assertIn("docs/implementations/echo/findings.md", markdown)

    def test_cli_rejects_invalid_config_without_writes(self) -> None:
        output = self.project / "inventory.json"
        invalid_config = Path(self.temp.name) / "invalid.json"
        invalid_config.write_text('{"schemaVersion": 2}', encoding="utf-8")
        command = [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "steady-state",
            "--project-root",
            str(self.project),
            "--config",
            str(invalid_config),
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
            "--output",
            str(output),
        ]
        completed = subprocess.run(
            command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("schemaVersion", completed.stderr)
        self.assertFalse(output.exists())

    def test_cli_rejects_missing_project_and_escaping_output(self) -> None:
        missing = Path(self.temp.name) / "missing-project"
        outside = Path(self.temp.name) / "outside.json"
        common = [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "steady-state",
            "--config",
            str(self.config),
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
        ]

        missing_result = subprocess.run(
            [*common, "--project-root", str(missing)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        escape_result = subprocess.run(
            [
                *common,
                "--project-root",
                str(self.project),
                "--output",
                str(outside),
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        self.assertEqual(missing_result.returncode, 2)
        self.assertIn("not a directory", missing_result.stderr)
        self.assertEqual(escape_result.returncode, 2)
        self.assertIn("output path", escape_result.stderr)
        self.assertFalse(outside.exists())


if __name__ == "__main__":
    unittest.main()
