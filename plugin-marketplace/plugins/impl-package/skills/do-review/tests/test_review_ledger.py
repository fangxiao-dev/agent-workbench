from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


DO_REVIEW_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = DO_REVIEW_DIR / "scripts" / "review_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("review_ledger", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ReviewLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module()
        self._tmp = TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        root = Path(self._tmp.name).resolve()
        self.repo = root / "repo"
        self.repo.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "review@example.test")
        self.git("config", "user.name", "Review Test")
        (self.repo / "contract.md").write_text("contract v1\n", encoding="utf-8")
        (self.repo / "code.txt").write_text("before\n", encoding="utf-8")
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").stdout.strip()
        (self.repo / "code.txt").write_text("after\n", encoding="utf-8")
        self.git("commit", "-qam", "head")
        self.head = self.git("rev-parse", "HEAD").stdout.strip()

        temp_root = root / "temp"
        temp_root.mkdir()
        env = mock.patch.dict(os.environ, {"TEMP": str(temp_root), "TMP": str(temp_root)})
        env.start()
        self.addCleanup(env.stop)
        self.ledger_dir = temp_root / "do-review"

    def git(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(self.repo), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
        )

    def create_args(self, *extra: str, base: str | None = None, head: str | None = None) -> list[str]:
        return [
            "create",
            "--repo-root",
            str(self.repo),
            "--base",
            base or self.base,
            "--head",
            head or self.head,
            *extra,
            "--slug",
            "My Review",
            "--mode",
            "single",
            "--round-cap",
            "2",
            "--timestamp",
            "2601010900",
        ]

    def run_cli(self, argv: list[str], stdin: str = "") -> tuple[int, str, str]:
        out = io.StringIO()
        err = io.StringIO()
        with (
            mock.patch.object(self.module.sys, "stdin", io.StringIO(stdin)),
            redirect_stdout(out),
            redirect_stderr(err),
        ):
            code = self.module.main(argv)
        return code, out.getvalue(), err.getvalue()

    def assert_no_ledger(self) -> None:
        self.assertFalse(self.ledger_dir.exists() and any(self.ledger_dir.iterdir()))

    def test_create_atomically_records_resolved_run_and_head_blob(self) -> None:
        (self.repo / "contract.md").write_text("uncommitted mutation\n", encoding="utf-8")
        code, out, err = self.run_cli(self.create_args("--source", "contract.md"))
        self.assertEqual(code, 0, err)
        payload = json.loads(out)
        path = Path(payload["ledger_path"])
        self.assertEqual(path.name, f"2601010900-my-review-{self.head[:7]}.md")
        self.assertTrue(path.exists())
        self.assertEqual(payload["resolved_base_sha"], self.base)
        self.assertEqual(payload["resolved_head_sha"], self.head)
        self.assertEqual(payload["diff_range"], f"{self.base}...{self.head}")
        self.assertEqual(
            payload["contract_sources"],
            [
                {
                    "path": "contract.md",
                    "git_object_id": self.git("rev-parse", f"{self.head}:contract.md").stdout.strip(),
                    "sha256": hashlib.sha256(b"contract v1\n").hexdigest(),
                }
            ],
        )
        content = path.read_text(encoding="utf-8")
        self.assertIn(f"Resolved base SHA: `{self.base}`", content)
        self.assertIn(f"Resolved head SHA: `{self.head}`", content)
        self.assertIn(f"Diff range: `{self.base}...{self.head}`", content)
        self.assertIn('"git_object_id":', content)
        self.assertIn("Review phase: `pending`", content)
        self.assertIn("Safety applicability / evidence / coverage: `pending`", content)

    def test_create_accepts_absolute_source_inside_repo(self) -> None:
        code, out, err = self.run_cli(self.create_args("--source", str(self.repo / "contract.md")))
        self.assertEqual(code, 0, err)
        self.assertEqual(json.loads(out)["contract_sources"][0]["path"], "contract.md")

    def test_create_is_fail_closed_on_duplicate(self) -> None:
        code, out, err = self.run_cli(self.create_args())
        self.assertEqual(code, 0, err)
        path = Path(json.loads(out)["ledger_path"])
        before = path.read_text(encoding="utf-8")
        code, out, err = self.run_cli(self.create_args())
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("refusing to overwrite", err)
        self.assertEqual(path.read_text(encoding="utf-8"), before)

    def test_create_rejects_empty_three_dot_diff_without_ledger(self) -> None:
        code, out, err = self.run_cli(self.create_args(base=self.base, head=self.base))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("empty diff", err)
        self.assert_no_ledger()

    def test_create_rejects_bad_ref_without_ledger(self) -> None:
        code, out, err = self.run_cli(self.create_args(base="missing-review-base"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("Needed a single revision", err)
        self.assert_no_ledger()

    def test_create_rejects_source_missing_from_resolved_head_without_ledger(self) -> None:
        (self.repo / "untracked.md").write_text("working tree only\n", encoding="utf-8")
        code, out, err = self.run_cli(self.create_args("--source", "untracked.md"))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("not a Git blob in resolved head", err)
        self.assert_no_ledger()

    def test_create_rejects_non_utf8_head_blob_without_ledger(self) -> None:
        (self.repo / "binary.dat").write_bytes(b"\xff\xfe")
        self.git("add", "binary.dat")
        self.git("commit", "-qm", "binary source")
        head = self.git("rev-parse", "HEAD").stdout.strip()
        code, out, err = self.run_cli(self.create_args("--source", "binary.dat", head=head))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("not valid UTF-8", err)
        self.assert_no_ledger()

    def test_create_rejects_source_outside_repository_without_ledger(self) -> None:
        outside = self.repo.parent / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        code, out, err = self.run_cli(self.create_args("--source", str(outside)))
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("escapes repository", err)
        self.assert_no_ledger()

    def test_write_atomically_replaces_and_refuses_empty(self) -> None:
        code, out, err = self.run_cli(self.create_args())
        self.assertEqual(code, 0, err)
        path = Path(json.loads(out)["ledger_path"])
        code, _, _ = self.run_cli(["write", "--ledger", str(path)], stdin="# updated ledger\n")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "# updated ledger\n")
        self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())
        code, _, _ = self.run_cli(["write", "--ledger", str(path)], stdin="   \n")
        self.assertEqual(code, 2)
        self.assertEqual(path.read_text(encoding="utf-8"), "# updated ledger\n")

    def test_write_rejects_path_outside_sandbox(self) -> None:
        outside = self.repo.parent / f"2601010900-my-review-{self.head[:7]}.md"
        code, _, _ = self.run_cli(["write", "--ledger", str(outside)], stdin="# nope\n")
        self.assertEqual(code, 2)
        self.assertFalse(outside.exists())

    def test_show_reads_back_content(self) -> None:
        code, out, err = self.run_cli(self.create_args())
        self.assertEqual(code, 0, err)
        path = Path(json.loads(out)["ledger_path"])
        code, out, err = self.run_cli(["show", "--ledger", str(path)])
        self.assertEqual(code, 0, err)
        self.assertEqual(out, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
