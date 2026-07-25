# Issue Reporter 设计

日期：2026-07-25

状态：决策已批准，待与 Issue Triage Router 一起实现

相关设计：[Issue Triage Router 设计](issue-triage-router-design.md)

## Goal

建立只读的 `$issue-reporter`，把 GitHub Issue 的 label 组合、父子关系、依赖和当前协作状态解释为一份短而可行动的简报。它服务于“现在有哪些类别的问题”“与我当前上下文相关的工作是什么”“哪些 Issue 没有被体系覆盖”这类读取需求，而不创建、编辑、评论、关闭或重新标记任何 GitHub Issue。

`$issue-reporter` 与 `$triage` 共同构成 issue-driven development 的一套能力：`$triage` 理解用户意图、追问缺失信息、提出路由方案并在确认后写入；`$issue-reporter` 读取已经存在的工作图谱，报告当前状态与合同健康度。

## Confirmed Decisions

- `$issue-reporter` 是 `$triage` 的 sibling，不是 `$triage` 的只读 mode。用户只想了解状态时，不应进入可能追问或准备写入远程 Issue 的工具。
- 它严格只读：禁止创建、编辑、评论、关闭、打 label、分配 assignee、创建分支、操作 Project 或修改本地文档。
- 两个 skill 共用一份 future `issue-contract.md`；不得在各自 `SKILL.md` 复制 label 定义、基数约束、关系语义或 view 覆盖规则。
- `$triage` 在 publish 前只校验当前目标 Issue 的组合；`$issue-reporter` 负责全部开放 Issue 的只读 combination contract audit。
- 不使用 `triage:managed` 或其他来源 label。每个开放 Issue 都按当前 label、正文与原生关系计算是否合规；人工或历史输入若不合规，作为异常列出，不假定它们无关。
- 报告只给出由 Issue、GitHub 原生关系、稳定文档链接和用户提供上下文支持的事实；不能从标题、label 或聊天记忆猜测实现进度。
- PR 是关联 Issue 的交付证据，不是需求入口。reporter 报告 Issue 的直接 PR；查看 parent 时可汇总子树 PR，并明确标注关联层级。

## Future Bundle Layout

```text
skills/issue-workflow/
├── references/
│   └── issue-contract.md
├── triage/
│   └── SKILL.md
└── issue-reporter/
    └── SKILL.md
```

bundle 根目录没有 `SKILL.md`，只是分组和共享资产位置；两个 leaf skill 保留独立调用名 `$triage` 与 `$issue-reporter`。实现时需要更新所有仍引用旧 `skills/triage/` 路径的消费者，确保没有两个同名 `$triage` 入口并存。

`issue-contract.md` 是下列事实的唯一来源：

- `work:initiative`、`work:investigation`、普通叶子 Issue 的语义；
- readiness、type 和 `priority:blocker` 的 label 合同及基数规则；
- 父/子 Issue、`blocked by` / `blocking`、Working Branch 与 PR 的职责边界；
- Next actions、Blocked、Initiatives、Archive 的报告覆盖规则，以及 Hygiene audit 的异常规则；
- combination contract audit 的违规分类与报告格式。

## Reporter Inputs and Modes

| 用户输入 | 模式 | 输出范围 |
| --- | --- | --- |
| “现在有哪些问题”或无范围请求 | Portfolio snapshot | 全部开放 Issue 的分类摘要和重点关注项。 |
| Issue 编号、URL 或父 Issue | Issue brief | 该 Issue、其父子树、依赖、label 组合和下一道门。 |
| 模块、领域、工作主题、label、assignee、日期或用户给出的上下文 | Focused report | 只报告与该上下文有明确关联的 Issue，说明筛选依据。 |
| “检查 Issue 面板/组合是否完整” | Contract audit | 所有开放 Issue 的合同违规与 Hygiene 异常；不修改它们。 |
| “检查有没有没挂 Issue 的 PR” | Repository hygiene | 仅扫描开放 PR 是否关联 Issue；不把 PR 当作新需求创建 Issue。 |

当输入无法可靠映射到 Issue 范围时，reporter 只询问一个最小澄清问题，例如“你希望按 Finance Assistant 领域、某个父 Issue，还是当前 assignee 范围查看？”它不会为了回答问题而创建 `needs-info` Issue。

## Reporting Model

### Portfolio snapshot

默认报告应先给总量和覆盖状态，再列出少量最需要人处理的事项。它只读取 Issue 已关联的 PR，不扫描全仓 PR；全仓 PR 检查使用 Repository hygiene。它至少包含：

| 类别 | 识别规则 | 面向用户的解释 |
| --- | --- | --- |
| Next actions | `ready-for-agent`、`needs-info` 或 `ready-for-human`，且非 `work:initiative`。 | 每日处理入口；前者可由 agent 或开发者领取，后两者需要人补事实、决策、授权或评审。 |
| Blocked | `blocked`。 | 工作定义充分，但正在等明确依赖。 |
| Initiatives | `work:initiative`。 | 目标、协作和子事项的汇总；不是直接编码队列。 |
| Hygiene | reporter 对全部开放 Issue 计算的组合异常。 | 缺 readiness、冲突组合、缺 type、缺依赖关系等；应由 `$triage` 提出最小修正方案。 |

