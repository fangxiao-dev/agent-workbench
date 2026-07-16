# Apply Runbook

Apply 只接受 owner 明确批准的 report item ID；禁止把"将报告全部处理"解释为批准。每个 apply item 必须明确来源 package、目标 stable doc、durable delta 类型（system PRD / system architecture or ADR / context PRD / context architecture or contract / context language / module PRD / module spec）、代码或 commit 证据，以及与现有 stable docs 的关系（新增、修正、替换、删除废弃说法或 no-op）。仓库没有配置 `contextKnowledge` 时不得发明 context destination。

写入 stable docs 后，把对应 item 记录为 `done`（`records.done`，默认 `docs/_backfill/done.json`）：

- 若该 item 来自 `_pending.md` 的既有登记（`origin: pending-registry`），必须同时在该 `_pending.md` 中把对应行标记为已处置（划掉或删除，按项目既有约定），不能只写 `done.json` 而留 `_pending.md` 条目继续挂着——否则下一轮 audit 会把它当新候选重新报一遍。
- 若该 item 来自 gap-catching 发现（`origin: gap-catching`），除了写入 stable docs，还要先补一条 `_pending.md` 登记再标记为已处置，保持"未决登记只活在 `_pending.md`"这条不变式。
- 若 owner 决定不回刷，也以 `done` 记录 decision 和原因，并同样关闭对应 `_pending.md` 条目。

每个批准 item 只写入唯一 canonical owner；跨 module 只写指针。首次创建 module PRD 必须满足 [module PRD 惰性创建门](constraint-extraction-and-routing.md#module-prd-惰性创建门)。

## Destructive Apply

以下操作不能靠普通 item 批准覆盖，必须额外拿到显式的 destructive-apply 授权，精确到具体路径或 package id 清单，不接受"这批全部处理"：

- 移动、重命名或删除已有 stable doc 内容（而不是新增/修正/替换其内容）。
- 批量删除或重组遗留语料目录。
- [Package Retirement](package-retirement-runbook.md) 清理 implementation package 目录。

批准后仍需在执行前重新核对目标路径未在批准之后发生新变化，避免用过期批准执行已经不适用的删除。

完成后记录 apply result，并运行项目规定验证。任何未批准、冲突或不可验证的内容都不写入。
