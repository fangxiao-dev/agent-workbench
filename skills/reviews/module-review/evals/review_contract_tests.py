from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL = EVALS_DIR.parent / "SKILL.md"
EVALS = EVALS_DIR / "evals.json"


def require_text(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected module-review contract text: {needle}")


def main() -> None:
    if not SKILL.exists():
        raise AssertionError(
            "Expected skills/reviews/module-review/SKILL.md to exist."
        )

    body = SKILL.read_text(encoding="utf-8")
    for needle in (
        "Standards",
        "Spec",
        "两个 general-purpose subagent",
        "codebase-design",
        "deep module",
        "interface",
        "seam",
        "contract fidelity",
        "状态机",
        "module boundary",
        "fixed point",
    ):
        require_text(body, needle)

    if "third reviewer" in body or "第三 reviewer" in body:
        raise AssertionError("module-review must not introduce a third drift reviewer.")
    if not EVALS.exists():
        raise AssertionError(
            "Expected module-review evals.json to cover fixed-point and dual-axis review."
        )

    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "module-review" or len(parsed.get("evals", [])) < 4:
        raise AssertionError(
            "module-review evals must identify the skill and cover trigger, "
            "fixed-point, and dual-axis behavior."
        )

    print("module-review generic contract checks passed")


if __name__ == "__main__":
    main()
