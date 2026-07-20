# 独立工程计划审查 Skill 设计与实施计划

日期：2026-07-13

最近修订：2026-07-20

状态：prototype 实现与 evaluable-candidate blind comparison 已完成；default rollout 与 gstack 安装面治理未执行

工作名称：`eng-plan-review`

设计资料目录：`docs/skill-design/independent-eng-plan-review/`。该目录只保存 proposal、语义保真矩阵、eval 记录和其他设计期临时文档，不是正式 skill 的运行时目录。

## 1. 背景与问题

现有 `plan-eng-review` 同时承载工程审查内核、gstack 运行时初始化、跨 session 记忆、问题偏好、telemetry、artifact sync、review dashboard、下游 skill chaining、Outside Voice、任务 JSONL 和 plan report 等职责。生成后的 `SKILL.md` 与 `review-sections.md` 合计 1,973 行、约 121 KB，而对应模板合计 381 行、约 28.7 KB；约 76.3% 的生成内容来自公共运行时注入。

这导致三个直接问题：单次审查需要加载过多与当前判断无关的指令；重复的 STOP、AskUserQuestion 和兼容分支增加规则冲突；工程师必须通过大量线性交互才能完成一个本可自动收敛的审查。

本计划不在原 gstack skill 上继续裁剪，而是提取其有效审查语义，创建一个 host-neutral、无 gstack runtime 依赖、渐进加载的新 skill。原 `plan-eng-review` 保持不动，作为行为基线和 A/B 对照对象。

## 2. 目标

新 skill 应在不降低工程审查质量的前提下实现以下能力：

- 审查明确的 implementation plan、technical plan 或 plan package。
- 对 Scope、Architecture、Code Quality、Tests、Performance 五个维度执行 materiality scan；每个维度必须记录“已审查”“不适用及理由”或“存在 finding”，不要求所有计划机械执行相同审查深度。
- 横切 rubric 贯穿每个 candidate 与 finding，聚焦 reference 只增加各维度的发现方法，不能相互替代；能力保真按风险类别召回验收，不按规则行数或 checklist 命中数验收。
- 探索期 candidate 只记录 claim、初步 evidence 或 reasoning 及 risk；正式 finding 才要求严重度、同轮可比较的置信表达、可核验 evidence、推荐和 owner gate，计划缺失项允许使用有界 `absence-proof`。
- Judge、Critic 和 Section Reviewer 都是按风险启用的工具，不是固定角色编制；Outside Voice 是唯一每轮必选的独立角色，并保持 fresh context。
- 用薄指导的批量决策规则替代逐 finding 一问一答：只有真正阻塞多个 material branches 的决定提前询问，其余决定按依赖关系分波次收集，owner 对最终 decision manifest hash 的一次明确 `apply` 同时构成 ratification 与写入授权。
- 使用 review ledger 保护目标与证据基线、合法 resolution、owner 授权、未决集合、原子写入和 stale 检测，不把角色编排或审查问题树固化为脚本工作流。
- Review 与 Apply 分离；审查阶段不修改目标 plan，只有 owner 明确要求 `apply` 后才写回。
- 小计划允许 Main session inline 执行 material sections，大计划或 cross-boundary plan 可并行 Section Reviewer；高影响自动归纳、证据冲突、不可逆性、跨边界影响或 reviewer 明显不确定时才启用 fresh Judge/Critic。
- 每轮在聊天中简短报告启用或跳过的角色与工具及理由；该报告只提供运行可见性，不要求恢复或固化角色状态。
- Outside Voice 每轮必须来自 fresh agent、不同模型或其他独立上下文，不能用 Main session inline 模拟新视角；独立能力不可用时仍可降级交付 findings，但不能宣称 `fully reviewed` 或 `cleared`。
- 主 `SKILL.md` 保持精简，按当前阶段加载 references，而不是一次性加载全部审查与收尾规则。

## 3. 非目标

- 不复刻 gstack 的 telemetry、GBrain、artifact sync、review dashboard、`/ship` readiness 或 question tuning 生态。
- 不直接替代 `plan-ceo-review`、`plan-design-review`、`qa`、`qa-only`、`autoplan` 或 `ship`。
- 不在审查阶段修改被审 plan、spec、代码或仓库配置。
- 不让 Judge 代替 owner 决定产品意图、风险偏好、范围扩张、契约变化或不可逆操作。
- 不以减少测试、failure modes、证据门槛或 review depth 的方式换取更短 prompt。
- 不修改或删除现有第三方 `plan-eng-review`；是否退役旧 skill 在新版通过对照 eval 后另行决定。

## 4. 已确认设计决策

