# 案例 2d：DMI-05 后端收口与统一导入 UI 规划

## 整体判断

本回放覆盖案例 2 的最后一片（4/4），共 65 个主控决策点；40 个命中现有处境表主 slug，25 个明确 unmatched，命中率为 61.5%，另有 13 个决策点存在多重命中。DMI-05 后端 Ticket 在本片末段已从 BLOCKED → SATISFIED，Attempt frozen、Gate pass；随后启动的统一 DATEV 导入 UI 包只完成 req-align 与 implementation planning，尚未初始化执行状态，因此本片涉及的整体工作不能称为 closed。

这里的“完成”只指本报告的 replay/extract/mapping 阶段；DMI-05 的后端收口、统一 UI 包的规划收口和整个产品的 UI 人工验收是三个不同边界。当前没有需要 Owner 立即裁决的操作；统一 UI 包的后续执行仍依赖 DMI 代码合入、bundle review、execution preflight 和 state init。

## 1. 案例概况

- **本片在案例 2 中的位置**：案例 2 共 9 个 session；本片是时间最晚、含收口的第 4/4 片。具体决策只取本文件内的记录，前三片的原始过程不用于补猜。
- **仓库与 worktree**：主要仓库为 D:\CodeSpace\kaispan-dev。本片涉及：
  - D:\CodeSpace\kaispan-dev\.worktrees\260812-datev-mandant-profile-import-planning
  - D:\CodeSpace\kaispan-dev\.worktrees\260813-datev-pdf-ai-form-prefill-planning
- **package**：
  - docs/domains/finance-assistant/implementations/2026-08-11-datev-mandant-profile-import
  - docs/domains/finance-assistant/implementations/2026-08-12-datev-pdf-ai-form-prefill-probe
- **本片 session**：
  - 421b50d6（完整 session id：01a000a4-abb7-7bf3-9ceb-4abb421b50d6），时间范围 2026-08-14T14:23:20.317Z → 2026-08-14T16:06:27Z。完成 DMI-05 的第一轮 blocker 修复、terminal-final FAIL 归并、D3/S7 对齐和 handoff。
  - 9a80c958（完整 session id：01a000ff-a81d-71b0-9746-7c509a80c958），时间范围 2026-08-14T15:59:12Z → 2026-08-15T10:38:22.838Z。先恢复 DMI-05 并完成修复、集成验证、复审和 Gate；再处理统一导入 UI 包的 req-align 与 planning。
- **本片整体时间范围**：2026-08-14T14:23:20.317Z → 2026-08-15T10:38:22.838Z。两个 session 的时间有交叠，不能把它们误读成严格串行的两个时间段。
- **最终状态**：
  - DMI-05：7837b2e9 上 terminal-final review PASS；ER-014、逐 claim audit、state 写入完成；Ticket SATISFIED，Attempt frozen，Gate pass。后续用户又明确确认这只是后端闭环，不代表已有 UI 的人工验收或可直接发布。
  - PDF/AI Probe 统一 UI 包：6 份规划 artifact 已形成，统一导入 Decision/Spec 已通过，patch plan 与 DPAP-04 已形成；没有实施业务代码，也没有 state init，package 仍未 closed。

## 2. 抽取口径

时间采用输入 JSONL 的 UTC ts；定位使用输入的 seq，不把 rollout 原始行号混入。决策点定义为主控实际选择下一动作，或消费 worker/reviewer 回执后改变路线、状态、证据、交接或 Gate 的动作。纯读取、重复播报、同一 reviewer 的无新结果轮询和单纯的成功测试命令不单独计点；测试失败导致换载体、返工、重开比较点或改变证据边界时计入。

本片的 tool output 和部分普通工具参数按抽取规则截断。凡是只能确认“主控采取了某动作”、但不能确认隐藏 state 条件或 evidenceIndex 是否在该动作前已写入的地方，报告在跳步检测中标 insufficient-evidence，不把截断当作事实。

## 3. 决策点时间线与映射

