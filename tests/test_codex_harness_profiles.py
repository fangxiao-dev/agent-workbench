from __future__ import annotations

import unittest
from pathlib import Path

from scripts.codex_harness_controller import load_parent_profile
from scripts.codex_harness_policy import load_orchestrator_policy
from scripts.codex_harness_profiles import ExecutionProfileError, load_execution_profiles, resolve_execution_profile, select_available_verifier_profile, select_available_worker_profile, verifier_profile_candidates_for_mode, worker_profile_candidates_for_mode, worker_profile_for_mode


ROOT = Path(__file__).resolve().parents[1]


class CodexHarnessExecutionProfilesTest(unittest.TestCase):
    def test_canonical_profiles_bind_parent_and_worker_roles(self) -> None:
        bundle = load_execution_profiles(ROOT)
        self.assertEqual(resolve_execution_profile(bundle, "parent-sol-high", "parent")["model"], "gpt-5.6-sol")
        self.assertEqual(resolve_execution_profile(bundle, "parent-terra-xhigh", "parent")["reasoning_effort"], "xhigh")
        self.assertEqual(worker_profile_for_mode(bundle, "full"), {"id": "worker-full-terra-high", "role": "worker", "model": "gpt-5.6-terra", "reasoning_effort": "high"})
        self.assertEqual(worker_profile_for_mode(bundle, "lite")["model"], "gpt-5.6-luna")
        self.assertEqual(worker_profile_for_mode(bundle, "lite")["reasoning_effort"], "max")
        self.assertEqual([profile["id"] for profile in worker_profile_candidates_for_mode(bundle, "lite")], ["worker-lite-luna-max", "worker-lite-terra-high"])
        self.assertEqual([profile["id"] for profile in verifier_profile_candidates_for_mode(bundle, "full")], ["verifier-sol-high"])

    def test_parent_toml_resolves_model_through_canonical_profile(self) -> None:
        profile = load_parent_profile(ROOT / ".codex" / "harness" / "crew-parent.toml")
        self.assertEqual(profile["execution_profile"], "parent-sol-high")
        self.assertEqual(profile["model"], "gpt-5.6-sol")
        self.assertEqual(profile["model_reasoning_effort"], "high")
        self.assertEqual(profile["execution_profile_identity"]["schema_version"], "codex-harness.execution-profiles.v0.2")

    def test_full_verifier_requires_the_canonical_sol_profile(self) -> None:
        bundle = load_execution_profiles(ROOT)
        selection = select_available_verifier_profile(
            bundle,
            "full",
            {"data": [{"id": "gpt-5.6-sol", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}]},
            observed_at=123.0,
        )
        self.assertEqual(selection["selected_profile"]["id"], "verifier-sol-high")
        with self.assertRaises(ExecutionProfileError):
            select_available_verifier_profile(bundle, "full", {"data": [{"id": "gpt-5.6-terra", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}]})

    def test_lite_profile_prefers_luna_when_catalog_supports_it(self) -> None:
        bundle = load_execution_profiles(ROOT)
        selection = select_available_worker_profile(
            bundle,
            "lite",
            {"data": [{"id": "gpt-5.6-luna", "supportedReasoningEfforts": [{"reasoningEffort": "max"}]}]},
            observed_at=123.0,
        )
        self.assertEqual(selection["selected_profile"]["id"], "worker-lite-luna-max")
        self.assertEqual(selection["reason"], "first_available_candidate")
        self.assertEqual(selection["observed_at"], 123.0)

    def test_lite_profile_falls_back_to_terra_only_from_catalog_evidence(self) -> None:
        bundle = load_execution_profiles(ROOT)
        selection = select_available_worker_profile(
            bundle,
            "lite",
            {"data": [{"model": "gpt-5.6-terra", "supportedReasoningEfforts": [{"reasoningEffort": "high"}]}]},
            observed_at=123.0,
        )
        self.assertEqual(selection["selected_profile"]["id"], "worker-lite-terra-high")
        self.assertEqual(selection["reason"], "fallback_after_unavailable_prior_candidates")

    def test_profile_selection_rejects_invalid_catalog_or_missing_candidates(self) -> None:
        bundle = load_execution_profiles(ROOT)
        with self.assertRaises(ExecutionProfileError):
            select_available_worker_profile(bundle, "lite", {"unexpected": []})
        with self.assertRaises(ExecutionProfileError):
            select_available_worker_profile(bundle, "lite", {"data": []})

    def test_thin_orchestrator_policy_is_versioned_and_validated_separately(self) -> None:
        bundle = load_orchestrator_policy(ROOT)
        self.assertEqual(bundle["identity"]["schema_version"], "codex-harness.runtime-policy.v1.3")
        self.assertEqual(bundle["policy"]["crew_control"]["capability_invocation"], "orchestrator_explicit_only")
        self.assertEqual(bundle["policy"]["crew_control"]["max_active_workers"], 4)
        self.assertNotIn("max_actions", bundle["policy"]["actions"])


if __name__ == "__main__":
    unittest.main()
