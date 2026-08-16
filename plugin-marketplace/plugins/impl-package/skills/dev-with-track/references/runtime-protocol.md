# Runtime Protocol

运行状态唯一来源是 `.impl-package/state.json`；格式和命令见 `../../../references/impl-package-current-state.md`。3.5 新 package 只读取 Ticket/evidence/checkpoint；3.4 Task/DAG/Handoff 只能由一次性迁移 prompt/validator 读取。

## 恢复顺序

1. 运行 `package validate`；projection drift 时先运行 `package refresh-progress`。
2. 打开 `progress.md`，确认 current Attempt、lifecycle、Gate、blocker、active checkpoint 和 next action；新 package 只确认 Ticket Acceptance，旧 package 才确认两条状态轴。
3. readiness 与 dependency 的具体处境和动作由处境表投递。Progress 不授权 readiness。
4. 新 package 只打开当前动作需要的 plan/Ticket/Execution Record/evidence；旧 package 才按需读取 DAG/Handoff。
5. 推进后使用语义 `ticket` 命令的 `--expect`，再写 `recovery checkpoint` 或必要 `recovery judgment`。

## Evidence 与 Execution Record

Evidence 必须是存在的仓库相对路径，可带 anchor，并足以解释状态变化。不要保存额外完整性证明。

- checkpoint：恢复边界；`activeCheckpoints[subject]` 是唯一 active 值并覆盖写。新合同的 `RETIRED` 对应旧 3.4 的 `WAIVED/SUPERSEDED`，状态进入 `NEEDS-REVALIDATION` 时 Progress 标为 stale。
- judgment：执行期 decision、finding disposition、failure learning、外部证据解释。
- routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。

## Readiness 与返工

- 旧 package：Task dependency 未释放时不得进入 READY/RUNNING；Task DONE 后由 Working Branch owner 集成、运行共享验证并映射 Ticket AC。
- plan/contract 变化在同一 package 直接更新；按需记录 affected subset 的 revalidation/coverage/verification，并沿用 initial bundle approval。

## Findings 与 Gate

- accepted Track C / Spec fidelity finding：先消费 `do-review` 在同一 ReviewRun 内完成的一次性独立 source recheck；该动作不改变 Ticket/Attempt 状态。
- current sources uniquely decide：按引用的 Decision/Spec/contract 作为 implementation 或 evidence defect，在当前 Attempt 修复并重验。
- source missing/ambiguous/conflicting：先回 req-align 更新当前 Spec contract ensemble，再进入实现。
- 多个合理业务结果：请求 owner decision；没有结论前不派发修复。
- 其他 accepted finding：沿用现有 implementation、安全、证据或知识分流，不触发 source recheck。
- durable knowledge：Stage 7 登记 `_pending.md` 与 truth pointer，后续交 backfill。

Gate 每次重写 current `gate.md`；Git 与旧 Attempt Execution Record 的 lifecycle/Gate 摘要提供历史。terminal Gate 后全部 runtime mutation fail closed。
