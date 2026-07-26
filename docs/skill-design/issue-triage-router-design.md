# Issue Triage Router 设计

日期：2026-07-23

状态：决策已批准，待实现

相关设计：[Issue Reporter 设计](issue-reporter-design.md) · [Issue Workflow 运行时实现设计](issue-workflow-implementation-design.md)

## Goal

为 2–3 人团队建立一个以 GitHub Issues 为协作入口、对 agent 友好的轻量 `issue-triage` skill。它根据用户自然语言、现有 Issue、父子关系、依赖与仓库上下文，先给出简短 triage 建议；只有用户明确确认后，才创建或更新 GitHub Issue、label 和原生关系。

该 skill 的目标是让 agent 可靠回答“这是什么工作、是否应由 agent 或人推进、应建父 Issue 还是 sub-issue、是否被依赖阻塞”，而不把小团队变成需要人工维护复杂流程的工单系统。

## Confirmed Decisions

- GitHub Issue 是实施协作的状态与协调入口；Implementation Package 仍拥有长篇 Design、Spec、Plan、Findings、Gate 和 durable evidence，PR 是关联 Issue 的交付证据，承担最终 review、CI 与 merge。
- 大事项使用 GitHub 原生父子关系表达。父 Issue 负责目标、范围、稳定文档链接、知情人与关闭条件，并有一个协调 owner assignee。PR 必须关联已有 parent 或 leaf Issue；只有工作需要独立验收、assignee、Working Branch 或依赖时，才创建 sub-issue。
- “同事需要知情但暂不行动”不使用 assignee。经用户确认后，writer 可在父 Issue 的 `Stakeholders` 中写入一次 `@mention`（例如“FYI，当前无需行动”），并建议对方 Subscribe；assignee 只表示对下一步行动负责。
- triage 先提案、后发布。读取和提出分类建议无需确认；任何创建、编辑、加 label、添加父子/依赖关系、评论或关闭 Issue 都必须等用户明确确认。
- V1 不为微小 PR 设置“无 Issue”豁免：每个进入 code review 的 PR 都关联已有 parent 或 leaf Issue；关联 PR 不要求创建 sub-issue。
- 不引入 `work:delivery`。普通的叶子 Issue 默认就是交付工作；`work:` 只标注两个需要特殊路由的形态：initiative 和 investigation。
- 不使用来源或“已管理”label。`$triage` 应一次性写出正确组合；`$issue-reporter` 在读取时对全部开放 Issue 计算合同健康度，把偏离规范的事项列为异常，交由 `$triage` 提出最小修正。
- 现有 `$triage` 是唯一入口，直接替换为本设计的 GitHub Issue router；不创建并行的 `$issue-triage`。保留调用名 `triage`，但将其 canonical skill 移入共享 bundle `skills/issue-workflow/triage/`，使共同合同与两个 skill 同处一个目录。
- readiness label 决定当前谁可以推进以及是否具备条件。GitHub Project 和其 `Status` 字段不是 V1 依赖；将来启用时，`Status` 仅展示 Todo/In progress/In review/Done，不取代 readiness。

## Label Contract

### Work shape

| Label | 含义 | 适用规则 |
| --- | --- | --- |
| `work:initiative` | 跨多个独立切片的目标、协调父事项或需要 FYI 的大事项。 | 不能被 agent 当作直接编码任务领取；默认不需要流程 label。 |
| `work:investigation` | 调研、澄清或决策工作。 | 交付是 findings、决策或规范，而非默认代码变更。 |

普通叶子 Issue 没有 `work:` label，即默认交付工作。一个 Issue 最多一个 `work:` label。

### Workflow readiness

| Label | 含义 | 与相邻状态的边界 |
| --- | --- | --- |
| `needs-info` | 工作本身尚未定义充分，例如事实、复现、验收目标或范围缺失。 | 不假定谁会补充；信息不足时使用。 |
| `ready-for-agent` | 输入、边界和验收已足够，agent 或开发者是当前下一位行动者。 | agent 实现或 Draft PR 期间保留；进入可供人 review 的交接时切换为 `ready-for-human`。 |
| `ready-for-human` | 信息已足够，但 owner 是当前下一位行动者，需要决策、授权或 PR review。 | 不是“必须由人手写代码”；若 review 要求修改，切回 `ready-for-agent`。 |
| `blocked` | 工作和验收已明确，但存在明确的外部或 Issue 依赖。 | 必须在正文或 GitHub `blocked by` 关系中指出依赖。 |
| `wontfix` | 已决定不做。 | 添加后立即关闭；不作为开放工作状态。 |

