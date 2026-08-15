# 案例 3：DATEV PDF AI 表单预填 UI 上传 Patch

## 整体判断

本回放覆盖 3 个连续 Codex session、42 个主控决策点；抽取、时间线重建和处境表映射已完成。命中 34 个、`unmatched` 8 个，命中率为 81.0%，其中 11 个决策点存在多重命中。被回放的源任务在最后一个 session 结束时仍停在 `terminal-final` review `in-progress`，没有新的 Gate verdict，因此源任务不能称为 closed；本次报告本身没有待 Owner 决策，Owner 已在回放中决定 mixed success/failure 采用 fail-closed。

这里的“完成”只指本报告的 replay/extract/mapping 阶段；不表示源任务的 UI patch 已通过最终 Gate。

## 1. 案例概况

- **任务包**：DATEV PDF AI 表单预填 UI 上传 Patch；上传模块负责 PDF 选择、逐文件上传/确认/失败重试/移除，以及向 future form host 交付安全引用。表单字段、OCR/AI 触发、建议采纳和批准属于另一个任务包。
- **仓库与 worktree**：`D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning`。
- **package**：`docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe`。
- **初始锚点**：`5b2db297ba9dd0f2a593f93dcaa91e9b4d509d03`；initial attempt 已是 `Gate=pass`、`lifecycle=frozen`、3/3 Ticket `SATISFIED`。证据见 S1:L30-L48、S1:L754-L755。
- **三个 session**：
  - **S1** `01a0012f-c343-77a0-b38e-8af4159ce0d7`，2026-08-14 16:51Z 起，完成 terminal 后的 req-align、UI upload/form 拆包、候选文档与首次 review，交接到实现 session。
  - **S2** `01a00156-2f48-7241-a471-44dfce868cb0`，2026-08-14 17:33Z 起，完成 upload-only UI、两轮 finding 修复、Owner 的 fail-closed 选择、合同传播和实际 commit `7941a077`；随后 closure review 仍有 1 个 P2 证据缺口，交接到 S3。
  - **S3** `01a004dc-c73b-7971-8b5a-ea92cbf128be`，2026-08-15 09:59Z 起，补 UI-CL-05 组件异步测试，修复 terminal-final review 发现并提交 `83576c99`；最后四条 review leaf 已启动，但 rollout 在收到 verdict 前结束。
- **最终状态**：initial Gate 仍为历史 `pass/frozen`；UI patch 没有新的 `gate pass/blocked/fail/defer` 结果。S3:L746 显示 review ledger 为 `Review phase: terminal-final`、`Status: in-progress`，S3:L766 只进入等待 reviewer 阶段。

## 2. 抽取口径

三个文件均按 JSONL 行流式扫描，没有整份加载。下面的 `S1:Lxxx`、`S2:Lxxx`、`S3:Lxxx` 是对应 rollout 文件的物理行号；时间采用 rollout 中的 UTC `timestamp`。

“决策点”定义为主控实际选择下一动作，或消费一个 worker/reviewer 回执后选择下一动作。纯读取、重复的状态播报、单纯测试命令和没有改变路线的轮询不另计；跨 session 的恢复与交接计入。命中计数按处境表优先级取一个主 slug；同一点明确同时符合两个或更多行时，另记多重命中，但不重复计入总数。

## 3. 决策点时间线与映射

