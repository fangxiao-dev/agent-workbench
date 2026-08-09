# Runtime Protocol

运行状态唯一来源是 `.impl-package/state.json`；格式和命令见 `../../references/impl-package-current-state.md`。`progress.md` 是完整恢复投影，Execution Record 是公共执行判断，Handoff 是条件式局部接手材料。

## 恢复顺序

1. validate 当前 package；projection drift 时先运行 `refresh-progress`。
2. 打开 `progress.md`，确认 current Attempt、lifecycle、Gate、两条状态轴、blocker、active checkpoint 和 next action。
3. 依据 DAG 与 typed Ticket dependency 现场判断 readiness；Progress 不授权 readiness。
4. 只打开当前动作需要的 plan/Ticket/DAG/Handoff/Execution Record/evidence。
5. 推进后使用 `set-state --expect`，再写 checkpoint 或必要 judgment。

## Evidence 与 Execution Record

Evidence 必须是存在的仓库相对路径，可带 anchor，并足以解释状态变化。不要保存额外完整性证明。

- checkpoint：恢复边界；同 subject 的最后一条为 active，状态进入 `NEEDS-REVALIDATION/SUPERSEDED` 时 Progress 标为 stale。
- judgment：执行期 decision、finding disposition、failure learning、外部证据解释。
- routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。

## Readiness 与返工

- Task dependency 未释放时不得进入 READY/RUNNING。
- Ticket implementation dependency 阻止实施；acceptance dependency 阻止 SATISFIED；release dependency在 Gate/release 前复核。
- Task DONE 后由 Working Branch owner 集成、运行共享验证并映射 Ticket AC。
- plan/contract 变化只使实际 affected subset 进入 NEEDS-REVALIDATION，并重新审查相应 coverage/verification。

## Findings 与 Gate

- implementation defect：当前 Attempt 修复并重验。
- behavior contract gap：回 req-align/impl-planning；affected state 失效。
- 多个合理业务结果：owner decision。
- durable knowledge：Stage 7 登记 `_pending.md` 与 truth pointer，后续交 backfill。

Gate 每次重写 current `gate.md`；Git 与旧 Attempt Execution Record 的 lifecycle/Gate 摘要提供历史。terminal Gate 后全部 runtime mutation fail closed。
