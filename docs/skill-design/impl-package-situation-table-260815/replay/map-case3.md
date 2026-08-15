# 回放映射 · case3

## 整体判断

这是案例 3 的完整时间线，不是分片。总范围是一个 DATEV PDF AI 表单预填的 upload-only UI patch：从 terminal 后的需求/合同对齐，经过 UI 实现、Owner 决策、合同传播、多轮修复与 terminal-final review，最后停在组件范围 conditional PASS；整个 Implementation Package 没有重新判 Gate，也不能称为 closed。

- 决策点：45
- 确定命中：38
- `unmatched`：5
- `insufficient-evidence`：2
- 命中率：38 / 45 = **84.4%**
- 同一决策点多重命中：**12** 个确定点；另有 1 个多重命中候选受证据不足影响

最终仍保留 3 条收口边界：`requesting_upload/confirming` 状态与两参数 adapter 合同不一致、失败上传后的 pending FileObject 清理责任与证据、组件卸载后已启动请求的取消/补偿责任。最终 review 的 conditional PASS 只覆盖 UI 组件拓扑，不等于 package Gate pass。

## 概况

仓库与 package 锚点来自时间线：

- worktree：`D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning`
- package：`docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe`
- session：3 个，按时间线标识为 `159ce0d7`、`ce868cb0`、`cbf128be`
- 时间范围：`2026-08-14T16:51:44.961Z` → `2026-08-15T11:56:32.846Z`
- session 1：docs-only req-align、patch 设计与首次独立 review；停在 Owner 的 partial-failure 产品决定之前。
- session 2：upload-only UI 实现、P1/P2 修复、fail-closed `onReady` 决策与合同传播；closure review 最初留下 UI-CL-05。
- session 3：修复 UI-CL-05，随后按 Owner 指示直接跑多轮 terminal-final 全量适用拓扑；最终 UI review 为 conditional PASS，package 未闭合。

三个 session 在交接窗口有时间重叠：session 2 已开始时 session 1 仍在输出交接收口；session 3 已开始时 session 2 仍在输出交接回报。因此下表按“决策发生的时间/seq”定位，不把 session 边界当成严格串行边界。

## 计数口径

只计“主控决定接下来做什么”的首次动作：派发 investigate/implement/fix/review、处理 reviewer 返回、选择业务路线、合同变更后的推进、跨 session 交接、review/Gate 收口与 finding 分流。合并同一条动作的等待、同 revision 重跑和状态播报；用户明确作出的产品选择计为该选择被采纳的决策点。没有直接 state/trail 字段的地方不推断，单列 `insufficient-evidence`。

## 决策点与映射

