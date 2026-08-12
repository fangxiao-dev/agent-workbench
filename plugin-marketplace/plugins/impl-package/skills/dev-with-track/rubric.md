# Dev With Track Rubric

## Confirmed preferences

- Preserve complete Progress: current Task/Ticket state、resume、Attempt checkpoint/judgment history and conditional Task Handoff.
- Keep `state.json` as the sole current-state source; Progress and runtime tables are projections.
- Task completion never implies Ticket acceptance.
- Evidence paths are repository-relative and must exist.
- Gate contains the current verdict; Git contains history.
- Revalidate only the subset affected by an actual contract or plan change.
- [已确认] terminal Gate 只冻结命令执行时的 Git HEAD，并清空 resume；历史 checkpoint 留在 frozen Execution Record，而不继续投影为 active。
- [已确认] review topology 与 coverage 由 `do-review` 拥有；本 skill 只消费 terminal-final coverage 和 finding closure 结论。
- [已确认] 长任务先写 durable state/ER/Gate，再输出最终叙述；dispatch 的 `INCOMPLETE` 恢复事实使用 Task Handoff 或 Attempt ER checkpoint 保存。
