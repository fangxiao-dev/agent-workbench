from __future__ import annotations

import importlib.util
import io
import os
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock


DO_REVIEW_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = DO_REVIEW_DIR / "scripts" / "review_ledger.py"

# Fixed create arguments reused across cases; --timestamp keeps the filename deterministic.
CREATE_ARGS = [
    "create",
    "--slug",
    "My Review",
    "--base-sha",
    "0000000base",
    "--head-sha",
    "ABCDEF1234",
    "--mode",
    "single",
    "--round-cap",
    "2",
    "--timestamp",
    "2601010900",
]
EXPECTED_NAME = "2601010900-my-review-abcdef1.md"


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
        # Resolve up front so comparisons stay stable where the temp dir sits behind a
        # symlink (e.g. macOS /var -> /private/var); ledger_directory() also resolves.
        temp_root = str(Path(self._tmp.name).resolve())
        env = mock.patch.dict(os.environ, {"TEMP": temp_root, "TMP": temp_root})
        env.start()
        self.addCleanup(env.stop)
        self.ledger_dir = Path(temp_root) / "do-review"

    def run_cli(self, argv: list[str], stdin: str = "") -> tuple[int, str]:
        out = io.StringIO()
        with mock.patch.object(self.module.sys, "stdin", io.StringIO(stdin)), redirect_stdout(out):
            code = self.module.main(argv)
        return code, out.getvalue()

    def test_create_writes_named_skeleton(self) -> None:
        code, out = self.run_cli(CREATE_ARGS)
        self.assertEqual(code, 0)
        path = self.ledger_dir / EXPECTED_NAME
        self.assertTrue(path.exists())
        self.assertEqual(out.strip(), str(path))
        content = path.read_text(encoding="utf-8")
        self.assertIn("Resolved base SHA: `0000000base`", content)
        self.assertIn("Resolved head SHA: `ABCDEF1234`", content)
        self.assertIn("Mode: `single`", content)
        self.assertIn("Round cap: `2`", content)
        self.assertIn("Status: `in-progress`", content)
        self.assertIn("## Review rounds", content)
        self.assertIn("## Known findings ledger", content)

    def test_create_is_fail_closed_on_duplicate(self) -> None:
        self.assertEqual(self.run_cli(CREATE_ARGS)[0], 0)
        before = (self.ledger_dir / EXPECTED_NAME).read_text(encoding="utf-8")
        # A second create with the same identity must refuse rather than overwrite.
        code, _ = self.run_cli(CREATE_ARGS)
        self.assertEqual(code, 2)
        self.assertEqual((self.ledger_dir / EXPECTED_NAME).read_text(encoding="utf-8"), before)

    def test_create_rejects_non_hex_head_sha(self) -> None:
        bad = list(CREATE_ARGS)
        bad[bad.index("--head-sha") + 1] = "zzzzzzz"
        code, _ = self.run_cli(bad)
        self.assertEqual(code, 2)
        self.assertFalse(self.ledger_dir.exists() and any(self.ledger_dir.iterdir()))

    def test_write_atomically_replaces_and_refuses_empty(self) -> None:
        self.assertEqual(self.run_cli(CREATE_ARGS)[0], 0)
        path = self.ledger_dir / EXPECTED_NAME
        code, _ = self.run_cli(["write", "--ledger", str(path)], stdin="# updated ledger\n")
        self.assertEqual(code, 0)
        self.assertEqual(path.read_text(encoding="utf-8"), "# updated ledger\n")
        self.assertFalse(path.with_suffix(path.suffix + ".tmp").exists())
        # An empty payload must not clobber the existing ledger.
        code, _ = self.run_cli(["write", "--ledger", str(path)], stdin="   \n")
        self.assertEqual(code, 2)
        self.assertEqual(path.read_text(encoding="utf-8"), "# updated ledger\n")

    def test_write_rejects_path_outside_sandbox(self) -> None:
        outside = Path(self._tmp.name) / EXPECTED_NAME  # correct name, wrong directory
        code, _ = self.run_cli(["write", "--ledger", str(outside)], stdin="# nope\n")
        self.assertEqual(code, 2)
        self.assertFalse(outside.exists())

    def test_show_reads_back_content(self) -> None:
        self.assertEqual(self.run_cli(CREATE_ARGS)[0], 0)
        path = self.ledger_dir / EXPECTED_NAME
        code, out = self.run_cli(["show", "--ledger", str(path)])
        self.assertEqual(code, 0)
        self.assertEqual(out, path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
