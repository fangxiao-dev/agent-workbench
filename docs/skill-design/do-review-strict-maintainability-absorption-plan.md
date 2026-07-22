# `do-review` 严格可维护性审查吸收方案

## 1. 文档状态

- 状态：implementation closed（2026-07-22）；active strict 已退役，叶子 skill 的协作叙述已回收到 `do-review`，严格材料与示例已保真沉淀并通过验证。
- 目标仓库：`agent-workbench`。
- 变更类型：`do-review` 三轨体系的 reviewer 职责收敛与退役迁移。
- 前置关系：本方案是 [do-review 三轨 Ownership 重构方案](do-review-three-track-ownership-refactor-plan.md) 第 24 节所列“收敛 `code-review` 与 `standards-review` 内容重叠”的后续独立工作；以当前已落地的 A/B/C 三轨为唯一起点。
- 实施边界：只修改 review skills、其 reference/eval、`do-review` 的 reviewer 说明和相关测试/文档；不修改业务项目代码，不增加默认 reviewer，不改变 `do-review` 的 orchestrator Ownership。

## 2. 背景与问题

方案实施前，active `strict-code-review` 专注于结构性可维护性：删除偶发复杂度、避免特例和 spaghetti 增长、检查抽象与模块归属、识别薄包装与边界类型混乱，并要求在存在明确替代方案时推进更直接的设计。

这些判断与 Track B `standards-review` 已有的 Fowler smell、module interface、depth、leverage、locality、adapter 和仓库规范审查高度重合。与此同时，Track A `code-review` 仍包含 architecture、组织、SOLID、通用 code quality 等结构性检查。若将 `strict-code-review` 作为第四条默认轨道，或将其全文直接并入 Track B，将分别产生同一结构问题的多轨重复报告，或使 Track B 退化为没有优先级的代码质量清单。

本方案的目标不是降低严格度，而是把结构性可维护性的唯一 Ownership 收拢到 Track B，并让 Track B 可根据任务背景自主决定审查深度。Track A 则集中于可观察行为与运行风险，避免与 Track B 竞争同一个 finding。

## 3. 目标与非目标

### 3.1 目标

- 默认 topology 保持 `code-review`、`standards-review`、`spec-review` 三条并列 leaf track，不新增 `strict-code-review` Track。
- Track B 将架构、模块组织、抽象、重复、条件复杂度、类型边界和长期可维护性作为首要审查意图，并在这些信号出现时优先深挖。
- Track B 对普通 diff 保持轻量；对明确存在结构风险信号的 diff，自主开启严格可维护性审查，而不依赖用户必须说出“strict”或“code judo”。
- Track A 首要关注行为正确性、安全、性能、资源/并发/原子性、错误与边界处理、测试充分性等运行风险；发现结构性风险时可以提出 candidate，并建议 Track B 优先深挖。
- 退役 active `strict-code-review`，不保留 alias、shim、第四轨或兼容路由。
- 结构性建议应提供具体 diff 证据、维护风险和可行方向；“还能更优雅”不能单独成为 blocker 或 follow-up。

### 3.2 非目标

- 不改变 `do-review` 的 base/head 固定、subagent dispatch、ledger、跨轨去重、severity/classification 或 fail-closed 聚合机制。
- 不把性能、并发、原子性和运行时数据完整性移出 Track A。
- 不把需求忠实度、scope creep、兼容窗口或状态机移出 Track C。
- 不把文件行数、SOLID 或任何单一通用准则变成脱离仓库上下文的硬性 blocker。
- 不让 Track B 为了“严格”而强行制造 finding，或把未被证据支撑的个人风格偏好记入 ledger。
- 不接管 `safety-review` 与默认三轨的组合策略（该项属 [do-review 三轨 Ownership 重构方案](do-review-three-track-ownership-refactor-plan.md) 第 24 节的独立后续工作）；本方案只承认 `safety-review` 作为信号触发的深度专项存在，不改其职责，也不为它砌新边界。

## 4. 目标职责边界

