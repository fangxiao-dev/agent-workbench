# Impl-Package Current State 3.5 / 3.6

3.5 与 3.6 是现役的 Ticket-first 运行格式，按 `state.formatVersion` 分流、互不读取对方字段：3.5 以 stable claim 验收（本文前半），3.6 以 Journey 与套件验收（[3.6 格式](#36-格式)）。新 runtime 不双读 3.4；3.4/Task package 只能先按 [迁移 Runbook](ticket-first-migration-runbook.md) 生成并验证 candidate。Git commit ID 是历史锚点。

`scripts/validate_ticket_first_migration.py` 是一次性、只读、显式调用的迁移脚本，不是 3.5 runtime、`package validate` 或普通 preflight 的后备入口。它位于 plugin 的 `scripts/` 而非 `skills/`，不得被 host skill link 或普通 runtime 调用。

## 文件与事实源

```text
<package>/
├─ progress.md
├─ execution/<attempt>/execution-record.md
├─ .impl-package/state.json
├─ .impl-package/attempts/<attempt>.json
├─ gate.md
└─ migration/archive/task-handoffs/   # 迁移后旧 handoff 归档
```

`state.json` 是 package 唯一可写 current-state。`.impl-package/attempts/` 保存 terminal Attempt 的不可变 Ticket 状态快照，只供历史查看，不参与当前 readiness、Gate 或恢复。主 session 是唯一 writer；worker 只返回结构化证据。`progress.md` 和 Execution Record header 是 machine-owned projection；Ticket 是发布后稳定的 Approved 合同，运行时验收状态不回写 Ticket。ER 只保存 judgment/history，不产生 active checkpoint。

路径口径固定：`attempt.plan`、`predecessors`、evidence 与 checkpoint evidence 是 repository-relative；`attemptHistory.executionRecord` 是 package-relative 的 `execution/<attempt>/execution-record.md`。

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
  "predecessors": null,
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

terminal Gate 自动写入 `.impl-package/attempts/<attempt>.json`；下一 Attempt 初始化前也会为旧 runtime 补写当前已冻结 Attempt。历史缺档时，只能用明确 Git revision 执行 `package archive-attempt`，不得从 Execution Record 文本猜测 Ticket 状态；已有不同快照时命令失败，不覆盖。

## Ticket 与 evidence

Ticket 状态为 `PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | RETIRED`。`RETIRED` 在 Ticket record 中携带 `disposition: waived | superseded`、evidence；superseded 还需 successor。

每个 Ticket 的 AC 和安全不变量必须有稳定 claim ID。AC claim 显式标记 evidence timing；安全不变量默认属于 `early-falsification`，不能被推迟到“加固组”。每条 evidence record 必须含 `timing`、`artifact`、`revision`、`environment`、`conclusion`；`invalidatedBy` 可选。`SATISFIED` 必须显式提供当前 revision/environment，并把该 pair 写入 Ticket 的 `acceptance`，覆盖全部 required claims、无未处置 contradictory/inconclusive evidence，且 implementation/acceptance 入边已释放。revision 必须是当前 Git 可解析的 commit；Gate pass 要求 acceptance revision 等于 comparison commit。release 边只在 Gate pass 前复核。`RETIRED/waived` 可释放边；`RETIRED/superseded` 只有 successor 已满足相应释放条件时才释放。

命令入口：新调用按职责选择一个命令组；根 router 的语义组是 `package`、`ticket`、`evidence`、`recovery`、`gate` 五组，另有低层 `trail` 组（dispatch/return 记账，见 [Situation Inputs](situation-inputs.md)）。

```text
python <plugin>/scripts/impl_package_state.py --package <package> package init --attempt <id> --plan <repo-relative-plan>
python <plugin>/scripts/impl_package_state.py --package <package> package validate
python <plugin>/scripts/impl_package_state.py --package <package> package refresh-progress
python <plugin>/scripts/impl_package_state.py --package <package> package archive-attempt --attempt <id> --from-revision <commit>
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> evidence add
python <plugin>/scripts/impl_package_state.py --package <package> evidence invalidate --ticket <id> --claim <id> --artifact <path> --invalidated-by <reason>
python <plugin>/scripts/impl_package_state.py --package <package> evidence retire-claim --ticket <id> --claim <id>
python <plugin>/scripts/impl_package_state.py --package <package> ticket satisfy <id> --expect <state> --revision <commit> --environment <id>
python <plugin>/scripts/impl_package_state.py --package <package> ticket block <id> --expect <state> --evidence <path>
python <plugin>/scripts/impl_package_state.py --package <package> ticket needs-revalidation <id> --expect <state> --claim <claim-id> [--claim <claim-id> ...] --invalidated-by <reason> [--evidence <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket pending <id> --expect <state> [--revalidation-plan <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket retire <id> --expect <state> --disposition waived|superseded --evidence <path> [--successor <id>]
python <plugin>/scripts/impl_package_state.py --package <package> recovery checkpoint --subject attempt|ticket:<id> --next <text> [--blocker <text>] [--evidence <path>] [--handoff]
python <plugin>/scripts/impl_package_state.py --package <package> recovery lease acquire --owner <worker-id> --key <resource-key> [--key <resource-key> ...]
python <plugin>/scripts/impl_package_state.py --package <package> recovery lease release --lease-id <id> --owner-token <token>
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> recovery judgment
python <plugin>/scripts/impl_package_state.py --package <package> gate <verdict> --comparison-commit <commit> --reason <text>
```

`evidence add` 从 stdin 接受一个 evidence object 或一个非空 evidence object array。单对象输出保持 `{ticket, claim, idempotent}`；数组输出为 `{records: [按输入顺序的单条结果], added, duplicates}`。批量输入会先完成全部记录的规范化与校验，任一元素非法则整批失败且不写入 state；完全重复（含批内重复）只返回幂等结果，不写入 state 或刷新 projection。含新增记录的批量调用只原子保存一次 state、刷新一次 projection，CLI 处境尾注仍按调用追加一次。

`evidence retire-claim` 只清理已从当前 Ticket 删除且所有旧 evidence 都已带 `invalidatedBy` 的孤立 claim mapping；它不删除 evidence artifact，也不创建额外历史副本。

`NEEDS-REVALIDATION`、`BLOCKED` 不释放依赖。ER 中旧 checkpoint 正文可作为历史保留，但 runtime 不从 ER 推导 active checkpoint；迁移后恢复只认 `activeCheckpoints`。

## 3.6 格式

`formatVersion: "3.6"` 由 plan 的 `Acceptance: journey` 选择，验收语义见 [composition contract §7](impl-package-composition-contract.md)。`attempt`、`attemptHistory`、`predecessors`、`tickets`、`activeCheckpoints`、唯一 writer 与 terminal 快照沿用上文；差异只有 `evidenceIndex` 与新增的 `acceptance`，没有 claim 映射。

```json
{
  "formatVersion": "3.6",
  "evidenceIndex": {
    "journey:run-01:J1-S1": [{
      "kind": "journey-step",
      "runId": "run-01", "journeyId": "J1", "stepId": "J1-S1",
      "entry": "<Spec 该步的操作入口原文>",
      "artifact": "evidence/journey/run-01.md#j1-s1",
      "revision": "<git commit>",
      "environment": "<Journey run 使用的 environment 字符串>",
      "conclusion": "supporting",
      "invalidatedBy": null
    }]
  },
  "acceptance": {
    "contractBaseline": {"head": "<init HEAD>", "files": {"spec.md": "<blob hash>"}},
    "releaseOrder": "required",
    "amendments": [{
      "id": "AM-1", "summary": "<一句话>", "affected": ["spec.md"],
      "artifact": "amendments/AM-1.md", "status": "PENDING",
      "confirmedBy": null, "confirmedRevision": null
    }]
  }
}
```

`evidenceIndex` 按 `evidenceKey` 索引，key 由 runtime 从 record 推出（传入的 `evidenceKey` 必须与推导一致）；`timing` 可省略；`artifact` 必须是 package 内路径（`evidence/…`、`execution/<attempt>/reviews/…`）；`conclusion` 取值同 3.5。`amendments[].affected` 是 package 内合同文件路径（如 `spec.md`），不是 Journey step ID；多个路径分别传入多个 `--affected`。`contractBaseline.files` 记录 init 时 `spec.md` 及存在的 `decision.md`、`contract-design.md` 的 Git blob hash，用于发现未被 Amendment 的 `affected` 路径覆盖的合同文件变化；runtime 不判断改动是否用户可见，分类由登记者负责。

| kind | 必填的专有字段 | evidenceKey | 说明 |
| --- | --- | --- | --- |
| `journey-step` | `runId`、`journeyId`、`stepId`、`entry` | `journey:<runId>:<stepId>` | `entry` 必须与 Spec 该步的操作入口一致；同一 run 从第 1 步起按顺序登记；失败不覆盖旧 run，另起新 run |
| `suite` | `suiteId` | `suite:<id>` | environment 必须等于 Spec 声明；归属由 Ticket Coverage 反查 |
| `review` | `ticket`（Ticket ID 或 `package`） | `review:<ticket>` | per-Ticket required review 的结果；最终 HEAD 的 review 仍由 terminal-final 承担 |
| `release` | 无 | `release` | artifact 为 package 内发布顺序表 |

**有效性**：记录的 `conclusion` 为 `supporting` 且未被 `invalidatedBy` 标记；`revision` 等于 Gate comparison commit，或两者之间只改动了本 package 目录内的文件；suite evidence 的 environment 与 Spec 字符串精确匹配，同一 Journey run 的 step evidence 使用同一 environment；active Attempt 的 artifact 文件存在。不满足的记录待复验，旧记录保留。**reach** 由 `journey-step` 记录派生（同一 run 内从第 1 步起连续有效的步数），不存储。

Ticket 的 Coverage 区块、Spec 三张固定表和 `Release order` 在 `package validate` 时按固定标题与列名解析，列缺失或多出即失败。

命令（长参数表以 `--help` 为准）：

```text
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> evidence add      # 单条或数组，整批合法才写入
python <plugin>/scripts/impl_package_state.py --package <package> evidence invalidate --key <evidenceKey> --invalidated-by <reason>
python <plugin>/scripts/impl_package_state.py --package <package> package amendment add --id <id> --summary <text> --affected <contract path> [--affected <contract path> ...] --artifact <package 内路径>
python <plugin>/scripts/impl_package_state.py --package <package> package amendment confirm --id <id> --expect PENDING --confirmed-by <owner> --confirmed-revision <commit>
python <plugin>/scripts/impl_package_state.py --package <package> ticket satisfy <id> --expect <state> --revision <commit> --environment <id>
python <plugin>/scripts/impl_package_state.py --package <package> gate pass --comparison-commit <commit> --reason <text> (--durable-delta <repo-relative path> ... | --no-durable-delta-reason <text>)
python <plugin>/scripts/impl_package_state.py --package <package> gate blocked --comparison-commit <commit> --reason <gap and next action>
```

`ticket satisfy` 要求 `--revision` 是当前 HEAD 的 ancestor，负责套件与 required review 有有效 evidence，且 implementation/acceptance 入边已释放。3.6 CLI 仍要求 `--environment`，但套件环境核对读取 Spec 的 Required Suites.Environment，不读取该参数值。`gate pass` 在 header 后生成 `## Owner Summary`（每条 Journey 的走通进度、套件通过数、待确认或漏登的合同修订、发布顺序状态、最终版本短 SHA、结论），并按 composition contract §7 的两层清单核对；待确认或漏登的 Amendment 只阻止 pass。`gate pass` 还要求 `--durable-delta` 或 `--no-durable-delta-reason`，以及 `--comparison-commit`、`--reason`。`gate blocked` 记录缺口与 next action，Attempt 保持 active。`recovery lease acquire|release` 与 3.5 相同，lease 文件位于 `execution/<attempt>/leases/`。
