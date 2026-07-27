---
name: execution-preflight
description: 当准备从 handoff、plan、review、audit、Issue 或 execution artifact 开始任务时使用；在执行前一次性收齐 permission、owner authorization、HITL decision、必要的当前启动前置与 subagent mode。默认/长任务模式将主 session 限定为治理与收口，并充分使用 subagent 执行其余可隔离工作以控制上下文压力；普通模式允许主 session 直接执行局部工作。
---

# Execution Preflight

在基于既有执行材料开工前，建立一次有边界的 execution authorization bundle。它收齐授权与协作合同；只在当前即将开始的高风险单元或 plan 明确标为启动前必须存在的资源上做最小 readiness 检查，不建立全量环境状态或第二份执行合同。

## 核心合同

- 沿当前批准范围检查完整生命周期：实现、验证、证据、清理、外部工具以及计划内 Git/Issue 收口；不要只申请下一步权限。
- 只检查当前即将开始的高风险单元、或 plan 明确要求启动前存在的环境变量、工具、临时资源或 cleanup 前置；后续验证步骤的资源仍由 Planned Verification 按需处理，不要求预先登记。
- 将结果分为 `已授权`、`本次请求授权`、`明确禁止/不适用`。每项说明对象、环境、数据边界和最大副作用，使 owner 能以“全部批准 + 例外”一次作答。
- 启动前置只记录实际检查或精确 blocker，不展示 secret、token 或完整连接串；不创建通用 `ready`/`repairable`/`blocked` 状态表。
- host 允许且 owner 未禁止时，默认采用下述“默认/长任务模式”；普通模式只用于确实短小、低耦合的工作，或 owner 明确选择时。
- 一次性授权只属于当前任务。它可按明确 Task 边界传递给 subagent，但不扩展到新系统、更高环境、真实数据或 materially broader/destructive scope。

### Subagent modes

| 模式 | 何时选择 | 主 session | Subagent |
| --- | --- | --- | --- |
| `default-long`（默认/长任务） | handoff、implementation package、DAG、多阶段验证、长时间运行，或预计普通执行会明显挤占主 session 上下文 | **只保留**调度、授权记录、owner decision、跨 Task seaming、共享验证、Ticket acceptance、completion-claim audit、gate 与最终集成。 | 应充分用于所有可隔离、可复核且不重叠的调研、实现、测试、review 准备、证据/记录整理与 bounded Task work，以降低主 session 上下文压力。 |
| `ordinary`（普通） | 小型、短时、低耦合工作，或 owner 明确选择 | 负责治理、集成与上述收口职责，也可直接处理小型、紧耦合的执行工作。 | 可负责明确、bounded 的调研、实现、验证或 review；按任务收益选择派发粒度。 |

选择模式时记录名称与理由。除非 owner 明确指定 `ordinary`，handoff / package execution 一律选择 `default-long`。两种模式都不改变授权边界、主 session 的最终 acceptance/gate ownership，或 subagent 的非重叠 primary ownership。

## Workflow

### 1. 判断是否需要 Preflight

以下情况运行：请求从 handoff/plan/review/audit/Issue/execution artifact 开工，或涉及 delegation、外部环境、migration、cleanup、Git 发布、真实集成或 owner decision。

小型只读回答、简单本地命令，或授权已精确覆盖且当前单元没有明确启动前置的局部可逆修改可跳过；记录一句具体理由后继续。

完成标准：已明确跳过理由，或已识别需要读取的授权来源与当前启动前置。

### 2. 提取完整授权边界

先收集当前 session 对本任务已经明确允许或禁止的事项，再读来源中的 permission/HITL、执行、验证、清理、发布和外部依赖部分。若 preflight 需要继续，在输出 bundle 前完整读取 [authorization-contract.md](references/authorization-contract.md)，按其中的生命周期扫描和当前启动前置规则检查遗漏。

若当前 plan earns Tickets/DAG，同时验证同一 Attempt/P revision 的完整 earned artifact set 已联合批准；缺失、错版或只批准部分 bundle 都阻止开工。不要从一般代码库知识推测来源未提及的外部系统。

完成标准：每项 source-stated/current-session authorization 与 HITL 只记录一次；当前单元的明确启动前置已识别，没有引入相邻系统。

### 3. 检查当前启动前置

只对当前即将开始的高风险单元、或 plan 明确标为启动前必须存在的资源执行最小检查。优先使用只读或无业务副作用的操作：

- 环境变量/配置文件的存在性、target 类型、host/port/database-name allow-list 和 secret redaction；
- 现有 local container/service/port、工具可执行性、browser/native tool/runner 的可启动性；
- 已批准的测试 identity、temporary storage、fixture namespace 与 cleanup owner 是否可确定；
- 已计划 external provider 的 endpoint/credential presence，但不发送业务 payload、不调用生产或共享系统。

不得运行 migration、写 fixture、触发 provider/browser business flow、执行正式测试或创建新外部资源。若唯一修复是已授权且低副作用的本地动作（例如启动既有 loopback test container、载入未提交的本机 test env），可在本步骤执行并复核；其余缺口进入下一步一次性请求。未解决的前置只阻止依赖它的当前单元；后续、可隔离的验证资源不在此处制造 blocker。

完成标准：当前单元的明确启动前置已有最小证据或精确 blocker；无 secret 被输出。

### 4. 一次询问全部缺口

使用 reference 中的授权包模板，一次列出所有缺失权限；不要按执行顺序连续提问。已经回答的类别只重述，不再申请。计划明确禁止的事项只记录边界，除非 owner 主动要求跨越，否则不要求其反向确认。

默认选择 `default-long`。owner 明确禁止 delegation、host 不支持，或 owner 明确选择 `ordinary` 时，记录例外及其影响；在 `default-long` 中，普通执行切片优先由 subagent 承担。

请求同时列出未授权操作与不可由当前授权修复的当前启动前置。owner 可以用“全部批准”加可选例外，给出覆盖当前任务完整可预见生命周期的有界授权与必要环境动作。

### 5. 记录并继续

用 reference 中的执行授权模板记录：subagent mode、完整 allowed scope、实际启动前置检查或 blocker、仍被禁止的边界及 HITL 结论。`default-long` 必须记录主 session 保留职责（调度、授权记录、决策、跨 Task seaming、共享验证、Ticket acceptance、completion-claim audit、gate、最终集成）以及 subagent 可充分承担的调研、实现、验证、review 准备和记录工作；`ordinary` 记录主 session 可直接处理小型/紧耦合执行工作的例外。两种模式都记录授权传递方式和必须串行化的共享资源。

授权只在当前任务内有效。记录完成后直接进入既定执行入口，不为已授权的验证、清理、同边界命令或将执行工作委派给明确 subagent 再次询问。

完成标准：后续 session/agent 能从记录唯一判断某个操作是否在授权包内，以及当前启动前置是否已解决或阻断该单元。

### 6. 执行期边界

只有操作引入未提及的外部系统、更高环境、真实/敏感数据、显著扩大或更具破坏性的范围、新财务/法律副作用，或真正 owner decision 时，才再次请求授权。若当前单元的明确启动前置遗漏，可补齐该单元的精确缺口；不得借此要求全量盘点后续资源。

最终只报告实际影响完成度的授权缺口。面向 owner 汇报 readiness/status 时使用 `talk-to-boss`。

完成标准：执行在授权 bundle 内连续推进，或以唯一、精确的当前单元权限/环境/决策 blocker 停止。
