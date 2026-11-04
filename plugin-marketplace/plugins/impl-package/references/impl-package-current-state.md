# Impl-Package Current State (3.6)

现役运行格式是 Ticket-first 的 3.6（`state.formatVersion: "3.6"`），由 plan 的 `Acceptance: journey` 选择，以 Journey 与套件验收（语义见 [composition contract §7](impl-package-composition-contract.md)）。runtime 只支持 3.6：`state.formatVersion` 不是 `"3.6"` 的旧 package，所有命令统一报 `format <v> is no longer supported; start a new package`，不迁移、不双读。Git commit ID 是历史锚点。

## 文件与事实源

```text
<package>/
├─ progress.md
├─ execution/<attempt>/execution-record.md
├─ .impl-package/state.json
├─ .impl-package/attempts/<attempt>.json
└─ gate.md
```

`state.json` 是 package 唯一可写 current-state。`.impl-package/attempts/` 保存 terminal Attempt 的不可变 Ticket 状态快照，只供历史查看，不参与当前 readiness、Gate 或恢复。主 session 是唯一 writer；worker 只返回结构化证据。`progress.md` 和 Execution Record header 是 machine-owned projection；Ticket 是发布后稳定的 Approved 合同，运行时验收状态不回写 Ticket。ER 只保存 judgment/history，不产生 active checkpoint。

路径口径固定：`attempt.plan`、`predecessors`、evidence 与 checkpoint evidence 是 repository-relative；`attemptHistory.executionRecord` 是 package-relative 的 `execution/<attempt>/execution-record.md`。

## State schema

`package check-spec --spec <repo-relative spec.md>` 不需要 state，执行与 `package validate`/`package init` 相同的 §7 解析和章节覆盖检查，有遗漏时非零退出并列出章节；req-align 在 init 前用它做 Spec Gate。

```json
{
  "formatVersion": "3.6",
  "attempt": {"id": "initial", "plan": "docs/implementations/topic/plan.md"},
  "attemptHistory": [{
    "id": "initial", "plan": "docs/implementations/topic/plan.md",
    "lifecycle": "active", "gate": null,
    "executionRecord": "execution/initial/execution-record.md"
  }],
  "predecessors": null,
  "tickets": {"TKT-01": {"state": "PENDING"}},
  "evidenceIndex": {
    "journey:run-01:J1-S1": [{
      "kind": "journey-step",
      "runId": "run-01", "journeyId": "J1", "stepId": "J1-S1",
      "actor": "<Spec 该步的角色>",
      "entry": "<Spec 该步的操作入口原文>",
      "surface": "page",
      "inputRef": "<承接的业务对象 ID，承接为 — 时 null>", "outputRef": "<本步产出的业务对象 ID>",
      "artifact": "evidence/journey/run-01-s1.zip",
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
      "affectedBlobs": {"spec.md": "<registration-time Git blob hash>"},
      "artifact": "amendments/AM-1.md", "status": "PENDING"
    }]
  },
  "activeCheckpoints": {"attempt": {
    "next": "<one next action>", "blocker": null,
    "evidence": ["evidence/context.md#anchor"]
  }}
}
```

`attemptHistory` 只作轻量导航；evidence/checkpoint 只覆盖 current Attempt。`activeCheckpoints` 覆盖写当前值，是正常跨 session 唯一恢复事实源；compact 仅为意外耗尽兜底。

terminal Gate 自动写入 `.impl-package/attempts/<attempt>.json`；下一 Attempt 初始化前也会为旧 runtime 补写当前已冻结 Attempt。历史缺档时，只能用明确 Git revision 执行 `package archive-attempt`，不得从 Execution Record 文本猜测 Ticket 状态；已有不同快照时命令失败，不覆盖。

plan 固定行（`package init/validate` 缺失或无效即拒绝）：`Harness setup: <cmd>`、`Harness precheck: <cmd>`、`Harness cleanup: <cmd>`、`Harness isolation: per-run`、`First visible step: <StepId> @ <TicketId>`。每个 run 的第 1 步 `outputRef` 不得出现在其他 run 中（每个 run 创建新对象）。`attempt.walking_skeleton_overdue`：声明的 Ticket 已 `SATISFIED` 而声明的 step 仍无匹配的 page/file record 时，situation 出一行并在 Owner Summary 提示。方法见 `validation-harness`。

## Ticket 与 evidence

