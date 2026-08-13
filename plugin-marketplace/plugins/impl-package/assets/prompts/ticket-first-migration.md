# Ticket-first migration prompt

你负责把一个已授权的 3.4/Task package 迁移为 3.5 Ticket-first package。

- 先记录当前 Git HEAD 作为 `pre-migration anchor`，暂停其他 writer。
- 只在临时 worktree/branch 生成 candidate；不要直接修改原 package。
- 逐条读取 Ticket、Task、DAG、Execution Record 和 Task Handoff。Handoff 不是 acceptance evidence；必须找到并验证它指向的真实测试、commit、日志或 DB diff。
- 生成 `formatVersion: 3.5` state：Ticket、`attemptHistory`、嵌套 `evidenceIndex`、`activeCheckpoints`；不保留 `tasks`、`resume` 或活跃 DAG projection。
- 将旧 Task Handoff 归档到 `migration/archive/task-handoffs/`，不要把 archive 路径写入 evidence index。
- 运行 `validate_ticket_first_migration.py`。任何 claim 缺失、证据只来自 handoff、路径不存在、未完成 Task Handoff 或 schema 不完整都停止迁移。
- candidate 未通过前，丢弃 staging，回到 pre-migration anchor；不得逐文件修复原 package。
- 只有 validator 通过后，才创建单一 migration commit。迁移 commit 是格式切换点，不是业务 Gate。