| # | 时间 / session | 主控决定 | 主映射 | 判定依据、次命中或证据边界 |
| ---: | --- | --- | --- | --- |
| 1 | 14:26:23 / 421b50d6，seq 6252 | 按现有 reviewer finding 派两个不重叠写集的 fresh fix worker，review required，之后由 owner 串行验证并做 closure review。 | finding.fix.reviewer-returned | 本片明确是“现有 finding”；该 finding 的原始 reviewer 回执在前片，来源本身 insufficient-evidence，但本片的 fresh fixer 动作符合 E1。 |
| 2 | 14:32:50，seq 6314 | 两个 worker 都 DONE 后，不宣称 closed，转入 owner 串行 diff/回归/evidence/closure review。 | ticket.review.awaiting-reviewer | implement 已返回且 review required，主命中 C6；同时像 ticket.record.evidence-unfiled，因为 worker 直接证据的即时 index 状态不可见。 |
| 3 | 14:33:46，seq 6325 | 合并验证发现 adapter regression fixture 的编译型 finding，先暂停 closure review。 | finding.fix.main-session-discovered | finding 是 owner 验证新发现，符合 E3。 |
| 4 | 14:33:48，seq 6326 | 为该 fixture 类型 finding 派 fresh fixer，只允许改测试 fixture。 | finding.fix.main-session-discovered | 主控直接消费自己发现的 finding；写集和 fresh invocation 均显式限定。 |
| 5 | 14:38:50，seq 6346 | fixture 修复后重新跑 4 个 spec、typecheck、lint，再确认授权写集。 | unmatched | 这是“fix 返回后的 owner 统一回归”处境，现有 verify 行没有描述该顺序。建议 ticket.verify.post-fix-regression-pending。 |
| 6 | 14:41:06，seq 6375 | 只提交 4 个业务文件，把 closure review 绑定到不可变 revision，保留 package metadata unstaged。 | unmatched | 比较点固定和 staged-scope 保护没有现成行。建议 attempt.review.comparison-head-fixed。 |
| 7 | 14:43:07，seq 6394 | 同 revision 的 API/focused/质量检查通过后，尝试 canonical loopback PostgreSQL integration；不可达则保留 blocked。 | ticket.accept.acceptance-edge-held | 已有部分证据但 acceptance 仍被数据库证据卡住，符合 C13；数据库载体缺失也使该点接近 readiness。 |
| 8 | 14:43:52，seq 6404 | 以固定 base/head 启动具名 finding 的 closure review，并把 Safety 纳入同一 scoped reviewer。 | ticket.review.awaiting-reviewer | C6；同时触发 ticket.review.required-trigger，因为 review required 与安全/原子性 seam 均明确。 |
| 9 | 14:49:21，seq 6435 | reviewer 对具名 precommit finding 返回 PASS 后，更新 ReviewRun ledger，并写入 Attempt/Execution Record/state。 | ticket.record.evidence-unfiled | reviewer 的直接证据需要落账，符合 C8。 |
| 10 | 14:51:00，seq 6446 | 继续做同 revision claim audit 和 terminal-final review；数据库端口不可用时按记录停止，不宣称 Gate。 | attempt.accept.completion-claim-unaudited | F2；terminal coverage 也尚未完整，次命中 attempt.review.terminal-coverage-incomplete。 |
| 11 | 14:51:20，seq 6452 | 用 ER-012 固化同 revision 验证、数据库失败和 closure PASS，再继续 claim audit/终审。 | attempt.record.checkpoint-missing | 长任务收口前写 durable execution record/checkpoint，符合 G1；同时包含 evidence record 写入。 |
| 12 | 14:51:51，seq 6458 | 保持 Attempt BLOCKED，拒绝复用旧 revision 的数据库绿证据，进入完整终审前的 claim-to-evidence 边界审计。 | ticket.accept.acceptance-edge-held | C13；ER-012 已有代码证据，但 acceptance edge 仍未释放。 |
| 13 | 14:52:35，seq 6475 | 以旧终审同一 immutable base 对当前 head 启动 Track A/B/C + Safety 四轨独立只读 review。 | attempt.review.terminal-coverage-incomplete | terminal coverage 尚未完成，符合 F3。 |
| 14 | 14:59:29–15:03:43，seq 6509、6512、6521、6530 | Track B 先返回 P1/P2 候选时不先裁决，保留其余三轨并继续等待完整 topology。 | attempt.review.terminal-coverage-incomplete | 单轨回执不能替代 terminal coverage，符合 F3。 |
| 15 | 15:04:42，seq 6544 | 四轨均返回后归并至少 7 个独立 P1 候选，保持 package/DMI-05 BLOCKED，不在本 session 擅自扩大实现。 | attempt.disposition.findings-triage-pending | 接近 terminal Gate 且 findings 尚未完成分流，主命中 E5；P1/P2 分级也构成 finding.disposition.grading-undecided 次命中。 |
| 16 | 15:05:56，seq 6562 | 合并跨轨重复的 orphan claim，标记 M6 合同冲突待 Owner，先对唯一规范项做 source recheck。 | finding.review.source-recheck-pending | E2；同时仍处于 findings triage，次命中 E5。 |
| 17 | 15:09:18，seq 6585 | source recheck 证明 frozen vocabulary 规则可执行，把终审和逐 AC audit 写入 ER-013，继续保持 BLOCKED。 | attempt.disposition.findings-triage-pending | 规范 finding 已消费但其余 findings 尚待分流，主命中 E5；ER/evidence 落账使 ticket.record.evidence-unfiled 同时成立。 |
| 18 | 15:11:11，seq 6619 | 将 Gate 从旧 revision 的状态更新为当前 head 的 blocked，不写 PASS。 | attempt.gate.verdict-undecided | Gate verdict 的选择符合 F6；旧 Gate 的 comparison revision 不匹配，但不是 F7 的 pass-only 条件。 |
| 19 | 15:12:03，seq 6629 | 修正 canonical review ledger 顶部的 pending/in-progress 元数据，使其与正文 terminal FAIL 一致。 | unmatched | 属于 review ledger provenance 卫生，现有 record 行没有“正文与头部生命周期不一致”。建议 attempt.record.review-ledger-stale。 |
| 20 | 15:48:25，seq 6646 | 根据 Owner 口径把 M1/M2/M6 统一为字段驱动的多材料 identity mapping，并把 Scope identity 一致性列为 blocking 修复。 | ticket.route.multiple-business-outcomes | C3 的 Owner 选择优先于来源冲突解释；同时像 ticket.route.sources-conflicting，因为前一轮合同对 M6 的要求相互冲突。 |
| 21 | 15:50:07–15:56:58，seq 6678、6731、6754 | 把 M6 语义落入 D3/S7/contract，健壮 hydration/typed client/tenant 重复逻辑留作 backlog，随后进入最小业务修复。 | ticket.route.sources-uniquely-decide | Owner 已解决路线歧义，按 C4 进入 implement-and-reverify；同时是 attempt.rework.contract-changed 的一次真实候选，因为 contract 已发生变化。 |
| 22 | 15:57:07，seq 6761 | 当前 session 只收口文档设计，恢复临时业务改动，使用 handoff 把 package/checkpoint/保护边界交给新 session。 | attempt.record.checkpoint-missing | 跨 session handoff 触发 G1。 |
| 23 | 15:58:50–16:04:20，seq 6807、6812 | 首次 handoff 的新 thread 重命名失败，停止继续实现并等待 Owner 重新触发。 | unmatched | 这是 handoff bootstrap 失败，不是 checkpoint 内容缺失。建议 attempt.record.handoff-bootstrap-failed。 |
| 24 | 16:04:27–16:05:15，seq 6815、6826 | Owner 表示 child 已就绪后，先核对 anchor PASS，再发送 continuation，并做一次理解回执审计。 | attempt.record.session-resumed | A3 的恢复顺序明确；没有把收到 continuation 当作 closed。 |
| 25 | 16:06:27，seq 6832 | handoff 成功，child 已匹配 worktree/HEAD/branch 并正式接管业务 blocker、PG 验证和终审。 | attempt.record.session-resumed | 跨 session 恢复完成，符合 A3；本片只记录本次 handoff，不推断前片交接细节。 |
| 26 | 16:05:23，seq 6843 | 新 session 从 ER-013/checkpoint 恢复，按既定 blocker 修复、同 revision 验证、claim audit、terminal review、Gate 顺序推进。 | attempt.record.session-resumed | A3；恢复输入来自本片中的 continuation 与 package entry point。 |
| 27 | 16:08:31，seq 6904 | 并发派 3 个 bounded fresh fix：approval/provenance/hydration、M6 identity、frozen publication vocabulary；全部 review required。 | finding.fix.reviewer-returned | 3 个任务都来自前一轮 review 的 accepted business-code blockers，符合 E1。 |
| 28 | 16:09:11–16:15:00，seq 6919、6998 | 选择 local-test profile，发现 5433 受本机端口限制后改用 process-scoped 55433，不改配置文件、不碰远程库。 | unmatched | 当前表没有“验收证据载体/端口 profile 不可用后选择等价本地载体”。建议 attempt.readiness.integration-carrier-unavailable。 |
| 29 | 16:16:11，seq 7006 | M6 worker 返回 focused 27/27、typecheck/lint 通过；主控只消费该局部 DONE，整体仍保持 BLOCKED。 | ticket.record.evidence-unfiled | worker 直接证据返回后需要归入 package evidence；即时 index 是否已写入受截断影响。 |
| 30 | 16:20:04，seq 7031 | frozen vocabulary worker 返回 focused 3/3；其 temporary typecheck 单点先等待共享 approval seam，不提前判失败。 | ticket.record.evidence-unfiled | 仍是 worker 回执先被消费的记录点；具体 evidenceIndex 时序 insufficient-evidence。 |
| 31 | 16:31:15，seq 7092 | 三个 seam worker 全部返回后，owner 串行审 diff/replay/事务语义，再跑统一 focused、质量和 PG 验证，之后独立 closure review。 | ticket.review.awaiting-reviewer | C6 的 review required 路径优先；同一回执批次也命中 C8 的 evidence-unfiled。 |
| 32 | 16:32:21–16:35:30，seq 7119、7135 | 发现 dotenv 顺序使第一次 integration 仍打到 5433，改为 base→loopback 的进程级覆盖并重跑 canonical runner。 | unmatched | 与 #28 同一类环境 readiness 缺口，建议仍用 attempt.readiness.integration-carrier-unavailable。 |
| 33 | 16:37:48–16:39:27，seq 7144、7159 | PG lane 可用但 11 个 DATEV integration 失败；定位为 hydration 把 parser 合法空文本误判为非空字段，最小放宽允许为空的字段后重跑。 | finding.fix.main-session-discovered | owner 从同 revision integration 新发现 finding，符合 E3。 |
| 34 | 16:44:26–16:48:59，seq 7208、7247 | 继续把 dynamic frozen reference、fault mapping、非 active attempt contract 码和 committed_unverified resume 语义对齐到 integration fixture，再只跑 clean/predecessor lanes。 | finding.fix.main-session-discovered | 这是验证暴露的 implementation/fixture finding，由主控限定修正并重验，符合 E3。 |
| 35 | 16:52:51–16:55:05，seq 7296、7338 | 发现 approvedPayload 只有 JSON parse 没有领域结构校验，新增最小结构/hash/enum fail-closed validation 和 synthetic fixture。 | finding.fix.main-session-discovered | 具名 ER-013 P1 的剩余缺口由主控验证发现并直接进入 bounded fix，符合 E3。 |
| 36 | 16:56:47–17:02:21，seq 7369、7402 | approvedPayload 回归通过后重跑 canonical migration lane；clean/predecessor、DB、API DATEV 11/11 通过，转入 root quality 和 contract drift checks。 | ticket.accept.acceptance-edge-held | C13：evidence 增加但 acceptance/review 边尚未释放；同时 terminal review coverage 仍未完成，次命中 F3。 |
| 37 | 17:02:40–17:04:40，seq 7411 | db:validate 因 worktree 缺 .env/DIRECT_URL 暴露配置前置，保留其他进程并用 process-scoped DIRECT_URL 重跑。 | unmatched | 仍是 integration carrier/config readiness，建议 attempt.readiness.integration-carrier-unavailable。 |
| 38 | 17:06:11，seq 7438 | governance fixture 在并行负载下超时，单独重跑 canonical governance，不修改 timeout 或治理代码。 | unmatched | 表没有“非断言型 runner timeout 的等价重验”处境。建议 attempt.verify.runner-timeout。 |
| 39 | 17:06:20–17:11:58，seq 7442、7474 | governance 重跑通过后进入 root typecheck/lint/test/build、Prisma schema validate 和 OpenAPI/contracts drift check。 | unmatched | 这是质量证据 bundle 的收口顺序，既非 manual result、safety invariant，也非 completion claim。建议 attempt.verify.quality-bundle-pending。 |
| 40 | 17:13:14，seq 7489 | 技术证据稳定后启动 independent terminal-final closure review，覆盖 Track A/B/C/Safety，owner 保留 claim audit/Gate 权责。 | attempt.review.terminal-coverage-incomplete | F3；review scope 作为 terminal coverage 的独立门。 |
| 41 | 17:23:24，seq 7544 | reviewer 对 dirty worktree 给出 UNCERTAIN，没有把 6/6 修复和 unit 110/110 当作 closure PASS。 | unmatched | coverage 已运行但 comparison head 不可作为 immutable anchor，现有 F3/C6 无专门行。建议 attempt.review.comparison-head-dirty。 |
| 42 | 17:23:45–17:24:16，seq 7548、7560 | Owner 只 stage 10 个 business-code/test 文件建立 implementation commit，保护 package docs 不入 commit，随后在 committed head 上重跑证据和 review。 | unmatched | 这是 review anchor 的物理固定，不等于 Gate comparison mismatch。建议 attempt.record.review-head-fixed。 |
| 43 | 17:24:35–17:30:54，seq 7569、7598 | 77d2db4a 固定后绑定 focused/PG evidence，并新开 committed-head terminal-final review；期间不以等待超时替代 verdict。 | attempt.review.terminal-coverage-incomplete | F3；新 comparison head 需要新一轮 terminal coverage。 |
| 44 | 17:40:19，seq 7665 | committed-head review 返回 1 个 P1，主控核对属实，保持 BLOCKED，只修 createImport claim 回滚路径并补 retry regression。 | finding.fix.reviewer-returned | reviewer returned finding → fresh bounded fix，符合 E1。 |
| 45 | 17:41:41–17:45:17，seq 7693、7719 | 最小事务异常修复和 42/42、111/111 focused 通过后，提交 7837b2e9，在新 revision 上重跑 PG integration 并重新 closure review。 | finding.fix.reviewer-returned | E1 为主；修复 worker/测试回执还需要落到当前 review/evidence record，次命中 C8。 |
| 46 | 17:46:35，seq 7741 | 7837b2e9 的 canonical API lane 暴露与本次变更无关的既有 recovery assertions，先用 fresh schema 重跑确认而不判 PASS。 | unmatched | 这是不可复现/污染敏感集成失败的重验，建议 attempt.verify.flaky-run-recheck。 |
| 47 | 17:48:49，seq 7754 | fresh schema 下 DMI backend 11/11、DB 17/17 通过，但 root wrapper 仍被非 DMI ReviewWorkspace 断言阻断；主控将 DMI 文件单独运行并保留 wrapper caveat。 | unmatched | 表没有“ticket-scoped evidence 与 out-of-scope wrapper failure 分离”的 verify 行。建议 ticket.verify.out-of-scope-wrapper-failure。 |
| 48 | 17:50:31–17:56:07，seq 7777、7786、7806 | DMI direct integration、全量 API tests、root typecheck/lint/build 和 contracts 检查均在同 revision 通过，等待 closure reviewer 后再收口。 | attempt.review.terminal-coverage-incomplete | F3；证据齐全不等于独立 terminal review 已完成。 |
| 49 | 17:59:21，seq 7831 | reviewer 在 7837b2e9 给出 terminal-final PASS 后，进入 owner-only ER judgment、逐 AC claim audit 和 state/Gate 写入，不改历史 ER-013。 | attempt.accept.completion-claim-unaudited | F2；先审计 completion claim，再执行 satisfy/Gate。 |
| 50 | 18:06:38，seq 7899 | DMI-05 从 BLOCKED → SATISFIED，Attempt frozen，Gate pass，acceptance 绑定 7837b2e9，并执行最终 validate/工作区审计。 | ticket.accept.satisfiable | C15 为主；同时命中 attempt.accept.all-tickets-terminal 与 attempt.gate.verdict-undecided，见多重命中清单。 |
| 51 | 18:08:01，seq 7918 | 把第一次 wrapper 的 suite-isolation caveat 补入 ER-014，不改变 DMI isolated acceptance/Gate 结论。 | ticket.record.evidence-unfiled | 这是新 caveat 的记录与结论边界落账，符合 C8。 |
| 52 | 09:49:55 / 9a80c958，seq 7949 | 对 PDF/AI Probe 新请求选择 req-align → impl-planning，只读检查，不直接实现或合并。 | unmatched | 这是 planning bundle 尚未进入 execution 的处境。建议 ticket.readiness.planning-bundle-pending。 |
| 53 | 09:52:36，seq 7981 | 确认现有实现只是 PDF upload surface，决定把它纳入同一完整 Mandant 导入，而不是形成第二套流程；继续判断 patch attempt 与整合包承接边界。 | ticket.route.multiple-business-outcomes | 多条合理产品/实现路线等待收敛，符合 C3。 |
| 54 | 09:55:20，seq 8011 | 对统一导入 UI 使用 ui-commonsense 做对象归属、状态和信息密度校准，不触发实现。 | unmatched | 这是设计调查载体选择，不是 C1 的事实/原因调查。建议 ticket.investigate.design-boundary-carrier。 |
| 55 | 09:56:30–10:04:56，seq 8030、8032、8057 | Owner 同意视觉伴侣后，先继续收敛流程，再生成可点击线框比较统一布局，随后才落合同与计划。 | unmatched | 设计预览的准备/消费没有现成行。建议 ticket.investigate.design-preview-pending。 |
| 56 | 10:02:47，seq 8051 | 将范围锁定为完整 CSV/Excel Mandant 导入 UI，PDF/AI 只作同一对象下的禁用占位，不接 provider/API、不形成第二流程。 | unmatched | 这是产品 scope freeze，不属于现有 route 对技术路线的描述。建议 attempt.record.product-scope-frozen。 |
| 57 | 10:06:23，seq 8077 | Owner 选择 C：桌面双栏工作台，左侧来源/进度，右侧唯一表单，明确不做小屏/移动端。 | ticket.route.multiple-business-outcomes | 多个布局结果中选择一个，符合 C3。 |
| 58 | 10:11:04，seq 8097 | 设计获批后正式进入 req-align 与 impl-planning，只更新 Decision/Spec/plan，不实现业务代码。 | unmatched | 仍是 planning bundle pending，建议 ticket.readiness.planning-bundle-pending。 |
| 59 | 10:13:12–10:14:28，seq 8115、8118 | 派 standing bookkeeper 物理写入 6 个规划 artifact 并做 focused validation，主控保留语义决策权。 | unmatched | 规划文档 writer 的 pending/dispatch 不在 dev-with-track 42 行内。建议 attempt.record.planning-artifact-write。 |
| 60 | 10:18:22–10:25:52，seq 8139、8148 | 把 DMI 合入设为未来执行准入条件、AI 占位设为零网络/零状态影响，并等待同一 bookkeeper 完成 DPAP-04 与链接校验。 | unmatched | 这是 planning contract freeze 与 bundle composition，不是当前表的 implementation route。建议 attempt.record.planning-contract-frozen。 |
| 61 | 10:30:35，seq 8183 | bookkeeper 返回 6 个规划 artifact 写入及 scoped validation 通过；主控接手 owner-side review，保护 runtime/state/gate 不变。 | unmatched | 这是规划 artifact review，不是 Ticket business-code reviewer。建议 attempt.review.planning-artifact-audit。 |
| 62 | 10:31:31，seq 8194 | owner review 发现 /new GET/render 必须零 mutation，并要求使用实际 DMI 组件路径；回派窄范围 correction。 | unmatched | 规划文档发现的安全/路径 correction 没有专门处境。建议 attempt.record.planning-correction-pending。 |
| 63 | 10:35:07，seq 8214 | validator 暴露 Ticket 头部格式问题，同时发现 HEAD 外部推进到 db063b4；不回退，先只读确认提交性质。 | unmatched | 外部 HEAD advance 的保留/确认动作不由当前 rework 行覆盖。建议 attempt.record.external-head-advanced。 |
| 64 | 10:37:01，seq 8231 | 将 Ticket header 改为标准 Publication Status/Attempt ID；明确不做 state init，接受 validator 下一步停在 runtime state 前置缺口。 | unmatched | 规划 bundle 已写入但 execution state 尚未初始化，建议 ticket.readiness.runtime-state-not-initialized。 |
| 65 | 10:38:22，seq 8245 | 宣布 req-align + impl-planning 的 6 份 artifact 已成形，但把后续 bundle review、DMI 合入、preflight、state init 留给未来，不宣称 package closed。 | unmatched | 这是 planning complete / execution not initialized 的收口状态，仍建议 ticket.readiness.runtime-state-not-initialized。 |

