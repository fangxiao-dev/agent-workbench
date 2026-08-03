from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SCRIPT = Path(__file__).with_name("impl_package_apply.py")
SPEC = importlib.util.spec_from_file_location("impl_package_apply_under_test", SCRIPT)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError(f"cannot load {SCRIPT}")
APPLY = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(APPLY)


class BuildContextTests(unittest.TestCase):
    def test_reuses_existing_binding_evidence_for_same_immutable_binding(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            package = Path(temp_dir)
            (package / "decision.md").write_text("# Decision\n", encoding="utf-8")
            (package / "spec.md").write_text("# Spec\n", encoding="utf-8")
            (package / "plan.md").write_text("# Plan\n", encoding="utf-8")
            state = {
                "current": {
                    "decision": {"artifact": "decision.md", "revision": "D7"},
                    "spec": {"artifact": "spec.md", "revision": "S8"},
                },
                "bindings": [
                    {
                        "artifact": "decision.md",
                        "revision": "D7",
                        "mode": "exact-blob",
                        "blob": "decision-blob",
                        "supersedes": None,
                        "evidence": "decision.md",
                        "id": "D7@decision-blob",
                    },
                    {
                        "artifact": "spec.md",
                        "revision": "S8",
                        "mode": "exact-blob",
                        "blob": "spec-blob",
                        "supersedes": "S8@prior-spec-blob",
                        "evidence": "machine:refresh-projections",
                        "id": "S8@spec-blob",
                    },
                ],
            }

            def registration_binding(_package, _state, kind, alias, artifact, attempt, evidence):
                blob = {"decision": "decision-blob", "spec": "spec-blob", "plan": "plan-blob"}[kind]
                binding = {
                    "artifact": artifact,
                    "revision": alias,
                    "mode": "plan-contract-v1" if kind == "plan" else "exact-blob",
                    "blob": blob,
                    "supersedes": None,
                    "evidence": evidence,
                    "id": f"{attempt + ':' if attempt else ''}{alias}@{blob}",
                }
                if attempt:
                    binding["attempt"] = attempt
                return binding, {}

            captured = {}

            def build_candidate(_package, registrations):
                captured["registrations"] = registrations
                return None, None, {"current": {"attempt": {"id": "initial", "plan": "plan.md"}}}, {}

            with (
                patch.object(APPLY.STATE, "_load_revision_state", return_value=(Path("state.json"), state)),
                patch.object(APPLY.STATE, "_registration_binding", side_effect=registration_binding),
                patch.object(APPLY.STATE, "_build_registration_candidate", side_effect=build_candidate),
                patch.object(APPLY.STATE, "_package_artifact", side_effect=lambda root, name: root / name),
                patch.object(APPLY.STATE, "_composition", return_value=(True, False)),
                patch.object(APPLY, "_validate_tickets", return_value=(["T-1", "T-2"], {}, {})),
                patch.object(APPLY, "_validate_dag"),
            ):
                APPLY._build_context(
                    package,
                    {"decision": "D7", "spec": "S8", "plan": "P1"},
                    {"decision": "decision.md", "spec": "spec.md", "plan": "plan.md"},
                    "initial",
                )

            registrations = {row["kind"]: row for row in captured["registrations"]}
            self.assertNotIn("decision", registrations)
            self.assertNotIn("spec", registrations)
            self.assertEqual("impl-package-apply:publish-plan/P1", registrations["plan"]["evidence"])

    def test_keeps_registration_when_binding_identity_differs(self) -> None:
        registration = {
            "kind": "decision",
            "alias": "D7",
            "artifact": "spec.md",
            "attempt": None,
            "evidence": "impl-package-apply:publish-plan/D7",
        }
        state = {
            "bindings": [
                {
                    "artifact": "decision.md",
                    "revision": "D7",
                    "mode": "exact-blob",
                    "blob": "same-blob",
                    "supersedes": None,
                    "evidence": "decision.md",
                    "id": "D7@same-blob",
                }
            ]
        }
        conflicting = {
            "artifact": "spec.md",
            "revision": "D7",
            "mode": "exact-blob",
            "blob": "same-blob",
            "supersedes": None,
            "evidence": registration["evidence"],
            "id": "D7@same-blob",
        }
        with patch.object(APPLY.STATE, "_registration_binding", return_value=(conflicting, {})):
            actual = APPLY._registration_is_needed(Path("package"), state, registration)

        self.assertTrue(actual)


if __name__ == "__main__":
    unittest.main()
