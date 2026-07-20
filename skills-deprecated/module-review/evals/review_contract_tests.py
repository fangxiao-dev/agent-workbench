from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
SKILL = ROOT / "skills-deprecated" / "module-review" / "SKILL.md"
RUBRIC = SKILL.parent / "rubric.md"
EVALS = SKILL.parent / "evals" / "evals.json"


def main() -> None:
    for path in (SKILL, RUBRIC, EVALS):
        if not path.exists():
            raise AssertionError(f"Expected deprecated module-review artifact: {path}")
    body = SKILL.read_text(encoding="utf-8")
    if "name: module-review" not in body or "deprecated: true" not in body:
        raise AssertionError("module-review archive must be explicitly deprecated")
    for needle in ("Standards", "Spec", "fixed point", "codebase-design", "contract fidelity"):
        if needle not in body:
            raise AssertionError(f"Expected archived module-review behavior: {needle}")
    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "module-review" or parsed.get("deprecated") is not True or len(parsed.get("evals", [])) < 4:
        raise AssertionError("Deprecated module-review evals are incomplete")
    registry = json.loads((ROOT / "skills" / "do-review" / "references" / "reviewer-registry.json").read_text(encoding="utf-8"))
    if "module-review" in registry.get("reviewers", {}):
        raise AssertionError("Deprecated module-review must not be active in do-review registry")
    print("deprecated module-review archive contract checks passed")


if __name__ == "__main__":
    main()
