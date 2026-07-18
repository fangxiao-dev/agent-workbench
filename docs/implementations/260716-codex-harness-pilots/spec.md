# Codex Harness Pilots 规格

状态（Status）：Spec Gate Passed
创建时间（Created）：2026-07-16
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D2
规格修订（Spec Revision）：S2
<!-- impl-package:projection revision-set end -->
需求来源（Requirement source）：Owner 于 2026-07-18 批准把 runtime policy、生命周期约束与 Impl-Package 3.2 schema migration 纳入 Codex Harness 探索性 implementation。
主题 slug（Topic slug）：codex-harness-pilots
任务包 ID（Package ID）：260716-codex-harness-pilots
规范任务包路径（Canonical package）：`docs/implementations/260716-codex-harness-pilots/`
决策（Decision）：[decision.md](decision.md)

## Decision 门记录（Decision Gate Record）

- 结果（Result）：PASSED
- 目标落点与预期结果：在保留父 agent 自主实现和 native subagent 编排的前提下，新增 canonical runtime policy enforcement、跨任务 fresh context、single-writer continuation、resource ledger 和 terminal disposition 的 POC acceptance。
- 权威来源 / 当前状态证据：[decision.md](decision.md)、[Codex Harness POC 设计资产](../../../skills/codex-harness/assets/codex-harness-poc-design.md)、canonical runtime policy JSON/Schema 与 Impl-Package 3.2 contract；当前 D2/S2/P1 直接按新 schema 验证，不提供旧 schema 兼容路径。
- 选定方向与理由：Harness 只绑定父角色并验收父结果；父 agent 在边界内自主选择完成方式；App Server v2 提供生命周期控制；canonical policy 承载策略值；外部 validator、lease 和 resource ledger 防止 false PASS、并发驱动和无主资源。
- 开放问题处理结果：模型默认值、多版本范围和 production cleanup 明确延后，不影响当前行为合同。
- Owner 决策（已解决 / 未解决）：已解决：父-only 边界、边界内自主委派、canonical policy、跨任务 fresh context、single-writer/resource lifecycle、粗粒度 package 与重点 Spec/Gate；未解决：0。
- 证据位置：[decision.md](decision.md)
- 评估人 / 日期：Codex，2026-07-18。

## Spec 门记录（Spec Gate Record）

- 结果（Result）：PASSED
- 八个章节完整：是；范围、数据合同、状态机、模块 seam、失败恢复、约束、16 个 AC 和一致性均已定义。
- 验收证据已映射：是；每个 AC 指向 Harness runner、独立 validator、fault fixture、attempt/resource ledger、policy fixture 或隔离工作树 evidence。
- 阻塞决策 / 歧义：0。
- 批准人 / 日期：Owner 授权 D2/S2 粗粒度 patch；Codex 按已批准设计固化，2026-07-18。

## 1. 范围 / 权威来源 / 非目标

- 范围：实现并验证一个以 Codex App Server v2 为控制面的父 agent Harness；Harness 加载父 profile 和 canonical runtime policy、提交 work package、监听父 turn、解析父结构化结果、独立验证 claims，并对 timeout、retry、resume/fork、single-writer continuation、resource ledger、disposition/cleanup 和隔离写入提供可审计行为。
- 权威来源与优先级：本 `spec.md` 是 package 行为与 acceptance SoT；[decision.md](decision.md) 拥有选择理由；[Codex Harness Skill](../../../skills/codex-harness/SKILL.md)、POC asset、runtime policy JSON/Schema 提供当前介绍、策略值与证据；OpenAI App Server v2 protocol 是外部接口权威；Impl-Package 3.2 schema/CLI 是 package sidecar、projection 和 gate 状态权威。
- 非目标：Harness 不指定、绑定或验收 child role/数量/模型/prompt/拓扑；不以 child activity 证明任务成功；本 patch 不承诺生产级多版本、MCP allowlist、token budget、长驻 server 的完整 orphan cleanup 或非隔离并行写入。
- 需要确认的假设：目标 Codex 版本可运行配置的父模型；若不可用，capability/profile/policy validation 必须 fail closed，不得静默换模型、跳过 policy 或继续使用无 lease 的 continuation。

## 2. 术语 / 数据合同

