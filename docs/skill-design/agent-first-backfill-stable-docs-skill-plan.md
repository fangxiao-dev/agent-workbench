# Agent-First Backfill Stable Docs Skill Plan

日期：2026-07-16
状态：设计已批准，待同步实现；已纳入两轮 litmus dry-run 结论，并已纳入独立设计评审（见下方"设计评审结论"）后的修订

## 设计评审结论（本轮修订的由来）

独立设计评审（只读，未改代码）发现两类问题，本次修订据此调整：

1. **三层 stable authority schema 尚未同步进实际 skill**（schema/脚本/references 仍是旧的两层 `topLevel`/`moduleKnowledge`）——这是正常的"设计先行、待同步"状态，不算设计缺陷，但必须在下一步同步实现时一次性做完，不能留半套。
2. **上一版"Litmus Dry-Run Findings"用了"已经验证过"的既成语气，但支撑这个结论的具体数字（5 个 module root、1 歧义 4 缺失等）只有套用仓库里现在真实存在的 `module-knowledge/` 命名才能对上，而当时的 Config Model 示例却指向从未存在过的 `modules/`/`context/` 命名**——评审判定这不是"还没实现"的问题，而是文档自己的验证叙事和自己最终提出的 schema 不是同一个东西。已在下方澄清：本文档的 Config Model 一律是**目标态**，Litmus Findings 一节明确标注是"针对当前真实命名的人工核对"，两者不再混用同一段落。

评审后与用户对齐的关键决定：

- `contextKnowledge` 是**可选**字段；不配置时该仓库退化为两层（system + module），不强迫扁平 repo 发明不存在的 context 层。
- KaiSpan 物理目标目录**保留 `module-knowledge/` 命名，不改成 `modules/`**——KaiSpan 是 TS monorepo，根下已有 `packages/` 作为真正的代码模块目录，`docs/.../modules/` 与之长期共存会造成混淆，这条风险与是否迁移无关，直接否决改名。
- KaiSpan **新增 `context/` 子目录**，把目前平铺在 context 根的 `CONTEXT.md`/`architecture.md`/`prd.md` 收进去，与 `module-knowledge/`、`implementations/`、`_pending.md` 并列。
- 两个仓库的 system 级目录统一命名为 **`system-knowledge/`**；prj-supplyer-webapp（webshop）现有 `docs/top-level-knowledge/` 需要改名迁移，KaiSpan 直接以此为目标新建。
- 物理迁移**确实要做**，不是可选项，但必须先锁定 contract（schema/脚本/references 同步）再迁移物理目录，且迁移和 contract 同步作为**一个任务的不同 phase**追踪，不拆成互相独立、可能各自漂移的两件事。见下方"Physical Migration Plan"。

## Goal

重设计 `$backfill-stable-docs`，把它从偏命令行式的可执行审计框架收敛为 agent-first 的内部团队工具：它帮助 agent 从已经完成的 implementation package 中识别 durable delta，并在 owner 批准后把短期设计回刷到 system、context 或 module 层的 stable docs。

当前目标只覆盖两个内部仓库：

- `D:\CodeSpace\kaispan-dev`：典型 monorepo，多 domain / platform 文档布局。
- `D:\CodeSpace\prj-supplyer-webapp`：普通 repo，implementation package 同样来自 Impl-Package 体系。

设计前提是：backfill 是 agent 的阅读、判断和写作任务，不是纯命令行工具。脚本只能提供清单、差异、校验和记录辅助，不能用一个状态字段代替 agent 对代码、Git commit、implementation package 与 stable docs 的实际阅读。

## Non-Goals

- 不把该 skill 做成开放产品或跨任意仓库的通用平台。
- 不要求 monorepo 为每个 domain 建独立配置文件。
- 不通过复杂 canonical schema 避免 agent 阅读文档。
- 不把 `docs/epic-plans/` 纳入 backfill 来源。
- 暂不把 `hands-on-knowledge/` 与 module knowledge 混在一个 backfill 通道中；hands-on knowledge 是经验沉淀，不是当前设计/规格快照。
- 不在 audit 阶段修改 stable docs、pending register 或 done state。
- 不在常规 audit/apply 里顺带删除 package 目录；清理只通过独立、需要显式批准的 Package Retirement Workflow 执行。
- 不把 `ideas/` 草稿箱纳入 stable destination 或 source discovery；idea 尚未启动、不是 current authority，进入实施后应转入或链接 implementation package。

## Core Principle

backfill 的输入是已实现变更的短期设计，输出是 stable docs 中的当前事实。implementation package 是变更事件，stable docs 是当前快照。

backfill 的主要输入不是从零重新发现，而是消费 `dev-with-track` Stage 7 在每个 terminal gate entry 写入前已经强制登记的 `_pending.md` durable-delta 队列——那里的每条登记本来就带着 destination、delta-id、statement 和来源 evidence 指针，是 Stage 7 已经做过一次分类判断的结果。`decision.md`/`spec.md` 仍是语义来源，但作用是核验和补充 `_pending.md` 已登记条目（确认 destination 仍然对、evidence 仍然站得住、没有被后续改动推翻），而不是重新做一遍 Stage 7 已经做过的分流。

只有当某个 package 的 gate ledger 已经 terminal 关闭、实现也已经进入目标分支，却在对应 `_pending.md` 里找不到任何登记条目时（Stage 7 纪律建立之前的遗留 package，或登记时误判为 `none`），才需要 agent 退回到重新读 `decision.md`/`spec.md`/`plan.md`/`gate.md`/代码去做 gap-catching 式发现——这是兜底通道，不是默认通道。`plan.md`、review、handoff、tickets 和 Git commit 仍用于理解实际落地范围；代码和 commit diff 仍是必要证据，不因为 `_pending.md` 已经登记就免检：如果短期设计没有实际落地或尚未进入目标分支，不能回刷为 stable truth。

