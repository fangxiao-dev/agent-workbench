# Impl-Package Composition Contract

## 1. 权威边界

- Decision 与 Spec contract ensemble 定义要交付的行为、跨模块数据/API 合同与验收语义。每个新建或被修订的 Spec ensemble 同时包含 `spec.md` 与从属 `contract-design.md`；未触及的 legacy Spec 可在下次 req-align 时补齐。
- Plan 定义一个 attempt 的执行策略、验证、Composition 和显式 Predecessors 声明。
- Ticket 定义纵向验收切片，是新 package 唯一持久实施与验收单元；DAG/Task 只作为旧 package 的迁移与恢复输入。
- `.impl-package/state.json` 只保存当前执行状态与恢复入口。
- `progress.md` 是 current Attempt 的统一恢复投影；Execution Record 保存公共执行判断，active checkpoint 是跨 session 的正常恢复入口。Task Handoff 只为旧 package 保留，不能成为新 package 的默认执行轴。
- `gate.md` 保存当前 gate 判决；历史由 Git 保存。

D/S/P 仅是可选的人类可读别名，不是新 artifact 的必填字段，也不绑定文件内容。不要为了小改动升级别名；需要固定比较点时只使用 Git commit ID。

`contract-design.md` 从属 `spec.md` 并共用 Status、审批和 Spec Gate；它没有独立 alias、revision、状态或生命周期。默认 `Disposition: detailed`；只有精确语义已由 `spec.md` 完整承担时才使用 `Disposition: not-required`，并写明理由。Plan 可以引用其中稳定章节，但不得复制或补设计另一套 DTO/schema。

Ticket 与 Task 引用 Decision/Spec/contract-design/Plan 中的合同或验收语义时，必须使用仓库相对路径并定位到具体一级或二级大章节（Markdown heading/anchor 或 `§章节名`）；引用 `contract-design.md` 时，因其体量大，必须在章节定位之外再命名具体 entry point（Operation/Aggregate/DTO/Seam/Projection 名称，或函数/类名），格式为 `path#section-anchor · <entry point 名>`；不得只裸指整份文档或整节，也不使用易漂移的行号。恢复、派发和验收默认按 section + entry point 定点检索，而不是把整节或整份合同文档作为无差别上下文。

## 2. Composition

新 package 的 Plan 必须声明 Ticket-only Composition：

```text
Composition：tickets=true, dag=false
```

阶段 A 保留 `dag=false` 作为当前 3.4 state engine 的兼容占位；它不表示创建 Task、DAG 或 Task Handoff。新 package 只有 Ticket-only 组合：

| tickets | dag | 用途 |
| --- | --- | --- |
| true | false | 需要独立验收切片的 Ticket-only package，依赖只写在 Ticket 上 |

`dag=true` 仅用于已有 3.4/Task package 的恢复、迁移或只读审计；新 planning 路径不得选择它。阶段 A 期间旧 state engine 可能仍写出空的 `tasks` 对象，但新 package 不产生 Task 行或 Task runtime projection；阶段 B 删除该兼容字段。

新 package 始终创建 Ticket；不要为了完整感创建 Task、DAG 或 Task Handoff。

## 3. 固定位置

- initial plan：`plan.md`
- patch plan：`<attempt-id>.patch-plan.md`
- Tickets：`tickets/` 的直接 Markdown 子文件
- initial/patch DAG：仅旧 package 的 `dag.md` 或 `<attempt-id>.patch-dag.md`
- current state：`.impl-package/state.json`
- current progress：`progress.md`
- Attempt Execution Record：`execution/<attempt-id>/execution-record.md`
- Task Handoff：仅旧 package 的 `execution/<attempt-id>/task-handoffs/<task-id>-handoff.md`
- current gate：`gate.md`

外部引用一律保存为仓库相对路径。现役流程只访问这些固定位置和显式路径。

## 4. 生命周期

