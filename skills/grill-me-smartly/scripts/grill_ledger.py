#!/usr/bin/env python3
"""Compatibility CLI for the Grill Me Smartly deterministic ledger writer."""
from __future__ import annotations

import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SRC = SKILL_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from grill_ledger_core.ledger import main


if __name__ == "__main__":
    raise SystemExit(main())