上表按“改变路线/状态/证据/交接的主控动作”计数；同一批次的连续 wait 没有重复计入。

## 4. 读数

### 4.1 总读数

| 指标 | 数值 |
| --- | ---: |
| 决策点总数 | 65 |
| 有主 slug 命中 | 40 |
| unmatched | 25 |
| 命中率 | 40 / 65 = **61.5%** |
| 多重命中点 | 13 |
| 主命中中 cli basis | 4 |
| 主命中中 prose basis | 36 |

insufficient-evidence 没有被另造为第 66 个决策点，而是用于下方跳步检测的条件级结论。主要原因是回执/evidenceIndex 的具体写入命令被截断；动作本身仍能由 seq 和 assistant 决定性叙述定位。

### 4.2 按环节的主命中分布

| 环节 | 命中次数 |
| --- | ---: |
| record | 9 |
| readiness | 0 |
| investigate | 0 |
| route | 4 |
| implement | 0 |
| fix | 9 |
| verify | 0 |
| review | 9 |
| accept | 6 |
| rework | 0 |
| disposition | 2 |
| gate | 1 |
| **合计** | **40** |

命中集中在 record、review、fix、accept。readiness、verify、implement、rework 没有主命中：环境和质量验证大量发生，但现有 verify/readiness 行无法精确表达；代码实施多数是 finding.fix 或 route 后的 bounded fix，而不是 C10-C12 的 worker incomplete/blocked。

