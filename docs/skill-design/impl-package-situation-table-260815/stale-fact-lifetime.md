# stale fact lifetime 调查与决策记录

状态：阶段 1（影响面调查）已落盘；阶段 2、阶段 3 尚未开始。

本阶段只读了当前工作树、现有 fixture 和外部真实 package，没有修改代码，也没有修改外部 package。有效 fact 名称是 `situation.py` 中的 29 个 canonical key（`FACT_KEYS`，约第 58–90 行）加上仍被兼容读取的 `ticket.judgment_unfiled` alias（约第 91 行），所以按用户口径列出 30 个接受名称；alias 最终归一到 `trail.judgment_unfiled`，不产生第 31 个语义。

## 1. 证据基线

- 真实 package：`D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning\docs\domains\finance-assistant\implementations\2026-08-15-datev-tax-advisor-import-workbench`。
- 用户给出的比较边界是 66 条可消费轨迹事件、8 条 `kind=fact`；取证期间外部 writer 又追加了 3 条未知 fact 行（物理文件曾观察到 69 行，之后继续增长），所以物理行数与用户口径可能不同。那 3 行是当前闭集之外的 key（`handoff_recovery_needed`、`b01.run_owned_database_prepared`、`b01.cleanup_verified`），被 renderer 警告并忽略；本报告不把外部追加归因于本次任务。
- 真实 package renderer 当前 `head` 是 `a1e55a569807d25fff351da858b1189aaaeac795`。`trail.handoff_target_corrected=true` 的 fact 在 `head=039c611adf304ab090a109702c84453819b476ee` 写入；它确实是旧 head 上的事实。
- 真实 package 当前有 5 个 Ticket context（TAW-01…TAW-05）和一个 finding 通配 context；renderer 报告 47 行无法判定。
- 现有 fixture 基线：`python -m pytest tests/test_situation_render.py -q` → `54 passed`（pytest 仅报告既有 `.pytest_cache` 权限 warning）。现有 fact fixture 的事实行没有 `head` 字段。

真实 package 改动前的人类渲染原始输出是：

```text
处境: attempt.record.handoff-target-corrected  (attempt)
可选: a) resend-corrected-handoff  b) cancel-corrected-handoff
判断点: 机械条件命中，优先执行默认动作
需要主控自行判断是否进入: ticket.route.multiple-business-outcomes, ticket.route.sources-conflicting
无法判定 47 行: attempt.record.anchor-mismatch (attempt), attempt.record.handoff-recovery-needed (attempt), attempt.record.checkpoint-missing (attempt), attempt.record.handoff-in-flight (attempt) …
读取提示: 1 条（JSON 模式含详情）
digest: 16d111744916
```

## 2. 30 个 fact key 的消费映射与生命周期分类

消费映射按 `references/situation-inputs.md` 的输入表和逐行合同读取；P0 顺序按 `situations.yaml` 的 priority（约第 13–26 行）读取。`无当前处境行` 表示该 key 仍在闭集/parser 中，但当前 `situations.yaml` 没有消费它。

