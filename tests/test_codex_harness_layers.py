from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.codex_harness_cli import app_server_command, find_codex_command
from scripts.codex_harness_controller import parse_parent_result


ROOT = Path(__file__).resolve().parents[1]


class CodexCliLayerTest(unittest.TestCase):
    def test_executable_override_is_resolved_without_host_lookup(self) -> None:
        with patch.dict(os.environ, {"CODEX_EXECUTABLE": "C:/tools/codex.cmd"}, clear=False):
            self.assertEqual(find_codex_command(), ["C:/tools/codex.cmd"])

    def test_default_app_server_command_keeps_poc_safety_defaults(self) -> None:
        with patch.dict(os.environ, {"CODEX_EXECUTABLE": "C:/tools/codex.cmd"}, clear=False):
            command = app_server_command()
        self.assertEqual(command[:2], ["C:/tools/codex.cmd", "app-server"])
        self.assertIn("multi_agent", command)
        self.assertIn('approval_policy="never"', command)
        self.assertIn("mcp_servers={}", command)

    def test_discovery_skips_windowsapps_resource_for_user_desktop_cli(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            stale_cli = Path(directory) / "OpenAI" / "Codex" / "bin" / "codex.exe"
            desktop_cli = stale_cli.parent / "current" / "codex.exe"
            stale_cli.parent.mkdir(parents=True)
            stale_cli.touch()
            desktop_cli.parent.mkdir()
            desktop_cli.touch()
            os.utime(stale_cli, (1, 1))
            os.utime(desktop_cli, (2, 2))
            with patch.dict(os.environ, {"LOCALAPPDATA": directory}, clear=False), patch(
                "scripts.codex_harness_cli.shutil.which",
                return_value="C:/Program Files/WindowsApps/codex.exe",
            ):
                self.assertEqual(find_codex_command(), [str(desktop_cli)])

    def test_command_construction_can_be_used_without_harness_policy(self) -> None:
        with patch.dict(os.environ, {"CODEX_EXECUTABLE": "codex"}, clear=False):
            command = app_server_command(enable_multi_agent=False, disabled_mcp_servers=(), disable_vercel_plugin=False, approval_policy="on-request")
        self.assertEqual(command, ["codex", "app-server", "-c", 'approval_policy="on-request"'])


class ControllerLayerTest(unittest.TestCase):
    def test_parent_result_requires_structured_verification_claim(self) -> None:
        raw = '{"schema_version":"codex-harness.parent-result.v0","run_id":"run-1","stage":"stage","status":"succeeded","summary":"ok","artifacts":[],"verification":[{"command":"check","exit_code":0,"claim":"passed"}],"findings":[],"owner_decisions":[],"retry_hint":"none","boundary_violations":[]}'
        self.assertIsNotNone(parse_parent_result(raw, "run-1"))
        self.assertIsNone(parse_parent_result(raw.replace(',"claim":"passed"', ""), "run-1"))

    def test_package_adapter_no_longer_loads_the_scenario_pilot(self) -> None:
        source = (ROOT / "scripts" / "codex_harness_package.py").read_text(encoding="utf-8")
        self.assertNotIn("importlib.util", source)
        self.assertNotIn("run-codex-app-server-pilot.py", source)


if __name__ == "__main__":
    unittest.main()
