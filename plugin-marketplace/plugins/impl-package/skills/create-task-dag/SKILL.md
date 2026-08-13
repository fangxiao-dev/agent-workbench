---
name: create-task-dag
description: 当需要只读审计或迁移已有 3.4/Task package 的 DAG 时使用；新 package 不创建 Task DAG，Task 不取代 Ticket 验收。
---

# Create Task DAG（legacy read-only）

新 package 不调用本 skill。仅在 owner 明确授权恢复或迁移已有 3.4 package、且当前 artifact 已存在时读取 `dag.md` 或 `<attempt-id>.patch-dag.md`；不得创建、发布或更新新的 DAG。

1. 读取当前 plan；有 Tickets 时同时读取 `tickets/` 的直接 Markdown 子文件。
2. 只审计已有 Task 的 primary ownership、确定依赖、贡献 Ticket、已知 seam/risk 和 section-level contract references。
3. 迁移时把 Task 的真实产物映射回 Ticket claim；不把 Task handoff 或 Task `DONE` 当作 acceptance proof。
4. Contract reference 使用仓库相对路径并定位到 Decision/Spec/contract-design/Plan 的具体一级或二级大章节；不得裸指整份文档或使用行号。只保留 Task 执行所需章节，不复制合同正文。
5. 不预列所有文件、consumer 或失败模式；不要创建 Phase/epic/子任务层。
6. 与 plan/Ticket 做只读联合检查：coverage、typed dependency、cycle、ownership、contribution mapping、section-level contract references、evidence feasibility、integration order 和 Gate 边界；发现新 DAG 需求时回到 `impl-planning`，不在本 skill 创建。

Task 状态只保存在 `.impl-package/state.json`。Task `DONE` 表示局部产出可集成，不表示 Ticket `SATISFIED`。P 变化时只把实际受影响 Task 设为 `NEEDS-REVALIDATION`。

初始化后 DAG Runtime State 表由 `refresh-progress` 维护。只有 dependency 已释放的 Task 才能进入 `READY/RUNNING`；未知 dependency 和 cycle 必须在发布前阻断。
