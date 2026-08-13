# Review Gate

复杂度只决定 `review`，不决定 worker。以下任一条件成立时使用 `review=required`：shared seam、安全、数据完整性、并发、migration、不可逆外部副作用，或 Plan/safety policy 明确要求独立审查。单纯跨文件、跨模块或接口变化不自动升级；非显然地选择 `review=none` 时记录 reason。

```text
implement/fix worker
  -> status=DONE, review_state=PENDING_REVIEW
  -> fresh independent reviewer
     -> PASS: review_state=PASSED
     -> finding: same worker + mode=fix, then closure review
     -> UNCERTAIN/BLOCKED: review_state=BLOCKED
```

reviewer 使用现有 `reviewer`/`do-review` 薄合同，默认逻辑 worker 为 `$grok-worker`，不复用实现进程。只有 `review_state=NOT_REQUIRED` 或 `PASSED` 的结果可以被主 session 消费；`PENDING_REVIEW`、`FINDING`、`BLOCKED` 都不能支持完成声明。
