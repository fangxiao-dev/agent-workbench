# Independent situation fixtures

本目录是独立复验 A 的 fixture 集合。共 25 个 fixture：

- P0 的 12 行全部各有一个 fixture。
- 本轮新增的 13 行全部覆盖；其中 6 行与 P0 重合，另补 7 个低层 fixture。
- 余下 6 个名额补了 basis=cli 的 B2、C13、C14、C15、F4、F7。

`p0-state-missing` 故意没有 `.impl-package/state.json`；其余 fixture 只保留 state、必要的 Ticket claim/dependency、Gate、finding 和最小 trail。trail 文件均为从 legacy 执行顺序补写的最短时间线，不声称 legacy 当时已经有 trail 机制。

## 覆盖索引

| Fixture | Primary | Legacy source |
| --- | --- | --- |
| p0-terminal-frozen | `attempt.gate.terminal-frozen` | kaispan `2026-08-10-accounting-scope-policy-ownership` |
| p0-state-missing | `package.record.state-missing` | supplyer `260712-order-detail-lifecycle-retirement` |
| p0-projection-drift | `package.record.projection-drift` | supplyer `order-create-release-consistency` |
| p0-anchor-mismatch | `attempt.record.anchor-mismatch` | supplyer `260719-rechnung-email-216` |
| p0-handoff-recovery-needed | `attempt.record.handoff-recovery-needed` | supplyer `260720-persistent-operation-recovery` |
| p0-handoff-target-corrected | `attempt.record.handoff-target-corrected` | kaispan `2026-07-22-kassel-pdf-to-extf-poc` |
| p0-session-resumed | `attempt.record.session-resumed` | supplyer `260720-persistent-operation-recovery` |
| p0-checkpoint-missing | `attempt.record.checkpoint-missing` | supplyer `inventory-lock-renewal` |
| p0-checkpoint-refresh | `attempt.record.checkpoint-refresh` | kaispan `260803-1332-category-sachkonto-bwa-coverage` |
| p0-handoff-in-flight | `attempt.record.handoff-in-flight` | supplyer `260719-rechnung-email-216` |
| p0-evidence-unfiled | `ticket.record.evidence-unfiled` | supplyer `order-create-release-consistency` |
| p0-judgment-unfiled | `ticket.record.judgment-unfiled` | kaispan `2026-08-04-ocr-ai-worker-lane-split` |
| p2-closure-awaiting | `finding.review.closure-awaiting` | supplyer `260719-rechnung-email-216` |
| p2-worker-envelope-invalid | `finding.fix.worker-envelope-invalid` | kaispan `2026-08-04-ocr-ai-worker-lane-split` |
| p2-reviewer-unavailable | `attempt.review.reviewer-unavailable` | supplyer `260719-rechnung-email-216` |
| p3-integration-evidence-unavailable | `attempt.verify.integration-evidence-unavailable` | supplyer `order-create-release-consistency` |
| p1-integration-carrier-unavailable | `attempt.readiness.integration-carrier-unavailable` | kaispan `2026-07-22-kassel-pdf-to-extf-poc` |
| p3-comparison-head-unfixed | `attempt.review.comparison-head-unfixed` | kaispan `2026-07-14-datev-format-validator-spike` |
| p1-worker-still-running | `attempt.readiness.worker-still-running` | kaispan `2026-08-04-ocr-ai-worker-lane-split` |
| p1-all-edges-held | `attempt.readiness.all-edges-held` | kaispan `260803-1332-category-sachkonto-bwa-coverage` |
| p4-acceptance-edge-held | `ticket.accept.acceptance-edge-held` | supplyer `order-create-release-consistency` |
| p3-contradictory-unresolved | `ticket.verify.contradictory-unresolved` | supplyer `260719-rechnung-email-216` |
| p4-satisfiable | `ticket.accept.satisfiable` | kaispan `260803-1332-category-sachkonto-bwa-coverage` |
| p4-release-edge-unchecked | `ticket.accept.release-edge-unchecked` | supplyer `order-create-release-consistency` |
| p4-comparison-mismatch | `attempt.gate.comparison-mismatch` | supplyer `order-create-release-consistency` |

## 未覆盖

达到本轮 25 个上限后，仍未独立构造以下 30 行：

- P1：`attempt.readiness.multiple-ready-tickets`、`ticket.readiness.blocker-maybe-resolved`。选定 legacy 包没有足够清楚的多 readyTicket 或 blocker 已解除时间点。
- P2：`ticket.investigate.no-carrier`、`ticket.investigate.evidence-gap`、`ticket.implement.worker-incomplete-first`、`ticket.implement.worker-incomplete-second`、`ticket.implement.worker-blocked`、`finding.fix.reviewer-returned`、`ticket.review.awaiting-reviewer`、`ticket.review.required-trigger`、`finding.review.source-recheck-pending`、`finding.fix.main-session-discovered`。这些行依赖更细的 dispatch/review outcome 轨迹；本轮先保留新增行和 P0。
- P3：`ticket.verify.safety-invariant-unfalsified`、`ticket.rework.evidence-conflict`、`ticket.rework.revision-diverged`、`ticket.rework.revalidation-pending`、`ticket.disposition.retire-undecided`、`ticket.route.multiple-business-outcomes`、`ticket.route.sources-conflicting`、`ticket.route.sources-uniquely-decide`、`attempt.rework.contract-changed`。legacy 素材虽有 finding 和 revision 变化，但不足以在不猜实现字段的前提下隔离这些处境。
- P4：`attempt.accept.all-tickets-terminal`、`attempt.verify.manual-result-missing`、`attempt.accept.completion-claim-unaudited`、`attempt.review.terminal-coverage-incomplete`、`finding.disposition.grading-undecided`、`attempt.disposition.findings-triage-pending`、`attempt.gate.durable-delta-missing`、`attempt.gate.verdict-undecided`。优先级较低，且容易与 Gate/terminal 场景重叠。
- P5：`package.record.intake-backlog`。允许读取的 legacy 包没有可核对的 intake 队列事实。

## 置信度提示

`confidence=low`：`p0-anchor-mismatch`。

`confidence=medium`：`p0-projection-drift`、`p0-handoff-recovery-needed`、`p0-handoff-target-corrected`、`p0-checkpoint-missing`、`p0-checkpoint-refresh`、`p0-handoff-in-flight`、`p0-judgment-unfiled`、`p3-integration-evidence-unavailable`、`p1-integration-carrier-unavailable`、`p4-release-edge-unchecked`。

这些犹豫都已写在各自 `expected.json.note` 中；主要问题是人读表没有公开 active checkpoint、handoff 和 projection drift 的机械字段形状，或 legacy 没有 trail 只能按真实时间线补写。
