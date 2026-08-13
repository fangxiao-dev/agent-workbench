# Ticket-first 3.4 → 3.5 迁移 Runbook

这是一次性、由 package 主 session 执行的迁移流程，不是 runtime 双读器，也不是通用迁移 CLI。执行前必须有 owner 授权并暂停同一 package 的其他 writer。

## 流程

1. 在旧 package 当前 worktree 记录 `pre-migration Git anchor`，确认旧 `state.json` 为 3.4，并确认当前 Attempt、Gate 和未完成 Ticket。
2. 创建临时 worktree/branch；所有 candidate 文件只写入 staging，不直接改原 package。
3. 读取旧 state、Plan、Ticket、Task/DAG、Execution Record 和 Task Handoff。Handoff 只能提供映射线索；从其中指向的测试、commit、日志或 DB diff 验证真实产物。没有真实产物就停止并请求人工 mapping。
4. 生成 3.5 candidate：删除 `tasks`、`resume`、DAG runtime projection；创建 `attemptHistory`、嵌套 `evidenceIndex` 和 `activeCheckpoints`。旧 Handoff 移入 `migration/archive/task-handoffs/`，不得进入 acceptance evidence。
   `attempt.plan`、evidence artifact 和 checkpoint evidence 使用 repository-relative 路径；`attemptHistory.executionRecord` 使用 package-relative 的 `execution/<attempt>/execution-record.md`。
5. 在任何切换或 migration commit 之前运行 `scripts/validate_ticket_first_migration.py --package <staging> --pre-anchor <commit>`。validator 是 admission gate：先检查 `spec.md`、当前 Attempt Ticket 的 `Publication Status: Approved`、3.5 state 的静态前置条件、真实 artifact、active checkpoint、attempt history、无 Task Handoff 活跃面和 archive；其中每条 `attemptHistory.executionRecord` 必须绑定 `execution/<attempt-id>/execution-record.md`，并通过与 3.5 runtime validate 相同的 header/ER 静态约束。candidate 还必须带有与可计算 runtime projection 完全一致的 `progress.md`；Ticket 不得携带已退休的 `runtime-acceptance` projection marker。静态检查完成后，validator 只读调用同一 3.5 `command_validate`，覆盖 `gate.md`/lifecycle 等 parity；该调用不得写盘。
   validator 输出中的 `warnings` 是 best-effort 历史提示：pre-anchor 的 ER blob 不存在、旧格式或无法解析时只产生结构化 warning，不阻断 candidate admission；若 source ER 可读取并解析，则 candidate 必须保留相同 judgment ID 集合及规范化 Subject/Title/Evidence/Content，否则 admission 失败。warnings 不代表 runtime validate 或业务 Gate 通过。
6. 若在生成、校验或切换前中断，删除 staging；原 package 与 pre-anchor 仍是唯一权威。不得在原 package 上逐文件修复半迁移状态。
7. 仅当 validator 返回 `valid: true` 后，在原 worktree 以一次 migration commit 切换 candidate。切换后新插件只读取 3.5；不要先切换再依赖 runtime validate 发现缺失前置条件。
8. 切换后仍必须执行同一 3.5 runtime 的 `validate`，再恢复当前 active checkpoint，由 owner 决定是否继续执行；不要把迁移 commit 自动视为 Gate pass，也不要把 best-effort warnings 当成已验证事实。

## 恢复边界

- `state.json.activeCheckpoints` 是正常跨 session 恢复唯一事实源；compact 只是意外耗尽兜底。
- ER 中旧 checkpoint 正文可以保留作历史，但不能重新成为 active checkpoint。
- broker/controller 不参与本阶段 package state 写入；主 session 仍是唯一 writer。