同一 Issue 可以同时出现在 Initiatives 与 Blocked 等多个类别；“覆盖”指合规 Issue 至少可在一个相关报告分类中被发现。异常由 Hygiene 单列，不要求类别互斥。

### Issue brief

单 Issue 简报按以下顺序输出：

1. 工作形态、type、readiness 与 `priority:blocker` 的解释。
2. 父 Issue、直接 sub-issue、直接 dependencies，以及它们对关闭条件的影响。
3. Issue 正文或 GitHub 关系中的当前 Working Branch、稳定文档链接和直接关联 PR；查看 parent 时另列直接关联 PR 与子树 PR。缺失时明确写“未记录”，不猜测。
4. 当前下一道门：可以领取、等待人类、等待依赖、等待子项，或已经可关闭。
5. 若发现合同违规，给出只读诊断和建议通过 `$triage` 修复的原因。

### Focused report

用户提供领域或工作上下文时，reporter 必须说明关联依据，例如 Issue label、父子链、稳定文档链接、标题中的明确术语或用户给出的 Issue 编号。无法建立明确关联的 Issue 不纳入结果，也不因为名称相似而声称相关。

## Contract Audit

contract audit 不依赖 GitHub Project。reporter 按共享 contract 计算以下合同违规：

- 普通叶子或 investigation 缺少 readiness、拥有多个 readiness，或缺少/拥有多个 type；
- initiative 带有 `ready-for-agent` 或拥有互相冲突的 readiness；
- `blocked` Issue 没有正文或原生关系所指向的已知依赖；
- `wontfix` Issue 仍开放；
- 合规 Issue 不属于任何合同规定的开放报告分类；

合同违规按类别分组，每项只写 Issue 或 PR 编号、当前组合或关联状态、违反的规则和建议交由 `$triage` 的修正原因。它不自动修复；人工外部输入只有在违反当前合同或缺失必要事实时才列为异常。

以下属于提示，不遮蔽合同违规，且只在用户请求 audit 详情时展开：Issue 未记录 Working Branch 或 PR、parent 未说明 Stakeholders、稳定文档链接可能过期。

### Repository hygiene

Repository hygiene 只在用户明确请求时扫描全部开放 PR。任一开放 PR 没有关联的 parent 或 leaf Issue 即为 Hygiene 违规；reporter 只报告 PR 编号、当前关联状态与建议交由 `$triage` 处理的原因，不从 PR 内容推断或创建需求。

## Output Contract

所有报告使用简体中文，先给可独立阅读的结论，再给必要明细。正常 portfolio snapshot 控制在一屏到两屏：总量、类别计数、最优先的少量事项和合同健康度。详细树、完整列表和每个 Issue 的 labels 只在用户要求展开、提供具体范围，或运行 contract audit 时输出。

报告必须区分：

- 已从 GitHub Issue/关系读取的事实；
- 基于合同得出的分类结论；
- 因缺失正文、关系或状态而无法判断的内容。

它不得把 Issue label 当作“代码已实现”或“PR 已合并”的证据，也不得把组合合同健康度表述为产品功能已完成。

## Boundaries

- 不取代 `$triage` 的路由、追问、确认和远程写入职责。
- 不做代码审查、Bug 复现、PR review、Agent Brief、Implementation Package 设计或任务执行。
- 不操作或依赖 GitHub Project；未来启用 Project 时，它只消费 Issue 已有事实。
- 不把已关闭历史 Issue 批量重分类。只有用户明确要求历史审计时才读取它们。

## Acceptance Criteria for the Future Skill

- 对全局、单 Issue 和用户指定上下文，reporter 都能给出只读且来源可追溯的简报。
- 它能正确解释 label 组合、直接父子关系、依赖和 PR 关联层级，且不把 PR 当需求入口。
- 所有开放且合规的 Issue 都会被归入至少一个合同类别；不合规 Issue 都会进入 Hygiene。
- contract audit 与 Repository hygiene 能完整报告 shared contract 中定义的 Issue 和 PR 违规，但不产生 GitHub 或本地写入。
- 报告不会把 label、标题或旧评论推断成未被证据支持的实现或合并事实。
- `$triage` 与 `$issue-reporter` 都从同一份 `issue-contract.md` 读取组合规则，不存在第二份 label 事实源。

## Implementation Sequence

该 skill 必须与 [Issue Triage Router 设计](issue-triage-router-design.md) 中的 Unified Rollout Boundary 一起交付：先建立共享 contract 和 fixture，再实现 triage 的局部 publish 校验与 reporter 的全局报告/audit，随后同步更新 KaiSpan tracker 文档、GitHub labels 和开放 Issue 迁移。任何一方单独启用都不构成完整的 issue-driven development 体系。
