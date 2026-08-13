# Runtime Protocol

运行状态唯一来源是 `.impl-package/state.json`；格式和命令见 `../../../references/impl-package-current-state.md`。先按 Plan 的 Composition 分支：新 package 是 Ticket-only/Plan-direct；只有旧 3.4 package 才读取 Task/DAG/Handoff。

## 恢复顺序

1. validate 当前 package；projection drift 时先运行 `refresh-progress`。
2. 打开 `progress.md`，确认 current Attempt、lifecycle、Gate、blocker、active checkpoint 和 next action；新 package 只确认 Ticket Acceptance，旧 package 才确认两条状态轴。
3. 新 package 依据 Ticket typed dependency 与 Ticket state 判断 readiness；旧 package 才依据 DAG/Task 和 Ticket dependency。Progress 不授权 readiness。
4. 新 package 只打开当前动作需要的 plan/Ticket/Execution Record/evidence；旧 package 才按需读取 DAG/Handoff。
5. 推进后使用 `set-state --expect`，再写 checkpoint 或必要 judgment。

## Evidence 与 Execution Record

Evidence 必须是存在的仓库相对路径，可带 anchor，并足以解释状态变化。不要保存额外完整性证明。

- checkpoint：恢复边界；同 subject 的最后一条为 active。新合同的 `RETIRED` 对应旧 3.4 的 `WAIVED/SUPERSEDED`，状态进入 `NEEDS-REVALIDATION` 时 Progress 标为 stale。
- judgment：执行期 decision、finding disposition、failure learning、外部证据解释。
- routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。

## Readiness 与返工

- 新 package：Ticket implementation dependency 阻止实施；acceptance dependency 阻止 SATISFIED；release dependency 在 Gate/release 前复核。
- 旧 package：Task dependency 未释放时不得进入 READY/RUNNING；Task DONE 后由 Working Branch owner 集成、运行共享验证并映射 Ticket AC。
- plan/contract 变化只使实际 affected subset 进入 NEEDS-REVALIDATION，并重新审查相应 coverage/verification。

## Findings 与 Gate

- implementation defect：当前 Attempt 修复并重验。
- behavior contract gap：回 req-align/impl-planning；affected state 失效。
- 多个合理业务结果：owner decision。
- durable knowledge：Stage 7 登记 `_pending.md` 与 truth pointer，后续交 backfill。

Gate 每次重写 current `gate.md`；Git 与旧 Attempt Execution Record 的 lifecycle/Gate 摘要提供历史。terminal Gate 后全部 runtime mutation fail closed。