1. req-align 产出并批准 Decision/Spec contract ensemble。
2. impl-planning 创建 plan 并选择 Composition。
3. Plan 冻结后，Ticket-only Composition 只创建 Draft Ticket；联合检查 coverage、typed dependency、证据可行性与集成顺序后取得一次 bundle approval。旧 package 的 DAG 只读，不重新发布。
4. `init` 发布当前 Attempt 的 Ticket，初始化 state 和完整 Progress 层，进入执行；3.4 兼容字段不代表 Task execution。
5. dev-with-track 从 `progress.md` 与 active checkpoint 恢复，根据 Ticket canonical dependency 选择下一动作，通过 CAS 更新状态并写 checkpoint/judgment。
6. dev-with-track 的 Verify and Gate 审计 completion claim。
7. gate 写入当前判决；`pass` 才支持默认的 merge-ready 结论。
8. durable delta 按需回刷稳定文档。

owner approval 绑定当时明确展示的 bundle；跨 session 恢复时用批准所在的 Git commit 加当前 diff 判断是否仍适用，不创建额外 receipt。

Plan、Ticket 或 DAG 的语义变化只使受影响范围的 approval/validation 失效；修正后只重审受影响部分。terminal Gate 冻结整个 Attempt，后续实现进入 patch Attempt，不改写旧记录。

## 5. Readiness

- 新 package 的 readiness 只由 Ticket typed dependency 与 Ticket state 判断。
- Ticket acceptance 由 Ticket AC、typed dependency 和 Ticket state 判断。
- 旧 package 的 Task `DONE` 不等于 Ticket `SATISFIED`，迁移时必须重新映射真实 evidence。
- `BLOCKED` 必须有直接原因和 evidence；checkpoint 只提供恢复上下文，不释放依赖。
- terminal gate 后若继续实现，创建新 patch attempt；不要改写旧 commit 来伪装原判决仍适用。
- Ticket dependency 必须拒绝未知 dependency 和 cycle，只允许 `implementation | acceptance | release`。
- 旧 DAG 的 `READY/RUNNING` 不得越过未释放 Task dependency；新 package 不创建这条状态轴。

## 6. Ticket-only 运行边界

以下 stable claim 条目是 3.5 package 的 acceptance 合同；3.6 package 见 §7。

- 新 package 严格使用 Ticket barrier：未释放 `implementation` 边的 Ticket 不进入 `readyTickets`；`acceptance` 边允许实施但阻止最终 `SATISFIED`；`release` 边只在发布/Gate 前复核。
- early evidence 只能索引真实产物，不能把 Ticket 推进到中间 acceptance 状态。Ticket 仍需覆盖全部 required claims 才能最终满足。
- stable claim 是 runtime 可判定的 acceptance atom。一个业务 AC 可以包含多个 stable claim ID；可独立失败或需要不同 oracle/evidence lane 直接证明的子句必须拆成不同 ID，同一不可分割 oracle 共同裁决的一组场景可以保留一个 ID。多个 claim 可以引用同一 artifact，但每个 ID 都必须有自己的 evidence record。
- Ticket AC 必须显式编号 stable claim ID；early falsification evidence 与 remaining completion evidence 分开描述。
- 第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；早期路径可以窄，但不能薄。
- 跨 session 续接沿用既有默认：交接前写 active checkpoint，长期判断写 ER judgment；compact 只作异常兜底，不是正常恢复权威。
- package task session 主线程是 `state.json` 唯一 writer；worker 只返回结构化 evidence。未来 broker 的协调 ledger 不属于本阶段。

`RETIRED` 是新合同中原 `WAIVED`/`SUPERSEDED` 的统一 terminal 状态，必须带 `disposition: waived | superseded`。3.4 runtime 只作为一次性迁移输入；3.5/3.6 runtime 只接受 Ticket/evidence/checkpoint 状态。

## 7. 3.6 Journey 验收合同

