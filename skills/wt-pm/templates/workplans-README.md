# Workplans

`planning-with-files` 的项目化落地目录。每个 plan 使用唯一 `plan_id`，并创建三份持久化上下文文件：

- `task_plan.<plan_id>.md`
- `findings.<plan_id>.md`
- `progress.<plan_id>.md`

详细触发语义、并行约束、命令契约见：`~/.claude/skills/wt-pm/rules/planning-with-files.md`。

## plan_id 规则

- 默认格式：`YYYYMMDD-<task_id>`
- 同一 `task_id` 在同一天重复创建时，脚本追加后缀 `-01`、`-02`...
- 示例：`20260218-TC-008`、`20260218-TC-008-01`

## task 状态机

- `UNPLANNED`：尚未绑定 plan
- `PLANNED`：已经绑定活跃 plan，正在执行
- `DONE`：任务已完成，需保留 `plan_id` 便于审计

## 并行约束

- 一个 `plan_id` 可以绑定多个 task。
- 一个 `task_id` 同时只允许一个活跃 `plan_id`。
- 默认短句“继续实现”会选择一个 `PLANNED` task（未指定时按表格顺序）。

## 推荐命令

```bash
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . list
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-plan --max-tasks 2
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . quick-resume
python ~/.claude/skills/wt-pm/scripts/plan_tracker.py --root . set-status --task-id TC-001 --status DONE --plan-id 20260218-TC-001
```