| # | 时间 / session | 主控决定 | 主映射 | 多重命中或判断依据 |
| ---: | --- | --- | --- | --- |
| 1 | 16:51:53 S1 | 新 session 首轮只做 anchor 检查，不读恢复记录、不开始工作。 | `attempt.record.session-resumed` | 通过 fresh-session + 尚无本 session 动作的恢复边界命中 A3。S1:L13-L14、L47-L48。 |
| 2 | 16:52:03 S1 | 发现 `req-align` 的 0.3.0 路径失效，先定位本机可用 skill。 | `unmatched` | 这是 skill catalog/version 处理，不是 package state 或 attempt 恢复；S1:L19-L26。建议 `attempt.record.skill-catalog-drift`。 |
| 3 | 16:53:03–16:56:12 S1 | 确认 initial Gate 已冻结，把新增 UI 视为 terminal 后的行为合同 patch，进入 req-align，停止复用旧 Probe 验收。 | `attempt.gate.terminal-frozen` | 同时像 `attempt.rework.contract-changed`：terminal attempt 已冻结且合同发生变化；但实际先走 req-align/候选文档，没有按 A4 直接回 impl-planning 开 patch attempt。S1:L47-L48、L59-L60、L132-L133。 |
| 4 | 16:59:20 S1 | 接受 Owner 的拆包：本包只拥有上传，表单交给另一个任务包。 | `unmatched` | 是 package scope/ownership 决策；`attempt.route` 不在允许矩阵中。建议 `attempt.record.patch-scope-split`。S1:L231-L236。 |
| 5 | 17:03:55–17:11:43 S1 | 以深模块边界形成 Decision/Spec、contract design、patch plan 和 Ticket 候选，并保持 docs-only、未初始化 patch attempt。 | `unmatched` | 这是 req-align/impl-planning 的候选产物阶段，README 明确本表不覆盖这些线性 stage。S1:L368-L369、L476-L477。建议 `attempt.record.patch-candidate-pending`。 |
| 6 | 17:11:43 S1 | 把独立 closure review 设为 required，并派发只读 reviewer。 | `ticket.review.required-trigger` | 同时命中 `ticket.review.awaiting-reviewer`：已有 candidate implementation bundle，且 review scope 明确为 closure。S1:L476-L477。 |
| 7 | 17:21:50–17:24:25 S1 | 消费 reviewer 的 5 项 finding；4 项可在文档合同内修订，partial-failure 继续条件保留给 Owner。 | `attempt.disposition.findings-triage-pending` | 同时命中 `ticket.route.multiple-business-outcomes`：发现了两个不同产品结果，不能替 Owner 选择。S1:L520-L553、L628-L629。 |
| 8 | 17:28:08 S1 | 使用 verification-before-completion 校准收口，只报告“候选已形成但被产品选择阻塞”，不宣称 patch 已批准/实现/验收。 | `attempt.accept.completion-claim-unaudited` | 对应 F2 的 completion claim audit；S1:L655-L692。 |
| 9 | 17:31:15–17:36:19 S1 | 写 handoff prompt，复用同一 worktree，创建 S2，并要求新 session 先 anchor 再恢复。 | `attempt.record.checkpoint-missing` | 交接触发 G1；rollout 未出现显式 `recovery checkpoint` mutation，而是依赖 plan/continuation prompt，故是“应命中但动作偏离”的记录卫生点。S1:L704-L711、L738-L755、L788-L815。 |
| 10 | 17:33:54–17:38:07 S2 | S2 通过 anchor 后从 initial frozen/pass 与 patch candidate 恢复，限定 upload-only 写集并保护 dirty docs。 | `attempt.record.session-resumed` | S2:L7-L47、L121-L121；跨 session 恢复命中 A3。 |
| 11 | 17:39:59 S2 | 选择 `mode=implement`、`worker=main-session`、`review=required`，直接实现 bounded upload slice，不实现 `onReady`/继续语义。 | `ticket.investigate.no-carrier` | C1 的判断动作选择了 `implement-direct`；同时命中 `ticket.review.required-trigger`。已有 Decision/Spec/Plan 是直接实现理由，但没有 investigate carrier。S2:L175-L175。 |
| 12 | 17:49:06 S2 | 聚焦测试发现 selector 不应携带 `fileId`，由主控直接修复为位置 selector。 | `finding.fix.main-session-discovered` | 这是主控在本地验证中发现并直接修复的 finding，符合 E3 的“无需先过 reviewer”。S2:L375-L375。 |
| 13 | 17:52:36 S2 | 全量 Web 回归通过后派发独立 closure reviewer，范围只含新模块和 spec。 | `ticket.review.awaiting-reviewer` | `review=required / closure` 已明确；S2:L474-L474。 |
| 14 | 17:57:30–17:58:52 S2 | 收到 P1=2、P2=3，停止自审并交 fresh fixer 处理两项 P1 及低风险修正。 | `finding.fix.reviewer-returned` | reviewer 返回 finding 后 fresh fix，符合 E1；S2:L547-L593。 |
| 15 | 18:05:34–18:06:02 S2 | fixer 没有有效返回且安全停止，主控接管同一 bounded finding。 | `unmatched` | `finding.fix.reviewer-returned` 没有描述 finding fixer 的 infrastructure `BLOCKED/shutdown` 恢复；建议 `finding.fix.infrastructure-blocked`。S2:L665-L677。 |
| 16 | 18:11:01–18:13:01 S2 | P1 修正通过后启动同范围 fresh closure re-review。 | `finding.fix.reviewer-returned` | reviewer finding → 修复 → 同 scope 重审，符合 E1/C6 的组合；S2:L801-L817。 |
| 17 | 18:16:25–18:19:11 S2 | 复审把 P1 降为 0；修一个可直接修正的 P2，保留真实 DOM 交互证据缺口。 | `finding.disposition.grading-undecided` | P2 既可能是代码修正，也可能是授权/证据缺口；先分级再决定 fix 或保留。S2:L869-L877。 |
| 18 | 18:19:11–18:21:34 S2 | 补删除 pending 的 host 引用回归断言，再请求最终独立复审。 | `finding.fix.reviewer-returned` | 继续消费 reviewer finding 并回到同范围 review；S2:L923-L968。 |
| 19 | 18:28:50–18:30:09 S2 | 最终 closure review 留下 P2 异步 `onChange` 证据缺口，拒绝称 patch closed，等待 Owner 的 partial-failure 选择。 | `attempt.accept.completion-claim-unaudited` | 同时命中 `attempt.review.terminal-coverage-incomplete`：review/证据未闭合，不能进入 terminal claim。S2:L1036-L1080。 |
| 20 | 22:12:12–22:18:58 S2 | 把 mixed success/failure 的含义解释给 Owner，并请求选择“成功子集可继续”或“失败项必须重试/移除”。 | `ticket.route.multiple-business-outcomes` | C3 的判断点是两个合理业务结果；在结论前不实现 `onReady`。S2:L1108-L1133。 |
| 21 | 22:19:21–22:26:04 S2 | Owner 同意 fail-closed；先把新语义传播到 Decision/Spec/contract/Plan/Ticket，再实现 strict `onReady` gate。 | `attempt.rework.contract-changed` | 同时命中 `ticket.route.sources-conflicting`：旧候选合同与 Owner 新选择不一致，先回 req-align 更新 Spec 再实现。S2:L1154-L1234。 |
| 22 | 22:27:51–22:31:38 S2 | bookkeeper 只写入 2/5 文档，继续派一个窄范围 writer 补 3 个从属文档。 | `package.record.intake-backlog` | 有待落账队列，进入 G2；S2:L1321-L1329。 |
| 23 | 22:35:42–22:38:56 S2 | 第二个窄 writer 0/3 写入后停止，主控改为直接做 3 个文件的机械性文字同步。 | `package.record.intake-backlog` | 仍是同一积压队列的 drain；但实际执行者从 bookkeeper 变为 main session，说明 G2 的唯一动作不足以描述失败后的转派。S2:L1425-L1433。 |
| 24 | 22:38:56–22:40:18 S2 | 合同传播完成，启动 fresh closure review。 | `ticket.review.awaiting-reviewer` | 文档合同已更新，review 是下一道独立门；S2:L1474-L1493。 |
| 25 | 22:44:47–22:50:13 S2 | reviewer 因收束中断没有有效回执，重新缩小范围启动 fresh reviewer。 | `ticket.review.awaiting-reviewer` | 同时命中 `attempt.review.terminal-coverage-incomplete`；原 review 不可采信，不能拿主控自检替代独立 review。S2:L1493-L1540。 |
| 26 | 09:22:32–09:22:59 S2 | 明确当前应做 closure review，不是 terminal；Owner GO 后启动 closure review。 | `attempt.accept.completion-claim-unaudited` | 同时命中 `attempt.review.terminal-coverage-incomplete`；S2:L1627-L1641。 |
| 27 | 09:27:50 S2 | 因 review 工具要求 immutable base/head，建立不挂分支的临时 snapshot，保持真实 branch 不变。 | `unmatched` | 这是 review 比较点/临时 snapshot 的 Git 机制，42 行没有对应的动作；建议 `attempt.review.temporary-comparison`。S2:L1769-L1769。 |
| 28 | 09:33:05–09:36:32 S2 | Owner 明确授权 commit 后，只提交 UI/合同 7 个文件，保留 package state/execution 脏项，再以 `7941a077` 建 fresh ReviewRun。 | `unmatched` | commit 授权、staged-scope 与 review head 固定不属于现有 42 行；建议 `attempt.record.review-head-fixed`。S2:L1876-L1974。 |
| 29 | 09:42:15–09:44:52 S2 | closure review 6/7 通过、唯一 P2 仍是真实组件异步测试缺口；拒绝 terminal，下一步只补该测试。 | `attempt.accept.completion-claim-unaudited` | 同时命中 `attempt.review.terminal-coverage-incomplete`；S2:L2049-L2084。 |
| 30 | 09:57:56–10:03:37 S2 | 按 Owner 指示把剩余 UI-CL-05 测试交接给 S3，修复后直接 terminal-final，不再单独 closure。 | `attempt.record.checkpoint-missing` | 第二次交接触发 G1；handoff 依赖 continuation 中的 commit/review 状态，仍没有显式 `recovery checkpoint` 写入。S2:L2099-L2105、L2138-L2167、L2186-L2200。 |
| 31 | 09:59:47–10:00:16 S3 | S3 通过 anchor，接受 `7941a077`、closure 6/7 与唯一 UI-CL-05 blocker。 | `attempt.record.session-resumed` | S3:L7-L39。 |
| 32 | 10:02:05 S3 | preflight 的 package validator 报 `04-ui-upload-acceptance.md` 缺 Ticket ID；主控把它视为既有 dirty-record/tool 问题，继续读取最小 checkpoint。 | `package.record.state-missing` | `package validate` 已失败，命中 A1；但 A1 规定只能 validate/init，实际选择了保留并继续，属于“命中但动作偏离”。S3:L52-L65。 |
| 33 | 10:04:06–10:04:22 S3 | 发现现有 spec 只有 reducer/SSR，确认需要真实组件异步 `onChange` 证据；先检查既有 DOM runtime，不新增依赖，必要时停在 blocker。 | `unmatched` | 证据不存在，语义上属于 verify，但“测试载体/运行时缺失”没有现成行。建议 `ticket.verify.component-test-carrier-missing`。S3:L117-L128。 |
| 34 | 10:05:25 S3 | 按 Owner 授权派 fresh `@luna-worker` 修复 UI-CL-05，写集只含同目录 spec，review 交给后续 terminal-final。 | `finding.fix.reviewer-returned` | UI-CL-05 是既有 review finding，派 fresh fixer，符合 E1；S3:L128-L165。 |
| 35 | 10:09:36–10:10:30 S3 | 第一 worker 因无 jsdom/happy-dom/renderer 返回 BLOCKED；主控在现有 React 19/ReactDOM 中找到 bounded fake-DOM 方案，派 fresh retry。 | `unmatched` | 这是 infrastructure `BLOCKED` 而非 C12 所说的 business `BLOCKED`；建议 `finding.fix.infrastructure-blocked`。实际选择了 fallback，正好显示现行表没有这个分支。S3:L240-L254。 |
| 36 | 10:20:10–10:23:59 S3 | 第二 worker 以 fake-DOM 完成 8/8；主控复核写集、固定 `db063b46`，启动四条 terminal-final review leaf。 | `ticket.review.awaiting-reviewer` | 同时命中 `attempt.review.terminal-coverage-incomplete`；S3:L365-L414、L463-L463。 |
| 37 | 10:26:06 S3 | 四条 reviewer 首个窗口未返回，继续有界等待，不提前判 PASS。 | `attempt.review.terminal-coverage-incomplete` | terminal coverage 尚未齐全，符合 F3；S3:L481-L481。 |
| 38 | 10:28:48–10:30:06 S3 | 四条 review 回执齐全后核验 P1/P2 findings，决定只对 upload-only 范围安排返工。 | `ticket.review.awaiting-reviewer` | 同时承接 F3 的 terminal coverage 完成到 findings consumption；S3:L501-L529。 |
| 39 | 10:31:19–10:39:49 S3 | 确认 safe-ref、错误脱敏、timer/unmount 和重复校验错误问题，派一个 worker 返工并等待其结果。 | `finding.fix.reviewer-returned` | reviewer findings → fresh fixer，符合 E1；S3:L565-L648。 |
| 40 | 10:40:26–10:40:40 S3 | 返工 worker 的 4/4 修复通过，但同 revision typecheck 暴露 11 个类型诊断，继续把纯类型修复回派给同一 worker。 | `finding.fix.main-session-discovered` | 类型诊断是主控验证新发现，语义接近 E3；但实际复用了同一 worker，而 E3 的默认动作是 fresh fixer，边界不完全匹配。S3:L648-L671。 |
| 41 | 10:43:29–10:43:56 S3 | 类型修复、15/15 focused、lint、Prettier、diff check 通过后，提交仅两个 UI 文件为 `83576c99`，重建四条独立 terminal-final review。 | `attempt.review.terminal-coverage-incomplete` | 新 head 必须重新 review，不能复用上一轮 verdict；S3:L702-L723、L725-L726。 |
| 42 | 10:44:54–10:45:34 S3 | 把 review ledger 置为 terminal-final/in-progress，启动 Track A/B/C/D，等待四个 verdict。 | `attempt.review.terminal-coverage-incomplete` | review 仍未完成，不能判 Gate；S3:L740-L766。 |

