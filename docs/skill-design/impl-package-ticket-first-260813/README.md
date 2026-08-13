# Impl-Package Ticket-first 重构

- 日期：2026-08-13
- 状态：方案与独立文档审阅已收敛；尚未实施
- 性质：**本目录是后续优化的权威设计文档。**实施与再讨论以本页为准；旧设计只作背景材料
- 适用范围：Impl-Package 的 Composition、Ticket、执行调度、状态、Execution Record 与会话交接

## 修订 checkpoint

| Checkpoint | 含义 |
| --- | --- |
| Git commit `9870d77` | 反方审阅与讨论修正前的原始方案、证据和复现脚本 |
| 当前工作树 | 收敛后的实施候选方案；独立 reviewer 首轮发现已修订，finding closure 为 5/5 PASS |

需要查看原始归因、旧顺序或 116k 的旧表述时，直接比较 `9870d77`，不在现行方案里保留两套竞争规则。

## 本目录

| 文件 | 内容 |
| --- | --- |
| 本页 | 目标模型、落地顺序、状态归属、迁移与验收 |
| [evidence/measurements.md](evidence/measurements.md) | 实测数字与口径 |
| [evidence/codex-session-analysis.md](evidence/codex-session-analysis.md) | 5 个 rollout 的会话分析 |
| [evidence/mattpocock-philosophy.md](evidence/mattpocock-philosophy.md) | Matt Pocock 公开理念调研，区分原话与推断 |
| [scripts/](scripts/) | 复现测量的脚本；本轮修订不重跑测量 |

背景材料：[原始设计文档](../impl-package-ticket-first-execution-design-260813.md)（不是现行方案）。

相邻方案：`docs/skill-design/unified-subagent-worker-strategy-refactor-plan-260813.md`（其 source unit 需要按本文的 Ticket-first 模型重新对齐）。

## 1. 目标模型

Impl-Package 收敛为以下结构：

1. **Ticket 是唯一持久实施与验收单元。**不再创建 Task 或 `dag.md`；Ticket 上的 typed dependencies 是唯一包内依赖图。
2. **跨 session 续接只认文档化 checkpoint。**Ticket 跨 session 沿用现有默认；交接前写清下一步与恢复证据，compact 只作意外耗尽后的兜底，不是正常交接方式。
3. **Ticket 只有最终 acceptance state。**早期证据、active checkpoint、session claim 都不能变成 Ticket 的中间状态。
4. **首发保持严格 barrier。**现行 `readyTickets` 语义继续生效；seam 提前派发是后续可选调度优化，不是 Ticket-first 的前置条件。
5. **package state 与协调 state 分层单写。**package task session 主线程单写该包 `state.json`；未来 broker/controller 单写跨 task session 的协调 ledger；worker 只返回结构化证据。
6. **ER 保留 judgment 与历史。**active checkpoint 和 evidence index 进入 `state.json`，但只有在 index、validation 和恢复路径同步改造后，才能减少恢复时对 ER 的解析。
7. **旧包显式迁移。**现存包数量少，不为 3.4/Task 格式维护长期双读运行时；提供一次性迁移 prompt/runbook，逐包验证后切换。

Ticket-first 的目标是减少重复执行对象、让证据直接归属验收单元，并降低过程文档与恢复成本；它不承诺消除所有串行和返工。

## 2. 实施顺序

### 阶段 A：锁定 Ticket-only 严格模式

先完成合同与 fixture，不迁移活动包：

- Composition 收敛为 Ticket-only / Plan-direct。
- 删除新建 Task、Task DAG 和 Task Handoff 的默认路径。
- 保留三型 Ticket 边与严格 `readyTickets`。
- 按 §3.2 定义 early evidence、remaining evidence 与不可延后安全属性。
- 定义 Task 字段的吸收去向、唯一 writer 和新 `state.json` schema。
- 建立旧格式→新格式迁移 fixture 与失败回退路径。

