# Impl-Package Composition Contract

## 1. 权威边界

- Decision 与 Spec contract ensemble 定义要交付的行为、跨模块数据/API 合同与验收语义。每个新建或被修订的 Spec ensemble 同时包含 `spec.md` 与从属 `contract-design.md`；未触及的既有 Spec 可在下次 req-align 时补齐。
- Plan 定义一个 attempt 的执行策略、验证、Composition 和显式 Predecessors 声明。
- Ticket 定义纵向验收切片，是 package 唯一持久实施与验收单元。
- `.impl-package/state.json` 只保存当前执行状态与恢复入口。
- `progress.md` 是 current Attempt 的统一恢复投影；Execution Record 保存公共执行判断，active checkpoint 是跨 session 的正常恢复入口。
- `gate.md` 保存当前 gate 判决；历史由 Git 保存。

D/S/P 仅是可选的人类可读别名，不是新 artifact 的必填字段，也不绑定文件内容。不要为了小改动升级别名；需要固定比较点时只使用 Git commit ID。

`contract-design.md` 从属 `spec.md` 并共用 Status、审批和 Spec Gate；它没有独立 alias、revision、状态或生命周期。默认 `Disposition: detailed`；只有精确语义已由 `spec.md` 完整承担时才使用 `Disposition: not-required`，并写明理由。Plan 可以引用其中稳定章节，但不得复制或补设计另一套 DTO/schema。

Ticket 与 Task 引用 Decision/Spec/contract-design/Plan 中的合同或验收语义时，必须使用仓库相对路径并定位到具体一级或二级大章节（Markdown heading/anchor 或 `§章节名`）；引用 `contract-design.md` 时，因其体量大，必须在章节定位之外再命名具体 entry point（Operation/Aggregate/DTO/Seam/Projection 名称，或函数/类名），格式为 `path#section-anchor · <entry point 名>`；不得只裸指整份文档或整节，也不使用易漂移的行号。恢复、派发和验收默认按 section + entry point 定点检索，而不是把整节或整份合同文档作为无差别上下文。

## 2. Composition

每个 Attempt 由 Ticket 组成，依赖写在 Ticket 上。

## 3. 固定位置

- initial plan：`plan.md`
- patch plan：`<attempt-id>.patch-plan.md`
- Tickets：`tickets/` 的直接 Markdown 子文件
- current state：`.impl-package/state.json`
- current progress：`progress.md`
- Attempt Execution Record：`execution/<attempt-id>/execution-record.md`
- current gate：`gate.md`

外部引用一律保存为仓库相对路径。现役流程只访问这些固定位置和显式路径。

## 4. 生命周期

1. req-align 产出并批准 Decision/Spec contract ensemble。
2. impl-planning 创建 plan 并选择 Composition。
3. Plan 冻结后只创建 Draft Ticket；联合检查 coverage、typed dependency、证据可行性与集成顺序后取得一次 bundle approval。
4. `init` 发布当前 Attempt 的 Ticket，初始化 state 和完整 Progress 层，进入执行。
5. dev-with-track 从 `progress.md` 与 active checkpoint 恢复，根据 Ticket canonical dependency 选择下一动作，通过 CAS 更新状态并写 checkpoint/judgment。
6. dev-with-track 的 Verify and Gate 审计 completion claim。
7. gate 写入当前判决；`pass` 才支持默认的 merge-ready 结论。
8. durable delta 按需回刷稳定文档。

owner approval 绑定当时明确展示的 bundle；跨 session 恢复时用批准所在的 Git commit 加当前 diff 判断是否仍适用，不创建额外 receipt。

Plan、Ticket 或 DAG 的语义变化只使受影响范围的 approval/validation 失效；修正后只重审受影响部分。terminal Gate 冻结整个 Attempt，后续实现进入 patch Attempt，不改写旧记录。

## 5. Readiness

