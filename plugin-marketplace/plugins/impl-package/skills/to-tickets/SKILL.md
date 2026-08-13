---
name: to-tickets
description: 当已批准 implementation plan 判定需要至少两个独立跟踪 acceptance 结论的交付切片时使用；只创建 Ticket 合同，不维护 Task 或运行状态。
---

# To Tickets

仅在当前 plan 声明 `tickets=true` 时使用。Ticket 放在 package 的固定 `tickets/` 目录，文件名可排序且稳定。

1. 按可独立验收的纵向交付切片拆分，不按文件、层或 worker 拆分。
2. 每个 Ticket 写 Ticket ID、Attempt、S/P 别名、`Draft`、建设内容、可观察 AC、evidence owner 和 typed dependency；Draft Runtime Acceptance 使用 `UNRECORDED`。
3. 每个 Ticket 的 contract references 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节；不得裸指整份文档或使用行号。Ticket 只引用其建设内容与 AC 实际依赖的章节。
4. evidence 说明验证入口或 owner；不复制通用 checklist。
5. 与当前 plan/spec 检查 coverage、重叠、依赖、section-level contract references 和 AC feasibility。
6. 若 `dag=true`，与 DAG 组成一个 bundle 一次 review/approval；不要创建 Ticket-only 中间审批。`init` 只发布当前 Attempt 的 Ticket，并将其原子推进为 Approved/PENDING。

Ticket acceptance state 保存在 `.impl-package/state.json`。Task `DONE` 不自动通过 Ticket。P 变化时只将实际受影响 Ticket 设为 `NEEDS-REVALIDATION`。

Ticket 发布后不承载 Phase、Next、worker 或 implementation progress。语义变化使受影响 Ticket 回到 Draft/重验流程；纯 projection 修复可由 `refresh-progress` 完成。