阶段 A 的重点是证明新模型完整，不是提前获得并行收益。

### 阶段 B：实现状态/恢复并迁移旧包

- 实现 Ticket evidence index、active checkpoint 和投影收敛。
- 同步修改 attempt index、ER validation 与恢复调用点。
- 使用迁移 prompt 处理活动 3.4/Task package；验证通过后才让新插件只读新格式。
- 冻结包保持只读；恢复执行前再迁移。

阶段 A/B 完成后即可长期使用 Ticket-only + 严格 barrier，不需要等待 §3.3。

### 阶段 C：可选 seam admission

只有当最小持久事实、revoke、revalidation 和恢复 fixture 都通过后，才允许调度 Agent 提前派发依赖已稳定 seam 的下游实施。用 strict barrier 做对照，收益不足或返工增加就不启用。

### 阶段 D：外层 broker/controller

后续单独建设 user-facing broker/controller，负责监控 task session、在授权 envelope 内调度、维护协调 ledger，并统一实现上下文 warning 与交接。它不是本轮 Ticket-first 首发的阻塞项。

## 3. 运行合同

### 3.1 Ticket、session 与 acceptance

- Ticket 状态词汇收敛为 `PENDING | BLOCKED | NEEDS-REVALIDATION | SATISFIED | RETIRED`；不增加 `READY`、`RUNNING` 或 per-AC 状态。
- 跨 session 前必须写 active checkpoint；需要长期保留的判断同时写入 ER judgment。下一 session 从文档状态恢复，不把 compact 摘要当权威输入。
- 当前单 task session 不需要持久 claim。未来多个 task session 并存时，assignment/claim 进入 broker ledger，不进入 Ticket 或 package acceptance state。
- Ticket 完成证据必须指向测试、commit、DB diff、运行日志等真实产物，不能指回流程 handoff 本身。

最小失效与恢复语义为：

1. 合同或实现变化只使**已有证据实际受影响**的 Ticket 进入 `NEEDS-REVALIDATION`，同时在受影响 evidence record 上记录 `invalidatedBy`；未受影响证据保留。
2. `NEEDS-REVALIDATION` 与 `BLOCKED` 都不释放依赖，也不进入 `readyTickets`。完成 impact triage 并写出 revalidation plan 后，仍需执行的 Ticket 以 CAS 回到 `PENDING`；解除 blocker 的 Ticket 同样回到 `PENDING`。
3. Ticket 只有在当前 revision/environment 下重新覆盖全部 required claims 后才能回到 `SATISFIED`。
4. `RETIRED` 合并原 `WAIVED` / `SUPERSEDED`，是 terminal、dependency-releasing 状态，但必须由 owner 决定并写 `disposition: waived | superseded`。`waived` 必须引用批准后的 scope 变更；`superseded` 必须指向 successor Ticket/attempt，且所有入边已改指 successor 或由 owner 明确解除。普通合同变化不得自动把 Ticket 设为 `RETIRED`。

这些是 Ticket 级状态转换，不是 per-AC 状态机。

上游 `to-tickets` 的“一张票在一个 fresh context 内做完”继续作为 planning sizing 启发式，但不是本地运行不变量。需要续接时统一执行 active checkpoint 合同；这是既有运行方式，不作为 Ticket-first 的新增主张。

### 3.2 AC：证据时机 × 安全不变量

不再把 AC 划为 `core` 与 `hardening`，也不改成三个顺序组。使用两个正交维度：

1. **证据时机**：early falsification evidence 与 remaining completion evidence。
2. **不可延后属性**：tenant、RBAC、privacy、幂等、数据完整性等 safety invariants 从第一条可执行路径起必须成立。

早期路径可以缩小业务范围，例如只覆盖一种受支持格式、单条入口或单个已授权主体；不得通过关闭授权、弱化租户隔离或跳过一致性约束得到“早绿”。原则是**纵切可以窄，不能薄**。

