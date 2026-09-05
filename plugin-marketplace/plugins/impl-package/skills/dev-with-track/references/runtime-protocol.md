# Runtime Protocol

运行状态唯一来源是 `.impl-package/state.json`；格式和命令见 `../../../references/impl-package-current-state.md`。

## Codex Resume Capsule

Codex Hook 已显式激活当前 package 时，`SessionStart` 可注入 `Impl-Package Resume Capsule v1`。Capsule 只提供 session/package、Attempt、HEAD、state/Gate 读取状态、situation/action 与 preview digest；它不拥有业务裁决，也不充当 Evidence、Acceptance、Gate、closure 或 dispatch credential。

Capsule 与当前 package/HEAD/approval 匹配时，可作为本次恢复入口；首次恢复缺失/失配 Capsule、Hook 不可用、读取 warning，或发生未知外部状态变化、CAS 失败、部分写入时，执行下方完整恢复顺序。已知 CLI 成功更新后消费记账回执，按 delta 更新当前事实，不重走完整恢复。普通 SDD 不激活 package，因此不产生 Capsule。

## 恢复顺序

1. 运行 `package validate`；projection drift 时先运行 `package refresh-progress`。
2. 打开 `progress.md`，确认 current Attempt、lifecycle、Gate、blocker、active checkpoint 和 next action。
3. 根据 typed Ticket dependency 选择业务动作；Progress/checkpoint 不授权 dispatch。
4. 对当前业务候选应用 `$dispatcher` 的 Topic-first admission，形成当前 baby step 批次并消费 worker return；每次返回后检查受影响候选补派，整批结束或准备 idle 时全局扫描；idle 不等于 package closed。
5. 只打开当前动作需要的 Plan/Ticket/Execution Record/evidence；旧 package 才按需读取 DAG/Handoff。
6. 消费结果后使用语义 Ticket/evidence/recovery/trail 命令写权威事实；真正 dispatch 前用普通 `situation.py render` 生成当前 credential。

## Evidence 与 Execution Record

Evidence 使用存在的仓库相对路径，可带 anchor，并足以解释状态变化；不保存额外完整性证明。

- checkpoint：恢复边界；`activeCheckpoints[subject]` 是唯一 active 值并覆盖写。
- judgment：执行期 decision、finding disposition、failure learning、外部证据解释。
- routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。

## Readiness、返工与调度

- 新 package：Ticket typed dependency 决定业务 readiness；Dispatcher 只调度已解锁且合格的动作。
- 旧 package：Task dependency 未释放时不得进入 READY/RUNNING；Task DONE 后仍需集成、共享验证与 Ticket AC 映射。
- plan/contract 变化只使 affected subset 进入 revalidation，并沿用同一 initial bundle approval。
- worker 返回不可归因或 `INCOMPLETE` 时，不套固定 fallback 次数。先核进程、diff、residue 与 Topic context；上下文可信则同 lane 继续，失效则由 Dispatcher 退役并重新派发。业务 `BLOCKED` 原样保留。

## Findings、Review 与 Gate

- accepted Track C finding：先消费 `do-review` 在同一 ReviewRun 内完成的一次独立 source recheck；该动作不改变 Ticket/Attempt 状态。
- current sources uniquely decide：轻量 delta review 的已确认 findings 随下一个 baby step 的 brief 一并下发，不单独派 bounded fix；独立 formal review 的 finding 作为 implementation/evidence defect，交 Dispatcher 的同 Topic work lane，worker 使用 SDD `fix` 方法。派发前若同一 Topic 已经过两次以上修复方向仍未收敛、同一 finding 或同一机制在后续 round 重新出现，或 review 结论跨多个 writer、多个入口或共享 authority/lock seam，先按 `/diagnosing-bugs` 做定位再决定修复动作；其余直接 bounded fix。diagnosing-bugs 只返回定位结论，Ticket/Attempt 状态与 dependency release 继续由本流程处理，finding closure 继续由 `/impl-package:do-review` 拥有。
- source missing/ambiguous/conflicting：先回 req-align；多个合理业务结果请求 Owner，结论前不派发 mutation。
- 其他 accepted finding：沿用 implementation、安全、证据或知识分流；review topology 与 closure 始终由 `do-review` 拥有。
- durable knowledge：Stage 7 登记 `_pending.md` 与 truth pointer，后续交 backfill。

Gate 每次重写 current `gate.md`；Git 与 frozen Execution Record 提供历史。terminal Gate 后全部 runtime mutation fail closed。