| ID | 决策 | 理由 | 状态 |
| --- | --- | --- | --- |
| R1 | 创建独立新 skill，不继续直接修改生成后的 `plan-eng-review` | 原 skill 受 gstack 生成器和 runtime 约束，直接删改容易被覆盖且难以真正独立 | 已确认 |
| R2 | 硬约束只保留目标与基线绑定、Review 不写目标、正式 finding evidence gate、owner 专属决策和 Apply stale/authorization gate | 其余机制都应作为 agent 按情境调用的工具，而不是固定流程 | 已确认 |
| R3 | 每轮先加载横切 rubric 与五个短聚焦 reference，再做 materiality scan；每维记录“已审查／不适用及理由／存在 finding” | 防止在尚未获得聚焦观察工具时误判 N/A，同时让调查深度、图示和输出仍保持风险驱动 | 已确认 |
| R4 | 使用两级 finding 合同，confidence 只要求同轮可比较 | 避免探索阶段填满 schema 和制造数值伪精度 | 已确认 |
| R5 | Judge、Critic、Section Reviewer 按风险启用；Outside Voice 每轮必选且保持 fresh context | 把独立复核成本绑定到具体风险，同时保留每轮新视角 | 已确认 |
| R6 | 每轮在聊天中报告启用或跳过的角色与工具及理由 | 提供运行可见性，但不形成角色恢复协议或持久状态机 | 已确认 |
| R7 | 行为变更默认生成 coverage map，复杂关系才升级 test diagram | 默认保护测试分析与 failure modes，不强制特定可视化形式 | 已确认 |
| R8 | Batch Decision Protocol 保持薄指导，owner 对 manifest hash 的单次明确 `apply` 同时完成 ratification 与写入授权 | 减少 owner 往返并避免重复授权门禁 | 已确认 |
| R9 | Ledger 位于用户 OS temp 并使用唯一 run identity；脚本只保护安全与状态不变量 | 临时工件不污染仓库，脚本不成为新的工作流引擎 | 已确认 |
| R10 | 每个 formal finding 记录实际 evidence dependency identity/hash，Apply 只对变化影响的 finding 做局部 stale 复核 | 证据变化不应静默，也不应无条件重跑整轮审查 | 已确认 |
| R11 | 默认不向目标 plan 写 ledger 路径或 review report | provenance 留在 ledger 与聊天；只有项目模板、稳定导出或 owner 明确要求时才写摘要 | 已确认 |
| R12 | Eval 采用 prototype、evaluable candidate、default rollout 三阶段 gate | 先保护安全与关键质量，再以预声明样本、容差和风险权重决定推广 | 已确认 |
| R13 | 其他 7 个 gstack skills 的 deprecated 迁移是独立 release workstream，不阻塞 prototype 或候选 eval | 安装面治理与审查内核验证没有技术依赖 | 已确认 |
| R14 | 横切工程判断与五维聚焦规则都必须保留；横切 rubric 应用于每个 candidate/finding，聚焦 reference 只叠加观察面 | 原 skill 的能力分散在主文档和 section 中，只迁移 section 短清单会系统性丢失工程经理判断力 | 已确认 |

## 5. Runtime 切割与质量替代矩阵

| 原能力 | 原作用 | 新 skill 处理 | 对质量的保护 |
| --- | --- | --- | --- |
| `gstack-config` | feature flags 与交互偏好 | 删除；用 invocation 中的 `mode` 和 skill 默认值代替 | 行为直接可见，不依赖隐藏全局状态 |
| `gstack-review-log/read` 与 dashboard | 审查状态、时效和 `/ship` readiness | 删除；在 ledger 与聊天摘要中记录本轮状态、基线和未决项 | 保留审计与 stale 判断，不保留 gstack dashboard 或默认污染目标 plan |
| `gstack-decision-log/search` | 跨 session 架构决策 | 用 ledger 的“已有决策”和“本轮决策”区替代；优先读取目标 package 内现有 design/spec/plan | 避免重复争论和无意推翻既有契约 |
| GBrain / brain cache | 产品背景和近期决定 | 改为定向读取目标 plan、相邻 design/spec、项目指令和明确引用的架构资料 | 上下文与当前任务绑定，避免加载无关记忆 |
| `gstack-learnings-*` | 复用历史坑和校准 | 可选读取新 skill 的 `rubric.md` 或未来 `review-memory.md`；首版不做自动写回 | 不把长期学习作为首版硬依赖 |
| `gstack-question-preference/log` | 重复问题自动选择 | 由本轮 evidence、同轮可比较的 confidence 和 owner gate policy 替代；owner 始终可 override | 自动化基于本次证据，不依赖隐藏偏好或固定 Judge |
| Codex probe / Outside Voice | 独立模型挑战 | 每轮使用 fresh 独立上下文只读运行；不可用时明确标记 degraded | 保留第二视角的漏检防护，且不伪造独立能力 |
| test-plan artifact | 给 QA 提供验收输入 | 行为变更默认在 ledger 产出 coverage map；复杂关系升级 test diagram，也可按 owner 要求导出到稳定 package docs | 保留测试和人工验收的可复用输入 |
| tasks JSONL / `/autoplan` | 下游任务聚合 | 首版删除；final report 只输出普通 Implementation Tasks | 不影响 finding 质量，减少生态耦合 |
| telemetry、timeline、artifact sync | 使用分析、历史顺序、跨设备同步 | 删除 | 对单次审查判断无直接影响 |
| checkpoint mode、vendoring、first-run onboarding | gstack 运维与安装体验 | 删除 | 与 plan review 无关，删除可减少中断和冲突 |
| review chaining | 推荐 CEO、Design、QA、Ship 等后续流程 | 改为非阻塞的一句话建议；不自动启动其他 skill | 避免新 skill 成为总编排器 |

## 6. 目标目录结构

