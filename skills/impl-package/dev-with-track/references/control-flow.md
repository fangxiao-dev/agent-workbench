# Dev With Track Control Flow

## 接入已有 package

1. 运行 committed validation，读取 decision/spec 当前 revision、current attempt plan、根 `progress.md`、`execution-records/index.md`、gate.md 最新 entry 与所需 module knowledge/code。
2. 最新 attempt 没有 terminal gate 时恢复该 attempt；已有 terminal gate 且有新工作时路由 impl-planning 创建 patch。
3. 当前 plan 是 Attempt ID、P revision 与 Composition 的事实源；spec 只提供当前 contract 与 AC。
4. `dag=true` 时从最小 Task graph 和 runtime state 恢复 Task；两条状态轴从根 `progress.md` 恢复。仅 BLOCKED、handoff、retry 或并行派发 Task 使用 `tasks/Tn-handoff.md`。

## 执行与 Ticket 验收

1. 只选择已知依赖满足且 primary ownership 不冲突的 Task；可委派时使用 `dispatch-bounded-task` 的最小派发模板。
2. Task `DONE` 后由 Working Branch owner 集成产出、处理实际 seam/冲突并运行共享验证；`DONE` 不改变 Ticket acceptance status。
3. Task `BLOCKED` 记录原因、建议动作和影响 Ticket。Ticket 最终验收前只扫描贡献该 Ticket 的 BLOCKED Task；若其影响 AC、行为或风险边界，则先解除阻塞。实际影响扩大时先更新 contribution mapping。
4. 固定 comparison point 后，按当前 diff 与 contract impact 运行 Ticket 正式 review；Task 局部验证或提前风险检查不能替代正式 review/acceptance。实际判断通过 `er-add` 追加到 Attempt ledger。

## Gate evaluation

1. 最终 package review 前，Working Branch owner 全局扫描未终结 Task：必须全部 `DONE`，或有明确、已批准且带理由的 `WAIVED` / `SUPERSEDED`；不得遗留 `BLOCKED`。
2. 再确认每个 Ticket AC 都有实际 evidence，且 active Spec 获得整体覆盖；不要以 Task 状态或分别通过的 Ticket 推断 package 已满足 Spec。
3. 固定 comparison point 和 ER index anchor，分流 execution findings，完成必要 D/S revision 与 re-gate。
4. 计算同 Attempt ID 的下一个未使用 G<n>；terminal verdict 先用该保留 ID 完成 Stage 7，再在 Gate Ledger 说明后一次性插入新 block。
5. status 变化用新 entry 和 Supersedes 表达，不修改旧 block；pass/fail/defer 冻结 plan，blocked 保持 active。

## 结束语义

- planned：attempt plan 已建立；
- running：runtime artifact 已有活动状态；
- verified：Attempt Execution Record 已有选定检查证据；
- gate blocked：最新 entry 为 blocked，attempt 仍 active；
- terminal：最新 entry 为 pass/fail/defer，对应 plan frozen；
- backfilled：terminal Durable Deltas 已进入稳定知识路径。
