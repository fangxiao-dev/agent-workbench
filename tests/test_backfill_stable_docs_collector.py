from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = (
    Path(__file__).resolve().parents[1]
    / "skills"
    / "backfill-stable-docs"
    / "scripts"
    / "collect_sources.py"
)


def load_module():
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
        self.method = Path(self.temp.name) / "method"
        self.project.mkdir()
        self.method.mkdir()

        for root in (self.project, self.method):
            run_git(root, "init")
            run_git(root, "config", "user.email", "test@example.com")
            run_git(root, "config", "user.name", "Test User")

        run_git(
            self.method,
            "remote",
            "add",
            "origin",
            "https://github.com/example/agent-workbench.git",
        )
        (self.method / "SKILL.md").write_text("method\n", encoding="utf-8")
        self.method_commit = commit_all(
            self.method, "method", "2026-07-01T00:00:00+00:00"
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

    def test_collects_deterministic_fixture_and_source_inventory(self) -> None:
        module = load_module()

        first = module.collect_inventory(
            mode="bootstrap",
            project_root=self.project,
            source_head=self.source_head,
            project_watermark=self.watermark,
            method_root=self.method,
            method_ref=f"example/agent-workbench@{self.method_commit}",
            fixture_count=2,
            carry_forward=(),
        )
        second = module.collect_inventory(
            mode="bootstrap",
            project_root=self.project,
            source_head=self.source_head,
            project_watermark=self.watermark,
            method_root=self.method,
            method_ref=f"example/agent-workbench@{self.method_commit}",
            fixture_count=2,
            carry_forward=(),
        )

        self.assertEqual(first, second)
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
        module = load_module()

        inventory = module.collect_inventory(
            mode="steady-state",
            project_root=self.project,
            source_head=self.source_head,
            project_watermark=self.source_head,
            method_root=self.method,
            method_ref=f"example/agent-workbench@{self.method_commit}",
            fixture_count=0,
            carry_forward=("echo", "foxtrot"),
        )

        self.assertEqual(inventory["watermark_new_packages"], [])
        self.assertEqual(inventory["eligible_packages"], ["echo", "foxtrot"])
        self.assertEqual(inventory["carry_forward"], ["echo", "foxtrot"])
        self.assertEqual(inventory["bootstrap_targets"], [])

    def test_rejects_non_ancestor_watermark(self) -> None:
        module = load_module()
        run_git(self.project, "checkout", "--orphan", "unrelated")
        run_git(self.project, "rm", "-rf", ".")
        (self.project / "unrelated.txt").write_text("unrelated\n", encoding="utf-8")
        unrelated = commit_all(
            self.project, "unrelated", "2026-07-10T00:00:00+00:00"
        )

        with self.assertRaisesRegex(module.CollectorError, "not an ancestor"):
            module.collect_inventory(
                mode="steady-state",
                project_root=self.project,
                source_head=unrelated,
                project_watermark=self.watermark,
                method_root=self.method,
                method_ref=f"example/agent-workbench@{self.method_commit}",
                fixture_count=0,
                carry_forward=(),
            )

    def test_rejects_method_repository_identity_mismatch(self) -> None:
        module = load_module()

        with self.assertRaisesRegex(module.CollectorError, "repository identity"):
            module.collect_inventory(
                mode="steady-state",
                project_root=self.project,
                source_head=self.source_head,
                project_watermark=self.watermark,
                method_root=self.method,
                method_ref=f"other/workbench@{self.method_commit}",
                fixture_count=0,
                carry_forward=(),
            )

    def test_rejects_method_ref_that_does_not_match_method_root_head(self) -> None:
        module = load_module()
        (self.method / "REFERENCE.md").write_text("new method\n", encoding="utf-8")
        commit_all(self.method, "advance method", "2026-07-11T00:00:00+00:00")

        with self.assertRaisesRegex(module.CollectorError, "method root HEAD"):
            module.collect_inventory(
                mode="steady-state",
                project_root=self.project,
                source_head=self.source_head,
                project_watermark=self.watermark,
                method_root=self.method,
                method_ref=f"example/agent-workbench@{self.method_commit}",
                fixture_count=0,
                carry_forward=(),
            )

    def test_rejects_machine_local_method_repository_identity(self) -> None:
        module = load_module()

        with self.assertRaisesRegex(module.CollectorError, "portable owner/repository"):
            module.collect_inventory(
                mode="steady-state",
                project_root=self.project,
                source_head=self.source_head,
                project_watermark=self.watermark,
                method_root=self.method,
                method_ref=f"C:/local/agent-workbench@{self.method_commit}",
                fixture_count=0,
                carry_forward=(),
            )

    def test_reports_package_deleted_after_watermark(self) -> None:
        module = load_module()
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

        inventory = module.collect_inventory(
            mode="steady-state",
            project_root=self.project,
            source_head=deletion_head,
            project_watermark=deletion_watermark,
            method_root=self.method,
            method_ref=f"example/agent-workbench@{self.method_commit}",
            fixture_count=0,
            carry_forward=(),
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
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
            "--method-root",
            str(self.method),
            "--method-ref",
            f"example/agent-workbench@{self.method_commit}",
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
        echo_blob = run_git(
            self.project,
            "rev-parse",
            f"{self.source_head}:docs/implementations/echo/findings.md",
        )
        self.assertIn(
            f"docs/implementations/echo/findings.md @ {echo_blob}", markdown
        )

    def test_cli_rejects_unresolved_method_ref_without_writes(self) -> None:
        output = self.project / "inventory.json"
        command = [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "steady-state",
            "--project-root",
            str(self.project),
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
            "--method-root",
            str(self.method),
            "--method-ref",
            "example/agent-workbench@deadbeef",
            "--output",
            str(output),
        ]
        completed = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        self.assertEqual(completed.returncode, 2)
        self.assertIn("does not resolve", completed.stderr)
        self.assertFalse(output.exists())

    def test_cli_rejects_missing_project_and_escaping_output(self) -> None:
        missing = Path(self.temp.name) / "missing-project"
        outside = Path(self.temp.name) / "outside.json"
        common = [
            sys.executable,
            str(SCRIPT),
            "--mode",
            "steady-state",
            "--source-head",
            self.source_head,
            "--project-watermark",
            self.watermark,
            "--method-root",
            str(self.method),
            "--method-ref",
            f"example/agent-workbench@{self.method_commit}",
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