```text
skills/eng-plan-review/
  SKILL.md
  agents/
    openai.yaml
  references/
    scope-review.md
    architecture-review.md
    code-quality-review.md
    test-review.md
    performance-review.md
    decision-policy.md
    ledger-records.md
    final-report.md
    subagent-prompts.md
  scripts/
    review_ledger.py
    test_review_ledger.py
  evals/
    evals.json
  rubric.md

docs/skill-design/independent-eng-plan-review/
  README.md
  independent-eng-plan-review-skill-plan.md
  parity-matrix.md
  eval-notes/                       # 按需创建，设计期临时材料
```

`SKILL.md` 只保留触发条件、目标绑定、薄工作流、安全边界、materiality 路由、Review/Apply 边界和 fallback 原则。目标控制在 150–250 行，并保持在 500 行上限以内。

每个 review reference 应只描述一个维度的检查项、finding 输出和完成条件。materiality scan 判定需要深入某维度时才读取对应 reference；`final-report.md` 只在形成 owner 摘要或 Apply 输出时按需加载。

`review_ledger.py` 只负责基线 identity/hash、合法 resolution、与 exact manifest hash 绑定的 owner Apply 来源、materiality/finding 一致性、未决集合、原子写入、异常锁恢复、stale 检测和单目标 guarded Apply，不做技术判断、角色编排、问题树或分支调度。脚本应使用 Python 标准库并跨 Windows/macOS/Linux 工作。

`docs/skill-design/independent-eng-plan-review/` 不会被正式 skill 在运行时读取。`parity-matrix.md` 是设计与 eval 的 traceability 工件；实现完成后可以保留为维护资料，也可以在 owner 确认不再需要后归档。

## 7. 顶层工作流

```text
明确目标并绑定目标/契约基线
        |
        v
五维 materiality scan
        |
        v
聊天报告本轮角色与工具选择
        |
        v
按材料风险执行 section review，并收集两级 findings
        |
        +--> 风险触发 fresh Judge / Critic / Section Reviewer
        |
        v
每轮 mandatory fresh Outside Voice
        |
        v
独立分支继续收集；必要决定按少量依赖波次询问
        |
        v
展示最终 decision manifest + hash
        |
        v
owner 单次明确 apply 授权
        |
        v
验证基线与 evidence dependencies，局部复核 stale findings 后一次性更新目标 plan
```

### 7.1 目标绑定

- 用户已经给出唯一存在的文件或目录时，直接绑定，不再强制询问 A/B/C。
- 没有目标、存在多个合理目标、目标不存在或 branch diff 与 plan file 意图冲突时，才向用户询问。
- 新 skill 默认审查 plan 文档或 plan package；纯代码 diff 应路由到 code review，而不是扩大本 skill 边界。

### 7.2 Scope Challenge

Scope Challenge 保留以下问题：现有能力复用、最小完整变更、跨边界数量、新基础设施、分发要求、TODO 阻塞、完整度与可逆性。

不再使用“超过 8 个文件或 2 个 class/service 就必须停止”的单一阈值。改为综合判断：新 contract、跨层数量、不可逆性、独立 owner、迁移窗口和验证成本。复杂度较高但由完整验收真实要求的计划不应仅因文件数量被迫缩减。

### 7.3 Finding 合同

探索期 candidate 只需记录足以支持继续调查的最小信息：

```yaml
id: ENG-A1
section: scope | architecture | code-quality | tests | performance
claim: suspected gap or risk
preliminary_evidence_or_reasoning: concise basis for investigation
risk: concrete failure or maintenance cost
```

只有晋升为 formal finding 后才补齐：

```yaml
severity: P0 | P1 | P2 | P3
confidence: comparable expression within this review run
evidence:
  - kind: direct-quote | absence-proof | repository-fact | contract-conflict | primary-source | inference
    identity: stable evidence source identity
    hash: content hash used by this finding
    file: path/to/file
    line: 42
    quote: motivating source text
    search_scope: bounded files or directories checked for an absence
    expected: contract or behavior that should exist
    observed: what was actually found
recommendation: one concrete change
owner_gate: required | not_required
decision_class: engineering-fact | owner-intent | risk-tolerance | contract-change | irreversible
resolution: pending
```

正式 finding 必须有可核验 evidence，但不强制每一种 evidence 都有正向原文。`direct-quote`、`repository-fact` 和 `contract-conflict` 应引用具体文件与行号；当 finding 指向计划中缺失的 rollback、distribution、auth boundary、failure handling 等内容时，可以用 `absence-proof` 记录有界搜索范围、预期契约和实际未发现的内容。每个 formal finding 还必须记录实际支撑其结论的 evidence dependency identity/hash。只有无直接证据、无有界缺失证明且主要依赖推断的候选才进入观察区，不能伪装成 formal finding。

`alternatives` 与 dependency 只在存在真实 owner choice 或真实依赖时添加。工程事实或明显缺陷不应为了制造选择而生成伪 alternatives；confidence 可以是数值、等级或自然语言校准，但同一轮必须可比较且不得伪造精度。

### 7.4 自动收敛门槛

