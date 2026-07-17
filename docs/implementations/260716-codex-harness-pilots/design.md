# Codex Harness Pilots 设计研究

状态（Status）：Design Gate Passed
创建时间（Created）：2026-07-16
设计修订（Design Revision）：D1
需求来源（Requirement source）：Owner 于 2026-07-16 要求将已完成的 Codex Harness 可行性调研转成粗粒度探索性 Impl-Package，重点定义 Spec 与 Gate。
主题 slug（Topic slug）：codex-harness-pilots
任务包 ID（Package ID）：260716-codex-harness-pilots
规范任务包路径（Canonical package）：`docs/implementations/260716-codex-harness-pilots/`

本文是本任务包当前设计选择与理由的事实源。完整调研、App Server Sources Index 与本地 POC 证据直接复用 [Codex Harness POC 设计资产](../../../skills/codex-harness/assets/codex-harness-poc-design.md)，本文不复制其研究正文；行为、失败恢复和验收语义由 [spec.md](spec.md) 独占。

## 1. 目标落点

- 预期结果：得到一个可以通过 Codex App Server 启动父 agent、约束父运行边界、验收父结构化结果并在失败后恢复的 Harness，并用分层 Pilot evidence 判断只读 POC、durable runner 与 development-ready 三种 readiness。
- 受影响的系统边界：`codex-harness` Skill、父 profile、App Server runner、结果 validator、attempt/lifecycle ledger，以及隔离写入 Pilot；Codex 原生 child orchestration 保持为父 agent 的内部实现。
- 合同交接点：本设计把已选方向交给 [spec.md](spec.md) 定义行为合同和 Pilot Gate，再由 [plan.md](plan.md) 安排粗粒度实现与验证。

## 2. 需求 / 结果

- 聚焦需求：证明父-only Codex Harness 不仅协议上可行，而且能稳定执行、拒绝 false PASS、守住边界、处理中断/重试/恢复，并最终承载真实 Impl-Package 和隔离写入任务。
- 用户或系统结果：Harness 使用者只需给父 agent 布置 work package 并验收父结果，无需知道或控制父 agent 是否以及如何使用 child agents。
- 成功信号：10 个 Spec AC 均有同 revision、同环境的直接 evidence；根据通过范围可准确声明只读 POC、durable runner 或 development-ready，而不会扩大 completion claim。

## 3. 知识来源 / 当前状态

- 已检查的权威来源：现有 Codex Harness POC 设计资产及其官方 Sources Index；`skills/codex-harness/SKILL.md`；`.codex/harness/parent.toml`；当前两个 pilot runner；Impl-Package composition、req-align、planning、gate 与 completion-claim 契约；仓库 `AGENTS.md`。
- 聚焦代码 / 测试事实：App Server thread/turn 和 native child thread 可追踪已在 `codex-cli 0.144.4` 上证明；修订后的父 profile 映射和结果 parser 已通过静态校验，但尚未完成 live parent-only run。
- 预期但缺失的知识：仓库没有既有 implementation package 或 module-knowledge 水印可复用；没有现成的 Harness fault-injection/soak test framework。
- 冲突或 drift：无；最新 owner 决策已明确取消 child role/数量验收，只绑定父角色。

## 4. 约束 / 非目标

- 约束：Harness 只控制父 thread/turn、父 profile、work package、运行边界和父结果 acceptance；独立 validator 而非父自述决定通过。
- 非目标：不实现外部 child scheduler；不绑定或验收 child role、数量、模型、prompt、拓扑；本 attempt 不承诺生产级多版本兼容、MCP allowlist 或 token budget。
- 安全或外部 mutation 边界：前期 Pilot 默认 read-only；写入验证只能在明确隔离的临时 repo/worktree 和 allowlisted path 中执行，不得污染当前主工作树或产生未授权外部副作用。

## 5. 选项 / 权衡

| 选项 | 收益 | 成本 / 风险 | 与仓库的契合度 |
| --- | --- | --- | --- |
| Harness 直接调度每个 child | 控制粒度细 | 复制 Codex scheduler、强耦合内部协议、扩大生命周期故障面 | 不采用 |
| Harness 只控制父 agent | 边界稳定，允许 Codex 自主进化，验收面清晰 | 需要更强的父结果 schema 与外部 validator | 采用 |
| `codex exec --json` 为主控制面 | 实现简单 | durable thread、interrupt/resume 和 provenance 不足 | 只保留对照 |
| App Server v2 为主控制面 | thread/turn 生命周期、事件与恢复能力完整 | 需要 capability probe、超时和兼容降级 | 采用 |
| 先按生产规格扩展全部权限/预算控制 | 一次覆盖完整 | 探索期成本高且会掩盖核心闭环 | 不采用；风险出现后再扩展 |

## 6. 决策 / 理由

| 决策 | 理由 | Owner | 日期 |
| --- | --- | --- | --- |
| Harness 只绑定和验收父 agent | 父 agent 对完成方式拥有自主权，child 只是内部策略；只有边界触发才介入 | Owner | 2026-07-16 |
| App Server v2 是主控制面 | 它提供父 thread/turn、interrupt、read、resume 与 fork 所需的协议能力 | Owner | 2026-07-16 |
| Pilot 采用 10 个 AC、三层 readiness | 可以把“协议可行”“能持续跑”“能做真实开发”分开声明，防止过早 closed | Owner | 2026-07-16 |
| initial attempt 使用 `tickets=false, dag=false` | 10 个 Pilot 是一个 Harness 的 acceptance matrix，不是独立 delivery slices；当前也没有多 owner 或必须持久化的执行图 | Codex / owner 授权的粗粒度模式 | 2026-07-16 |

## 7. 开放问题 / Owner 决策 / 就绪度

### 开放问题

| 问题 | Owner | 解决方式 / 延后安排 | 对 Spec 的影响 |
| --- | --- | --- | --- |
| `gpt-5.6/high` 是否是长期默认父 profile | Owner | 本 POC 作为可配置默认值使用；性能/成本数据产生后再决定 | 不阻塞；Spec 要求记录实际投影，不把具体模型写成永久合同 |
| 多版本支持范围 | Future owner | durable runner 通过后再建立兼容矩阵 | 不阻塞本版本 POC |

### Design 门

- 结果（Result）：PASSED
- 目标落点可回答：是；Harness readiness 由 10 个 Pilot evidence 分层判定。
- 仓库契合度已有证据：是；复用现有 Skill、父 profile、runner 和 Impl-Package 契约。
- 实质选择已决定：是；父-only、App Server v2、独立父结果验收、边界触发介入。
- 开放问题不阻塞 Spec：是；模型默认值和多版本范围均有明确延后边界。
- Owner 决策已记录：是。
- 证据 / 剩余 blocker：设计无 blocker；实现与 Pilot evidence 尚未产生。
- 评估人 / 日期：Codex，2026-07-16。

## 8. Backfill 候选

| 可能的目标位置 | 候选洞见 | 可能长期有效的原因 |
| --- | --- | --- |
| `skills/codex-harness/` | Pilot 通过后将父-only lifecycle 与 acceptance 规则收敛为可执行 Skill workflow | 这些规则可能成为 Harness 的稳定操作合同；是否 backfill 由 terminal gate 的 Durable Deltas 决定 |

## 修订历史

| 前一修订 | 新修订 | 变化摘要 | 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| none | D1 | 从现有 POC 设计资产建立父-only Harness Pilot package 设计基线 | Owner 决策与 `codex-harness-poc-design.md` | 2026-07-16 | 初始修订 |
