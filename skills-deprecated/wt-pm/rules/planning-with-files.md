# planning-with-files Rule

Primary entrypoint: `skills/wt-pm/SKILL.md` and `skills/wt-pm/references/wt-pm-workflow.md`.

## Purpose

将 `planning-with-files` 统一为 `task tracker + per-task workplan directory` 协作模式，支持并行任务 worktree 开发，降低状态冲突和上下文漂移。

## Source of Truth

- `plans/todo_current.md`：任务与状态唯一来源。
- `plans/workplans/<task_id>/task_plan.md`
- `plans/workplans/<task_id>/findings.md`
- `plans/workplans/<task_id>/progress.md`
- 操作说明：`plans/workplans/README.md`

## State Machine

- `UNPLANNED -> PLANNED -> DONE`（互斥）
- 状态更新优先通过 `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . ...`

## Trigger Semantics

1. `/planning-with-files 规划还未规划的task`
   - 读取全部未完成任务（`UNPLANNED + PLANNED`）
   - 用户显式指定 task 范围时，优先按用户指定创建该 task 的 workplan
2. `/planning-with-files 读取当前未完成的task progress继续实现`
   - 继续一个 `PLANNED` task
   - 未指定 `task_id` 时，默认按 `todo_current.md` 顺序选择第一个 `PLANNED`

## Selection Policy

- 用户显式指定范围优先于自动选择
- 用户未指定范围时，agent 可自主选择一个 task 创建 workplan
- 自主选择时，必须将选择理由写入 `plans/workplans/<task_id>/findings.md`

## Concurrency Rules

- 一个 `task_id` 同时只允许一个活跃 workplan（`PLANNED` 状态）
- 继续执行前必须先读取对应 task 的 workplan 三文件
- 一个 task 应只绑定一个活跃 worktree
- worktree 路径可以由工具托管；如果已有 worktree，继续执行时应直接进入它，而不是重复创建

## CLI Contract

- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list`
- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --task-id <id>`
- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-resume [--task-id <id>]`
- `python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . set-status --task-id <id> --status <UNPLANNED|PLANNED|DONE>`

## Audit & Handoff

- 每完成一个可交接单元，更新 `plans/workplans/<task_id>/progress.md`（记录已完成项、阻塞项、下一步）
- 风险和技术决策记录在 `plans/workplans/<task_id>/findings.md`
- 跨 task 依赖通过 `todo_current.md` 的 `note` 字段声明（如 `blocked by TC-008`）
