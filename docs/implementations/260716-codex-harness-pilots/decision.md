# Codex Harness Pilots 决策研究

状态（Status）：Decision Gate Passed
创建时间（Created）：2026-07-16
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D2
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：Owner 于 2026-07-18 批准将 Codex Harness runtime policy、任务上下文隔离、自主委派边界、thread lease、资源账本与处置生命周期推进为探索性 POC implementation，并要求直接采用当前 Impl-Package schema 重写相关引用。
主题 slug（Topic slug）：codex-harness-pilots
任务包 ID（Package ID）：260716-codex-harness-pilots
规范任务包路径（Canonical package）：`docs/implementations/260716-codex-harness-pilots/`

本文是本任务包当前决策选择与理由的事实源。完整调研、App Server Sources Index 与本地 POC 证据直接复用 [Codex Harness POC 设计资产](../../../skills/codex-harness/assets/codex-harness-poc-design.md)，本文不复制其研究正文；行为、失败恢复和验收语义由 [spec.md](spec.md) 独占。

## 1. 目标落点

- 预期结果：在保留父 agent 自主实现和 native subagent 编排的前提下，让 Harness 读取 canonical runtime policy，并对跨任务上下文、同一 thread 单写者、资源证据、owner decision 路由和 terminal disposition 提供可审计的 POC 级运行约束。
- 受影响的系统边界：`codex-harness` Skill、canonical runtime policy JSON/Schema、父 profile、App Server/package runner、共享 runtime ledger、Parent Result validator、隔离执行与 cleanup seam；Codex 原生 child orchestration 保持为父 agent 的内部实现。
- 合同交接点：本 implementation 将已选方向交给 [spec.md](spec.md) 定义 D2/S2 行为合同和新增 lifecycle acceptance，再由当前 plan 安排实现与验证；任务包直接采用 Impl-Package 3.2，不保留旧 schema 兼容层。

## 2. 需求 / 结果

- 聚焦需求：把已确认的 runtime policy 设计从 design baseline 推进到一个可验证的 runtime-enforced POC seam，同时保持父-only、自主委派和 fail-closed evidence 合同。
- 用户或系统结果：不同任务不会因复用命名 worker 而继承旧上下文；同一 work package 的 continuation 具备单写者和可追踪资源证据；父 agent 在边界内可以自主委派，超出范围的请求会进入 Harness/owner decision 路由。
- 成功信号：新增生命周期 acceptance 均有同 revision、同环境的直接 evidence，policy 的 maturity 只有在 loader、enforcement、failure path 和 deterministic validation 都闭合后才可升为 `runtime_enforced`；旧 10 个 AC 不因新增 policy 而被无证据地重标通过。

## 3. 知识来源 / 当前状态

- 已检查的权威来源：现有 Codex Harness POC 设计资产及其官方 Sources Index；`skills/codex-harness/SKILL.md`；`.codex/harness/parent.toml`；当前两个 pilot runner；Impl-Package composition、req-align、planning、gate 与 completion-claim 契约；仓库 `AGENTS.md`。
- 聚焦代码 / 测试事实：App Server thread/turn、native child thread 可追踪、Parent Result parser、retry ledger 和隔离写入 pilot 已在 `codex-cli 0.144.4` 上有 POC evidence；本 patch 已形成 policy loader、package/App Server resource ledger、resume lease、decision routing 与 Impl-Package 3.2 adapter 的最小 seam，但尚未在所有入口和失败路径闭合 `runtime_enforced` 所需证据。
- 预期但缺失的知识：仓库没有可复用的 production lifecycle controller；当前 D2/S2/P1 已按 Impl-Package 3.2 直接注册并完成 working-tree revalidate，committed validation 与 terminal gate 仍待同一发布提交后完成。
- 冲突或 drift：发现 package 历史修订与 Spec 对不存在的 `codex-harness-poc-decision.md` 有旧引用；本 patch 将其收敛到当前 `codex-harness-poc-design.md`，并保持 D/S/P marker 与 sidecar 由 Impl-Package CLI 维护。