| # | fact key（含兼容 alias） | 当前消费的处境行 | P0 | 分类 | 理由 |
|---:|---|---|:---:|---|---|
| 1 | `package.validate.projection_drift` | `package.record.projection-drift` | 是 | 持续状态 | projection 与 state 漂移在刷新前持续存在，须显式变为 false 才解除。 |
| 2 | `attempt.session_resumed` | `attempt.record.session-resumed`（兼容 parser 名） | 是 | 一次性事件 | “跨 session 已接手”是一次边界事件；恢复动作完成后不应继续作为当前动作依据。当前实现已经不读取该声明，实际 row 由 active checkpoint 与 checkpoint 后动作数决定。 |
| 3 | `attempt.in_flight` | `attempt.readiness.multiple-ready-tickets` | 否 | 持续状态 | open dispatch/worker 是否仍在运行是当前 liveness，直到 result 或显式 false 才改变。 |
| 4 | `attempt.handoff_or_long_task` | `attempt.record.checkpoint-missing` | 是 | 持续状态 | 当前动作只要仍是 handoff/long task 就仍需要 checkpoint，完成或重新分类后才解除。 |
| 5 | `attempt.integration_carrier_available` | `attempt.readiness.integration-carrier-unavailable` | 否 | 持续状态 | carrier 可用性是当前环境状态，不能因时间流逝自动认为恢复。 |
| 6 | `attempt.integration_evidence_available` | `attempt.verify.integration-evidence-unavailable` | 否 | 持续状态 | integration evidence 的可用性持续到载体补齐或显式撤销。 |
| 7 | `attempt.manual_verification_owner` | `attempt.verify.manual-result-missing` | 否 | 持续状态 | owner 是否存在是当前人工验证安排，直到 owner 被替换/撤销才改变。 |
| 8 | `attempt.manual_verification_result_present` | `attempt.verify.manual-result-missing` | 否 | 持续状态 | 结果是否已经登记是当前证据状态，不能自动过期。 |
| 9 | `attempt.completion_claim_pending` | `attempt.accept.completion-claim-unaudited`、`attempt.gate.comparison-mismatch` | 否 | 持续状态 | completion claim 在审计完成前仍 pending；第二个 row 也把它作为写 Gate 前置条件。 |
| 10 | `attempt.terminal_coverage_complete` | `attempt.review.terminal-coverage-incomplete` | 否 | 持续状态 | coverage 是否完整是当前收口状态，直到补齐/重判才变更。 |
| 11 | `ticket.blocker_maybe_resolved` | `ticket.readiness.blocker-maybe-resolved` | 否 | 一次性事件 | “可能已解除”是触发一次重新评估的信号；评估完成后旧 true 不应反复投递同一动作。 |
| 12 | `ticket.no_longer_needed` | `ticket.disposition.retire-undecided` | 否 | 持续状态 | “不再需要”是当前处置判断，在 Ticket 退休或判断被改写前持续有效。 |
| 13 | `ticket.release_edge_rechecked` | `ticket.accept.release-edge-unchecked` | 否 | 一次性事件 | recheck 是针对某个当前边界/版本完成的动作，新的 head/依赖变化后旧完成事件不能继续代表当前 recheck。 |
| 14 | `ticket.review_required` | `ticket.review.awaiting-reviewer` | 否 | 持续状态 | reviewer requirement 是当前流程要求，直到显式取消或完成 review 才改变。 |
| 15 | `ticket.review_trigger` | `ticket.review.required-trigger` | 否 | 一次性事件 | trigger 是派发/进入 review 的一次性触发器，处理后应失效，避免重复派发。 |
| 16 | `ticket.post_fix_regression_pending` | 无当前处境行（闭集/parser 保留） | 否 | 持续状态 | regression 是否 pending 是当前验证缺口，直到回归检查完成才解除；当前 YAML 尚未消费它。 |
| 17 | `evidence.sources_uniquely_decide` | `ticket.route.sources-uniquely-decide` | 否 | 持续状态 | “当前证据足以唯一裁决”随证据集变化，未改变前仍是当前判断。 |
| 18 | `git.comparison_head_fixed` | `attempt.review.comparison-head-unfixed` | 否 | 一次性事件 | fixed 是针对某个比较点完成的动作；Git head 变化后旧 fixed 不能代表新的 comparison head。 |
| 19 | `trail.anchor_mismatch` | `attempt.record.anchor-mismatch` | 是 | 持续状态 | mismatch 是当前轨迹完整性问题，直到对齐/修复并显式 false 才解除。 |
| 20 | `trail.bookkeeper_partial_write` | 无当前处境行（闭集/parser 保留） | 否 | 持续状态 | partial write 是当前写入完整性缺口，修复前持续存在；当前 YAML 尚未消费它。 |
| 21 | `trail.checkpoint_projection_race` | 无当前处境行（闭集/parser 保留） | 否 | 一次性事件 | race 是一次检测到的 checkpoint 对账事件，处理/对账后旧事件不应无限重放；当前 YAML 尚未消费它。 |
| 22 | `trail.checkpoint_refresh_needed` | `attempt.record.checkpoint-refresh` | 是 | 持续状态 | checkpoint 未刷新前仍需要刷新，完成后才应显式 false。 |
| 23 | `trail.envelope_valid` | `finding.fix.worker-envelope-invalid` | 否 | 持续状态 | 当前 worker return 的 envelope validity 是当前返回证据状态，直到新的有效/无效返回覆盖它才改变。 |
| 24 | `trail.handoff_in_flight` | `attempt.record.handoff-in-flight` | 是 | 持续状态 | handoff 是否仍在进行是当前 liveness，直到结束/取消才变 false。 |
| 25 | `trail.handoff_recovery_needed` | `attempt.record.handoff-recovery-needed` | 是 | 持续状态 | recovery 仍未完成时需求持续存在；完成后需显式 false。 |
| 26 | `trail.handoff_target_corrected` | `attempt.record.handoff-target-corrected` | 是 | 一次性事件 | target corrected 描述已经完成的一次纠正，纠正后的 handoff 已处理后不应继续重发。 |
| 27 | `trail.judgment_unfiled` | `ticket.record.judgment-unfiled` | 是 | 持续状态 | judgment 在归档前仍是未登记状态，直到显式登记/false。 |
| 28 | `trail.reviewer_unavailable` | `attempt.review.reviewer-unavailable` | 否 | 持续状态 | reviewer 不可用是当前能力状态，不能仅因时间过去就假设恢复。 |
| 29 | `finding.closure_review_pending` | `finding.review.closure-awaiting` | 否 | 持续状态 | closure review 未完成前仍 pending，直到 review/关闭改变状态。 |
| 30 | `ticket.judgment_unfiled`（legacy alias） | 归一为 `trail.judgment_unfiled`，消费 `ticket.record.judgment-unfiled` | 是 | 持续状态 | 只是历史输入名，不是新语义；生命周期必须与 canonical key 相同。 |