| # | 时间 / timeline seq | 主控决定 | 映射与判定依据 |
| --- | --- | --- | --- |
| DP01 | 16:51:52 / `4` | 新 session 首轮只做 worktree、HEAD、package 与 Gate 锚点只读核验。 | **命中** `attempt.record.session-resumed`（prose）：存在新 session 与 active checkpoint；但先做 anchor 而非直接 restore，动作细节不完全可见。 |
| DP02 | 16:53:49–16:56:12 / `25`, `60` | 识别 initial Gate 已 terminal/frozen，把本轮转为 behavior-contract/Decision/Spec patch，停在实现前。 | **命中** `attempt.gate.terminal-frozen`（cli）：terminal Gate 后不能继续推进旧 attempt，应回 patch 规划。 |
| DP03 | 16:59:19 / `109` | 接受 Owner 的范围收窄：本包只拥有 PDF 上传与处理状态，表单由另一任务包拥有。 | **命中** `ticket.route.multiple-business-outcomes`（prose）：多个 surface/ownership 结果中由 Owner 作出路线选择。 |
| DP04 | 17:03:54 / `155` | 将上传边界收敛为可嵌入深模块，复用 File Security 生命周期，再写 patch plan 与 Ticket。 | **命中** `ticket.route.sources-uniquely-decide`（prose）：现有产品/API/权限事实足以裁定最小技术路线。 |
| DP05 | 17:11:42–17:12:08 / `202`, `207` | candidate 文档具备后派发独立 closure reviewer，主控保留合同与结论所有权。 | **命中** `ticket.review.required-trigger`（prose）：共享 seam、安全、隐私与不可逆文件副作用触发 review。 |
| DP06 | 17:21:49–17:24:24 / `233`, `271` | reviewer 返回 5 项后修订 4 项确定的合同问题，同时把 partial-failure 继续条件留给 Owner。 | **命中** `finding.fix.reviewer-returned`（prose）：finding 来源是 reviewer；同点另像 `ticket.route.multiple-business-outcomes`。 |
| DP07 | 17:27:58 / `283` | 用 verification-before-completion 校准收口措辞，只声明 candidate/review 形成，不声明批准、实现或验收。 | **命中** `attempt.accept.completion-claim-unaudited`（prose）：完成性表述前先审计证据。 |
| DP08 | 17:31:21–17:35:03 / `305`, `336`, `351` | 以现有 checkpoint 交接到新 local session；新 session 继续前先恢复 anchor，并保留 partial-failure blocker。 | **命中** `attempt.record.session-resumed`（prose）；同时碰到 frozen initial Gate，另像 `attempt.gate.terminal-frozen`。 |
| DP09 | 17:35:16–17:38:06 / `382`, `415` | 在 initial frozen/pass 仍存在、patch attempt 尚未初始化的情况下，按 Owner 授权进入 upload-only UI 实现。 | **unmatched**；建议 `attempt.readiness.patch-attempt-not-initialized`。表中没有“terminal initial 的新 patch 已获批但 patch attempt 尚未初始化”的 readiness 行。 |
| DP10 | 17:39:58 / `442` | 选择 `mode=implement`，限定 UI 两文件写集，并把 review 设为 required/closure。 | **命中** `ticket.route.sources-uniquely-decide`（prose）：合同边界已裁定，进入实现；同点另像 `ticket.review.required-trigger`。 |
| DP11 | 17:49:05 / `515` | 主控发现 DOM selector 暴露 `fileId` 的隐私问题并立即改为位置 selector。 | **命中** `finding.fix.main-session-discovered`（prose）：finding 由主控发现并直接修正。 |
| DP12 | 17:52:35 / `562` | focused/full Web 验证通过后派发独立 closure review。 | **命中** `ticket.review.awaiting-reviewer`（prose）：实现已完成且 review required，转交 reviewer。 |
| DP13 | 17:58:51 / `613`, `614` | 首轮 review 返回 2 个 P1、3 个 P2，派发 fresh fixer 修复授权范围内的 P1 与 UI 细节。 | **命中** `finding.fix.reviewer-returned`（prose）：reviewer finding 只能由 fresh fixer 消费。 |
| DP14 | 18:06:01 / `653` | fixer 未返回且安全停止，主控接管同一 bounded finding 的修正。 | **命中** `finding.fix.reviewer-returned`（prose）：finding 仍来自 reviewer；但“fixer 不可用后由主控接管”不是表内显式分支。 |
| DP15 | 18:11:00 / `721` | P1 修复和局部验证通过后，重新启动同 comparison point 的独立 closure re-review。 | **命中** `ticket.review.awaiting-reviewer`（prose）：修复后仍需同 scope review。 |
| DP16 | 18:16:49 / `750` | 将 P1 降为 0，修复删除 pending 不应阻塞其他文件的 P2，并保留真实 DOM harness 缺口。 | **命中** `finding.fix.reviewer-returned`（prose）：review finding 分别进入修复或保留风险；另像 finding triage。 |
| DP17 | 18:19:10 / `769` | 补 host 引用回归断言并再次进入最终独立收口复审。 | **命中** `ticket.review.awaiting-reviewer`（prose）。 |
| DP18 | 18:29:56 / `845` | 因无现成 DOM harness 且未获 browser/外部链路授权，不新增依赖或伪造组件异步证据，保持 patch 未 closed。 | **unmatched**；建议 `attempt.verify.component-harness-missing`。`attempt.verify.manual-result-missing` 只覆盖已有 manual owner 的结果缺失，不能准确承载此处的组件级 harness/授权缺口。 |
| DP19 | 22:17:55–22:19:20 / `863`, `864`, `868` | Owner 选择 fail-closed：混合成功/失败时，失败项必须重试成功或明确移除后才允许 `onReady`。 | **命中** `ticket.route.multiple-business-outcomes`（prose）：同一产品情形存在“成功子集继续/等待全部”的两个合理结果。 |
| DP20 | 22:20:18–22:21:17 / `881`, `898` | 将 Owner 决策传播为合同，再实现 `onReady` gate；不触及表单、API、DB、provider 或 browser。 | **命中** `attempt.rework.contract-changed`（prose）：contract 实际变化后记录受影响子集并推进；同点另像 `ticket.route.sources-uniquely-decide`。 |
| DP21 | 22:26:03–22:28:01 / `938`, `951`, `954` | 代码与本地验证通过，但 bookkeeper 只写入 Decision/Spec 2/5；主控决定继续补写其余 3 份 package 文档。 | **insufficient-evidence**：候选 `ticket.record.evidence-unfiled`。时间线能看到 worker 直接回报与继续派发，但看不到 `evidenceIndex` 是否已更新。 |
| DP22 | 22:35:57–22:38:55 / `1006`, `1025` | 窄范围 bookkeeper 0/3 写入后停止，主控改为机械性同步 contract-design、Plan、Ticket，再启动 review。 | **unmatched**；建议 `attempt.record.worker-write-partial`。表中没有 package 文档 bookkeeper 部分写入/停止后的记录层恢复动作。 |
| DP23 | 22:39:01 / `1026` | 合同残留扫描通过后再次派发 fresh closure reviewer。 | **命中** `ticket.review.awaiting-reviewer`（prose）：待审查的实现/合同结果已形成。 |
| DP24 | 22:44:47–22:44:53 / `1058`, `1059` | reviewer 被中断且没有有效结论，主控不采信它，改派更窄的 fresh reviewer。 | **命中** `ticket.review.awaiting-reviewer`（prose）：review required 仍未消费；表没有“无效回执后缩小 review scope”的独立行。 |
| DP25 | 09:22:31–09:22:58 / `1093`, `1096` | 明确先做 closure review，再做 terminal；收到 GO 后执行 closure，不提前判 terminal。 | **命中** `attempt.review.terminal-coverage-incomplete`（prose）：terminal-final coverage 尚未形成，先补 review。 |
| DP26 | 09:27:50–09:33:04 / `1151`, `1186`, `1206` | 为获得 immutable review head 先建临时 snapshot；Owner 随后授权真实 commit，主控只提交 UI/合同写集。 | **unmatched**；建议 `attempt.review.comparison-head-unfixed`。`ticket.rework.revision-diverged` 需要 acceptance revision 已分叉，本点只有未提交工作树与 review head 固定问题。 |
| DP27 | 09:36:31–09:36:38 / `1250`, `1251` | 真实 commit `7941a077` 形成后，以该 head 重建 fresh closure review。 | **命中** `ticket.review.awaiting-reviewer`（prose）：不可变实现结果形成后重新消费 review required。 |
| DP28 | 09:42:14–09:44:51 / `1288`, `1306` | closure 6/7 PASS、UI-CL-05 失败；主控写 canonical ledger，拒绝把缺口包装成 terminal PASS。 | **命中** `attempt.disposition.findings-triage-pending`（prose）：临近 terminal 的 finding 仍需分流/收口。 |
| DP29 | 09:58:07–10:03:37 / `1311`, `1335`, `1356` | 将 UI-CL-05 剩余工作交接到第三个 session，明确修复后直接 terminal-final，不再单独 closure。 | **命中** `attempt.record.session-resumed`（prose）：新 session 从已记录 commit/checkpoint 恢复；“跳过单独 closure”本身不在表中。 |
| DP30 | 10:01:01 / `1371` | 新 session 的目标限定为修复 reviewer 留下的 UI-CL-05，再做 terminal-final。 | **命中** `finding.fix.reviewer-returned`（prose）。 |
| DP31 | 10:02:04 / `1383` | package validator 报 `04-ui-upload-acceptance.md` 缺少 Ticket ID；主控将其视为既有记录问题，保护 dirty 记录，不覆盖修复。 | **命中** `package.record.state-missing`（cli）：validator 明确暴露记录无效；已执行 validate，随后选择保留/escape，未执行 init。 |
| DP32 | 10:04:05 / `1412` | 先确认现有 React/测试运行时能否提供真实 mounted async 证据；没有可复用 DOM 能力则停在 blocker。 | **insufficient-evidence**：候选 `ticket.investigate.evidence-gap`。事实缺口明确，但 timeline 没有 `trail.last_outcome=EVIDENCE_GAP` 的机械字段。 |
| DP33 | 10:05:24 / `1432` | 按 Owner 要求派发 fresh `mode=fix` worker，只改 UI-CL-05 测试文件，后续由 terminal-final 承担 review。 | **命中** `finding.fix.reviewer-returned`（prose）。 |
| DP34 | 10:09:35–10:10:29 / `1468`, `1474` | 第一个 fix worker 因缺少 jsdom 等依赖返回 BLOCKED；主控根据 fake-DOM 新事实再派第二个 fresh fix worker。 | **unmatched**；建议 `finding.fix.worker-blocked`。允许矩阵有 `finding.fix`，但当前只有 ticket 的 `worker-blocked`，无法合法套用 `ticket.implement.worker-blocked`。 |
| DP35 | 10:20:09–10:21:43 / `1530`, `1531`, `1553` | UI-CL-05 8/8 通过后保留 review pending，固定 commit `db063b46`，准备 terminal-final 全量拓扑。 | **命中** `ticket.review.awaiting-reviewer`（prose）。 |
| DP36 | 10:23:59 / `1577` | 在 `5b2db297...db063b46` 上并行派发行为、规范、Spec fidelity、Safety 四条 terminal-final review leaf。 | **命中** `attempt.review.terminal-coverage-incomplete`（prose）：terminal coverage 尚未齐全。 |
| DP37 | 10:30:05–10:31:18 / `1609`, `1624` | 四轨返回 P1/P2 后，核验 finding，派 worker 修 timer/unmount、safe-ref projection、错误脱敏与重复校验。 | **命中** `finding.fix.reviewer-returned`（prose）；同点也像 terminal finding triage。 |
| DP38 | 10:40:25–10:40:39 / `1673`, `1677` | worker 修复后主控复核发现 typecheck 的 nullable/type errors，回派同一 worker 做纯类型修复。 | **命中** `finding.fix.main-session-discovered`（prose）：新的可执行缺陷由主控验证时发现；不是正式 `INCOMPLETE` 返回。 |
| DP39 | 10:43:28–10:43:55 / `1693`, `1704` | 类型修复通过后提交 `83576c99`，不复用旧 verdict，重新启动四轨 terminal-final。 | **命中** `attempt.review.terminal-coverage-incomplete`（prose）。 |
| DP40 | 10:53:30–10:53:54 / `1769`, `1773` | 新四轨指出 runtime status 未 fail-closed与三参数 `onStage` 合同偏差；派 worker 只修 UI 两项，pending cleanup 留作外部 gap。 | **命中** `finding.fix.reviewer-returned`（prose）。 |
| DP41 | 11:03:38–11:04:05 / `1820`, `1829` | 两项 UI 修复和 17/17 验证通过，提交 `d84366cb`，再次以最终 head 跑四轨 review。 | **命中** `attempt.review.terminal-coverage-incomplete`（prose）。 |
| DP42 | 11:13:09–11:13:24 / `1880`, `1883` | 最终拓扑发现文件名隐私泄露、同步 throw 卡状态、超限 handoff guard；再派 UI worker，继续保留外部 gap。 | **命中** `finding.fix.reviewer-returned`（prose）。 |
| DP43 | 11:20:00–11:20:19 / `1910`, `1916`, `1921` | 三项修复通过后，主控又发现“全量 state items 超限”整合边界，做最小修正并重新验证。 | **命中** `finding.fix.main-session-discovered`（prose）。 |
| DP44 | 11:20:39–11:20:53 / `1928`, `1932` | 在最终 head `7ebe1a1e` 上重新创建完整四轨 terminal-final review，不复用前轮结论。 | **命中** `attempt.review.terminal-coverage-incomplete`（prose）。 |
| DP45 | 11:28:03–11:56:32 / `1969`, `1986`, `1991` | canonicalize 最终 verdict：UI 组件 conditional PASS，但把状态阶段、pending cleanup、取消/补偿列为外部/合同 gap，保持 package 未 closed。 | **命中** `attempt.disposition.findings-triage-pending`（prose）：finding/边界被保留并需要 Owner/外部链路分流；不是新的 Gate verdict。 |

