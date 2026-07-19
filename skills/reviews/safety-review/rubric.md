---
target: skills/reviews/safety-review
updated: 2026-07-11
---

## Review-quality rubric

- 只在明确安全信号或用户明确要求时运行；说明触发信号，而不是杜撰风险。
- 对 diff 审查必须有调用者给出的 comparison ref；开始时把 base/head 都解析为完整 commit SHA，review evidence 只保存不可变 SHA range，不能用 `HEAD~1` 或可移动 branch/tag 作为证据。
- 五类范围都应覆盖，或针对不适用项给出基于 change map 的理由。
- P0 必须严格遵守 fail-closed 条件；P1/P2 不可伪装成 P0，也不可因无证据而放行。
- 复用需求、设计、验证合同与项目安全规范；不得新建登记面，也不得把完整安全 checklist 写入 release gate。
- finding 必须有文件/行或稳定来源、可重现风险路径和建议动作。
