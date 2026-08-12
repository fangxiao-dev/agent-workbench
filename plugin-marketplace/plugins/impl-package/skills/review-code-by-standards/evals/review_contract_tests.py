from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL = EVALS_DIR.parent / "SKILL.md"
RUBRIC = EVALS_DIR.parent / "rubric.md"
EVALS = EVALS_DIR / "evals.json"
REFERENCE = EVALS_DIR.parent / "references" / "strict-maintainability.md"


def require_text(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected review-code-by-standards contract text: {needle}")


def main() -> None:
    for path in (SKILL, RUBRIC, EVALS, REFERENCE):
        if not path.exists():
            raise AssertionError(f"Expected review-code-by-standards artifact to exist: {path}")

    body = SKILL.read_text(encoding="utf-8")
    for needle in (
        "name: review-code-by-standards",
        "完整 diff",
        "comparison point",
        "调用者必须提供",
        "Fowler code-smell baseline",
        "仓库规范优先",
        "Mysterious Name",
        "Refused Bequest",
        "codebase-design",
        "depth / leverage",
        "locality",
        "adapter",
        "hard violation",
        "judgement call",
        "400 words",
        "审查深度选择",
        "非穷尽启发式",
        "strict-maintainability.md",
        "证据指引",
        "首要深挖方向",
    ):
        require_text(body, needle)

    reference = REFERENCE.read_text(encoding="utf-8")
    for needle in (
        "Core Prompt",
        "Original positioning",
        "Non-Negotiable Additional Standards",
        "Primary Review Questions",
        "What to Flag Aggressively",
        "Preferred Remedies",
        "Review Tone",
        "Output Expectations",
        "Approval Bar",
        "sequential orchestration",
        "non-atomic updates",
    ):
        require_text(reference, needle)

    for forbidden in (
        "并行运行两个 Reviewer",
        "两个 general-purpose subagent",
        "第三个 drift reviewer",
        "定位 Spec 来源",
        "固定比较点",
        "do-review",
        "Track A",
        "Track B",
        "Track C",
        "review-code-by-spec",
        "safety-review",
        "ledger",
        "reviewer topology",
        "subagent",
    ):
        if forbidden in body:
            raise AssertionError(f"review-code-by-standards must not retain orchestrator workflow: {forbidden}")

    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "review-code-by-standards" or len(parsed.get("evals", [])) < 5:
        raise AssertionError("review-code-by-standards evals must identify the skill and cover Standards and depth behavior.")

    print("review-code-by-standards generic contract checks passed")


if __name__ == "__main__":
    main()