### 4.3 多重命中清单

以下 13 个点同时符合多个现有行；主 slug 按现有优先级和对象/环节边界保留，次命中不重复计数：

1. #2：ticket.review.awaiting-reviewer + ticket.record.evidence-unfiled。
2. #8：ticket.review.awaiting-reviewer + ticket.review.required-trigger。
3. #10：attempt.accept.completion-claim-unaudited + attempt.review.terminal-coverage-incomplete。
4. #11：attempt.record.checkpoint-missing + ticket.record.evidence-unfiled。
5. #15：attempt.disposition.findings-triage-pending + finding.disposition.grading-undecided。
6. #16：finding.review.source-recheck-pending + attempt.disposition.findings-triage-pending。
7. #17：attempt.disposition.findings-triage-pending + ticket.record.evidence-unfiled。
8. #20：ticket.route.multiple-business-outcomes + ticket.route.sources-conflicting。
9. #21：ticket.route.sources-uniquely-decide + attempt.rework.contract-changed。
10. #31：ticket.review.awaiting-reviewer + ticket.record.evidence-unfiled。
11. #36：ticket.accept.acceptance-edge-held + attempt.review.terminal-coverage-incomplete。
12. #45：finding.fix.reviewer-returned + ticket.record.evidence-unfiled。
13. #50：ticket.accept.satisfiable + attempt.accept.all-tickets-terminal + attempt.gate.verdict-undecided。

