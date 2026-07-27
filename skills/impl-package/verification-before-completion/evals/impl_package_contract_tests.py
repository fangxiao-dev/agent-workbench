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
    runtime_protocol = IMPL_ROOT / "dev-with-track" / "references" / "runtime-protocol.md"
    contract = IMPL_ROOT / "references" / "impl-package-composition-contract.md"
    progressive_evidence = IMPL_ROOT / "references" / "progressive-system-evidence.md"
    old_skill = (
        REPO_ROOT
        / "skills"
        / "superpowers"
        / "verification-before-completion"
        / "SKILL.md"
    )

    for path in (skill, router, executor, runtime_protocol, contract, progressive_evidence):
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
        "关键因果输入",
        "真实 browser/provider/native-tool/E2E evidence",
        "历史 failure",
    ):
        require_text(skill_body, needle, "skill")

    require_text(
        router.read_text(encoding="utf-8"),
        "verification-before-completion",
        "router",
    )

    executor_body = executor.read_text(encoding="utf-8")
    runtime_body = runtime_protocol.read_text(encoding="utf-8")
    for needle in (
        "references/runtime-protocol.md",
        "GO 后自动完成",
    ):
        require_text(executor_body, needle, "dev-with-track")
    for needle in (
        "## Claim and gate",
        "terminal `pass`",
        "只补受影响检查",
        "目标分支",
        "关键因果输入",
    ):
        require_text(runtime_body, needle, "runtime protocol")
    for needle in (
        "不要创建 freshness registry",
        "真实 E2E",
        "不追溯清偿",
    ):
        require_text(progressive_evidence.read_text(encoding="utf-8"), needle, "progressive evidence")

    contract_body = contract.read_text(encoding="utf-8")
    for needle in ("completion claim", "不进入 DAG", "terminal pass entry 写入前"):
        require_text(contract_body, needle, "composition contract")

    evals = json.loads((EVALS_DIR / "evals.json").read_text(encoding="utf-8"))
    if evals.get("skill_name") != "verification-before-completion" or len(
        evals.get("evals", [])
    ) < 7:
        raise AssertionError(
            "Expected verification-before-completion evals to cover pass, stale "
            "evidence, post-merge claims, causal freshness, real E2E residue and "
            "claim-scoped failure learning."
        )
    by_id = {item["id"]: item for item in evals["evals"]}
    for eval_id in (4, 5, 6, 7):
        if eval_id not in by_id:
            raise AssertionError(f"Missing progressive-evidence completion eval {eval_id}")

    print("verification-before-completion Impl-Package contract checks passed")


if __name__ == "__main__":
    main()