## 命中分布

以下只统计 38 个确定命中；2 个 `insufficient-evidence` 不计入命中，5 个 unmatched 不计入命中。

| 环节 | 命中数 | 主要 slug |
| --- | ---: | --- |
| `record` | 4 | `attempt.record.session-resumed` 3，`package.record.state-missing` 1 |
| `readiness` | 0 | — |
| `investigate` | 0 | 1 个候选点，证据不足 |
| `route` | 4 | `ticket.route.multiple-business-outcomes` 2，`ticket.route.sources-uniquely-decide` 2 |
| `implement` | 0 | 没有可直接观察到的 formal Ticket worker outcome |
| `fix` | 12 | `finding.fix.reviewer-returned` 9，`finding.fix.main-session-discovered` 3 |
| `verify` | 0 | 1 个 component harness 候选点未能合法落入现有行 |
| `review` | 13 | `ticket.review.awaiting-reviewer` 7，`ticket.review.required-trigger` 1，`attempt.review.terminal-coverage-incomplete` 5 |
| `accept` | 1 | `attempt.accept.completion-claim-unaudited` 1 |
| `rework` | 1 | `attempt.rework.contract-changed` 1 |
| `disposition` | 2 | `attempt.disposition.findings-triage-pending` 2 |
| `gate` | 1 | `attempt.gate.terminal-frozen` 1 |
| **合计** | **38** |  |

