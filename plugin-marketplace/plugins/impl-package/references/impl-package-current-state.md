# Impl-Package Current State 3.5

3.5 是 Ticket-first 的唯一运行格式。新 runtime 不双读 3.4；3.4/Task package 只能先按 [迁移 Runbook](ticket-first-migration-runbook.md) 生成并验证 candidate。Git commit ID 是历史锚点。

`scripts/validate_ticket_first_migration.py` 是一次性、只读、显式调用的迁移脚本，不是 3.5 runtime、`package validate` 或普通 preflight 的后备入口。它位于 plugin 的 `scripts/` 而非 `skills/`，不得被 host skill link 或普通 runtime 调用。

## 文件与事实源

```text
<package>/
├─ progress.md
├─ execution/<attempt>/execution-record.md
├─ .impl-package/state.json
├─ gate.md
└─ migration/archive/task-handoffs/   # 迁移后旧 handoff 归档
```

`state.json` 是 package 唯一可写 current-state。主 session 是唯一 writer；worker 只返回结构化证据。`progress.md` 和 Execution Record header 是 machine-owned projection；Ticket 是发布后稳定的 Approved 合同，运行时验收状态不回写 Ticket。ER 只保存 judgment/history，不产生 active checkpoint。

路径口径固定：`attempt.plan`、evidence 与 checkpoint evidence 是 repository-relative；`attemptHistory.executionRecord` 是 package-relative 的 `execution/<attempt>/execution-record.md`。

## State schema

```json
{
  "formatVersion": "3.5",
  "attempt": {"id": "initial", "plan": "docs/implementations/topic/plan.md"},
  "attemptHistory": [{
    "id": "initial", "plan": "docs/implementations/topic/plan.md",
    "lifecycle": "active", "gate": null,
    "executionRecord": "execution/initial/execution-record.md"
  }],
  "tickets": {"TKT-01": {"state": "PENDING"}},
  "evidenceIndex": {"TKT-01": {"AC-1": [{
    "timing": "early-falsification",
    "artifact": "evidence/test.md#anchor",
    "revision": "<git commit>",
    "environment": "<explicit environment>",
    "conclusion": "supporting",
    "invalidatedBy": null
  }]}},
  "activeCheckpoints": {"attempt": {
    "next": "<one next action>", "blocker": null,
    "evidence": ["evidence/context.md#anchor"]
  }}
}
```

新 package 不包含 `tasks`、`resume`、DAG runtime projection 或 Task Handoff。`attemptHistory` 只作轻量导航；evidence/checkpoint 只覆盖 current Attempt。`activeCheckpoints` 覆盖写当前值，是正常跨 session 唯一恢复事实源；compact 仅为意外耗尽兜底。

## Ticket 与 evidence

Ticket 状态为 `PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | RETIRED`。`RETIRED` 在 Ticket record 中携带 `disposition: waived | superseded`、evidence；superseded 还需 successor。

每个 Ticket 的 AC 和安全不变量必须有稳定 claim ID。AC claim 显式标记 evidence timing；安全不变量默认属于 `early-falsification`，不能被推迟到“加固组”。每条 evidence record 必须含 `timing`、`artifact`、`revision`、`environment`、`conclusion`；`invalidatedBy` 可选。`SATISFIED` 必须显式提供当前 revision/environment，并把该 pair 写入 Ticket 的 `acceptance`，覆盖全部 required claims、无未处置 contradictory/inconclusive evidence，且 implementation/acceptance 入边已释放。revision 必须是当前 Git 可解析的 commit；Gate pass 要求 acceptance revision 等于 comparison commit。release 边只在 Gate pass 前复核。`RETIRED/waived` 可释放边；`RETIRED/superseded` 只有 successor 已满足相应释放条件时才释放。

命令入口：新调用按职责选择一个命令组；根 router 只暴露 `package`、`ticket`、`evidence`、`recovery`、`gate` 五组。

```text
python <plugin>/scripts/impl_package_state.py --package <package> package init --attempt <id> --plan <repo-relative-plan>
python <plugin>/scripts/impl_package_state.py --package <package> package validate
python <plugin>/scripts/impl_package_state.py --package <package> package refresh-progress
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> evidence add
python <plugin>/scripts/impl_package_state.py --package <package> evidence invalidate --ticket <id> --claim <id> --artifact <path> --invalidated-by <reason>
python <plugin>/scripts/impl_package_state.py --package <package> ticket satisfy <id> --expect <state> --revision <commit> --environment <id>
python <plugin>/scripts/impl_package_state.py --package <package> ticket block <id> --expect <state> --evidence <path>
python <plugin>/scripts/impl_package_state.py --package <package> ticket needs-revalidation <id> --expect <state> --claim <claim-id> [--claim <claim-id> ...] --invalidated-by <reason> [--evidence <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket pending <id> --expect <state> [--revalidation-plan <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket retire <id> --expect <state> --disposition waived|superseded --evidence <path> [--successor <id>]
python <plugin>/scripts/impl_package_state.py --package <package> recovery checkpoint --subject attempt|ticket:<id> --next <text> [--blocker <text>] [--evidence <path>] [--handoff]
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> recovery judgment
python <plugin>/scripts/impl_package_state.py --package <package> gate <verdict> --comparison-commit <commit> --reason <text>
```

旧平铺拼法 `init`、`validate`、`set-state`、`evidence-add`、`checkpoint`、`er-add` 等保留为兼容别名；新文档和新 package 统一使用分组拼法。`ticket transition` 是旧 `set-state` 的组内兼容入口，优先使用上面的语义命令。

`NEEDS-REVALIDATION`、`BLOCKED` 不释放依赖。ER 中旧 checkpoint 正文可作为历史保留，但 runtime 不从 ER 推导 active checkpoint；迁移后恢复只认 `activeCheckpoints`。
