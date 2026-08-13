# 五个 Codex rollout 的 Impl-Package 执行事实分析

## 范围、口径与总判断

本报告只分析五个按时间顺序提供的 Codex rollout JSONL，不评价业务代码质量，也不把规划完成、Task 完成、Ticket 满足和 Gate 通过混为一谈。分析脚本逐行执行 `json.loads`，没有把整个 JSONL 读入内存；五个文件共解析 11,650 个事件，解析错误为 0。报告中的“函数调用”包含两种 rollout 事件：原生 `function_call` 870 个，以及 `custom_tool_call` 1,308 个；后者内部通常是 `exec`，再包裹 `shell_command`、`apply_patch` 等工具。

截至第五个 session 结束，证据显示：规划和执行控制面已经形成，9 个 Task 中 7 个被标为 DONE，但 5 个 Ticket 仍为 0 个 SATISFIED，Gate 仍 open；更重要的是，五个 session 内没有出现“真实文件从解析到 tenant-scoped staging 入库再读回”的完整端到端证据。因此，本报告的“审计/提取阶段”已完成，但被分析的 implementation package 本身在这些记录的终点仍未 closed。

统计限制：一个 `exec` 可能在同一脚本中串行执行多个命令，函数调用计数不是操作系统进程计数；命令输出长度是观察到的输出字节估计，不等于被读文件的真实字节数。派发 prompt 的正文在原始记录中主要是 `gAAAA...` 加密载荷，所以可以统计字符数量级，不能诚实地计算其中多少字符是在复述合同。

## Q1 时间线与工作量分布

### 结论

五段 session 不是五个独立实现阶段，而是“长规划 → T1–T5 实现 → T6 反复补 seam → T7 前置修复/重跑”的连续链。每次后续 session 都在读取上一个 session 的 Execution Record、当前状态和 handoff，但仍付出了明显的重新定位成本。五段记录在 UTC 时间上有约 1–2 分钟的边界重叠，这是父/子 agent 或续接 session 的调度重叠，不应把五段时长直接相加当成单线程墙钟时间。

### 数据表

| Session | UTC 起止与持续时间 | 事件数 | 函数调用数 | 实际触及的 Task / Ticket | 主要产出 |
|---|---|---:|---:|---|---|
| S1：2026-08-11 | 2026-08-11 13:51:53.117Z – 2026-08-12 20:07:26.821Z；约 30:15:33.704 | 4,175 | native 198 + custom 466 = 664 | 规划覆盖 T1–T9；DMI-01–DMI-05；另对 ASP-01–08 做上游依赖确认 | 研究结论、Decision D1/D2、Spec S1–S6、Plan P1–P5、5 个 Ticket、DAG、评审意见、初始状态与 `initial-ER-003`；没有进入核心业务实现 |
| S2：2026-08-12 | 2026-08-12 19:38:30.249Z – 23:02:14.512Z；约 03:23:44.263 | 2,237 | 262 + 197 = 459 | 实际 T1–T5；文档仍覆盖 DMI-01–DMI-05；T6 为下一工作单元 | T1 解析/规范化，T2 Files 能力/保留策略，T3 Prisma staging/tenant/CAS，T4 authoring，T5 authority seam；产生测试与 `initial-ER-011` |
| S3：2026-08-12/13 | 2026-08-12 23:00:18.305Z – 2026-08-13 04:28:25.716Z；约 05:28:07.411 | 1,204 | 112 + 136 = 248 | 实际 T6；T7–T9 被明确作为下游；主要关联 DMI-03/04/05 | T6 publication facade、authority-owned scope readiness/currentness seam；首次 Implementer 返回 INCOMPLETE，经过 scope-authority、fixer、verifier 再闭合为 T6 DONE；产生 `initial-ER-015` |
| S4：2026-08-13 | 2026-08-13 04:27:27.411Z – 07:44:50.501Z；约 03:17:23.090 | 2,638 | 186 + 319 = 505 | 以 T7 readiness 为主；重新验证/修复 T3、T4、T6 的 S6/P5 seam；DMI-04/05 为实际焦点，Ticket 轴仍未满足 | T7 首次被阻塞；补做 T3 persistence guard、T4 authoring/readiness port、T6 publication/projection closure；两次 `call-grok` 检查尝试；产生 `initial-ER-019` |
| S5：2026-08-13 | 2026-08-13 07:42:10.899Z – 09:22:25.291Z；约 01:40:14.392 | 1,396 | 112 + 190 = 302 | T4-F3 修复后实际 T7；T8/T9 只作为下一步和剩余依赖；DMI-04/05 | Billing controller/DTO/mapper、OpenAPI 与 generated client、contract tests；T7 DONE，写出 `initial-ER-022`，但真实 HTTP/DB/Web/T9 尚未执行 |

