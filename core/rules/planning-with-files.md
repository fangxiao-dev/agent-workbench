# planning-with-files Rule

## Purpose

将 `planning-with-files` 统一为 `task tracker + per-plan workplans` 协作模式，支持并行任务 worktree 开发，降低状态冲突和上下文漂移。

## Source of Truth

- `plans/todo_current.md`：任务与状态唯一来源。
- `plans/workplans/task_plan.<plan_id>.md`
- `plans/workplans/findings.<plan_id>.md`
- `plans/workplans/progress.<plan_id>.md`
- 操作说明：`plans/workplans/README.md`

## State Machine

- `UNPLANNED -> PLANNED -> DONE`（互斥）
- `PLANNED` 与 `DONE` 必须有 `plan_id`
- 状态更新优先通过 `python scripts/plan_tracker.py ...`

## Trigger Semantics

1. `/planning-with-files 规划还未规划的task`
   - 读取全部未完成任务（`UNPLANNED + PLANNED`）
   - 用户显式指定 task 范围时，优先按用户指定创建 plan
2. `/planning-with-files 读取当前未完成的task progress继续实现`
   - 继续一个 `PLANNED` task
   - 未指定 `task_id/plan_id` 时，默认按 `todo_current.md` 顺序选择第一个 `PLANNED`

## Selection Policy

- 用户显式指定范围优先于自动选择
- 用户未指定范围时，agent 可自主选择 1..N 个 task 作为 plan 范围
- 自主选择时，必须将选择理由写入 `findings.<plan_id>.md`（`Technical Decisions` 或 `Research Findings`）

## Concurrency Rules

- 一个 `plan_id` 可以绑定多个 task
- 一个 `task_id` 同时只允许一个活跃 plan（`PLANNED` 状态）
- 继续执行前必须先读取对应 plan 的三文件
- task worktree 默认使用同级可见目录（`../wt-<task_id>`）

## CLI Contract

- `python scripts/plan_tracker.py list`
- `python scripts/plan_tracker.py quick-plan --task-ids <ids>`
- `python scripts/plan_tracker.py quick-plan --max-tasks <n>`
- `python scripts/plan_tracker.py quick-resume [--plan-id <id> | --task-id <id>]`
- `python scripts/plan_tracker.py set-status --task-id <id> --status <UNPLANNED|PLANNED|DONE>`
- `python scripts/plan_tracker.py bind-task --task-id <id> --plan-id <id>`

## Audit & Handoff

- 每完成一个可交接单元，更新 `progress.<plan_id>.md`（记录已完成项、阻塞项、下一步）
- 风险和技术决策记录在 `findings.<plan_id>.md`
- 跨 task 依赖通过 `todo_current.md` 的 `note` 字段声明（如 `blocked by TC-008`）
