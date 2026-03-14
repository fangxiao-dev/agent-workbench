# Development Scope & Worktree Workflow

本文件定义任务工作流、文件范围语义指导和提交规范，适用于统一 worktree 开发模式。

## File Scope Semantic Guidance

在实现任务时，应注意文件改动范围的语义清晰性：

- Frontend scope：
  - `frontend/**`
  - 前端相关文档与 API 调用示例
- Backend scope：
  - `src/bills_analysis/**`
  - 后端相关 `tests/*.py`（迁移期）
  - `README.md` 后端段落

这些范围是语义指导而非严格禁止。在单个任务 worktree 中，Agent 可根据需要同时修改前后端文件以完成任务闭环。

## Task-Based Worktree Lifecycle

每个任务使用独立 worktree 进行开发：

1. **PM 创建任务**：在 `main` 分支的 `plans/todo_current.md` 中新建 task（`UNPLANNED` 状态）。PM 仅负责创建/确认 task 并分配 `task_id`，不直接编码。
2. **创建 worktree**：从 main 分支创建任务分支和 worktree。
   ```bash
   git worktree add -b feat/<task_id>-<slug> ../wt-<task_id> main
   ```
3. **Planning**：使用 `/planning-with-files` 将计划落盘。
4. **Implementation**：在 worktree 内完成前后端代码实现。
5. **Sync main**：合并前先同步 main 最新变更。
   ```bash
   git merge main
   ```
6. **Regression gate**：运行完整回归测试。
   ```bash
   uv run pytest tests/test_api_schema_v1.py -q        # backend contract
   pnpm --dir frontend test                              # frontend tests
   ```
7. **Merge to main**：测试通过后合并并清理 worktree。
   ```bash
   git checkout main
   git merge feat/<task_id>-<slug>
   git worktree remove ../wt-<task_id>
   ```

## Commit Conventions

- 分支命名：`feat/<task_id>-<slug>`（例如 `feat/TC-007-batch-delete`）
- Commit 前缀：`<task_id>: <描述>`（例如 `TC-007: add batch delete endpoint and UI`）
- 允许在单个 commit 中同时包含前后端改动，要求围绕同一 task_id 且原子。
- 建议在可能时拆分为多个 commit 以保持历史清晰，但不强制。

## Safety Guardrails

无论在哪个范围工作，以下规则始终适用：

- API Contract 冻结：`v1` schema 在 M1 期间不得有 breaking change（参见 `api-contract.md`）。
- `.env` 不入库，示例配置放 `.env.example`。
- 阈值与业务参数统一走 `tests/config.json`（后续迁移到 `config/`）。
- 所有 merge 写入需保留审计日志（操作者、时间、目标表、变更摘要）。
- 目标流程为：`PDF -> 提取/归档 -> 待校验数据 -> 人工确认 -> merge -> Lark`。

## Scope Awareness（最佳实践建议）

虽然统一 worktree 允许跨范围修改，但应保持语义清晰：

- 纯前端 UI/样式任务优先只改 `frontend/**`。
- 纯后端业务逻辑任务优先只改 `src/bills_analysis/**`。
- 需要前后端联动的任务（如新 API endpoint + frontend integration）可在同一 worktree 中完成。
- 通过语义指导控制 Agent 上下文范围，避免过长的上下文导致偏移。
