# Review Gate

复杂度只增加 reviewer gate，不自动更换 implementer。`review_scope` 表示 reviewer 的边界：`checkpoint` 验收一个已声明的 bounded slice，`closure` 验收整个 source unit。不要为每个文件或每个小动作都增加 checkpoint。

以下任一条件要求 `review=required`：shared seam、安全、数据完整性、并发、migration、不可逆外部副作用，或 Plan/safety policy 明确要求独立审查。复杂任务在切片边界设置 `checkpoint`；最终仍需 `closure`。单纯跨文件、跨模块或接口变化不自动升级；非显然地选择 `review=none` 时记录 reason。

```text
implementer(slice)
  -> reviewer(checkpoint)
     -> PASS: 继续下一个 slice
     -> finding: fresh fixer -> reviewer(checkpoint)

implementer(last slice)
  -> reviewer(closure)
     -> PASS: review_state=PASSED
     -> finding: fresh fixer -> reviewer(closure)

main-session finding
  -> fresh fixer
  -> reviewer(对应 scope)
```

Implementer 或 fixer 的 `DONE` 在 reviewer 运行前都标记为 `review_state: PENDING_REVIEW`。Reviewer 必须是独立 fresh invocation，默认逻辑 worker 为 `$grok-worker`；fixer 使用新的 `@luna-worker` 或 `$grok-worker` invocation，不能复用发现 finding 的旧进程。Reviewer 只读、不修复、不替 main session 做 Ticket acceptance。`UNCERTAIN/BLOCKED` 原样上交。只有 `review_state=NOT_REQUIRED` 或 `PASSED` 的结果可以被主 session 消费；`PENDING_REVIEW`、`FINDING`、`BLOCKED` 都不能支持完成声明。
