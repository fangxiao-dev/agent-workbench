# 独立工程计划审查 Skill 设计与实施计划

日期：2026-07-13

状态：设计方案已对齐，尚未创建 skill 实现

工作名称：`eng-plan-review`（最终名称可在实现前调整）

## 1. 背景与问题

现有 `plan-eng-review` 同时承载工程审查内核、gstack 运行时初始化、跨 session 记忆、问题偏好、telemetry、artifact sync、review dashboard、下游 skill chaining、Outside Voice、任务 JSONL 和 plan report 等职责。生成后的 `SKILL.md` 与 `review-sections.md` 合计 1,973 行、约 121 KB，而对应模板合计 381 行、约 28.7 KB；约 76.3% 的生成内容来自公共运行时注入。

这导致三个直接问题：单次审查需要加载过多与当前判断无关的指令；重复的 STOP、AskUserQuestion 和兼容分支增加规则冲突；工程师必须通过大量线性交互才能完成一个本可自动收敛的审查。

本计划不在原 gstack skill 上继续裁剪，而是提取其有效审查语义，创建一个 host-neutral、无 gstack runtime 依赖、渐进加载的新 skill。原 `plan-eng-review` 保持不动，作为行为基线和 A/B 对照对象。

## 2. 目标

新 skill 应在不降低工程审查质量的前提下实现以下能力：

- 审查明确的 implementation plan、technical plan 或 plan package。
- 保留 Scope、Architecture、Code Quality、Tests、Performance 五个审查阶段。
- 每个正式 finding 必须有严重度、置信度、文件与行号、原文证据、风险和推荐。
- 使用独立 Judge 判断哪些结论可自动收敛，哪些需要记录后继续，哪些会阻塞后续，哪些必须由 owner 决定。
- 使用 review ledger 保存问题、证据、自动决策、用户决策、依赖和停止证明。
- Review 与 Apply 分离；审查阶段不修改目标 plan，只有 owner 明确要求 `apply` 后才写回。
- 在 subagent 不可用时仍可 inline 完成同等审查，并明确记录 fallback，不能伪称完成了独立复核。
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
| D1 | 创建独立新 skill，不继续直接修改生成后的 `plan-eng-review` | 原 skill 受 gstack 生成器和 runtime 约束，直接删改容易被覆盖且难以真正独立 | 已确认 |
| D2 | 去除 gstack runtime，但保留影响质量的语义并提供轻量替代 | telemetry、sync、dashboard 不决定 finding 质量；decision memory、Outside Voice、test plan 和 final gate 需要重建 | 已确认 |
| D3 | 使用 progressive disclosure，把各审查阶段拆到独立 reference | 当前单个 923 行 section 使渐进加载名存实亡 | 已确认 |
| D4 | 引入独立 Judge 的置信度与依赖分类 | 高置信度工程事实可自动收敛；不确定项按阻塞性处理，减少无价值往返 | 已确认 |
| D5 | Review 与 Apply 分离 | 自动决策先进入 ledger，owner 可审计和 override；只有明确 `apply` 后修改目标 plan | 已确认 |
| D6 | 参考 `grill-me-smartly` 的 ledger、角色分工和停止证明，并在本文使用独立章节描述 | 保留自动研究和可审计决策，同时避免主 session 重新垄断问题树 | 已确认 |
| D7 | 新增本地 skill 内容使用中文，保留必要英文术语 token；Markdown prose 不做固定列宽硬折行 | 遵循 agent-workbench 已确认的全局 skill 写作偏好 | 已确认 |

## 5. Runtime 切割与质量替代矩阵

