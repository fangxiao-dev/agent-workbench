#!/usr/bin/env python3
"""Verify that a pinned pre-3.2 DATEV package is rejected before adapter preparation."""

from __future__ import annotations

from pathlib import Path

from codex_harness_prepare import PrepareError, prepare_adapter


WORKBENCH_ROOT = Path(__file__).resolve().parents[1]
DATEV_REPOSITORY = Path("D:/CodeSpace/kaispan-dev")
DATEV_REF = "3cc2a9350d5820c236a352b7e1a756f13a837e27"
DATEV_PACKAGE = "docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules"


def main() -> int:
    try:
        prepare_adapter(
            DATEV_REPOSITORY,
            DATEV_REF,
            DATEV_PACKAGE,
            str(WORKBENCH_ROOT / ".codex" / "harness" / "parent.toml"),
        )
    except PrepareError as error:
        assert "contractVersion must be 3.2" in str(error), error
    else:
        raise AssertionError("pre-3.2 package unexpectedly reached adapter preparation")
    print("DATEV pre-3.2 upgrade fixture: rejected as expected")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
