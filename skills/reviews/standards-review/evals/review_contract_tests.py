from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL = EVALS_DIR.parent / "SKILL.md"
RUBRIC = EVALS_DIR.parent / "rubric.md"
EVALS = EVALS_DIR / "evals.json"


def require_text(text: str, needle: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected standards-review contract text: {needle}")


def main() -> None:
    for path in (SKILL, RUBRIC, EVALS):
        if not path.exists():
            raise AssertionError(f"Expected standards-review artifact to exist: {path}")

    body = SKILL.read_text(encoding="utf-8")
    for needle in (
        "name: standards-review",
        "leaf reviewer",
        "完整 diff",
        "comparison point",
        "不调用 `do-review`",
        "不调度 subagent",
        "不重新计算 reviewer topology 或容量",
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
        "spec-review",
    ):
        require_text(body, needle)

    for forbidden in (
        "并行运行两个 Reviewer",
        "两个 general-purpose subagent",
        "第三个 drift reviewer",
        "定位 Spec 来源",
        "固定比较点",
    ):
        if forbidden in body:
            raise AssertionError(f"standards-review must not retain orchestrator workflow: {forbidden}")

    parsed = json.loads(EVALS.read_text(encoding="utf-8"))
    if parsed.get("skill_name") != "standards-review" or len(parsed.get("evals", [])) < 3:
        raise AssertionError("standards-review evals must identify the skill and cover leaf and Standards behavior.")

    print("standards-review generic contract checks passed")


if __name__ == "__main__":
    main()