事件计数含所有 rollout 事件类型，不只是消息和工具；因此它反映日志工作量，而不是代码行数。S1 的持续时间特别长，主要原因是规划、研究、多个盲审/方案审查和跨 session handoff，而不是持续实现。

### 原文佐证

S5 末尾给出的累计状态清楚地区分了 Task 与 Ticket：

> `T7 已完成并验收；当前为 7/9 Tasks DONE、0/5 Tickets SATISFIED、Gate open。`（S5，2026-08-13T09:09:48.932Z）

S2 的续接不是从零开始，而是从上一个 ER 进入 T1–T3：

> `initial-ER-003` 被作为当前锚点，随后按 T1、T2、T3 的 bounded work 依次派发。（S2，2026-08-12T19:40 左右）

## Q2 核心纵切第一次形成端到端证据的位置

### 结论

在这五个 session 中，第一次完整的“XLSX/CSV 文件 → 解析 → 规范化 → tenant-scoped staging 表入库 → 读回”证据不存在，时间点为 N/A。最高进度是 T7 的公共 API/OpenAPI 契约完成；T8、T9 以及真实 PostgreSQL/HTTP/Web 场景仍未跑通，所以不能把 parser 测试、迁移测试或 DTO contract test 拼接成端到端证据。

如果以“整体进度”作参照，日志终点是 7/9 Task DONE，即约 77.8%，但 0/5 Ticket SATISFIED；不存在一个可以标记为“在 77.8% 处首次 E2E”的时刻。这个反差是本题最重要的事实之一。

### 数据表：在 E2E 之前实际优先做掉的工作

| 先后 | 实际优先工作 | 产生的局部证据 | 仍缺的 E2E 环节 |
|---:|---|---|---|
| 1 | S1 研究、Decision/Spec、Plan、Ticket、DAG、上游 AccountingScope ASP-07/08 对齐 | 形成了纵切验收与横向依赖的书面合同 | 没有运行时业务证据 |
| 2 | T1 parser/normalizer：XLSX 依赖、表头/字段映射、负面用例 | parser 与 normalizer focused tests | 输入不是通过真实上传链路进入 staging |
| 3 | T2 Files capability/retention 与 T3 migration、tenant guard、CAS | S2 有 54 个 parser/Files/admin 测试；另有 4 个 DB 文件、138 个测试 | 不是“读真实文件并写真实 staging 再读回”的同一旅程 |
| 4 | T4 authoring/form/approval 与 T5 authority/policy seam | authoring、authority focused tests 和状态证据 | 尚未连接完整 publication/read-back journey |
| 5 | T6 publication facade、scope readiness/currentness 与可发布投影 | S3 focused Vitest、typecheck、lint 通过；但明确不证明真实 PG/HTTP | 仍缺真实数据库事务和下游 contract/scenario |
| 6 | T7 controller/DTO/OpenAPI/generated client | 11 个 operation 的 API contract evidence | 真实 HTTP app、Web consumer、T9 integrated scenario 未执行 |

### 原文佐证

S2 的 54 个测试是局部、内存型证据，不是 E2E：

> `3 files passed; 54 tests passed`；覆盖 parser/Files/admin focused tests。（S2，2026-08-12T20:41:11.683Z）

S3 的 handoff 主动写明剩余证据边界：

> `该证据不证明 authority scope composition、真实 PostgreSQL CAS/fault、T7 contract propagation、T9 scenario 或任何 Ticket acceptance。`（S3，2026-08-12T23:58:53.596Z）

S5 终点也没有把 T7 契约误报为旅程完成：

> `真实HTTP app启动、Web consumer、real PostgreSQL/scenario...仍未执行。`（S5，2026-08-13T09:09:48.932Z）