每个开放的 investigation 或普通叶子 Issue 必须有且仅有一个 readiness label。`work:initiative` 默认没有 readiness label；只有父事项本身需要 owner 决策或被外部依赖阻塞时，才添加相应 readiness label。

`needs-info` 表示任务定义缺失；`ready-for-human` 表示定义充分但等待决定；`blocked` 表示定义充分但等待已知依赖。这三者不得同时存在。

### Readiness handoff

readiness 表示“现在谁必须行动”，而不是历史上谁曾经能够开始。当前行动者完成自己的阶段时调用 `$triage` 提出下一状态；没有自动 bot 改 label。

```text
needs-info → ready-for-agent / ready-for-human   信息补足后
ready-for-agent → ready-for-human                PR 可供人 review 或需要 owner 决策
ready-for-human → ready-for-agent                review 要求修改或需要 agent 继续处理
ready-for-human → close                          review 通过且 PR 合并，或 owner 已完成决定
任一开放状态 → blocked                           出现已知外部或 Issue 依赖
blocked → 原先的可行动 readiness                依赖解除后
```

### Type and urgency

| Label | 含义 |
| --- | --- |
| `bug` | 现有行为错误，或存在安全、正确性问题。 |
| `enhancement` | 新能力或用户可见改进。 |
| `doc` | 主要验收物是文档事实本身。 |
| `maintenance` | 重构、测试基线、内部清理、依赖维护等。 |
| `priority:blocker` | 不完成会阻碍父事项、合入或关键目标关闭。 |

可执行的叶子 Issue 与 investigation 各有一个 type label；对 investigation，type 表示“为什么调查”（例如故障调查用 `bug`、能力探索用 `enhancement`），不是调查的交付形式。`priority:blocker` 是可选例外标签。它不等于 `blocked`：前者说明它阻碍别人，后者说明它自己现在无法推进，二者可以同时出现。

### Combination contract

组合本身就是唯一事实，不增加“由哪个工具处理过”的来源标签。writer 在发布前校验当前目标 Issue 的组合、父子关系和依赖关系；reporter 在读取时审计全部开放 Issue。人工编辑造成的漂移不会被静默掩盖，而会进入 reporter 的异常项。

| 开放 Issue | 组合约束 | reporter 分类 |
| --- | --- | --- |
| 父事项 | `work:initiative`；readiness 可省略。 | Initiatives |
| 普通交付或 investigation，agent 可开始 | 一个 type + `ready-for-agent`。 | Next actions |
| 普通交付或 investigation，等待人处理 | 一个 type + `needs-info` 或 `ready-for-human`。 | Next actions |
| 已知依赖阻塞 | 一个 type + `blocked`，且正文或 GitHub 关系声明依赖。 | Blocked |
| 不做 | `wontfix` 后关闭。 | Archive，不进入开放 view |

`priority:blocker` 不改变基础分类；`work:investigation` 也不形成独立状态队列，它按 readiness 进入 Next actions 或 Blocked。

`$triage` 在 publish 前校验当前目标的组合；跨 Issue 的只读 contract audit 由 `$issue-reporter` 负责。异常不是另一套工作状态或来源 label，而是 reporter 根据当前组合计算出的结果。合规的开放 Issue 必须由 Next actions、Blocked 或 Initiatives 至少一个 reporter 分类覆盖；关闭的 `wontfix` 进入 Archive。未满足合同的开放 Issue 由 Hygiene 直接暴露，随后可交给 triage 修复。

### Retirement and migration mapping

| 旧 label | 新处理方式 |
| --- | --- |
| `question` | 用 `work:investigation` 表达工作性质，再根据输入选择 readiness。 |
| `no-blocker` | 删除；没有 `priority:blocker` 即默认非阻塞。 |
| `duplicate` / `invalid` | 不进入日常 label 体系；关闭时写明原因和关联 Issue。 |

现有 `bug`、`enhancement`、`doc`、`needs-info`、`ready-for-agent`、`ready-for-human`、`blocked`、`wontfix` 保持原名称，避免不必要的批量重命名和文档漂移。

## Parent, Sub-issue, Dependency and PR Rules

```mermaid
flowchart TD
  I["work:initiative parent"] --> R["work:investigation sub-issue"]
  I --> D["ordinary delivery sub-issue"]
  I --> P0["PR directly linked to parent"]
  R --> D
  D --> B["Working Branch"]
  B --> P["PR"]
  P --> C["Merge and close delivery issue"]
```