### `unmatched` 清单

| 决策点 | 真实发生的事 | 建议 slug（符合允许矩阵） | 缺口 |
| --- | --- | --- | --- |
| `seq 382–415` | initial terminal/frozen 仍在，Owner 已授权新 UI patch，但 patch attempt 尚未初始化就进入实现。 | `attempt.readiness.patch-attempt-not-initialized` | 没有“新 patch readiness/初始化边界”行，A4 无法区分合法 patch 还是继续推进旧 terminal attempt。 |
| `seq 845` | 真实组件异步证据因没有 DOM harness/授权而暂缺，主控决定保持未 closed。 | `attempt.verify.component-harness-missing` | F1 只描述 manual owner 无结果，未覆盖组件 harness/测试运行时缺失。 |
| `seq 1006–1025` | 文档 bookkeeper 0/3 写入后停止，主控转为机械性补写并继续 review。 | `attempt.record.worker-write-partial` | 没有 attempt-level 记录 worker/书写代理部分落账的处置行。 |
| `seq 1151–1206` | 为 review 创建临时 immutable snapshot，之后才因 Owner 授权创建真实 commit。 | `attempt.review.comparison-head-unfixed` | `revision-diverged` 不是“未提交工作树导致 review head 尚未固定”。 |
| `seq 1468–1474` | `finding.fix` worker 因测试运行时依赖缺失返回 BLOCKED，随后 fresh retry。 | `finding.fix.worker-blocked` | 现有 `worker-blocked` 只合法落在 `ticket.implement`，对象×环节矩阵阻止直接套用。 |

