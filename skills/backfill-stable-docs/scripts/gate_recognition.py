#!/usr/bin/env python3
"""Read-only adapter to the canonical Impl-Package gate resolver.

Backfill intentionally owns no copy of gate grammar, binding validation, or
current-attempt resolution. Those mechanics and their versioned data policy
live in the Impl-Package skill; this adapter keeps the backfill interface small.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any


IMPL_STATE_PATH = Path(__file__).resolve().parents[2] / "impl-package" / "scripts" / "impl_package_state.py"


def _load_canonical_module() -> Any:
    spec = importlib.util.spec_from_file_location("impl_package_state_for_backfill", IMPL_STATE_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load canonical Impl-Package state engine: {IMPL_STATE_PATH}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise RuntimeError(f"cannot initialize canonical Impl-Package state engine: {exc}") from exc
    return module


_CANONICAL = _load_canonical_module()
TERMINAL_GATE_VERDICTS = _CANONICAL.TERMINAL_GATE_VERDICTS


def resolve_gate(package: Path) -> dict[str, Any]:
    return _CANONICAL.resolve_gate(package)
