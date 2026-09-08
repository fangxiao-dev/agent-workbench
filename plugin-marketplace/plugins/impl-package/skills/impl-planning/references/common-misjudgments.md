# Impl Planning 常见误判

本页只承载每条规则对应的具体误判后果（为什么错、错了会有什么下游代价），不复述规则本身——规则的权威定义在 `SKILL.md` 正文；行为回归只放在 `../evals/evals.json`，不把 eval 当运行时清单。

## Admission 与计划

- 拿未批准或过期的 D/S 事实开始写 Plan，会把实现候选误写成已冻结的行为合同。
- 把 Plan 当成补齐 Spec 留白的地方，会产生第二套 DTO/schema，两个实施者随后可以按不同合同实现。
- patch 重述整份历史范围，会把未变化的 evidence 和 gate 重新混入当前 delta，无法判断真正受影响的边界。
- 为新 package 顺手创建 DAG，会重新引入 Ticket/Task 双层状态和两个 acceptance authority。
- 只审 Plan 文本、不审跨 Ticket 的 coverage/ownership/order，会让一个局部看似完整的 candidate 直接进入执行。

## 并行与调度安排

- 把逐约束映射和逐项验证细节写回 Plan 的全局调度表，会与 Ticket 的 Contract references 与 AC 重复，制造两处可能漂移的合同来源。
- 把 Ticket 拆分交给旧 DAG 入口，会把已经选择的 Ticket-only Composition 偷换成另一套任务结构。

## Ticket 合同与证据

- 按文件或层切分会得到无法独立验收的半条路径，Ticket 数量看似增加但 acceptance 没有变清楚。
- 缺少稳定 ID、owner 或 typed dependency，后续 evidence 无法归属，状态也会漂移到文档正文之外。
- 不区分 `EXISTS`/`NEW`，reviewer 会把待建设入口当成已存在，或把已有依赖重复纳入本 Ticket。
- 只让后端接线 Ticket 通过，会把 UI 形状错误或组件复用错误隐藏在“UI 已实现”的笼统声明里。
- 引用整份文档会让 Ticket 看似有依据，却无法判断实际依赖哪条 authority；引用 `contract-design.md` 只停在章节级而不点名 entry point，等于把一大节都当成了下游默认要读的上下文。
- 只写“有测试”而不写入口、owner 和 coverage，或让一个 stable claim 同时承载可独立失败的结论，会把不可执行、重叠或部分可证的 AC 留到执行末端才暴露。

## State 与发布边界

- 跳过 `package validate` 或先写 state 再确认 Plan，会把不可恢复的 runtime 事实当成已获批的 package 状态。
- 绕过 execution-boundaries 的授权确认与完成前 evidence gate，会让 mutation 在未确认授权范围时发生。
- 发布时又创建 Task/DAG 或手写状态，会产生第二个运行时 authority，Ticket 的 Approved/PENDING 也无法回放。
- 把旧 Task `DONE` 或一次 early falsification 当成 Ticket 满足，会漏掉 remaining evidence 和第一条路径上的安全不变量。
- 把进度或 runtime projection 写回 Ticket，会让接受状态、执行状态和恢复投影形成多个可写来源。

## 仅进 evals 的回归价值

`../evals/evals.json` 只验证上述规则在模型行为中仍成立，例如缺合同时回 req-align、stable claim 原子化、不可分拆 oracle、真实依赖与轻量调度判断；它不替代本页的执行提醒。