- 领域术语：Harness 是外层控制与验收程序；Parent 是 Harness 唯一直接控制的 Codex thread；Child 是 Parent 可选的内部执行细节；Attempt 是一次不可变 evidence identity；Pilot Gate 是本 Spec 的 AC，不等同于 gate.md entry。
- Canonical runtime policy：位于 `skills/codex-harness/assets/codex-harness-runtime-policy.v0.json`、由相邻 `codex-harness-runtime-policy.schema.json` 校验的 JSON policy；其 `schema_version`、canonical path/hash、`maturity` 与策略选择共同构成一次 run 的 policy identity。它是当前 Harness 的内部 canonical vocabulary，不是 Codex、OpenAI 或行业标准。
- Maturity vocabulary：`design_baseline` 表示策略值与 schema 已冻结但尚未证明所有相关执行路径都强制采用；`runtime_enforced` 表示 loader、allow/deny path、failure path、独立 verifier 和 policy-specific evidence 已对所有相关入口闭合。loader 只验证枚举，不自行升级/降级；升级只能由 completion audit 与 owner-approved atomic edit 绑定 AC-11..AC-16 direct evidence。
- Continuation 与 single-writer lease：continuation 仅指同一 work package 的既有 thread 后续 turn；跨任务必须 fresh thread。lease 是 Harness 在 runner-owned `.codex/harness-runs` 中以 `owner_token`、`run_id`、`thread_id`、`expires_at` 和 heartbeat 识别的独占持有权；acquire/release/reconcile 必须 token-match、幂等且冲突 fail closed。
- Resource ledger：独立于 Attempt Ledger 的 append-only JSONL；每个事件至少包含 `event_id`、`run_id`、`resource_type`、`resource_id`、`operation`、`observed_at`、`prev_hash`、`content_hash` 与 `evidence`，必要时包含 `thread_id`、`turn_id`、`worktree`、`process_id`、`lease` 和 `disposition`。旧事件不可覆盖；链断或缺 terminal event 只能产生 orphan candidate。
- Decision request 与 terminal disposition：`decision_requests[]` 是 Harness-private typed routing envelope，按 `category`（`same_task_correction`、`scope_change`、`authority_expansion`、`irreversible_external_side_effect`、`acceptance_ambiguity`）和 `audience`（`harness` 或 `owner`）路由，不由自然语言猜测。terminal disposition 是互斥且幂等的 `promote`、`retry`、`discard` 或 `needs_owner` 记录；cleanup 只处理 Harness 明确拥有的资源，未知副作用/无主资源进入 quarantine/orphan evidence。
- 输入、输出、身份与不变量：每次 run 由 Harness 生成唯一 `run_id` 和 attempt identity，绑定父 profile version、policy version/maturity、Codex version、cwd/worktree、输入 hash、thread id、turn id、deadline 与允许边界；Parent 只返回一个符合版本化 schema 的最终结果；Harness verdict、Parent status、disposition 和 resource-ledger state 分离。
- Schema、归一化、精度与 ownership 语义：Parent Result 至少包含 `schema_version`、`run_id`、`stage`、`status`、`summary`、`artifacts`、`verification`、`findings`、`owner_decisions`、`retry_hint` 与 `boundary_violations`；Harness-owned summary envelope 另含 `policy_identity`、`decision_requests[]`、`disposition` 与 `resource_ledger` pointer，不能要求 Parent 伪造这些字段。runtime policy 必须通过 canonical JSON Schema；路径按 repository-relative canonical form 比较；Harness 拥有最终 verdict、lease、resource ledger 和 disposition，Parent 只拥有其报告内容。
- 条件化 evidence-integrity 合同：主要断言是“指定父 profile 在指定环境完成 work package 且外部 gate 通过”；比较单元是同一 `run_id`、revision、worktree/environment 的 Parent Result 与 Harness fresh evidence；App Server event/history、实际文件/diff、命令 exit status 和 gate artifact分别是对应字段权威。缺失、stale、跨 run/revision、无法解析或相互冲突的 evidence 必须 fail closed；`succeeded`、child activity 或自然语言信心不能替代外部验证。所有 terminal 状态写入稳定公共 result shape，内部 provider/private event 字段不得泄漏进公共合同。
- Maturity 语义：`design_baseline` 和 `runtime_enforced` 是本 Harness 的内部 vocabulary；前者只表示策略语义和 canonical JSON 已就绪，后者要求 policy loader、所有相关 enforcement path、允许/拒绝验证和 evidence 复核均闭合。不能因单个字段或单个 runtime seam 已实现而升级整份 policy。

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
| Harness | Starting 前 | 读取 canonical runtime policy JSON，按相邻 Schema 校验 schema/version、maturity 和 required policy values | 校验失败则 fail closed；成功后 run 记录 policy path/hash/version/maturity |
| Harness | 同一 work package continuation | 为既有 thread 获取 single-writer lease，验证 context/role/config/history continuity 后再提交 turn | lease 冲突或 continuity 证据缺失则不驱动原 thread，按 policy 进入 owner/fresh fallback |
| Harness | Run lifecycle event | 将 run/thread/turn/worktree/process/lease/disposition 事件追加到 resource ledger | 账本 append-only；旧事件不可覆盖，缺 terminal disposition 的资源可被 reconciliation 识别 |
| Harness | Parent 请求建议或越界能力 | 按 policy 将同任务内可修正问题继续交给 Harness，将 scope/authority/不可逆外部副作用/验收歧义路由 owner | 不自动提升权限；boundary rejection 不进入普通 transient retry |
| Harness | Terminal disposition | 根据 verdict 与 policy 记录 promote/retry/discard/needs_owner，并在安全条件满足后释放 lease、关闭 session、标记 cleanup | disposition 是 terminal evidence；清理失败被记录为 residual/orphan，不伪造 cleanup 成功 |

