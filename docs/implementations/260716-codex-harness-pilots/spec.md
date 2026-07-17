# Codex Harness Pilots 规格

状态（Status）：Spec Gate Passed
创建时间（Created）：2026-07-16
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D1
规格修订（Spec Revision）：S1
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：Owner 于 2026-07-16 批准把现有 Harness 设计转成粗粒度探索性任务包，重点定义 Spec 与 Gate。
主题 slug（Topic slug）：codex-harness-pilots
任务包 ID（Package ID）：260716-codex-harness-pilots
规范任务包路径（Canonical package）：`docs/implementations/260716-codex-harness-pilots/`
决策（Decision）：[decision.md](decision.md)

## Decision 门记录（Decision Gate Record）

- 结果（Result）：PASSED
- 目标落点与预期结果：通过父-only App Server Harness 与 10 个 Pilot AC，分层证明只读 POC、durable runner 和 development-ready。
- 权威来源 / 当前状态证据：[decision.md](decision.md) 与 [Codex Harness POC 设计资产](../../../skills/codex-harness/assets/codex-harness-poc-decision.md)；当前 native App Server/thread feasibility 已证明，父-only live loop 尚待执行。
- 选定方向与理由：Harness 只绑定父角色并验收父结果；父 agent 自主选择完成方式；App Server v2 提供生命周期控制；外部 validator 防止 false PASS。
- 开放问题处理结果：模型默认值和多版本范围明确延后，不影响当前行为合同。
- Owner 决策（已解决 / 未解决）：已解决：父-only 边界、粗粒度 package、重点 Spec/Gate；未解决：0。
- 证据位置：[decision.md](decision.md)
- 评估人 / 日期：Codex，2026-07-16。

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED
- 八个章节完整：是；范围、数据合同、状态机、模块 seam、失败恢复、约束、10 个 AC 和一致性均已定义。
- 验收证据已映射：是；每个 AC 指向 Harness runner、独立 validator、fault fixture、attempt ledger 或隔离工作树 evidence。
- 阻塞决策 / 歧义：0。
- 批准人 / 日期：Owner 授权粗粒度任务包；Codex 按已批准设计固化，2026-07-16。

## 1. 范围 / 权威来源 / 非目标

- 范围：实现并验证一个以 Codex App Server v2 为控制面的父 agent Harness；Harness 加载父 profile、提交 work package、监听父 turn、解析父结构化结果、独立验证 claims，并对 timeout、retry、resume/fork、cleanup 和隔离写入提供可审计行为。
- 权威来源与优先级：本 `spec.md` 是 package 行为与 acceptance SoT；[decision.md](decision.md) 拥有选择理由；[Codex Harness Skill](../../../skills/codex-harness/SKILL.md) 与其 POC asset 提供当前介绍、调研和 Sources Index；OpenAI App Server v2 protocol 是外部接口权威。
- 非目标：Harness 不指定、绑定或验收 child role/数量/模型/prompt/拓扑；不以 child activity 证明任务成功；本 attempt 不承诺生产级多版本、MCP allowlist、token budget 或非隔离并行写入。
- 需要确认的假设：目标 Codex 版本可运行配置的父模型；若不可用，capability/profile validation 必须 fail closed，不得静默换模型后仍宣称原 profile 已验证。

## 2. 术语 / 数据合同