Ticket 状态为 `PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | RETIRED`。`RETIRED` 在 Ticket record 中携带 `disposition: waived | superseded`、evidence；superseded 还需 successor。`NEEDS-REVALIDATION`、`BLOCKED` 不释放依赖。`RETIRED/waived` 可释放边；`RETIRED/superseded` 只有 successor 已满足相应释放条件时才释放。release 边只在 Gate pass 前复核。ER 中旧 checkpoint 正文可作为历史保留，但 runtime 不从 ER 推导 active checkpoint；恢复只认 `activeCheckpoints`。

`evidenceIndex` 按 `evidenceKey` 索引，key 由 runtime 从 record 推出（传入的 `evidenceKey` 必须与推导一致）；`timing` 可省略；`artifact` 必须是 package 内路径（`evidence/…`、`execution/<attempt>/reviews/…`）；`conclusion` 取值为 `supporting | contradictory | inconclusive`。`amendments[].affected` 是 package 内合同文件路径（如 `spec.md`），不是 Journey step ID；多个路径分别传入多个 `--affected`，登记时的 blob 写入 `affectedBlobs`。漏登检测按当前内容匹配：合同文件当前 blob 不同于 `contractBaseline` 时，必须有一条 Amendment 为该路径记录相同 blob；旧 state 中没有 `affectedBlobs` 的 Amendment 不覆盖当前内容。每条 Amendment 都需 Owner 确认后才不再阻止 `gate pass`。

| kind | 必填的专有字段 | evidenceKey | 说明 |
| --- | --- | --- | --- |
| `journey-step` | `runId`、`journeyId`、`stepId`、`entry`、`surface`（`page \| file \| log \| api`） | `journey:<runId>:<stepId>` | `entry` 必须与 Spec 该步的操作入口一致；`page` 默认是 package 内截图加 `manualBy`（走查人：Owner 或执行 agent 的标识），Spec 的 `取证：` 声明 Playwright 的步骤才用 package 内 trace `.zip`（动作含对 Spec 声明控件的 click/press/fill，否则拒绝）；`file` 需用户实际收到的文件（不接受 .md/.txt/.log），runtime 存其 sha256；`log`（对应 Spec 的 `记录` 步）的 artifact 须为 package 内文件；`api` 恒接受；同一 run 从第 1 步起按顺序登记；Spec 该步“承接”不是 `—` 时，`inputRef` 必须等于同一 run 上一步的 `outputRef`，否则 `evidence add` 拒绝；失败不覆盖旧 run，另起新 run |
| `run-setup` | `runId` | `run-setup:<runId>` | artifact 为 plan 的 `Harness setup` 与 `Harness precheck` 输出（package 内文件）；某 runId 的 `journey-step` 必须在该 run 已有有效 `run-setup` 后才被接受 |
| `suite` | `suiteId` | `suite:<id>` | environment 必须等于 Spec 声明；归属由 Ticket Coverage 反查 |
| `review` | `ticket`（Ticket ID 或 `package`） | `review:<ticket>` | per-Ticket required review 的结果；最终 HEAD 的 review 仍由 terminal-final 承担 |
| `release` | 无 | `release` | artifact 为 package 内发布顺序表 |

**有效性**：记录的 `conclusion` 为 `supporting` 且未被 `invalidatedBy` 标记；`revision` 等于 Gate comparison commit，或两者之间只改动了本 package 目录内的文件；suite evidence 的 environment 与 Spec 字符串精确匹配，同一 Journey run 的 step evidence 使用同一 environment；active Attempt 的 artifact 文件存在。不满足的记录待复验，旧记录保留。Gate 只在缺少当前有效替代时保留 stale blocker：非 Journey evidence 需同 key 的当前有效 supporting 记录；Journey 历史 step/setup 需同一 Journey 的完整连续有效 run，步骤不跨 run 拼接。invalidated 或非 supporting 记录不构成替代。terminal Gate 在任何持久化写入前按 comparison commit 的完整冻结合同校验；冻结 Attempt 的 Journey 校验读取该 commit 中的 `spec.md`，并由 `contractBaseline` 或已登记 Amendment 的 blob 证明归属；历史合同缺失或 blob 不匹配时拒绝。活动 Attempt 校验工作区合同。进度由 `journey-step` 记录派生，不存储：**reach** 是同一 run 内从第 1 步起、surface 与 Spec 入口类型一致（页面—page、文件—file、记录—log）的连续有效步数，Gate 只认它；**rehearsalReach** 不限 surface。Owner Summary 形如 `J1 …：页面走通 2/4 · API 预演 4/4`，并列出走查的步骤。

Ticket 的 Coverage 区块、Spec 三张固定表和 `Release order` 在 `package validate` 时按固定标题与列名解析，列缺失或多出即失败。Journey 标题下的 `准备：` 行被解析，`取证：` 行是 Spec 合同的一部分但 runtime 不解析，加减该行不影响校验。

## 命令

