# situation fixture 还原集

这组 fixture 来自两个只读 legacy 源仓库中按 `.impl-package/` 标志目录发现的真实 package。只保留 `situation.py` 会读取的状态、Ticket claim/typed dependency、evidence index、Gate、finding 和 trail 字段；业务正文、客户/账号/金额/真实地址等均替换为占位。

共 50 个 fixture；由于一个 fixture 可以覆盖同层并列或 secondary 处境，当前覆盖以各 fixture 的 `expected.json` 和测试结果为准。测试把 `selected` 或 `parallel_matches` 视为 primary，把 `other_matches` 视为 secondary；`expected_suppressed` 用于验证被更高优先级正确压住的行；`must_not_hit` 针对可见集合断言。

## 2026-08-16 语义修正回归更新

按修正后的 situation table 与 `situation-inputs.md` 合同，更新以下 5 个回归 fixture 的 `expected.json`：

- `p2-awaiting-reviewer`：没有真实 release dependency，移除误报的 `ticket.accept.release-edge-unchecked`。
- `p3-contradictory`：同一 acceptance pair 有 active contradictory evidence，移除不再满足条件的 `ticket.accept.satisfiable`。
- `p4-comparison-mismatch`：pass Gate 已存在，移除 Gate 后仍检查 `attempt.gate.comparison-mismatch` 的旧 suppressed 期望。
- `p4-gate-verdict-undecided`：没有 Gate 且 Ticket 集合为空，不再合成 `attempt.gate.verdict-undecided`，也不满足 `attempt.gate.missing` 的 all-terminal 前提。
- `p4-release-edge-unchecked`：没有真实 typed release dependency，只保留 `ticket.accept.satisfiable`。

本次没有调整这 5 个 fixture 的输入数据；A2 与 independent 冻结 oracle 未修改。

## Fixture 来源与场景

### P0

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p0-anchor-mismatch` | kaispan-dev/docs/domains/finance-assistant/historical-unverifiable/260731-1332-kontierung-rule-engine — original .impl-package/runtime-state.json contractVersion 3.2 | legacy package 的 revision binding/anchor 无法回读；trail 为按真实恢复失败时间线补写的 anchor-mismatch 事实。 | attempt.record.anchor-mismatch |
| `p0-checkpoint-missing` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy attempt 存在长时间外部验证 blocker 但旧格式没有 active checkpoint；trail 为按真实长任务开始后尚未落 checkpoint 补写。 | attempt.record.checkpoint-missing |
| `p0-checkpoint-refresh` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy execution record 的 Resume checkpoint 下一动作随 review/fix 反复刷新；trail 为按真实 next-action 改写补写。 | attempt.record.checkpoint-refresh |
| `p0-evidence-unfiled` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy gate 记录了直接 evidence，但没有把它登记进 evidence index；正文已脱敏。 | ticket.record.evidence-unfiled |
| `p0-handoff-in-flight` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy package 的跨 session/外部阻塞交接尚未完成；trail 为按真实 handoff pending 时间线补写。 | attempt.record.handoff-in-flight |
| `p0-handoff-recovery-needed` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy package 在跨 session 修订 handoff 后仍需重建 continuation；trail 为按真实 recovery retry 时间线补写。 | attempt.record.handoff-recovery-needed |
| `p0-handoff-target-corrected` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy review-closure 的下一动作随修订范围被改写；trail 为按真实 handoff target/order 修正过程补写。 | attempt.record.handoff-target-corrected |
| `p0-judgment-unfiled` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Execution Record 已有判断结果，但 judgment 没有归档；trail 为按真实记录缺口补写。 | ticket.record.judgment-unfiled |
| `p0-projection-drift` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy 3.4 attempt 的 authoritative state 与 progress 投影在 review-closure 期间短暂漂移；trail 为按该真实修订时间线补写的 projection-drift 事实。 | package.record.projection-drift |
| `p0-session-resumed` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy execution record 多次以 Resume checkpoint 接续；trail 为按真实接续时间线补写，checkpoint 后尚无新动作。 | attempt.record.session-resumed |
| `p0-state-missing` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-12-finance-office-tax-advisor — original marker had no state.json/runtime-state.json | 原包只有标志目录而没有可用 runtime state；state-missing 用缺失 state 还原，故本 fixture 是唯一不放 3.5 state.json 的例外。 | package.record.state-missing |
| `p0-terminal-frozen` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy package 已有 terminal pass Gate；翻译为全部 Ticket 已满足且当前 attempt 被 terminal Gate 冻结。 | attempt.gate.terminal-frozen |
| `p4-comparison-mismatch` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Gate 虽为 pass，但 comparison commit 与 satisfied Ticket 的 acceptance revision 不一致；现行 F7 只在 Gate 写入前检查，因此已有 pass Gate 时只保留 P0 terminal-frozen。 | attempt.gate.terminal-frozen |

### P1

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p1-all-edges-held` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Ticket 依赖外部 acceptance/实现前置且 blocker 未释放；翻译为 pending child 的 implementation edge 全部 held。 | attempt.readiness.all-edges-held |
| `p1-blocker-maybe-resolved` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Gate 从 blocked 进入后续 pass 前，原 Ticket blocker 已出现可能解除信号；trail 为按该 recheck 窗口补写。 | ticket.readiness.blocker-maybe-resolved |
| `p1-integration-carrier-unavailable` | prj-supplyer-webapp/docs/implementations/release-external-readiness-audit — original .impl-package/runtime-state.json contractVersion 3.2 | legacy release/cutover package 明确把 production/provider mutation 延后，当前没有获批 integration carrier；trail 为按真实 deferred gate 补写。 | attempt.readiness.integration-carrier-unavailable |
| `p1-multiple-ready` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy package 同时有多个无前置 Ticket 可开始；trail 为按真实 admission 后尚未选卡补写。 | attempt.readiness.multiple-ready-tickets |
| `p1-worker-still-running` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy T9 仍处于 RUNNING/外部 blocker；trail 为按 worker 已派发但尚无 result 补写。 | attempt.readiness.worker-still-running |