## 4. 读数

### 4.1 总读数

| 指标 | 数值 |
| --- | ---: |
| 决策点总数 | 42 |
| 有主 slug 命中 | 34 |
| `unmatched` | 8 |
| 命中率 | 34 / 42 = **81.0%** |
| 多重命中点 | 11 |
| 主命中中 `cli` basis | 2（A1、A4） |
| 主命中中 `prose` basis | 32 |

命中率按主 slug 计算；多重命中只增加诊断信息，不把一个决策点复制成两个样本。

### 4.2 按环节的主命中分布

| 环节 | 命中次数 |
| --- | ---: |
| `record` | 8 |
| `readiness` | 0 |
| `investigate` | 1 |
| `route` | 1 |
| `implement` | 0 |
| `fix` | 7 |
| `verify` | 0 |
| `review` | 9 |
| `accept` | 4 |
| `rework` | 1 |
| `disposition` | 2 |
| `gate` | 1 |
| **合计** | **34** |

最密集的是 `review`、`record`、`fix`；`readiness`、`implement`、`verify` 没有主命中。直接实现被 C1 的 `implement-direct` 动作吸收，所以没有单独的 `implement` 主命中；本地验证则多数没有形成表内的 `verify` subject/载体。

### 4.3 多重命中清单

以下 11 个点同时符合多个候选，实际按表内优先级保留主 slug：