### P0 影响计数

按“P0 row 的输入映射”计，9 个 canonical key 映射到 P0 row：`package.validate.projection_drift`、`attempt.session_resumed`、`attempt.handoff_or_long_task`、`trail.anchor_mismatch`、`trail.handoff_recovery_needed`、`trail.handoff_target_corrected`、`trail.checkpoint_refresh_needed`、`trail.handoff_in_flight`、`trail.judgment_unfiled`。legacy alias 是第 10 个接受名称，但与最后一个 canonical key 同义。

按“当前实现中 stale fact 真能驱动 P0”计，只有 8 个 canonical key：`attempt.session_resumed` 虽然仍在闭集并映射到 P0 row，但当前 renderer 明确忽略该声明，row 使用 active checkpoint 与 `trail.actions_since_checkpoint`；所以它不会制造本题所说的 latest-wins stale-fact 误命中。

真实 package 当前 P0 事实情况：

- `package.validate.projection_drift=false`、`trail.checkpoint_refresh_needed=false` 已知，不命中；
- `trail.handoff_target_corrected=true` 命中并被选为 P0；
- `trail.anchor_mismatch`、`trail.handoff_recovery_needed`、`attempt.handoff_or_long_task`、`trail.handoff_in_flight`、`trail.judgment_unfiled` 缺声明，因此对应 9 个 P0 U 行（其中 judgment row 在 5 个 Ticket context 各出现一次）；
- P0 的 `attempt.record.session-resumed` 由 state/checkpoint 规则判定，不是该 fact 声明判定。

## 3. 47 行 U 的真实计数

真实 package JSON render 的 `undetermined.Count` 是 47。按“unknown reason 明确表示缺少 `kind=fact`/canonical fact”的严格口径计：

- **30/47 行** 是因为缺 fact；这是本题第 4 问的直接答案；
- 其中 **9/47 行** 是 P0 fact 缺失导致：`attempt.record.anchor-mismatch`、`attempt.record.handoff-recovery-needed`、`attempt.record.checkpoint-missing`、`attempt.record.handoff-in-flight` 各 1 行，`ticket.record.judgment-unfiled` 5 行；
- 如果把“闭集 fact key 的 resolver 最终为 unknown”也算作宽口径 fact-related，则是 **37/47 行**。多出的 7 行不是缺 `kind=fact`：`ticket.no_longer_needed` 5 行是业务判断缺口，`attempt.terminal_coverage_complete` 1 行和 `trail.envelope_valid` 1 行是各自没有列出的机械输入/结构化 envelope 输入；不能把它们误报为可用 fact 漏写。
- 剩余的严格非 fact 缺口为：`git.head_advanced_since_last_trail` 4 行、`intake.has_backlog` 1 行、`gate.verdict` 1 行、`gate.stage7_complete` 1 行、`finding.review_track + finding.source_recheck_pending` 1 行、`finding.grading_pending` 1 行、`attempt.compaction_pressure_high` 1 行；这些与上面的宽口径解释共同覆盖 47 行。

真实 package 当前命中的 active rows 是 6 行：选中的 P0 `attempt.record.handoff-target-corrected`，以及被 P0 压下的 `attempt.readiness.all-edges-held`、`attempt.readiness.worker-still-running`、`finding.review.closure-awaiting`、`attempt.review.reviewer-unavailable`、`ticket.rework.revalidation-pending`。其中当前为 true 且带旧 head 的 fact-driven row 有 3 个：

1. P0 `trail.handoff_target_corrected=true`（一次性事件）；
2. P2 `trail.reviewer_unavailable=true`（持续状态）；
3. P2 `finding.closure_review_pending=true`（持续状态）。