## 4. 约束 / 非目标

- 约束：Harness 只控制父 thread/turn、父 profile、work package、canonical runtime policy、运行边界和父结果 acceptance；独立 validator 而非父自述决定通过。父 agent 在边界内自主决定实现、委派和汇总方式。
- 非目标：不实现外部 child scheduler；不绑定或验收 child role、数量、模型、prompt、拓扑；不把 worktree 隔离误报为消除物理冲突；本 patch 不承诺生产级多版本兼容、MCP allowlist、token budget 或长驻 server 的完整 orphan cleanup。
- 安全或外部 mutation 边界：Pilot 默认 read-only；写入验证只能在明确隔离的临时 repo/worktree 和 allowlisted path 中执行，不得污染当前主工作树或产生未授权外部副作用。能力被 policy/sandbox 阻断时不自动提升权限；scope、authority、不可逆外部副作用或验收歧义交给 owner。

## 5. 选项 / 权衡

| 选项 | 收益 | 成本 / 风险 | 与仓库的契合度 |
| --- | --- | --- | --- |
| Harness 直接调度每个 child | 控制粒度细 | 复制 Codex scheduler、强耦合内部协议、扩大生命周期故障面 | 不采用 |
| Harness 只控制父 agent | 边界稳定，允许 Codex 自主进化，验收面清晰 | 需要更强的父结果 schema 与外部 validator | 采用 |
| `codex exec --json` 为主控制面 | 实现简单 | durable thread、interrupt/resume 和 provenance 不足 | 只保留对照 |
| App Server v2 为主控制面 | thread/turn 生命周期、事件与恢复能力完整 | 需要 capability probe、超时和兼容降级 | 采用 |
| 先按生产规格扩展全部权限/预算控制 | 一次覆盖完整 | 探索期成本高且会掩盖核心闭环 | 不采用；风险出现后再扩展 |
| 每个 child 操作都由 Harness 审批 | 过程控制细 | 抢走父 agent 自主权，复制 child scheduler | 不采用；边界内自主委派 |
| policy 值散落在 Markdown/prompt | 书写直观 | 无法稳定解析、校验和演进 | 不采用；canonical JSON + Schema |
| 一个命名 worker 跨任务复用持久 thread | 可节省启动成本 | 旧上下文、角色和权限可能泄漏到新任务 | 不采用；跨任务 fresh thread |
| 用单写者 lease + run resource ledger 控制 continuation | 可防并发驱动并保留处置证据 | 需要 POC 级文件锁、账本和 reconciliation | 采用；不扩大到 child scheduler |

## 6. 决策 / 理由

| 决策 | 理由 | Owner | 日期 |
| --- | --- | --- | --- |
| Harness 只绑定和验收父 agent | 父 agent 对完成方式拥有自主权，child 只是内部策略；只有边界触发才介入 | Owner | 2026-07-16 |
| App Server v2 是主控制面 | 它提供父 thread/turn、interrupt、read、resume 与 fork 所需的协议能力 | Owner | 2026-07-16 |
| Pilot 采用 10 个 AC、三层 readiness | 可以把“协议可行”“能持续跑”“能做真实开发”分开声明，防止过早 closed | Owner | 2026-07-16 |
| initial attempt 使用 `tickets=false, dag=false` | 10 个 Pilot 是一个 Harness 的 acceptance matrix，不是独立 delivery slices；当前也没有多 owner 或必须持久化的执行图 | Codex / owner 授权的粗粒度模式 | 2026-07-16 |
| D2 patch 继续使用 `tickets=false, dag=false` | 本 patch 有三个实现 area，但不构成独立 delivery slice；它们共享同一个 POC policy/lifecycle acceptance，由单一 owner 集成和验收，不额外制造 ticket/DAG runtime SoT | Codex / owner 授权的探索模式 | 2026-07-18 |
| Impl-Package 3.2 的跨 artifact revision 使用原子注册 | D2/S2 与当前 P1 会同时改变当前选择；逐项 register 命令在另一份 exact-blob 已漂移时会 fail closed，因此需要由 canonical CLI 一次校验并提交整组 revision binding，不手改 sidecar | Impl-Package 3.2 schema migration finding | 2026-07-18 |
| 父 agent 在边界内自主委派 | 信任高能力主控减少过程遥控；Harness 只守住 policy、权限、证据和结果边界 | Owner | 2026-07-18 |
| runtime policy maturity 是内部 vocabulary | `design_baseline` 与 `runtime_enforced` 只描述该 policy 的运行时采用程度，不代表外部标准或整体生产成熟度 | Owner | 2026-07-18 |

