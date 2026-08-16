# SKILL 规则 → 处境表覆盖对照

## 口径与统计

本表对照最终版的五个目标文件；`dev-with-track/SKILL.md` 的行号包含本轮新增接线。规则单元按编号项、bullet、控制流节点或可独立判断的同句子句拆分；同一行拆分时，每条原文仍是目标文件中的逐字连续摘录。标题、front matter 的 `name`、空行和纯 Markdown 围栏不计入。

覆盖程度的含义：

- **完全承载**：表在合适的 subject/处境投递了同一触发边界和行动/限制，下一轮可作为降载候选。
- **部分承载**：表覆盖触发或行动的一部分，但卸掉散文会丢失本表“说明”列列出的限定、顺序、所有权、证据或后果。
- **未承载**：没有对应表行。说明会区分“遗漏”（应成为可观测流程处境）与“本来不该进表”（共享合同、授权、caller glue 或不可机械裁决的人类判断）。

共 **127** 条规则：**25** 条完全承载、**72** 条部分承载、**30** 条未承载。`references/impl-package-composition-contract.md` 与 `references/impl-package-current-state.md` 是跨 skill 共享合同；目标 SKILL 中“先读它们”的规则仍列出，但标为“不应进表”，不列入下一轮降载候选。

## 1. `dev-with-track/SKILL.md`