| 原能力 | 原作用 | 新 skill 处理 | 对质量的保护 |
| --- | --- | --- | --- |
| `gstack-config` | feature flags 与交互偏好 | 删除；用 invocation 中的 `mode` 和 skill 默认值代替 | 行为直接可见，不依赖隐藏全局状态 |
| `gstack-review-log/read` 与 dashboard | 审查状态、时效和 `/ship` readiness | 删除；在 ledger 与目标 plan report 中记录本轮状态、commit 和未决项 | 保留审计与 stale 判断，不保留 gstack dashboard |
| `gstack-decision-log/search` | 跨 session 架构决策 | 用 ledger 的“已有决策”和“本轮决策”区替代；优先读取目标 package 内现有 design/spec/plan | 避免重复争论和无意推翻既有契约 |
| GBrain / brain cache | 产品背景和近期决定 | 改为定向读取目标 plan、相邻 design/spec、项目指令和明确引用的架构资料 | 上下文与当前任务绑定，避免加载无关记忆 |
| `gstack-learnings-*` | 复用历史坑和校准 | 可选读取新 skill 的 `rubric.md` 或未来 `review-memory.md`；首版不做自动写回 | 不把长期学习作为首版硬依赖 |
| `gstack-question-preference/log` | 重复问题自动选择 | 由 Judge 的 evidence/confidence/dependency policy 替代；owner 始终可 override | 自动化基于本次证据，不依赖隐藏偏好 |
| Codex probe / Outside Voice | 独立模型挑战 | 保留概念；直接使用可用的独立 subagent 或 Codex，只读运行；不可用时明确 fallback | 保留第二视角的漏检防护 |
| test-plan artifact | 给 QA 提供验收输入 | 作为 ledger 的独立 Test Plan 区，或写入用户指定的 package docs | 保留测试和人工验收的可复用输入 |
| tasks JSONL / `/autoplan` | 下游任务聚合 | 首版删除；final report 只输出普通 Implementation Tasks | 不影响 finding 质量，减少生态耦合 |
| telemetry、timeline、artifact sync | 使用分析、历史顺序、跨设备同步 | 删除 | 对单次审查判断无直接影响 |
| checkpoint mode、vendoring、first-run onboarding | gstack 运维与安装体验 | 删除 | 与 plan review 无关，删除可减少中断和冲突 |
| review chaining | 推荐 CEO、Design、QA、Ship 等后续流程 | 改为非阻塞的一句话建议；不自动启动其他 skill | 避免新 skill 成为总编排器 |

## 6. 目标目录结构

```text
skills/eng-plan-review/
  SKILL.md
  references/
    scope-review.md
    architecture-review.md
    code-quality-review.md
    test-review.md
    performance-review.md
    decision-policy.md
    final-report.md
    subagent-prompts.md
  assets/
    review-ledger-template.md
  scripts/
    review_ledger.py
  evals/
    evals.json
  rubric.md
```

`SKILL.md` 只保留触发条件、目标绑定、顶层状态机、阶段路由、Review/Apply 边界和 fallback 原则。目标控制在 150–250 行，并保持在 500 行上限以内。

每个 review reference 应只描述一个阶段的检查项、finding 输出和完成条件。执行某阶段前才读取对应 reference；`final-report.md` 只在全部 review branch 停止后加载。

`review_ledger.py` 只负责确定性地初始化、追加和校验 ledger，不做技术判断。脚本应使用 Python 标准库并跨 Windows/macOS/Linux 工作。

## 7. 顶层工作流

```text
明确目标或解析歧义
        |
        v
加载 plan + 必要相邻契约
        |
        v
Scope Challenge
        |
        v
Architecture / Code Quality / Tests / Performance findings
        |
        v
独立 Judge 分类与依赖分析
        |
        +--> AUTO_CONVERGE ----------> 写入已收敛决策
        |
        +--> DEFER_NONBLOCKING ------> 写入待统一批准，继续其他分支
        |
        +--> USER_REQUIRED_BLOCKING -> 冻结依赖分支，继续独立分支
        |
        +--> REJECT_UNVERIFIED ------> 写入驳回原因，不进入正式 findings
        |
        v
Critic 检查遗漏与过早收敛
        |
        v
停止证明 + owner 快速审阅
        |
        v
owner 明确 apply
        |
        v
一次性更新目标 plan 并验证 final report
```

### 7.1 目标绑定