Readiness 派生规则：AC-1 至 AC-6 全部通过才可称为 `read-only Harness POC verified`；AC-1 至 AC-8 全部通过才可称为 `durable Harness runner verified`；AC-1 至 AC-10 全部通过才可称为 `development-ready Harness verified`。AC-11 至 AC-16 全部通过且 policy-specific evidence 完整，才可把 canonical runtime policy 的 `maturity` 从 `design_baseline` 声明为 `runtime_enforced`；该声明不自动推导旧三层 readiness 或生产就绪。较低层通过不能推导较高层 closed。

## 4. 模块边界 / 依赖

- Owning 模块及其职责：`.codex/harness/parent.toml` 拥有父 profile 输入；runtime policy JSON/Schema loader 拥有 policy identity/shape/maturity；App Server runner 拥有 transport、thread/turn lifecycle 和事件采集；Parent Result validator 拥有 schema/identity/claim 检查；attempt ledger 拥有 immutable retry lineage；resource ledger/lease seam 拥有 lifecycle resource identity、single-writer 和 disposition evidence；Impl-Package adapter 拥有 work package/gate 映射；隔离执行层拥有 worktree 与 mutation allowlist。
- 接口与 seam：父 profile TOML + runtime policy JSON → `thread/start`/runner boundary；work package → `turn/start`；App Server notifications/history → lifecycle state；Parent Result + repository/runtime facts → Harness verdict；lease/resource ledger → continuation/disposition/reconciliation；Spec AC → plan ER → gate.md entry。
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
| runtime policy 文件缺失、Schema 不匹配、版本/maturity 不可识别 | 本次运行的策略边界不可证明 | start 前按 canonical JSON/Schema fail closed；不回退到 prompt 默认值 | 修正 policy 后 fresh attempt；不得静默运行 | Harness |
| 同一持久 thread 已被其他 controller 占用 | 并发 turn、上下文交叉或 evidence 归属不明 | exclusive lease 文件与 owner token；冲突不驱动 thread | 返回 `needs_owner`/fresh fallback；不得强行接管 | Harness / Owner |
| resource ledger 缺记录、链断或 terminal disposition 缺失 | run/resource 状态不可审计，可能遗留 session/lease | append-only ledger、hash/identity 校验和只读 reconciliation | 标记 orphan candidate；不伪造 cleanup 成功，不自动删除未知资源 | Harness |
| policy 阻断能力请求或 owner decision 未解决 | 父 agent 无法在当前授权内继续 | 结构化 decision routing，区分 Harness-resolvable 与 owner-required | 同任务纠偏可新 turn；owner-required 终止当前 disposition | Harness / Owner |

## 6. 约束合同