## Q3 T6 → T7 → T8 → T9 串行段的真实依赖强度

### 结论

宣告的 DAG 是严格串行的：T6 依赖 T4/T5，T7 依赖 T4/T6，T8 依赖 T7，T9 依赖 T1–T8。实际已观察到的 T6→T7 依赖很窄，主要是一个 public application/projection/schema seam，而不是 T6 的大部分内部实现；大致应归类为“只依赖某个接口或 schema”。T7→T8 和 T8→T9 在这五段里没有实际后继执行，只有声明式依赖，不能把未发生的读取写成已发生。

### Task 定义、ownership 与声明依赖

| Task | 描述与 ownership | declared dependency | Ticket / acceptance 关联 |
|---|---|---|---|
| T6 | Import publication facade；拥有 durable attempt/replay、Tx-A/Tx-B、authority projection、publication readiness/currentness；不拥有 publisher 私有表或 Workbench 类型 | T4、T5 | ASP-07；DMI-03、DMI-04、DMI-05 |
| T7 | API and generated contracts；拥有 Billing module wiring、controller/DTO、OpenAPI/generated client、contract tests | T4、T6 | ASP-08；DMI-04、DMI-05；后续修订还触及 DMI-01 的 opaque `uploadToken` |
| T8 | Web onboarding surface；拥有固定范围 deep-link route、组件、API wrapper、query keys、Web tests；route 为 `/billing/accounting-scopes/{accountingScopeId}/datev-policy-imports/{importId}` | T7 | DMI-04、DMI-05；不拥有 Workbench DTO 或 scope discovery |
| T9 | Cross-layer verification；拥有 real-postgres-integration-runner、scenario governance、共享验收证据 | T1–T8 以及 ASP-07/08 | DMI-01–DMI-05 全部；Task DONE 不等于 Ticket accepted |

### 三条边的实际产物证据

| 边 | 后继实际读取/消费的前驱产物 | 后继是否修改前驱文件 | 真实依赖强度判断 |
|---|---|---|---|
| T6 → T7 | T7 读取/消费 T6 的 public application seam 与 projection：`DatevPolicyPublicationProjectionDto`、`DatevPolicyImportRuntimeReadinessDto`、`DatevPolicyImportSourceIdentityDto`，以及 `blockingCode`、`publishedProfileVersionId`、`publishedSourceImportId`、`publishedCompiledPolicyId`、`publicationAttemptId`、`runtimeReadiness` 等安全字段；`publish/resume` 通过 attempt id 路由 | T7 修改的是自己的 `apps/api/src/billing/...` controller/DTO/mapper/spec、`packages/contracts/openapi/openapi.json` 和 generated client，不是 T6 的内部 repository/私有表 | **只依赖某个接口/DTO/schema**。T7 不依赖 T6 的大多数事务和内部实现，但依赖 seam 是否真实存在、是否能承载 idempotency/optimistic binding/read projection |
| T7 → T8 | 本期没有 T8 worker 或 T8 source edit；只留下 T7 的 public route/DTO/OpenAPI/generated-client contract 作为宣告上的输入 | 没有实际 T8 修改可供比较 | **未观测**；宣告上只应消费 API contract，而非 Billing 内部类型 |
| T8 → T9 | 本期 T8、T9 都没有实现；T9 只在 DAG 中声明依赖 T1–T8、真实 PG runner 和场景证据 | 没有实际后继读取/修改 | **宣告上全量依赖，实际证据为 0**；不能据此推断实现耦合比例 |

T6→T7 的“接口依赖”不是纯理论：T7 首次执行时发现既有 T6/T4 application seam 不能承载冻结的公共契约，因而被阻塞并回退修复。这里依赖的是投影和行为承诺，而不是某个类名本身。

### 原文佐证

四个 Task 的 DAG 行给出了声明式串行关系：

> `| T6 | Import publication facade | T4, T5 | DMI-03, DMI-04, DMI-05 | canonical publication and readiness |`
> `| T7 | API and generated contracts | T4, T6 | DMI-04, DMI-05 | controller/OpenAPI/client propagation |`
> `| T8 | Web onboarding surface | T7 | DMI-04, DMI-05 | scope-owned onboarding UI |`（S1，2026-08-11T19:53:50.883Z）

