---
name: execution-preflight
description: 当准备从 handoff、plan、review、audit、Issue 或 execution artifact 开始任务时使用；一次性确认 permission、owner authorization、HITL 和 destructive boundary。
---

# Execution Preflight

执行前只确认会改变权限或安全边界的事实，不重复审计 artifact 历史。

## 渐进读取

1. **Wave 1 — anchor**：确认 worktree、branch、HEAD、package、current Attempt 和 `progress.md`；先判断是否仍是同一任务与授权范围。
2. **Wave 2 — control map**：读取 current plan、Composition、授权/write-set、Ticket/DAG 状态、blocker、Gate 和外部 mutation 边界。
3. **Wave 3 — active unit**：只展开下一动作需要的 Ticket、Task、Handoff、Execution Record checkpoint、evidence 与目标代码。

Wave 1 已暴露 package/authority drift 时停止，不通过全量读取制造“看起来已恢复”的假象。

## 必查

- 当前仓库/worktree、branch、HEAD Git commit；
- package 与 current plan 的仓库相对路径；
- owner 批准的 scope/write-set 和明确禁区；
- 当前 dirty paths 是否与 write-set 冲突；
- push、merge、发布、生产/shared mutation、数据迁移、删除等是否另需授权；
- `.impl-package/state.json` 是否通过 validate，`progress.md` 是否可重建，是否有 blocker/next action；
- 高风险动作是否有 rollback、可观察结果和必要 HITL。

跨 session approval 只有在 handoff/记录给出批准时的 Git commit 且当前 diff 未扩大 contract、authority 或 public behavior 时可复用。不要创建第二套 freshness 记录。

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

`READY` 只授权列出的下一动作，不自动授权 commit/push/merge/发布或外部 mutation。

需要 main-session/subagent 调度时使用 `/impl-package:subagent-driven-development`；preflight 只提供任务特定的 scope、write-set、authorization、verification 和输出合同。