Agent 只有在 evidence 可核验、结论属于工程事实、不改变 owner 已批准的产品意图或 contract、且不会代替 owner 承担不可逆风险选择时，才可将 formal finding 归为 `AUTO_CONVERGE`。置信度是判断输入而不是固定数值门槛；高影响自动归纳、证据冲突、不可逆性、跨边界影响或 reviewer 明显不确定时启用 fresh Judge/Critic 复核。

产品意图、风险容忍度、范围或 contract 变化和不可逆决策始终进入 owner gate。其他不确定项按实际依赖影响进入 `DEFER_NONBLOCKING` 或 `USER_REQUIRED_BLOCKING`，不因未创建独立 Judge 而机械降级所有可验证工程事实。

### 7.5 阻塞与依赖判断

以下情况视为阻塞后续：会改变架构边界、数据模型、contract、测试 oracle、范围基线、迁移策略、不可逆操作或后续 finding 的前提。

阻塞项只冻结依赖它的 review branch，Architecture 的未决项不应自动阻止独立的 Test Framework Detection 或既有能力盘点。最终返回时必须列出每个阻塞项冻结了哪些结论。

不确定但非阻塞的项继续记录和审查，最后以编号列表统一交给 owner，支持类似 `1A 2B 3A` 的批量回复。

### 7.6 Batch Decision Protocol（薄指导）

本协议只规定交互边界，不引入独立流程引擎或复杂持久化状态机：

1. **Preflight Ask**：只询问不回答就无法绑定目标或开始有效审查的问题。
2. **Collect**：继续所有不依赖 owner 决定的 review branches，并把待裁决项记录到 ledger。
3. **Decision Waves**：按依赖顺序展示待裁决项；同一波只包含彼此独立的决定，owner 可用 `1A 2B 3A` 批量回复。只有某项冻结多个 material branches、会使大量后续结论失效或涉及不可逆契约时才 early flush。
4. **Validate**：检查漏答、矛盾选择和被上游选择失效的下游选择；必要时只重问受影响项，不重放整轮 review。
5. **Manifest-bound Apply**：展示简短 decision manifest 及其 hash，列出自动收敛项、owner 选择、override、未决项和 ledger identity；owner 对该 hash 的一次明确 `apply` 同时完成 ratification 与写入授权。只有 manifest、目标基线或未决集合变化时才重新确认。

如果依赖关系要求多轮问题，优先使用少量拓扑波次，不追求把所有决定强塞进一个批次。该协议的成功指标是减少无价值 owner 往返，同时保持依赖安全，而不是实现更多交互仪式。

## 8. 参考 `grill-me-smartly` 的自治审查计划

本章节独立描述新 skill 如何借用 `grill-me-smartly` 的角色能力、ledger 和覆盖证明。它不是 gstack 或 `grill-me-smartly` 的运行时依赖；新 skill 只复用其经过验证的协作思想，不复刻固定角色编制。

### 8.1 Review Then Apply

审查阶段的唯一持久化输出是 Review Ledger。任何 reviewer、Judge、Critic 或 Outside Voice 都不能直接修改目标 plan。只有 owner 对最终 manifest hash 发出明确 `apply` 授权，Main session 才应用其中已收敛决策和 owner 选择。

### 8.2 角色

- **Main session**：绑定目标、维护 owner gate、汇总 findings 并调用 ledger 安全操作；它可以自行完成材料风险较低的 section review，不需要模拟固定问题树角色。
- **Questioner / Section Reviewer**：在存在可独立并行的材料审查分支时返回 finding candidates；它是按风险启用的逻辑能力，不是每次 invocation 都必须创建的固定 agent 编制。
- **Answerer**：只在事实需要额外调查时启用；它只能读取本地代码、文档、Git 历史和只读工具，不能推断产品意图或风险偏好。
- **Decision Judge / Critic**：高影响自动归纳、证据冲突、不可逆性、跨边界影响或 reviewer 明显不确定时，使用 fresh context 检查 resolution、遗漏、过早收敛和未声明依赖；同一个 fresh reviewer 可以合并 Judge 与对抗检查，不能修改 ledger 或目标 plan。
- **Outside Voice**：每轮必选并使用 fresh agent、不同模型或其他独立上下文，挑战整个计划和主审视角，不能 inline 模拟。首次调用只提供目标、基线和必要契约，不提供主审结论，随后在 owner decision waves 前汇总 tension。

Main session 先加载横切 rubric 与五个短聚焦 reference，再对 Scope、Architecture、Code Quality、Tests 和 Performance 做 materiality scan，并在聊天中简短报告本轮 Outside Voice、Section Reviewer、Judge/Critic 和 coverage map/diagram 的启用或跳过及理由；运行中选择变化时只报告增量，不把角色状态写成恢复协议。加载镜头不等于机械深挖：小计划可 inline 深入 material sections，大计划或 cross-boundary plan 可并行 Section Reviewer，不使用固定文件数阈值。

Outside Voice 每轮都必须在 owner decision waves 之前运行，使 fresh-context tension 能进入同一轮统一裁决。独立能力不可用时可降级交付 findings，但必须报告 `degraded: outside-voice-unavailable`，不得宣称 `fully reviewed` 或 `cleared`。

### 8.3 风险触发的独立复核输出