## 5. unmatched 清单

| 决策点 | 真实处境 | 建议 slug | 判定 |
| --- | --- | --- | --- |
| #5 / seq 6346 | fix 返回后由 owner 统一跑 focused、typecheck、lint，再进入 review。 | ticket.verify.post-fix-regression-pending | Ticket/verify 允许组合；描述修复后验证尚未完成。 |
| #6 / seq 6375 | 为 review 固定不可变 head 和 staged-scope。 | attempt.review.comparison-head-fixed | Attempt/review 允许组合；这是 review anchor preparation。 |
| #19 / seq 6629 | ledger 正文已 terminal FAIL，但顶部元数据仍是 pending/in-progress。 | attempt.record.review-ledger-stale | Attempt/record 允许组合；是 provenance/记录卫生。 |
| #23 / seq 6807、6812 | handoff bootstrap 因新 thread 重命名失败。 | attempt.record.handoff-bootstrap-failed | Attempt/record 允许组合；与 checkpoint 内容缺失不同。 |
| #28 / seq 6919、6998 | 5433 不可用，改用 55433 的 process-scoped 本地 PG 载体。 | attempt.readiness.integration-carrier-unavailable | Attempt/readiness 允许组合；环境载体不足以用 B2 精确表达。 |
| #32 / seq 7119、7135 | dotenv 覆盖顺序导致 canonical runner 打错端口，修正 profile 后重跑。 | attempt.readiness.integration-carrier-unavailable | 同一缺行的第二次命中。 |
| #37 / seq 7411 | db:validate 缺 .env/DIRECT_URL，使用进程级变量重跑。 | attempt.readiness.integration-carrier-unavailable | 同一缺行的第三次命中。 |
| #38 / seq 7438 | 并行负载造成 governance timeout，单独重跑且不改规则。 | attempt.verify.runner-timeout | Attempt/verify 允许组合；区别于断言 FAIL。 |
| #39 / seq 7442、7474 | root quality bundle、schema validate、OpenAPI/contracts drift 作为 Gate 前证据链。 | attempt.verify.quality-bundle-pending | Attempt/verify 允许组合；现有 F1 只描述 manual result。 |
| #41 / seq 7544 | dirty worktree 使 terminal review 只能给 UNCERTAIN。 | attempt.review.comparison-head-dirty | Attempt/review 允许组合；不是 coverage 缺失，也不是 pass 后 F7。 |
| #42 / seq 7548、7560 | 选择性 commit 以创建可审查的 committed comparison head。 | attempt.record.review-head-fixed | Attempt/record 允许组合；是 review anchor 的物理落盘。 |
| #46 / seq 7741 | 与本次修改无关的 recovery assertion 失败，先 fresh schema 重验。 | attempt.verify.flaky-run-recheck | Attempt/verify 允许组合；描述非确定性/污染敏感失败的复核。 |
| #47 / seq 7754 | Ticket 直接 DMI evidence 已通过，但 root wrapper 被非 DMI ReviewWorkspace 阻断。 | ticket.verify.out-of-scope-wrapper-failure | Ticket/verify 允许组合；表达 ticket-scoped evidence 与 wrapper failure 分离。 |
| #52 / seq 7949 | 新 UI 请求停在 req-align/impl-planning，尚未进入 execution。 | ticket.readiness.planning-bundle-pending | Ticket/readiness 允许组合；此处是新包的启动准入。 |
| #54 / seq 8011 | 用 UI 设计 skill 校准对象边界和信息密度。 | ticket.investigate.design-boundary-carrier | Ticket/investigate 允许组合；但它不是事实/原因调查。 |
| #55 / seq 8030、8032、8057 | 先收敛流程，再用视觉伴侣生成可点击线框。 | ticket.investigate.design-preview-pending | Ticket/investigate 允许组合；是设计调查载体选择。 |
| #56 / seq 8051 | 冻结统一导入 + AI 禁用占位 + 无新后端的产品 scope。 | attempt.record.product-scope-frozen | Attempt/record 允许组合；现有 route 没有产品 scope freeze。 |
| #58 / seq 8097 | 设计批准后只写 Decision/Spec/plan，不初始化 execution。 | ticket.readiness.planning-bundle-pending | 与 #52 同一规划准入缺行的第二次命中。 |
| #59 / seq 8115、8118 | 派 standing bookkeeper 物理写入规划 artifact。 | attempt.record.planning-artifact-write | Attempt/record 允许组合；不是 intake backlog。 |
| #60 / seq 8139、8148 | 冻结 planning contract 和 bundle 组成，并等待同一 writer 校验。 | attempt.record.planning-contract-frozen | Attempt/record 允许组合；属于 req-align/planning 边界。 |
| #61 / seq 8183 | 规划 writer 返回后由 owner 审阅 artifact，而不是 business-code review。 | attempt.review.planning-artifact-audit | Attempt/review 允许组合；区别于 C6/F3。 |
| #62 / seq 8194 | owner 发现 /new GET/render 必须零 mutation，回派文档 correction。 | attempt.record.planning-correction-pending | Attempt/record 允许组合；是 planning finding 的修订。 |
| #63 / seq 8214 | validator 问题与外部 HEAD advance 同时出现，选择确认而不是 reset/checkout。 | attempt.record.external-head-advanced | Attempt/record 允许组合；现有 D2 只描述 acceptance revision diverged。 |
| #64 / seq 8231 | 修正 Ticket metadata，但有意不做 state init。 | ticket.readiness.runtime-state-not-initialized | Ticket/readiness 允许组合；表达 planning→execution 的边界。 |
| #65 / seq 8245 | planning artifact 成形但 runtime state、执行和 package closure 尚未发生。 | ticket.readiness.runtime-state-not-initialized | 与 #64 同一缺行的终态命中。 |

