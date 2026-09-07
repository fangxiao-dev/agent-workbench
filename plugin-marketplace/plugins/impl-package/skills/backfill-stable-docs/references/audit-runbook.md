# Audit Runbook

1. Resolve the main worktree and record Source HEAD、branch、dirty state.
2. Validate the repository configuration and target branch.
3. Collect optional pending files, `records.done`, and direct child packages.
4. Emit item-level inventory: `pending-registry` items, reachable terminal Gate Durable Deltas as `gap-catching`, and done-filtered items with reasons. Pending never suppresses gap-catching; done does.
5. Read each source, current code/tests and destination stable docs.
6. Classify each durable statement; do not infer truth from Gate alone. `none` produces no candidates.
7. Report origin counts, item IDs, done filter reasons, manual Gate reviews, blockers and owner decisions.
8. Stop without writes. Output stays on CLI or an explicit path; no required reports directory.

## 判断提醒

- 先固定主工作区的 Source HEAD、branch 和 dirty 状态，再收集 source；Source HEAD 只定义本轮读取快照，target branch 另行证明是否已合入。
- inventory 只提供候选；`candidate`、冲突和 owner intent 仍由 agent 依据直接证据判断，报告中的候选不等于 apply 批准。
- `validate_config.py`、`contract_preflight.py` 和 inventory 脚本保持只读；`contract_preflight.py` 委托当前状态引擎校验 format/version，backfill 不另建兼容层。Audit 输出也不改变 stable docs、pending、records 或 package。