```yaml
finding_id: ENG-T2
resolution: AUTO_CONVERGE | DEFER_NONBLOCKING | USER_REQUIRED_BLOCKING | REJECT_UNVERIFIED
confidence_assessment: high — direct evidence and no conflicting source found
evidence_sufficient: true
user_intent_required: false
contract_or_scope_change: false
reversible: true
dependency_impact:
  blocks: []
rationale: concise Chinese explanation
recommended_resolution_record: converge | defer | need-user | reject
```

独立复核不能因为推荐项标注为“recommended”就自动接受，也不能把 Question Tuning 的历史偏好当成本轮工程证据。该输出只在风险触发 fresh Judge/Critic 时使用；普通机械 finding 可以由 Main session 依据本轮可审计事实分类，最终仍受 manifest-hash-bound owner Apply 约束。

### 8.4 Ledger 结构

Ledger 默认放在用户 OS 临时目录，避免污染目标仓库，也不进入上述设计资料目录：

```text
<os-temp>/eng-plan-review/<run-id>/ledger.json
```

每个 authoritative JSON ledger 必须记录 `run_id`、repo、branch、HEAD、skill version、规范化目标路径、目标文件 hash、必要相邻契约 hash、创建时间、manifest hash、owner authorization source、Outside Voice 的 `complete/unavailable` 安全状态，以及每个 formal finding 实际使用的 evidence dependency identity/hash。Run ID 使用 UTC timestamp 与随机短标识生成；脚本使用原子写入，同一 run 可以 resume，不同 run 不覆盖。Ledger 属于可清理的临时工件，final summary 必须给出绝对路径；只有用户明确要求导出时才复制到项目文档目录。Markdown 仅可作为可选人类可读导出，不是状态源。

JSON 的逻辑结构：

```text
run + baseline
review_state.outside_voice + degraded
materiality[scope|architecture|code_quality|tests|performance]
findings[id] + evidence_dependencies + resolution
authorization.manifest_hash + owner source
verification.baseline_stale + per-finding stale
```

上述结构只定义可审计记录，不要求脚本管理 Critic 过程、问题树、依赖图或角色调度；这些内容在真实存在时可以作为普通 notes 附加。

### 8.5 覆盖与停止判断

Review 结束前必须为 Scope、Architecture、Code Quality、Tests 和 Performance 每个维度记录“已审查”“不适用及理由”或“存在 finding”，并公开未决项、stale findings 与能力降级。所有 material branches 已收敛、或剩余问题已明确进入 owner gate 并列出其真实阻塞范围时即可结束；依赖图和详细停止证明只在关系确实复杂时生成。

行为变更必须检查测试覆盖与 failure modes，并默认生成 coverage map，记录行为、风险、测试层级、oracle 和 failure mode；只有多路径、跨组件或映射关系难以用短列表表达时才升级为 test diagram。Critic 与 Judge 仅在风险触发时参与停止判断，不作为每轮固定门禁。

### 8.6 Owner 快速审阅面

最终回复只向 owner 展示三组信息：

1. 审查侧已自动收敛：结论、证据和影响，尚未 apply，owner 可 override。
2. 待统一批准：编号、选项和推荐，owner 可用 `1A 2B 3A` 一次回复。
3. 阻塞项：为什么必须决定、冻结了哪些后续结论。

自动收敛的完整过程仍保留在 ledger 中，但不把所有 Questioner/Answerer 内部往返复制到聊天主界面。

### 8.7 Subagent 不可用时的 fallback

当 host 不支持 subagent 或用户禁止 delegation 时，Main session 可以按相同合同 inline 执行 material section review 和事实调查，但必须：

- 在 ledger 标记 `review_mode: inline-fallback`。
- 不声称存在独立 Judge、Critic 或 Outside Voice；Outside Voice 直接标记 unavailable，不能由 Main session 模拟，最终 verdict 必须 degraded 且不能使用 `fully reviewed` 或 `cleared`。
- 需要独立复核的高风险 finding 保持未决或交给 owner；不因缺少独立 Judge 而全面禁止对证据充分、局部可逆的工程事实进行分类。Mandatory regression test requirement 可以继续标记为不可省略的质量要求，但仍不能在 review phase 自动修改目标 plan。
- 在聊天中照常报告本轮启用或跳过的角色与工具及理由。

## 9. 输出与 Apply 合同

Review 阶段输出：

- OS 临时目录中的 Review Ledger。
- 聊天中的 owner 快速审阅摘要。
- 可核验的 decision manifest 及其 hash；它包含 ledger identity 和本次授权覆盖的 resolution 集合。
- 不修改目标 plan。

Apply 阶段输出：

- 只应用 owner 对 manifest hash 发出的单次明确 `apply` 授权；manifest 可以包含审查侧归类的 `AUTO_CONVERGE`、owner 已选择项和 override 后的最终选择。manifest、目标基线或未决集合变化时授权失效。
- 保留未决项，不以 recommended 代替批准。
- 重新验证目标基线和 manifest 引用的 evidence dependencies；证据变化只使关联 findings stale，并要求局部复核，不无条件重跑整轮 review。
- 默认不向目标 plan 写 ledger 路径或 review report。只有项目模板要求、ledger 已导出到稳定位置或 owner 明确要求时才写摘要；摘要使用稳定 `run_id`，不写 OS-temp 路径。

