# Control Flow

```text
validate → progress restore → resolve readiness → implement/investigate → verify
                                      ↑                                ↓
                          affected-scope revalidation ← CAS state + ER checkpoint
                                                                       ↓
                         review/manual acceptance → findings routing → claim audit
                                                                       ↓
                                                            Stage 7 / current Gate：处境表投递
```

- blocker 或 evidence 缺失：停在当前 unit，记录 checkpoint。
- contract/plan 变化：留在同一 package 记录 affected scope 并沿用 initial bundle approval；新 package 从 owning stage 取得初始 bundle approval。
- completion claim 与 release edge 的具体动作由处境表投递。
- 旧 package 的 Task 完成后交 Working Branch owner 集成，不自动接受 Ticket；旧 Task/Ticket 终态共同进入 completion claim audit。
- terminal Gate 后禁止继续当前 Attempt；新工作由 impl-planning 创建 patch Attempt。
