# Runtime Protocol

运行状态唯一来源是 `.impl-package/state.json`；格式和命令见 `../../../references/impl-package-current-state.md`。

## Codex Resume Capsule

Codex Hook 已激活 current package 时，`SessionStart` 可注入 `Impl-Package Resume Capsule v1`。Capsule 只提供 session/package、Attempt、HEAD、state/Gate 读取状态、situation/action 与 preview digest；它不拥有业务裁决，也不充当 Evidence、Acceptance、Gate、closure 或 dispatch credential。

Capsule 与 current package/HEAD/approval 匹配时可作为恢复入口；首次恢复缺失/失配、Hook 不可用、读取 warning、未知外部状态变化、状态更新失败（含 CAS 失败）或部分写入时执行完整恢复。已知 CLI 成功更新后按 delta 更新当前事实。

Capsule 的 `projection-complete: false` 表示宿主长度预算只能承载摘要；先按其中命令读取完整只读 JSON 投影，再判断候选或写入。完整投影由 `situation.py render --no-write-credential --json` 提供，派发前另生成当前 credential。

## 恢复顺序

1. 运行 `package validate`；projection drift 时运行 `package refresh-progress`。
2. 打开 `progress.md`，确认 current Attempt、lifecycle、Gate、blocker、active checkpoint 和恢复入口。
3. 根据 typed Ticket dependency 与批准范围恢复业务重点和全部相关候选；Progress/checkpoint 不授权 dispatch。
4. 把候选交给 `$dispatcher`；Dispatcher 负责资源 admission、receipt、return、review pacing、补派与 idle，idle 不等于 package closed。
5. 只打开当前候选需要的 Plan/Ticket/Execution Record/evidence；旧 package 才按需读取 DAG/Handoff。
6. 准备派发、记录返回或恢复待派审增量时，读取 [Situation Inputs](../../../references/situation-inputs.md) 的 trail 合同。按当前业务事实、dependency、授权、资源与 in-flight 选择工作；派发前用 `situation.py render` 刷新当前投影和 credential，取得真实 receipt 后记录 dispatch。投影只展示派生业务动作，不替代主控扫描剩余工作。消费结果后用语义 Ticket/evidence/recovery/trail 命令写权威事实。

## Evidence 与 Execution Record

Evidence 使用存在的仓库相对路径，可带 anchor，并足以解释状态变化。checkpoint 是恢复边界；judgment 记录执行期 decision、finding disposition、failure learning 与外部证据解释。routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。

## Readiness、返工与调度

- 新 package 由 Ticket typed dependency 决定业务 readiness；Dispatcher 只执行已获业务放行的候选。
- 旧 package 的 Task dependency 未释放时不得进入 READY/RUNNING；Task DONE 后仍需集成、共享验证与 Ticket AC 映射。
- plan/contract 变化只使 affected subset 进入 revalidation，并沿用 initial bundle approval。
- worker return 不可归因或 `INCOMPLETE` 时，核对 dispatch identity、进程、diff、residue 与上下文。边界可信则沿原 worker 恢复；边界失真则由 Dispatcher 先调查受影响范围再决定 worker。业务 `BLOCKED` 原样保留。
- 恢复旧 Attempt 时，机器只读忽略历史候选清单；主控读取旧 trail/候选清单及 Execution Record、checkpoint、handoff，沿用其中仍成立的授权和资源限制，无需重写旧记录。
- native dispatch 已成功但 CLI 因 stale credential 未记入 trail 时，保留真实 receipt 与 `dispatch_id`，刷新 canonical facts 后补齐该次记录；记账恢复不得重派 worker。

## Findings、Review 与 Gate

- accepted Track C finding：先消费 do-review 在同一 ReviewRun 内完成的独立 source recheck；该动作不改变 Ticket/Attempt 状态。
- current sources uniquely decide：把 finding 作为 implementation/evidence defect，保留原始意见、定位和裁决，交 Dispatcher 按影响、资源和整合成本安排 fix。
- source missing/ambiguous/conflicting：回 req-align；多个合理业务结果请求 Owner，结论前不派 mutation。
- 其他 accepted finding：沿用 implementation、安全、证据或知识分流；review topology 与 closure 由 do-review 拥有。
- durable knowledge：Stage 7 登记 `_pending.md` 与 truth pointer，后续交 backfill。

Gate 每次重写 current `gate.md`；terminal Gate 同时生成 `.impl-package/attempts/<attempt>.json` 的只读 Ticket 快照。历史快照缺失时只用明确 revision 运行 `package archive-attempt` 补录。terminal Gate 后全部 runtime mutation fail closed。