| ID | 文件与行 | 规则原文（逐字摘录） | 承载 slug | 覆盖程度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| D01 | `SKILL.md:3` | `当批准 implementation plan 正式开始或者恢复执行、选择下一 actionable unit、记录证据、处理返工失效、分流 findings 或写 Gate 时使用` | `attempt.record.session-resumed`；`attempt.readiness.multiple-ready-tickets`；`ticket.record.evidence-unfiled`；`ticket.rework.evidence-conflict`；`attempt.disposition.findings-triage-pending`；`attempt.gate.missing` | 部分承载 | 表覆盖列出的多数触发点，但没有“批准 plan 正式开始”这一 skill 入口，也没有把“使用本 skill”作为统一 row。 |
| D02 | `SKILL.md:3` | `新 package 以 Ticket 为执行轴，不重新定义 Decision/Spec/Plan/Ticket。` | — | 未承载 | **本来不该进表**：这是 package composition/owning-stage 边界，不是一个待投递处境。 |
| D03 | `SKILL.md:8` | `先读 ../../references/impl-package-composition-contract.md 和 ../../references/impl-package-current-state.md。` | — | 未承载 | **本来不该进表**：明确属于跨 skill 共享合同的读取规则。 |
| D04 | `SKILL.md:8` | `当前 attempt 涉及 material seam、browser/provider/native-tool 或昂贵系统验证时，再读 progressive-system-evidence.md。` | `ticket.review.required-trigger`；`attempt.verify.integration-evidence-unavailable` | 部分承载 | 表能提示 shared seam/昂贵验证相关的 review 或证据缺口，但不承载“按风险再读哪份证据合同”的读取动作。 |
| D05 | `SKILL.md:8` | `本 skill 拥有执行控制、finding 分流、验证和 Gate 的语义判断` | — | 未承载 | **本来不该进表**：这是语义 ownership 声明，不能由处境 row 取代。 |
| D06 | `SKILL.md:8` | `current state、Progress、Attempt Execution Record、active checkpoint、execution findings 和 current Gate 的物理写入由绑定的 /impl-package:standing-bookkeeper 执行` | — | 未承载 | **本来不该进表**：这是跨 skill writer/物理存储合同。 |
| D07 | `SKILL.md:8` | `旧 package 的 Task Handoff 仅作兼容恢复材料，各上游 artifact 仍由 owning skill 维护。` | — | 未承载 | **本来不该进表**：兼容迁移与 artifact ownership 不应由 situation table 再定义。 |
| D08 | `SKILL.md:9` | `需要委派或决定本地执行时，通过 /impl-package:subagent-driven-development 取得 scheduling contract；本 skill 只消费调度结果。` | `ticket.review.required-trigger`；`ticket.review.awaiting-reviewer`；`ticket.implement.worker-blocked` | 部分承载 | 表能投递 worker 尚未返回、结果不完整、需 review 等处境，但不能承载统一 scheduling contract 和“只消费结果”的跨 skill 边界。 |
| D09 | `SKILL.md:13` | `在第 1 步 package validate 返回后，把当前处境渲染作为恢复起点，再进入第 2 步的 progress/checkpoint 读取。` | — | 未承载 | **本来不该进表**：这是 renderer caller 的接线顺序，不是表内处境；表只能提供被渲染的 row。 |
| D10 | `SKILL.md:16-20` | `python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> package validate`；`{"projection_drift":false,"source":"package validate"}`；`{"projection_drift":true,"source":"package validate"}` | — | 未承载 | **本来不该进表**：这是 validation-result adapter 的调用 glue；`package.record.state-missing` / `package.record.projection-drift` 是它要投递的结果，不是调用规则本身。 |
| D11 | `SKILL.md:22` | `python <impl-package-plugin-root>/scripts/situation.py render --package <package> --validation-result $validationResult --json` | — | 未承载 | **本来不该进表**：这是表的运行时 caller。 |
| D12 | `SKILL.md:25` | `这里的布尔值是对 package validate 退出结果的结构化适配：成功传 false，非零结果保守传 true；不解析 stdout/stderr。` | `package.record.state-missing`；`package.record.projection-drift` | 部分承载 | 两个 P0 row 会被投递，但“成功/非零如何适配”与“不解析 stdout/stderr”属于 adapter 合同；非零也可能是 state invalid，不能说表完全承载 projection 语义。 |
| D13 | `SKILL.md:25` | `若非零同时意味着 package.state_invalid，renderer 自己推导的 P0 package.record.state-missing 仍按表的顺序优先显示。` | `package.record.state-missing`；`package.record.projection-drift` | 部分承载 | P0 顺序和两个 row 被表承载，但“一个 validation failure 同时提供两个信号并依赖优先级消歧”是 caller 说明。 |
| D14 | `SKILL.md:25` | `渲染结果是参考，不是 gate；主控可以按实际判断偏离建议，但要在轨迹中写一行理由。` | `attempt.record.anchor-mismatch`；`ticket.route.multiple-business-outcomes`；`ticket.route.sources-conflicting` | 部分承载 | 表有人工判断/逃逸相关 row，但没有一个通用“renderer 非 gate、偏离须记理由”的 row；轨迹规则见 D47-D51。 |
| D15 | `SKILL.md:27` | `运行 package validate；跨 session 或授权绑定比较点时附 --commit <Git commit>。` | `package.record.state-missing`；`package.record.projection-drift`；`attempt.gate.comparison-mismatch` | 部分承载 | 表能提示 validate、projection refresh 和 comparison mismatch，但没有承载每次 restore 的 unconditional validate 以及 --commit 的授权绑定条件。 |
| D16 | `SKILL.md:28` | `打开根 progress.md，读取 current Attempt、可选合同别名、Composition、Ticket 状态、blocker、active checkpoint、next action、Gate 及 Execution Record 指针` | `attempt.record.session-resumed`；`attempt.record.checkpoint-missing`；`attempt.readiness.multiple-ready-tickets`；`attempt.accept.all-tickets-terminal`；`attempt.gate.missing`；`attempt.disposition.findings-triage-pending` | 部分承载 | 表覆盖恢复、readiness、terminal Gate 等若干投递点，但不承载完整的 progress/ER 字段读取清单。 |
| D17 | `SKILL.md:28` | `只有旧 package 才读取 Task/DAG/Handoff 轴。` | — | 未承载 | **本来不该进表**：这是 3.5/3.4 composition 兼容边界。 |
| D18 | `SKILL.md:29` | `只沿当前动作读取必要 Ticket、Task、Handoff、Execution Record judgment、review 或 evidence；不要重读全部历史。` | — | 未承载 | **本来不该进表**：这是主控的信息读取成本/范围判断，不是可稳定推导的处境。 |
| D19 | `SKILL.md:30` | `根据初始 bundle approval 和实际 diff确认仍在同一 package。` | — | 未承载 | **本来不该进表**：这是 authorization/package identity 检查。 |
| D20 | `SKILL.md:30` | `implementation、behavior、acceptance、data/security 与 package record 更新均沿用该 approval；新 package 从 owning stage 取得新的初始 bundle approval。` | — | 未承载 | **本来不该进表**：approval 生命周期和 owning stage 合同不属于 situation row。 |
| D21 | `SKILL.md:34` | `每轮在 Investigate、Decide、Implement 或 Evaluate 任何一步落地前，先按 Restore 上面的 package validate → 结构化 --validation-result → situation.py render --json 顺序查看当前处境与可选动作` | — | 未承载 | **本来不该进表**：这是主循环 caller glue；表是被消费的规则源。 |
| D22 | `SKILL.md:34` | `这只是导航参考，不是推进 gate。` | — | 未承载 | **本来不该进表**：这是 renderer 与 workflow engine 的边界，而不是某个处境。 |
| D23 | `SKILL.md:36` | `Investigate：确认首个真实违约边界、输入、持久状态、权威来源和已通过边界。` | `ticket.investigate.no-carrier`；`ticket.investigate.evidence-gap` | 部分承载 | 表能提示何时补 investigate 或补取证，但不承载“调查质量”的五项确认内容。 |
| D24 | `SKILL.md:37` | `现有 Decision/Spec 能唯一裁决时作为 implementation defect` | `ticket.route.sources-uniquely-decide` | 完全承载 | row 的唯一来源路由和 implement-and-reverify 动作覆盖该判断。 |
| D25 | `SKILL.md:37` | `存在多个合理业务结果才请求 owner。` | `ticket.route.multiple-business-outcomes` | 完全承载 | row 明确投递 owner decision，且没有结论前不派修复。 |
| D26 | `SKILL.md:38` | `Implement：只修复已证实、当前可归责的范围` | — | 未承载 | **遗漏**：表有 worker/finding 结果处境，但没有“bounded、已证实、可归责实现范围”的 row。 |
| D27 | `SKILL.md:38` | `派发时给 primary ownership、禁区、成功条件、反例和局部验证。` | — | 未承载 | **遗漏**：这是可机械检查的 dispatch brief 合同，当前表没有对应 row。 |
| D28 | `SKILL.md:39` | `Evaluate：使用最便宜且忠实的证据。昂贵 runtime/E2E 重跑必须有新修复、环境变化或决定性观察目标。` | — | 未承载 | **本来不该进表**：证据成本与“是否有决定性观察目标”是主控验证策略判断，不能安全由现有机械输入裁决。 |
| D29 | `SKILL.md:41` | `步骤 1、3 的事实调查、实现、修复和验证策略由 /impl-package:subagent-driven-development 统一形成；本 skill 只消费其 mode / worker / schedule / review 与结果合同。` | — | 未承载 | **本来不该进表**：这是跨 skill scheduling/result contract。 |
| D30 | `SKILL.md:41` | `步骤 2 和 4 由主 session 把控，package 记录通过 bookkeeper 落盘。` | `ticket.record.evidence-unfiled`；`ticket.record.judgment-unfiled`；`attempt.disposition.findings-triage-pending` | 部分承载 | 表能提示记录缺失和 findings 分流，但不能承载“谁把控/谁落盘”的 owner 分工。 |
| D31 | `SKILL.md:42` | `依赖是否释放由新 package 的 typed Ticket dependency 与 canonical state 判断；旧 package 才额外读取 DAG。` | `attempt.readiness.multiple-ready-tickets`；`attempt.readiness.all-edges-held`；`ticket.accept.acceptance-edge-held`；`ticket.accept.satisfiable` | 部分承载 | 表覆盖 dependency/release 的机械结果，但没有完整保留新旧 package 的来源轴区分。 |
| D32 | `SKILL.md:42` | `Progress/checkpoint 不授权 dispatch，也不释放 acceptance/release dependency。` | `attempt.readiness.all-edges-held`；`ticket.accept.acceptance-edge-held`；`ticket.accept.satisfiable` | 部分承载 | row 的条件/动作支持正确 readiness，但“不授权”这一负向边界没有独立投递。 |
| D33 | `SKILL.md:46` | `状态变化优先使用语义 Ticket 命令 ticket satisfy\|block\|needs-revalidation\|pending\|retire ... --expect ...` | `ticket.accept.satisfiable`；`ticket.implement.worker-blocked`；`ticket.rework.revalidation-pending`；`ticket.disposition.retire-undecided` | 部分承载 | 表动作覆盖主要 transition，但不承载统一命令优先级、所有 --expect 约束和 legacy alias。 |
| D34 | `SKILL.md:46` | `SATISFIED 必须带当前 --revision/--environment` | `ticket.accept.satisfiable` | 完全承载 | satisfiable row 的条件和 ticket satisfy 动作都包含 revision/environment。 |
| D35 | `SKILL.md:46` | `BLOCKED/RETIRED 使用直接 evidence` | `ticket.implement.worker-blocked`；`ticket.disposition.retire-undecided` | 完全承载 | 两个 row 的动作分别要求 block/retire 的 evidence。 |
| D36 | `SKILL.md:46` | `stale transition 必须重新读取当前状态。旧 set-state ticket ... 仅作兼容别名。` | `ticket.rework.revalidation-pending` | 部分承载 | revalidation row 能提示重验，但没有 stale CAS reread 与兼容命令的完整语义。 |
| D37 | `SKILL.md:47` | `新 package 不产生 READY/RUNNING/DONE Task 状态；旧 package 的 Task DONE 不等于 Ticket SATISFIED。` | — | 未承载 | **本来不该进表**：这是跨版本状态模型合同。 |
| D38 | `SKILL.md:48` | `主 session 将 checkpoint、judgment 和其他已确定执行事实交给 bookkeeper；由 bookkeeper 通过 recovery checkpoint、recovery judgment 等现有入口写入。worker 默认不直接写 package state 或 Execution Record。` | `attempt.record.checkpoint-missing`；`attempt.record.checkpoint-refresh`；`ticket.record.judgment-unfiled`；`ticket.record.evidence-unfiled` | 部分承载 | 表能提示要补 checkpoint/judgment/evidence，但不承载 writer ownership 和 worker 禁写边界。 |
| D39 | `SKILL.md:49` | `recovery checkpoint 是 active checkpoint 写入快捷入口，更新 state.activeCheckpoints[subject]。` | `attempt.record.checkpoint-missing`；`attempt.record.checkpoint-refresh`；`attempt.record.session-resumed` | 部分承载 | row 提供写/刷新/恢复动作；状态路径和快捷入口属于 CLI/state 合同。 |
| D40 | `SKILL.md:50` | `新 package 在 BLOCKED、retry、跨 session/owner 或需要交接时写文档化 active checkpoint` | `attempt.record.checkpoint-missing`；`attempt.record.handoff-in-flight`；`ticket.implement.worker-incomplete-first`；`ticket.implement.worker-incomplete-second`；`ticket.implement.worker-blocked` | 部分承载 | 表覆盖长任务/交接、worker blocked/incomplete 的若干触发，但没有把四类 checkpoint 时机完整合并。 |
| D41 | `SKILL.md:50` | `checkpoint 不授权派发、不释放依赖，也不创建 Task Handoff。旧 package 的 handoff 仅作迁移材料。` | `attempt.record.checkpoint-missing`；`attempt.record.handoff-in-flight`；`attempt.readiness.all-edges-held` | 部分承载 | 表能提醒 checkpoint/handoff/readiness，但不能承载这些“不产生授权/不创建 handoff”的负向约束。 |
| D42 | `SKILL.md:51` | `checkpoint 只记录下一动作与恢复证据，不授权派发；长期判断写 ER judgment。compact 只作异常兜底，不是正常交接权威。` | `attempt.record.checkpoint-missing`；`ticket.record.judgment-unfiled` | 部分承载 | row 能提示 checkpoint/judgment，但没有 compact 例外及 checkpoint/ER 的信息分工。 |
| D43 | `SKILL.md:52` | `合同或计划实际变化直接记录受影响 Ticket（旧 package 另含受影响 Task）并保留未受影响 evidence` | `attempt.rework.contract-changed` | 完全承载 | contract-changed row 直接投递 affected subset，并要求保留未受影响 evidence。 |
| D44 | `SKILL.md:52` | `同一 package 持续沿用 initial bundle approval。` | — | 未承载 | **本来不该进表**：这是 approval 生命周期合同。 |
| D45 | `SKILL.md:55-56` | `Get-Content .\er-payload.json -Raw \| python <impl-package-plugin-root>/scripts/impl_package_state.py --package <package> recovery judgment` | `ticket.record.judgment-unfiled`；`finding.disposition.grading-undecided`；`attempt.disposition.findings-triage-pending` | 部分承载 | row 的 action 可提示写 judgment/triage，但不会承载具体 stdin 命令和 payload transport。 |
| D46 | `SKILL.md:59` | `<impl-package-plugin-root> 指当前已加载 skill 所属的插件根目录；不要假设 workbench 仓库路径或宿主缓存路径。` | — | 未承载 | **本来不该进表**：这是 skill loader/path resolution 合同。 |
| D47 | `SKILL.md:61` | `3.5 的 recovery judgment payload 只使用 purpose=judgment、subject=attempt\|ticket:<id>、title、content 和可选 evidence；checkpoint 使用显式 recovery checkpoint --subject ... --next ...，旧 package 的 Task Handoff 只在迁移时读取。` | `ticket.record.judgment-unfiled`；`attempt.record.checkpoint-missing` | 部分承载 | row 能提示补 judgment/checkpoint，但不承载 payload 字段闭集、subject 形状及旧 handoff 迁移限制。 |
| D48 | `SKILL.md:65` | `处境表漏掉某个当前处境时，按判断行动并走 escape 出口是合法路径，不是违规` | — | 未承载 | **本来不该进表**：escape/unmatched 是 table 的落账协议，不是另一个 situation row。 |
| D49 | `SKILL.md:65` | `若主控偏离渲染建议，也只需记录理由，不把 renderer 当成阻断器。` | — | 未承载 | **本来不该进表**：这是 caller 的导航/非 gate 约束。 |
| D50 | `SKILL.md:65` | `没有其它载体的动作要显式写一行轨迹：派发的发起与返回、escape、Ticket 选择、finding 定级与分流、来源路由判断，以及需要声明的 fact。` | — | 未承载 | **本来不该进表**：这些是 trail writer 的事件/fact 分类，不应由 situation row 自己承载。 |
| D51 | `SKILL.md:65` | `execution/<attempt>/trail.jsonl 中每个非空行是 JSON object，事件使用 dispatch、result/worker-return 或 kind=fact，带正确的 subject，fact 带 key、value、ts，需要 Git 对账时带 head。` | — | 未承载 | **本来不该进表**：这是 trail-schema/input contract。 |
| D52 | `SKILL.md:65` | `首版全部显式写行，不要求改 impl_package_state.py。` | — | 未承载 | **本来不该进表**：这是本轮 implementation scope/写入策略。 |
| D53 | `SKILL.md:69` | `通过 /impl-package:do-review 运行 initial、finding-closure 和 terminal-final review` | `ticket.review.awaiting-reviewer`；`finding.review.closure-awaiting`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | 表覆盖等待 reviewer、finding closure、terminal coverage，但没有统一表达三类 review 的调度入口。 |
| D54 | `SKILL.md:69` | `review topology、适用范围和 coverage 由该 skill 拥有。本 skill 消费报告，terminal pass 要求 terminal-final coverage 完整且所有阻断 finding 已关闭。` | `attempt.review.terminal-coverage-incomplete`；`finding.disposition.grading-undecided` | 部分承载 | 表能提示 coverage/finding 未收口，但不能承载 do-review ownership、报告消费和“所有阻断 finding”汇总条件。 |
| D55 | `SKILL.md:70` | `当 do-review parent 已接受并归类 Track C / Spec fidelity finding 时，修复派发前读取 Runtime Protocol 的 Findings 路由并消费同一 ReviewRun 已记录的一次性独立 source recheck` | `finding.review.source-recheck-pending` | 完全承载 | source-recheck-pending row 正是在该处境下投递 dispatch-source-recheck。 |
| D56 | `SKILL.md:70` | `本 skill 不重复调度 reviewer，记录缺失或 incomplete 时交回 do-review。该检查不创建 Ticket/Attempt 状态，也不替代 finding-closure 或 terminal-final。` | `finding.review.source-recheck-pending`；`finding.review.closure-awaiting`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | 表覆盖 recheck/closure/coverage 的动作，但不承载同一 ReviewRun 去重、回交和“不改状态/不替代 review”的边界。 |
| D57 | `SKILL.md:71` | `P1/P2 finding 必须修复并 closure verify；editorial suggestion 不阻断 Gate。` | `finding.disposition.grading-undecided`；`finding.review.closure-awaiting`；`attempt.gate.missing`；`attempt.gate.verdict-undecided` | 完全承载 | grading row 明确 P1/P2 阻断、editorial 不阻断，并配合 closure/gate rows 投递后续动作。 |
| D58 | `SKILL.md:72` | `package 级 execution-findings.md 在 terminal Gate 前必须完成分流：Decision rationale→Decision，规范行为→Spec，执行判断→Execution Record，长期知识→Durable Delta/_pending.md。` | `attempt.disposition.findings-triage-pending` | 完全承载 | findings-triage-pending 的四路 action 与该规则逐项对应。 |
| D59 | `SKILL.md:73` | `Planned Verification 有 manual owner 时，使用 assets/templates/manual-acceptance-readiness.md 把入口、oracle、环境、失败反馈和 teardown owner 写入 judgment 或 canonical handoff，并取得结果 evidence。` | `attempt.verify.manual-result-missing` | 部分承载 | row 只承载 manual owner/结果缺失和“取得结果”，不承载模板字段、teardown owner 和写入载体。 |
| D60 | `SKILL.md:77` | `completion claim 先交给 /impl-package:verification-before-completion。` | `attempt.accept.completion-claim-unaudited` | 完全承载 | row 直接投递 audit-before-completion。 |
| D61 | `SKILL.md:77` | `Gate 只判断 current Attempt：` | `attempt.gate.missing`；`attempt.gate.verdict-undecided`；`attempt.gate.terminal-frozen` | 部分承载 | Gate rows 的 subject 是 attempt，但“只判断 current Attempt”的 owning-scope 限制不是 row 内容。 |
| D62 | `SKILL.md:79` | `blocked：保持 active，记录 gap 和 next action。` | `attempt.gate.missing`；`attempt.gate.verdict-undecided` | 部分承载 | 表能投递 blocked gate 的写入选择，但没有把 active/gap/next 三项作为完整结果合同。 |
| D63 | `SKILL.md:80` | `pass：所有 earned Task/Ticket、适用验证、review、manual acceptance 和 findings closure 均满足。` | `attempt.accept.all-tickets-terminal`；`attempt.review.terminal-coverage-incomplete`；`attempt.verify.manual-result-missing`；`attempt.disposition.findings-triage-pending`；`attempt.gate.durable-delta-missing` | 部分承载 | 各前置条件分别有 row，但表没有一个汇总 pass predicate，也不能表达 earned Task 的旧 package 语义。 |
| D64 | `SKILL.md:81` | `fail \| defer：如实终结；后续实现进入 patch Attempt。` | `attempt.gate.missing`；`attempt.gate.verdict-undecided`；`attempt.gate.terminal-frozen` | 部分承载 | gate verdict 与 terminal freeze 有 row，但“新建 patch Attempt”属于 impl-planning，不在本表。 |
| D65 | `SKILL.md:83` | `terminal Gate 必须完成 Stage 7：记录 Durable Delta 及 _pending.md/truth pointer，或通过 --no-durable-delta-reason 明确无增量原因。terminal 后 state、active checkpoint 和 Execution Record 冻结。` | `attempt.gate.durable-delta-missing`；`attempt.gate.terminal-frozen` | 完全承载 | durable-delta-missing 与 terminal-frozen 两个 P0/P4 row 分别承载 Stage 7 缺失和 terminal freeze。 |
| D66 | `SKILL.md:85` | `Gate CLI 拥有 comparison commit 与 lifecycle 校验。` | `attempt.gate.comparison-mismatch`；`attempt.gate.terminal-frozen` | 部分承载 | 表能提示 comparison mismatch/frozen，但没有 Gate CLI 的 lifecycle 校验 ownership。 |
| D67 | `SKILL.md:85` | `长任务先让 bookkeeper 完成 state/ER/Gate 等 durable 写入，再输出最终叙述；transport disconnect 后从这些幂等事实恢复，不创建第二个完成结论。` | `attempt.record.checkpoint-missing`；`attempt.gate.missing`；`attempt.gate.verdict-undecided` | 部分承载 | 表有 checkpoint/Gate 恢复信号，但不承载 transport disconnect、幂等恢复和禁止第二 completion claim。 |
| D68 | `SKILL.md:87` | `若 active skill catalog 中存在 talk-to-boss，优先按其汇报合同输出；否则直接分别说明实施、验证、Gate、backfill/合入状态，给出 Task/Ticket 总数、剩余数、blocker、是否 closed 和唯一下一动作。` | — | 未承载 | **本来不该进表**：这是回答编排与状态汇报格式，不是执行处境。 |

