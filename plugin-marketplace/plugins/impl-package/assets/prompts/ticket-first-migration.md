# Ticket-first migration prompt

你负责把一个已授权的 3.4/Task package 迁移为 3.5 Ticket-first package。

- 先记录当前 Git HEAD 作为 `pre-migration anchor`，暂停其他 writer。
- 只在临时 worktree/branch 生成 candidate；不要直接修改原 package。
- 逐条读取 Ticket、Task、DAG、Execution Record 和 Task Handoff。Handoff 不是 acceptance evidence；必须找到并验证它指向的真实测试、commit、日志或 DB diff。
- 生成 `formatVersion: 3.5` state：Ticket、`attemptHistory`、显式 `predecessors`、嵌套 `evidenceIndex`、`activeCheckpoints`；不保留 `tasks`、`resume` 或活跃 DAG projection。
- 将旧 Task Handoff 归档到 `migration/archive/task-handoffs/`，不要把 archive 路径写入 evidence index。
- 在切换前先运行 `validate_ticket_first_migration.py`，把它当作 admission gate：candidate 必须具备 `spec.md`，当前 Attempt 的每个 Ticket 必须有 `Publication Status: Approved`，并满足同一 3.5 runtime validate 的静态前置条件。每个 `attemptHistory.executionRecord` 使用 package-relative 的 `execution/<attempt-id>/execution-record.md`，其 header 与 history row、ER ID/Subject/Title/Evidence/Content 必须一致，judgment content 不能为空；`progress.md` 必须存在且与可计算 runtime projection 一致，Ticket 文本不得包含已退休的 `runtime-acceptance` projection marker。静态检查后 validator 只读调用同一 3.5 `command_validate`（含 `gate.md`/lifecycle parity），不得写盘。
- validator 的 `warnings` 是 best-effort 历史提示：仅当 pre-anchor ER blob 不可读或旧格式无法解析时返回结构化 warning，不阻断 candidate；若 source judgment 可解析，candidate 必须保留相同 judgment ID 集合及规范化 Subject/Title/Evidence/Content，否则停止迁移。任何 claim 缺失、证据只来自 handoff、路径不存在、未完成 Task Handoff 或 schema 不完整都停止迁移。
- candidate 未通过前，丢弃 staging，回到 pre-migration anchor；不得逐文件修复原 package。
- 只有 validator 返回 `valid: true` 后，才创建单一 migration commit；切换后再运行 3.5 runtime `validate`。迁移 commit 是格式切换点，不是业务 Gate，warnings 也不等同于 Gate 结果。
