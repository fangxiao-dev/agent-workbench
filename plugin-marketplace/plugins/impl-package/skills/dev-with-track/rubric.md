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
- [已确认] 只有 parent 已接受并归类的 Track C / Spec fidelity finding 才在 fix 前消费一次独立 source recheck；该机制不新增 Ticket/Attempt 状态，也不扩张 `dispatch-fix`。
- [已确认] 长任务先写 durable state/ER/Gate，再输出最终叙述；Ticket-only 的 `INCOMPLETE` 恢复事实使用 active checkpoint/Attempt ER，旧 Task package 才使用 Task Handoff。