## 2. `dev-with-track/references/runtime-protocol.md`

| ID | 文件与行 | 规则原文（逐字摘录） | 承载 slug | 覆盖程度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| R01 | `runtime-protocol.md:3` | `运行状态唯一来源是 .impl-package/state.json；格式和命令见 ../../../references/impl-package-current-state.md。` | `package.record.state-missing`；`attempt.readiness.all-edges-held`；`attempt.accept.all-tickets-terminal` | 部分承载 | 表从 state 推导多个 row，但“唯一来源”和共享 current-state 命令合同本身不在表。 |
| R02 | `runtime-protocol.md:3` | `3.5 新 package 只读取 Ticket/evidence/checkpoint；3.4 Task/DAG/Handoff 只能由一次性迁移 prompt/validator 读取。` | — | 未承载 | **本来不该进表**：跨版本读取轴与迁移入口是 composition/current-state 合同。 |
| R03 | `runtime-protocol.md:7` | `运行 package validate；projection drift 时先运行 package refresh-progress。` | `package.record.state-missing`；`package.record.projection-drift` | 完全承载 | 两个 P0 row 的动作正是 validate/init 与 refresh-progress，且顺序可由 P0 优先级表达。 |
| R04 | `runtime-protocol.md:8` | `打开 progress.md，确认 current Attempt、lifecycle、Gate、blocker、active checkpoint 和 next action` | `attempt.record.session-resumed`；`attempt.record.checkpoint-missing`；`attempt.gate.missing`；`attempt.gate.verdict-undecided` | 部分承载 | 表提示恢复、checkpoint 和 Gate，但不承载完整 progress 字段读取。 |
| R05 | `runtime-protocol.md:8` | `新 package 只确认 Ticket Acceptance，旧 package 才确认两条状态轴。` | `attempt.accept.all-tickets-terminal`；`ticket.accept.satisfiable` | 部分承载 | acceptance/terminal 条件有 row，3.5/3.4 两条状态轴边界没有。 |
| R06 | `runtime-protocol.md:9` | `新 package 依据 Ticket typed dependency 与 Ticket state 判断 readiness；旧 package 才依据 DAG/Task 和 Ticket dependency。` | `attempt.readiness.multiple-ready-tickets`；`attempt.readiness.all-edges-held`；`ticket.accept.acceptance-edge-held`；`ticket.accept.satisfiable` | 完全承载 | 表的 readiness/acceptance rows 直接使用这些 dependency/state 结果，并按 P1/P4 投递动作。 |
| R07 | `runtime-protocol.md:9` | `Progress 不授权 readiness。` | `attempt.readiness.multiple-ready-tickets`；`attempt.readiness.all-edges-held` | 部分承载 | 两个 readiness row 能防止无 readyTicket 时硬上，但“不授权”是负向合同而非 row。 |
| R08 | `runtime-protocol.md:10` | `新 package 只打开当前动作需要的 plan/Ticket/Execution Record/evidence；旧 package 才按需读取 DAG/Handoff。` | — | 未承载 | **本来不该进表**：这是主控读取范围和迁移兼容策略。 |
| R09 | `runtime-protocol.md:11` | `推进后使用语义 ticket 命令的 --expect，再写 recovery checkpoint 或必要 recovery judgment。` | `ticket.record.evidence-unfiled`；`ticket.record.judgment-unfiled`；`attempt.record.checkpoint-missing`；`attempt.record.checkpoint-refresh` | 部分承载 | 表能投递记录补写，但不承载“推进后→CAS expect→checkpoint/judgment”的顺序。 |
| R10 | `runtime-protocol.md:15` | `Evidence 必须是存在的仓库相对路径，可带 anchor，并足以解释状态变化。不要保存额外完整性证明。` | `ticket.record.evidence-unfiled`；`ticket.accept.satisfiable` | 部分承载 | evidence-unfiled/satisfiable 能提示证据缺失或不支持，但路径/anchor 形状和“不保存额外证明”不在表。 |
| R11 | `runtime-protocol.md:17` | `checkpoint：恢复边界；activeCheckpoints[subject] 是唯一 active 值并覆盖写。` | `attempt.record.session-resumed`；`attempt.record.checkpoint-missing`；`attempt.record.checkpoint-refresh` | 部分承载 | 三个 row 覆盖恢复/缺失/刷新，但唯一值、覆盖写和恢复边界是 state writer 合同。 |
| R12 | `runtime-protocol.md:17` | `新合同的 RETIRED 对应旧 3.4 的 WAIVED/SUPERSEDED，状态进入 NEEDS-REVALIDATION 时 Progress 标为 stale。` | `ticket.disposition.retire-undecided`；`ticket.rework.revalidation-pending` | 部分承载 | retire/revalidation row 覆盖状态处境，但旧状态映射和 Progress stale 投影不由表承载。 |
| R13 | `runtime-protocol.md:18` | `judgment：执行期 decision、finding disposition、failure learning、外部证据解释。` | `ticket.record.judgment-unfiled`；`finding.disposition.grading-undecided`；`attempt.disposition.findings-triage-pending` | 部分承载 | 表能提示 judgment 未落账或 finding 分流，但不能完整定义 judgment 的四类内容。 |
| R14 | `runtime-protocol.md:19` | `routine state change、普通 PASS 和可从 Git/state 推导的事实不重复写入 Execution Record。` | — | 未承载 | **本来不该进表**：这是 ER 去重/写入分工合同。 |
| R15 | `runtime-protocol.md:23` | `新 package：Ticket implementation dependency 阻止进入 readyTickets；acceptance dependency 允许实施但阻止 SATISFIED；release dependency 在 Gate/release 前复核。` | `attempt.readiness.all-edges-held`；`attempt.readiness.multiple-ready-tickets`；`ticket.accept.acceptance-edge-held`；`ticket.accept.satisfiable`；`ticket.accept.release-edge-unchecked` | 完全承载 | P1 readiness、P4 acceptance/release rows 覆盖三种 dependency 的不同后果。 |
| R16 | `runtime-protocol.md:24` | `旧 package：Task dependency 未释放时不得进入 READY/RUNNING；Task DONE 后由 Working Branch owner 集成、运行共享验证并映射 Ticket AC。` | `attempt.readiness.all-edges-held`；`attempt.verify.integration-evidence-unavailable`；`attempt.accept.all-tickets-terminal` | 部分承载 | 表能提示边未释放、集成证据和 terminal acceptance，但没有 Working Branch owner、READY/RUNNING 旧轴和 AC mapping。 |
| R17 | `runtime-protocol.md:25` | `plan/contract 变化在同一 package 直接更新；按需记录 affected subset 的 revalidation/coverage/verification，并沿用 initial bundle approval。` | `attempt.rework.contract-changed` | 完全承载 | contract-changed row 的动作覆盖 affected subset；approval 的 ownership 细节在表外。 |
| R18 | `runtime-protocol.md:29` | `accepted Track C / Spec fidelity finding：先消费 do-review 在同一 ReviewRun 内完成的一次性独立 source recheck；该动作不改变 Ticket/Attempt 状态。` | `finding.review.source-recheck-pending` | 部分承载 | row 投递 source recheck，但不承载同一 ReviewRun、一次性、无状态变化的完整约束。 |
| R19 | `runtime-protocol.md:30` | `current sources uniquely decide：按引用的 Decision/Spec/contract 作为 implementation 或 evidence defect，在当前 Attempt 修复并重验。` | `ticket.route.sources-uniquely-decide` | 完全承载 | row 的 implement-and-reverify 与该路由一致。 |
| R20 | `runtime-protocol.md:31` | `source missing/ambiguous/conflicting：先回 req-align 更新当前 Spec contract ensemble，再进入实现。` | `ticket.route.sources-conflicting` | 完全承载 | row 直接投递 return-to-req-align。 |
| R21 | `runtime-protocol.md:32` | `多个合理业务结果：请求 owner decision；没有结论前不派发修复。` | `ticket.route.multiple-business-outcomes` | 完全承载 | row 明确 owner decision，且不派修复。 |
| R22 | `runtime-protocol.md:33` | `其他 accepted finding：沿用现有 implementation、安全、证据或知识分流，不触发 source recheck。` | `finding.disposition.grading-undecided`；`attempt.disposition.findings-triage-pending` | 部分承载 | 表覆盖分流入口，但没有“其他 finding 不触发 source recheck”的排除逻辑。 |
| R23 | `runtime-protocol.md:34` | `durable knowledge：Stage 7 登记 _pending.md 与 truth pointer，后续交 backfill。` | `attempt.gate.durable-delta-missing`；`attempt.disposition.findings-triage-pending` | 部分承载 | durable-delta row 覆盖登记缺失和 truth pointer，后续 backfill 交接不在表。 |
| R24 | `runtime-protocol.md:36` | `Gate 每次重写 current gate.md；Git 与旧 Attempt Execution Record 的 lifecycle/Gate 摘要提供历史。` | `attempt.gate.missing`；`attempt.gate.verdict-undecided`；`attempt.gate.comparison-mismatch` | 部分承载 | Gate rows 能投递缺失/未决/比较不匹配，但没有 current overwrite 与历史摘要的写入语义。 |
| R25 | `runtime-protocol.md:36` | `terminal Gate 后全部 runtime mutation fail closed。` | `attempt.gate.terminal-frozen` | 完全承载 | terminal-frozen row 直接以 fail-closed 为 action。 |