- 领域术语：Harness 是外层控制与验收程序；Parent 是 Harness 唯一直接控制的 Codex thread；Child 是 Parent 可选的内部执行细节；Attempt 是一次不可变 evidence identity；Pilot Gate 是本 Spec 的 AC，不等同于 gate.md entry。
- 输入、输出、身份与不变量：每次 run 由 Harness 生成唯一 `run_id` 和 attempt identity，绑定父 profile version、Codex version、cwd/worktree、输入 hash、thread id、turn id、deadline 与允许边界；Parent 只返回一个符合版本化 schema 的最终结果；Harness verdict 与 Parent status 分离。
- Schema、归一化、精度与 ownership 语义：Parent Result 至少包含 `schema_version`、`run_id`、`stage`、`status`、`summary`、`artifacts`、`verification`、`findings`、`owner_decisions`、`retry_hint` 与 `boundary_violations`；路径按 repository-relative canonical form 比较；Harness 拥有最终 verdict 和 attempt ledger，Parent 只拥有其报告内容。
- 条件化 evidence-integrity 合同：主要断言是“指定父 profile 在指定环境完成 work package 且外部 gate 通过”；比较单元是同一 `run_id`、revision、worktree/environment 的 Parent Result 与 Harness fresh evidence；App Server event/history、实际文件/diff、命令 exit status 和 gate artifact分别是对应字段权威。缺失、stale、跨 run/revision、无法解析或相互冲突的 evidence 必须 fail closed；`succeeded`、child activity 或自然语言信心不能替代外部验证。所有 terminal 状态写入稳定公共 result shape，内部 provider/private event 字段不得泄漏进公共合同。

## 3. 行为 / 状态机 / 工作流

| Actor / 系统 | 条件 / 状态 | 动作 / 事件 | 结果 / 下一状态 |
| --- | --- | --- | --- |
| Harness | Start requested，profile/capability 尚未验证 | 校验 Codex version、App Server capability、父 profile 与边界，创建 run/attempt | 通过后进入 Starting；失败则 Failed 且不启动父 turn |
| Harness | Starting | `thread/start` 映射父 developer instructions、model/effort、cwd 与 sandbox，再 `turn/start` 提交 work package/result contract | Running，并记录 thread/turn identity |
| Parent | Running | 自主完成任务，可选择 0..N 个 child；遵守 Harness 边界 | 返回单一 Parent Result；child telemetry 不改变 acceptance |
| Harness | 收到 `turn/completed` | 解析 schema、核对 identity，并运行 artifact/command/diff/gate validator | 全部通过则 Succeeded；歧义/owner decision 则 NeedsOwner；可恢复失败则 Retryable；其余 Failed |
| Harness | Running 超过 deadline 或 operator cancel | 调用 `turn/interrupt`，等待有限 grace period；必要时终止 App Server | Interrupted；根据 retry policy 进入 Retryable 或终止 |
| Harness | Retryable | 创建新 attempt id，保留旧 evidence；按策略选择 same thread new turn、resume、fork 或 fresh thread | 新 Running；不得覆盖旧 attempt |
| Harness | App Server 重启或上下文不可信 | 验证 role canary、model/effort 与 history boundary；失配时放弃恢复 | Resume/Fork 成功，或 fail closed 到 fresh thread |
| Harness | Terminal candidate | 固定 comparison point，保存 Parent Result、validator evidence 与 lifecycle decision | 形成可审计 verdict；只有 Spec AC 对应 evidence 完整时提升 readiness claim |

Readiness 派生规则：AC-1 至 AC-6 全部通过才可称为 `read-only Harness POC verified`；AC-1 至 AC-8 全部通过才可称为 `durable Harness runner verified`；AC-1 至 AC-10 全部通过才可称为 `development-ready Harness verified`。较低层通过不能推导较高层 closed。

## 4. 模块边界 / 依赖

- Owning 模块及其职责：`.codex/harness/parent.toml` 拥有父 profile 输入；App Server runner 拥有 transport、thread/turn lifecycle 和事件采集；Parent Result validator 拥有 schema/identity/claim 检查；attempt ledger 拥有 immutable run evidence 与 retry lineage；Impl-Package adapter 拥有 work package/gate 映射；隔离执行层拥有 worktree 与 mutation allowlist。
- 接口与 seam：父 profile TOML → `thread/start` 映射；work package → `turn/start`；App Server notifications/history → lifecycle state；Parent Result + repository/runtime facts → Harness verdict；Spec AC → plan ER → gate.md entry。
- 上游 / 下游依赖：上游为已批准 Impl-Package work package、Codex CLI/App Server 和仓库 policy；下游为 validator、review/gate、attempt ledger 与 owner-facing readiness claim。
- 兼容或迁移窗口：本 attempt 只绑定并记录当前验证的 Codex version/capabilities；unsupported method 只允许显式 capability fallback（如 `thread/items/list` → `thread/read`），不得把未知字段或静默 fallback 当作已验证兼容。

