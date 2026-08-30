# Control Flow

```text
validate → progress restore → choose business action
                                  ↓
                 $dispatcher admission / dispatch / return
                                  ↓
          bounded worker follows subagent-driven-development
                                  ↓
               dev-with-track consumes result and writes
               State / Evidence / Checkpoint / Trail
                                  ↓
              review / manual acceptance / claim audit
                                  ↓
                        Stage 7 / current Gate
```

Dispatcher 与 SDD 平级：前者指导上游主控调度，后者指导下游 bounded worker 方法；dev-with-track/main session 写入 package State、Evidence、Checkpoint 与 Gate。

- blocker 或 evidence 缺失：保留当前业务结论，写 checkpoint；Dispatcher 在没有已解锁且合格动作时进入 idle。
- contract/plan 变化：记录 affected scope 并沿用 current package 的 initial bundle approval；新 package 才取得新 approval。
- 旧 package 的 Task 完成后由 Working Branch owner 集成，不自动接受 Ticket。
- terminal Gate 后冻结当前 Attempt；新工作由 impl-planning 创建 patch Attempt。

完成条件：任何节点都能明确是业务 owner、上游调度、下游方法还是 package state write，不存在第二个 owner。