## 3. `dev-with-track/references/control-flow.md`

| ID | 文件与行 | 规则原文（逐字摘录） | 承载 slug | 覆盖程度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| C01 | `control-flow.md:4` | `validate → progress restore → resolve readiness → implement/investigate → verify` | `package.record.state-missing`；`attempt.record.session-resumed`；`attempt.readiness.multiple-ready-tickets`；`ticket.investigate.no-carrier`；`ticket.implement.worker-blocked`；`ticket.verify.safety-invariant-unfalsified` | 部分承载 | 每个阶段都有相关 row，但表没有单独承载这条全局顺序。 |
| C02 | `control-flow.md:6` | `affected-scope revalidation ← CAS state + ER checkpoint` | `attempt.rework.contract-changed`；`ticket.rework.revalidation-pending`；`attempt.record.checkpoint-missing` | 部分承载 | affected/revalidation/checkpoint 有 row；CAS state 与 ER checkpoint 的联动顺序不在表。 |
| C03 | `control-flow.md:8` | `review/manual acceptance → findings routing → claim audit` | `ticket.review.awaiting-reviewer`；`attempt.verify.manual-result-missing`；`attempt.disposition.findings-triage-pending`；`attempt.accept.completion-claim-unaudited` | 部分承载 | 各阶段有 row，但表没有表达这条跨阶段顺序和 claim audit 汇总条件。 |
| C04 | `control-flow.md:10` | `Stage 7 → current Gate` | `attempt.gate.durable-delta-missing`；`attempt.gate.missing`；`attempt.gate.verdict-undecided` | 完全承载 | Stage 7 缺失和 Gate 缺失/未决由相邻 P4 row 按动作顺序承载。 |
| C05 | `control-flow.md:13` | `blocker 或 evidence 缺失：停在当前 unit，记录 checkpoint。` | `attempt.readiness.all-edges-held`；`ticket.implement.worker-blocked`；`ticket.record.evidence-unfiled`；`attempt.record.checkpoint-missing` | 部分承载 | 表能提示 blocker/evidence/checkpoint，但没有一个统一 row 同时表达“停在当前 unit”。 |
| C06 | `control-flow.md:14` | `contract/plan 变化：留在同一 package 记录 affected scope 并沿用 initial bundle approval；新 package 从 owning stage 取得初始 bundle approval。` | `attempt.rework.contract-changed` | 完全承载 | affected scope 的表动作完整；approval/owning-stage 是表外授权合同。 |
| C07 | `control-flow.md:15` | `新 package 所有 earned Ticket satisfied、适用验证与 review 通过：进入 completion claim audit；release 边在 Gate 前复核。` | `attempt.accept.all-tickets-terminal`；`attempt.accept.completion-claim-unaudited`；`attempt.review.terminal-coverage-incomplete`；`ticket.accept.release-edge-unchecked` | 完全承载 | terminal、claim audit、review coverage、release edge 都有对应 row。 |
| C08 | `control-flow.md:16` | `旧 package 的 Task 完成后交 Working Branch owner 集成，不自动接受 Ticket；旧 Task/Ticket 终态共同进入 completion claim audit。` | `attempt.accept.all-tickets-terminal`；`attempt.verify.integration-evidence-unavailable` | 部分承载 | 表有 terminal/integration evidence，但没有旧 Task、owner、自动接受禁止及 Task/Ticket 双轴。 |
| C09 | `control-flow.md:17` | `terminal Gate 后禁止继续当前 Attempt；新工作由 impl-planning 创建 patch Attempt。` | `attempt.gate.terminal-frozen` | 部分承载 | terminal-frozen 完整覆盖 fail-closed；创建 patch Attempt 的 owning skill 不在表。 |