## Stable Knowledge Levels And Physical Layout

Stable knowledge 分成三种 semantic authority；配置字段表达语义，不要求物理目录与字段同名，`contextKnowledge` 是可选层——不配置时该仓库退化为 system + module 两层，不强迫扁平 repo 发明不存在的 context 层：

| 层 | Authority | 是否必需 | KaiSpan 目标物理位置 | prj-supplyer-webapp（webshop）目标物理位置 |
| --- | --- | --- | --- | --- |
| system knowledge | 由 `repo-wide` owner 拥有、跨 context 或无法归属单一 context 的当前事实 | 必需 | `docs/system-knowledge/**` | `docs/system-knowledge/**`（现 `docs/top-level-knowledge/`，需迁移改名） |
| context knowledge | 由单一 domain/platform context 直接拥有、跨该 context 内多个 module 的当前事实 | 可选，KaiSpan 使用 | `docs/platform/*/context/**`、`docs/domains/*/context/**` | 不使用；webshop 是扁平 repo，不建 context 层 |
| module knowledge | 只属于 context 内具体 module 的当前意图与行为合同 | 必需 | `docs/platform/*/module-knowledge/**`、`docs/domains/*/module-knowledge/**` | `docs/module-knowledge/**`（不变） |

**目录命名明确保留 `module-knowledge/`，不改成 `modules/`**：KaiSpan 是 TS monorepo，根下已有 `packages/` 作为真正的代码模块 workspace；如果 docs 侧也叫 `modules/`，两者会在长期使用中反复混淆，这条命名冲突和要不要做物理迁移无关，直接否决。`context/` 是新增子目录，用来收纳目前平铺在 context 根的 `CONTEXT.md`/`architecture.md`/`prd.md`，与 `module-knowledge/`、`implementations/`、`_pending.md` 并列。DDD 将 bounded context 视为拥有自身模型和语言的边界，并以内聚部分组织 context 内的 module；arc42 同样把 Context and Scope 与内部 Building Block 分解区分开来，这一层级与上述目录语义一致。参考：[Microsoft Domain Analysis](https://learn.microsoft.com/en-us/azure/architecture/microservices/model/domain-analysis)、[arc42 Context and Scope](https://docs.arc42.org/section-3/)、[arc42 Building Block View](https://docs.arc42.org/section-5/)。

```text
docs/
├── system-knowledge/
│   ├── product/
│   ├── architecture/                   # 含 repo-wide ADR 与跨 context seams
│   ├── terminology/
│   ├── engineering/
│   └── operations/
├── ideas/                             # 扁平草稿箱，不属于 stable docs
├── implementations/                   # repo-wide / cross-context packages
├── _pending.md                         # system-level durable delta queue
├── platform/<context>/
│   ├── context/
│   ├── module-knowledge/
│   ├── implementations/
│   └── _pending.md
└── domains/<context>/
    ├── context/
    ├── module-knowledge/
    ├── implementations/
    └── _pending.md
```

`context/` 不是 C4 意义上仅包含一张 Context Diagram 的目录；它承载该 owner 的当前 PRD、架构、术语、journey 与跨模块合同。`module-knowledge/` 中每个 module 的 `prd.md`/`spec.md` 仍分别拥有 intent 与 behavior。`system-knowledge/` 不是 ownerless knowledge，它由 `repo-wide` owner 直接拥有。

KaiSpan 现有 repo-wide `docs/operations/`、`docs/engineering/` 等平铺目录在目标态分别迁入 `docs/system-knowledge/operations/`、`docs/system-knowledge/engineering/`；只服务某个 context 的运行知识则进入该 context 的 `context/` 或明确的 hands-on knowledge 路由。`docs/platform/identity-access/` 仍是一个 platform context，因此它内部拥有自己的 `context/`、`module-knowledge/`、`implementations/`，不会被折叠成单一 `platform/context/` 下的 module。

prj-supplyer-webapp 是扁平结构，没有多 context 分区：`docs/module-knowledge/` 本身已经同时承担 context 和 module 的角色，因此它的目标态只有两层——`docs/system-knowledge/`（现 `docs/top-level-knowledge/` 改名）与 `docs/module-knowledge/`（不变），`contextKnowledge` 字段留空。

## State Model

状态只保留三类：

| 状态 | 含义 | 谁来判断 |
| --- | --- | --- |
| `candidate` | 有 durable delta 迹象，可能需要处理 | 两条来源：(1) 主渠道——`_pending.md` 中尚未关闭的登记条目，agent 复核后确认仍然成立；(2) gap-catching——gate 已 terminal 关闭但 `_pending.md` 里没有对应登记的 package，由 agent 主动发现 |
| `pending` | 有 durable delta 迹象，但目标文档、事实冲突、证据充分性或 owner 裁决未闭合 | agent 提出，owner 裁决或后续 evidence 关闭；对应 `_pending.md` 条目保持未关闭 |
| `done` | 已回刷，或 owner 明确决定无需回刷 / 由其他 stable home 承载 | apply / verify / owner decision 记录，同时关闭对应 `_pending.md` 条目 |

`candidate -> pending -> done` 是工作状态，不是事实来源。状态只引导下一步阅读和处理，不决定内容是否真实。`_pending.md` 本身就是这条状态机的持久化载体——它是 Stage 7 已经在维护的队列，backfill 只负责读取、核验和关闭，不另开一份平行清单。

## Config Model

每个 repo 只保留一个配置文件。配置的职责是告诉 agent 去哪里读、哪里写、哪些路径忽略，以及记录文件放在哪里。

建议默认路径：

```text
.stable-docs-backfill.json
```

建议配置形状：

```json
{
  "schemaVersion": 3,
  "repository": "fangxiao-dev/KaiSpan",
  "implementations": [
    "docs/implementations",
    "docs/platform/*/implementations",
    "docs/domains/*/implementations"
  ],
  "stableDocs": {
    "systemKnowledge": [
      "CONTEXT-MAP.md",
      "docs/README.md",
      "docs/system-knowledge"
    ],
    "contextKnowledge": [
      "docs/platform/*/context",
      "docs/domains/*/context"
    ],
    "moduleKnowledge": [
      "docs/platform/*/module-knowledge",
      "docs/domains/*/module-knowledge"
    ]
  },
  "ignore": [
    {
      "paths": ["docs/epic-plans", "docs/**/hands-on-knowledge", "docs/ideas"],
      "owner": "repo-wide",
      "reason": "not implementation source or stable destination; excluded regardless of context"
    }
  ],
  "records": {
    "pending": "auto",
    "pendingOverrides": {},
    "done": "docs/_backfill/done.json",
    "reports": "docs/_backfill/reports"
  }
}
```

`repository` 必须是 git remote 的 `owner/repo` 身份（例如 `fangxiao-dev/KaiSpan`、`FujigawaFood/fujigawafood-webapp`），不是本地文件夹名；它至少用于人类可读的记录归属，不因为放弃了旧版的 fail-closed 双锚点就可以写错。

上面这份是 KaiSpan 的**目标态**配置，`context`/`module-knowledge` 两个 root 要等 Physical Migration Plan 的 Phase 2 完成后才会真正在磁盘上出现——Phase 1（本节 schema 同步）完成、Phase 2 尚未执行期间，`contextKnowledge` root 会展开成空集，这是预期状态，不代表配置写错。prj-supplyer-webapp（webshop）的等价目标配置只有两层：`systemKnowledge` 指向 `docs/system-knowledge`（迁移前是 `docs/top-level-knowledge`），`moduleKnowledge` 指向不变的 `docs/module-knowledge`，`contextKnowledge` 字段整体省略。

字段表达 repo 内布局，不表达多个独立配置 context。`systemKnowledge`、`contextKnowledge`（可选）、`moduleKnowledge` 是稳定语义层；物理目录名和字段名不要求相同，但本次修订后 KaiSpan 与 webshop 的目标物理名统一收敛为 `system-knowledge/`、`context/`（仅 KaiSpan）、`module-knowledge/`。monorepo 的差异由 glob 和 stable doc destinations 承载；agent 在审计时根据 implementation package 的路径、owner-local docs、CONTEXT/README 路由和代码影响范围判断目标 stable home。

`ignore` 从扁平字符串数组改成按 owner 分组的条目数组：每组自带 `owner`（通常是 domain/platform context 名，仓库级排除写 `"repo-wide"`）和 `reason`。这不引入新配置文件——仍然是同一个 `.stable-docs-backfill.json`——但让确实需要长期排除的路径有清楚归属和理由。KaiSpan finance-assistant 旧实验配置中的 15 条历史 exclude 已在第二轮 litmus 中逐条由 agent 人工消化：1 条判定为 already-covered，14 条判定为 no-delta；它们是一次性审计输入，不迁入 v3 `ignore`，旧实验配置只作为 provenance 保留。新增排除项时必须有持续有效的排除理由，并带 `owner` 和 `reason`，不能把“这次已经审完”当成永久 ignore 理由。

`records.pending` 不是一个新文件，它必须指向 `dev-with-track` Stage 7 已经在写的 `_pending.md`。`_pending.md` 是 owner/context 层的流程状态，必须与 `context/`、`module-knowledge/`、`implementations/` 并列，不能放进任何 current knowledge 目录。真实布局里这个文件的位置随 stable authority root 的层级变化，不是单一固定路径：

- 目标态普通 repo：`docs/_pending.md` 与 `module-knowledge/`、`implementations/` 同级；迁移期继续支持 prj-supplyer-webapp 已存在的 `docs/module-knowledge/_pending.md`。
- 目标态 monorepo：每个 domain/platform context 有自己的 `_pending.md`，与该 context 的 `context/`、`module-knowledge/`、`implementations/` 同级，例如 `docs/domains/finance-assistant/_pending.md`；repo-wide/system 队列为 `docs/_pending.md`。

**system 级 `docs/_pending.md` 目前在两个仓库里都不存在，是全新文件，不是"发现歧义"场景**：发现规则里的"两处都存在或都不存在时报 config gap"是给已有过 pending 文件历史的 root 用的；system 级是首次冷启动，不能套用同一条规则粗暴报 gap。Phase 1 同步实现时需要明确：system 级 `_pending.md` 缺失时，audit 是报告"待 owner 决定是否现在创建"，还是由 backfill 自己在 owner 明确同意后创建一个空文件起步——这是一条独立于本次已确认决定的开放问题，留给下一步同步实现时向 owner 确认，不在本轮方案里替 owner 决定。

`records.pending: "auto"` 时，对每个配置的 system/context/module stable root，agent 依次检查该 root 自身目录和它的上一级目录是否存在 `_pending.md`，再按解析后的 pending 路径去重：恰好存在一处即为该 owner 的权威 pending register；两处都存在或都不存在时停下来向 owner 报告 config gap，不能猜。无法自动判定的 root 可以在 `pendingOverrides` 里显式给出 `"<stableDocs 相对路径>": "<pending.md 相对路径>"`，跳过自动发现。KaiSpan 当前迁移态必须把 finance-assistant 显式指向父级 `docs/domains/finance-assistant/_pending.md`，不能因为 `module-knowledge/` 内还存在同名文件就自行选择。

## Litmus Dry-Run Findings

第一轮（prj-supplyer-webapp）是真正跑过工具、留有 audit report、apply record 和 done.json 的正式 dry-run，结论可复核：暴露了旧格式 `gate.md` 无法机械解析、gate 顶部摘要与 append-only ledger 可能不同步、checklist 状态不能证明代码已经落入目标分支等问题。新版 audit 必须让 agent 读完整 gate ledger，并以 Git 目标分支中的实际提交为 package completion 证据。

第二轮（KaiSpan）**不是一次正式工具 audit，是针对当前仓库真实命名（`module-knowledge/`，不是本文档 Config Model 描述的目标态 `module-knowledge/`+`context/` 组合）做的人工核对，未落地任何 config 文件或 report**，独立评审时确认 kaispan-dev 仓库里没有任何 `.stable-docs-backfill.json`、`docs/_backfill/` 或相关 git 记录。以下结论按此前提理解，不代表已经用目标 schema 正式跑过：

- KaiSpan 当前有 9 个 implementation roots（已独立核实为真）。
- 现有 5 个 `module-knowledge/` root 里，`_pending.md` 自动发现出现 1 个歧义和 4 个缺失；finance-assistant 已确认使用父级 `docs/domains/finance-assistant/_pending.md`（已独立核实存在）。其余缺失在配置或目录迁移明确前都必须报告 config gap，不能猜。
- 12 个历史 gate 经人工分类：8 个 historical non-current、2 个 nonterminal、1 个 docs-refactor 虽 terminal 且已合入但仍有 decision/spec 与 inbound references，不能 retirement、1 个 DATEV gate 文本 terminal 但代码未进入 `origin/develop`（`2026-07-14-datev-format-validator-spike` 的判断方向与此一致：gate 里同时出现"terminal pass"与"do not describe the whole package as closed"的措辞，用户主工作区当时也确实检出在个人分支而非 `develop`）。机械识别失败不是请求 owner 裁决的充分理由；agent 必须先完整阅读，只有证据真的矛盾或缺失时才升级。这 12 个的精确编号未留存可复核的持久化记录，标记为 unverified，仅作方向性参考。
- KaiSpan 本轮读到的 Stage 7 registered candidates 为 0、gap-catching candidates 为 0、Package Retirement candidates 为 0。零候选是有完整解释的有效结果，不能为了满足测试数量制造候选；但这个结论同样需要在 Phase 1 schema 同步、Phase 2 物理迁移完成后，用真正落地的 config 重新正式跑一遍 audit 并留存 report 才能确认，不能只依赖这次人工核对。
- package 是否完成由代码是否实际进入配置的目标分支决定，不由 gate checklist 是否打勾决定。已经落地的 package 即使仍有非阻塞遗留项，也可视为本次实现闭合；遗留项建议作为独立 GitHub issue 跟踪，不能据此把 package 永久挂成未完成。创建 issue 仍是外部副作用，必须在当前 session 获得 owner 对具体事项的明确授权。

## Physical Migration Plan

三层 schema 的 contract 变更和两个仓库的物理目录迁移是**一个任务的不同 phase**，不拆成两个可能互相漂移的独立事项；Phase 1 完成的定义里必须包含"Phase 2/3 已经排进同一个任务"，不能只交付文档就算数。

- **Phase 1 — Contract**：把 `contextKnowledge` 实现为可选字段，`moduleKnowledge` 保持指向 `module-knowledge/`（不引入 `modules/`），`systemKnowledge` 的目标命名统一为 `system-knowledge/`；同步改 `repository-config.schema.json`、`repository-config.example.json`、`stable_docs_config.py`、`collect_sources.py`、`verify_stable_docs.py`、`source-selection-and-pending-consumption.md`、`constraint-extraction-and-routing.md`、`audit-runbook.md`——必须一次改完，不允许再出现"方案文档一个样子、skill 代码另一个样子"的缺口。这一步产出的两份 repo config 用的是目标路径，Phase 2/3 完成前 `contextKnowledge`（KaiSpan）和迁移后的 `systemKnowledge`（webshop）root 会展开成空集，这是预期状态。
- **Phase 2 — KaiSpan 物理迁移**：把每个 platform/domain context 根目前平铺的 `CONTEXT.md`/`architecture.md`/`prd.md` 挪进新建的 `context/` 子目录；同步更新 `CONTEXT-MAP.md`、`AGENTS.md`、`docs/agents/doc-governance.md` 和所有 inbound 引用；`docs/operations/`、`docs/engineering/` 等 repo-wide 平铺目录迁入 `docs/system-knowledge/`；`module-knowledge/` 不动。**`doc-governance.md` 是这一 phase 明确要更新的文件之一，不是被这次重设计悬空冲突的对象**——它当前的 `module-knowledge/<module>/` 措辞在 Phase 2 里只需要补充 `context/` 的路由说明，不需要改名。
- **Phase 3 — webshop 物理迁移**：`docs/top-level-knowledge/` 改名为 `docs/system-knowledge/`；同步更新 `AGENTS.md`、`CLAUDE.md` 中对应引用（已核实至少 4 处：`vercel-env-deployment.md`、`admin-layout-grammar.md`、目录说明段落、`ard.md`/`prd-customer.md`/`prd-supplier.md`/`tech-stack.md` 所在段落）；不建 `context/`，`contextKnowledge` 字段保持不配置。

Phase 2、3 谁先做可以按 owner 意愿排序，但两者都必须在同一任务下追踪，且都要求执行前对具体迁移范围（哪些文件、哪些引用）做显式确认，属于会影响多人协作路径的变更，不是纯内部实现细节。

## Audit Workflow

Audit 是只读阶段，输出候选报告，不修改 stable docs。

1. 读取单 repo 配置，展开 implementation roots、stable doc roots（含按 Config Model 规则发现的 `_pending.md` 位置）和 ignore paths。
2. 枚举每个已发现 `_pending.md` 中尚未关闭的登记条目——这是本轮 audit 的主渠道候选种子，每条已经带 destination、delta-id、statement 和来源 package 指针（Stage 7 登记时写入）。
3. 对每条 `_pending.md` 登记条目：回到其来源 package 重新核对 `decision.md`/`spec.md`/`plan.md`/gate entry，确认 statement 仍然准确；核对当前代码和测试，确认设计仍然落地、没有被后续改动推翻；核对 destination 处的 stable docs，判断是否已被别的 apply 覆盖。三者任一冲突就写入报告并标记为需要 owner 裁决；agent 不自行改写 `_pending.md` 登记内容本身——登记内容的修改权属于来源 package 的 gate，不属于 backfill。
4. 补充做 gap-catching 扫描：枚举 gate ledger 有 terminal entry、实现也已进入目标分支、但在对应 `_pending.md` 中找不到任何登记条目的 implementation package。这类 package 要么是 Stage 7 纪律建立之前的遗留 package，要么是 gate 登记时误判为 `none`。只有这些 package 才需要 agent 从 `decision.md`、`spec.md`、`plan.md`、review、handoff、tickets 和 Git commit 重新发现候选。
5. 对 gap-catching 发现的候选，同样解析相关 Git commit / branch / diff（缺少显式 commit 时按 package 日期、相关文件、plan execution record 和 Git history 做有界确认），并对照目标分支当前代码和测试确认设计是否实际落地；代码与短期设计冲突时，以当前实现和最终 evidence 为准，并把冲突写入报告。仍未进入目标分支的实现不进入 durable-delta candidate，而是作为 package-not-closed 报告。
6. 对照 stable docs，判断每条候选（无论来自主渠道还是 gap-catching）是否已覆盖、需要回刷、应 pending，或不属于 stable docs。
7. 生成 audit report，明确区分“来自 `_pending.md` 登记的候选”和“gap-catching 发现的候选”两类来源，并列出 candidate、pending proposal、already-covered、rejected-with-reason 和需要 owner 决策的 item。

`gate.md` 和 `_pending.md` 都不作为唯一判定依据。按 `impl-package-composition-contract.md` §7，应读取 append-only gate ledger 的 terminal entry；顶部摘要或 checklist 只能作为导航，不能覆盖 ledger，更不能代替目标分支 Git 证据。旧格式无法机械解析时由 agent 完整阅读并正常分类，只有真实证据矛盾或缺失才提交 owner 裁决。

## Apply Workflow

Apply 是写入阶段，只处理 owner 已批准的 report item。

每个 apply item 必须明确：

- 来源 package。
- 目标 stable doc。
- durable delta 类型：system PRD / system architecture or ADR / context PRD / context architecture or contract / module PRD / module spec / context language。
- 代码或 commit 证据。
- 与现有 stable docs 的关系：新增、修正、替换、删除废弃说法或 no-op。

Apply 写入 stable docs 后，把对应 item 记录为 `done`：

- 若该 item 来自 `_pending.md` 的既有登记，apply 必须同时在该 `_pending.md` 中把对应行标记为已处置（划掉或删除，按项目既有约定），不能只写自己的 `done.json` 而留 `_pending.md` 条目继续挂着——否则下一轮 audit 会把它当新候选重新报一遍。
- 若该 item 来自 gap-catching 发现（`_pending.md` 中原本没有对应登记），apply 除了写入 stable docs，还要先补一条 `_pending.md` 登记再标记为已处置，保持“未决登记只活在 `_pending.md`”这条不变式，不在 backfill 自己的 records 里维护一份平行副本。
- 如果 owner 决定不回刷，也以 `done` 记录 decision 和原因，并同样关闭对应 `_pending.md` 条目，避免后续 audit 反复提出同一项。

### Destructive Apply（独立于普通 apply 的更高门槛）

以下操作不能靠普通 apply item 的“owner 批准该 item”覆盖，必须额外拿到显式的 destructive-apply 授权：

- 移动、重命名或删除已有 stable doc 内容（而不是新增/修正/替换其内容）。
- 批量删除或重组遗留语料目录（例如迁移后废弃的旧专题路径）。
- Package Retirement（见下）清理 implementation package 目录。

Destructive apply 的批准必须精确到具体路径或 package id 的清单，不能用“这批全部处理”代替；批准 Package Retirement 候选、执行删除和创建 GitHub issue 都必须在当前 session 获得针对具体对象的明确授权，先前 session 对其他对象的授权不延续。批准后仍需在执行前重新核对目标路径未在批准之后发生新变化，避免用过期批准执行已经不适用的删除。

## Verify Workflow

Verify 是独立检查阶段，不隐式修复。

它检查：

- 已标记 `done` 的 item 是否仍能追溯到 implementation package 和代码证据。
- stable docs 是否存在断链、重复事实源或明显冲突。
- pending item 是否仍然有未解决 owner decision 或 evidence gap。
- 配置中的 implementation roots 和 stable doc roots 是否仍覆盖当前仓库布局。
- 是否存在已完全吸收、gate 已终态、只剩过程性目录的空壳 package——标记为 Package Retirement 候选，不在 verify 里直接清理。

Verify 发现问题时只报告，不自动 apply。

## Package Retirement Workflow

一次性迁移和历史 bootstrap 会留下大量 package：它们的 durable delta 已经被吸收进 stable docs、gate 已经 terminal 关闭，目录里剩下的只是 `evidence/`、`tasks/`、`tickets/`、`_compaction/` 这类过程性内容，不再提供任何仍需查阅的信息。这些“空壳” package 不应无限期占用 `docs/implementations/`，但清理是破坏性操作，必须显式 owner 批准，不能在普通 audit/apply 里顺带做掉。

### 识别 GC 候选

Verify（或独立的 `gc` 扫描）按以下条件识别候选，不自动清理：

1. append-only gate ledger 已 terminal（pass/fail/defer）——顶部摘要或 checklist 不足以证明 terminal，Active/blocked 的 package 永不作为候选。
2. Git 已证明 package 声称的实现实际进入配置的目标分支；gate 自述已 merge 不能替代这一条。
3. 该 package 产生的所有登记在任何已发现的 `_pending.md` 里都已关闭（没有仍指向它的未决条目）。
4. package 目录下 `decision.md`/`spec.md` 要么不存在，要么其内容已被判定为 already-covered（已被当前 stable docs 完整吸收），且没有其他文档的 inbound reference，不再提供任何仍需保留的信息。

满足以上四条时列为“可清理候选”，附上 gate 终态、目标分支 Git 证据、closure 时间、吸收去向（具体 stable doc 路径）、inbound reference 检查和目录当前剩余内容清单。四条缺一即保留，不因为“看起来只有 evidence”就放宽判断——必须真的核对过目标分支、`_pending.md`、stable docs 和 gate ledger。

例如 prj-supplyer-webapp 里 `docs/implementations/legacy-plan-conflict-closeout/`、`legacy-impl-plans-retirement/` 这类命名本身就提示已是历史收尾产物，属于值得优先核实的候选；但具体是否满足上面三条仍需逐一核实，不能只凭包名判断。

### 清理执行

清理属于 Destructive Apply（见 Apply Workflow），需要 owner 对具体 package id 清单显式批准，不能用“全部清理”当批准。批准后：

- 确认待删除内容已经反映进当前 stable docs（逐条对照 `done.json` 或 `_pending.md` 关闭记录）；
- 确认没有其他 package 或 stable doc 仍在引用这里的具体文件（比如别的 `decision.md` 链接到本 package 的截图或数据），有引用时改为暂缓清理并报告；
- 删除整个 package 目录，提交为一次独立 commit，不与其他内容变更混在一起，方便日后按 commit 找回；
- 在 `done.json`（或新增的轻量 `retired.json`）记录被删除的 package id、closure 证据（gate entry id）、吸收去向和删除 commit——这条记录本身就是新的 provenance 指针，替代原来的目录。

删除后 provenance 由 Git 历史承载（该 package 曾经存在、其内容和删除时间都在 commit log 里），不要求 package 目录本身永久保留才算“保留 provenance”。

## Records

记录层保持轻量：

- `_pending.md`：Stage 7 已经在维护、backfill 只负责消费和关闭的唯一未决队列，位置见 Config Model 的发现规则。backfill 不另开一份自己的 pending 清单。
- `done.json`：机器可读的去重记录，记录 source package、source evidence、target doc、decision、applied commit 或 decision 时间，以及对应 `_pending.md` item 的关闭引用。
- `reports/`：audit report 输出目录，报告可丢弃但应足够 owner 审阅；报告需要区分“来自 `_pending.md` 登记”与“gap-catching 发现”两类候选来源。

不再使用复杂 carry-forward 概念。未关闭的 `_pending.md` 条目本身就是 carry-forward；下次 audit 直接读取各处 `_pending.md` 现状和 `done.json` 后继续处理，不需要单独的 carry-forward 字段。

## Source Selection Rules

默认纳入：

- `docs/implementations/**`
- `docs/platform/*/implementations/**`
- `docs/domains/*/implementations/**`
- 普通 repo 中配置指定的 implementation root

默认排除：

- `docs/epic-plans/**`
- `docs/**/hands-on-knowledge/**`
- `docs/ideas/**`；它只承载尚未启动的未来想法，不是 current truth、implementation evidence 或 backfill destination
- 临时 exchange、scratch、generated reports，除非配置显式纳入

Package 进入 candidate 的条件不是单一文件存在，而是 agent 能找到足够的 implementation package 结构和完成证据。`gate.md` 缺失时可以进入 pending 或 lower-confidence candidate，但不能因为缺失 gate 就忽略明显已落地且有 commit 证据的 package。

`_pending.md`（连同其登记条目指向的来源 package）永远在扫描范围内，不受 `ignore` 列表影响；`ignore` 只影响 gap-catching 阶段要不要重新扫描某个 package 目录，不影响主渠道读取已登记的候选。

## Stable Destination Rules

Backfill 的目标是 stable design knowledge：

- 跨 context、无法归属单一 context 的 repo-wide 产品、系统架构、跨 context seam、全局术语、engineering 和 operations 当前事实进入 `systemKnowledge`；KaiSpan 的目标物理位置是 `docs/system-knowledge/**`。
- 由单一 domain/platform context 拥有、但横跨其内部多个 module 的当前 PRD、架构、术语、journey 与合同进入 `contextKnowledge`；KaiSpan 的目标物理位置是各 context 的 `context/**`。
- module 存在目的、用户价值、outcome、scope / non-goals 进入 module `prd.md`。
- module 行为、接口、状态、权限、失败语义、验收约束进入 module `spec.md` 或其子域合同文件。
- `ideas/` 只接收尚未启动的未来想法；一旦进入设计或实施协作，应转入或链接 implementation package，不能从草稿箱直接回刷为 current truth。
- implementation package 保留 provenance，不成为长期 SoT（provenance 可以是 Git 历史，不要求 package 目录本身永久存在；完全吸收且 gate 已终态的空壳 package 按下方 Package Retirement Workflow 清理）。

如果一个 delta 同时包含 why 和 how，apply 前拆分成 PRD delta 和 spec delta。不能把同一句话原样复制到两个 stable home。

新建 module `prd.md` 沿用现有惰性创建门（见 `skills/impl-package/backfill-stable-docs/references/constraint-extraction-and-routing.md#module-prd-惰性创建门`）：必须同时具备 Purpose、用户或 journey、Outcomes、Scope/Non-goals，且能上链到 owning context 的 PRD（跨 context 时再上链到 system PRD）、下链到 module spec，intent authority 来自 system/context PRD、批准 design、owner 决策或 confirmed gate。材料不足时留在 `_pending.md`，不创建只有标题和一句 slogan 的空文件。这条门槛这次重设计不降级，agent-first 不等于降低首建 module PRD 的证据门槛。

## Agent Responsibilities

Agent 在 audit/apply 时必须承担判断责任：

- 实际阅读相关 implementation package，而不是只消费脚本输出。
- 实际核对相关代码、测试和 Git diff。
- 明确指出短期设计、代码实现和 stable docs 之间的冲突。
- 在证据不足时进入 pending，而不是猜测性写入 stable docs。
- 对 owner 决策保持可追溯记录。

脚本可以辅助：

- 枚举 package。
- 找 gate entries。
- 搜索 touched files 和 commit range。
- 生成 report skeleton。
- 校验 links、done 去重和 pending 覆盖。

脚本不能替 agent 做事实裁决。

## Migration From Current Design

现有 `$backfill-stable-docs` 中以下假设需要降级或替换：

- `stableDocs.topLevel` 拆成明确的 `systemKnowledge`、`contextKnowledge`（可选）、`moduleKnowledge` 三层语义；KaiSpan 目标物理目录采用 `docs/system-knowledge/` 与 context 内新增的 `context/`，`module-knowledge/` 命名保留不变（不改成 `modules/`，避免与 monorepo 根下真正的代码 `packages/` workspace 混淆）；`top-level-knowledge/` 作为目标命名被 `system-knowledge/` 取代，两个仓库统一收敛。
- “每份配置只定义一个 context”改为“每个 repo 一个配置，路径规则表达 repo 内布局”；原本靠多份独立 per-domain 配置文件（如 kaispan 实验用的 `docs/domains/finance-assistant/_compaction/backfill-experiment/config.json`）表达的按域 exclude 颗粒度，现在由同一份仓库级配置里 `ignore` 数组的按 owner 分组条目表达，不需要为每个 domain 开新配置文件，但保留原来的归属和理由颗粒度。
- KaiSpan 旧 finance-assistant 实验配置里的 15 条 exclude 不做机械 schema migration：第二轮 litmus 已逐条人工分类为 1 条 already-covered、14 条 no-delta，新仓库级配置不携带这些临时历史排除；旧配置保留原样作为 provenance。
- `carry_forward` 改为 pending register 的自然延续，不再作为独立状态机制。
- 这里的 watermark 特指 backfill 自己的扫描下界优化（backfill scan watermark），与 `impl-package-composition-contract.md` 里 attempt 级的 `Module Knowledge Watermark`（记录 plan 依赖的 module-knowledge commit SHA，用于判断某个 attempt 依赖是否被后续改动推进）是两个不同概念，不共用同一个不加限定的“watermark”说法。backfill scan watermark 不再作为 fail-closed 的唯一入口；它可以作为扫描优化和重复控制，但不能阻止 agent 对 owner 指定 package 做审计。
- audit JSON contract 保留为可选机器辅助输出，不作为 agent 工作的唯一事实形态。
- apply 仍然必须绑定 owner 批准的 item，避免 audit 自动写入 stable docs；破坏性操作（移动/删除/重命名、Package Retirement）需要独立于普通 item 批准的 destructive-apply 授权，见 Apply Workflow。
- backfill 不再自建一份新的 pending 队列；`_pending.md` 从“Stage 7 的登记终点”升级为“backfill audit 的默认输入起点”，两边共用同一份文件，不重复维护。
- 现有 `docs/module-knowledge/_pending.md`（prj-supplyer-webapp）与各 domain 的 `_pending.md`（kaispan-dev）在迁移期继续作为权威队列，不因为目录目标态变化被替换或旁置；KaiSpan finance-assistant 明确使用父级 `docs/domains/finance-assistant/_pending.md`。里面已有的未决登记（例如 prj-supplyer-webapp 那条 METRO EDI 遗留意图）在首轮新版 audit 里必须被读到，不能因为改版而失联。旧 `docs/module-knowledge/_compaction/state.json` 里的 `carry_forward`、`last_applied_item_ids` 等历史记录只作 provenance 参考，首轮新版 audit 以当前各处 `_pending.md` 现状为准重新生成 report，不强行转换旧 schema。
- `references/constraint-extraction-and-routing.md`（两问 litmus、约束型合同清单、Source 顺序、惰性 PRD 创建门、人工 fixtures）保留为 agent 判断参考，不因这次重设计删除；被这版简化模型取代的只是 `audit-json-contract.md`、`source-selection-and-dual-anchor.md` 里严格 schema/fingerprint/双锚点部分，不影响其中的判断辅助内容。
- implementation package 不再假设永久保留目录；已完全吸收、gate 已终态的空壳 package 按新增的 Package Retirement Workflow 清理，provenance 转由 Git 历史承载。

## Acceptance Criteria

- KaiSpan 可以用一个 repo-level config 表达 system/context/module 三层 stable authority（`contextKnowledge` 可选），覆盖 9 个 repo-wide、platform 和 domain implementation roots，并在每个 owner 上发现唯一 pending register；当前 finance-assistant 使用显式 override 指向父级 `docs/domains/finance-assistant/_pending.md`，其余歧义或缺失必须成为 config gap，不能猜。
- webshop 可以用同一 schema 表达为 system/module 两层（`contextKnowledge` 不配置），目标 `systemKnowledge` 指向迁移后的 `docs/system-knowledge/`；Phase 3 完成前指向迁移前的 `docs/top-level-knowledge/` 作为过渡态。
- Phase 1 同步实现时必须显式定义"目标分支"字段或规则（例如新增 `targetBranch` 配置，说明它和 SKILL.md 已有的"工作区基准"章节——默认用主 Git 工作区、不等同 `main`/`develop`——如何共存），不能让"package completion 用 Git 验证是否进入目标分支"这条规则在不同仓库、不同工作区分支下有歧义解读。
- prj-supplyer-webapp 首轮 audit 时，`docs/module-knowledge/_pending.md` 中现有的未决登记（如 METRO EDI 那条）必须原样出现在 report 的候选列表里，不因改版而丢失或需要重新发现；同时确认 audit 不读取 `docs/epic-plans/`。
- Audit report 中每个需要回刷的 item 都能指向 package evidence、Git/code evidence 和目标 stable doc，且能区分它来自 `_pending.md` 登记还是 gap-catching 发现。
- 旧格式 `gate.md` 无法机械识别 verdict 时，agent 会完整阅读 gate ledger 并给出正常分类；只有 evidence 真正矛盾或缺失时才升级为 owner decision，不把“需要人工读”本身当作最终结论。
- package completion 必须用 Git 验证实现是否进入配置的目标分支，不能用 gate 文本或 checklist 代替；非阻塞遗留项可以建议独立 issue 跟踪，但不阻止已落地 package 闭合，创建 issue 需要当前 session 的明确授权。
- KaiSpan 旧 finance-assistant 配置的 15 条 exclude 在迁移测试中必须保持逐条分类结果（1 条 already-covered、14 条 no-delta），且不出现在新 v3 ignore 列表里。
- Apply 只处理 owner 批准 item，并能把已处理或明确不处理的 item 记录为 `done`；apply 一个来自 `_pending.md` 的 item 后，对应登记行必须被关闭，下一轮 audit 不再重复报告同一条。
- Verify 能检查 `_pending.md`/done/stable docs 的一致性，但不隐式修复。
- Audit/verify 允许给出零 gap-catching candidate 或零 Package Retirement candidate，只要逐项排除理由完整；若出现 retirement 候选，必须同时满足 gate terminal、代码已进入目标分支、pending 全关闭、stable docs 已完整吸收、无仍需保留的 decision/spec 或 inbound reference，不能为了满足测试数量放宽条件。
- 破坏性操作（destructive apply、Package Retirement）在提案里与普通 apply item 明确区分，且都要求精确到路径/package id 的显式批准，不接受“全部处理”这类笼统批准。

## Confirmed Decisions And Remaining Implementation Work

| 决策点 | 已确认口径 / 剩余工作 |
| --- | --- |
| Stable authority | 配置使用 `systemKnowledge`（必需）、`contextKnowledge`（可选）、`moduleKnowledge`（必需）；KaiSpan 目标物理目录为 `system-knowledge/`、`context/`、`module-knowledge/`（不改名）；webshop 目标物理目录为 `system-knowledge/`（现 `top-level-knowledge/`）、`module-knowledge/`（不变），不使用 `context/` |
| Ideas | `ideas/` 是不分层的草稿箱，只放尚未启动的未来想法，不属于 stable docs 或 backfill 输入 |
| 配置文件名 | 继续使用 `.stable-docs-backfill.json`，升级 schemaVersion 到 3 |
| pending 记录位置 | 不新建文件；`records.pending: "auto"` 按 Config Model 的发现规则定位既有 `_pending.md`，歧义时用 `pendingOverrides` 显式指定；system 级使用 `docs/_pending.md` |
| pending 发现歧义 | 某个 stable root 的自身目录和上级目录同时存在或都不存在 `_pending.md` 时，audit 报 config gap 并停止该 root 的处理，不猜测；KaiSpan finance-assistant 使用已确认的父级文件 |
| done state 位置 | 默认 `docs/_backfill/done.json`，避免污染 stable docs 正文 |
| Litmus 状态 | prj-supplyer-webapp 与 KaiSpan 两轮 dry-run 已完成设计验证；下一步是同步更新实际 skill、references 与脚本 schema，再回归两仓库 |
| 旧 v2 report 兼容 | 只作为 historical provenance，首轮 v3 audit 重新生成 report |
| destructive-apply 批准粒度 | 精确到路径或 package id 清单，不接受“全部处理”；批准后执行前重新核对目标未发生新变化 |
| Package Retirement 记录位置 | 实现阶段在复用 `done.json` 与新增轻量 `retired.json` 之间选择；无论选哪一个，都要记录 closure 证据（gate entry id）、目标分支 Git 证据、吸收去向和删除 commit |
| ignore 列表分组粒度 | 按 owner（通常是 domain/platform 名）分组，仓库级排除用 `"repo-wide"`；新增条目强制带 `owner` 和 `reason` |