T9 的全量依赖和 integrated acceptance ownership 已在上面的定义表中记录。

T7 首次 handoff 直接说明它对前驱 seam 的实际依赖：

> `DatevPolicyImportService + repository did not have [the mutation idempotency] key seam; T7 must not receive/discard.`
> `dry-run/publish/resume expected fields [were] absent from service/facade.`（S5，2026-08-13T08:51:26.482Z）

## Q4 流程开销 vs 实现工作

### 结论

按“能无歧义识别”的函数调用计数，2,178 个函数调用中只有 64 个可以直接归为实现动作（业务源码 patch 或明确的测试/lint/typecheck/build/db 命令），约 2.9%；状态机 CLI 98 个，约 4.5%；方法论/合同文档读取 223 个，约 10.2%。其余 1,793 个是 agent 协作、等待、列表、状态/文件探查、混合脚本或无法安全归类的调用，约 82.3%。

这是保守下界，不是说所有“其他”都没有实现价值：一些 `exec` 在一个脚本里同时读文档、运行测试或生成文件，无法无争议拆分。若把关键词能识别但含混的实现相关调用也上收，implementation-related 上界为 custom call 199 个，约占全部函数调用 9.1%；报告主结论使用 64 个保守数，避免把状态核对误算成实现。

### 计数表

总量：native `function_call` 870 + custom `custom_tool_call` 1,308 = **2,178**。

| 分类（互斥主计数） | 次数 | 占全部函数调用 | 计数说明 |
|---|---:|---:|---|
| 状态机 CLI | 98 | 4.5% | `impl_package_state.py` 或变量绑定 CLI 的 custom `exec` wrapper；其中 94 个能直接读出子命令，另 4 个为变量/组合脚本 |
| 方法论/合同文档读取 | 223 | 10.2% | 去掉状态 CLI 重叠后的唯一 wrapper；观察到输出约 1,801,416 bytes |
| 明确实现动作 | 64 | 2.9% | 业务源码 `apply_patch` 27 个 + 明确测试/lint/typecheck/build/db shell wrapper 37 个；shell 内命令可能仍有合并 |
| 其他 / 协作 / 检查 | 1,793 | 82.3% | 923 个剩余 custom call + 870 个 native 协作/等待/派发调用 |
| **合计** | **2,178** | **100%** |  |

状态机直接可识别的子命令次数如下；一个 wrapper 可能含多个真实 CLI 进程，所以这是保守的文本识别数：

| 子命令 | init | status | validate | refresh-progress | set-state | er-add | checkpoint | gate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| 直接识别次数 | 4 | 3 | 22 | 9 | 32 | 14 | 10 | 0 |

方法论/合同读取按 target hit 的重叠计数如下；一条调用可同时命中多个 target，不能把这一表纵向求和：

| 文档 target | hit 次数 | 观察到的输出字节 |
|---|---:|---:|
| `SKILL.md` | 110 | 945,985 |
| `composition-contract` | 12 | 164,604 |
| `current-state` | 11 | 131,791 |
| `plan.md` | 66 | 685,268 |
| `tickets/*.md` | 30 | 256,945 |
| `dag.md` | 42 | 381,145 |
| `progress.md` | 48 | 179,161 |
| `execution-record` | 12 | 146,415 |
| `handoff` / `task-handoffs` | 47 | 392,552 |
| **target hit 合计** | **338** | **3,283,862** |

这里 target hit 合计大于 223，是因为同一调用可能读多个文档；`references/*.md` 已归入方法论/合同读取，但没有另拆一行。主比例使用互斥的 223 个 wrapper 和 1,801,416 bytes。实现侧的可见细分为：测试命令 26 次、lint 11 次、typecheck 18 次、build/contracts 3 次、数据库命令 22 次；这些类别有重叠，取并集后为 37 个 shell wrapper，再与 27 个业务 patch 合并为 64。

状态账本写入的额外规模也很清楚：直接 patch 触及 Task Handoff 的调用 28 个、路径出现 44 次，patch 输入约 71,568 字符；真正通过 `er-add` 写 Execution Record 的调用 11 个，命令/payload 输入约 17,354 字符。这些是流程产物的写入规模估计，不是最终 Markdown 文件大小。

### 原文佐证

状态投影错误需要单独修复，而不是普通实现命令：