- 用户已经给出唯一存在的文件或目录时，直接绑定，不再强制询问 A/B/C。
- 没有目标、存在多个合理目标、目标不存在或 branch diff 与 plan file 意图冲突时，才向用户询问。
- 新 skill 默认审查 plan 文档或 plan package；纯代码 diff 应路由到 code review，而不是扩大本 skill 边界。

### 7.2 Scope Challenge

Scope Challenge 保留以下问题：现有能力复用、最小完整变更、跨边界数量、新基础设施、分发要求、TODO 阻塞、完整度与可逆性。

不再使用“超过 8 个文件或 2 个 class/service 就必须停止”的单一阈值。改为综合判断：新 contract、跨层数量、不可逆性、独立 owner、迁移窗口和验证成本。复杂度较高但由完整验收真实要求的计划不应仅因文件数量被迫缩减。

### 7.3 Finding 合同

每个候选 finding 必须包含：

```yaml
id: ENG-A1
section: architecture | code-quality | tests | performance
severity: P0 | P1 | P2 | P3
confidence: 1-10
evidence:
  - file: path/to/file
    line: 42
    quote: motivating source text
risk: concrete failure or maintenance cost
recommendation: one concrete change
alternatives:
  - option: A
    tradeoff: ...
decision_class: engineering-fact | user-intent | risk-tolerance | contract-change
depends_on: []
blocks: []
reversible: true
resolution: pending
```

没有可引用原文证据的 finding 最高只能标为中等置信度，不能进入阻塞主报告；它可以进入 ledger 的观察区供 Critic 审计。

### 7.4 自动收敛门槛

只有同时满足以下条件，Judge 才能使用 `AUTO_CONVERGE`：

- confidence 至少为 9/10。
- 有直接文件/行号/原文证据。
- 属于工程事实，不涉及产品意图、风险容忍度或审美偏好。
- 不改变已批准的 Design/Spec、REST/NATS 边界、验收要求或外部 contract。
- 不减少测试覆盖或 failure handling。
- 修改局部、可逆且不会造成外部副作用。
- 不与其他 finding 或已有决策冲突。
- 推荐方案明显优于替代方案，而不是纯 taste call。

高置信度本身不等于自动批准；门槛中的任一条件不满足，都必须进入 `DEFER_NONBLOCKING` 或 `USER_REQUIRED_BLOCKING`。

### 7.5 阻塞与依赖判断

以下情况视为阻塞后续：会改变架构边界、数据模型、contract、测试 oracle、范围基线、迁移策略、不可逆操作或后续 finding 的前提。

阻塞项只冻结依赖它的 review branch，Architecture 的未决项不应自动阻止独立的 Test Framework Detection 或既有能力盘点。最终返回时必须列出每个阻塞项冻结了哪些结论。

不确定但非阻塞的项继续记录和审查，最后以编号列表统一交给 owner，支持类似 `1A 2B 3A` 的批量回复。

## 8. 参考 `grill-me-smartly` 的自治审查计划

本章节独立描述新 skill 如何借用 `grill-me-smartly` 的角色分工、ledger 和停止证明。它不是 gstack 或 `grill-me-smartly` 的运行时依赖；新 skill 只复用其经过验证的协作思想。

### 8.1 Review Then Apply

审查阶段的唯一持久化输出是 Review Ledger。Questioner、Answerer、Judge 和 Critic 都不能直接修改目标 plan。Main session 只有在 owner 阅读 ledger 并明确要求 `apply` 后，才应用已收敛决策和用户批准项。

### 8.2 角色

- **Main session**：orchestrator、scribe 和 user-intent gatekeeper；唯一允许通过 `review_ledger.py` 写 ledger 的角色。
- **Questioner / Section Reviewer**：维护每个 review branch 的问题树，每次返回当前最高价值 finding candidate，不回答自己的问题。
- **Answerer**：只调查可由本地代码、文档、Git 历史和只读工具回答的事实，不推断产品意图或风险偏好。
- **Decision Judge**：独立读取 candidate、evidence、已有决策和依赖图，输出四类 resolution；不能修改 ledger 或目标 plan。
- **Critic**：在最终停止前检查遗漏、重复、过早收敛、错误自动批准和未声明依赖。