这些建议只用于 replay 报告；没有修改 situations.yaml、设计文档或允许矩阵。

## 6. 跳步检测

### 6.1 没有任何调查载体就直接进入实现

- **确认：0 次。**
- DMI-05 在本片中的代码动作都消费了前一轮 review findings、Owner 对齐后的 D3/S7 或主控验证中新发现的 finding；没有看到 PENDING + 无 investigate/evidence 后直接用 C1 的 implement-direct。
- #21 的前片 investigate/原始 evidence 不在本片，是否完整存在只能标 insufficient-evidence；不能据此把它算成一次跳步。

### 6.2 worker 返回后未记 evidence 就推进

- **确认：0 次永久漏记。**
- **可疑批次：8 批，全部标 insufficient-evidence，不计入确认逃逸次数。** 定位如下：
  1. seq 6304、6313 → seq 6314：两个 fix worker 返回后进入 owner 串行收口。
  2. seq 6345 → seq 6346：fixture fixer 返回后立即重跑验证。
  3. seq 6509、6533、6538、6543 → seq 6544、6562：四轨 finding 回执后先归并/去重。
  4. seq 7005 → seq 7006：M6 worker 返回后消费局部 DONE。
  5. seq 7028 → seq 7031：frozen vocabulary worker 返回后处理临时 typecheck 单点。
  6. seq 7091 → seq 7092：三个 seam worker 全返后进入 owner 串行 integration。
  7. seq 7544 → seq 7548：UNCERTAIN review 回执后建立 committed head。
  8. seq 7664 → seq 7665：P1 review 回执后进入最小返工。