- 当目标需要两个或以上可独立关闭的切片、需要协调知情人，或需要汇总关闭条件时，创建 `work:initiative` 父 Issue；它必须有明确 owner（assignee）和关闭条件。
- 当工作有自己的验收标准、assignee、Working Branch 或依赖时，创建 sub-issue；不能仅因“有一个 PR”而强制拆分。满足这些条件前，PR 可以直接关联 parent。
- 当一个请求是单一、可独立验收的切片且没有更高层目标时，创建普通叶子 Issue，不人为创建父事项。
- 当主要未知项是事实或决策时，创建 `work:investigation`；其结论可以关闭该 Issue，也可以产生后续 delivery sub-issue。
- 真实前置条件使用 GitHub 原生 `blocked by` / `blocking` 关系。`blocked` label 只说明当前状态，不能代替关系。
- PR 不是需求入口、不是 triage 对象，也不替代 Issue。每个协作或代码审查中的 PR 必须关联已有 parent 或 leaf Issue，负责最终审核、CI 和合并；没有关联 Issue 的开放 PR 是 reporter 的 Hygiene 异常。

## Router Contract

### Inputs

router 接受自然语言请求，也可以接受 Issue 号、URL、Implementation Package 路径、PR 链接或当前分支上下文。它读取足以判断的本地和 GitHub 上下文：Issue 正文、评论、labels、assignee、父子关系、依赖、稳定文档链接和当前 Working Branch。

router 只在判断确实依赖代码事实时进行针对性的只读检索；它不对每次新想法强制做完整代码复现、全仓 redundancy audit、grilling 或领域文档修改。信息不足时，它进行一轮最小澄清：可以在同一轮问完互相依赖的关键问题；若回答后仍无法分类，明确说明缺少的外部事实，而不猜测。

### Read-only triage proposal

在任何外部写入之前，router 返回不超过五行的提案：

```text
Triage proposal
- 操作：创建 sub-issue，父项 #140
- 形态：work:investigation；类型：enhancement；状态：ready-for-agent
- 依赖：无
- 依据：当前先需冻结 adapter 边界；结论将决定后续 delivery 切片
- 发布：等待确认
```

提案可以建议更新既有 Issue、创建父 Issue、创建 sub-issue、设置依赖、关联 PR、仅通知同事，或不创建 Issue。提案必须说明最关键的一条依据。用户确认“发布”“创建”或等效指令后，writer 才执行对应 GitHub 操作。一份提案中的多个相互关联变更（例如创建父项及两个 sub-issue）只需一次确认；超出该提案范围的变更须重新确认。

### Publication behavior

- 创建/更新时，writer 只写已确认的标题、正文最小模板、labels、assignee、父子关系、依赖关系和关联 PR。
- writer 在完成组合校验后发布已确认的变更；若任意现有 Issue 已违反合同，先给出最小修正提案，不静默覆盖。
- 不自动发表 AI triage 评论、不自动 @mention、不自动创建 Agent Brief、不自动关闭 Issue。
- 规范化既有 Issue 时，writer 仅新增或更新约定的最小区块（`Outcome`、`Acceptance`、`Working Branch`、`Stakeholders` 等）；不重写用户已有背景、讨论或证据。若这些区块与现有正文冲突，提案必须展示最小 diff。
- Issue 进入实际实施协作并开始分支工作时，由开始执行的工作流写入唯一有效的 Working Branch 指针；router 不因创建任务而虚构分支。
- 如果现有 Issue label 不完整或冲突，router 仍可读取和解释它；提案中标出最小修正，而不拒绝服务。

## Minimal Issue Body

父 Issue 只保留 `Outcome`、`Scope / Non-goals`、`Context links`、`Stakeholders` 和 `Closure condition`。`Stakeholders` 只在需要留存知情范围时出现，可记录经确认的 `@mention`；日常 FYI 仍建议 GitHub Subscribe。

普通叶子或 investigation Issue 只保留 `Outcome`、`Scope / Non-goals`、`Acceptance`、`Context links` 和 `Working Branch`。长篇设计不复制进 Issue，而是链接到 Implementation Package。

## Future Project Views（不属于 V1）

V1 不创建、不要求加入、也不审计 GitHub Project。团队将来需要面板时，可把 Issue 的既有 label 组合投影为以下三个 view：