### `insufficient-evidence` 清单

- `seq 938, 951, 954`：worker/bookkeeper 返回了直接结果，随后继续派发或补写；但 timeline 没有 state/evidenceIndex 读回，不能断言 `ticket.record.evidence-unfiled` 已命中。
- `seq 1412`：明确存在“未真正挂载组件、无法证明 effect 驱动 `onChange`”的证据缺口，但没有可见的 `trail.last_outcome=EVIDENCE_GAP`，不能机械断言 `ticket.investigate.evidence-gap`。

## 多重命中

确定的 12 个多重命中如下。括号中的“优先”是按 YAML priority 的现有顺序推导；被优先级表遗漏的 slug 没有可证明的胜出顺序。

| seq | 同时像哪些行 | 当前优先结果 / 暴露的问题 |
| --- | --- | --- |
| `4` | `attempt.record.session-resumed` + `attempt.gate.terminal-frozen` | `terminal-frozen` 应先；A3 未列入 priority。 |
| `233` | `finding.fix.reviewer-returned` + `ticket.route.multiple-business-outcomes` | reviewer 返回优先消费，E1 先于 C3。 |
| `305/336` | `attempt.record.session-resumed` + `attempt.gate.terminal-frozen` | A4 先于 A3；同样暴露 A3 遗漏。 |
| `442` | `ticket.route.sources-uniquely-decide` + `ticket.review.required-trigger` | C4 先于 C7。 |
| `868` | `ticket.route.multiple-business-outcomes` + `attempt.rework.contract-changed` | C3 先于 D4；Owner 决策是原因，合同传播是后续动作。 |
| `881/898` | `attempt.rework.contract-changed` + `ticket.route.sources-uniquely-decide` | C4 在 current-subject 顺序中先于 D4，边界容易把“合同已变”吞掉。 |
| `1250/1251` | `ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete` | C6 先消费 implementation review，F3 再表达 terminal coverage。 |
| `1530/1577` | `ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete` | 同时有局部 review pending 与全局 terminal review pending；C6 先。 |
| `1609/1624` | `finding.fix.reviewer-returned` + `attempt.disposition.findings-triage-pending` | E1 先于 terminal finding triage；E5 未列入 priority。 |
| `1769/1773` | `finding.fix.reviewer-returned` + `attempt.disposition.findings-triage-pending` | E1 先；外部 pending cleanup 的归属没有优先级。 |
| `1880/1883` | `finding.fix.reviewer-returned` + `attempt.disposition.findings-triage-pending` | E1 先；同一 review finding 还需跨 UI/API 责任分流。 |
| `1928/1932` | `attempt.review.terminal-coverage-incomplete` + `attempt.disposition.findings-triage-pending` | F3 先；E5 未列入 priority。 |