- 之所以不判成真实 C8 逃逸，是因为 seq 6619 明确说 ER-013、evidence index 和 Ticket checkpoint 已同步，seq 7899 又明确说 ER-014 已追加、旧证据做了 invalidation；但具体写入发生在每个回执之前还是之后，受截断的 nested tool call 影响不可判定。

### 6.3 未经独立 review 就宣称完成或 satisfy

- **0 次。**
- DMI-05 的 SATISFIED 写入发生在 seq 7830 的 committed-head terminal-final PASS 之后，并伴随 ER-014、claim audit 和 Gate 写入（seq 7831、7899）。
- worker 回执中的局部 DONE 都明确限定为 worker scope；统一 UI 包到 seq 8245 仍明确没有实现、state init 或 package closure。

### 6.4 已 SATISFIED 的 Ticket 被新证据触及时的处置

- **0 次。**
- 本片 DMI-05 在 seq 6619 时仍是 BLOCKED，直到 seq 7899 才 SATISFIED；之后没有新的 DMI claim evidence 触发 needs-revalidation。
- 后续 PDF/AI Probe 规划引用 DMI 作为前置能力，但被建模为新 UI scope/新规划包，没有把 DMI-05 原 claim 证伪，也没有调用 evidence invalidate、needs-revalidation 或 retire。这个判断只覆盖本片。

### 6.5 交接信号

- handoff bootstrap 失败 **1 次**（seq 6812），随后通过 anchor/continuation 审计并在 seq 6832 成功接管。
- 本片能看到 ER-013/checkpoint 作为恢复锚点；没有证据表明这次 handoff 是单纯依赖未落盘 prompt。前三片的 checkpoint 写入过程不在本片，不能外推。

