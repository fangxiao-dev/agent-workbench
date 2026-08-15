# B2 独立复验报告：A2 的 25 个 fixture

复验日期：2026-08-15。

## 1. 执行与判定口径

对 `tests/fixtures/situations-a2/` 下的 25 个目录逐个执行：

```text
python plugin-marketplace/plugins/impl-package/scripts/situation.py render --package <fixture> --json
```

25/25 次命令返回码均为 0，且 stdout 都能解析为 JSON。

本报告的比较口径是：

- `primary`：有 `selected` 时取 `selected.slug`；没有 `selected` 时取 `parallel_matches[*].slug`，并按集合比较，因此同层并列 primary 的顺序不影响一致性。
- `layer`：取 `highest_match_layer`。
- `secondary`：取 `other_matches[*].slug`。A2 的 25 个 `expected.json` 都没有 `expected_secondary` 字段，所以这里不把缺省的 `[]` 当作冻结的二级期望，而是核对每个 secondary 是否由当前输入事实和优先级合理推出。
- `must_not_hit`：只检查 active primary（含并列 primary）与 `other_matches`；`suppressed_matches` 和 `undetermined` 不算 active 违反。这与 `tests/test_situation_render.py` 的合同一致。

## 2. 逐个结果

| fixture | 场景一句话 | 期望 primary | 实际 primary | 期望层 | 实际层 | 实际 secondary（是否合理） | `must_not_hit` 是否违反 | 一致与否 |
|---|---|---|---|---:|---:|---|---|---|
| `p0-anchor-mismatch` | 跨记录锚点不一致，恢复校验应 fail-closed。 | `attempt.record.anchor-mismatch` | `attempt.record.anchor-mismatch` | P0 | P0 | — | 否 | 是 |
| `p0-checkpoint-missing` | 需要跨 session 收口但没有 active checkpoint。 | `attempt.record.checkpoint-missing` | `attempt.record.checkpoint-missing` | P0 | P0 | — | 否 | 是 |
| `p0-checkpoint-refresh` | 下一动作变化，已有 checkpoint 需要刷新。 | `attempt.record.checkpoint-refresh` | `attempt.record.checkpoint-refresh` | P0 | P0 | — | 否 | 是 |
| `p0-evidence-unfiled` | 已返回直接证据，但尚未进入 evidenceIndex。 | `ticket.record.evidence-unfiled` | `ticket.record.evidence-unfiled` | P0 | P0 | — | 否 | 是 |
| `p0-handoff-in-flight` | handoff/continuation 正在等待返回。 | `attempt.record.handoff-in-flight` | `attempt.record.handoff-in-flight` | P0 | P0 | — | 否 | 是 |
| `p0-handoff-recovery-needed` | handoff bootstrap 失败，需要一次受控恢复。 | `attempt.record.handoff-recovery-needed` | `attempt.record.handoff-recovery-needed` | P0 | P0 | — | 否 | 是 |
| `p0-handoff-target-corrected` | handoff target/order 已修正，需要重发。 | `attempt.record.handoff-target-corrected` | `attempt.record.handoff-target-corrected` | P0 | P0 | — | 否 | 是 |
| `p0-judgment-unfiled` | 执行判断已形成但尚未写入 recovery judgment 记录。 | `ticket.record.judgment-unfiled` | `ticket.record.judgment-unfiled` | P0 | P0 | — | 否 | 是 |
| `p0-projection-drift` | authoritative state 与 projection 不一致，需要重新生成。 | `package.record.projection-drift` | `package.record.projection-drift` | P0 | P0 | — | 否 | 是 |
| `p0-session-resumed` | 新 session 有 active checkpoint，当前 session 尚无动作。 | `attempt.record.session-resumed` | `ticket.investigate.no-carrier` | P0 | P2 | `attempt.gate.verdict-undecided`（合理：缺 Gate 的默认 verdict） | 否 | 否 |
| `p0-state-invalid` | legacy 3.4 state 不能作为当前 3.5 package admission。 | `package.record.state-missing` | `package.record.state-missing` | P0 | P0 | — | 否 | 是 |
| `p0-terminal-frozen` | 已有 pass Gate，却仍请求推进同一 attempt。 | `attempt.gate.terminal-frozen` | `attempt.gate.terminal-frozen` | P0 | P0 | — | 否 | 是 |
| `p1-integration-carrier-unavailable` | 外部 integration carrier 暂不可用。 | `attempt.readiness.integration-carrier-unavailable` | `attempt.readiness.integration-carrier-unavailable` | P1 | P1 | `ticket.investigate.no-carrier`、`attempt.gate.verdict-undecided`（合理：分别由 PENDING/no-investigate/无 evidence 与缺 Gate 导出） | 否 | 是 |
| `p1-worker-still-running` | worker 已派出但当前 attempt 尚未收到返回。 | `attempt.readiness.worker-still-running` | `attempt.readiness.worker-still-running` | P1 | P1 | `ticket.investigate.no-carrier`、`attempt.gate.verdict-undecided`（合理的低层并行事实） | 否 | 是 |
| `p2-closure-awaiting` | finding fix 已完成，等待同 scope closure reviewer。 | `finding.review.closure-awaiting` | `finding.review.closure-awaiting` | P2 | P2 | `attempt.gate.verdict-undecided`（合理） | 否 | 是 |
| `p2-reviewer-unavailable` | reviewer timeout/旧 ReviewRun 不可采信，需要 fresh review。 | `attempt.review.reviewer-unavailable` | `attempt.review.reviewer-unavailable` | P2 | P2 | `attempt.gate.verdict-undecided`（合理） | 否 | 是 |
| `p2-worker-envelope-invalid` | fixer 返回的 envelope 不完整，结果不能直接采信。 | `finding.fix.worker-envelope-invalid` | `finding.fix.worker-envelope-invalid` | P2 | P2 | `attempt.gate.verdict-undecided`（合理） | 否 | 是 |
| `p3-comparison-head-unfixed` | review 尚未固定可信 immutable comparison head。 | `attempt.review.comparison-head-unfixed` | `ticket.investigate.no-carrier` | P3 | P2 | `attempt.review.comparison-head-unfixed`、`attempt.gate.verdict-undecided`（目标 row 合理命中但落为 secondary；P2 no-carrier 抢先） | 否 | 否 |
| `p3-integration-evidence-unavailable` | protected integration evidence 载体暂不可取得。 | `attempt.verify.integration-evidence-unavailable` | `ticket.investigate.no-carrier` | P3 | P2 | `attempt.verify.integration-evidence-unavailable`、`attempt.gate.verdict-undecided`（目标 row 合理命中但落为 secondary） | 否 | 否 |
| `p3-revalidation-pending` | 既有结论进入 NEEDS-REVALIDATION，尚未重新满足。 | `ticket.rework.revalidation-pending` | `ticket.rework.revalidation-pending` | P3 | P3 | `attempt.gate.verdict-undecided`（合理） | 否 | 是 |
| `p3-revision-diverged` | SATISFIED acceptance revision 停在旧提交而 HEAD 已推进。 | `ticket.rework.revision-diverged` | `ticket.rework.revision-diverged` | P3 | P3 | `attempt.accept.all-tickets-terminal`、`ticket.accept.satisfiable`、`ticket.accept.release-edge-unchecked`、`attempt.gate.verdict-undecided`（按各自 `when` 均合理，且低于 P3） | 否 | 是 |
| `p4-acceptance-edge-held` | supporting evidence 已有，但前置 Ticket 未释放 acceptance edge。 | `ticket.accept.acceptance-edge-held` | `ticket.accept.acceptance-edge-held`、`attempt.gate.verdict-undecided` | P4 | P4 | `other_matches` 无；`attempt.gate.verdict-undecided` 是同层并列 primary，确实命中 | 否 | 否 |
| `p4-durable-delta-missing` | 无待执行 Ticket，但 terminal Gate 前缺少 Durable Delta。 | `attempt.gate.durable-delta-missing`、`attempt.accept.all-tickets-terminal` | `attempt.accept.all-tickets-terminal`、`attempt.gate.durable-delta-missing` | P4 | P4 | — | 否 | 是（集合一致，顺序不同） |
| `p4-release-edge-unchecked` | acceptance 条件满足，但 Gate 前 release edge 尚未复核。 | `ticket.accept.release-edge-unchecked`、`ticket.accept.satisfiable` | `ticket.accept.satisfiable`、`ticket.accept.release-edge-unchecked` | P4 | P4 | — | 否 | 是（集合一致，顺序不同） |
| `p4-satisfiable` | required claims 有 supporting evidence、入边已释放且 revision 可解析。 | `ticket.accept.satisfiable` | `ticket.accept.satisfiable` | P4 | P4 | — | 否 | 是 |