> `progress projection mismatch; run refresh-progress`
> 随后运行 `refresh-progress`，再重新 `validate`。（S1，2026-08-12T18:35:16.639Z 起）

测试虽然大量通过，仍处在局部实现层：

> `4 files; 138 tests passed`
> 同一段还执行了 `pnpm db:validate`，但不是完整文件旅程。（S2，2026-08-12T20:46:01.322Z）

## Q5 状态机与文档摩擦点

### 结论

摩擦主要不是单个 CLI 崩溃，而是三类循环：状态投影落后于事实、Task 证据或依赖未释放导致 set-state 拒绝、canonical 文档位置/插件版本漂移导致重复搜索。`NEEDS-REVALIDATION` 和 `BLOCKED` 确实阻止了假完成；但连续片段显示 agent 也花了相当时间补状态账和写 handoff。原始记录中没有发现明确的“CAS `--expect` mismatch”错误行，只有 CAS/乐观绑定合同、状态投影 mismatch 和依赖未释放；不把后者冒充成 CAS mismatch。

### 事件表

| 摩擦类型 | 观察到的事件 | 影响 |
|---|---|---|
| init / validate 失败 | S1 的 `init` 报 `earned DAG is missing the Task graph section`；随后 validate 报 projection mismatch | 先修复 earned DAG / progress 投影，才能继续状态操作 |
| refresh-progress 修复 | S1 18:35 左右、S4 05:39 左右均先失败再 refresh-progress 后重验 | 状态机把派生投影当作需要显式维护的账本，产生额外调用 |
| set-state 被拒绝 | S2 20:01 的 bulk set-state 报 `DAG runtime projection mismatch`；S4 04:38 设置 T7 BLOCKED 也遇到同类错误 | 不能直接按预期状态覆盖 runtime projection |
| 依赖未释放 | S2 22:09 T4、22:10 T5 的 set-state 被拒绝，因为 dependency 未 released | 迫使当前 Task 回退或标记 revalidation |
| NEEDS-REVALIDATION / BLOCKED | S2 T4/T5 进入 NEEDS-REVALIDATION；S5 07:57 T7 BLOCKED、T4 NEEDS-REVALIDATION | 把前置 seam 缺口显式暴露给后续 session |
| FAILED | 没有观察到 Task 被置为 `FAILED`；只有命令级失败/exit 1 或 worker `INCOMPLETE` | 不能声称状态机发生了 FAILED 转换 |
| canonical 路径漂移 | S1 找不到 mapped worktree 的 idea 目录；S1/S2 多次尝试 0.2.1、0.2.7 等旧插件路径；S5 误找 package `handoffs` 目录 | 恢复时重复搜索真实 skill、script、handoff canonical 位置 |

### 状态恢复的连续补账片段

| 时间跨度 | 连续行为 | 判断 |
|---|---|---|
| S1 18:06:57–18:08:21，约 1 分 24 秒 | init 失败 → 修复/再次 init → checkpoint → refresh/validate | 典型状态账修复片段 |
| S2 22:08:39–22:10:49，约 2 分 10 秒 | status/help、证据不存在、依赖未释放、T4/T5 revalidation | 状态转换与证据登记占主导，非业务代码推进 |
| S4 05:52:50–06:25:46，约 32 分 56 秒 | 反复读取/修订 T3/T4/T6 状态、set-state、validate、写 handoff | 五段中最明显的补状态账长片段 |
| S5 09:07:28–09:09:25，约 1 分 57 秒 | er-add help、写判断/checkpoint、T7 DONE、validate/progress | 在报告 T7 结论前补齐状态投影和 ER |

### 原文佐证

S2 的依赖保护是真正的拒绝，而非主 agent 忘了运行命令：

> `Task T4 is RUNNING while dependencies are not released`
> 随后 T5 也被报 `dependencies are not released`。（S2，2026-08-12T22:09:16.085Z–22:10:20.396Z）

S5 的状态机把 T7 的阻塞和 T4 的返工同时保留下来：

> `T7 BLOCKED; T4 NEEDS-REVALIDATION; T4 RUNNING`
> 之后才转为 `T4 DONE / T7 READY / RUNNING`。（S5，2026-08-13T07:57:18 左右）

路径摩擦也确实发生过：