另有 `seq 938–954` 可能同时命中 C8 与 C6，但因为 evidenceIndex 状态不可见，未计入上述 12 个确定点。

## 跳步检测

| 检查项 | 计数 | seq 定位与结论 |
| --- | ---: | --- |
| 没有任何调查载体就直接进入实现 | **确认 0；insufficient-evidence 2** | `seq 442`、`898` 进入 implement 前有需求、代码事实、合同与 review 载体，但没有可见的 Ticket-specific `trail.has_investigate` 字段；不能把“没有 `sdd mode=investigate` 命令”直接等同于无调查。 |
| worker 返回后未记 evidence 就推进 | **确认 0；insufficient-evidence 10 个返回→下一动作 bundle** | 返回点为 `seq 600, 747, 828, 951, 1003, 1468, 1530, 1666, 1816, 1910`；全 timeline 没有可见 `evidence add`，但截断规则不允许据此证明 state/evidenceIndex 从未落账。 |
| 未经独立 review 就宣称完成或 satisfy | **确认 0** | 没有可见 `ticket satisfy`、`gate pass` 新判定或满足性声明；主控多次明确“不能 closed”。worker 的 scoped `PASS/closed` 没有被冒充为 package closure。 |
| 已 SATISFIED 的 Ticket 被新证据触及时是否处置 | **确认 0；insufficient-evidence 1** | `seq 23` 只显示 initial 3/3 SATISFIED，之后 `seq 60/305` 把 UI 需求作为 terminal 后的新 patch，而不是 claim 被证伪；没有 claim-level evidence/`needs-revalidation` 记录，无法确认 D1 是否应触发。 |

补充：timeline 中只有 initial snapshot 声称 `3/3 Ticket SATISFIED`；没有直接可见的 Ticket state transition、`ticket satisfy/block/retire/needs-revalidation` 或 `evidence add` 命令。关于 Ticket 状态的读数因此是“不可从本片直接复原”，不是“没有发生”。

## 表本身的问题