早期证据只进入 evidence index。Ticket 仍需全部 acceptance 满足才进入最终状态，不新增 per-AC 状态机。

对 DMI-01 的 fixture，应先取得“受支持 M1/M2 输入确定性生成 snapshot 并可读回”的证据，同时保持该窄范围内所需的 uploadToken、权限和数据读取安全属性。具体早期行为由 Spec/Plan 明示，不从固定“加固项”清单推断。

### 3.3 Ticket 边与可选 seam admission

保留三型 Ticket 边：

- `implementation`：阻挡下游正常实施；
- `acceptance`：允许实施，但阻挡最终验收；
- `release`：允许实施与验收，但阻挡发布。

首发阶段严格按这些边计算 `readyTickets`。

后续启用 seam admission 时，调度 Agent 根据当前代码、测试、接口稳定度、共享资源和返工风险启发式判断。系统只提供“允许并记录这个判断”的机制，不维护稳定度评分或穷举规则表。

`state.json` 只保存已作出的最小 admission 事实：上游、下游、允许使用的 seam scope、admit/revoke 结果与证据引用。硬边界是：

- checkpoint 自身不授权派发；
- admission 不改变上游 Ticket，也不释放下游 acceptance/release；
- 上游 seam 改变时必须 revoke，并把受影响证据送入 revalidation；
- `readyTickets` 继续表示严格 ready，提前派发不能伪装成 canonical ready；
- ER 可以解释判断，但不得与 `state.json` 维护竞争事实。

共享 migration、generated client、授权表、DB runner 或测试数据可能使窄接口也不可并行。这类约束写成真实 Ticket 边或 Plan 的单写资源约束，由 Agent 纳入判断。

### 3.4 状态权威与双层单写

Package 层：

- 每个 package 的 task session 主线程是 `state.json` 唯一写入者；
- `state.json` 保存 Ticket acceptance、evidence index、active checkpoint，以及阶段 C 启用后的包内 seam admission；
- `progress.md` 是恢复视图，ticket 文档是稳定合同，不再内嵌 runtime acceptance；
- worker/subagent 只返回结构化证据，不直接更新 package state。

未来 broker 层：

- broker/controller 面向用户负责监控、路由、有限授权和跨 task session 协调；
- broker 单写协调 ledger，记录用户决定、task session claim、跨包 seam、阻塞和交接；
- broker 不直接代写各包 `state.json`。需要改变包内事实时，向相应 task session 发结构化事件，由包的唯一 writer 落盘；
- broker 的部分授权不得超出 owner 预先给定的 envelope。

这与 `thread-harness` 的结构相同，但只复用“双层单写、结构化事件、自交接”三个概念，不照搬其完整 registry/seam 机器。

### 3.5 Evidence index、checkpoint 与 ER

`state.json` 增加两个紧凑索引，不引入 per-AC 状态：

- **evidence index**：按 Ticket 与 stable claim ID 指向真实产物、revision、验证环境与结论；
- **active checkpoint**：按 attempt/Ticket 保存当前 `next` 与恢复证据，覆盖写当前值。

claim ID 来自 Ticket 合同中显式编号的 AC 和安全断言，例如 `AC-1`、`INV-tenant-isolation`，不能由运行期 Agent 临时改名。每条 evidence record 至少包含 `artifact`、`revision`、`environment`、`conclusion`，可选 `invalidatedBy`。它表达证据映射与有效性，不保存 claim 的 `PENDING/DONE` 状态。

`SATISFIED` validator 必须机械检查：Ticket 声明的全部 required claim ID 均至少有一条适用于当前 revision/environment 的 supporting evidence；不存在未处置的 contradictory evidence；所有 implementation/acceptance dependency 已释放。缺 claim、只有失效证据或只有自由文本总括，都拒绝进入 `SATISFIED`。

