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
import contract_preflight  # noqa: E402


class PreflightTests(unittest.TestCase):
    def test_reports_invalid_current_state_as_advisory(self) -> None:
        with tempfile.TemporaryDirectory() as value:
            repo = Path(value)
            subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
            package = repo / "docs/implementations/example"
            (package / ".impl-package").mkdir(parents=True)
            (package / ".impl-package/state.json").write_text("{}", encoding="utf-8")
            config = {"implementations": ["docs/implementations"], "ignore": []}
            result = contract_preflight.run_preflight(repo, config)
            self.assertEqual(result["status"], "advisory")
            self.assertEqual(result["invalidPackageCount"], 1)


if __name__ == "__main__":
    unittest.main()