## 5. 错误边界 / 失败恢复

| 失败模式 | 可观察影响 | 隔离方式 | 重试 / 补偿 / 恢复 | Owner |
| --- | --- | --- | --- | --- |
| 父 profile、model 或 capability 无效 | 父执行未启动或实际配置不可证明 | Start 前 fail closed，记录请求值与可观察投影 | 修正 profile/capability 后 fresh attempt | Harness |
| Parent Result malformed、identity 错误或字段缺失 | 无可信 acceptance input | verdict=Failed/Retryable，不执行成功副作用 | 仅按明示 transient policy 有界重试 | Harness |
| Parent 自报成功但 artifact/command/gate 不成立 | false-PASS 风险 | 外部 validator 覆盖 Parent status | verdict=Failed，保留冲突证据；确定性失败不自动重试 | Harness |
| 越权写入、路径、网络或外部副作用请求 | 安全/数据边界风险 | sandbox、allowlist 和 mutation authority 拒绝；记录 violation | 默认终止；扩大 authority 需新 owner 授权 | Harness / Owner |
| 父 turn 超时、cancel 或 App Server 无响应 | run 停滞 | `turn/interrupt` + grace period + process kill fallback | 新 attempt；上下文可信才 same-thread/resume，否则 fresh | Harness |
| resume/fork 后 instructions/model/effort 失配 | 父角色漂移 | role canary 与 observable config 检查 | 放弃该恢复路径并 fresh thread | Harness |
| child/session/slot 泄漏 | 后续 run 无法 spawn 或 server 退化 | bounded session/process、loaded-state/soak 监测 | 清理有界；不可靠时重建 App Server 进程 | Harness |
| 隔离写入失败或越界 diff | 工作树污染风险 | 临时 repo/worktree、allowed-path diff gate | 丢弃隔离环境；未知副作用不自动重试 | Harness |

## 6. 约束合同

- 禁止行为：不得以 Parent `succeeded`、最终自然语言、child 数量/角色/activity 或相邻测试代替 Harness direct evidence；不得覆盖失败 attempt；不得在 resume/fork 配置失配时继续并宣称原角色有效。
- Trust 与 permission 边界：Harness 只信任其生成的 `run_id`、启动参数、App Server identity、fresh validator 和固定 comparison point；Parent/Child 无权扩大 sandbox、mutation authority、network、deadline、并发/成本边界或 acceptance scope。
- 精度 / 归一化义务：路径、revision、环境、命令 exit code 和 schema version 必须精确归一化；任何无法确定是否同一 run/revision/environment 的 evidence 视为不可信。
- 外部 provider 义务：本 POC 不要求外部 provider；若未来加入，必须单独定义 authority、side-effect commit point、补偿和 fail-closed evidence。
- 负向依赖（不得依赖）：不得依赖 Desktop UI、固定 child topology、`.codex/agents/*.toml` 为父 thread 自动绑定、`codex exec --json` 的 child provenance、App Server 未声明支持的分页 API、模型自行声明其真实配置。

## 7. 验收语义 / 验证证据