| Track | 首要审查意图 |
| --- | --- |
| Track A `code-review` | 变更后的行为正确性、错误与边界处理、安全、性能、资源生命周期、并发/原子性、测试充分性。 |
| Track B `standards-review` | 仓库规范、代码味道、模块归属、抽象与接口深度、重复、条件复杂度、类型边界、结构性可维护性与 strict 深挖。 |
| Track C `spec-review` | issue/Decision/Spec/Plan/DAG 合同忠实度、缺失实现、scope creep、兼容性、状态机与声明的 cross-module seam。 |

每个 Track 都先沿自己的首要意图审查。role 是正向引导，不是禁止 reviewer 探索或如实记录其他风险的墙。只有 `do-review` 说明 role、track、跨域证据的归属、去重、分类和交接；任何 leaf `SKILL.md` 或其 reference 只说明自身审查方法、证据和输出。

当 `safety-review` 被选入 topology 时，security boundary、data integrity、concurrency 与 external side effect 的**深度**判断归它；默认三轨未选它时，Track A 保留这些运行风险的 baseline 覆盖，作为覆盖地板而非专项。

## 5. Track B 的分层审查设计

### 5.1 常规 Standards 审查

每个 Track B review 均保留现有仓库规范优先级、Fowler smell baseline、deep-module vocabulary、hunk 级证据和 hard violation/judgement call 区分。普通小 diff 在完成这些检查后即可结束；不默认进行重构式“code judo”搜索。

### 5.2 严格可维护性深挖

Track B 在用户明确要求深度/严格可维护性审查时开启深挖；此外，reviewer 可根据完整 diff、共享上下文和仓库规范自行判断是否值得继续探索。下列是非穷尽的深挖信号，而不是固定触发链：

- shared/general-purpose 路径新增 feature-specific 条件、模式或状态分支；
- 同一概念的条件链、flag、nullable mode 或转换逻辑跨多个 hunk/module 增长；
- 新增 adapter、wrapper、generic mechanism、cast-heavy 或 loosely shaped type boundary；
- 变更跨越既有 concept owner，或把知识/验证移出 canonical layer；
- 大型重构或文件/模块显著膨胀，特别是 PR 将原本较小文件推过约 1000 行时；
- diff 本身显示可删除整层间接、合并重复分支或收回不必要通用性的明确机会。

“约 1000 行”只是一项调查信号，不是自动 finding，更不是无条件 blocker。reviewer 必须结合文件职责、仓库既有结构和可行替代方案判断。

深挖方法从退役 skill 原样迁入 `standards-review` 的按需 reference，例如 `references/strict-maintainability.md`。reference 保留原有的 Core Prompt、完整检查标准、问题清单、积极 flag、remedy、语气、输出优先级和 approval bar；`SKILL.md` 只保留如何选择深度、如何形成有证据的建议及避免审美 blocker 的指导。迁移以移动为主，不擅自压缩、删减或重述原设计；与既有 Standards 基线重叠的内容允许并存，避免在保真迁移时损失可用的例子和判断材料。

### 5.3 严格 finding 的证据指引

Track B 形成严格可维护性建议时，应尽可能说明：

1. 当前 diff 中具体的文件/稳定 hunk 与新增或放大的复杂度；
2. 该复杂度带来的可解释维护风险，例如未来同类变更会继续散落、调用方必须理解额外顺序/类型细节、或 shared path 被 feature policy 污染；
3. 一个可行的简化或集中方向，以及它可能删除或集中哪些具体分支、层、wrapper、type escape hatch 或重复知识；
4. 它是仓库规则硬性违规还是 judgement call。

这些是帮助 reviewer 给出可验证建议的证据指引，不是逐项打勾的准入门槛。缺少足够证据时，reviewer 可以在 Coverage record 中记录担忧或明确 evidence gap。Track B 不自行把“更优雅”升级为合入门槛。

## 6. 实施决策

### 6.1 收紧 Track A

保留 `code-review` 既有审查清单、判断标准、实践指导和有效示例，不以 role 收敛为由删除或改写它们。在 `SKILL.md` 增加简短的自身审查偏重说明，但不提及其他 reviewer、Track、交接或分类。将冗长的代码、反馈和安全示例原样移动到按需 reference，不在 leaf 侧描述协作关系。