### P2

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p2-awaiting-reviewer` | prj-supplyer-webapp/docs/implementations/order-snapshot-reuse — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Ticket 实现结果已返回，但显式要求的 reviewer 尚未运行；当前没有真实 release dependency。 | ticket.review.awaiting-reviewer；secondary: ticket.accept.satisfiable |
| `p2-closure-awaiting` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy patch attempt 的 finding 已修复但仍等待 closure review；正文已脱敏。 | finding.review.closure-awaiting；secondary: finding.disposition.grading-undecided, attempt.disposition.findings-triage-pending |
| `p2-envelope-invalid` | prj-supplyer-webapp/docs/implementations/inventory-manufacture-issues-153-158 — original .impl-package/runtime-state.json contractVersion 3.2 | legacy review-fix package 有审查 finding 与修复返回边界；trail 为按真实 fixer 返回 envelope 不可采信补写。 | finding.fix.worker-envelope-invalid；secondary: attempt.disposition.findings-triage-pending |
| `p2-incomplete-first` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 外部验证首次未完成，仍允许一次 fresh fallback；trail 为按真实一次 INCOMPLETE 返回补写。 | ticket.implement.worker-incomplete-first |
| `p2-incomplete-second` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 外部 blocker 在两次 implementation 返回中仍未完成；trail 为按第二次连续 INCOMPLETE 补写。 | ticket.implement.worker-incomplete-second |
| `p2-investigate-evidence-gap` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-22-kassel-pdf-to-extf-poc — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 调查无法取得足够外部/手工证据，返回 EVIDENCE_GAP；trail 为按真实调查时间线补写。 | ticket.investigate.evidence-gap |
| `p2-investigate-no-carrier` | prj-supplyer-webapp/docs/implementations/release-external-readiness-audit — original .impl-package/runtime-state.json contractVersion 3.2 | legacy investigation 需要外部 carrier/production 访问，但记录显示没有获批 carrier；trail 为按真实调查时间线补写。 | ticket.investigate.no-carrier |
| `p2-main-session-finding` | prj-supplyer-webapp/docs/implementations/inventory-manufacture-issues-153-158 — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 主控在验证/审阅中直接发现 finding，需要直接进入 fresh fix；正文已脱敏，trail 为按真实主控发现补写。 | finding.fix.main-session-discovered；secondary: finding.disposition.grading-undecided, attempt.disposition.findings-triage-pending |
| `p2-review-required-trigger` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Ticket 的记录明确触发 review，但尚未形成 reviewer 结果；正文已脱敏。 | ticket.review.required-trigger |
| `p2-reviewer-returned` | prj-supplyer-webapp/docs/implementations/order-snapshot-reuse — original .impl-package/runtime-state.json contractVersion 3.2 | legacy reviewer 返回新的 finding，要求 fresh fixer 处理；正文已脱敏，trail 为按真实 review loop 补写。 | finding.fix.reviewer-returned；secondary: finding.disposition.grading-undecided, attempt.disposition.findings-triage-pending |
| `p2-reviewer-unavailable` | prj-supplyer-webapp/docs/implementations/order-document-completion-workflow — original .impl-package/runtime-state.json contractVersion 3.2 | legacy review loop 因 reviewer/ReviewRun 不可用而中断；trail 为按真实超时记录补写。 | attempt.review.reviewer-unavailable |
| `p2-source-recheck` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy Track C finding 的来源需要同一 ReviewRun 复核，当前状态仍 pending。 | finding.review.source-recheck-pending；secondary: finding.disposition.grading-undecided, attempt.disposition.findings-triage-pending |
| `p2-worker-blocked` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy implementation ticket 因外部依赖不可用而保持 blocked；为避免把同一事实误判成 attempt-level carrier 缺失，fixture 只保留 Ticket-level blocker；trail 为按真实阻塞时间线补写。 | ticket.implement.worker-blocked |

### P3

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p3-comparison-head-unfixed` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy review 的 comparison head 没有固定在 immutable revision；trail 为按真实 review 重开前状态补写。 | attempt.review.comparison-head-unfixed |
| `p3-contradictory` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 已 satisfied 的 Ticket 后续出现同 acceptance pair 的 contradictory evidence，需先裁决冲突；正文已脱敏。 | ticket.verify.contradictory-unresolved, ticket.rework.evidence-conflict；secondary: attempt.accept.all-tickets-terminal, attempt.gate.durable-delta-missing |
| `p3-integration-evidence-unavailable` | prj-supplyer-webapp/docs/implementations/release-external-readiness-audit — original .impl-package/runtime-state.json contractVersion 3.2 | legacy acceptance 依赖外部/生产载体，但当前没有可采信的 integration evidence；trail 为按真实审计阻塞时间线补写。 | attempt.verify.integration-evidence-unavailable |
| `p3-retire-undecided` | kaispan-dev/docs/implementations/legacy-impl-plans-retirement — original .impl-package/runtime-state.json contractVersion 3.2 | legacy retirement ledger 表明 Ticket 已不再需要，但尚未决定 waived 还是 superseded；正文已脱敏。 | ticket.disposition.retire-undecided |
| `p3-revalidation-pending` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy evidence/contract 变化后 Ticket 被置为 NEEDS-REVALIDATION，重验尚未完成。 | ticket.rework.revalidation-pending |
| `p3-revision-diverged` | kaispan-dev/docs/domains/finance-assistant/historical-unverifiable/260731-1332-kontierung-rule-engine — original .impl-package/runtime-state.json contractVersion 3.2 | legacy satisfied 绑定的 acceptance revision 已落后于当前 HEAD，且 trail 也证明 HEAD 已前进；trail 为按真实返工时间线补写。 | ticket.rework.revision-diverged；secondary: attempt.accept.all-tickets-terminal, attempt.gate.durable-delta-missing |
| `p3-safety-invariant` | prj-supplyer-webapp/docs/implementations/inventory-manufacture-issues-153-158 — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 验证已覆盖普通 acceptance，但安全不变量没有被证据反驳/确认，需单独 verify；trail 为按真实验证时间线补写。 | ticket.verify.safety-invariant-unfalsified |
| `p3-sources-unique` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-22-kassel-pdf-to-extf-poc — original .impl-package/runtime-state.json contractVersion 3.2 | legacy 多来源调查最终只剩一个可裁决来源，允许进入 implementation/reverify；trail 为按真实取证时间线补写。 | ticket.route.sources-uniquely-decide |