| AC ID | 承诺结果 / 约束 | 证据 producer 或 manual owner | 通过证据 |
| --- | --- | --- | --- |
| AC-1 | Harness 可加载父 profile，经 App Server 启动父 thread/turn，并取得 schema-valid Parent Result | App Server runner + schema validator | 同版本/环境连续 3 次 live run；每次记录 version/capability、profile 请求与可观察投影、thread/turn、正确 `run_id`、合法 result；无 worktree drift |
| AC-2 | Parent 对完成方式自主，Harness verdict 不依赖 child 行为 | 场景 runner + verdict comparator | 简单、并行型、模糊型任务均不指定 child；无论观察到 0..N child，只有父结果/外部 gate 相同时 verdict 才相同；child 只进入 telemetry |
| AC-3 | Harness 对 malformed/伪造/stale Parent evidence fail closed | Deterministic fault fixtures + validator tests | malformed JSON、错误 `run_id`、不存在 artifact、实际失败命令、stale revision、`needs_owner` 全部得到预期非成功分类，false PASS=0 |
| AC-4 | 权限、路径、mutation、network 和外部副作用边界不可由 Parent 绕过 | Sandbox/allowlist probe + worktree/external-state check | read-only 越权场景被拒绝，boundary violation 可观察，允许范围外 worktree/external state 无变化 |
| AC-5 | deadline/cancel 能中断父 turn，并在不可靠时回收 App Server | Timeout pilot + process/state observer | 人为长任务到期后发出 `turn/interrupt`；grace period 内 terminal，或 process fallback 生效；随后 fresh run 成功 |
| AC-6 | Retry 只作用于明示可恢复失败，并保持 attempt evidence 不可变 | Fault-injection runner + attempt ledger validator | transient case 有界重试并生成新 attempt；deterministic failure、NeedsOwner、安全拒绝和未知副作用不自动重试；lineage/旧 evidence 未覆盖 |
| AC-7 | resume/fork 后父角色、model/effort 和 history boundary 可证明，失配时 fresh fallback | Restart/resume/fork pilot + role canary | App Server 重启后 resume/fork 场景通过 canary/config/history 检查；故意失配场景被拒绝并切换 fresh thread |
| AC-8 | 多轮普通、child、自主并发和 interrupted run 不导致持续 slot/session/process 泄漏 | Soak runner + resource observer | 至少 20 轮完成；无持续 orphan process/agent slot，资源回到定义阈值，最后一轮 fresh run 成功 |
| AC-9 | Harness 能消费一个真实 approved Impl-Package work package，并把父结果/外部 evidence 写回正确 gate 链 | Impl-Package adapter + review/gate owner | work package → Parent Result → external verification → plan ER → gate entry 全链可解析；child telemetry 不进入 acceptance dependency |
| AC-10 | Harness 能在隔离环境完成允许范围内的真实写入，并拒绝越界 diff | Isolated worktree pilot + diff/test validator | 允许路径改动和指定测试通过；越界 mutation fixture 被拒绝；失败/取消后隔离环境可丢弃且主工作树无污染 |

条件化 false-PASS 覆盖：AC-3 验证声明与权威 evidence 冲突；AC-4 验证拒绝/副作用边界；AC-5/6 验证中断后状态和重试补偿；AC-7 验证恢复投影漂移；AC-9/10 验证 gate/diff 公共状态不能因 Parent 自述而漂移。

## 8. 合同一致性

- 跨章节一致性：父-only 控制边界、Harness-owned verdict、immutable attempt、fail-closed evidence 与三层 readiness 在输入、工作流、错误恢复、约束和 AC 中一致。
- 接口 / seam ownership：父 profile、App Server lifecycle、Parent Result、validator、attempt ledger、Impl-Package adapter 和隔离执行层均有唯一 owner；child orchestration 不成为 Harness seam。
- 验收覆盖：AC-1/2 覆盖基本父闭环与自主性；AC-3/4 覆盖 false PASS 与权限边界；AC-5/6 覆盖中断和重试；AC-7/8 覆盖 durable lifecycle；AC-9/10 覆盖真实任务与写入。
- 剩余非阻塞假设：具体默认模型和支持版本可配置；每次 evidence 必须记录实际值，不能把本次默认提升为永久合同。

## 修订记录

| 前一修订 | 新修订 | 合同变化 | 原因 / 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| none | S1 | 建立父-only Harness、10 个 Pilot AC、三层 readiness 与 fail-closed evidence 合同 | D1、Owner 决策和现有 POC 调研 | 2026-07-16 | 初始修订 |