1. #3：`attempt.gate.terminal-frozen` + `attempt.rework.contract-changed`。
2. #6：`ticket.review.required-trigger` + `ticket.review.awaiting-reviewer`。
3. #7：`attempt.disposition.findings-triage-pending` + `ticket.route.multiple-business-outcomes`。
4. #11：`ticket.investigate.no-carrier` + `ticket.review.required-trigger`。
5. #19：`attempt.accept.completion-claim-unaudited` + `attempt.review.terminal-coverage-incomplete`。
6. #21：`attempt.rework.contract-changed` + `ticket.route.sources-conflicting`。
7. #25：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。
8. #26：`attempt.accept.completion-claim-unaudited` + `attempt.review.terminal-coverage-incomplete`。
9. #29：`attempt.accept.completion-claim-unaudited` + `attempt.review.terminal-coverage-incomplete`。
10. #36：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。
11. #38：`ticket.review.awaiting-reviewer` + `attempt.review.terminal-coverage-incomplete`。

主要重叠不是表内“同组取首个”的小差异，而是 `review` 与 `accept/gate`、以及“合同变化”与“业务路由”跨组重叠。优先级能稳定选主 slug，但没有消除另一个候选的解释价值。

## 5. `unmatched` 清单

| 发生点 | 真实处境 | 建议 slug | 为什么这样命名 |
| --- | --- | --- | --- |
| #2 | 旧 skill 路径不存在，先发现 0.3.1 安装位置。 | `attempt.record.skill-catalog-drift` | 对象是 attempt，动作是恢复记录/工具入口；`attempt.record` 在矩阵内。 |
| #4 | 上传与表单的 package ownership 由 Owner 拆开。 | `attempt.record.patch-scope-split` | 当前没有已初始化的 patch Ticket，不能伪造 `attempt.route`；先作为 attempt record 保留 scope 决策。 |
| #5 | req-align/impl-planning 形成 candidate 文档但尚未初始化 attempt。 | `attempt.record.patch-candidate-pending` | 这是候选生命周期的记录状态，不是 Ticket readiness 或 implementation。 |
| #15 | finding fixer 未返回/安全停止，主控接管。 | `finding.fix.infrastructure-blocked` | finding/fix 是允许组合，状况明确区分业务 BLOCKED 与测试/执行基础设施 BLOCKED。 |
| #27 | review 因缺少 immutable head 建立临时 snapshot。 | `attempt.review.temporary-comparison` | review 是 attempt 活动，比较点准备不是 Gate 或 Ticket acceptance。 |
| #28 | Owner 授权后只提交目标文件并固定真实 review head。 | `attempt.record.review-head-fixed` | commit/staged-scope 是记录层的 review anchor，当前表没有提交/比较点准备行。 |
| #33 | 组件级异步证据不存在，现有环境没有 DOM test carrier。 | `ticket.verify.component-test-carrier-missing` | 六条判定线中“证据不存在”归 `verify`，且 Ticket/verify 在矩阵内。 |
| #35 | finding fixer 因缺少 jsdom/renderer 返回 infrastructure BLOCKED，随后发现 fake-DOM 后 retry。 | `finding.fix.infrastructure-blocked` | 与 #15 是同一缺行的第二次真实命中，不应误记成 `ticket.implement.worker-blocked`。 |