active checkpoint 覆盖写是有意丢弃已过时的恢复指令。Git **只保留已经提交的版本**，不能假定每次覆盖都有历史；任何需要长期保留的决策、失败学习或审计事实必须先写入 ER judgment/evidence index。ER 不再承担 active checkpoint，但继续保存判断、attempt history 与审计上下文。

不能只把 checkpoint 移进 `state.json` 就声称 ER 退出恢复路径。当前 `_parse_execution_record` 仍被 `_ensure_execution_record`、`_attempt_history`、`_validate_projections`、ER 渲染与追加路径调用。实施时必须同时：

1. 固定 state/evidence index 与 ER judgment 的事实边界。
2. 修改 attempt history/index，避免恢复时为每个 attempt 重扫完整 ER。
3. 修改 projection validation，使其验证索引与 ER 的关系。
4. 用同一 fixture 覆盖 active checkpoint、未完成 Ticket、历史 attempt 与 projection mismatch。

这些改动验证前，ER 仍在恢复/validation 路径。

### 3.6 Task 内容的吸收去向

| 原 Task 内容 | 新位置 |
| --- | --- |
| execution boundary | Ticket 的建设内容 |
| contributes-to tickets | 删除；迁移时转为 evidence 映射 |
| `READY` / `RUNNING` | 不进 Ticket；未来 assignment 进 broker ledger |
| `DONE` evidence | Ticket evidence index，指向真实产物 |
| section-level contract references | 一次派发 brief |
| known seam / risk | 合同部分进 Ticket AC/Spec；执行判断进 ER judgment |
| primary ownership / 单写资源 | Plan 的执行策略表 |

Task Handoff 的默认路径随 Task 删除。跨 session checkpoint/handoff 继续保留，两者目的不同。

### 3.7 旧包迁移

不维护长期旧格式双读器。发布新格式前提供一次性迁移 prompt/runbook，由活动 package 的 task session 在 owner 授权下执行。迁移在独占的临时 worktree/branch 上运行，暂停该 package 的其他 writer，并记录 pre-migration Git anchor：

1. 读取旧 `state.json`、Ticket、Task、ER 和 active checkpoint。
2. 从 Task handoff/ER **提取并验证其指向的真实产物**，再映射到 Ticket claim；`task-handoffs/*` 本身不得成为 acceptance proof。只有 handoff 而没有可验证产物时，迁移停止并请求人工 evidence mapping。多 Ticket 贡献不得静默丢失。
3. 保留原 ER 与 attempt history，不把迁移写成新的业务事实。
4. 在临时 worktree 生成完整 Ticket-only candidate，验证 claim coverage、ready 集、恢复入口、未完成 acceptance、历史 attempt 与 projection；不得逐文件激活半成品。
5. 全部验证通过后生成单一 migration commit，作为格式切换点。新插件和新 controller 只从该 commit 启动；切换前失败直接放弃临时 worktree，原 package 仍以 pre-migration anchor 为权威。

fixture 必须模拟 candidate 生成前、生成中、validation 时和切换后的中断，并断言新 evidence index 不把 `task-handoffs/` 当直接证据。活动 DATEV package 先作为迁移 fixture；冻结 package 只在恢复执行前迁移。

### 3.8 会话交接与 116k

当前算术示例为：

```
150,000 − 20 × 1,720 = 115,600 ≈ 116k
```

116k 只记录为当前模型/harness 的初始 warning estimate：150k 是启发式 policy anchor，20 次收尾请求没有观测分布，p75 单请求增量也不是累计预算上界。不得称其为推导出的安全上限、按窗口百分比推广或声称自动适配模型。

当前主 task session 没有可靠可见的自动 token 监控，本轮只要求 checkpoint/handoff 路径可用。后续 broker 再按 model+harness 和 closure-phase 分布校准 warning，并把“停止新探索、减少大读取、准备交接”作为 Agent 默认启发式，不做硬禁令。

`skills/handoff-to-new-session/SKILL.md` 的 anchor/continuation 与“只指不抄”可复用；通过 downstream protocol extension 支持同 Ticket 的滚动交接。

