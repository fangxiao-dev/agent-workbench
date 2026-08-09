from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL = EVALS_DIR.parent / "SKILL.md"
EVALS = EVALS_DIR / "evals.json"


def require_text(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected safety-review contract text: {needle}")


def main() -> None:
    if not SKILL.exists():
        raise AssertionError(
            "Expected plugin skills/safety-review/SKILL.md to exist."
        )

    body = SKILL.read_text(encoding="utf-8")
    for needle in (
        "Data integrity",
        "Security boundary",
        "Concurrency",
        "External side effects",
        "Change map",
        "auth",
        "payment",
        "webhook",
        "migration",
        "external mutation",
        "idempotency",
        "compensation",
        "permission",
        "rollback",
        "comparison ref",
        "git rev-parse",
        "base-sha",
        "head-sha",
    ):
        require_text(body, needle)

    if not EVALS.exists():
        raise AssertionError("Expected safety-review evals.json to exist.")

    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "safety-review" or len(parsed.get("evals", [])) < 7:
        raise AssertionError(
            "Safety-review evals must identify the skill and cover all five review domains."
        )

    print("safety-review generic contract checks passed")


if __name__ == "__main__":
    main()