## 4. `subagent-driven-development/references/review-gate.md`

| ID | 文件与行 | 规则原文（逐字摘录） | 承载 slug | 覆盖程度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| G01 | `review-gate.md:3` | `复杂度只增加 reviewer gate，不自动更换 implementer。` | `ticket.review.required-trigger`；`ticket.review.awaiting-reviewer` | 部分承载 | 表能投递需 review/等待 reviewer，但不承载“复杂度不换 implementer”的调度边界。 |
| G02 | `review-gate.md:3` | `review_scope 表示 reviewer 的边界：checkpoint 验收一个已声明的 bounded slice，closure 验收整个 source unit。` | `ticket.review.awaiting-reviewer`；`finding.review.closure-awaiting`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | row 能区分等待 review/closure/terminal coverage，但没有完整的 scope 取值合同。 |
| G03 | `review-gate.md:3` | `不要为每个文件或每个小动作都增加 checkpoint。` | `ticket.review.required-trigger` | 部分承载 | row 能提示 review trigger，但没有“按 bounded slice 而非文件/动作过切”的负向规则。 |
| G04 | `review-gate.md:5` | `以下任一条件要求 review=required：shared seam、安全、数据完整性、并发、migration、不可逆外部副作用，或 Plan/safety policy 明确要求独立审查。` | `ticket.review.required-trigger` | 完全承载 | required-trigger row 的触发条件和 require-review action 对应这组条件。 |
| G05 | `review-gate.md:5` | `复杂任务在切片边界设置 checkpoint；最终仍需 closure。` | `ticket.review.awaiting-reviewer`；`finding.review.closure-awaiting`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | 有对应等待/closure/coverage row，但没有由复杂度自动选择 checkpoint、最终 closure 的完整调度语义。 |
| G06 | `review-gate.md:5` | `单纯跨文件、跨模块或接口变化不自动升级；非显然地选择 review=none 时记录 reason。` | `ticket.review.required-trigger` | 部分承载 | required-trigger 能防止无条件 review，但没有“none 必须留 reason”的独立投递。 |
| G07 | `review-gate.md:8-11` | `implementer(slice) -> reviewer(checkpoint) -> PASS: 继续下一个 slice；finding: fresh fixer -> reviewer(checkpoint)` | `ticket.review.awaiting-reviewer`；`finding.fix.reviewer-returned`；`finding.review.closure-awaiting` | 完全承载 | reviewer 等待、finding 返回和 fresh fixer/重审动作均有 row。 |
| G08 | `review-gate.md:13-16` | `implementer(last slice) -> reviewer(closure) -> PASS: review_state=PASSED；finding: fresh fixer -> reviewer(closure)` | `ticket.review.awaiting-reviewer`；`finding.review.closure-awaiting`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | 表覆盖 closure/terminal coverage，但没有 review_state=PASSED 作为完整状态合同。 |
| G09 | `review-gate.md:18-20` | `main-session finding -> fresh fixer -> reviewer(对应 scope)` | `finding.fix.main-session-discovered`；`finding.review.closure-awaiting` | 完全承载 | main-session-discovered 与 closure review row 直接表达这条路径。 |
| G10 | `review-gate.md:23` | `Implementer 或 fixer 的 DONE 在 reviewer 运行前都标记为 review_state: PENDING_REVIEW。` | `ticket.review.awaiting-reviewer` | 部分承载 | awaiting-reviewer 可由 DONE+required 触发，但没有显式 PENDING_REVIEW 写入规则。 |
| G11 | `review-gate.md:23` | `Reviewer 必须是独立 fresh invocation，默认逻辑 worker 为 $grok-worker；fixer 使用新的 @luna-worker 或 $grok-worker invocation，不能复用发现 finding 的旧进程。` | `ticket.review.awaiting-reviewer`；`finding.fix.reviewer-returned`；`finding.fix.worker-envelope-invalid` | 部分承载 | 表覆盖需派 reviewer/fixer 和 envelope 失败，但不承载 worker resolver、fresh process 和禁止 reuse。 |
| G12 | `review-gate.md:23` | `Reviewer 只读、不修复、不替 main session 做 Ticket acceptance。` | `ticket.review.awaiting-reviewer`；`ticket.accept.satisfiable` | 部分承载 | 表分别有 reviewer/acceptance row，但没有 reviewer 的只读及不代替主控验收边界。 |
| G13 | `review-gate.md:23` | `UNCERTAIN/BLOCKED 原样上交。` | `attempt.review.reviewer-unavailable`；`ticket.implement.worker-blocked` | 部分承载 | 有 unavailable/blocked row，但“原样上交”是 envelope/result contract。 |
| G14 | `review-gate.md:23` | `只有 review_state=NOT_REQUIRED 或 PASSED 的结果可以被主 session 消费；PENDING_REVIEW、FINDING、BLOCKED 都不能支持完成声明。` | `ticket.review.awaiting-reviewer`；`finding.fix.reviewer-returned`；`attempt.accept.completion-claim-unaudited` | 部分承载 | 表能阻止等待 review 的 completion claim，但没有完整的 review_state allow/deny 集合。 |