> mapped worktree 中 `docs\\ideas\\datev-mandant-profile-import` 不存在，随后改查主 workspace。（S1，2026-08-11T13:52:26 左右）

> 旧的 `...impl-package\\0.2.7\\scripts\\impl_package_state.py` 不存在，随后搜索并切到 0.2.8。（S2，2026-08-12T20:54:06 左右）

## Q6 派发与并行的实际情况

### 结论

派发不是象征性的：出现了 61 次 `spawn_agent`、52 次 `followup_task`，共 113 次原生派发/续派尝试；实际有 50 个 `sub_agent_activity` start，6 个被 interrupt。另有 3 次可识别的 `call-grok` 外部 worker。真实并行集中在早期 T1/T2/T3 调查和实现：最高可从时间戳确认的并发度为 3；T6、T7 及其关键修复基本是串行推进，背景 blind review 没有形成稳定的代码并行产出。

### 派发来源与 source unit

| 来源 | 次数/状态 | source unit 示例 |
|---|---:|---|
| `spawn_agent` | 61 次调用尝试；实际 start 计入 50 个活动中的一部分 | S1 的 research/spec/grill/review；S2 的 `t1_investigation`、`t2_investigation`、`t3_investigation` 与实现单元；S3 的 `t6_implementer`、scope-authority、fixer、verifier；S4/S5 的 `t7_api_contracts` |
| `followup_task` | 52 次 | 重试 T2/T3、补 T3 accounting-year/status guard、T6 fixer/verifier、T7 retry 等 |
| `luna-worker` | 7 次 spawn 尝试 | S1 研究/方案审查；S4/S5 的 bounded implementation/review 单元 |
| `call-grok` | 可识别实际启动 3 次 | S4 `grok-datev-s6-blind`、S4 `grok-datev-p5-finding-closure`、S5 `grok-t4-f3`；S4 首次结果为 0 bytes，S5 T4-F3 结果被主 session 集成 |
| Codex subagent 原生工具 | 未观察到单独名为 `codex subagent` 的工具 | rollout 中使用的是通用 `spawn_agent` / `followup_task`，不能把所有 generic agent 都改称某种具体 worker |
| Codex app thread plumbing | `create_thread` 7、`send_message_to_thread` 6、`wait_threads` 8，另有 list/read/title 调用 | 这些是线程/续接控制面；记录没有把它们明确标成独立实现 worker，故不重复计入上面的 50 个实际 start |

### 可确认的并行重叠

| 时间 | 重叠事实 |
|---|---|
| S2 19:42:34.112、19:42:46.548、19:42:58.735 | T1、T2、T3 三个 investigation 在约 25 秒内连续启动，返回时间跨越，形成三路并行调查 |
| S2 20:02:24.241、20:02:43.623、20:02:56.223 | T1、T2、T3 三个 implementer 也并行启动 |
| S1 14:47:59、14:49:01、14:51:57 | 三个 grill/review 单元重叠 |
| S4/S5 | T7 主线仍按依赖串行；背景 `call-grok` 有启动但至少一项没有可用返回，不能算有效并行实现 |

### Prompt 与集成成本

| 指标 | 结果 |
|---|---:|
| 仅 `spawn_agent` prompt | 61 个；平均约 2,854 字符，中位数约 2,744，范围约 760–8,140 |
| `spawn_agent + followup_task` dispatch message | 113 个；平均约 1,956 字符，中位数约 1,164，范围约 312–8,140 |
| 可直接测量的合同复述比例 | 不可测；prompt 正文主要为加密 `gAAAA...`，可读证据下界只能写成 0/113，不代表真实复述为零 |
| 主 session 集成/返工 | 至少 4 个明显波次：S2 T2/T3 retry 与 guard 修复；S3 T6 INCOMPLETE → authority/fixer/verifier；S4 T7 blocked → T3/T4/T6 seam 修复；S5 T4-F3 worker 结果 → T7 retry |

### 原文佐证

T6 的第一次 worker 结果不是成功交付，主线继续调度了范围 authority 和 fixer：

> `INCOMPLETE`：缺少 authority-owned、scope-keyed 的 public seam；随后才派发 scope-authority、fixer、verifier。（S3，2026-08-12T23:06–23:58）

