# Final Report

## Bundle admission 输出

admission mode 先输出一行本轮配置，再输出 `Admission verdict`、简短证据、已检查或不适用的维度、full-review trigger scan 和下一动作。本轮配置必须明确 `Mode=bundle-admission`、fresh reviewer 的实际 runtime（subagent 或 ephemeral runner）、fallback 原因（如有）、额外 Outside Voice/ledger 未启用以及 signal 路由；它只负责让 owner 看见实际审查深度，即使不阻塞也不能省略。`ready` 可以交回 `impl-planning` 请求 owner approval；`full review` 必须按确切 `skills/plan-review/SKILL.md` 路径转入正常 workflow，并只交接经 `verify-clearance` 成功验证的 ledger 绝对路径；`revise` 回到对应 owning skill；`unavailable` 只能重试、暂停或取消 approval。

不得为 admission 输出 ledger 路径、manifest hash、receipt、`cleared`、Apply 授权或跨 session 状态。它是当前 approval 前的独立判断，不是新的 canonical artifact；只有后续正常 full review 的临时 ledger 可以作为 runtime handoff。

## Focused closure verification 输出

先说明 `Mode=focused-closure-verification`、fresh verifier 的实际 runtime、fallback 原因（如有）、closure brief 的项数与已验证项数，再按 brief 顺序列出每项的 `verified / failed / blocked` 及最短证据。全局只可为 `closure-verified`、`reopen-full-review` 或 `blocked`：`closure-verified` 还必须说明 `verify-clearance` 已成功，verified ledger 绝对路径仍是唯一可交给 `impl-planning` 的凭据；`reopen-full-review` 只说明直接矛盾或边界漂移的升级理由与下一动作，不扩展成一轮新 findings；`blocked` 说明缺失的输入或证据。

本模式不请求额外 owner approval、不新增长期 artifact，也不把 mode verdict 当作 `cleared` 的替代品。

## Review 输出顺序

1. **整体判断**：是否可进入 owner 决策或 Apply；存在未决、stale 或 degraded 时明确不能称为 cleared。
2. **本轮配置**：Outside Voice 状态；每个 fresh reviewer 的实际 runtime 与 fallback 原因；Section Reviewer、Judge、Critic 和工具的启用/跳过及理由；coverage map 或 diagram 的选择。
3. **材料性覆盖**：Scope、Architecture、Code Quality、Tests、Performance 各自的 `reviewed / not_applicable + reason / finding`。
4. **计划边界**：`What already exists` 与 `NOT in scope`。
5. **Formal findings**：按 severity 和 dependency 排序，展示 claim、证据、风险、recommendation、owner gate 和 resolution；accepted finding 对应可执行动作、受影响模块、真实依赖和 observable verification oracle，不猜测不存在的文件或 effort。
6. **测试与失败**：coverage map、critical regression requirements、failure handling 与 user-visible outcome。
7. **决策与状态**：自动归纳、待 owner wave、阻塞范围、stale/degraded、manifest hash 和 authorization 状态。

仅当存在两个以上真正独立的 workstreams 时输出简短 dependency map 与并行化建议，标出共享 contract、migration/integration gate 和合并冲突面；否则说明顺序执行即可。

## Apply 输出

说明应用了哪些 manifest decisions、哪些未应用、验证结果和目标是否仍有开放风险。成功或中断过 guarded Apply 时必须从 ledger 的 `apply_backups` 枚举全部同目录、run-bound preimage backup 绝对路径，并说明它们是持久恢复物：owner 确认目标内容及无迟到写入需要恢复后才可清理；skill 不自动删除。默认不要在目标 plan 追加运行报告或 OS-temp ledger 路径；聊天中可以给当前用户 ledger 的绝对路径。

不要输出含糊的“review passed”。使用 `cleared`、`not cleared` 或 `applied with degraded review`，并立即解释未决、stale 或降级边界。
