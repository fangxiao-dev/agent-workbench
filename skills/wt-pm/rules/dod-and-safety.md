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

## Safety Guardrails

- 遵循文件范围语义指导（参见 `collaboration-boundaries.md` 的 Scope Awareness）。
- `.env` 不入库，示例配置放 `.env.example`。
- 阈值与业务参数统一走 `tests/config.json`（后续迁移到 `config/`）。
- 所有 merge 写入需保留审计日志（操作者、时间、目标表、变更摘要）。
- Task worktree 完成前必须 sync main 并通过完整回归测试（参见 `collaboration-boundaries.md` 的 Regression gate）。
