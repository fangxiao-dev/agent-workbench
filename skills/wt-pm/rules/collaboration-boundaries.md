# Development Scope & Worktree Workflow

Primary entrypoint: `skills/wt-pm/SKILL.md` and `skills/wt-pm/references/wt-pm-workflow.md`.

本文件是通用协作规则（被 `wt-pm` / `wt-plan` / `wt-dev` 引用），不作为工作流主入口。

## File Scope Semantic Guidance

在实现任务时，优先按语义边界控制改动范围：

- Frontend scope（示例）：
  - `frontend/**`
  - 前端文档与 API 调用示例
- Backend scope（示例）：
  - `src/**`（后端服务主目录）
  - `tests/**`（后端/契约测试）
  - 后端相关 README 段落
- Shared scope（示例）：
  - `shared/**`、`schemas/**`、`contracts/**`、公共配置文件

以上是语义指导而非硬性隔离。在单个 task worktree 中可跨前后端修改，但必须围绕同一 `task_id` 保持原子闭环。

## Workflow Reference

完整阶段流转、门禁和职责分工以 `wt-pm` 体系为准：

- 入口编排：`wt-pm`
- 规划与建树：`wt-plan`
- 实现与合并：`wt-dev`

规划与状态机规则参见：`rules/planning-with-files.md`。

## Commit Conventions

- 分支命名：`feat/<task_id>-<slug>`
- Commit 前缀：`<task_id>: <description>`
- 允许单个 commit 同时包含前后端改动，前提是同一 `task_id` 且改动原子。
- 建议在可能时拆分 commit 以提高可审计性，但不强制。

## Safety Guardrails

无论在哪个 scope 工作，以下规则始终适用：

- API contract 冻结期禁止 breaking change（具体版本策略见项目 contract 规则）。
- `.env` 不入库；示例配置使用 `.env.example`。
- Merge/状态迁移前必须通过项目定义的 regression gate。
- 任何可交接节点需有可追溯记录（`progress/findings/todo_current`）。

## Scope Awareness

- 纯 UI 任务优先只改 frontend 目录。
- 纯后端任务优先只改 backend 目录。
- 端到端任务可跨范围改动，但要保持改动理由明确并记录在 `findings`。