### P4

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p4-acceptance-edge-held` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy Ticket 已有部分 evidence，但 acceptance dependency 仍被 blocker 持有，不能进入 satisfied；正文已脱敏。 | ticket.accept.acceptance-edge-held |
| `p4-all-terminal-durable-missing` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy attempt 的 Ticket 已全部 terminal，但 Gate 前要求的 durable delta 尚未记录；这两个 P4 条件在状态上并列。 | attempt.accept.all-tickets-terminal, attempt.gate.durable-delta-missing |
| `p4-completion-claim-unaudited` | prj-supplyer-webapp/docs/implementations/order-document-completion-workflow — original .impl-package/runtime-state.json contractVersion 3.2 | legacy attempt 已接近完成声明，但 completion claim 还没有经过 verification audit；trail 为按真实收口前状态补写。 | attempt.accept.completion-claim-unaudited |
| `p4-findings-triage-pending` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules — original .impl-package/runtime-state.json contractVersion 3.2 | legacy finding 已定为 P1，但仍没有分流到 Decision/Spec/Execution Record/Durable Delta；正文已脱敏。 | attempt.disposition.findings-triage-pending |
| `p4-gate-verdict-undecided` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-12-finance-office-tax-advisor — marker had no state.json; translated as original legacy package with missing Gate verdict | fixture 没有 Gate，且 state 中没有 Ticket；缺 Gate 不合成 undecided，all-terminal 前提也不成立。 | 无可见 situation |
| `p4-grading-undecided` | prj-supplyer-webapp/docs/implementations/inventory-manufacture-issues-153-158 — original .impl-package/runtime-state.json contractVersion 3.2 | legacy finding 已有候选 route，但仍未决定 P1/P2 还是 editorial grade；正文已脱敏。 | finding.disposition.grading-undecided |
| `p4-manual-result-missing` | kaispan-dev/docs/domains/finance-assistant/implementations/2026-07-22-kassel-pdf-to-extf-poc — original .impl-package/runtime-state.json contractVersion 3.2 | legacy manual acceptance 已指定 owner，但结果未回填到 Execution Record；trail 为按真实手工验收阻塞补写。 | attempt.verify.manual-result-missing |
| `p4-release-edge-unchecked` | prj-supplyer-webapp/docs/implementations/order-create-release-consistency — original .impl-package/runtime-state.json contractVersion 3.2 | legacy acceptance evidence 已支持 claim，但当前 fixture 没有真实 typed release dependency。 | ticket.accept.satisfiable |
| `p4-satisfiable` | kaispan-dev/docs/implementations/2026-08-10-accounting-scope-policy-ownership — original .impl-package/state.json formatVersion 3.4 | legacy Ticket 的 required claims 已有同 revision supporting evidence，acceptance/release 边均已复核，达到 satisfiable。 | ticket.accept.satisfiable |
| `p4-terminal-coverage-incomplete` | prj-supplyer-webapp/docs/implementations/inventory-manufacture-issues-153-158 — original .impl-package/runtime-state.json contractVersion 3.2 | legacy verification 尚未覆盖所有 terminal/final 证据边，不能完成 terminal review；trail 为按真实收口检查补写。 | attempt.review.terminal-coverage-incomplete |

### P5

| fixture | 真实来源（原格式） | 还原场景 | primary / secondary |
|---|---|---|---|
| `p5-intake-backlog` | kaispan-dev/docs/implementations/legacy-impl-plans-retirement — original .impl-package/runtime-state.json contractVersion 3.2 | legacy retirement/standing-bookkeeper 队列仍有待落账 item；业务内容已替换为占位。 | package.record.intake-backlog |

## 未覆盖的 3 行

| slug | 原因 |
|---|---|
| `ticket.route.multiple-business-outcomes` | `manual` 判据：真实 legacy 材料确实出现过多种合理业务结果，但没有机械来源替 owner 做语义裁决；renderer 只把它列在 `manual`，不应伪造 primary fixture。 |
| `ticket.route.sources-conflicting` | `manual` 判据：来源冲突的最终处置需要业务判断；同上，不用合成一个“可自动推导”的状态。 |
| `attempt.rework.contract-changed` | 真实 legacy package 没有 `trail.jsonl`；该行还要求 trail head 到当前 HEAD 的 Git diff 中出现 package contract/Ticket 变化。fixture 目录是未跟踪测试输入，无法不修改受保护实现或制造仓库提交来忠实还原。 |

## 备注

- legacy package 原始格式是 `.impl-package/runtime-state.json` contractVersion 3.2，或少量 `.impl-package/state.json` formatVersion 3.4；fixture 翻译到 3.5。
- legacy 没有 trail；凡 `expected.json` scenario 标注“trail 为按真实流程补写”的 fixture，只补写从真实 Execution Record/Gate/阻塞时间线可直接推出的最小行。
- `p0-state-missing` 是有意例外：它验证缺失 state 的 fail-closed 行，因此不放 3.5 `state.json`。
- 未把 `situations.yaml`、`situation.py` 或两个素材仓库作为测试适配目标修改。