## 5. `subagent-driven-development/references/mode-contracts.md`

| ID | 文件与行 | 规则原文（逐字摘录） | 承载 slug | 覆盖程度 | 说明 |
| --- | --- | --- | --- | --- | --- |
| M01 | `mode-contracts.md:6-11` | `Investigation: EVIDENCE_SUFFICIENT \| EVIDENCE_GAP；cause、blast radius、existing solution、boundary facts、unresolved facts` | `ticket.investigate.evidence-gap`；`ticket.investigate.no-carrier` | 部分承载 | 表能识别 EVIDENCE_GAP 和无 investigate carrier，但不承载 investigate envelope 的字段闭集。 |
| M02 | `mode-contracts.md:14` | `EVIDENCE_SUFFICIENT 只释放实施判断，不释放授权、acceptance 或 Gate。` | `ticket.route.sources-uniquely-decide`；`ticket.accept.satisfiable`；`attempt.gate.verdict-undecided` | 部分承载 | 表有路由/acceptance/Gate 的独立 row，但不以一个约束阻止把 worker 结果升级成 authorization/acceptance/Gate。 |
| M03 | `mode-contracts.md:18` | `输入必须包含批准来源、bounded outcome、ownership、禁改范围、依赖、局部验证和 strategy。` | `ticket.review.required-trigger`；`ticket.investigate.no-carrier` | 部分承载 | 表能提示 review/dispatch，但没有实现 brief 的完整输入字段合同。 |
| M04 | `mode-contracts.md:18` | `输出包括变更文件、直接证据、residue/cleanup 和 residual risk；DONE 只代表局部单元完成。` | `ticket.record.evidence-unfiled`；`ticket.review.awaiting-reviewer` | 部分承载 | evidence/review rows 覆盖部分结果，但不承载 residue、risk 和局部 DONE 非 package 完成的全合同。 |
| M05 | `mode-contracts.md:22` | `输入必须包含 finding ID/来源、comparison point、broken invariant、disposition、ownership、禁改范围和验证入口。Fixer 不重新裁决 finding、不扩大范围、不宣称 finding closure` | `finding.fix.reviewer-returned`；`finding.fix.main-session-discovered`；`finding.disposition.grading-undecided` | 部分承载 | 表有 finding 来源/定级/修复入口，但不承载 fixer input 闭集、范围不扩大和不得宣称 closure。 |
| M06 | `mode-contracts.md:22` | `reviewer 必须针对修复后的 comparison point 重新检查。` | `finding.review.closure-awaiting`；`attempt.review.comparison-head-unfixed` | 部分承载 | closure/comparison row 能提示重审和固定 head，但不表达“修复后针对同一 comparison point”的完整关联。 |
| M07 | `mode-contracts.md:26` | `只执行既定无写副作用的动作，返回 command/procedure、exit status、pass/skip/failure count、首个 actionable failure、cleanup/residue 和必要 artifact pointer。` | `attempt.review.reviewer-unavailable`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | reviewer 失败/coverage 有 row，但结果 envelope 的字段清单没有进入表。 |
| M08 | `mode-contracts.md:26` | `会重写 snapshot、generated file 或工作区内容的命令改走 implement/fix 或主 session 集成。` | `ticket.review.required-trigger` | 部分承载 | review trigger 可提醒边界，但没有“有写副作用即换 mode/owner”的 row。 |
| M09 | `mode-contracts.md:30` | `Reviewer 使用 mode=review 的只读合同，但拥有独立的审查职责。review_scope=checkpoint 只判断当前 bounded slice；review_scope=closure 才判断整个 source unit 是否可以收口。` | `ticket.review.required-trigger`；`ticket.review.awaiting-reviewer`；`attempt.review.terminal-coverage-incomplete` | 部分承载 | 表有 review required/awaiting/coverage，但没有 mode=review、bounded slice/source unit 的完整判断域。 |
| M10 | `mode-contracts.md:30` | `两者都是 fresh invocation；checkpoint PASS 不代表 package 完成，closure PASS 才能支持 closure 判断。` | `ticket.review.awaiting-reviewer`；`attempt.accept.completion-claim-unaudited` | 部分承载 | 表能延迟 completion claim，但不承载 fresh invocation 和 checkpoint/closure 的证明级别差异。 |
| M11 | `mode-contracts.md:30` | `Reviewer 发现问题时返回 finding，由 main session 交给 fresh fixer，不在 reviewer invocation 内修复。` | `finding.fix.reviewer-returned`；`finding.fix.main-session-discovered`；`finding.review.closure-awaiting` | 完全承载 | reviewer-returned → fresh fixer → 同 scope review 的处境链由表完整投递。 |

