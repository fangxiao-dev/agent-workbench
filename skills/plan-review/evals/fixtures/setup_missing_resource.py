#!/usr/bin/env python3
"""Copy the real skill and remove one mandatory reference for eval 10."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile


skill_root = Path(__file__).resolve().parents[2]
runtime = Path(tempfile.mkdtemp(prefix="plan-review-missing-resource-eval-"))
snapshot = runtime / "plan-review"
shutil.copytree(skill_root, snapshot)
missing = snapshot / "references" / "code-quality-review.md"
missing.unlink()
print(json.dumps({"skill": str(snapshot / "SKILL.md"), "missing": str(missing)}, indent=2))