如果并发资源允许，Architecture、Code Quality、Tests 和 Performance Reviewer 可以并行收集 candidates；Judge 必须在 evidence 完整后统一分类，避免不同 reviewer 使用不一致的自动批准标准。

### 8.3 Judge 输出合同

```yaml
finding_id: ENG-T2
resolution: AUTO_CONVERGE | DEFER_NONBLOCKING | USER_REQUIRED_BLOCKING | REJECT_UNVERIFIED
confidence_assessment: 9
evidence_sufficient: true
user_intent_required: false
contract_or_scope_change: false
reversible: true
dependency_impact:
  blocks: []
rationale: concise Chinese explanation
recommended_ledger_action: converge | defer | need-user | reject
```

Judge 不能因为推荐项标注为“recommended”就自动接受，也不能把 Question Tuning 的历史偏好当成本轮工程证据。自动收敛必须由本轮可审计事实支持。

### 8.4 Ledger 结构

Ledger 默认放在 OS 临时目录，避免污染目标仓库：

```text
<os-temp>/eng-plan-review/review-<slug>.md
```

建议结构：

```markdown
# Engineering Plan Review Ledger

## 审查目标与契约基线

## 已有决策

## 已自动收敛决策

## 待 owner 统一批准

## 阻塞项与冻结分支

## 被驳回或低置信度观察

## Architecture Findings

## Code Quality Findings

## Test Coverage And Failure Modes

## Performance Findings

## Critic Check

## 停止证明

## Apply 清单
```

### 8.5 停止证明

只有满足以下任一条件才允许结束 review：

- 所有 material branches 已收敛。
- 剩余问题都已明确标记为 owner intent，并列出其阻塞范围。
- 继续提问只会重复已有 finding 或超出目标 plan 范围。

一个 finding 被自动收敛不代表整个 review 完成。Critic 必须在停止前确认：四个 review sections 都被覆盖、test diagram 已生成、failure modes 已检查、没有静默未决项、没有把用户意图误判为工程事实。

### 8.6 Owner 快速审阅面

最终回复只向 owner 展示三组信息：

1. 已自动采用：结论、证据和影响，owner 可 override。
2. 待统一批准：编号、选项和推荐，owner 可用 `1A 2B 3A` 一次回复。
3. 阻塞项：为什么必须决定、冻结了哪些后续结论。

自动收敛的完整过程仍保留在 ledger 中，但不把所有 Questioner/Answerer 内部往返复制到聊天主界面。

### 8.7 Subagent 不可用时的 fallback

当 host 不支持 subagent 或用户禁止 delegation 时，Main session 可以按相同 schema inline 执行 Section Reviewer、Answerer、Judge 和 Critic，但必须：

- 在 ledger 标记 `review_mode: inline-fallback`。
- 不声称存在独立 Judge 或 Outside Voice。
- 对本可自动收敛但缺少独立判断的 finding 降低自动化强度；涉及 contract、scope 或风险偏好的项仍交给 owner。

## 9. 输出与 Apply 合同

Review 阶段输出：

- OS 临时目录中的 Review Ledger。
- 聊天中的 owner 快速审阅摘要。
- 不修改目标 plan。

Apply 阶段输出：

- 只应用 ledger 中的 `AUTO_CONVERGE`、owner 明确批准项和被 owner override 后的最终选择。
- 保留未决项，不以 recommended 代替批准。
- 在目标 plan 最后追加简化的 `## ENGINEERING REVIEW REPORT`，包含 review mode、findings 数量、自动决策数量、owner 决策数量、未决项、commit 和 verdict。
- report 最后一行必须明确是 `NO UNRESOLVED DECISIONS` 或未决事项列表，避免“看起来已通过但仍有开放决定”。

## 10. Progressive Disclosure 路由