- 新 package 的 readiness 只由 Ticket typed dependency 与 Ticket state 判断。
- Ticket acceptance 由 Ticket AC、typed dependency 和 Ticket state 判断。
- `BLOCKED` 必须有直接原因和 evidence；checkpoint 只提供恢复上下文，不释放依赖。
- terminal gate 后若继续实现，创建新 patch attempt；不要改写旧 commit 来伪装原判决仍适用。
- Ticket dependency 必须拒绝未知 dependency 和 cycle，只允许 `implementation | acceptance | release`。

## 6. Ticket 运行边界

- Ticket barrier：未释放 `implementation` 边的 Ticket 不进入 `readyTickets`；`acceptance` 边允许实施但阻止最终 `SATISFIED`；`release` 边只在发布/Gate 前复核。
- early evidence 只能索引真实产物，不能把 Ticket 推进到中间 acceptance 状态。
- 第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；早期路径可以窄，但不能薄。
- 跨 session 续接沿用既有默认：交接前写 active checkpoint，长期判断写 ER judgment；compact 只作异常兜底，不是正常恢复权威。
- package task session 主线程是 `state.json` 唯一 writer；worker 只返回结构化 evidence。未来 broker 的协调 ledger 不属于本阶段。

`RETIRED` 是新合同中原 `WAIVED`/`SUPERSEDED` 的统一 terminal 状态，必须带 `disposition: waived | superseded`。3.6 runtime 只接受 Ticket/evidence/checkpoint 状态。

## 7. 3.6 Journey 验收合同

plan 必须写 `Acceptance: journey`（缺失即拒绝），生成 `formatVersion: "3.6"`；`Release order: required | none` 可选，缺省为 `none`。字段、record 与命令见 [current-state](impl-package-current-state.md)。

**验收对象由 Spec 定义，归属由 Ticket 声明。** `spec.md §7` 用三张固定列表承载合同，Spec 只写 Journey、step 与套件，不点名 Ticket：

| 表 | 列 | 要点 |
| --- | --- | --- |
| `### Journeys` 下每条 `#### J<n> <终态>` | `Step \| 角色 \| 入口类型 \| 控件 \| 操作入口 \| 观察表面 \| 预期 \| 承接` | step id 为 `J<n>-S<m>`，顺序固定；角色是执行该步的人（页面步用该角色自己的账号）；入口类型为 `页面 \| 文件 \| 记录`，页面步的控件写触发该步的可见控件名，文件与记录步写 `—`；`记录` 核对页面无法呈现的运行记录，不替代页面/文件步，不能是第 1 步；Journey 标题下可有 `准备：` 行写账号、权限、种子账套等由 harness 预置的前置条件，它不是 step；Journey 只含用户亲手做或亲自收到的步骤，用户看不到的行为（并发、幂等、回滚、租户隔离）归 Rule Matrix 与套件；承接是上一步交给本步的业务对象（如 `账单 ID`），无则 `—`，第 1 步恒为 `—` |
| `### Rule Matrix` | `Rule \| Source \| Suite \| Oracle` | 每条规则有 oracle，并指向一个已登记套件；Source 是 spec.md 内的章节引用（`§N`、`§N.M` 或标题原文，逗号分隔） |
| `### Required Suites` | `Suite \| Kind \| Scope \| Entry \| Environment` | Kind 为 `rule \| safety`，Scope 为 `ticket \| package`；Environment 写明确字符串，记录按字符串精确匹配 |

§7 可另有与 `### Journeys` 同级的 `### Journey 变体` 小节（语义见 req-align 的 acceptance-contract），runtime 不解析；放进 `### Journeys` 内会被当作 Journey 解析并报错。

表后固定一行 `- 无需验收的章节：<章节引用 | none>`。除 §7 外，spec.md 每个二、三级标题都要被某条 Source 引用（引用父章节覆盖子章节）或列在该行，否则 `package validate`/`package init`/`package check-spec` 失败并列出章节。

包级 safety 套件按风险声明：触及 tenant、RBAC/privacy、幂等或数据完整性时必须有，未触及时在 Spec 写明理由。套件清单是随 Spec Gate 审批的合同，Plan 与 Gate 不临时补造。

Ticket 的 `## Coverage` 是归属的唯一来源：