## 10. Progressive Disclosure 路由

| 阶段 | 必读内容 | 不应提前加载 |
| --- | --- | --- |
| 启动、目标绑定与 materiality scan | `SKILL.md` | 未判定为 material 的详细 references、final report |
| Materiality scan | `rubric.md`、五个短聚焦 reference、目标与必要 contract | 聚焦维度之外的扩展资料 |
| Material section review | material 维度的必要项目资料、`decision-policy.md` | 不适用 section 的扩展调查 |
| Mandatory Outside Voice | `subagent-prompts.md` 中 Outside Voice 部分、目标、基线和必要契约 | 主审 findings 与最终推荐，直到首次独立观察完成 |
| 风险触发独立复核 | `subagent-prompts.md` 中 Judge/Critic 部分、相关 candidates/evidence | 不相关 section 的完整正文 |
| Owner 摘要与 decision waves | `final-report.md`、最新 ledger | 已完成 section 的完整正文 |
| Apply | 最新 ledger、manifest hash、目标 plan、实际 evidence dependencies、`final-report.md` | Questioner/Answerer prompt |

`decision-policy.md` 是唯一的 finding 分类和 owner gate 来源。各 section 不重复 AskUserQuestion、STOP、confidence 或 apply 规则，只引用该 policy。

设计期 `parity-matrix.md` 不属于 progressive disclosure 路由，也不会被正式 skill 读取。它只用于证明旧语义如何被 preserve、adapt 或 drop，并把每个保留能力映射到对应 eval。

## 11. 实施阶段

### 独立 Release Workstream：缩减现有 gstack skill 安装面

- 审计当前 `skills/gstack/` 中 8 个 skill 的安装、registry、文档和测试引用。
- 保留现有 `skills/gstack/plan-eng-review/` 活跃，将其他 7 个 gstack skills 迁移到统一 deprecated 区；具体路径和 installer 暴露规则在执行前按现有 registry 结构确定。
- 同步更新 `install.sh`、`install.ps1`、`tests/install.ps1`、README 和相关 registry；deprecated skills 默认不再安装，但保留源码和恢复说明；registry 变更后运行 `verify-registry-state`。
- 此工作线是独立仓库治理变更，不修改现有 `plan-eng-review` 内容，也不与新 skill 实现混在同一提交；它只作为默认 rollout 前置条件，不阻塞 prototype、evaluable candidate 或候选 eval 反馈。

完成条件：默认安装面只暴露现有 `plan-eng-review`；其他 7 个 gstack skills 可在 deprecated 区审计和恢复；跨 host installer 测试通过。

### Phase 1：创建独立骨架

- 使用 `skill-creator` 创建 `skills/eng-plan-review/` 骨架、精简 `SKILL.md`、按需 references、`agents/openai.yaml`、ledger 脚本和 rubric。
- Frontmatter 明确触发语义：用户要求审查、锁定、挑战或批准 implementation plan 时使用；纯代码 diff 和产品战略 review 不应触发。
- 不引用 `~/.gstack`、`~/.claude/skills/gstack`、gstack commands 或其他 gstack skills。

完成条件：`SKILL.md` 少于 250 行；所有阶段有明确 reference 路由；静态搜索无 gstack runtime 路径。

### Phase 2：实现审查内核

- 编写 Scope、Architecture、Code Quality、Tests、Performance 短 references；每轮全部加载观察镜头，由 materiality scan 决定仓库调查、图示、角色和输出深度。
- 用 `rubric.md` 承载 goal/contract/outcome、完整 slice、blast radius、reversibility、ownership、failure learning、change sequencing、reliability 和 DX 等横切镜头，并确保聚焦 reference 不会替代这些镜头。
- 保留 evidence gate、confidence calibration、regression exception、coverage map、复杂场景 test diagram、failure modes、NOT in scope 和 What already exists。
- 明确哪些 outputs 是 always、conditional 和 optional，避免所有计划都生成全部仪式性产物。

完成条件：给定一个完整 plan，每个维度都有 materiality 状态；每个 material candidate 都能从 goal/contract 追踪到 consumer、user/operator outcome 与 verification oracle；inline 模式能深入材料维度并生成两级 findings，行为变更能生成 coverage map 并按复杂度升级 diagram。

### Phase 3：实现 Ledger 安全内核与独立审查工具

- 首个可运行版本即实现最小标准库 Python `review_ledger.py`，不先用自由格式 Markdown 代替状态约束。脚本只支持 `init`、`record`、`authorize`、`verify` 和 `status`，保护基线 identity/hash、合法 resolution、与 exact manifest hash 绑定的 owner Apply source、materiality/finding 一致性、未决集合、原子写入、异常锁恢复和 stale 检测；`verify --apply-output` 为单目标 plan 提供 guarded Apply，不增加新的 workflow command。
- 编写 mandatory Outside Voice prompt，以及风险触发的 Judge/Critic/Section Reviewer prompts；每轮角色与工具选择只在聊天报告，不进入脚本状态机。
- 依赖和 alternatives 只在真实存在时记录；复杂 dependency graph 由 agent 按需构建，不成为脚本必经状态。