### 3.9 变更形状与 wide refactor

返工范围由**变更形状 × Ticket 边界**共同决定。纵切 Ticket 可以收敛同形的纵向变更，不能消除横切合同修订。

S5→S6 同时改变 uploadToken producer/consumer、idempotency、PublicationAttempt authority/CAS 与 API walkthrough，是横切五张 Ticket 的合同修订；新模型也必须让受影响 Ticket revalidation。S4→S5 的 SKR/currency/accountLength 更接近 source-identity 形状，适合作为“边界可能收敛影响面”的 fixture。

改列名、共享符号换类型、给既有表增加租户维度等 wide refactor 走 expand–contract：先 expand，再按 blast radius 分批迁移，最后 contract，不强行包装成单张纵切 Ticket。

## 4. 五项既有机制如何保留

| 机制 | Ticket-first 合同 | 验证方式 |
| --- | --- | --- |
| ready 集门禁 | 首发严格 `readyTickets`；可选 admission 不改 canonical ready | blocker fixture |
| 局部证据 ≠ 完成 | evidence index 只索引证据，Ticket 仍需最终 acceptance | 局部证据不得触发 acceptance/release |
| Ticket 轴独立 | claim、checkpoint、acceptance 分属协调、恢复、验收 | 跨 session 状态 fixture |
| ER 跨 session judgment | ER 保留判断/历史；checkpoint 迁移与 validation 同步 | 多次恢复与历史 attempt fixture |
| 三型 Ticket 边 | implementation、acceptance、release 均保留 | 每种边的 ready/acceptance/release fixture |

完成的无 Task package 与 DATEV 只作为 evidence 中的分析案例，不进入规范性方法论，也不用于承诺速度收益。

## 5. 设计依据与证据边界

完整数字和口径见 [evidence/measurements.md](evidence/measurements.md)。现有材料用于选择设计，不替代实施 fixture。

| 观察 | 对设计的意义 | 不能推出 |
| --- | --- | --- |
| DATEV 为 Task 7/9 `DONE`、Ticket 0/5 `SATISFIED`，Ticket×Task 为多对多 | 去掉重复执行轴并让证据直接索引 Ticket 值得验证 | Task 是唯一原因；Ticket 已在运行时证明为合格纵切 |
| DMI-01 无 Ticket blocker，但宽 AC 的贡献链到 T7 | 需要区分 early evidence 与 remaining evidence | 安全 AC 可后移；AC 分期必然让第一 session 完成 Ticket |
| P5 存在 T3→T4→T6→T7→T8→T9 返工链；T6→T7 依赖窄 seam | seam admission 值得作为后续对照实验 | 后半段串行全由 barrier 导致；提前派发一定减少总耗时 |
| S5→S6 是横切 API 合同修订，影响五张 Ticket | affected scope 必须按 change shape 计算 | Ticket-first 总能把返工收敛为一张票 |
| 完成的 ticket-only 案例通过 gate | 现行实现已有可复用分支 | 它与 DATEV 构成性能或因果对照 |
| 36–48% 请求超过 150k，压缩约在 226k | 需要在退化前主动 checkpoint/handoff | 150k 是本地测得的质量边界；116k 是通用阈值 |

## 6. 验收标准

### 阶段 A/B：首发正确性