因此，若只对一次性事件做 head 新鲜度检查，真实数据会把当前选中的 P0 row 从 true 降为 U，P0 不再抢占，现有 P1 `all-edges-held`/`worker-still-running` 才会成为最高层；这不是把仍然成立的连续状态清掉，而是识别出旧 head 上的一次性纠正已被后续轨迹推进覆盖。

若对全部 fact 一刀切，另外两个仍为 true 的连续状态（reviewer unavailable、closure review pending）也会因旧 head 被降为 U；这会错误清掉当前仍需 reviewer/review 的状态。因此“全部 fact 都 freshness”不安全，分类必须参与判定。

阶段 1 结论：影响面不是一两行；有一个真实、P0、已被后续 head 推进证实陈旧的错误最高建议，同时 37 行 U 说明缺 fact 本身已经是主要不确定性来源。进入阶段 2 选择方案。

## 4. 阶段 2：方案选择

### 4.1 候选比较

| 方案 | 能否处理真实 P0 stale fact | 主要代价/风险 | 对本项目的判断 |
|---|---|---|---|
| A：要求处理完追加 `false` | 能，但依赖每次 handoff/review 都记得补写 | 继续依赖纪律；本项目已有多次“纯自觉规则衰减”的证据；漏写时仍永久 true | 不选。它没有消除本次根因。 |
| B：按 fact `head` 做新鲜度 | 能。真实 `handoff_target_corrected` 的旧 head 与当前 head 不同，会安全降为 U，释放 P0 抢占 | 需要区分一次性事件与持续状态；`head` 可选，旧无 head 轨迹必须有兼容策略 | **选择 B**。已有 head 载体，且能只收敛本次已证实的 P0 事件。 |
| C：相关 row 改 `judgment: true` | 不会自动误投递，但每次都把机械事实升级成主控判断 | 把可机械验证的 stale 问题转成人工负担；真实 package 仍会把错误 P0 暴露给主控 | 不选。它回避了过期判定，没有利用已有 head。 |

### 4.2 选择 B 的边界

新鲜度**只作用于阶段 1 分类为“一次性事件”的 key**：

```text
attempt.session_resumed
ticket.blocker_maybe_resolved
ticket.release_edge_rechecked
ticket.review_trigger
git.comparison_head_fixed
trail.checkpoint_projection_race
trail.handoff_target_corrected
```

其中 `attempt.session_resumed` 的声明目前不参与 row 判定，列入集合只是保持生命周期语义一致，不改变现有 session-resumed 推导。

不对持续状态做 head 过期：`trail.reviewer_unavailable`、`attempt.manual_verification_owner`、`attempt.integration_*`、`trail.handoff_in_flight` 等为真时，应一直保持为真直到显式改变。阶段 1 的真实数据直接证明了这一点：`reviewer_unavailable=true` 与 `finding.closure_review_pending=true` 仍是当前 active match，不能因它们的记录 head 较旧就清除。

### 4.3 可选 head 的处理

- **有 `head`**：一次性 fact 的记录 head 能解析且等于当前 package head（允许 Git 可解析的短 SHA 与完整 SHA 等价）时保持原值；不能证明同一 head 时转为 `U`，原因写入 JSON `when`，不转成 false。
- **没有 `head`**：保持现有值，不自动过期。

理由是兼容性与可证据化边界：现有 fixture 和历史 package 大量使用无 head fact；若把无 head 一律视为 U，会直接改变现有 P0 fixture 的期望并使老包大面积退化，而报告已证明本轮真正需要修正的是“有 head 且明确跨 head”的真实事件。无 head 既不能证明新鲜也不能证明陈旧，因此本阶段不伪造过期结论；后续新写入规范由文档要求携带 head。这个 fallback 不会把无 head 转成 false，也不会拒绝 renderer；它保留旧行为，同时让带 head 的新轨迹获得自动防陈旧能力。

### 4.4 安全降级与范围

- head 不同/当前 head 不可得时只返回 unknown（U），不返回 false，不触发任何反向“已恢复”结论，也不让 renderer 报错。
- 不新增 fact key、gate、常驻进程；不改变 `situations.yaml` 的 row 判据。
- 预计实现写集只有 `plugin-marketplace/plugins/impl-package/scripts/situation.py` 与本文件中相关 fact 行；补充针对有 head / 旧 head / 无 head / 持续状态的 focused tests，不改任何既有 fixture `expected.json`。
- `dispatch_audit.py`、`compaction_pressure.py`、`impl_package_state.py` 和四个 leaf agent 不在写集内。

阶段 2 结论：选择 B，范围限于一次性事件的 head freshness；无 head 保持兼容值，有 head 跨当前 head 则安全降为 U。进入阶段 3 实施与实测。