T7 也不是一个 worker 返回后直接结束，而是发现前置 seam 不足后重新回修：

> `T7 cannot faithfully implement frozen API`，原因包括 durable idempotency、optimistic binding 和 safe read projection 缺口。（S4/S5，2026-08-13T04:39–08:51）

## Q7 这套机制真正产生价值的地方

### 结论

机制的真实价值不在于让代码更快生成，而在于把“可以继续做什么”和“什么还不能声称完成”变成可审计的状态。至少有四类错误被挡住：下游 Task 的过早启动、把局部测试当成 Ticket acceptance、把 worker 的 INCOMPLETE 当 DONE、以及跨 session 续接时丢失剩余风险。与此同时，状态机的 projection 维护确实带来成本；价值和摩擦是同时存在的。

### 证据表

| 价值点 | 实际证据 | 如果没有机制，最可能的失控 |
|---|---|---|
| DAG 顺序挡住过早启动 | S2 validate 只给 `readyTasks [T1,T2,T3]`；S3 只给 `[T6]`；S4 只给 `[T7]`；S5 终点只给 `[T8]` | T6/T7/T8/T9 可能被同时声称可做，导致 API/Web/scenario 在公共 seam 未冻结时并行漂移 |
| Task AC 阻止假完成 | T6 首次 worker 只有局部 64-test/typecheck/lint 证据却返回 INCOMPLETE；T7 发现 service/facade 缺 idempotency 和 read projection 后被 BLOCKED | “测试绿了”会被误写成 Task DONE，尤其会把 T7 的 DTO 自己填字段当成真实 publication contract |
| Ticket 轴阻止整体假完成 | S5 明确是 7/9 Task DONE、0/5 Ticket SATISFIED、Gate open | 可能把纵切未满足的 DMI-01..05 误报告为 package 已交付 |
| 跨 session 状态恢复成功 | S2 读 `initial-ER-003` 进入 T1–T3；S3 读 `initial-ER-011` 只启动 T6；S4 读 `initial-ER-015` 进入 T7 readiness；S5 读 `initial-ER-019` 处理 T7 blocked 并写 `initial-ER-022` | 新 session 需要重新推断当前 head、证据、owner、下一动作，极易重复实现或越过阻塞 |
| ER/Handoff 提供不可由代码推导的信息 | 记录了 source unit、protected write-set、forbidden package、worker 返回是 INCOMPLETE 的原因、已跑测试、未证明的真实 PG/HTTP/Web/T9 | 代码树只能告诉“有哪些文件”，不能告诉“本次尝试为什么不接受、下次从哪里继续” |

### 原文佐证

DAG runtime 在 S2 的可执行判断不是泛泛的“按顺序做”，而是给出了唯一 ready 集：

> `readyTasks ["T1","T2","T3"]`，`readyTickets ["DMI-01","DMI-05"]`。（S2，2026-08-12T19:40:20.473Z）

T6 的局部证据没有被当成整体完成：

> `focused Vitest 9 files / 64 tests、API typecheck 与 changed-files ESLint 均 exit 0。`
> 紧接着说明这不证明真实 PostgreSQL、T7 contract、T9 scenario 或 Ticket acceptance。（S3，2026-08-12T23:58:53.596Z）

跨 session 的续接锚点最终仍保留未完成范围：

> `initial-ER-022` 把下一动作交给 T8，同时保留真实 DB、HTTP、Web、T9 和 Ticket acceptance 为未完成证据。（S5，2026-08-13T09:09 左右）

## Q8 跨 session 恢复成本

### 结论

“前 30 个事件”本身会低估恢复税，因为 S2–S4 的前 30 个事件主要属于短暂的 anchor/continuation 子段；更有意义的指标是从 session 开始到第一次真正的 bounded Task dispatch。按“native + custom function call，含首个实际 dispatch”计数，S2、S3、S4、S5 分别花了 16、25、31、25 次调用才开始真正干活；S1 首先花 1 次调用读 skill 后开始研究派发，但它是规划 session，不是实现续接。

### 数据表

