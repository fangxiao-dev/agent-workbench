# Control Flow

```text
validate → restore canonical facts → choose business focus + candidate scope
                                      ↓
             $dispatcher selects / delegates / consumes / reviews
                                      ↓
          dev-with-track records State / Evidence / Checkpoint / Trail
                                      ↓
              formal review / manual acceptance / claim audit
                                      ↓
                          Stage 7 / current Gate
```

dev-with-track/main session 拥有业务 readiness、语义裁决和 package state write；Dispatcher 拥有通用执行协作。worker 的局部 outcome、review PASS 和调度 idle 都作为输入返回 dev-with-track，不创建第二个 completion owner。

- blocker 或 evidence 缺失：记录受影响候选和恢复入口；Dispatcher 继续评估其他合法候选。
- contract/plan 变化：记录 affected scope 并沿用 current package 的 initial bundle approval；新 package 才取得新 approval。
- 旧 package 的 Task 完成后由 Working Branch owner 集成，不自动接受 Ticket。
- terminal Gate 后冻结 current Attempt；新工作由 impl-planning 创建 patch Attempt。

完成条件：任一节点都能明确属于业务裁决、执行协作或 package state write，且候选范围没有被局部等待缩成单一路径。
