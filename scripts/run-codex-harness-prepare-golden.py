#!/usr/bin/env python3
"""Golden fixture: derive the DATEV adapter from its approved package snapshot."""

from __future__ import annotations

import sys
from pathlib import Path

from codex_harness_package import load_manifest
from codex_harness_prepare import prepare_adapter


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
DATEV_REPOSITORY = Path("D:/CodeSpace/kaispan-dev")
DATEV_REF = "3cc2a9350d5820c236a352b7e1a756f13a837e27"
DATEV_PACKAGE = "docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules"


def main() -> int:
    manifest_text, readiness = prepare_adapter(DATEV_REPOSITORY, DATEV_REF, DATEV_PACKAGE, str(WORKBENCH_ROOT / ".codex" / "harness" / "parent.toml"))
    assert readiness["revisions"] == {"design": "D5", "spec": "S7", "plan": "P6"}, readiness
    assert readiness["stage_count"] == 9, readiness
    assert readiness["initial_ready_stages"] == ["T1", "T2"], readiness
    assert readiness["sensitive_on_demand"] == ["T7"], readiness
    assert readiness["manual_acceptance"] == ["T9"], readiness
    # The selected assertions cover the ambiguous source wording that must not
    # silently turn a generated draft into an incorrect execution boundary.
    import tempfile

    with tempfile.TemporaryDirectory() as temporary:
        manifest_path = Path(temporary) / "datev.generated.toml"
        manifest_path.write_text(manifest_text, encoding="utf-8")
        stages = {stage.id: stage for stage in load_manifest(manifest_path).stages}
    assert stages["T1"].parent_role == "impl_package_t1_parent"
    assert stages["T5"].cohort == "C3"
    assert stages["T6"].cohort == "C3"
    assert stages["T7"].cohort == "C3"
    assert stages["T8"].ticket == "integration-gate"
    print("DATEV prepare golden: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
