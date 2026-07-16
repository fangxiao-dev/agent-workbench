---
name: backfill-stable-docs
description: Use when auditing, applying approved durable knowledge deltas, retiring fully-absorbed implementation packages, or independently verifying an evergreen module-knowledge layer.
---

# Backfill Stable Docs

公共入口 `$backfill-stable-docs` 维护项目的常青 module-knowledge 快照。它只做意图路由：默认执行 audit；apply、verify 和 package retirement 分别加载独立 runbook。不要把 runbook 名当成独立 Skill。

## Agent-First 前提

backfill 是 agent 的阅读、判断和写作任务，不是纯命令行工具。脚本只能提供清单、差异、校验和记录辅助（枚举 package、找 `_pending.md` 登记、搜索 touched files 和 commit range、生成 report skeleton、校验链接/done 去重/pending 覆盖），不能用一个状态字段代替 agent 对代码、Git commit、implementation package 与 stable docs 的实际阅读，也不强制要求 fingerprint、双锚点这类机械 state machine 作为唯一事实形态。

机械识别不到的信号（比如 legacy gate.md 把 verdict 写成自由文本、不是新模板的固定 heading）只是脚本的能力上限，不是 agent 的能力上限。规则本来就是"能读懂就能判断"，固定格式只是给脚本一个加速识别的捷径，不是判断能力的天花板。脚本标出"无法机械解析"时，agent 必须在同一轮里把这些内容自己读完、给出正常分类（candidate / already-covered / conflict / no-delta，或 Package Retirement 候选），不能把它当成流程终点晾在那里、假装留给下一个人工来处理；只有真正读不出结论（证据本身矛盾或缺失）才升级为 owner 决策。

## 工作区基准

backfill 默认以 Git 主工作区为基准，不以当前分支名或某个特定分支为基准。主工作区指 `git worktree list --porcelain` 输出中的第一条 `worktree` 记录；它可以检出任意分支，例如 `dev-fang` 或 `develop`，不能把主工作区与 `main` 分支混同。

如果 backfill 从其他 linked worktree 启动，必须先解析并记录主工作区路径、当前分支、HEAD 和 dirty 状态，再默认基于主工作区执行 audit、apply、verify 和 package retirement。报告和 apply record 应明确写出实际使用的主工作区路径与 Source HEAD。

其他 branch/worktree 可以按需作为调研输入，但必须显式记录其 worktree 路径、分支和 HEAD。未合入其他 worktree 的内容不能默认当作仓库当前事实，也不能与主工作区证据混合后形成 backfill 结论。

如果主工作区存在未提交修改，audit 可以继续读取并报告 dirty 状态；apply 必须保留无关修改并避开冲突路径。目标文件与现有修改冲突时应停止并报告，不得自动切换分支、reset、覆盖或清理主工作区内容。

配置 `targetBranch` 与主工作区基准承担不同职责：主工作区路径与 Source HEAD 定义本轮读取 current docs/code 的快照；`targetBranch` 定义 package completion 的 Git 合入目标。脚本只执行 `git rev-parse <targetBranch>` 解析本地已有 ref，不自动 fetch，也不区分远程跟踪分支和本地分支；ref 无法解析时报告 config gap。gate 文本或 checklist 不能代替“相关实现 commit 已进入 targetBranch”的 Git 证据。

## 共享输入合同

- 目标项目必须是 Git top-level；配置取显式 `--config <path>`，否则取项目根 `.stable-docs-backfill.json`（schemaVersion 3）。`targetBranch`、`stableDocs.systemKnowledge`、`stableDocs.moduleKnowledge` 必填，`stableDocs.contextKnowledge` 可选；省略 context 层时按 system + module 两层运行。
- 每个 repo 只保留一个配置文件；monorepo 的差异由配置里的 glob 和 stable doc destinations 承载，不引入多份独立配置或 `contexts[]`。
- backfill 的主要输入是 `dev-with-track` Stage 7 已经在维护的 `_pending.md` 登记队列，不是重新发现。`_pending.md` 的位置按配置 `records.pending` 的发现规则覆盖 system、可选 context 和 module 三层并按 pending 路径去重；context/module root 缺失或歧义时报告 config gap，system 级 `docs/_pending.md` 首次不存在时报告非阻塞 `cold-start` owner decision，不自动创建。只有 gate 已 terminal、实现已进入 `targetBranch`、却找不到对应登记的遗留 package，才需要 gap-catching 式地重新读 `design.md`/`spec.md`/`plan.md`/代码。
- `ignore` 按 owner 分组，每组自带 `owner`（domain/platform 名，或 `"repo-wide"`）和 `reason`；新增排除项必须带这两个字段，不能只加路径。
- 破坏性操作（移动/删除/重命名 stable doc 内容、Package Retirement 清理 package 目录）需要独立于普通 apply item 的显式 destructive-apply 授权，精确到路径或 package id 清单，不接受“全部处理”这类笼统批准。

完整的 Config Model、Audit/Apply Workflow、Package Retirement 规则见 [来源选择与 pending 消费](references/source-selection-and-pending-consumption.md)。

## 路由

| 用户意图 | 读取 | 写入边界 |
| --- | --- | --- |
| 未指定阶段、盘点、扫描、报告 | [audit runbook](references/audit-runbook.md) | 只允许配置 `records.reports` 目录下的新报告（默认 `docs/_backfill/reports/`）；不改 canonical docs、`_pending.md`、done state 或链接 |
| 应用某报告的批准 item ID | [apply runbook](references/apply-runbook.md) | 只写 owner 明确批准的 item；来自 `_pending.md` 的 item 写入后必须关闭对应登记行；破坏性操作需要独立授权 |
| 检查已完全吸收、可清理的历史 package | [package retirement runbook](references/package-retirement-runbook.md) | 只报告候选，不自动删除；清理执行仍属于破坏性操作 |
| 检查 `_pending.md`、链接、覆盖率或残留 | [verify runbook](references/verify-runbook.md) | 不补写内容、不隐式 apply |

如果意图含混，默认 audit。apply 必须同时给出 report 路径和 owner 批准的精确 item ID；“全部处理”不是批准清单。verify 绝不因为发现问题而修复文档。

## 持久知识边界

`CONTEXT.md`/`CONTEXT-MAP.md` 与配置 `stableDocs.systemKnowledge`、可选的 `stableDocs.contextKnowledge`、`stableDocs.moduleKnowledge` 指向的目录只承载当前产品语言、意图、架构与行为。物理目录名由仓库配置决定；本次 contract 保留 `module-knowledge/`，不引入 `modules/`。退役能力的 provenance 留在 Git 历史、implementation package 或 audit/apply record；只有 owner 已批准的 future 能作为明确标记的 TODO 留下。历史输入与当前权威冲突时按 Source 顺序（见 [约束提取与分流](references/constraint-extraction-and-routing.md)）和 owner conflict gate 裁决，不通过把历史说明留在常青层回避裁决。已完全吸收且 gate 已终态的空壳 implementation package 不在常规 audit/apply 里清理，走 [package retirement runbook](references/package-retirement-runbook.md)。

## 输出

最终说明实际 runbook、Source HEAD、报告或 apply record 路径、candidate/covered/conflict/pending 计数、来自 `_pending.md` 登记与 gap-catching 各自的候选数、Package Retirement 候选（如有）与仍需 owner 决策的 item ID。只有用户明确要求 PR 时才读取 [PR Summary 模板](assets/pr-summary-template.md)。

`human-report.md` 面向 owner 阅读；目标仓库存在语言规定时，按该规定编写。
