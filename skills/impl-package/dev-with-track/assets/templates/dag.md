# Task DAG

Attempt ID：<attempt-id>
Spec Revision：S<n>
Plan Revision：P<n>

> 本文件只定义 Task 边界和依赖。运行状态保存在 `.impl-package/state.json`；Task `DONE` 不等于 Ticket accepted。

## Task graph

| Task | Primary ownership | Known depends on | Contributes to tickets | Known seam / risk |
| --- | --- | --- | --- | --- |
| T1 | <模块或目录> | none | <ticket-id 或 none> | <风险或 none> |

只记录已知依赖和明确 ownership，不预列所有文件或失败模式。计划变化影响现有 Task 时，将受影响项设为 `NEEDS-REVALIDATION`；未受影响项可保留原状态。

## Integration responsibility

- Working Branch owner：
- Shared verification：
- Integration order：

## Runtime State

<!-- impl-package:projection runtime-state begin -->
| Task | State | Evidence | Handoff |
| --- | --- | --- | --- |
| T1 | PENDING | none | none |
<!-- impl-package:projection runtime-state end -->