## 3. 汇总

- 总数：25。
- 一致：21（84.0%）。
- 不一致：4（16.0%）。
- 误报：0；25 个 fixture 都没有 active primary/secondary 命中自己的 `must_not_hit`。
- 命令失败：0。
- 4 个不一致中，目标 row 都没有被错误地“凭空命中”：`p0-session-resumed` 的目标因缺少 checkpoint marker 而是 `undetermined`；两个 P3 目标出现在 secondary；P4 目标出现在同层并列 primary。
- A2 没有冻结 secondary 列表：25/25 个 `expected.json` 都省略 `expected_secondary`。本轮观察到的 secondary 均能由当前输入和公开的 key 语义解释；真正影响一致性的，是 4 条的 primary/layer 选择。

## 4. 每条不一致的归因

### 4.1 `p0-session-resumed`：合同缺口

依据：fixture 的 `.impl-package/state.json` 有 `activeCheckpoints.attempt`，trail 也有 `attempt.session_resumed=true`。但 trail 没有 checkpoint marker。实际 JSON 将目标 row 放进 `undetermined`，原因是 `trail.actions_since_checkpoint` 为 unknown：“active checkpoint 存在，但 trail 中没有可定位的 checkpoint 行”。

当前 `situations.yaml` 的 `attempt.record.session-resumed`（约第 59 行）实际要求三个条件同时成立：`attempt.session_resumed=true`、`attempt.active_checkpoint_present=true`、`trail.actions_since_checkpoint=0`。合同 `situation-inputs.md` §2.1/§4.3（约第 95、133 行）说明了这个 key 和 marker 的读取规则，却没有在逐行 slug 合同中把这组三元组合公开给构造者。构造者只写了 fact 和 checkpoint，无法知道还需要可识别的 checkpoint marker。

