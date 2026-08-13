---
name: to-tickets
description: 当已批准 implementation plan 判定需要至少两个独立跟踪 acceptance 结论的交付切片时使用；只创建 Ticket 合同，不维护 Task 或运行状态。
---

# To Tickets

仅在当前 plan 声明 `tickets=true` 时使用。Ticket 放在 package 的固定 `tickets/` 目录，文件名可排序且稳定。

1. 按可独立验收的纵向交付切片拆分，不按文件、层或 worker 拆分。
2. 每个 Ticket 写 Ticket ID、Attempt、S/P 别名、`Draft`、建设内容、可观察 AC、evidence owner 和 typed dependency；运行时验收状态只写入 `.impl-package/state.json`。
3. 每个 Ticket 的 contract references 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节；不得裸指整份文档或使用行号。Ticket 只引用其建设内容与 AC 实际依赖的章节。
4. evidence 说明验证入口或 owner；不复制通用 checklist。
5. 与当前 plan/spec 检查 coverage、重叠、依赖、section-level contract references 和 AC feasibility。
6. 新 package 使用 `tickets=true, dag=false` Ticket-only 合同；不创建 DAG，也不建立 Ticket/Task 双层 bundle。`init` 只发布当前 Attempt 的 Ticket，并将其原子推进为 Approved/PENDING。旧 package 的 `dag=true` 只读，不由本 skill 创建或更新。

Ticket acceptance state 保存在 `.impl-package/state.json`。Ticket AC 必须使用稳定 claim ID，并把 early falsification evidence 与 remaining completion evidence 分开描述；第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量。旧 Task `DONE` 不自动通过 Ticket。P 变化时只将实际受影响 Ticket 设为 `NEEDS-REVALIDATION`。

Ticket 发布后不承载 Phase、Next、worker、implementation progress 或 Runtime Acceptance projection。语义变化使受影响 Ticket 回到 Draft/重验流程；`package refresh-progress` 只重建 `progress.md` 与必要的 Execution Record header。新合同使用 `RETIRED` 统一表示 waived/superseded，并要求记录对应 disposition；3.4 runtime 旧状态只作为迁移输入。
