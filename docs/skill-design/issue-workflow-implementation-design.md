# Issue Workflow 运行时实现设计

日期：2026-07-26

状态：设计已批准，待实施

相关设计：[Issue Triage Router 设计](issue-triage-router-design.md) · [Issue Reporter 设计](issue-reporter-design.md)

## Goal

为 2 人、agent-assisted 的 KaiSpan 团队实现一套轻量 Issue 工作流运行时：`$triage` 是唯一远程写入入口，`$issue-reporter` 是严格只读的工作图谱读取入口，`$write-issue` 只辅助中文正文措辞。规则可被脚本稳定校验，但业务分类、例外解释和用户确认始终由 agent 完成。

GitHub CLI `gh` 是唯一 GitHub 远程适配器。Python 不读取 token、不直接请求 GitHub API；它只调用已认证的 `gh` 获取 JSON，或处理已有 JSON。私有仓库权限完全继承当前 `gh` 账户。

## Runtime Layout

```text
skills/issue-workflow/
├── references/
│   ├── issue-contract.yaml       # 机器 canonical
│   └── issue-contract.md         # 人类语义、边界和例子
├── templates/
│   ├── initiative.md             # 含固定 Closure condition 标题
│   └── actionable-issue.md       # leaf / investigation 的软模板
├── scripts/
│   ├── issue_workflow.py         # 唯一 Python CLI
│   └── fixtures/                 # mock gh 输入与断言样例
├── triage/
│   └── SKILL.md
└── issue-reporter/
    └── SKILL.md

<target-repo>/.agents/issue-workflow.yaml  # 项目级团队身份映射
```

bundle 根目录不是 skill。实现后 `$triage` 的唯一 canonical 路径为 `skills/issue-workflow/triage/`；所有旧 `skills/triage/` 引用必须同步迁移，不能保留两个入口。

## Canonical Contract and Templates

`references/issue-contract.yaml` 是所有机器规则的唯一来源，包含：

- `work:initiative`、`work:investigation`、四个 readiness、四个 type 与 `priority:blocker`；
- label 基数、互斥与适用对象；
- readiness handoff 允许边；
- `blocked` 所需依赖、initiative 所需 `Closure condition`、PR 所需关联 Issue；
- reporter 的 hard violation、advisory 与 unknown 分类；
- `contractVersion`。

`issue-contract.md` 不复制可枚举规则表，只解释术语、判断边界、典型组合和人工可读例子，并链接 YAML。模板也是外链资产：skill 在真正需要写 body 时引用它们，而不在 `SKILL.md` 重复粘贴正文。

模板是软引导。`Outcome`、`Scope`、`Acceptance`、`Context links` 和 `Stakeholders` 都可以按任务省略或自由表达；只有 initiative 的非空 `## Closure condition` 是机器可检查的固定标题。

## Project Identity Mapping

共享 contract 不含项目成员。KaiSpan 在 `.agents/issue-workflow.yaml` 声明已确认的两人映射：

```yaml
version: 1

people:
  owner:
    github: fangxiao-dev
    aliases: ["我", "我自己", "@我"]
  teammate:
    github: haisapan
    aliases: ["同事", "@同事", "haisapan", "@haisapan"]
```

triage 将自然语言别名规范化为 GitHub login。`bodyMention`、`commentMention`、`issueAssignee` 和 `prReviewer` 是不同 operation，必须在提案中分别出现并在确认后才写入。未知、冲突或未配置别名返回 `unknown`，不猜测 @ 人。

## Skill Boundaries

| Skill | 负责 | 不负责 |
| --- | --- | --- |
| `$triage` | 读取上下文、业务分类、最小澄清、父/子/PR 关系选择、生成 proposal、获得确认后通过 `gh` 写入。 | 自动远程写入、自动创建分支、自动评论、自动修复。 |
| `$issue-reporter` | 读取 Issue/PR 图谱，生成 portfolio、focused report、Issue brief、contract audit 与显式 Repository hygiene。 | 追问、准备 mutation、调用模板、任何 GitHub 写入。 |
| `$write-issue` | 按共享模板协助产出中文标题和正文。 | label/关系决策、调用 Python/`gh`、发布。 |

readiness 表示“当前下一位行动者”：Draft PR 期间保持 `ready-for-agent`，PR 进入可供人 review 的交接时变为 `ready-for-human`，review 要求修改时切回 `ready-for-agent`，合并/决策完成时关闭。当前行动者调用 triage 提出交接；不使用 bot 自动改 label。

## Python CLI

`issue_workflow.py` 只实现确定性读模型和计划计算。默认向 stdout 输出 JSON，也可额外输出简短人类摘要；不维护数据库、队列或持久运行状态。

