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
                "print(json.dumps({'status': 'current', 'contractVersion': '3.3', 'currentContractVersion': '3.3'}))\n",
                encoding="utf-8",
            )
            result = preflight.inspect_package(package, state_engine=state)
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["contractVersion"], "3.3")
        self.assertEqual(result["currentContractVersion"], "3.3")

    def test_upgrade_required_is_not_treated_as_current(self) -> None:
        preflight = load_module("contract_preflight")
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            state = Path(temp) / "state.py"
            state.write_text(
                "import json,sys\n"
                "print(json.dumps({'status': 'upgradeRequired', 'contractVersion': '3.2', 'currentContractVersion': '3.3'}))\n"
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
        self.assertIsNone(result["currentContractVersion"])

    def test_missing_canonical_current_version_is_not_backfilled_from_backfill_contract(self) -> None:
        preflight = load_module("contract_preflight")
        with tempfile.TemporaryDirectory() as temp:
            package = Path(temp) / "package"
            package.mkdir()
            state = Path(temp) / "state.py"
            state.write_text(
                "import json\n"
                "print(json.dumps({'status': 'upgradeRequired', 'contractVersion': '3.2'}))\n",
                encoding="utf-8",
            )
            result = preflight.inspect_package(package, state_engine=state)
        self.assertEqual(preflight.CONTRACT_VERSION, "3.2")
        self.assertIsNone(result["currentContractVersion"])

    def test_run_preflight_reports_upgrade_as_non_blocking_advisory(self) -> None:
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
                "currentContractVersion": "3.3",
            }
            with mock.patch.object(preflight, "inspect_package", return_value=stale):
                result = preflight.run_preflight(project, config)
        self.assertEqual(result["status"], "advisory")
        self.assertEqual(result["advisoryPackageCount"], 1)
        self.assertEqual(result["packages"], [stale])

    def test_backfill_output_contract_stays_3_2_when_package_contract_is_3_3(self) -> None:
        preflight = load_module("contract_preflight")
        stable_docs_config = load_module("stable_docs_config")
        config = {
            "implementations": ["docs/implementations"],
            "ignore": [],
        }
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp)
            package = project / "docs/implementations/pkg"
            package.mkdir(parents=True)
            current = {
                "package": str(package),
                "status": "current",
                "contractVersion": "3.3",
                "currentContractVersion": "3.3",
            }
            with mock.patch.object(preflight, "inspect_package", return_value=current):
                result = preflight.run_preflight(project, config)
        self.assertEqual(result["contractVersion"], "3.2")
        self.assertEqual(stable_docs_config.CONTRACT_VERSION, "3.2")
        self.assertEqual(result["status"], "current")
        self.assertEqual(result["packages"][0]["currentContractVersion"], "3.3")


if __name__ == "__main__":
    unittest.main()