## 7. 开放问题 / Owner 决策 / 就绪度

### 开放问题

| 问题 | Owner | 解决方式 / 延后安排 | 对 Spec 的影响 |
| --- | --- | --- | --- |
| `gpt-5.6/high` 是否是长期默认父 profile | Owner | 本 POC 作为可配置默认值使用；性能/成本数据产生后再决定 | 不阻塞；Spec 要求记录实际投影，不把具体模型写成永久合同 |
| 多版本支持范围 | Future owner | durable runner 通过后再建立兼容矩阵 | 不阻塞本版本 POC |

### Decision 门

- 结果（Result）：PASSED
- 目标落点可回答：是；D2 以 canonical policy enforcement、同任务上下文连续性、单写者 lease、资源账本和 terminal disposition 为 patch 目标，旧 10 个 Pilot AC 仍按历史/当前 evidence 分开判定。
- 仓库契合度已有证据：是；复用现有 Skill、父 profile、runner、runtime ledger seam 和 Impl-Package contract 3.2 CLI；D2/S2/P1 已通过 canonical `validate --working-tree`，提交后的 `validate --committed` 与新 terminal gate 仍未宣称通过。
- 实质选择已决定：是；父-only、App Server v2、独立父结果验收、边界内自主委派、跨任务 fresh thread、canonical policy、single-writer continuation 和 fail-closed authority routing。
- 开放问题不阻塞 Spec：是；具体 lease 文件实现、账本字段和处置事件由 spec/plan 固化，production cleanup、跨版本兼容和精细预算继续延后。
- Owner 决策已记录：是；D2 的 patch 继续采用 owner-approved coarse `tickets=false, dag=false`，实现 area 不成为新的交付状态源。
- 证据 / 剩余 blocker：Decision 无 blocker；D2 runtime implementation、确定性 policy/lease/ledger/adapter evidence 与 live package smoke 已产生，仍需完成独立 review、计划 ER/gate 登记及 committed validation；这些是当前 patch 的收口阶段，不改变已批准方向。
- 评估人 / 日期：Codex，2026-07-18。

## 8. Backfill 候选

| 可能的目标位置 | 候选洞见 | 可能长期有效的原因 |
| --- | --- | --- |
| `skills/codex-harness/` | Pilot 通过后将父-only lifecycle 与 acceptance 规则收敛为可执行 Skill workflow | 这些规则可能成为 Harness 的稳定操作合同；是否 backfill 由 terminal gate 的 Durable Deltas 决定 |

## 修订历史

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| none | D1 | 从现有 POC 设计资产建立父-only Harness Pilot package 设计基线 | Owner 决策与 `codex-harness-poc-design.md` | 2026-07-16 | 初始修订 |
| D1 | D2 | 将 canonical runtime policy、边界内自主委派、跨任务上下文重置、single-writer lease、resource ledger 与 disposition lifecycle 纳入 patch 方向；修正旧设计资产引用 | Owner 于 2026-07-18 的设计确认、当前 policy/schema 与 Impl-Package 3.2 validation | 2026-07-18 | 当前修订 |
