---
target: skills/safety-review
updated: 2026-07-11
---

## Review-quality rubric

- 只在明确安全信号或用户明确要求时运行；说明触发信号，而不是杜撰风险。
- 对 diff 审查必须有调用者给出的 fixed point；不能用 `HEAD~1` 或当前工作树猜测。
- 五类范围都应覆盖，或针对不适用项给出基于 change map 的理由。
- P0 必须严格遵守 fail-closed 条件；P1/P2 不可伪装成 P0，也不可因无证据而放行。
- 复用 `dag.md` 的 Verification Gates 和 `gate.md` 的 Data Safety；不得新建登记面。
- finding 必须有文件/行或稳定来源、可重现风险路径和建议动作。