## 未承载清单与归因

以下是上表所有 `未承载` 项，逐条说明它们是遗漏还是本来不应进入 situation table；表头统计会按完整规则单元计数。

| ID | 规则主题 | 归因 | 原因 |
| --- | --- | --- | --- |
| D02 | 新 package 以 Ticket 为执行轴、不能重定义上游 artifact | 本来不该进表 | composition/owning-stage contract。 |
| D03 | 读取 composition/current-state 共享合同 | 本来不该进表 | 跨 skill 共享合同，且用户明确排除其降载。 |
| D05 | dev-with-track 拥有语义判断 | 本来不该进表 | owner boundary。 |
| D06 | bookkeeper 负责物理写入 | 本来不该进表 | writer/存储边界。 |
| D07 | 旧 Handoff 兼容、上游维护 artifact | 本来不该进表 | 迁移与 artifact ownership。 |
| D09 | Restore validate 后先 render | 本来不该进表 | caller glue；由 SKILL 接线实现。 |
| D10 | validation result 的退出码适配 | 本来不该进表 | caller/adapter glue；表只消费 package.validate.projection_drift。 |
| D11 | situation.py render --json 调用 | 本来不该进表 | caller glue。 |
| D17 | 旧 package 才读取 Task/DAG/Handoff | 本来不该进表 | 版本/迁移合同。 |
| D18 | 只读当前动作所需材料 | 本来不该进表 | 主控的信息读取效率判断。 |
| D19 | 确认同一 package | 本来不该进表 | authorization/package identity。 |
| D20 | 沿用/取得 initial bundle approval | 本来不该进表 | approval lifecycle。 |
| D21 | 主循环每轮推进前 render | 本来不该进表 | caller glue。 |
| D22 | render 不是推进 gate | 本来不该进表 | workflow engine 边界。 |
| D26 | 只修复已证实、可归责范围 | 遗漏 | 可作为实现范围/归责处境，但当前表没有 row。 |
| D27 | dispatch brief 必须包含 ownership/禁区/成功条件等 | 遗漏 | 可机械审查的 dispatch contract 缺 row。 |
| D28 | 证据成本与昂贵 E2E 重跑条件 | 本来不该进表 | 需要主控判断，现有输入不能安全裁决。 |
| D29 | subagent scheduling/result contract | 本来不该进表 | 跨 skill 合同。 |
| D37 | 3.5/3.4 Task 状态模型差异 | 本来不该进表 | 跨版本 current-state contract。 |
| D44 | initial bundle approval 持续有效 | 本来不该进表 | approval lifecycle。 |
| D46 | plugin root 路径解析 | 本来不该进表 | host/loader invocation contract。 |
| D48 | escape 合法、表漏处境按判断行动 | 本来不该进表 | table output/trail policy，不是另一个 situation row。 |
| D49 | 偏离建议只记理由、renderer 不阻断 | 本来不该进表 | caller navigation policy。 |
| D50 | 无其它载体的动作显式写 trail | 本来不该进表 | trail writer schema/落账分工。 |
| D51 | trail JSONL/event/fact 字段形状 | 本来不该进表 | 已有 situation-inputs/trail-schema 合同。 |
| D52 | 首版显式写行、不改 state writer | 本来不该进表 | implementation scope。 |
| D68 | talk-to-boss 汇报字段 | 本来不该进表 | 输出编排，不是执行处境。 |
| R02 | 3.5/3.4 读取轴与迁移入口 | 本来不该进表 | composition/current-state contract。 |
| R08 | 当前动作最小读取范围 | 本来不该进表 | 信息读取效率/迁移策略。 |
| R14 | routine state/普通 PASS/Git fact 不重复写 ER | 本来不该进表 | ER 去重与 writer contract。 |