建议 slug 均使用小写、三段式和允许矩阵；没有修改 YAML 或设计文档。

## 6. 跳步检测

### 6.1 没有调查载体就直接进入实现：1 次

- **S2:L175**：preflight 已有 Decision/Spec/Plan，主控直接选择 `mode=implement`，没有 `mode=investigate` 或新的 evidence。它符合 C1 允许的 `implement-direct` 分支，但没有看到对应的机器轨迹 `reason`。
- S1 的 req-align/patch planning 和 S3 的 UI-CL-05 `mode=fix` 不计入此项：前者不是 `dev-with-track` implementation，后者消费的是既有 review finding。

### 6.2 worker 返回后未记 evidence 就推进：11 批

按处境表的定义，检查的是 worker/reviewer 返回之后是否出现 `evidenceIndex` 对应的 `evidence add` 或等价前沿 mutation。三个 rollout 中没有找到 `evidence add` 命令；以下 11 批均是 return 后直接进入下一动作的可观测转移：

1. S1:L553 → L628：首次 reviewer findings → 文档合同修订。
2. S2:L547 → L593：closure findings → fresh fixer。
3. S2:L665-L677：fixer 未返回/停止 → 主控接管。
4. S2:L869 → L877：复审 P2 → 直接修复一个、保留一个证据缺口。
5. S2:L1038-L1076 → L1108：closure P2 → Owner 产品选择。
6. S2:L1321 → L1329：bookkeeper 2/5 → 窄范围补写。
7. S2:L1425 → L1433：窄 writer 0/3 → 主控机械同步。
8. S3:L240 → L254：第一 worker BLOCKED → fresh retry。
9. S3:L365 → L392-L414：第二 worker PASS → commit/review 准备。
10. S3:L501-L524 → L529-L565：terminal findings → 返工 worker。
11. S3:L648 → L664-L671：返工 PASS 后 typecheck diagnostics → 再次派修复。

