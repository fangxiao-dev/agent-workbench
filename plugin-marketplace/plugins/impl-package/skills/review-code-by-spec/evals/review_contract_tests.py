from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL = EVALS_DIR.parent / "SKILL.md"
RUBRIC = EVALS_DIR.parent / "rubric.md"
EVALS = EVALS_DIR / "evals.json"


def require_text(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected review-code-by-spec contract text: {needle}")


def main() -> None:
    for path in (SKILL, RUBRIC, EVALS):
        if not path.exists():
            raise AssertionError(f"Expected review-code-by-spec artifact to exist: {path}")

    body = SKILL.read_text(encoding="utf-8")
    for needle in (
        "name: review-code-by-spec",
        "完整 diff",
        "comparison point",
        "调用者必须提供",
        "issue、Decision、Spec、Plan、DAG",
        "缺失或部分实现的需求",
        "scope creep",
        "兼容窗口",
        "状态机",
        "跨 slice seam",
        "跨模块 seam",
        "contract evidence",
        "400 words",
    ):
        require_text(body, needle)

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
        "review-code-by-standards",
        "safety-review",
        "ledger",
        "reviewer topology",
        "subagent",
    ):
        if forbidden in body:
            raise AssertionError(f"review-code-by-spec must not retain orchestrator workflow: {forbidden}")

    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "review-code-by-spec" or len(parsed.get("evals", [])) < 3:
        raise AssertionError("review-code-by-spec evals must identify the skill and cover Spec behavior.")

    print("review-code-by-spec generic contract checks passed")


if __name__ == "__main__":
    main()
