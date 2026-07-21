#!/usr/bin/env python3
"""Create two reproducible unfinished plan-review runs for eval 8."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile


SKILL_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = SKILL_ROOT / "scripts" / "review_ledger.py"
SPEC = importlib.util.spec_from_file_location("review_ledger", MODULE_PATH)
assert SPEC and SPEC.loader
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)

runtime = Path(tempfile.mkdtemp(prefix="plan-review-eval-"))
target = runtime / "plan.md"
target.write_text("# Fixture plan\n\nImplement one deterministic parser branch.\n", encoding="utf-8")
temp_root = runtime / "ledger-root"
runs = [ledger.init_ledger([target], temp_root=temp_root) for _ in range(2)]
print(
    json.dumps(
        {
            "target": str(target),
            "temp_root": str(temp_root),
            "ledgers": [str(item) for item in runs],
        },
        indent=2,
    )
)
