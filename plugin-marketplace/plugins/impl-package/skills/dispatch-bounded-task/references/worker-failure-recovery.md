# Worker Failure Recovery

只在 dispatch 边界得到 `Outcome: INCOMPLETE` 时读取。正常 `DONE` 与业务 `BLOCKED` 不进入本分支。各 executor 的原生未完成状态（例如超时、断连、取消、partial 或无效 envelope）先由 dispatch 适配为这一语义结果。

## Fail-closed 处理

1. `INCOMPLETE` 不能解释为 `DONE`，也不能支持 finding closure 或 Ticket acceptance。
2. 确认进程已退出或被清理，并记录 terminal status 与 cleanup 结果。进程状态未知时返回 `BLOCKED`，不要启动第二个可能争用同一资源的 worker。
3. 检查实际 worktree diff、ownership 之外的修改、临时文件和外部资源 residue。只保留可归因且在授权写集内的副作用；无法确认来源或安全集成时返回 `BLOCKED`。
4. 只有角色表存在下一档 worker 时才 fallback，并且最多一次。fallback 使用 fresh worker 与 canonical input，明确携带 terminal status、已存在 diff、cleanup 结果和仍需完成的 source unit。
5. worker 已成功执行并返回业务 `BLOCKED` 时原样上交；不得换模型绕过未决合同、范围、authority 或 owner decision。

## 恢复记录

- 有 DAG Task 时，把中断或 retry、已有 evidence、residue/cleanup 与唯一下一动作写入该 Task Handoff。
- 没有 DAG Task 时，由调用方在 Attempt Execution Record 写 checkpoint，保留 source unit、worker terminal status、实际 diff/residue、cleanup 和下一动作。
- 恢复记录是连续执行证据，不授权扩大 ownership，也不把 partial prose 变成完成结论。
