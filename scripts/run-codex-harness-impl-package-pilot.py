#!/usr/bin/env python3
"""Validate the live parent result against the current Impl-Package contract."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--write-back", action="store_true", help="Append adapter evidence to plan.md and gate.md.")
    args = parser.parse_args()
    root = args.repository_root.resolve()
    package = root / "docs" / "implementations" / "260716-codex-harness-pilots"
    summary = json.loads(args.summary.read_text(encoding="utf-8"))
    parent = summary.get("parent_result") or {}
    parent_text = " ".join(
        [str(parent.get("summary", "")), *(str(item) for item in parent.get("findings", [])), *(str(item.get("claim", "")) for item in parent.get("verification", []) if isinstance(item, dict))]
    ).lower()
    checks = {
        "package_documents_present": all((package / name).is_file() for name in ("decision.md", "spec.md", "plan.md", "gate.md")),
        "ten_spec_acs": len(re.findall(r"\| AC-\d+ \|", (package / "spec.md").read_text(encoding="utf-8"))) == 10,
        "binding_sidecar_present": (package / ".impl-package" / "revision-bindings.json").is_file(),
        "parent_result_valid": summary.get("status") == "passed" and summary.get("parent_result_valid") is True and parent.get("status") == "succeeded",
        "parent_only_finding": "parent-only" in parent_text and "child" in parent_text and "accept" in parent_text,
        "gate_chain_current": "current-G6 · passed" in (package / "gate.md").read_text(encoding="utf-8") and "### ER-6" in (package / "plan.md").read_text(encoding="utf-8"),
        "worktree_unchanged": summary.get("worktree_changed") is False,
    }
    passed = all(checks.values())
    write_back = {"requested": args.write_back, "applied": False, "plan_anchor": "ER-4", "gate_anchor": "current-G4"}
    if args.write_back and passed:
        plan_path = package / "plan.md"
        gate_path = package / "gate.md"
        plan_text = plan_path.read_text(encoding="utf-8")
        gate_text = gate_path.read_text(encoding="utf-8")
        if "### ER-4" not in plan_text:
            plan_text += f"\n### ER-4\n\n- 记录时间：2026-07-16T22:45:00Z\n- Design / Spec / Plan 修订：D1 / S1 / P1\n- 检查或命令：`python scripts/run-codex-harness-impl-package-pilot.py --summary .codex/harness-runs/{summary['run_id']}.app-server.summary.json --write-back`。\n- 结果：Impl-Package adapter 已消费真实 Parent Result，核对 package documents、10 个 AC、binding sidecar、parent-only finding、当前 gate chain 与 worktree 状态，并将本次 adapter evidence 写回 plan/gate。\n- 证据路径：`.codex/harness-runs/{summary['run_id']}.impl-package-adapter.json`、`.codex/harness-runs/{summary['run_id']}.app-server.summary.json`。\n- 剩余风险 / 后续动作：adapter write-back 已闭合，但 AC-7 runtime profile projection 缺少 provider-observable model/effort，继续保持 fail-closed。\n"
            plan_path.write_text(plan_text, encoding="utf-8")
        if "## current-G4" not in gate_text:
            gate_text += "\n## current-G4 · blocked\n\n- Attempt ID：initial\n- Supersedes：current-G3\n- Evaluated at：2026-07-16T22:45:00Z\n- Revision set：D1 / S1 / P1\n- Binding validation：passed\n- Evidence：plan.md#er-4 与本 adapter summary。\n- Verdict reason：Impl-Package adapter 原生 ER/gate write-back 已通过；整体仍因 AC-7 provider-observable model/effort projection 缺失而 fail closed。\n"
            gate_path.write_text(gate_text, encoding="utf-8")
        write_back["applied"] = True
    output_dir = root / ".codex" / "harness-runs"
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / f"{summary['run_id']}.impl-package-adapter.json"
    evidence = {"run_id": summary["run_id"], "status": "passed" if passed else "failed", "package": str(package), "checks": checks, "parent_thread_id": summary.get("root_thread_id"), "parent_result": parent, "write_back": write_back}
    output.write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
