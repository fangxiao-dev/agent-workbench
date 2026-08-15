# Independent 复验 B：situations fixture 比对报告

复验日期：2026-08-15。范围：`tests/fixtures/situations-independent/` 下 25 个 fixture。

执行命令（逐个运行）：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py render --package <fixture> --json
```

25/25 次命令返回码均为 0。`primary` 取 `selected.slug`；`layer` 取 `highest_match_layer`；`secondary` 只取 `other_matches`。`must_not_hit` 按当前测试合同只检查 active visible（primary + secondary），不把 `suppressed_matches` 算作违反。

## 1. 逐个结果

| Fixture | 场景（一句话） | 期望 primary | 实际 primary | 期望层 | 实际层 | `must_not_hit` 违反 | 实际 secondary（合理性） | 结果 |
|---|---|---|---|---:|---:|---|---|---|
| `p0-anchor-mismatch` | handoff 的恢复锚点与 active checkpoint 锚点不一致，校验失败。 | `attempt.record.anchor-mismatch` | `package.record.state-missing` | P0 | P0 | 否 | `attempt.record.anchor-mismatch`；合理的同层 secondary | 不一致 |
| `p0-checkpoint-missing` | 需要跨 session/长任务恢复，但没有 active checkpoint。 | `attempt.record.checkpoint-missing` | `package.record.state-missing` | P0 | P0 | 否 | 无；目标行因机械前提未知而未 active | 不一致 |
| `p0-checkpoint-refresh` | 已有 checkpoint，但下一动作已经从 TKT-01 改为 TKT-02。 | `attempt.record.checkpoint-refresh` | `package.record.state-missing` | P0 | P0 | 否 | 无；active checkpoint 前提未被 parser 接受 | 不一致 |
| `p0-evidence-unfiled` | worker 已返回可用 evidence，但 current `evidenceIndex` 没有对应 claim 行。 | `ticket.record.evidence-unfiled` | `package.record.state-missing` | P0 | P0 | 是：`package.record.state-missing` | 无；state-missing 已成为 primary | 不一致 |
| `p0-handoff-in-flight` | handoff relay 正在发送或等待 continuation，不能另起推进线。 | `attempt.record.handoff-in-flight` | `package.record.state-missing` | P0 | P0 | 否 | `attempt.record.handoff-in-flight`；合理的同层 secondary | 不一致 |
| `p0-handoff-recovery-needed` | handoff bootstrap/create 失败，只能进行一次受控 recovery retry。 | `attempt.record.handoff-recovery-needed` | `package.record.state-missing` | P0 | P0 | 否 | `attempt.record.handoff-recovery-needed`；合理的同层 secondary | 不一致 |
| `p0-handoff-target-corrected` | handoff target/order 已纠正，准备重发 continuation。 | `attempt.record.handoff-target-corrected` | `package.record.state-missing` | P0 | P0 | 否 | `attempt.record.handoff-target-corrected`；合理的同层 secondary | 不一致 |
| `p0-judgment-unfiled` | implementation routing judgment 已形成，但没有写入 current record。 | `ticket.record.judgment-unfiled` | `package.record.state-missing` | P0 | P0 | 否 | `ticket.record.judgment-unfiled`；合理的同层 secondary | 不一致 |
| `p0-projection-drift` | Ticket projection 已 SATISFIED，而 current state 仍是 PENDING。 | `package.record.projection-drift` | `package.record.state-missing` | P0 | P0 | 是：`package.record.state-missing` | 无；projection 行没有 active 命中 | 不一致 |
| `p0-session-resumed` | 新 session 刚接手，已有 active checkpoint 但当前 session 尚无动作。 | `attempt.record.session-resumed` | `package.record.state-missing` | P0 | P0 | 否 | 无；目标行因 state/trail 前提未知 | 不一致 |
| `p0-state-missing` | 只有 legacy sidecar，没有迁移后的 `state.json`。 | `package.record.state-missing` | `package.record.state-missing` | P0 | P0 | 否 | 无；合理 | 一致 |
| `p0-terminal-frozen` | 已写入 terminal pass Gate，却仍请求推进同一 attempt。 | `attempt.gate.terminal-frozen` | `attempt.gate.terminal-frozen` | P0 | P0 | 是：`package.record.state-missing` | `package.record.state-missing`；违反 forbidden secondary | 不一致 |
| `p1-all-edges-held` | 后续 Ticket 依赖的前置 Ticket 仍 PENDING，没有 readyTicket。 | `attempt.readiness.all-edges-held` | `package.record.state-missing` | P1 | P0 | 否 | 无；P1 前提因 state invalid 未知 | 不一致 |
| `p1-integration-carrier-unavailable` | 没有可用的预置 integration carrier，需先取得环境能力。 | `attempt.readiness.integration-carrier-unavailable` | `package.record.state-missing` | P1 | P0 | 否 | 无；目标 P1 被 P0 state-missing suppress | 不一致 |
| `p1-worker-still-running` | 已派出 worker 但尚未返回，主控应等待结果。 | `attempt.readiness.worker-still-running` | `package.record.state-missing` | P1 | P0 | 否 | 无；`dispatch/RUNNING` 写法未被 decision parser 识别 | 不一致 |
| `p2-closure-awaiting` | fixer 已完成，但 finding 仍等待同 scope 的 closure reviewer。 | `finding.review.closure-awaiting` | `package.record.state-missing` | P2 | P0 | 否 | 无；`F-001` 未解析为结构化 finding | 不一致 |
| `p2-reviewer-unavailable` | 旧 review run timeout/envelope 无效，必须重开 fresh review。 | `attempt.review.reviewer-unavailable` | `package.record.state-missing` | P2 | P0 | 否 | 无；目标 P2 被 P0 state-missing suppress | 不一致 |
| `p2-worker-envelope-invalid` | finding fixer 返回缺少 evidence/revision 的无效 envelope。 | `finding.fix.worker-envelope-invalid` | `package.record.state-missing` | P2 | P0 | 否 | 无；finding subject 未解析，envelope fact 未 active | 不一致 |
| `p3-comparison-head-unfixed` | review 只记录浮动 HEAD，没有 immutable comparison head。 | `attempt.review.comparison-head-unfixed` | `package.record.state-missing` | P3 | P0 | 否 | 无；目标 P3 被 P0 state-missing suppress | 不一致 |
| `p3-contradictory-unresolved` | 同一 claim 同时有 supporting 与未处置的 contradictory evidence。 | `ticket.verify.contradictory-unresolved` | `package.record.state-missing` | P3 | P0 | 否 | 无；evidence state 未通过 schema 校验 | 不一致 |
| `p3-integration-evidence-unavailable` | 本地证据完成，但 Gate 所需的真实 integration read-back 不可取得。 | `attempt.verify.integration-evidence-unavailable` | `package.record.state-missing` | P3 | P0 | 否 | 无；目标 P3 被 P0 state-missing suppress | 不一致 |
| `p4-acceptance-edge-held` | supporting evidence 已有，但 PENDING reviewer Ticket 仍挡住 acceptance edge。 | `ticket.accept.acceptance-edge-held` | `package.record.state-missing` | P4 | P0 | 否 | 无；acceptance facts 因 state invalid 未知 | 不一致 |
| `p4-comparison-mismatch` | acceptance revision 与 Gate pass 的 comparison commit 不一致。 | `attempt.gate.comparison-mismatch` | `attempt.gate.terminal-frozen` | P4 | P0 | 是：`attempt.gate.terminal-frozen` | `package.record.state-missing`；次级本身可解释，但 primary 已被 terminal Gate 抢占 | 不一致 |
| `p4-release-edge-unchecked` | Ticket acceptance 看似满足，但 Gate 前 release edge 仍未复核。 | `ticket.accept.release-edge-unchecked` | `package.record.state-missing` | P4 | P0 | 否 | 无；release recheck 没有可判定机械输入 | 不一致 |
| `p4-satisfiable` | 全部 required claims 有支撑、revision/environment 明确且入边已释放。 | `ticket.accept.satisfiable` | `package.record.state-missing` | P4 | P0 | 否 | 无；acceptance facts 因 state invalid 未知 | 不一致 |

## 2. 汇总

- 总数：25。
- 一致：1（4.0%）。
- 不一致：24（96.0%）。
- `must_not_hit` 违反：4 个 fixture，分别为 `p0-evidence-unfiled`、`p0-projection-drift`、`p0-terminal-frozen`、`p4-comparison-mismatch`；按本报告口径也是 4 个 active 误报。
- 命令失败：0。
- 实际 primary 与期望完全相同：2/25；实际层与期望相同：12/25。
- 24 个有 `state.json` 的 fixture 都把 `attempt` 写成了 `id + plan + lifecycle`。实现的 state parser 要求 `attempt` 只能含 `id` 与 `plan`，所以 24 个输入都会得到 `package.state_invalid=true`；其中 22 个因此选中 `package.record.state-missing`，另外 2 个把它作为 secondary 命中。

这个共同原因不是 suppressed 误报：`state-missing` 在这些输出中是 active primary 或 active secondary。相反，P3 目标行出现在 `suppressed_matches` 时不计 `must_not_hit` 违反。

## 3. 每条不一致的归因

下列归因只针对该 fixture 的期望与实际不一致；没有修改 fixture、expected、situations 表或 renderer。

1. **`p0-anchor-mismatch` — 表述不清。** expected note 已承认 active checkpoint 的 anchor 字段形状未定义；trail 的 mismatch 语义其实被识别，只是额外的 `lifecycle` 让 state-missing 抢走 primary。
2. **`p0-checkpoint-missing` — 表述不清。** 人读描述说“长任务/跨 session”，但没有给出实现所需的 `attempt.handoff_or_long_task` 机械信号；active checkpoint 又因 state 形状无效而不可判定。
3. **`p0-checkpoint-refresh` — 表述不清。** trail 明确写了 next changed，但规则还要求 active checkpoint 存在，表述没有规定这个前提应如何编码。
4. **`p0-evidence-unfiled` — 推导器错。** fixture 的 `worker-return + EVIDENCE_SUFFICIENT + evidence` 已直接表达“worker 返回证据”，但 `direct_evidence_returned` 实现只从 `kind=result` 读取；即使把 state schema 单独修正，该自然表示仍不会命中。
5. **`p0-handoff-in-flight` — 表述不清。** 人读表没有规定 in-flight 必须落在 state、checkpoint 还是 trail；trail marker 能命中，但未定义的 state 形状改变了优先级。
6. **`p0-handoff-recovery-needed` — 表述不清。** recovery failure/retry 的语义清楚，但 handoff failure 的机械载体未指定，因此 state 与 trail 两种读法都成立。
7. **`p0-handoff-target-corrected` — 表述不清。** target/order 已纠正的文字明确，但没有规定 parser 应从 checkpoint 还是 trail 取该事实；trail 命中而 state-missing 抢占说明边界未封闭。
8. **`p0-judgment-unfiled` — 表述不清。** judgment 已形成的语义被 trail 识别，但“current record”及其固定字段没有定义，无法保证 state 合法且只产生该行。
9. **`p0-projection-drift` — 表述不清。** 描述没有提供 `package.validate.projection_drift` 所需的 authoritative projection 输入；用 Ticket 文档与 state 内嵌状态替代 progress/validate 结果，两种解释都说得通。
10. **`p0-session-resumed` — 期望造错。** 该条的语义边界本身清楚，但 fixture 明知要表达 active state，却给 `attempt` 添加了 schema 不允许的 `lifecycle`，使 expected 同时违反了实际的 state-missing 前提。
11. **`p0-terminal-frozen` — 期望造错。** Gate/terminal 语义命中正确，但 fixture 的非法 `lifecycle` 额外制造了 expected 明确禁止的 `package.record.state-missing` secondary。
12. **`p1-all-edges-held` — 期望造错。** Ticket dependency 的内容足以表达 all edges held，但外层 state 先因 `lifecycle` 非法而失效，expected 没有满足自己依赖的合法 current state。
13. **`p1-integration-carrier-unavailable` — 表述不清。** expected note 已承认 carrier 与 evidence 的边界是人为拆分；trail 能识别 carrier unavailable，但没有规则说明两者的优先和承载方式。
14. **`p1-worker-still-running` — 推导器错。** `kind=dispatch、outcome=RUNNING、returned=false` 对人已经明确表示 worker 未返回，但实现只寻找带标识符的 `kind=decision` 且缺少对应 `kind=result` 的悬空决策，未把该等价语义纳入判据。
15. **`p2-closure-awaiting` — 期望造错。** `execution-findings.md` 使用 `F-001`，而 parser 的 finding ID 规则只接受 `FND-*`、`FIND-*` 或 `FINDING-*`；结果是 count=0，expected 所依赖的结构化 finding 根本未被 fixture 建立。
16. **`p2-reviewer-unavailable` — 期望造错。** trail 的 timeout/invalid envelope/old run 信号已被实现识别为 reviewer-unavailable，但非法 state 仍把该 P2 行压在 P0 state-missing 之后。
17. **`p2-worker-envelope-invalid` — 期望造错。** 该 finding 也使用未被 parser 识别的 `F-001` subject，导致 `finding:*` 无法消费 trail；expected note 虽然写得明确，fixture 的结构化 finding 载体并未成立。
18. **`p3-comparison-head-unfixed` — 期望造错。** `comparisonHead=HEAD、immutable=false` 已被实现识别，目标 P3 行只是被非法 state 产生的 P0 state-missing suppress。
19. **`p3-contradictory-unresolved` — 期望造错。** evidence records 使用 `timing=completion`，而 state validator 允许的是 `early-falsification` 或 `remaining-completion`，同时还有非法 `lifecycle`；因此 expected 的 contradictory evidence 没有形成可消费的合法 state。
20. **`p3-integration-evidence-unavailable` — 表述不清。** expected note 明确承认“evidence carrier”与“integration carrier”是本轮人为拆分；trail 语义可识别，但表述不足以裁决应落 P1 还是 P3。
21. **`p4-acceptance-edge-held` — 期望造错。** supporting evidence 和 dependency 文本虽已写出，但 state 同时含非法 `lifecycle`，其 evidence timing 也不是当前 schema 的合法值，expected 的 acceptance facts 未真正建立。
22. **`p4-comparison-mismatch` — 期望造错。** fixture 明确写了 `Gate Verdict: pass`；实现把 pass 视为 terminal，且 P0 `terminal-frozen` 位于 P4 mismatch 之前，expected 又把 terminal-frozen 列入 `must_not_hit`，这是与优先级直接冲突的期望。
23. **`p4-release-edge-unchecked` — 表述不清。** 描述说 release check PENDING，但没有给出 `ticket.release_edge_rechecked=false` 的显式字段或可解析 trail；checkpoint blocker 与依赖 Ticket 不能唯一裁决该 when。
24. **`p4-satisfiable` — 期望造错。** 两个 claim 的语义有写出，但 state 的 `lifecycle` 和 evidence 的 `timing=completion` 都不符合当前 state schema，故 expected 的“可 satisfy”输入并未构成。

归因计数：推导器错 2 条，表述不清 11 条，期望造错 11 条。没有把所有差异归给同一类。

## 4. 置信度与一致性的相关性

| A confidence | 总数 | 一致 | 不一致 | 不一致率 |
|---|---:|---:|---:|---:|
| high | 14 | 1 | 13 | 92.9% |
| medium | 10 | 0 | 10 | 100% |
| low | 1 | 0 | 1 | 100% |
| medium + low | 11 | 0 | 11 | 100% |

high 置信度并非“都一致”：唯一一致的是故意没有 `state.json` 的 `p0-state-missing`。medium/low 的不一致率更高，且 11 条全部被归为“表述不清”，说明这些行需要先补足机械载体、边界和前置条件。与此同时，high 也有 13/14 不一致，说明问题不只在低置信度措辞，fixture/state/trail 合同和优先级也必须单独收紧。

## 5. 结论

当前不能进入接线阶段。25 条中只有 1 条一致，且有 4 个 active `must_not_hit` 误报；如果现在接线，主控会被大量引向 `package.record.state-missing`，并在 `p4-comparison-mismatch` 上被错误引向 `terminal-frozen`。

接线前必须先完成以下事项：

1. 明确并修正独立 fixture 的 state 合同：合法 `attempt` 是否只能有 `id/plan`；若是，24 个 fixture 必须重新构造，且不能再让非法 state 参与处境比较。
2. 固化 trail/finding/evidence 的输入合同，至少明确 `decision/result`、worker 未返回、direct evidence、finding ID 和 evidence timing；随后决定是扩展 parser 兼容自然写法，还是要求 fixture 严格按合同表达。
3. 为 projection drift、checkpoint/long-task、carrier-vs-evidence、release-edge recheck 补出唯一机械判据，消除 medium/low 行的歧义。
4. 单独处理 `Gate pass` 与 `terminal-frozen` 的优先关系，并重新定义 `p4-comparison-mismatch` 的期望边界。
5. 在上述合同/规则收紧后重新运行完整 25 条 independent 比对；本报告的 1/25 结果不能作为接线验收依据。
