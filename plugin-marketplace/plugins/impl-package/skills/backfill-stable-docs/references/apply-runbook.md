# Apply Runbook

Apply 将 owner 的明确批准解析并记录为精确 report/CLI item ID 集合；对已展示且未变化报告的明确批量批准可直接解析。冲突项、未决选择和 destructive apply 另行裁决；集合不明确时才询问。每个 apply item 必须明确来源 package、目标 stable doc、durable delta 类型（system PRD / system architecture or ADR / context PRD / context architecture or contract / context language / module PRD / module spec）、代码或 commit 证据，以及与现有 stable docs 的关系（新增、修正、替换、删除废弃说法或 no-op）。仓库没有配置 `contextKnowledge` 时不得发明 context destination。

写入 stable docs 后，把对应 item 记录为 `done`（`records.done`）：

- 每条 done 记录至少包含 `id`（`<package-path>::<delta-id>`）、`packagePath`、`deltaId`、`comparisonCommit`，以及 disposition/decision 说明。这是 gap-catching 去重的唯一机器依据。
- 若该 item 来自 `_pending.md` 的既有登记（`origin: pending-registry`），同时在该 pending 文件中关闭对应行（划掉或删除，按项目既有约定），避免人工队列继续挂着。
- 若该 item 来自 gap-catching（`origin: gap-catching`），**只写 `records.done`**，不要为了“关闭”去伪造一条 pending 再立刻关掉。
- 若 owner 决定不回刷，也以 `done` 记录 decision 和原因；若存在对应 pending 行则一并关闭。

每个批准 item 只写入唯一 canonical owner；跨 module 只写指针。首次创建 module PRD 必须满足 [module PRD 惰性创建门](constraint-extraction-and-routing.md#module-prd-惰性创建门)。

## Destructive Apply

以下操作不能靠普通 item 批准覆盖，必须额外拿到显式的 destructive-apply 授权，精确到具体路径或 package id 清单，不接受"这批全部处理"：

- 移动、重命名或删除已有 stable doc 内容（而不是新增/修正/替换其内容）。
- 批量删除或重组遗留语料目录。
- [Package Retirement](package-retirement-runbook.md) 清理 implementation package 目录。

批准后仍需在执行前重新核对目标路径未在批准之后发生新变化，避免用过期批准执行已经不适用的删除。

完成后记录 apply result，并运行项目规定验证。任何未批准、冲突或不可验证的内容都不写入。