这不是说这些回执没有自然语言 evidence；它们大多有测试结果、finding 或路径说明。结论是：按本次回放能观察到的处境表 record contract，没有看到把这些直接证据落进 `evidenceIndex` 的动作。由于 rollout 运行的是旧版 prose/bookkeeper 形态，见第 8 节，这个读数不能直接外推到新 CLI 自动记账实现。

### 6.3 未经独立 review 就宣称完成或 satisfy：0 次主控事件

- 没有发现本案例中的 `ticket satisfy` 调用。
- S1:L692、S2:L1080、S2:L1601、S2:L2084、S3:L414 都明确区分 scoped implementation/local verification 与 package closed/terminal Gate。
- worker 回执中的“本回合 closed”（例如 S3:L697）都明确限定为 scoped fix，且 `review_state=PENDING_REVIEW` 或仍待 terminal review；不计为主控绕过 review 的完成声明。

### 6.4 已 `SATISFIED` Ticket 被新证据触及时的处置：0 次

initial attempt 的 3/3 Ticket 在 S1:L54、S2:L121 仍是历史 `SATISFIED`；新增 UI 是一个新 patch contract，主控没有声称它证伪 DPAP-01～03 的原 claim，也没有调用 `needs-revalidation`、`evidence invalidate` 或 `ticket retire`。因此 D1 未被触发，按“新需求/新 patch”分离处理是合理的；但也说明本案例没有实际检验 D1 四路处置。

