# Definition of Done & Safety Guardrails

## Definition of Done

每个任务完成需满足：

- Contract consistency verified（schema + tests）。
- 功能可运行（按最小命令验证）。
- 有日志和错误提示（可观测）。
- 不破坏既有脚本主流程。
- 新加的 class、function 等有 docstring 或者 comment。
- 如果 API model 更新，contract 测试需要 pass。
- 说明类的文档按需更新（plan 三文件中的 `progress` 和 `findings` 需反映最新状态）。
- 人工测试通过后，已重新同步最新 trunk，并在该状态上完成最终回归。
- 已 merge 回 trunk，且 `plans/todo_current.md` 中任务状态更新为 `DONE`。

## Completion Semantics

- `implementation complete`:
  - 代码和验证在 task worktree 中已经完成，但还没有 merge 回 trunk。
- `task complete`:
  - 已 merge 回 trunk，并已更新为 `DONE`。

除非达到 `task complete`，否则不要把 WT-PM task 对外表述为真正完成。

## Safety Guardrails

- 遵循文件范围语义指导（参见 `collaboration-boundaries.md` 的 Scope Awareness）。
- `.env` 不入库，示例配置放 `.env.example`。
- 阈值与业务参数统一走 `tests/config.json`（后续迁移到 `config/`）。
- 所有 merge 写入需保留审计日志（操作者、时间、目标表、变更摘要）。
- Task worktree 完成前必须 sync main 并通过完整回归测试（参见 `collaboration-boundaries.md` 的 Regression gate）。
- 人工测试通过后不得直接 merge；必须先重新同步 trunk 并重跑最终回归。
- trunk 阶段只负责 task context；依赖安装、ignored local file sync、私有配置生成等环境副作用必须在 task worktree 内完成。