完成条件：ledger 安全不变量可测试；没有结构化 owner Apply 来源或 exact manifest hash 不匹配时不能 authorize，materiality 与 findings 矛盾时拒绝授权，manifest 或基线变化使授权失效，evidence dependency 变化只使关联 finding stale，空/截断 stale lock 可恢复，guarded Apply 在完整目标 hash 不匹配时零写入停止；脚本不含角色编排、Critic 或 stop 子命令。

### Phase 4：实现 Review Then Apply

- 审查结束只输出 ledger 与摘要。
- `apply` 时先在 OS temp 生成完整 proposed plan，再由 `verify --apply-output` 在 ledger/目标锁内重新读取 ledger、manifest、目标 plan 和 evidence dependencies，执行完整目标 hash precondition 与同目录原子替换；baseline 不匹配时零写入停止，并保留 preimage backup 供异常恢复。
- 只应用 owner 对 manifest hash 单次明确授权的最终 resolution；首版 guarded Apply 只支持单一目标 plan，多目标 package 保持未写入并要求 owner 拆分或选择目标；默认不追加 engineering review report，只有项目模板、稳定导出或 owner 明确要求时才写稳定摘要。

完成条件：目标 plan 在 review phase 保持 byte-identical；apply phase 对已批准决定可重复执行或明确拒绝重复应用。

### Phase 5：分阶段 Eval 与精简

- 用原 `plan-eng-review` 作为行为基线，新 skill 作为候选版本。
- 先在设计目录的 `parity-matrix.md` 中把旧规则映射为 preserve、adapt 或 drop，并为保留项分配 eval ID；该矩阵不进入正式 skill。
- 对同一组 plan 使用固定 owner answer script 运行旧版与新版，以人工裁决的 union/golden findings 作为 oracle，而不是把旧 skill 输出直接视为真值。
- Prototype gate 只验证安全不变量与关键功能用例，不由完整质量/成本比较阻断。
- 成为 evaluable candidate 前，对代表性 P1/P2 与 test-gap 用例执行一次小规模 blind comparison，防止因为新版更短就主观判定更好。
- 首轮 blind comparison 及由失败到修订的闭环记录在 `eval-notes/2026-07-20-prototype-blind-comparison.md`；该记录证明 candidate gate，不代表 default rollout gate。
- 默认 rollout 或 deprecated 旧版前，才按预声明样本、容差和风险权重比较 severity-weighted finding recall、false positives、evidence validity、owner 交互次数、aggregate tokens、全部 agent 工具调用、wall time 和未决项透明度。
- 根据 eval 删除没有贡献的规则，不为单个测试样本增加过拟合指令。

完成条件：prototype 通过安全与关键功能用例；evaluable candidate 完成代表性 blind comparison；只有 default rollout gate 才要求完整质量与成本指标落在预声明容差内，不要求所有维度零容差支配旧版；所有自动决策可由 ledger 审计。

## 12. Eval 计划

首轮至少覆盖以下场景：

| 场景 | 预期行为 |
| --- | --- |
| 用户给出唯一 plan 路径 | 直接绑定目标，不再询问 A/B/C |
| 用户只说“审查这个计划”但有多个候选 | 请求一次目标澄清，不读取或修改候选 plan |
| 高置信度、局部、可逆的测试接线缺口 | Agent 依据 evidence 自动归纳并记录，owner 摘要可 override；不因未创建 Judge 而机械降级 |
| 中等置信度且不阻塞后续的性能担忧 | 记录为待统一批准并继续其他 review branch |
| 会改变 REST contract 的架构建议 | 标为 owner-required blocking，冻结依赖结论 |
| 产品意图或风险偏好问题 | 不由 reviewer 代判，返回 owner gate |
| 已确认 regression 缺少测试 | 自动加入 critical test requirement，并记录 regression exception |
| Subagent 不可用 | 使用 inline fallback，诚实标记 Outside Voice unavailable 与 degraded，不伪造独立角色且不能给出 fully reviewed/cleared verdict |
| Outside Voice 与主审冲突 | 每轮在 decision waves 前记录 tension，不自动修改 plan |
| 简单行为变更 | 默认产出 behavior/risk/test level/oracle/failure mode coverage map，不强制 diagram |
| 多路径跨组件行为变更 | coverage map 难表达关系时升级为 test diagram |
| Review 后 plan 被外部修改 | Apply 检测 stale baseline，使授权失效并要求重新确认 |
| Formal finding 的证据源变化 | 只将关联 finding 标为 stale 并局部复核，不重跑整轮 |
| 无未决项且 Outside Voice 成功 | ledger/chat 摘要可给出 cleared verdict，目标 plan 默认不追加 report |
| 有未决项或能力降级 | ledger/chat 列出未决或 degraded 状态，不能给出 cleared verdict |
| 每轮角色配置 | 聊天报告 Outside Voice、Section Reviewer、Judge/Critic 和 coverage map/diagram 的启用或跳过及理由，不要求恢复状态 |

建议的量化指标：