新调用按职责选择一个命令组；根 router 的语义组是 `package`、`ticket`、`evidence`、`recovery`、`gate` 五组，另有低层 `trail` 组（dispatch/return 记账，见 [Situation Inputs](situation-inputs.md)）。长参数表以 `--help` 为准。

```text
python <plugin>/scripts/impl_package_state.py --package <package> package init --attempt <id> --plan <repo-relative-plan>
python <plugin>/scripts/impl_package_state.py --package <package> package validate
python <plugin>/scripts/impl_package_state.py --package <package> package refresh-progress
python <plugin>/scripts/impl_package_state.py --package <package> package archive-attempt --attempt <id> --from-revision <commit>
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> evidence add      # 单条或数组，整批合法才写入
python <plugin>/scripts/impl_package_state.py --package <package> evidence invalidate --key <evidenceKey> --invalidated-by <reason>
python <plugin>/scripts/impl_package_state.py --package <package> package amendment add --id <id> --summary <text> --affected <contract path> [--affected <contract path> ...] --artifact <package 内路径>
python <plugin>/scripts/impl_package_state.py --package <package> package amendment confirm --id <id> --expect PENDING --confirmed-by <owner> --confirmed-revision <commit>
python <plugin>/scripts/impl_package_state.py --package <package> ticket satisfy <id> --expect <state> --revision <commit> [--environment <id>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket block <id> --expect <state> --evidence <path>
python <plugin>/scripts/impl_package_state.py --package <package> ticket needs-revalidation <id> --expect <state> --invalidated-by <reason> [--evidence <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket pending <id> --expect <state> [--revalidation-plan <path>]
python <plugin>/scripts/impl_package_state.py --package <package> ticket retire <id> --expect <state> --disposition waived|superseded --evidence <path> [--successor <id>]
python <plugin>/scripts/impl_package_state.py --package <package> recovery checkpoint --subject attempt|ticket:<id> --next <text> [--blocker <text>] [--evidence <path>] [--handoff]
python <plugin>/scripts/impl_package_state.py --package <package> recovery lease acquire --owner <worker-id> --key <resource-key> [--key <resource-key> ...]
python <plugin>/scripts/impl_package_state.py --package <package> recovery lease release --lease-id <id> --owner-token <token>
printf '<json>' | python <plugin>/scripts/impl_package_state.py --package <package> recovery judgment
python <plugin>/scripts/impl_package_state.py --package <package> gate pass --comparison-commit <commit> --reason <text> (--durable-delta <repo-relative path> ... | --no-durable-delta-reason <text>)
python <plugin>/scripts/impl_package_state.py --package <package> gate blocked --comparison-commit <commit> --reason <gap and next action>
```

`evidence add` 从 stdin 接受一个 evidence object 或一个非空 evidence object array。单对象输出为 `{evidenceKey, idempotent}`；数组输出为 `{records: [按输入顺序的单条结果], added, duplicates}`。批量输入会先完成全部记录的规范化与校验，任一元素非法则整批失败且不写入 state；完全重复（含批内重复）只返回幂等结果，不写入 state 或刷新 projection。含新增记录的批量调用只原子保存一次 state、刷新一次 projection，CLI 处境尾注仍按调用追加一次。

`ticket satisfy` 要求 `--revision` 是当前 HEAD 的 ancestor，负责套件与 required review 有有效 evidence，且 implementation/acceptance 入边已释放；`--environment` 可省略，若提供则写入 Ticket acceptance。套件环境核对始终读取 Spec 的 Required Suites.Environment。`ticket needs-revalidation` 把 Ticket 置为 `NEEDS-REVALIDATION`（不释放依赖），并失效该 Ticket 自有的 evidence（`review:<id>` 与其 Coverage 中 scope 为 ticket 的套件记录，reason 为 `--invalidated-by`；已失效的记录保持原 reason）；Journey step 与 package 级套件的 evidence 被多个 Ticket 共享，只用 `evidence invalidate --key` 失效。回到 `PENDING` 后重新 `satisfy` 需要新的有效 evidence。`gate pass` 在 header 后生成 `## Owner Summary`（每条 Journey 的走通进度、套件通过数、待确认或漏登的合同修订、发布顺序状态、最终版本短 SHA、结论），并按 composition contract §7 的两层清单核对；待确认或漏登的 Amendment 只阻止 pass。`gate pass` 还要求 `--durable-delta` 或 `--no-durable-delta-reason`，以及 `--comparison-commit`、`--reason`。`gate blocked` 记录缺口与 next action，Attempt 保持 active。`recovery lease acquire|release` lease 文件位于 `execution/<attempt>/leases/`。