| Session | 前 30 事件中的工具调用 | 前 30 事件读到的主要文件/记录 | 首次真实 Task dispatch | 从开始到该 dispatch 的调用数 |
|---|---:|---|---|---:|
| S1 | 4 | `datev-tax-accounting/SKILL.md`、talk-to-boss、用户给出的 idea 路径检查 | 研究/审查 bounded work；随后才定位主 workspace 的 idea 文档 | 1（若把首个 research spawn 算作 dispatch，则为 2） |
| S2 | 1 | `initial-ER-003`/anchor、current-state、progress、composition-contract、plan、DAG、T1/T2/T3/Ticket 文档、investigate/dispatch/Task template；也搜索了错误的旧 skill 路径 | T1/T2/T3 investigation | 16 |
| S3 | 1 | `initial-ER-011`、current-state/progress、T6/T7/T8/T9、T6 handoff、composition/dispatch/template、authority 规范/代码、测试治理 | T6 implementer | 25 |
| S4 | 1 | `initial-ER-015`、T6 handoff、T7 contract/spec/plan/DAG、progressive evidence、repo QA/authority/T7 module | T7 readiness/implementer | 31 |
| S5 | 3 | `initial-ER-019`、T3/T4/T6/T7 handoff、current-state/progress、contract/spec/plan/DAG、repo QA/RBAC/domain/file-security/testing | T7 first bounded retry | 25 |

这些数字包含“恢复正确所必需”的读取，不应全部视为浪费：ER、DAG 和 current-state 让后续 session 没有越过阻塞；但旧路径搜索、重复读取 skill/合同和 projection 修复构成了真实恢复税。S4 的 31 次是五段中最高，原因是 T7 的公共契约要回头重新核对 T3/T4/T6 的前置 seam。

### 原文佐证

S2 的续接逻辑是先验证 anchor，再决定派发范围：

> `initial-ER-003` anchor PASS；读取 current state 后只将 T1/T2/T3 作为首批 bounded work。（S2，2026-08-12T19:38–19:42）

S4 的恢复并没有直接把 T7 当成 ready，而是保留了前置修复：

> `initial-ER-015` 后先进入 T7 readiness，随后因 T3/T4/T6 seam 和 projection 证据不足而转入 blocked/revalidation。（S4，2026-08-13T04:27–05:39）

## 与设计假设的对照

1. **反直觉：五个 session、约 44 小时的日志跨度，并没有产生一次完整业务纵切。** 终点是 7/9 Task DONE，而不是 5/5 Ticket 满足；T8/T9 和真实 DB/HTTP/Web 仍未执行。

2. **反直觉：DAG 的串行边很长，但 T6→T7 的真实代码依赖很窄。** T7 主要需要 T6 的 public projection/application seam；T6 的事务、私有表和大部分内部实现并不是 T7 的直接输入。串行化的主要价值是冻结契约和阻止假启动，而不是文件级耦合。

3. **预期中的并行只发生在 T1/T2/T3。** 这些 Task 的 investigation 和 implementation 都明确三路重叠；T6/T7 的关键阶段反而因 seam 不足、revalidation 和 acceptance 证据要求而串行。

4. **恢复不是“读一份 handoff 就继续”。** 后续 session 到第一次实际 dispatch 仍消耗 16–31 次函数调用，并多次搜索旧插件版本和错误的 canonical 目录；handoff 降低了重新推理成本，但没有消除恢复税。

5. **状态机既是安全网，也是主要摩擦源。** `NEEDS-REVALIDATION`、`BLOCKED`、ready 集和 Gate 防止了假完成；但 progress projection mismatch、DAG runtime projection mismatch 和 dependency 未释放又反复消耗调用。

6. **测试数量没有直接等价于 Task 完成。** T6 有 9 files/64 tests 的局部绿证据仍被标为 INCOMPLETE；T7 也在已有前置代码可用时因 idempotency/read projection 不足而被阻塞。

7. **派发 prompt 的“合同复述比例”无法从 rollout 直接得出。** 记录保留的是加密 prompt，不是可读正文；可以量化平均长度约 1,956–2,854 字符，却不能把不可见内容伪精确地拆成方法论和业务指令。

8. **纵向 Ticket 轴比横向 Task 轴更保守。** 7 个 Task DONE 仍对应 0 个 Ticket SATISFIED，说明 package 的设计假设确实把“局部执行完成”和“用户旅程验收完成”分开了；在本次执行中，这个区分产生了实际约束，而不是文档装饰。
