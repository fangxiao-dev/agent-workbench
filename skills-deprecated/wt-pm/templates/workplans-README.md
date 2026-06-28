# Workplans

`planning-with-files` 的项目化落地目录。每个 task 使用自己的 workplan 目录，并创建三份持久化上下文文件：

- `plans/workplans/<task_id>/task_plan.md`
- `plans/workplans/<task_id>/findings.md`
- `plans/workplans/<task_id>/progress.md`

详细触发语义、并行约束、命令契约见：`~/.claude/skills/wt-pm/rules/planning-with-files.md`。

## 目录规则

- 一个 task 对应一个目录：`plans/workplans/<task_id>/`
- workplan 唯一标识就是 `task_id`
- 目录内固定文件名：`task_plan.md`、`findings.md`、`progress.md`

## task 状态机

- `UNPLANNED`：尚未创建 workplan
- `PLANNED`：已经绑定活跃 workplan，正在执行
- `DONE`：任务已完成

## 并行约束

- 一个 task 只对应一个 workplan 目录。
- 一个 `task_id` 同时只允许一个活跃 workplan。
- 默认短句“继续实现”会选择一个 `PLANNED` task（未指定时按表格顺序）。

## 推荐命令

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --task-id TC-001
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-resume
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . set-status --task-id TC-001 --status DONE
```