真正值得后续补表的缺口是 D26、D27；其余未承载项不建议为了“覆盖率”硬塞进表。

## 下一轮降载候选

完全承载是机械候选上限，不等于下一轮可以无条件删除全部完全承载散文。建议先卸纯重复的触发→动作短句，再保留带有 owner、证据边界或跨 skill 后果的上下文。

仍建议保留的“完全承载”规则：

- D24/D25、R19-R21、G04/G07、M11：它们包含 owner decision、来源路由、review/fixer 的语义边界；表能投递处境和动作，但不能替代读者理解“为什么此处不应直接修复/为什么要 fresh”。
- D34/D35、R03、R25、D65：这些与 CLI/state 的 fail-closed 合同相邻；在降载初期保留一句短提醒有助于把处境 row 与实际命令对上，避免把表误当成 state engine。
- D43、R17、C06：affected subset/contract change 同时牵涉 approval 与 evidence 保留，当前表承载了动作但没有承载完整 approval lifecycle；应先保留限定语。

基于这些保留项，下一轮建议先卸 **9 条**纯重复散文规则：D55、D57、D58、D60、R06、R15、C04、C07、G09。完全承载条目中的上述 16 条保留项不要随第一批删除。D26/D27 应先补 row 或另立 dispatch-contract 后，再考虑相邻散文降载。