1. **priority 不覆盖多行真实命中。** YAML priority 明确列出了 A1/A2/A4、C6/C10–C12/E1、C/D、B3/F、G2，但遗漏 `attempt.record.session-resumed`、B1/B2/B4、E2–E5、`attempt.record.checkpoint-missing` 等。case3 中 A3/A4、E1/E5、F3/E5 的重叠已经实际出现，无法对遗漏行给出稳定胜出顺序。
2. **缺少新 patch readiness 边界。** A4 把“terminal Gate 后仍有推进请求”统一导向 fail closed，但 case3 是 initial attempt frozen 后经 Owner 明确授权启动新 patch；没有 patch-attempt 初始化/绑定行，A4 既可能误阻合法 patch，也可能漏掉未初始化就实现的动作。
3. **worker 失败/部分写入的对象覆盖不完整。** `ticket.implement.worker-blocked` 不能用于 `finding.fix` worker；bookkeeper 0/3 写入也不是 Ticket implement。真实流程需要 `finding.fix.worker-blocked` 与 attempt-level record recovery，表当前无法合法表达。
4. **review head 与 review phase 混在一起。** case3 需要“未提交工作树 → 临时 snapshot/真实 commit → immutable review head”，但 `revision-diverged` 只表达 acceptance revision 已分叉；同时 closure review、terminal-final、组件 conditional PASS 与 package Gate pass/frozen 并存，表没有区分这些 verdict 层级。
5. **验证载体缺口没有对应行。** 真实组件 mounted async 证据因没有 DOM harness/授权而停住；F1 的 manual owner 语义过窄，无法涵盖 test runtime、browser 授权和组件级 harness 缺失。
6. **C8 的 evidence 边界不清。** reviewer report、bookkeeper 文档写入回执、worker verification envelope 是否都算“direct evidence returned”没有写清；因此 case3 的“返回后是否已 indexed”只能标 `insufficient-evidence`。
7. **`finding.fix.reviewer-returned` 的动作假设过于理想化。** 真实流程出现 fixer shutdown、fresh retry、主控接管、同一 worker 的纯类型修复回合；表只规定 fresh fixer + 同 scope review，没有 unavailable/blocked/类型回归等分支。
8. **`basis` 暂不应因本例改写，但有观察信号。** C6、E1、E3、F3 的 prose 规则在本例被多次实际采用，说明它们可被继续观测；这不是把 basis 直接升为 `observed` 的充分证据。A1 的 cli validator 与旧 package 记录不一致也可能是版本/旧 schema 干扰，不能仅凭本片改 basis。

## 版本干扰

- `seq 5` 先尝试读取不存在的 Impl-Package `0.3.0` skill，`seq 8–10` 再定位到 `0.3.1`；早期行为可能受 skill cache 版本切换影响。
- 后续 `execution-preflight`、`do-review`、`review-code*`、`safety-review` 与 review ledger 均按 `0.3.1` 脚本/skill 运行；不能把旧 attempt 的字段缺失直接视为当前表的语义缺口。
- `seq 1383` 的 package validator 报 Ticket ID 缺失，发生在既有 dirty package 记录上；它可能是旧 package/schema 与新 validator 的兼容问题，不能据此断言 `package.record.state-missing` 的所有触发都应进入新的修复流程。
- `seq 1309` 的 Owner 指令明确要求“修复后不用再 closure，直接 terminal-final”；因此这条路径是用户覆盖工作流的授权，不应简单算作 agent 擅自跳过 C6/F3。
- initial `pass/frozen@5b2db297` 属于先前 Probe attempt；UI patch 是 terminal 后的新行为合同与实现。若不把“新 patch”与“旧 terminal attempt”分开，A4、D4、F3 的命中会被错误解释。
- 由于抽取规则把 tool output 截断到 200 字符、user/assistant 也有长度上限，本报告没有把“看不见 `evidence add`/state transition”当成绝对未发生；相关位置已按 `insufficient-evidence` 或跳步不确认处理。

## 最值得注意的三个发现

1. **优先级表本身是当前最大机械性风险。** case3 实际触发了 A3/A4、C4/C7、E1/E5、C6/F3 等重叠；但 A3、E5 等行未进入 priority，渲染器即使能发现命中，也没有完整的稳定胜出依据。
2. **流程证据比最终代码 verdict 更薄。** 45 个决策点中只有 38 个能确定映射；Ticket state、evidenceIndex、checkpoint 写入和新 Gate 判定都没有可直接复原的命令/读回，跳步结论必须保守。
3. **真实工作流已经超出表的对象边界。** `finding.fix` worker BLOCKED、bookkeeper 部分写入、immutable review head 和 component harness 缺失都是真实决策，但当前 42 行没有合法且精确的处境；最终 UI conditional PASS 也仍被 3 个外部/合同 gap 阻塞，不能把组件收口当 package closed。