### 6.5 额外的交接记录信号

两次 handoff 都依赖 continuation prompt 传递状态。S3 preflight 的输出显示 `Active Checkpoints` 为 `none`（S3:L65），同时 continuation 又声明从 active checkpoint 恢复（S3:L34）。这不是上述四项跳步计数之一，但它是 `G1` 的直接风险：跨 session 可恢复性主要靠 prompt，而不是可查询的 durable checkpoint。

## 7. 表本身的问题

1. **A4 对 terminal 后新需求的边界过窄。** S1 明确 initial attempt 已 `pass/frozen`，但新增 UI 不是继续推进旧 attempt，而是先 req-align、拆 ownership、等待 partial-failure 业务选择，再进入实现。A4 的“只能 fail closed，回 impl-planning 开 patch attempt”能识别冻结，但没有表达“新需求先完成 contract alignment、暂不初始化 patch attempt”的合法路径。建议新增状况或把 A4 的适用条件限定为“继续旧 attempt”。

2. **`finding.fix` 没有 infrastructure BLOCKED 分支。** S2、S3 都出现 finding fixer 因测试运行时/worker 状态而 `BLOCKED`，随后在新事实出现后 retry。C12 只覆盖 `ticket.implement` 的业务 BLOCKED，不能合法映射 finding/fix；这是本案例最明确的 unmatched 缺口。

3. **reviewer 不可用没有明确处境。** S2 出现 reviewer 超时、shutdown、无有效回执，主控要求收束后重新缩小范围派 reviewer（S2:L1493-L1540）。`awaiting-reviewer` 和 `terminal-coverage-incomplete` 可以解释现状，但没有区分“仍在正常等待”和“本 ReviewRun 已不可采信、必须重开”的动作。建议增加 `attempt.review.reviewer-unavailable`。

4. **worker PASS 后的本地验证反例边界不清。** S3 返工 worker 报告 4/4 closed 后，同 revision typecheck 才暴露 11 个类型诊断（S3:L648-L671）。这接近 E3，但 E3 的默认动作是 fresh fixer；真实流程把同一 worker 继续用于纯类型修复。表需要明确“主控验证新 finding”与“是否允许复用 worker”的边界。