这不是已证实的推导器错：在当前 `when` 下，缺 marker 后 fail-closed 为 unknown 是一致行为。若 owner 认为显式 `attempt.session_resumed=true` 应绕过 marker，则那是另一个尚未决策的 when/实现契约，而不是本 fixture 能单独证明的 bug。

### 4.2 `p3-comparison-head-unfixed`：合同缺口

依据：fixture 的 trail 明确写了 `git.comparison_head_fixed=false`，实际 `attempt.review.comparison-head-unfixed` 出现在 `other_matches`；但同一 package 的 Ticket 是 `PENDING`，没有 investigate signal，`evidence.count=0`，所以 P2 的 `ticket.investigate.no-carrier` 也成立并抢到 primary。

当前表中 `ticket.investigate.no-carrier`（约第 143 行）是 `ticket.state=PENDING`、`trail.has_investigate=false`、`evidence.count=0` 的 AND；它位于 P2，而目标 `attempt.review.comparison-head-unfixed`（约第 863 行）位于 P3。合同公开了各 key 的来源，但没有公开完整 slug→when、层级和“为了测试一个 P3 primary 必须怎样让更高优先级 no-carrier 不成立”的组合。目标处境本身已被正确识别，差异来自构造者不知道需要同时补一个 investigate/evidence 抑制条件或接受 P2 抢占。

### 4.3 `p3-integration-evidence-unavailable`：合同缺口

依据：fixture 的 trail 明确写了 `attempt.integration_evidence_available=false`，实际 `attempt.verify.integration-evidence-unavailable` 出现在 `other_matches`；P2 的 `ticket.investigate.no-carrier` 仍因 PENDING、无 investigate、无 evidence 成立并成为 primary。P1 的 carrier row 没有被误命中，因为 fixture 没有提供 `attempt.integration_carrier_available=false`。

这与上一条是同一类实证：目标 row 的 fact 已成立，推导器也识别了它；构造者没有完整的 slug→when/priority 图，因而没有知道还要排除 P2 no-carrier，或没有把这种并存情况写进 expected primary。归因选合同缺口，不是推导器错。

### 4.4 `p4-acceptance-edge-held`：合同缺口

依据：fixture 的 `evidenceIndex` 让 `evidence.count=1`，`TKT-CHILD` 的 acceptance dependency 又使 `ticket.acceptance_edge_released=false`，因此目标 `ticket.accept.acceptance-edge-held` 正确命中。但 fixture 没有 `gate.md`；合同规定缺 Gate 时 `gate.verdict=undecided`，而 `attempt.gate.verdict-undecided` 与目标处于同一个 P4 层，所以 renderer 返回两个并列 primary。

当前表中目标 row（约第 317 行）与 `attempt.gate.verdict-undecided`（约第 608 行）的同层关系、以及缺 Gate 的默认 verdict（`situation-inputs.md` §2.1，约第 131 行）没有在逐行 slug 合同中组合呈现。这里不是 acceptance-edge 语义被误解：目标事实确实成立；是 expected primary 漏掉了一个合法的同层 co-match。因此归因选合同缺口，而不是期望造错。

归因计数：推导器错 0 条；合同缺口 4 条；期望造错 0 条。

## 5. 与上一轮 `reverify-report.md` 对比