- Core finding recall 与 false-positive rate：在 default rollout gate 按预声明样本、风险权重和容差比较，不要求每个维度零容差支配旧 skill。
- Evidence completeness：正式 finding 100% 有直接引用或有界 `absence-proof` 等可核验证据。
- User interruptions：在相同独立 findings 集合下显著少于旧 skill。
- Runtime context：实际加载内容显著低于旧 skill 的约 121 KB 执行面。
- Aggregate runtime：包括 Main session、Section Reviewers、Judge、Critic 和 Outside Voice 在内的总 tokens、工具调用和 wall time 均受控；不能只把成本从主上下文搬到 subagents。
- Unauthorized apply：0。
- Silent unresolved decisions：0。

## 13. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 删除 GBrain 后丢失既有决定 | 重新争论或产生矛盾 | 强制读取 plan package 中的 design/spec、已有 ledger 和 project instructions |
| Agent 过度自动归纳 | 未经 owner 同意改变范围或 contract | 正式 finding evidence gate；用户意图、contract 和不可逆项永远进入 owner gate；高影响情形触发 fresh Judge/Critic |
| 多 reviewer 输出重复或冲突 | ledger 噪声和错误依赖 | Main session 统一 deduplicate；证据冲突时触发 fresh Judge/Critic |
| Subagent 不可用 | Outside Voice 独立性缺失 | inline fallback 明确 degraded，不伪造 outside evidence，禁止 fully reviewed/cleared verdict |
| 新 skill 与旧 skill 行为漂移 | 关键检查被遗漏 | 建立旧版基线 eval 和 blind comparison，按 finding recall 验收 |
| Ledger script 变成新的重型 runtime | 再次产生复杂依赖 | 脚本只做确定性状态管理，技术判断全部留在 references 和 agent roles |
| 临时 ledger 丢失 | 长 session 无法恢复 | final summary 给出绝对路径；未来可选显式导出到用户指定 docs，但不默认污染仓库 |
| 多角色编制抵消 runtime 精简收益 | 总 tokens 和 wall time 高于旧版 | 小计划 inline material sections；Judge/Critic/Section Reviewer 按风险触发；Outside Voice 每轮只做独立挑战；eval 统计 aggregate cost |
| 批量裁决包含依赖冲突 | owner 一次回复产生不一致 plan | 只合并独立决定；按少量拓扑波次展示；单次 Apply 授权前校验 decision manifest hash |
| Evidence dependency 在 Review 后变化 | 已有 finding 依据失效 | 每个 formal finding 记录实际 evidence identity/hash，只局部复核受影响 finding |

## 14. 已确认的实现默认值

1. 最终 skill 名称使用 `eng-plan-review`。
2. Outside Voice 每轮必选并使用 fresh context；不可用时必须标记 degraded，且不能给出 `fully reviewed` 或 `cleared` verdict。
3. 首个可运行版本立即实现最小 `review_ledger.py`，不使用自由格式 Markdown 替代核心状态约束。
4. 新旧 Eng Review skill 在 eval 阶段共存；新版通过验收后，旧版先标记 deprecated 并保留迁移周期，不立即删除。
5. Batch Decision Protocol 保持薄指导，只规定提问时机、依赖波次、回复校验和 manifest-hash-bound 单次 Apply 授权。
6. 设计期 parity matrix 和 eval 临时材料只保存在 `docs/skill-design/independent-eng-plan-review/`，不进入正式 skill 运行时。
7. Runtime ledger 始终保存在用户 OS temp；设计资料目录不接收运行时 ledger。
8. 另外 7 个 gstack skills 的 deprecated 迁移作为独立 release workstream，只在 default rollout 前完成，不阻塞 prototype 或候选 eval。

## 15. Definition Of Done

只有满足以下条件，独立 skill 创建任务才算完成：

- 独立目录、`SKILL.md`、references、ledger、脚本测试和 prototype/candidate eval 都已落盘。
- 运行时不依赖 gstack commands、paths、skills、dashboard 或 user-level gstack state。
- 核心工程审查能力与 evidence gate 未被削弱；横切 rubric 与五维聚焦规则分别可触发且共同作用于 material candidates。
- 两级 finding、五维 materiality、coverage map/diagram 分级、owner gate 和未决透明度均有测试。
- 每个 ledger 具有唯一 run identity、基线 hashes、formal finding evidence dependency hashes 和原子写入保证；运行时 ledger 不进入仓库或设计资料目录。
- Review phase 不修改目标 plan；Apply phase 只接受 owner 对当前 manifest hash 的单次明确授权，并在写入前验证目标与 evidence dependencies。
- Subagent 与 inline fallback 的声明和证据真实一致。
- Outside Voice 每轮保持 fresh context；Judge、Critic 和 Section Reviewer 按风险启用；每轮角色与工具选择均在聊天报告，inline fallback 不伪造独立能力且使用 degraded verdict。
- Batch Decision Protocol 能校验实际存在的依赖、矛盾和漏答，并以 manifest-hash-bound 单次 Apply 授权收口。
- Prototype 通过安全不变量和关键功能用例；evaluable candidate 完成代表性 P1/P2 与 test-gap blind comparison。
- 设计期 parity matrix 已覆盖旧 skill 的保留、适配和删除语义，并映射到 eval ID，但不进入正式 skill 执行面。
- Default rollout 前的完整质量与成本 eval 使用预声明样本、容差和风险权重，owner 据此确认是否推广并 deprecated 旧版；该 rollout gate 不阻塞 prototype 完成。