| 阶段 | 必读内容 | 不应提前加载 |
| --- | --- | --- |
| 启动与目标绑定 | `SKILL.md` | 四个详细 review references、final report |
| Scope Challenge | `scope-review.md`、必要项目资料 | Outside Voice、apply 规则细节 |
| Architecture | `architecture-review.md`、`decision-policy.md` | Test/Performance 详细清单 |
| Code Quality | `code-quality-review.md`、`decision-policy.md` | final report |
| Tests | `test-review.md`、`decision-policy.md` | 非测试 section 的重复规则 |
| Performance | `performance-review.md`、`decision-policy.md` | final report |
| Critic 与收尾 | `final-report.md`、`subagent-prompts.md` 中 Critic 部分 | 已完成 section 的完整正文 |
| Apply | 最新 ledger、目标 plan、`final-report.md` | Questioner/Answerer prompt |

`decision-policy.md` 是唯一的 finding 分类和 owner gate 来源。各 section 不重复 AskUserQuestion、STOP、confidence 或 apply 规则，只引用该 policy。

## 11. 实施阶段

### Phase 1：创建独立骨架

- 创建 `skills/eng-plan-review/` 目录、精简 `SKILL.md`、references、ledger template 和 rubric。
- Frontmatter 明确触发语义：用户要求审查、锁定、挑战或批准 implementation plan 时使用；纯代码 diff 和产品战略 review 不应触发。
- 不引用 `~/.gstack`、`~/.claude/skills/gstack`、gstack commands 或其他 gstack skills。

完成条件：`SKILL.md` 少于 250 行；所有阶段有明确 reference 路由；静态搜索无 gstack runtime 路径。

### Phase 2：实现审查内核

- 编写 Scope、Architecture、Code Quality、Tests、Performance references。
- 保留 evidence gate、confidence calibration、regression exception、test coverage diagram、failure modes、NOT in scope 和 What already exists。
- 明确哪些 outputs 是 always、conditional 和 optional，避免所有计划都生成全部仪式性产物。

完成条件：给定一个完整 plan，inline 模式能覆盖所有核心阶段并生成符合 schema 的 findings。

### Phase 3：实现 Ledger 与 Judge

- 实现标准库 Python `review_ledger.py`，支持 init、add-finding、record-evidence、resolve、need-user、reject、critic、stop 和 status。
- 编写 Decision Judge prompt 与自动收敛门槛。
- 支持 dependency graph，只冻结受阻塞分支。

完成条件：ledger 状态转换可测试；没有 owner 批准时脚本不能把 `USER_REQUIRED_BLOCKING` 标为 resolved；stop 必须有证明。

### Phase 4：实现 Review Then Apply

- 审查结束只输出 ledger 与摘要。
- `apply` 时重新读取 ledger 与目标 plan，检测 plan 是否在 review 后发生变化。
- 只应用最终 resolution，并追加 engineering review report。

完成条件：目标 plan 在 review phase 保持 byte-identical；apply phase 对已批准决定可重复执行或明确拒绝重复应用。

### Phase 5：对照 Eval 与精简

- 用原 `plan-eng-review` 作为行为基线，新 skill 作为候选版本。
- 对同一组 plan 运行旧版与新版，比较 finding recall、false positives、owner 交互次数、总 tokens、完成时间和未决项透明度。
- 使用至少一次 blind comparison，防止因为新版更短就主观判定更好。
- 根据 eval 删除没有贡献的规则，不为单个测试样本增加过拟合指令。

完成条件：新版不降低 P1/P2 finding recall 和 test-gap detection；显著减少无价值 owner 往返与运行时 tokens；所有自动决策可由 ledger 审计。

## 12. Eval 计划

首轮至少覆盖以下场景：