保留并明确 Track A 的运行风险审查：业务行为、错误处理、输入与授权、数据保护、性能与资源、并发/atomicity、回归与测试。代码位置或抽象只有在它直接造成上述风险时，才作为该风险的证据而非独立结构 finding。

### 6.2 扩展但不膨胀 Track B

更新 `standards-review/SKILL.md`，在现有 Standards 基线之后增加“审查深度选择”和“严格 finding 证据指引”两小节。正文只解释何时深挖与如何给出结论；将完整的原 strict 检查项和示例移至按需 reference，确保常规调用不加载完整 strict 清单。

`do-review` 的 Track B prompt 继续只分配 `standards-review`。它可以在 shared context 中保留用户的审查强度偏好，但不向 registry 新增 profile、capability 或第四 reviewer；Track B 自行根据输入合同决定审查深度，并在需要时用 Coverage record 简述已检查的结构风险或 evidence gap，不强制填写触发依据。

### 6.3 退役 `strict-code-review`

在 Track B 的 strict reference 与 §7.3 场景核对通过后，将 standalone `skills/strict-code-review/` 移至 `skills-deprecated/strict-code-review/`（沿用仓库既有约定，参见 `skills-deprecated/module-review/`），并在归档中明确标记 deprecated/不可自动调用。此外**硬删除**两处纯重复物：顶层 `skills/code-review/`（与 `strict-code-review` 正文逐字相同的 Grok bundle 静音克隆，其 `name: code-review` 还与 Track A 撞名）和陈旧的 `skills/reviews/code-review/SKILL.toon`。不得在 `skills/` 留下 alias、转发 skill、克隆或兼容入口。

更新文档、测试和任何路由引用，使 `strict-code-review` 及其克隆不再作为 active reviewer 或 `do-review` 自定义选择的推荐项。清理核对按**角色/内容**进行（grep 所有 strict-maintainability 制品，而非只搜 `strict-code-review` 路径名），以确保上述同名静音克隆也被发现。历史设计文档可保留它作为迁移背景，但必须明确已退役。

### 6.4 保持 `do-review` 三轨稳定

`reviewer-registry.json` 的默认 A/B/C 三轨不变，也不注册 `strict-code-review`。`do-review` 保留当前 leaf dispatch、同轮隔离、canonical ledger 和 cross-track dedupe；它不判断“code judo”是否成立，只在接收 Track B candidate 后按既有证据与 classification 规则处理。

## 7. 文件与测试变更

### 7.1 修改与新增

- `skills/reviews/code-review/SKILL.md`：保留既有审查知识，在正文补充自身审查偏重；将原有冗长示例原样移动到 `references/examples.md`，不擅自压缩或改变其含义；同时删除其陈旧派生物 `SKILL.toon`（仅此轨遗留、无人消费，与 git 已移除 `git-workflow/SKILL.toon` 的方向一致）。
- `skills/reviews/standards-review/SKILL.md`：加入常规/严格深度选择、非穷尽信号和严格 finding 证据指引。
- `skills/reviews/standards-review/references/strict-maintainability.md`：新增按需深挖材料，保真迁入 `strict-code-review` 的完整指导与例子。
- `skills/reviews/standards-review/evals/evals.json` 与相应 contract test：覆盖深度选择和证据指引。
- `skills/do-review/SKILL.md` 与 leaf brief/reference：由 `do-review` 集中说明 role/track 的 Ownership、跨域证据的交接、去重和分类；leaf skill 与 reference 不描述这些互动。保留允许 Standards 自主选择审查深度的共享上下文表达；不改 topology、registry 或调度算法。
- `docs/skill-design/` 中相关三轨文档：标明本方案已接管其后续“职责重叠收敛”工作项，避免两份 canonical 方案对同一终态作出不同规定。

### 7.2 退役与清理

- 将 standalone `skills/strict-code-review/` 移至 `skills-deprecated/strict-code-review/`。
- **硬删除**顶层重复 `skills/code-review/` 与陈旧 `skills/reviews/code-review/SKILL.toon`。
- 按角色/内容 grep 清理路由与文档中把 strict（含同名克隆）列为可调用 reviewer 的内容；不修改纯历史说明。
- 不修改 `reviewer-registry.json` 的默认三轨，也不添加 strict profile registry schema。

