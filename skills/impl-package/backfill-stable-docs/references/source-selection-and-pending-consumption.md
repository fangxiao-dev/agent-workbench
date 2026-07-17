# 来源选择与 pending 消费

Stable Docs Backfill 不再依赖强制的双锚点 fail-closed 校验、item-scoped fingerprint 或 `configSha256` 全局一致性作为唯一事实形态；这些机制属于历史实现，不是当前 contract 输入。当前事实来源是 agent 对 `_pending.md`、decision/spec/plan、execution-findings、代码和 stable docs 的实际阅读；`review findings` 保持 review 证据语义，`investigations/` 只有正式文档明确链接时才可作为 provenance 补充，不作为权威来源。

## Config Model

每个 repo 只保留一个 `.stable-docs-backfill.json`（contractVersion `"3.2"`）。字段：

- `repository`：git remote 的 `owner/repo` 身份，不是本地文件夹名。
- `targetBranch`：package completion 的 Git 目标 ref；脚本按 `git rev-parse <targetBranch>` 解析本地已有 ref，不自动 fetch，也不区分远程跟踪分支和本地分支。它不替代主工作区 Source HEAD：前者判断实现是否已合入，后者定义本轮读取 current docs/code 的工作区快照。
- `implementations`：implementation package 根的 glob 列表。
- `stableDocs.systemKnowledge`：repo-wide current authority 的 glob 列表，必填且非空。
- `stableDocs.contextKnowledge`：单一 domain/platform context 直接拥有的跨 module current authority glob，可选；省略时仓库退化为 system + module 两层。
- `stableDocs.moduleKnowledge`：module current authority 的 glob 列表，必填且非空；物理目录名继续使用仓库既有的 `module-knowledge/`，contract 不要求改成 `modules/`。
- `ignore`：按 owner 分组的排除条目数组，每组 `{ paths, owner, reason }`；仓库级排除用 `owner: "repo-wide"`。新增条目必须带 `owner` 和 `reason`。
- `records.pending`：默认 `"auto"`，见下方发现规则；歧义 root 用 `records.pendingOverrides` 显式指定。
- `records.done` / `records.reports`：backfill 自己的机器记录和报告输出目录，默认 `docs/_backfill/done.json` / `docs/_backfill/reports`。

## `_pending.md` 发现规则

`_pending.md` 是 `dev-with-track` Stage 7 已经在维护的登记队列，不是 backfill 另开的文件。真实布局里它的位置随 stable authority 层级变化：

- system knowledge 是单一 repo-wide owner，默认 pending register 为 `docs/_pending.md`。该文件首次不存在时返回 `cold-start`：audit 继续其他层、报告预期路径和 owner decision，不算 config gap，也不自动创建。发现其他非约定 system pending 文件时不能把它静默当作冷启动成功，必须报告歧义；非默认位置只能通过 `pendingOverrides` 明确指定。
- context/module root 依次检查 root 自身目录和上一级目录的 `_pending.md`；恰好一处存在为 `ok`，两处都不存在为 `missing`，两处都存在为 `ambiguous`。`missing`/`ambiguous` 都是 config gap，只停止该 root，不阻塞其他可解析层。
- 多个 stable roots 可以解析到同一个 owner pending register（典型情况是同一 context 的 `context/` 与 `module-knowledge/` 都指向父级 `_pending.md`）；消费登记时必须按 `pendingPath` 去重，不能把同一行重复生成两次候选。

`pendingOverrides` 以 stable root 相对路径为 key、pending 文件相对路径为 value；override 目标不存在时，system 层仍是 `cold-start`，context/module 层为 `missing`。

## 候选来源：主渠道与 gap-catching

1. **主渠道**：枚举每个已发现 `_pending.md` 中尚未关闭的登记条目——每条已经带 destination、delta-id、statement 和来源 package 指针（Stage 7 登记时写入）。agent 的工作是核验（destination 仍然对、evidence 仍然站得住、没被后续改动推翻），不是重新分类。
2. **gap-catching（兜底）**：collector 只提供尚未核验 Git reachability 的 `gapCatchingStructuralCandidates`；agent 只对“Gate 对当前 revision set 有可信 terminal resolution、相关实现 commit 已进入 `targetBranch`、但 `_pending.md` 里找不到对应登记”的 package 建立真实 `gapCatchingCandidates`，再读 `decision.md`/`spec.md`/`plan.md`/`execution-findings.md`、review、handoff、tickets 和 Git commit 去发现候选。可信当前 resolution 来自 content binding 完整核验、且 entry D/S/P 与当前 revision set 一致的 `indexed`，terminal 为 pass/fail/defer；旧格式 package 必须先完成 contract preflight 升级，`mismatch`/`manual` fail closed。`investigations/` 不进入 backfill runtime/state；只有正式文档明确链接时才可作为 provenance 补充输入，不能作为权威来源。这类 package 通常是 Stage 7 纪律建立之前的遗留 package，或登记时误判为 `none`。`targetBranch` 无法解析时报告 config gap，不用 gate 自述或 checklist 替代 Git 验证。

`_pending.md`（连同其登记条目指向的来源 package）永远在扫描范围内，不受 `ignore` 列表影响；`ignore` 只影响 gap-catching 阶段要不要重新扫描某个 package 目录。

默认排除：`docs/epic-plans/**`、`docs/**/hands-on-knowledge/**`、`docs/ideas/**`、临时 exchange/scratch/generated reports，除非配置显式纳入；`ideas/` 只放尚未启动的未来想法，不是 current truth 或 implementation evidence。

## 关闭闭环

Apply 一个来自 `_pending.md` 的 item 后，必须同时关闭该 `_pending.md` 里对应的登记行；来自 gap-catching 的 item 则先补一条登记再关闭。未决登记只活在 `_pending.md`，backfill 不在自己的 records 里维护一份平行副本——未关闭的 `_pending.md` 条目本身就是 carry-forward，不需要单独的 carry-forward 字段。

## 破坏性操作

移动、重命名或删除已有 stable doc 内容，批量删除/重组遗留语料，以及 Package Retirement 清理 package 目录，都属于 destructive apply：需要 owner 在当前 session 对具体路径或 package id 清单显式批准，先前 session 的授权不延续；不接受"全部处理/全部清理"这类笼统批准，执行前要重新核对目标未在批准之后发生新变化。详见 [package retirement runbook](package-retirement-runbook.md)。

## 判断辅助（不因简化而降级）

module `prd.md` 首建仍然要求 Purpose、用户或 journey、Outcomes、Scope/Non-goals 齐全，且能上下链和有明确 intent authority——见 [约束提取与分流](constraint-extraction-and-routing.md#module-prd-惰性创建门)。这是判断辅助，不是这次简化想拆掉的机械 state machine，agent-first 不等于降低首建证据门槛。