| Command | 输入 | 输出 | 禁止 |
| --- | --- | --- | --- |
| `snapshot` | repo、Issue/PR scope | 规范化 snapshot JSON | `gh` 写命令、token 读取、持久化状态 |
| `validate` | snapshot + contract | `hardViolations`、`advisories`、`unknowns` | 猜测业务修复 |
| `report` | snapshot + contract + scope | reporter 所需结构化摘要 | Issue/PR 写入 |
| `plan` | snapshot + contract + agent 传入的 intent | 逐项 `operations[]` 与 diff | 自行选择 parent/type/业务语义、写入 |
| `contract check` | contract、模板、身份映射 | schema/版本/alias 冲突检查 | 扫描或修改 GitHub |

snapshot 至少携带 `schemaVersion`、`contractVersion`、repository、fetchedAt、issues、pullRequests 与 `unknowns`；不含 token。plan 若发现 snapshot contract 版本不一致，拒绝沿用旧 plan，要求重新 snapshot。

agent 提供的 `intent` 只是明确的已判断意图，例如“将 #140 交给 review，并关联 PR #152”。Python 验证合同并精确计算 labels、关系、固定 body section 与身份 operation 的差异；它不会决定是否该建 parent/sub-issue，也不会从自然语言推断 type。

`gh` 不可用、没有私库权限或关系字段不可读时，Python 必须返回 `unknown` 和缺失字段。skill 只能据此缩小结论、追问或报告读取范围，不得将读取失败称为合规。

## Triage Publication Contract

triage 的 read-only proposal 包含所有将发生的 operation：Issue 创建/编辑、label、父子/依赖、PR 关联、body section diff，以及 body/comment mention、assignee、reviewer。一次确认可覆盖同一份逐项 operation 列表。

日常单 Issue 操作与 backlog sweep 都使用同一 plan 格式。sweep 可以一次确认，但必须逐项展示每个 Issue 的 label、关系和 body diff；存在正文冲突、未知字段或无法判断事实的事项不能藏在聚合摘要中。初始化迁移先 dry-run 全部开放 Issue，无法判断的事项进入 `needs-info`，不虚构 assignee、分支、PR、文档链接或关闭决定。

确认后，triage 使用 `gh` 执行已确认 operation。Python 没有 `apply` 子命令。若新发现额外 Issue、@mention、关闭动作或范围扩大，必须重新提案确认。

## Reporter Contract

普通 portfolio 读取 Issue 已关联的 PR，报告直接 PR 和 parent 子树 PR，并标注关联层级；它不扫描全仓 PR。只有用户明确请求 `Repository hygiene` 时，才读取全部开放 PR 并报告没有关联 parent 或 leaf Issue 的 PR。

reporter 对 Issue/PR 与 readiness 显示不一致时写“需要 `$triage` 确认交接”，不修改 label，也不从 PR 标题或聊天内容猜测下一动作。

## Validation

Python fixture 全部 mock `gh` JSON，并断言 `snapshot`、`validate`、`report`、`plan` 从不调用 `gh` 写命令。六个场景为：

1. 普通 leaf；
2. parent 直接关联 PR；
3. parent + sub-issue；
4. investigation；
5. `blocked` 依赖；
6. 历史不规范 Issue 的迁移。

每个场景验证确认前零写入、确认后预期组合/关系、readiness handoff、reporter 分类与 PR 证据一致。另加身份 fixture，验证 `@同事` 在 body mention、Issue assignee 与 PR reviewer 中均解析为 `haisapan`，且不会产生额外 mention。

## Non-Goals

- 不创建 GitHub Project，不依赖 Project views 或 Project Status。
- 不建立 webhook、bot、数据库、后台 worker 或自动修复。
- 不让 Python 直接保存 token、绕过 `gh` 或执行 GitHub 写操作。
- 不将软模板、业务分类、文档链接质量或正文自由文本升级成硬校验。

## Implementation Order

1. 建立 bundle、YAML contract、Markdown 解释、两份模板与项目身份配置；实现 `contract check` 和 fixture harness。
2. 实现只读 `snapshot`、`validate`、`report` 与 `plan`，覆盖 mock `gh` fixture。
3. 原地替换 `$triage` 语义并迁移其路径，建立 proposal/confirmation/writer 边界；同步更新 `$write-issue` 的模板引用。
4. 实现 `$issue-reporter` 的四种报告模式与 Repository hygiene。
5. 更新 Matt triage ecosystem、KaiSpan issue tracker 文档和 GitHub labels；执行全量开放 Issue dry-run、确认后的统一迁移与真实 read-only 验证。

关闭门：只有所有五步完成且真实读取验证通过，才能称为新 issue-driven development 体系启用。
