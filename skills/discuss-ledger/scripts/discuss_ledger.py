#!/usr/bin/env python3
"""Compatibility CLI for the discuss-ledger deterministic writer."""
from __future__ import annotations

import sys
from pathlib import Path


SKILL_DIR = Path(__file__).resolve().parents[1]
SRC = SKILL_DIR / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from discuss_ledger_core.ledger import main


if __name__ == "__main__":
    main()