1. Ticket-only fixture 在严格 barrier 下生成正确 `readyTickets`，未释放 blocker 不会被绕过。
2. stable claim ID 能覆盖全部 AC/安全断言；只有当前 revision/environment 的 supporting evidence 完整、无未处置 contradiction 时才允许 `SATISFIED`。
3. 早期窄路径维持声明的 tenant、RBAC、privacy、幂等和数据完整性不变量。
4. S4→S5 与 S5→S6 两种 change shape 产生与实际 affected scope 一致的 revalidation，不硬编码“一次只失效一票”。
5. §4 五项机制逐项通过 fixture，不以案例类比替代验证。
6. 活动 3.4/Task package 在临时 worktree 中显式迁移后，ER/attempt history、active checkpoint、未完成 Ticket 与真实 evidence 均可恢复；各中断点不改变 pre-migration authority，handoff 不被直接当作 acceptance proof。
7. `NEEDS-REVALIDATION → PENDING → SATISFIED` 只重验 affected claims，且全程保持依赖不释放；`BLOCKED` 不被隐式改写，`RETIRED` 必须有 owner evidence、合法 disposition，并在 `superseded` 时指向 successor。
8. `_parse_execution_record` 是否退出恢复路径由调用点与恢复测试证明，不能从 schema 设计推断。
9. package state、broker ledger 与 worker 回报遵守唯一 writer 边界。

### 阶段 C：调度收益

10. seam admission 由 package state 唯一记录；ER 不产生竞争事实。
11. revoke 只触发 affected evidence revalidation，不改变无关 Ticket。
12. 与 strict barrier 对照，提前派发的等待收益大于新增返工；否则保持关闭。

### 诊断指标

13. 继续记录读文档 : 实现动作、首次真实 dispatch 调用数、150k 以上请求占比和 package 纸面量，但只比较同 fixture 前后。
14. ER `subject: ticket:*` 只作 logging/ownership 诊断，不是 Ticket-first 成功的充分条件。
15. 116k 只作为未来 broker 的初始 policy estimate；有 model+harness 与 closure-phase 数据后再定 warning。

## 7. 影响面

| Surface | 变化 |
| --- | --- |
| `references/impl-package-composition-contract.md` | Composition 收敛为 Ticket-only / Plan-direct；三型边保留；严格 barrier 为默认 |
| `references/impl-package-current-state.md` | 删除 Task 轴；定义 evidence index、active checkpoint 与唯一 writer |
| `skills/to-tickets/` | 增加证据时机/安全不变量提示与 wide-refactor 例外；fresh-context 仅作 sizing heuristic |
| `skills/impl-planning/` | 删除 Task DAG 组合；增加单写资源表；保留安全 backstop |
| `skills/create-task-dag/` | 从新包默认流程退役；旧包迁移前只读 |
| `skills/dev-with-track/` | 以 Ticket 为恢复/推进单位；首发严格 barrier；seam admission 为后续可选能力 |
| `skills/handoff-to-new-session/` | 支持同 Ticket 多次滚动交接 |
| `skills/thread-harness/` 或后续 broker | 复用双层单写、结构化事件与自交接，不照搬完整机器 |
| `scripts/impl_package_state.py` | 删除 Task 轴；增加 evidence/checkpoint 索引；同步修改 attempt index、validation 和恢复调用点 |
| migration prompt / fixture | 在临时 worktree 逐包迁移 3.4/Task package；以单一 migration commit 激活，覆盖中断回退、真实 evidence 提取与历史保留 |
| templates / evals / tests | 覆盖严格 ready、两维 AC、三型边、change shape、恢复与可选 seam admission |

## 8. 暂不在本轮解决

- **跨 package acceptance 边。**当前仍以散文表达，`validate` 与 `progress.md` 无法检查；未来 broker ledger 可能承载路由，但 package contract 如何引用尚未设计。
- **跨 attempt 交付全貌。**当前 `state.json` 只显示 active attempt；evidence index 是否跨 attempt 聚合仍需单独决定，迁移不得擅自抹平历史。
- **自动上下文 warning。**留给 broker/controller 阶段，不伪装成当前主 task session 已具备的能力。
- **Spec 完整性 gate 分期。**可另行研究，但任何首条可执行路径所需的 permission、tenant boundary、privacy、concurrency、recovery 与数据完整性合同仍须先闭合。

这次重构的主要风险不是对象删除本身，而是迁移正确性、跨 session 恢复、唯一 writer 与安全不变量。实施必须按 A/B/C/D 分阶段验收，不能把上游阶段通过写成整个重构完成。