| View | Filter | 用途 |
| --- | --- | --- |
| Next actions | `is:open is:issue label:"ready-for-agent","ready-for-human","needs-info" -label:"work:initiative"` | 每日处理入口；按 readiness 分组或筛选，区分 agent 可领与人需处理。 |
| Blocked | `is:open is:issue label:"blocked"` | 跟踪已知依赖。 |
| Initiatives | `is:open is:issue label:"work:initiative"` | 非每日视图；查看大事项及子事项进度。 |

Project `Status` 只用于 board 执行可视化，不作为 router 判断 readiness 的唯一事实。

Hygiene 不是第四个 Project view：GitHub filter 无法可靠表达组合基数与关系完整性，强行配置会漏掉多 readiness、缺 type 等异常。它是 `$issue-reporter` 输出的只读 audit 分组；用户可从异常项直接调用 `$triage` 生成最小修正提案。

## Assessment of the Existing `triage` Skill

### Reusable concepts

- 先读取 Issue 正文、评论、labels 和关联上下文，再给维护者分类建议。
- 明确区分工作类型与推进状态。
- 在状态变更前向用户说明将发生什么。
- 对已有 triage 记录做增量阅读，避免重复问已解决的问题。

### Incompatible behavior

| 现有 `triage` 行为 | 为什么不适用 | 新体系处理 |
| --- | --- | --- |
| `needs-triage` 是默认入口。 | 新体系不把未判断状态写入 GitHub；router 先在会话中提案。 | 不使用 `needs-triage`。 |
| 外部 PR 与 Issue 共用入站队列。 | KaiSpan 的 PR 不是需求入口，也不用于早期设计协作。 | PR 仅作为既有 delivery Issue 的最终证据。 |
| 只有 `bug` / `enhancement` 两类。 | 缺少 initiative、investigation、doc 和 maintenance。 | 使用本设计的四个 label 维度。 |
| 每个 Issue 强制一类和一状态。 | 父 initiative 不是可执行工作，强贴 readiness 会污染 agent 队列。 | initiative 的 readiness 默认可省略。 |
| 自动发布 AI disclaimer、triage note 与 Agent Brief。 | 会在用户确认前产生外部副作用，并把 Issue 评论错误升级为长期合同。 | 默认只输出会话提案；确认后只执行请求的写入。 |
| 对每次 triage 强制代码 redundancy、复现、grilling 与领域文档更新。 | 对 2–3 人团队过重，且把 issue 路由扩张为设计/诊断流程。 | 只按不确定性做针对性只读检查；深度设计交给独立 skill。 |
| enhancement 的 `wontfix` 写入 `.out-of-scope/`。 | 这是 Matt 流程的知识库政策，当前 GitHub/Implementation Package 体系未采用。 | 关闭理由与稳定决策链接写在 Issue；不新建 `.out-of-scope/` 机制。 |
| `ready-for-human` 表示人工实现。 | 本体系中它表示需要人类决策、授权或评审。 | 保留 label 名称，调整语义。 |

### Design decision

直接替换 `$triage` 的实际语义并迁移至 `skills/issue-workflow/triage/`。现有 skill 当前未被团队主动采用，保留它再新增 `$issue-triage` 只会让用户和 agent 面对两个相互竞争的入口；新体系必须成为 `$triage` 的实际语义。

实现时保留 `name: triage`，并更新所有仍指向旧 `skills/triage/` 路径的消费者；新 skill 把说明、状态模型和副作用边界替换为本设计的 router。它只继承现有 skill 的“收集上下文 → 给出建议 → 获得确认 → 执行”交互骨架，不继承 `needs-triage`、PR 入站、自动评论、Agent Brief 或 `.out-of-scope` 职责。

这是一次有意的内部破坏性语义变更，因此实现必须同步更新 `setup-matt-pocock-skills`、其 label seed/reference，以及任何仍声明 Matt 默认 triage 词汇的相邻 skill。`AGENT-BRIEF.md` 和 `OUT-OF-SCOPE.md` 不再是 `triage` 的运行时依赖；实施时应删除或明确归档它们，不能保留为看似仍有效的隐含流程。

## Non-Goals

- 本设计不立即创建或迁移 GitHub labels、Issue forms 或开放 Issue；GitHub Project views 不是 V1 的实现目标。
- 本设计阶段不立即修改旧 `skills/triage/`、`setup-matt-pocock-skills`、`to-spec` 或 KaiSpan 的现有 issue-tracker 文档；它们只在 Unified Rollout 中同步变更。
- 不实现自动标签修复、自动评论、自动分配 assignee、自动创建分支或自动关闭 Issue。
- 不把 issue-triage 变成代码诊断、设计评审、agent brief 写作、PR review 或发布工具。

