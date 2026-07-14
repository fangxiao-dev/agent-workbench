from __future__ import annotations

import json
from pathlib import Path


EVALS_DIR = Path(__file__).resolve().parent
SKILL_DIR = EVALS_DIR.parent
IMPL_ROOT = SKILL_DIR.parent
REPO_ROOT = IMPL_ROOT.parents[1]


def require_text(text: str, needle: str, owner: str) -> None:
    if needle not in text:
        raise AssertionError(f"Expected {owner} contract text: {needle}")


def main() -> None:
    skill = SKILL_DIR / "SKILL.md"
    router = IMPL_ROOT / "SKILL.md"
    executor = IMPL_ROOT / "dev-with-track" / "SKILL.md"
    contract = IMPL_ROOT / "references" / "impl-package-composition-contract.md"
    old_skill = (
        REPO_ROOT
        / "skills"
        / "superpowers"
        / "verification-before-completion"
        / "SKILL.md"
    )

    for path in (skill, router, executor, contract):
        if not path.exists():
            raise AssertionError(f"Expected Impl-Package verification contract file: {path}")
    if old_skill.exists():
        raise AssertionError(
            "verification-before-completion must live under skills/impl-package, "
            "not skills/superpowers."
        )

    skill_body = skill.read_text(encoding="utf-8")
    for needle in (
        "Impl-Package",
        "不是 DAG task",
        "terminal `pass`",
        "implemented, not verified",
        "merge-ready",
        "release-ready",
    ):
        require_text(skill_body, needle, "skill")

    require_text(
        router.read_text(encoding="utf-8"),
        "verification-before-completion",
        "router",
    )

    executor_body = executor.read_text(encoding="utf-8")
    for needle in (
        "## Completion claim gate",
        "terminal `pass`",
        "不机械重跑全部检查",
        "目标分支",
    ):
        require_text(executor_body, needle, "dev-with-track")

    contract_body = contract.read_text(encoding="utf-8")
    for needle in ("completion claim", "不进入 DAG", "terminal pass entry 写入前"):
        require_text(contract_body, needle, "composition contract")

    evals = json.loads((EVALS_DIR / "evals.json").read_text(encoding="utf-8"))
    if evals.get("skill_name") != "verification-before-completion" or len(
        evals.get("evals", [])
    ) < 3:
        raise AssertionError(
            "Expected verification-before-completion evals to cover pass, stale "
            "evidence and post-merge claims."
        )

    print("verification-before-completion Impl-Package contract checks passed")


if __name__ == "__main__":
    main()
