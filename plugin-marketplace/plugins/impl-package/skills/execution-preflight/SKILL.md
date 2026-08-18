---
name: execution-preflight
description: 当准备从 handoff、plan、review、audit、Issue 或 execution artifact 开始任务时使用；一次性确认 permission、owner authorization、HITL 和 destructive boundary。
---

# Execution Preflight

执行前确认初始 Decision/Spec/Plan bundle 的最终批准和会改变权限或安全边界的事实；同一 package 的后续更新直接沿用该批准。

## 渐进读取

1. **Wave 1 — anchor**：确认 worktree、branch、HEAD、package、current Attempt 和 `progress.md`；先判断是否仍是同一任务与授权范围。
2. **Wave 2 — control map**：读取 current plan、Composition、授权/write-set、Ticket/DAG 状态、blocker、Gate 和外部 mutation 边界。
3. **Wave 3 — active unit**：只展开下一动作需要的 Ticket、Task、Handoff、Execution Record checkpoint、evidence 与目标代码。

Wave 1 已暴露 package/authority drift 时停止，不通过全量读取制造“看起来已恢复”的假象。恢复只读 `progress.md` 与当前 Ticket，不要读 `state.json` 全文或 `situation.py --json` 全量。

## Ticket 首次激活

当 `/impl-package:dev-with-track` 首次派发一个新 Ticket，且 Planned Verification 为该 Ticket 声明了 `Evidence Lane Contract` 时，**主 session 自己**核这四项并只输出 `READY | BLOCKED`：

1. target 唯一（实际 URL/库身份）
2. 端口 owner
3. 应用库与 integration 库不串
4. cleanup owner

子代理只回收路径/符号/缺口，**不得输出 READY|BLOCKED 或判 lane 生死**。不要派环境探路 agent 当闸门。admission 失败时主 session 做有界 investigate，在现有授权内安全修复后重查；只有缺授权、下一步不安全/破坏性，或安全路径耗尽才 `BLOCKED`。

Ticket preflight 每个 Ticket 首次激活只执行一次，不放进每轮控制循环，也不产生 receipt、profile artifact、持久 readiness 状态或新的 Ticket/Attempt 状态。昂贵验证真正运行前再核 health / session / S3；那些结果不回溯否定已经开始的纯代码 dispatch。

## 必查

- 当前仓库/worktree、branch、HEAD Git commit；
- package 与 current plan 的仓库相对路径；
- 初始 Decision/Spec/Plan bundle 的 owner final approval、scope/write-set 和明确禁区；
- 当前 dirty paths 是否与 write-set 冲突；
- push、merge、发布、生产/shared mutation、数据迁移、删除等是否另需授权；
- `.impl-package/state.json` 是否通过 validate，`progress.md` 是否可重建，是否有 blocker/next action；
- 高风险动作是否有 rollback、可观察结果和必要 HITL。

初始 bundle 的 final approval 在同一 package 内持续有效，覆盖后续 plan、state、progress、Execution Record、evidence、review 和 Gate 更新；跨 session、普通 diff 或 package 记录变化均使用该 approval。Git commit 用于版本边界和审计，freshness 由现有记录承担。

## 输出

```text
Preflight: READY | BLOCKED
worktree: <absolute local path，仅会话输出，不持久化>
branch: <name>
HEAD: <git commit>
package: <repo-relative path>
authorized write-set: <repo-relative paths>
dirty conflicts: <none | paths>
external mutation: <none | authorization>
next action: <one action>
blocker/owner decision: <none | item>
```

`READY` 授权列出的下一动作及同一 package 的正常记录收口；push/merge/发布和外部 mutation 使用独立授权。

需要 main-session/subagent 调度时使用 `/impl-package:subagent-driven-development`；preflight 只提供任务特定的 scope、write-set、authorization、verification 和输出合同。