## Unified Rollout Boundary

本体系必须作为一个工作单元实施和发布，不能先单独替换 `$triage`、再在未来某次才更换 labels 或 KaiSpan 约定。否则 agent 可能依据新 skill 写入旧的 Matt label，或依据旧 setup 文件重新引入 `needs-triage`，形成两套语义。

实现可以在同一 Working Branch 内按下列顺序开发和验证，但只有以下五部分同时满足时，才可以将本次变更视为可用：

| Slice | 必须同步的结果 |
| --- | --- |
| Skill runtime | `$triage` 变为 read-only proposal first 的 issue router，并在确认后才 publish；`$issue-reporter` 提供只读 portfolio、focused report 和 contract audit。 |
| Skill ecosystem | `setup-matt-pocock-skills`、seed/reference 和相邻消费者不再假设 `needs-triage`、外部 PR 入站或自动 Agent Brief。 |
| KaiSpan tracker contract | `docs/agents/issue-tracker.md` 与 `docs/agents/triage-labels.md` 采用本设计的 label、父子关系和 PR 边界。 |
| GitHub materialization | GitHub labels 与本设计一致；不创建或配置 GitHub Project。 |
| Open-issue migration | reporter 先对全部开放 Issue 做 dry-run，router 再给出统一批量修正提案；确认后一次性规范化。无法从事实判断的事项使用 `needs-info`，不猜测关闭、assignee、分支、PR 或文档链接。 |

关闭门：任何一个 slice 未完成时，都只能称为“实现或迁移进行中”，不能称为新的 issue-triage 体系已启用。

## Acceptance Criteria for the Future Skill

- 用户描述一个新事项时，router 能在不写 GitHub 的前提下，判断创建 initiative、investigation、普通叶子或 sub-issue，并输出不超过五行的 triage proposal。
- 用户确认前，不发生 GitHub Issue、label、评论、依赖、assignee、关联 PR 或分支变更。
- router 能正确区分 `needs-info`、`ready-for-human`、`blocked` 与 `priority:blocker`，并将真实依赖映射为 GitHub 原生关系。
- `work:initiative` 不出现在 Next actions；普通 leaf 与 `work:investigation` 在 `ready-for-agent` 时可以出现。
- 每个由 router 成功创建或规范化的开放 Issue 都满足组合合同，并至少出现在一个 reporter 分类；任意开放 Issue 的 contract violation 由 `$issue-reporter` 的只读 audit 报告。
- router 读取旧 Issue 时可报告 label 缺失或冲突，但不因历史数据不整洁而拒绝给出建议。
- router 不把 PR 作为新需求入口，也不创建 Draft PR。
- 对“同事仅需知情”的请求，提案使用通知/Subscribe 建议，不把同事自动设为 assignee。
- 现有 `$write-issue` 只作为中文 Issue 文本辅助；它不自行决定 label、关系或发布，需由 `$triage` 统一路由和写入。

## Implementation Sequence

1. 审计 `$triage` 的所有消费者和 Matt triage vocabulary 的引用，锁定需要同步替换的文件清单；不在此阶段修改 GitHub。
2. 在同一 Working Branch 内建立共享 `skills/issue-workflow/` bundle，在其中实现 `$triage` 的 read-only router 和 proposal 输出，再增加以确认后的 proposal 为唯一输入的 publish writer；同步移除旧 `skills/triage/` 并归档不再适用的 Agent Brief 与 `.out-of-scope` 依赖。
3. 同步更新 `setup-matt-pocock-skills`、其 label seed/reference、`write-issue` 和仍假设 `needs-triage` 或 PR 入站的相邻 skill；补齐六个 fixture：普通 leaf、parent 直接关联 PR、parent + sub-issue、investigation、`blocked` 依赖和历史不规范 Issue 的迁移。每个 fixture 都验证确认前零写入、确认后正确组合/关系、readiness handoff，以及 reporter 的分类与 PR 证据一致。
4. 经 owner 明确批准后，在 GitHub 创建/重命名目标 labels，并更新 KaiSpan 的 `docs/agents/issue-tracker.md` 与 `docs/agents/triage-labels.md`；不创建或配置 Project。
5. reporter 对全部开放 Issue 做 dry-run，再由 router 提出统一批量迁移；用户一次确认后写入。已关闭历史 Issue 保留原 label 作为历史证据。
6. 在所有 slices 一致后，以真实 Issue dry-run 验证 `$issue-reporter` 的全量 combination contract audit 与 PR Hygiene；两者均无遗漏后才宣布新体系启用。
