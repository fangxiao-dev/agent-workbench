from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = ROOT / "skills" / "impl-package" / "backfill-stable-docs" / "scripts"


def load_module(name: str):
    if str(SCRIPT_DIR) not in sys.path:
        sys.path.insert(0, str(SCRIPT_DIR))
    spec = importlib.util.spec_from_file_location(name, SCRIPT_DIR / f"{name}.py")
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {name}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ContractPreflightTest(unittest.TestCase):
    def test_canonical_current_status_is_forwarded(self) -> None:
        preflight = load_module("contract_preflight")
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            state = Path(temp) / "state.py"
            state.write_text(
                "import json\n"
                "print(json.dumps({'status': 'current', 'contractVersion': '3.2', 'currentContractVersion': '3.2'}))\n",
                encoding="utf-8",
            )
            result = preflight.inspect_package(package, state_engine=state)
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["contractVersion"], "3.2")

    def test_upgrade_required_is_not_treated_as_current(self) -> None:
        preflight = load_module("contract_preflight")
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            state = Path(temp) / "state.py"
            state.write_text(
                "import json,sys\n"
                "print(json.dumps({'status': 'upgradeRequired', 'contractVersion': '3.1', 'currentContractVersion': '3.2'}))\n"
                "sys.exit(2)\n",
                encoding="utf-8",
            )
            result = preflight.inspect_package(package, state_engine=state)
        self.assertEqual(result["status"], "upgradeRequired")

    def test_malformed_canonical_output_fails_closed(self) -> None:
        preflight = load_module("contract_preflight")
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            state = Path(temp) / "state.py"
            state.write_text("print('not-json')\n", encoding="utf-8")
            result = preflight.inspect_package(package, state_engine=state)
        self.assertEqual(result["status"], "invalid")

    def test_require_current_blocks_upgrade_before_read_only_work(self) -> None:
        preflight = load_module("contract_preflight")
        config = {
            "implementations": ["docs/implementations"],
            "ignore": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            package = project / "docs/implementations/pkg"
            package.mkdir(parents=True)
            stale = {
                "package": str(package),
                "status": "upgradeRequired",
                "contractVersion": "3.0",
                "currentContractVersion": "3.2",
            }
            with mock.patch.object(preflight, "inspect_package", return_value=stale):
                with self.assertRaises(preflight.ContractPreflightError):
                    preflight.require_current(project, config)


if __name__ == "__main__":
    unittest.main()
