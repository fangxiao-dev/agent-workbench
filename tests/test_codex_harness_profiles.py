from __future__ import annotations

import unittest
from pathlib import Path

from scripts.codex_harness_controller import load_parent_profile
from scripts.codex_harness_profiles import load_execution_profiles, resolve_execution_profile, worker_profile_for_mode


ROOT = Path(__file__).resolve().parents[1]


class CodexHarnessExecutionProfilesTest(unittest.TestCase):
    def test_canonical_profiles_bind_parent_and_worker_roles(self) -> None:
        bundle = load_execution_profiles(ROOT)
        self.assertEqual(resolve_execution_profile(bundle, "parent-sol-high", "parent")["model"], "gpt-5.6-sol")
        self.assertEqual(resolve_execution_profile(bundle, "parent-terra-xhigh", "parent")["reasoning_effort"], "xhigh")
        self.assertEqual(worker_profile_for_mode(bundle, "full"), {"id": "worker-full-terra-high", "role": "worker", "model": "gpt-5.6-terra", "reasoning_effort": "high"})
        self.assertEqual(worker_profile_for_mode(bundle, "lite")["model"], "luna")
        self.assertEqual(worker_profile_for_mode(bundle, "lite")["reasoning_effort"], "max")

    def test_parent_toml_resolves_model_through_canonical_profile(self) -> None:
        profile = load_parent_profile(ROOT / ".codex" / "harness" / "crew-parent.toml")
        self.assertEqual(profile["execution_profile"], "parent-sol-high")
        self.assertEqual(profile["model"], "gpt-5.6-sol")
        self.assertEqual(profile["model_reasoning_effort"], "high")
        self.assertEqual(profile["execution_profile_identity"]["schema_version"], "codex-harness.execution-profiles.v0")


if __name__ == "__main__":
    unittest.main()
