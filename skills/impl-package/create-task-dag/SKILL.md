---
name: create-task-dag
description: 当已批准 implementation plan 需要转为最小横向 Task DAG，以协调 ownership、并行和已知依赖时使用；Task 不取代 Ticket 验收。
---

# Create Task DAG

仅在当前 plan 声明 `dag=true` 时创建。initial 写 `dag.md`；patch 写 `<attempt-id>.patch-dag.md`。

1. 读取当前 plan；有 Tickets 时同时读取 `tickets/` 的直接 Markdown 子文件。
2. 以 ownership、可并行边界和已知依赖切分最少数量的 Task。
3. 为每个 Task 写 primary ownership、确定依赖、贡献 Ticket 和已知 seam/risk。
4. 不预列所有文件、consumer 或失败模式；不要创建 Phase/epic/子任务层。
5. 与 plan/Ticket 做联合检查：coverage、typed dependency、cycle、ownership、contribution mapping、evidence feasibility、integration order 和 Gate 边界。

Task 状态只保存在 `.impl-package/state.json`。Task `DONE` 表示局部产出可集成，不表示 Ticket `SATISFIED`。P 变化时只把实际受影响 Task 设为 `NEEDS-REVALIDATION`。

初始化后 DAG Runtime State 表由 `refresh-progress` 维护。只有 dependency 已释放的 Task 才能进入 `READY/RUNNING`；未知 dependency 和 cycle 必须在发布前阻断。