### 7.3 测试场景

- 普通局部 bugfix：Track B 完成常规 Standards 审查，不无依据地要求大规模重构或产生 code-judo finding。
- shared path 新增 feature flag 与多个条件分支：Track B 可选择严格深挖，并说明其结构风险与更集中的 ownership 方向。
- 文件由不足 1000 行增长到超过 1000 行：Track B 进行结构复核，但没有明确拆分价值时不自动报 blocker。
- 仅存在“可以更优雅”的替代写法：Track B 不产生 ledger finding。
- 新增 thin wrapper/cast-heavy boundary 且存在直接、合同等价的替代：Track B 以具体 hunk、维护风险和可删除复杂度报告 judgement finding。
- 同一结构问题：`do-review` 接收独立 reviewer evidence 后确定首要归属、保留必要的来源信息并去重。
- 运行错误处理遗漏：验证 leaf 输出只陈述其自身可证实的风险与 evidence gap，协作归属由 `do-review` 处理。
- `do-review` 默认运行仍精确 dispatch A/B/C 三轨，且不出现第四轨或 strict registry entry。
- 按角色/内容清理核对后，active `skills/` 下不再发现 `strict-code-review`、顶层 `code-review` 克隆、`reviews/code-review/SKILL.toon` 或任何指向 strict 的 active 路由/推荐名；`skills-deprecated/strict-code-review/` 仅作为明确标记的历史归档存在。

## 8. 验收标准

本方案的 implementation 只有同时满足下列条件才可称为 closed：

1. `do-review` 默认 topology 仍是 Track A `code-review`、Track B `standards-review`、Track C `spec-review`，没有 strict 第四轨。
2. 三个 Track 的 active contract 都以首要审查意图引导 reviewer，不将其他风险类别写成能力禁令；role、track、交接、归属和跨域协作只在 `do-review` 描述。
3. Track B 将结构性可维护性作为首要深挖方向，并能根据用户意图、完整 diff 与共享上下文自主决定是否深挖。
4. 常规 Track B 调用不加载冗长 strict 清单；深挖才按需读取 strict reference。
5. 严格可维护性建议提供足以交接的 diff 证据、维护风险和可行方向；证据不足时明确为担忧或 evidence gap，不以审美偏好升级为合入门槛。
6. “还能更优雅”或单一文件行数阈值不能单独成为 blocker/follow-up。
7. active `strict-code-review`、alias、兼容入口和 review routing 都已退役；只允许 `skills-deprecated/strict-code-review/` 留作历史归档。
8. 用现有机制核验通过：`standards-review` 的 contract test（`skills/reviews/standards-review/evals/`）覆盖深度选择与证据指引；`do-review` 的 `verify-reviewer-skills.py` 预检确认三轨 canonical path；按角色/内容 grep 确认 strict 制品（含同名克隆与陈旧 `.toon`）已清除；`git diff --check` 通过。不新增 code-review 专属 eval 或跨轨去重 gate。

## 9. 实施顺序

1. 从 `strict-code-review` 保真迁入完整的严格可维护性材料，写入 Track B 的按需 reference。
2. 更新 Track B 的深度选择、证据指引和 Coverage record，并补充对应 eval。
3. 保留 Track A 的既有审查设计，在 skill 顶层明确自身审查偏重；将原有示例原样移动到 reference，不新增 code-review 专属 eval。
4. 更新 `do-review` 的 role/track 责任说明、交接和 leaf brief，不改变 registry 或 dispatch topology。
5. 用 §7.3 的场景手动核对 A/B/C 路由、职责归位与 strict 深挖行为；修正重复 finding 或无证据 blocker（不新建自动化跨轨 eval）。
6. 将 standalone `strict-code-review` 移至 deprecated 归档，硬删除顶层 `code-review` 克隆与 `reviews/code-review/SKILL.toon`，按角色/内容 grep 清理所有 active 引用。
7. 更新本方案与三轨 Ownership 文档的状态，记录实现证据后再宣称 implementation closed。