新 package 的 plan 写 `Acceptance: journey` 生成 `formatVersion: "3.6"`；`Release order: required | none` 可选，缺省为 `none`。无该标记的 plan 与既有 3.5 package 继续使用 §6 的 stable claim 合同，不迁移；两种格式互不读取对方字段。字段、record 与命令见 [current-state](impl-package-current-state.md)。

**验收对象由 Spec 定义，归属由 Ticket 声明。** `spec.md §7` 用三张固定列表承载合同，Spec 只写 Journey、step 与套件，不点名 Ticket：

| 表 | 列 | 要点 |
| --- | --- | --- |
| `### Journeys` 下每条 `#### J<n> <终态>` | `Step \| 操作入口 \| 观察表面 \| 预期` | step id 为 `J<n>-S<m>`，顺序固定；承诺落在页面上的步骤，入口与表面都是页面 |
| `### Rule Matrix` | `Rule \| Suite \| Oracle` | 每条规则有 oracle，并指向一个已登记套件 |
| `### Required Suites` | `Suite \| Kind \| Scope \| Entry \| Environment` | Kind 为 `rule \| safety`，Scope 为 `ticket \| package`；Environment 写明确字符串，记录按字符串精确匹配 |

包级 safety 套件按风险声明：触及 tenant、RBAC/privacy、幂等或数据完整性时必须有，未触及时在 Spec 写明理由。套件清单是随 Spec Gate 审批的合同，Plan 与 Gate 不临时补造。

Ticket 的 `## Coverage` 是归属的唯一来源：

```text
- Journey steps: J1-S1, J1-S2 | none
- Suites: <suite id>[, ...] | none
- Required review: none | <review 范围与原因>
```

steps 与 suites 不同时为 `none`，harness、migration、加固类 Ticket 因负责套件而合法；每个 step 与每个 ticket 级套件至少被一张 Ticket 认领。依赖仍写在 `## Blocking Dependencies`，三类 typed edge 不变。

**Ticket `SATISFIED`** 的依据是：`--revision` 已合入（当前 HEAD 的 ancestor）、Coverage 里负责的套件都有有效 evidence、Required review 有有效结果，且 implementation/acceptance 入边已释放。Journey step 不是 Ticket 的满足条件，它归 Gate，下游因此不必等上游走通整条旅程。

**Journey 走通** 用 `journey-step` evidence 登记；reach 是同一 run 内从第 1 步起连续有效的步数，给 Owner 看进度，不是 Gate 条件。Gate 要求每条 Journey 在最终版本上有一次覆盖全部 step 的连续 run。runtime 只核对 `entry` 与 Spec 一致、顺序与有效期；“上一步输出是下一步输入”由执行者在 artifact 中记录，由 review 与 Owner 抽查。

**Gate 分两层核对**：产品层（Journey）与规则/安全层（Required Suites）；其余是 Ticket 与合入、最终 HEAD 的 terminal-final review、Amendment、发布顺序和既有终态条件。任一必需事实 unknown 即不放行。

**Amendment** 登记批准后改变用户可见结果的合同修订，Owner 确认绑定具体修订版本，内容再变化用新 ID。待确认或漏登的 Amendment 只阻止 `gate pass`，已授权且不依赖该语义的工作继续。

**发布顺序** `Release order: required` 时是一条 `release` evidence，artifact 为 package 内的发布顺序表（合入、fixture/backfill、开关/发布、清理），不逐条记录 worker dispatch。

**旧检查的接替关系**：

| 3.5 检查 | 3.6 |
| --- | --- |
| Ticket AC stable claim、per-claim evidence | Journey 连续走通记录与规则套件结果，按套件登记 |
| Safety Invariants claim | 包级 safety 套件 |
| Ticket `SATISFIED` 的 claim 覆盖 | 已合入 + 负责套件通过 + required review 通过 |
| acceptance map、Final Gate “Spec AC 能定位到 Ticket claim” | Gate 两层核对 |
