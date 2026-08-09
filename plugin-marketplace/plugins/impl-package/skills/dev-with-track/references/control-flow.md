# Control Flow

```text
validate → progress restore → resolve readiness → implement/investigate → verify
                                      ↑                                ↓
                          affected-scope revalidation ← CAS state + ER checkpoint
                                                                       ↓
                         review/manual acceptance → findings routing → claim audit
                                                                       ↓
                                                           Stage 7 → current Gate
```

- blocker 或 evidence 缺失：停在当前 unit，记录 checkpoint。
- contract/plan 变化：回 owning stage，并仅 revalidate 受影响状态。
- Task 完成：交 Working Branch owner 集成；不自动接受 Ticket。
- 所有 earned Ticket satisfied、Task done/waived/superseded、适用验证与 review 通过：进入 completion claim audit。
- terminal Gate 后禁止继续当前 Attempt；新工作由 impl-planning 创建 patch Attempt。