5. **A3/G1 的推导输入无法覆盖 prompt-only handoff。** 表把 active checkpoint 作为恢复输入；真实 rollout 的 handoff prompt 声明有 checkpoint，但 S3 实际读取到 `activeCheckpoints=none`。如果 checkpoint 没落盘，应该由 G1 先点名；如果 prompt 是合法的临时交接载体，则 A3 的输入定义需要显式包含它，否则推导器无法重建这个处境。

6. **partial-failure 路由落在对象矩阵的缝隙。** 业务选择发生在 patch candidate/attempt 层，但 `attempt.route` 不允许；若把它归为 `ticket.route`，当时又尚未初始化 patch attempt。C3 能表达“多个合理业务结果”，但不能表达这个 candidate subject 的生命周期。建议先决定是否把 patch candidate 视作 Ticket subject，或增加允许矩阵/record 过渡规则。

7. **C8 的 prose 规则被真实流程反复绕过，但没有即时信号。** 11 批 return→next-action 都没有可观察的 `evidence add`，而主控仍能继续实现、修复和 review。表的判断是对的，但 basis 是 `prose`，旧版工具也没有阻断或自动写入；如果不把这一读数接入 renderer/record check，C8 只是事后解释，不能变成当场缺席信号。

## 8. 版本干扰与结论边界

- S1 首先尝试读取 `impl-package\0.3.0\skills\req-align\SKILL.md`，路径不存在，随后发现并读取 `0.3.1`（S1:L15-L26）。S2、S3 的 `execution-preflight`、`do-review`、`verification-before-completion` 也来自缓存的 0.3.1。
- 这批 rollout 没有处境表 renderer、`trail.jsonl`、三段式 `situation` slug 或显式 `evidence add` 的运行记录；主控使用自然语言 continuation、package 文档和旧版 bookkeeper 回执。`trial-readout.md` 也明确这是 §19 bounded write unit 之前的形态：主 thread 给自然语言更新，bookkeeper 自己定位写入位置。
- 因此，本报告可以可靠评价“真实流程行为与当前 42 行设计的语义相似度”，但不能把 unmatched 直接解释为新版 CLI 失败，也不能把 11 次未见 `evidence add` 解释为新版自动记账漏写。
- 同理，A1/A4 的 `cli` basis 命中发生在旧版 validator/frozen package 上；`C1/C3/E1/F3` 等 `prose` 行被本案例支持，只能作为一个真实样本的 observed signal，不能仅凭本案例把 basis 改成 `observed`。
- 初始 Gate 的 `pass/frozen` 是旧 Probe 的 Gate，不是 UI patch 的终态 Gate；S3 最后只启动了新的 terminal-final ReviewRun，未产生 verdict。上述版本/阶段干扰不应据此修改处境表或 YAML。

## 9. 结论

这个案例证明处境表对“交接恢复、review/finding 循环、拒绝过早收口、合同变更、Owner 业务选择、terminal coverage”有较高覆盖；34/42 的主命中和 11 个多重命中也证明优先级确实能稳定压缩复杂流程。

最值得保留的反例是：表能识别 review/fix 的大循环，却还没有给 infrastructure BLOCKED、reviewer 不可用、prompt-only checkpoint 和 patch-candidate route 留出精确位置。另一方面，表中的 `record` 规则已经指出了真实痛点：旧版流程中 worker 返回的自然语言证据很丰富，但 evidence indexing 没有形成可见的机械动作。后续若扩展设计，应先补这些处境的读数和命名，再决定是否改变 basis 或允许矩阵；本案例本身不授权修改设计。

## 附：rollout 文件索引

- S1：`C:\Users\Xiao\.codex\sessions\2026\08\14\rollout-2026-08-14T18-51-42-01a0012f-c343-77a0-b38e-8af4159ce0d7.jsonl`
- S2：`C:\Users\Xiao\.codex\sessions\2026\08\14\rollout-2026-08-14T19-33-40-01a00156-2f48-7241-a471-44dfce868cb0.jsonl`
- S3：`C:\Users\Xiao\.codex\sessions\2026\08\15\rollout-2026-08-15T11-59-33-01a004dc-c73b-7971-8b5a-ea92cbf128be.jsonl`
