# API Contract Rules (v1 Frozen)

## Current Contract Baseline

- 当前对外 contract 版本：`v1`（Frozen）。
- 当前执行阶段：`M1`（MVP 本地全流程闭环）。
- 实现任务时：以 `src/bills_analysis/models/` 中 `v1` schema 为唯一契约基线，不依赖临时脚本输出。
- 内部实现边界：M1 允许重构 backend 内部逻辑或 frontend 组件，但不得改变 `v1` 对外 API 字段、类型与语义。

## 契约优先规则

- 所有开发统一以 `src/bills_analysis/models/` 为唯一 contract 来源。
- API 变更必须先更新 schema，再更新调用方（即使在同一 worktree 中也应遵循此顺序）。
- `v1` schema 冻结：禁止删除/重命名/改类型已发布字段。
- 如必须做 breaking change：先版本升级（如 `v1.1`/`v2`），并在 `findings.<plan_id>.md` 中标注风险和迁移建议。

## Implementation & Debug Constraints

在 M1 阶段的实现与调试过程中：

- 任务实现时只对接 `v1` 冻结契约，不依赖临时脚本返回结构。
- 允许重构 backend 内部实现或 frontend 组件结构，但不得改变 `v1` 对外 API 字段与语义。
- 若在同一 worktree 中同时修改 API schema 和调用方，必须先 commit schema 变更再 commit 调用方，保持审计清晰。
