#!/usr/bin/env python3
"""Recognize the current readable Gate without maintaining a second gate contract."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Any


TERMINAL_GATE_VERDICTS = {"pass", "fail", "defer"}


def resolve_gate(package: Path) -> dict[str, Any]:
    path = package / "gate.md"
    if not path.is_file():
        return {"recognition": "none", "verdict": None, "comparisonCommit": None, "reason": "gate.md is absent"}
    text = path.read_text(encoding="utf-8-sig")
    verdict = re.search(r"(?m)^- Verdict:\s*(pass|fail|blocked|defer)\s*$", text)
    attempt = re.search(r"(?m)^- Attempt:\s*([^\s]+)\s*$", text)
    commit = re.search(r"(?m)^- Comparison commit:\s*([0-9a-fA-F]{7,64})\s*$", text)
    if not verdict or not attempt or not commit:
        return {"recognition": "invalid", "verdict": None, "comparisonCommit": None, "reason": "Gate fields are incomplete"}
    state_path = package / ".impl-package/state.json"
    if state_path.is_file():
        try:
            current_attempt = json.loads(state_path.read_text(encoding="utf-8-sig"))["attempt"]["id"]
        except (OSError, json.JSONDecodeError, KeyError, TypeError):
            return {"recognition": "invalid", "verdict": None, "comparisonCommit": commit.group(1), "reason": "Current state Attempt is unavailable"}
        if current_attempt != attempt.group(1):
            return {"recognition": "none", "verdict": None, "comparisonCommit": None, "reason": "Gate belongs to a previous Attempt"}
    repo = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=package, capture_output=True, text=True, check=False)
    check = subprocess.run(["git", "rev-parse", "--verify", f"{commit.group(1)}^{{commit}}"], cwd=package, capture_output=True, text=True, check=False)
    if repo.returncode or check.returncode:
        return {"recognition": "invalid", "verdict": None, "comparisonCommit": commit.group(1), "reason": "Comparison commit is not available"}
    return {"recognition": "current", "verdict": verdict.group(1), "comparisonCommit": check.stdout.strip(), "reason": None}