上一轮报告记录的是 1/25 一致、24/25 不一致；24 个带 state 的 fixture 都把 `lifecycle` 放进了 `attempt`，触发 `package.record.state-missing`，主要失败原因是拼不出被 parser 接受的合法数据形状。

本轮结果不同：

- 25/25 命令返回 0，24 个非故意 invalid 的 fixture 的 `sources.state.valid=true`；`p0-state-invalid` 是唯一故意构造的 invalid state，且按期望命中 `package.record.state-missing`。
- `p0-evidence-unfiled`、`p1-worker-still-running`、两个 P2 finding fixture、P3/P4 acceptance fixture 都能被 parser 消费到对应的结构化事实；没有上一轮那种全局 state-invalid 抢占。
- 因此，上一轮的“合法 JSON/state/Ticket/trail/finding 形状”类失败已经消失。合同和已实现的 canonical 输入入口解决了字段形状问题。
- 剩余 4 条不是 malformed state、未知 finding ID、worker event kind 不兼容或 JSON 解析失败，而是判据组合、优先级隔离和同层并列 primary 的语义/映射问题。换句话说，形状问题解决后，失败从“parser 不认识输入”转成“构造者不知道怎样让目标 slug 成为唯一/最高 primary”。

## 6. `slug → when` 映射缺口的实证

结论是：4/4 个不一致 fixture（100%）都能由“未公开完整 slug→when 组合”直接解释；这验证了 A2 自评的核心缺口。

1. `p0-session-resumed`：构造者提供了 `attempt.session_resumed` 和 active checkpoint，却不知道还必须让 `trail.actions_since_checkpoint=0` 可判定；证据是实际目标进入 `undetermined`，unknown reason 明确指出缺 checkpoint marker。
2. `p3-comparison-head-unfixed`：构造者知道目标只需 `git.comparison_head_fixed=false`，不知道同一输入还满足 P2 `ticket.investigate.no-carrier` 的三个 AND 条件；证据是目标落 `other_matches`、P2 no-carrier 成为 primary。
3. `p3-integration-evidence-unavailable`：构造者知道目标需 `attempt.integration_evidence_available=false`，不知道仍未排除 P2 no-carrier；证据与上一条相同，目标在 secondary、P2 在 primary。
4. `p4-acceptance-edge-held`：构造者知道 evidence 与 acceptance edge 的组合，却不知道缺 Gate 会产生同层 `attempt.gate.verdict-undecided`；证据是两个 slug 同时出现在 P4 `parallel_matches`。

所以这里的“缺口”不只是目标 row 的单个 key 没写，而是没有公开：

- 一个 slug 的全部 AND 条件；
- 为了让它成为 primary 所需排除的更高层 when；
- 同层多个 when 同时成立时，expected primary 应列出并列集合还是由 fixture 额外隔离；
- secondary 与 suppressed/undetermined 的边界。

## 7. 结论与接线前置项

当前不能接线。虽然字段形状已经足以让 25 个 fixture 被稳定解析，且没有 `must_not_hit` 误报，但 4/25 的主控入口仍会落到错误层级、变成 unknown，或漏掉同层并列 primary；这足以把主控引向错误处境。

必须先补的内容分两类：

### 补文档/合同（必须）

1. 发布 55 行完整的 `slug → when` 映射，包含每个条件的 subject/scope、AND 组合、unknown 规则、priority layer 和同层并列语义。
2. 给出 P0/P3/P4 这类“目标 row 的最小输入 + 排除更高层/并列 row 的隔离输入”示例，至少覆盖 checkpoint marker、no-carrier、Gate 默认 undecided。
3. 明确 `attempt.session_resumed` 的直接 fact 与 `trail.actions_since_checkpoint=0` 是当前实现中的 AND，还是 direct fact 应短路；文档不能同时表达“fact 优先”和“row 仍需 marker”而不说明边界。
4. 明确 `expected_primary` 是否按集合接受并列 primary，并为 secondary 提供冻结字段或明确“只做语义合理性检查”的合同。

### 改实现（当前证据不要求）

本轮没有确认需要修改 `situation.py` 或 `situations.yaml`：推导器正确识别了 4 个目标事实，并按当前表的 when/priority 做了 fail-closed、P2 抢占和 P4 并列。只有 owner 先决定改变上述语义（例如让显式 session-resumed fact 绕过 marker，或不把缺 Gate 的 undecided row 纳入 P4 并列）后，才应据该决定改实现/表，并重新跑完整 25 条。

完成合同补齐或语义决定后，必须重新运行全部 25 个 fixture；在复验达到 25/25 一致前，不应把当前结果作为接线验收依据。