- 禁止行为：不得以 Parent `succeeded`、最终自然语言、child 数量/角色/activity 或相邻测试代替 Harness direct evidence；不得覆盖失败 attempt；不得在 resume/fork 配置失配时继续并宣称原角色有效。
- Trust 与 permission 边界：Harness 只信任其生成的 `run_id`、启动参数、App Server identity、canonical policy projection、fresh validator、lease owner token 和固定 comparison point；Parent/Child 无权扩大 sandbox、mutation authority、network、deadline、并发/成本边界或 acceptance scope。
- 精度 / 归一化义务：路径、revision、环境、命令 exit code 和 schema version 必须精确归一化；任何无法确定是否同一 run/revision/environment 的 evidence 视为不可信。
- 上下文与任务分区义务：独立任务必须从 fresh thread 开始；同一 work package continuation 才可使用 resume/fork/new turn；任务责任默认不重叠，worktree 隔离不等于物理冲突或外部副作用隔离。
- Lifecycle 与 maturity 义务：所有 run 必须有 resource ledger 和 terminal disposition；`runtime_enforced` 只能在 AC-11..AC-16 及相应 direct evidence 完整时声明。
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
| AC-11 | Harness 只在 canonical runtime policy 可加载、Schema/version/maturity 可验证时启动 run | Runtime policy loader + malformed policy fixtures | 正常 policy 通过并记录 canonical path/hash/version/maturity；缺失、错误 Schema、未知 enum、非法 maturity transition 全部 fail closed，不回退到 prompt 默认值 |
| AC-12 | 独立任务使用 fresh thread，同一 work package continuation 使用 single-writer lease 和 continuity evidence | Runtime lease fixture + resume/fork controller seam | 跨任务复用旧 thread 被拒绝；同一 thread 并发 acquire 只有一个成功；释放 token 不匹配被拒绝；continuity 缺失时不提交 turn |
| AC-13 | 每次 run 的 thread/turn/worktree/process/lease/disposition 资源事件进入 append-only resource ledger | Resource ledger fixture + reconciliation check | 事件 identity/顺序/hash 可验证；旧事件不可覆盖；缺 terminal event、残留 lease 或无主资源被识别为 orphan candidate 且不被静默删除 |
| AC-14 | 父 agent 在边界内可自主委派；可由 Harness 处理的同任务纠偏继续，scope/authority/不可逆副作用/验收歧义路由 owner | Decision-routing fixture + boundary comparator | 无 child、不同 child topology 不改变 verdict；policy blocked 不自动提权；owner-required request 不被误重试或误判失败 |
| AC-15 | terminal run 具有明确 disposition，并按 disposition 安全释放 session/lease、标记 cleanup 和后续 reconciliation | Disposition/cleanup fixture + package runner summary | promote/retry/discard/needs_owner 状态互斥且可重放；cleanup 成功/失败可观察；未知副作用或 orphan 不自动清理或重试 |
| AC-16 | Harness Impl-Package adapter 遵守当前 3.2 Composition、revision binding、runtime-state、gate 和 plan-contract-v1 语义 | Canonical CLI validation + no-DAG/optional-artifact/ER-append fixtures | 不把 `dag.md` 或 `decision.md` 当无条件必选；缺 runtime-state、gate mismatch、frozen current attempt、D/S/P binding drift 均 fail closed；合法 no-DAG 与 plan ER append 不被误判；adapter 不复制另一套 package schema |

条件化 false-PASS 覆盖：AC-3 验证声明与权威 evidence 冲突；AC-4 验证拒绝/副作用边界；AC-5/6 验证中断后状态和重试补偿；AC-7 验证恢复投影漂移；AC-9/10 验证 gate/diff 公共状态不能因 Parent 自述而漂移；AC-11/12 覆盖 malformed/unknown policy、非法 maturity、stale/forged lease 与跨任务复用；AC-13 覆盖 ledger truncation/hash-chain 断裂；AC-14 覆盖 owner-route bypass 与 policy blocked 自动提权；AC-15 覆盖 disposition/cleanup replay；AC-16 覆盖 no-DAG、optional decision、runtime-state/gate 缺失及 plan ER append 的 adapter 误判。

## 8. 合同一致性

- 跨章节一致性：父-only 控制边界、边界内自主委派、Harness-owned verdict、immutable attempt、canonical policy、single-writer、resource ledger、fail-closed evidence 与三层 readiness/maturity 规则在输入、工作流、错误恢复、约束和 AC 中一致。
- 接口 / seam ownership：父 profile、runtime policy、App Server lifecycle、Parent Result、validator、attempt ledger、resource ledger/lease、Impl-Package adapter 和隔离执行层均有唯一 owner；child orchestration 不成为 Harness seam。
- 验收覆盖：AC-1/2 覆盖基本父闭环与自主性；AC-3/4 覆盖 false PASS 与权限边界；AC-5/6 覆盖中断和重试；AC-7/8 覆盖 durable lifecycle；AC-9/10 覆盖真实任务与写入；AC-11..15 覆盖 policy enforcement、上下文/lease、资源账本、决策路由和处置/cleanup；AC-16 覆盖 Impl-Package 3.2 adapter schema migration。
- 剩余非阻塞假设：具体默认模型和支持版本可配置；每次 evidence 必须记录实际值，不能把本次默认提升为永久合同。

## 修订记录

| 前一修订 | 新修订 | 合同变化 | 原因 / 权威来源 | 日期 | 被取代说明 |
| --- | --- | --- | --- | --- | --- |
| none | S1 | 建立父-only Harness、10 个 Pilot AC、三层 readiness 与 fail-closed evidence 合同 | D1、Owner 决策和现有 POC 调研 | 2026-07-16 | 初始修订 |
| S1 | S2 | 增加 canonical runtime policy、maturity vocabulary、跨任务 fresh context、single-writer lease、resource ledger、decision routing、disposition/cleanup 与 Impl-Package 3.2 adapter schema migration 的行为合同和 AC-11..AC-16；修正当前设计资产路径 | D2、runtime policy v0/schema、当前 runner 与 Impl-Package 3.2 contract | 2026-07-18 | 当前修订 |