```text
- Journey steps: J1-S1, J1-S2 | none
- Suites: <suite id>[, ...] | none
- Required review: none | <review 范围与原因>
```

steps 与 suites 不同时为 `none`，harness、migration、加固类 Ticket 因负责套件而合法；每个 step 与每个 ticket 级套件至少被一张 Ticket 认领。依赖仍写在 `## Blocking Dependencies`，三类 typed edge 不变。

**Ticket `SATISFIED`** 的依据是：`--revision` 已合入（当前 HEAD 的 ancestor）、Coverage 里负责的套件都有有效 evidence、Required review 有有效结果，且 implementation/acceptance 入边已释放。Journey step 不是 Ticket 的满足条件，它归 Gate，下游因此不必等上游走通整条旅程。

**取证方式**是 Spec 合同的一部分：每条 Journey 在 `准备：` 下有 `取证：浏览器走查` 或 `取证：Playwright（理由：…）` 一行，建 Journey 时定，`package check-spec` 不解析它，由 Spec Gate 与 plan-review 核对。

**Journey 走通** 用 `journey-step` evidence 登记，每条带 `surface`（`page | file | log | api`）。面向客户的端到端验收是页面级（或用户实际收到的文件）；API 跑 Journey 是早期预演，在 UI 出现前让进度可见。

- `page`：默认是 package 内每步截图加 `manualBy`（走查人：Owner 或执行 agent 的标识，字段名沿用），走查方法见 `run-acceptance`。Playwright trace `.zip` 只用于 Spec 的 `取证：` 行声明了 Playwright 的步骤，其记录的动作须含对该步声明控件的 click/press/fill（runtime 解析 trace，不符即拒绝）。
- `file`：用户实际收到的文件（不接受 .md/.txt/.log），runtime 记录其 sha256。
- `log`：对应 `记录` 步，artifact 为 package 内文件。
- `api`：恒被接受，只计入预演。

两个进度数：`reach` 是同一 run 内从第 1 步起、surface 与声明的入口类型一致的连续有效步数，Gate 只认它；`rehearsalReach` 不限 surface。Gate 要求每条 Journey 在最终版本上有一次 reach 覆盖全部 step 的连续 run。证据版本漂移按实际判断：包外只有非运行时路径改动时自动沿用；有运行时改动时由 agent 看 diff 决定重走，或用 `evidence carry-forward` 登记沿用并写明理由与判断人（Owner Summary 单列）。runtime 还核对 `entry` 与 Spec 一致、顺序与有效期；“上一步输出是下一步输入”由执行者在 artifact 中记录，由 review 与 Owner 抽查。

**Harness 与 run 隔离**：3.6 plan 用固定行 `Harness setup/precheck/cleanup`、`Harness isolation: per-run` 与 `First visible step: <StepId> @ <TicketId>` 声明验证 harness（命令来自项目 QA 入口，性质见 `validation-harness`），缺失或无效时 `package init/validate` 拒绝。每个 run 先登记 `run-setup` evidence（setup 与 precheck 输出），该 run 的 `journey-step` 才被接受；第 1 步的 `outputRef` 不得出现在其他 run，即每个 run 使用自己创建的对象。声明的 Ticket 已 `SATISFIED` 而声明的 step 仍无匹配的 page/file record 时，触发 `attempt.walking_skeleton_overdue`，进入 situation 与 Owner Summary。

**Gate 分两层核对**：产品层（Journey）与规则/安全层（Required Suites）；其余是 Ticket 与合入、最终 HEAD 的 terminal-final review、Amendment、发布顺序和既有终态条件。任一必需事实 unknown 即不放行。

**Amendment** 登记批准后改变用户可见结果的合同修订，Owner 确认绑定具体修订版本，内容再变化用新 ID。待确认或漏登的 Amendment 只阻止 `gate pass`，已授权且不依赖该语义的工作继续。

**发布顺序** `Release order: required` 时是一条 `release` evidence，artifact 为 package 内的发布顺序表（合入、fixture/backfill、开关/发布、清理），不逐条记录 worker dispatch。