## 7. 表本身的问题

1. **integration carrier/readiness 没有精确行。** 5433 不可用、改用 55433、dotenv 顺序打错端口、缺 DIRECT_URL 都是“验收载体不可用但可以通过等价本地 profile 恢复”的真实处境。B2 all-edges-held 太宽，F1 manual-result-missing 又要求 manual owner；三次 unmatched 说明应至少有 attempt.readiness.integration-carrier-unavailable，或明确这类处境属于表外环境层。

2. **dirty comparison head 没有精确行。** review 实际运行并得到 UNCERTAIN，但问题不是 coverage 缺失，而是 dirty worktree 不能成为 immutable comparison point；主控因此只提交业务文件、保留 protected docs，再重开 review。F3/C6 可以勉强解释“需要 review”，不能解释“为何原 ReviewRun 不可采信”。

3. **ticket-scoped evidence 与 out-of-scope wrapper failure 没有精确行。** DMI direct integration 11/11、DB 17/17 和全量 unit 通过，但 root wrapper 被非 DMI ReviewWorkspace assertion 阻断；主控正确地保留 caveat 并按 Ticket 范围收口。现有 verify 行没有表达这种证据隔离，建议先补读数再决定是否扩展命名。

4. **review ledger 的元数据漂移没有精确行。** seq 6629 显示正文已经 terminal FAIL，而 ledger 顶部仍是 pending/in-progress。A1/A2/C8/G1 只能覆盖 state/projection/evidence/checkpoint 的相邻问题，不能准确表示 ReviewRun provenance header stale。

5. **planning/req-align 与 dev-with-track 的边界没有显式标记。** seq 7949–8245 的大量 unmatched 不是 implementation 规则失败，而是“规划 artifact 已形成、execution state 尚未初始化”的另一个生命周期。若强行把这些行塞入 dev-with-track，会污染表的对象和环节；更稳妥的是在表外标记 stage boundary，或另建 planning 状态表。

6. **C8 的时间语义不足。** 本片能看到 worker/reviewer 的自然语言证据先推动下一动作，稍后又有 ER/evidence index 同步，但看不到每条 evidence 的 precise timing。若只用 evidence.indexed true/false，无法区分“尚未落账”“同一 owner action 内原子落账”和“后来补账”；renderer 应保留回执到落账的顺序或时间。

7. **terminal Gate 的产品范围容易被误读。** DMI-05 Gate pass 只覆盖后端业务/数据安全闭环；seq 7944–7946 明确确认没有对应 UI 的人工验收。表的 Ticket accept/Gate 行没有错，但报告和渲染层应显示 package scope，避免把 backend SATISFIED 读成整条产品旅程可发布。

## 8. 版本干扰与结论边界

- 本片使用的是缓存的 Impl-Package 0.3.1 skill/script 路径，timeline 中可见多次读取 C:\Users\Xiao\.codex\plugins\cache\agent-workbench\impl-package\0.3.1。它没有显示当前处境表 renderer、三段式 situation slug 或按 subject 写入的 trail.jsonl。
- 本片主要靠自然语言 continuation、Execution Record、state.py、review ledger 和 standing bookkeeper 回执推进；不是按当前 42 行表逐轮机械投递。因此 unmatched 只能说明语义上没有精确行，不能直接解释为新版 CLI 拒绝或新版 agent 违规。
- evidenceIndex 的跳步读数尤其受旧版直接 patch/状态脚本和 tool-call 截断影响；不能仅凭本片把 C8 的 basis 从 prose 改成 observed，也不能把 8 批 insufficient-evidence 候选改成 8 次确定逃逸。
- package validate、Gate pass、SATISFIED 的具体 CLI 约束来自当时 0.3.1 行为；当前表中 cli basis 的强度不能直接由旧版命令结果外推。
- DMI-05 的后端 Gate 收口和 PDF/AI Probe 的规划收口是两个不同 package lifecycle。后者在 seq 8245 明确没有 state init；不能因为同一 session 之前 DMI-05 已 SATISFIED，就把后者解释成 rework、satisfy 或 closed。
- M6 的前一轮合同争议、DMI-05 更早的 review 生成过程和前三片的 checkpoint 写入不在本片；本报告只使用本片提供的 continuation/assistant 说明，涉及原始触发来源的地方显式标 insufficient-evidence。

## 9. 结论

本片最值得注意的三个发现是：

1. **表对 DMI-05 的 review → finding fix → committed-head re-review → claim audit → satisfy/Gate 主循环覆盖良好。** 40 个命中主要集中在 record、review、fix、accept；并且没有观察到未经独立 review 就 satisfy 的跳步。
2. **真正的覆盖缺口在验证载体和比较点，而不在“有没有 review”这条主线。** PG 端口/profile、并行 timeout、dirty comparison head、非相关 wrapper failure 都需要主控做实际判断，但当前表没有精确处境；这解释了 unmatched 大量集中在 readiness/verify，而两者主命中都是 0。
3. **最后的 PDF/AI Probe 规划段验证了生命周期边界。** “统一产品 scope 已冻结、6 份 planning artifact 已写入”不等于 execution started，更不等于 package closed；如果不把 planning stage 与 dev-with-track 分开标示，回放读数会把合法的表外工作误报成 implementation 逃逸。

本报告只报告回放结果和建议 slug，没有修改处境表、YAML、设计文档或其它仓库内容。