| 场景 | 预期行为 |
| --- | --- |
| 用户给出唯一 plan 路径 | 直接绑定目标，不再询问 A/B/C |
| 用户只说“审查这个计划”但有多个候选 | 请求一次目标澄清，不读取或修改候选 plan |
| 高置信度、局部、可逆的测试接线缺口 | Judge 自动收敛并记录证据，owner 摘要可 override |
| 中等置信度且不阻塞后续的性能担忧 | 记录为待统一批准并继续其他 review branch |
| 会改变 REST contract 的架构建议 | 标为 owner-required blocking，冻结依赖结论 |
| 产品意图或风险偏好问题 | Judge 不代判，返回 owner |
| 已确认 regression 缺少测试 | 自动加入 critical test requirement，并记录 regression exception |
| Subagent 不可用 | 使用 inline fallback，诚实标记模式，不伪造独立 Judge |
| Outside Voice 与主审冲突 | 记录 tension，不自动修改 plan |
| Review 后 plan 被外部修改 | Apply 检测 stale baseline 并停止，要求重新确认 |
| 无未决项 | final report 明确 `NO UNRESOLVED DECISIONS` |
| 有未决项 | final report 列出每项及阻塞范围，不能给出 cleared verdict |

建议的量化指标：

- Core finding recall：不低于旧 skill。
- False-positive rate：不高于旧 skill。
- Evidence completeness：正式 finding 100% 有可核验引用。
- User interruptions：在相同独立 findings 集合下显著少于旧 skill。
- Runtime context：实际加载内容显著低于旧 skill 的约 121 KB 执行面。
- Unauthorized apply：0。
- Silent unresolved decisions：0。

## 13. 风险与缓解

| 风险 | 影响 | 缓解 |
| --- | --- | --- |
| 删除 GBrain 后丢失既有决定 | 重新争论或产生矛盾 | 强制读取 plan package 中的 design/spec、已有 ledger 和 project instructions |
| Judge 过度自动批准 | 未经 owner 同意改变范围或 contract | 使用多条件门槛；用户意图、contract 和不可逆项永不自动批准 |
| 多 reviewer 输出重复或冲突 | ledger 噪声和错误依赖 | Judge 统一 deduplicate；Critic 检查冲突与过早收敛 |
| Subagent 不可用 | 独立性下降 | inline fallback 明确降级，不伪造 outside evidence |
| 新 skill 与旧 skill 行为漂移 | 关键检查被遗漏 | 建立旧版基线 eval 和 blind comparison，按 finding recall 验收 |
| Ledger script 变成新的重型 runtime | 再次产生复杂依赖 | 脚本只做确定性状态管理，技术判断全部留在 references 和 agent roles |
| 临时 ledger 丢失 | 长 session 无法恢复 | final summary 给出绝对路径；未来可选显式导出到用户指定 docs，但不默认污染仓库 |

## 14. 待实现前确认

以下事项尚未由 owner 最终裁决，不应在实现时静默假设：

1. 最终 skill 名称使用 `eng-plan-review`、`smart-eng-plan-review` 还是其他名称。
2. Outside Voice 默认开启、默认关闭，还是仅在 P1/P2 或 cross-boundary plan 上自动开启。
3. 首版是否立即实现 `review_ledger.py`，或先用 Markdown ledger 验证流程后再脚本化。
4. 新 skill 通过 eval 后，旧 `plan-eng-review` 是继续共存、标记 deprecated，还是从默认 registry 移除。

## 15. Definition Of Done

只有满足以下条件，独立 skill 创建任务才算完成：

- 独立目录、`SKILL.md`、references、ledger、脚本测试和 eval 都已落盘。
- 运行时不依赖 gstack commands、paths、skills、dashboard 或 user-level gstack state。
- 核心工程审查能力与 evidence gate 未被削弱。
- Autonomous Ledger 的自动收敛、非阻塞记录、阻塞冻结和 owner gate 均有测试。
- Review phase 不修改目标 plan，Apply phase 只应用最终批准决定。
- Subagent 与 inline fallback 的声明和证据真实一致。
- 新旧 skill 对照 eval 证明 finding recall 和 test-gap detection 不下降。
- owner 已审阅 eval 结果并确认新版满足预期。
