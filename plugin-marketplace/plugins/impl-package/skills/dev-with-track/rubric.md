# Dev With Track Rubric

## Confirmed preferences

- Preserve complete Progress: new package 的 Ticket state、active checkpoint、Attempt judgment history；旧 package 才保留 Task state 与 conditional Task Handoff。
- Keep `state.json` as the sole current-state source; Progress and runtime tables are projections.
- 旧 Task completion never implies Ticket acceptance；新 package 不创建 Task 状态。
- Evidence paths are repository-relative and must exist.
- Gate contains the current verdict; Git contains history.
- Revalidate only the subset affected by an actual contract or plan change.
- [已确认] terminal Gate 只冻结命令执行时的 Git HEAD，并清空 active checkpoint；历史 judgment 留在 frozen Execution Record，而不继续投影为 active。
- [已确认] review topology 与 coverage 由 `do-review` 拥有；本 skill 只消费 terminal-final coverage 和 finding closure 结论。
- [已确认] 只有 parent 已接受并归类的 Track C / Spec fidelity finding 才在 fix 前消费一次独立 source recheck；该机制不新增 Ticket/Attempt 状态，也不扩张修复调度边界。
- [已确认] 长任务先写 durable state/ER/Gate，再输出最终叙述；Ticket-only 的 `INCOMPLETE` 恢复事实使用 active checkpoint/Attempt ER，旧 Task package 才使用 Task Handoff。
- [已确认] `$dispatcher` 与 `/impl-package:subagent-driven-development` 是平级指导：前者面向上游 Topic-first admission、baby step 批次、dispatch/return/idle，后者面向下游 bounded worker 的 Topic/dependency/mode/execution-lane/lifecycle；本 Skill 选择业务动作并消费两者结果。
- [已确认] Dispatcher idle、worker 局部 DONE 与 SDD review PASSED 是局部事实；本 Skill 依据 canonical Ticket/State/Evidence/Gate 判断业务 closure。
- [已确认] 业务控制循环置于入口前部，先刷新事实并选择动作，再形成 Topic、调用 Dispatcher/SDD、消费结果并写入 package 权威状态。
- [已确认 · 2026-09-05] owning-stage 主 thread 更新业务文档并裁决语义；一个 execution-boundaries 记账 subagent 串行调用 CLI 更新 state 与运行投影，日常异步，依赖落盘或收口时等待；取代此前「主 thread 是 state 唯一 writer、bookkeeper 仅作异常 slow path」的表述。
