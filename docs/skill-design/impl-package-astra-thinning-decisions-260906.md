# Impl-Package 打薄讨论记录

日期：2026-09-06（落地施工：2026-09-07）
状态：T1–T8、E1–E3、D1–D3 的决定及 D2 承接方案已确认，T7/D1 的复核补充已校正（T7 范围含 backfill-stable-docs）。E4–E5 保留观察。T9 本轮取舍已结束：32 个 fact key 中，删除 22 个声明入口（其中 5 个保留现有计算或结构化输入判定）、保留 2 个、暂缓 8 个；原处理分类不作为实施依据。T10 已确认通过 Codex hook 接入运行检查，2026-09-07 复核后收窄为只保留 `SessionStart` capsule 扩展（`PostToolUse`/`SubagentStop`/硬拦截三项撤销）。DSH 不在本轮范围内。backfill-stable-docs 核查健康、无需改动；do-review Loop 轮次上限留作观察。

**2026-09-07 落地完成**：T1、T3、T4、T7（含 dev-with-track/Dispatcher/SDD 定义去重与 req-align/impl-planning/execution-boundaries/backfill-stable-docs 的常见误判三分）、T8、T9（situation.py/situations.yaml/situation-inputs.md/protocols.json/回归 fixture）、D1（bookkeeper 角色与 role.md 删除、`standing-bookkeeper` 孤儿 evals 与悬空 intake-backlog 引用清理、impl-planning/plan-review 的 bound-writer 修正）、D2（dev-with-track 与 execution-boundaries 的 Ticket 激活 preflight 删除）均已通过 Codex 分批实施并交叉核对；`pytest tests/` 598 项全部通过。D3（situations.yaml 的 `ticket-boundary-handoff` 自动换 session 触发删除，含 `situation-inputs.md`/`protocols.json`/回归测试同步）与 `standing-bookkeeper/` 空目录清理已由主控直接完成（改动小、边界明确，未经 Codex 派发）。至此 T1–T10、D1–D3 本轮范围内的全部决定均已落地；`pytest tests/` 598 项全部通过。

**2026-09-07 独立审阅（commit `a0a33b2`）发现 4 项 P2 缺口，已逐条核实并修复**：验收声明偏满——主要删减符合设计、安全轨无新增边界回归，但以下 4 处已确认决定未真正落地，均已修复（无需新设计决定）：

1. **E1 未修复**：`_when_gate_terminal`（[situation.py:1968](../../plugin-marketplace/plugins/impl-package/scripts/situation.py:1968)）此前只解析 verdict，未核对 `gate.md` 的 Attempt 是否等于当前 attempt，与 `engine.py` 的 `_lifecycle` 逻辑不一致，旧 initial/defer Gate 仍可能被导航器误判为当前 attempt 已 terminal。已修：`GateView` 新增 `attempt` 字段并解析 `gate.md` 的 `- Attempt:` 行；`_when_gate_terminal` 在 verdict terminal 后核对 attempt 是否匹配当前 `state.json`，不匹配则为 `false`；`gate.md` 未写 Attempt 行（legacy/单 attempt 场景）时假定匹配，避免误伤没有歧义的旧 fixture。新增 3 个直接单元测试覆盖 mismatch/match/无 Attempt 行三种情况。
2. **E2 未承接**：Dispatcher（[dispatcher/SKILL.md:33](../../skills/dispatcher/SKILL.md:33)）只落地了 T3 的“有实际收益”一般判断，没有 E2 明确要求的“消费返回后优先检查未接通业务路径，不要只围绕最近 findings 循环”。已在调度循环步骤 5 开头补回这句话。
3. **E3 缺失执行分支**：dev-with-track（[dev-with-track/SKILL.md:17](../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md:17)）步骤 6 只描述了派发 bounded worker，没有 E3 的“主控直接实现”分支及其 write ownership、独立 delta review 条件。已补回该分支。
4. **T7（impl-planning）质量问题，比最初报告更严重**：`references/common-misjudgments.md` 首版把原来 18 条“常见误判”（含“为什么错、错了有什么后果”的解释）压扁成规则复述，跟 `SKILL.md` 正文同一条规则重复，没有保留三分机制第 2 类要求的“独特提醒”；触发方式又是开头一句覆盖 admission/拆票/审查/初始化的笼统前言，等于普通规划全程都要读，没有真正减负。已重写：恢复原始 18 条的“会导致 XX 后果”解释、删除与正文重复的规则复述，并把触发方式改成逐步骤在 `SKILL.md` 对应句子后挂一句精确指针（对齐 req-align 已验证的做法）。

以上 4 处修复直接由主控完成，未再派 Codex；修复 E2 时最初的措辞插入位置破坏了 `test_dispatcher_contract.py` 的一处精确字符串断言，已调整插入位置保留原断言字符串，不是放宽测试。跑通全套测试。

**2026-09-08 二次独立审阅发现 E1 残留（已核实并修复）**：commit `0046d3c` 的 E1 修复只改了 `_when_gate_terminal`，`gate.present`、`gate.verdict`、`gate.stage7_complete`、`attempt.near_terminal_gate` 四个消费者仍直接读 `snapshot.gate`，没有走 Attempt 匹配；`sources.gate`（[situation.py:3167](../../plugin-marketplace/plugins/impl-package/scripts/situation.py:3167)）同样未过滤，SessionStart capsule 的 `gate-verdict` 行（[impl_package_hooks.py:303](../../plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py:303)）因此仍会显示上一个 Attempt 的 verdict。复现：旧 Attempt 留下 terminal Gate，新 Attempt 所有 Ticket 已 terminal 但未写 Gate 时，`attempt.gate.missing` 与 `attempt.gate.durable-delta-missing` 均不命中。已修：抽出共享判据 `_gate_attempt_matches`（[situation.py:1983](../../plugin-marketplace/plugins/impl-package/scripts/situation.py:1983)），`_when_gate_terminal`、`_when_gate_present`、`_when_gate_verdict`、`_when_gate_stage7_complete`、`_when_attempt_near_terminal_gate` 统一通过它核对 Attempt；`_effective_gate`（[situation.py:993](../../plugin-marketplace/plugins/impl-package/scripts/situation.py:993)）供 `_json_result` 的 `sources.gate` 复用同一判据，capsule 不再读到跨 Attempt 的 verdict。`references/situation-inputs.md` 同步更新 `gate.*` 四行、`attempt.near_terminal_gate` 行及相关叙述性段落，修正了 `gate.terminal` 一直未记录 Attempt 判据的既有文档缺口。新增 4 个单元测试覆盖 present/verdict/stage7_complete/near_terminal_gate 在跨 Attempt 场景下的取值；`pytest tests/` 全量跑通。

## 讨论边界

- 主控使用 Astra/High，implementer 仍使用 Luna/Max。
- Hook 接入仅讨论 Impl-Package 的 Codex 宿主能力；DSH 不在本轮讨论、研究或修改范围内。
- 评估下表中的 req-align、impl-planning、dev-with-track、Dispatcher 和 SDD；重点是 impl-planning 的规划职责，以及 dev-with-track、Dispatcher、SDD 的执行调度职责。
- 保留有实际价值的方法论，寻找重复、过细或过度流程化的指导；不预设必须删除大型机制。
- 每轮只记录已确认的取舍，讨论结束后统一修改。候选建议不等于已批准修改。

## 简称与源文件

本轮最初阅读的是用户指定的 Impl-Package 0.4.2 缓存及 workbench 的 Dispatcher；下列链接均指向 **agent-workbench 仓库源文件**，供后续修改与追溯，不指向用户级插件缓存。实例证据仍指向当时的 KaiSpan worktree。

| 本文用语 | 对应 Skill 或文件 | 本轮涉及的职责 |
| --- | --- | --- |
| 需求讨论 / req-align | [impl-package:req-align][req-align] | Decision/Spec 的行为合同与验收语义 |
| Planning / 规划 | [impl-package:impl-planning][impl-planning] | 创建 Plan/Ticket，核实复用、依赖、接线安排及验证可行性；不是泛指所有主控思考 |
| 主控执行 / dev-with-track | [impl-package:dev-with-track][dev-with-track] | 选择业务动作，采信结果，维护 State/Evidence/Gate |
| Dispatcher / 调度 | [dispatcher][dispatcher] | 形成 Topic，选择当前步骤与批次，消费返回并补派 |
| SDD / 下游工作方法 | [impl-package:subagent-driven-development][sdd] | worker 的任务边界、资源、mode、lane 和生命周期 |
| 执行边界 / preflight / bookkeeper | [impl-package:execution-boundaries][execution-boundaries] | 授权与完成证据边界；D1 删除其中的专用 bookkeeper 流程，D2 删除 Ticket 环境激活检查 |
| 正式 review / terminal-final | [impl-package:do-review][do-review] | 正式审查编排与 finding closure；T4 的逐步 delta review 节拍由 Dispatcher/SDD 指导 |
| Situation / 导航器 | [situation.py][situation-cli]、[situations.yaml][situations] | 从包事实生成处境与动作建议；不是另一个 Skill |
| Codex Hook / 事件接入 | [codex-hooks.json][codex-hooks-config]、[impl_package_hooks.py][codex-hooks-code]、[codex-hooks.md][codex-hooks-reference] | 将运行检查接入工具、worker 结束与恢复事件；T10 扩展现有入口 |
| 渐进式系统证据 | [progressive-system-evidence.md][system-evidence] | 按 claim 选择忠实证据及真实运行前检查；共享 reference，不是独立 Skill |

`Plan`、`Ticket`、`ER` 分别指任务包的计划文档、验收切片文档和 Execution Record；`Planning` 指上表中的 impl-planning Skill。每项决定下面的“落点”说明涉及哪个源文件和哪段职责，不代表该文件已修改。

## T1 · 步骤边界（已确认）

- 落点：[Dispatcher 的 Topic-first 派发门槛][dispatcher]、[SDD 的步骤授权与结果消费][sdd]；同步核对 [worker-briefs.md][worker-briefs] 和 [SDD evals 的 id=14][sdd-evals]。
- 决定：放宽相邻主控返回点的合并条件。后段不必仅限于“机械接线”；只要无需新的主控裁决、不损失并行机会，且不妨碍及时复核，由 Astra 根据任务难度决定是否合并。
- 保留：逐步授权、异步 review，以及方向、ownership、依赖、资源或授权需要重新判断时的返回边界。独立系统验证仍按实际环境和证据边界安排。
- 理由：跨技术层本身不构成强制返回理由；避免主控只接收一个尚不完整的结果，再机械重发后续工作。单步范围仍需适合 Luna 完成。
- 后续修改关注：Dispatcher 的“后段只是机械接线”条件，以及 SDD eval 14 固定分段的预期；以最终讨论结论统一校准。
- 确认依据：用户在上述建议后回复“我同意”，并要求先记录每轮决策、后续一起改。

## T2 · impl-planning 的规划职责与详细程度（已确认）

- 落点：[impl-package:impl-planning][impl-planning] 的流程第 5 步及“Ticket 拆分”，对应 [Plan 模板][plan-template] 的全局调度与 Planned Verification。
- 决定：保持 impl-planning 在编写 Plan/Ticket 时核实复用入口、真实依赖产物、接线条件和验证可行性的职责；主要压缩重复表达，不预先固化完整 baby-step 队列，不新增模板。
- 保留：真实调用链核实、已核实的复用入口、关键交接产物及其验证条件；具体派发、步骤大小和人员调整由 Astra 执行时决定。
- 理由：不能把主控指导打薄变成下游事实缺失，导致派发时或多个 Luna 重复调查。
- 确认依据：用户回复“其他我同意”，仅对 T4 请求澄清。

## T3 · 并行与 look-ahead（已确认）

- 落点：[Dispatcher 的调度循环][dispatcher]、[SDD 的“形成当前批次”及 look-ahead 完成条件][sdd]；[dev-with-track 的业务动作选择][dev-with-track] 同步消费，E2 补充收益的判断方向。
- 决定：从“所有合格动作都应派发”调整为“主动释放有实际收益的合格动作”。允许 Astra 因预期收益不足暂不派发。
- 保留：主动扫描和 look-ahead，以及依赖、授权、实际资源隔离的并行边界。
- 不要求每轮产出前瞻任务，不新增评分表或成本记录。是否值得现在派发，要考虑提前产出的价值以及派发、回收、整合成本。
- 确认依据：用户回复“其他我同意”，仅对 T4 请求澄清。

## T4 · Review 节拍（已确认）

- 落点：[Dispatcher 的 worker return 消费][dispatcher]、[SDD 的“消费结果并重排”][sdd]；[dev-with-track 的 Review/Findings][dev-with-track] 保持一致。[do-review][do-review] 的正式 review 与 terminal-final 职责保留。
- 决定：每个实现步骤返回后，都及时派独立 reviewer 审查本步改动，不攒到最后一起审。纯调查或只重跑测试、没有新增代码改动时，不机械派代码审查。
- 保留：异步 review；不依赖审查结果的下一步可以继续。正式 review 与 terminal review 的职责不变。
- 与 T1 的关系：合并不必要拆开的实现步骤，可以减少返回和对应派审次数；每个实际实现步骤仍然要审。
- 确认依据：用户在澄清“要派”及上述条件后回复“同意”。

## T5 · Worker 生命周期（保留现状）

- 保留落点：[SDD 的等待分钟数及 lane/lifecycle][sdd]、[Dispatcher 的 Topic 生命周期][dispatcher]。D3 只删除主控按 Ticket 自动换 session，不修改这些 worker 规则。
- 决定：不采纳取消固定等待分钟数的建议；保留普通实现至少观察 15 分钟、shared seam 调研至少观察 30 分钟的简单兜底，本轮不改 worker 生命周期策略。
- 用户依据：实际经常发生误伤仍在工作的 subagent，真正卡死很少；改为持续判断进程、工具调用和产物活动，反而增加主控负担。
- 取舍：机械规则可以降低判断成本并防止常见误操作，不能仅因 Astra 判断能力更强就删除。

## T6 · Situation 与恢复（已由 E1 确认）

- 落点：[situation.py][situation-cli] 的 `_parse_gate`、`_when_gate_terminal`，对照 [runtime engine][state-engine] 的 `_lifecycle`；[dev-with-track Restore][dev-with-track] 与 [Runtime Protocol][runtime-protocol] 中的 escape 留痕保留。
- 决定：保留 escape 留痕和提醒，优先修复当前 Attempt 的导航误报；实例与具体范围见已确认 E1。
- 用户依据：escape 用于留下后续优化机制的依据，同时提醒主控重新检查选择。
- 原建议“普通策略调整不额外走 escape”未获采纳，不进入本轮修改范围。
- 阅读中发现的 situation 与正文不一致保留为候选问题；本轮回答不视为批准整套 situation 策略改造。

## T7 · Skill 分工与文字（已确认；2026-09-06 复核后范围扩大）

- 落点：跨 Skill 定义去重检查 [dev-with-track][dev-with-track]、[Dispatcher][dispatcher]、[SDD][sdd] 及直接 references；“常见误判”密度处理检查 [req-align][req-align]、[impl-planning][impl-planning]、[execution-boundaries][execution-boundaries]、[backfill-stable-docs][backfill-stable-docs]（2026-09-07 补充：5 个阶段共 8 处“常见误判”，同一密度模式，见下方 T9 之后的补充记录）。
- 决定（跨 Skill 定义去重）：保留 dev-with-track、Dispatcher、SDD 三个执行 Skill 的分工，每条规则只在一处详细定义；其他入口保留必要摘要和明确引用。例如 Topic 的定义目前在 dispatcher（`SKILL.md` 第 11 行）与 SDD（`SKILL.md` 第 6-7 行）中近乎原文重复，收敛为一处权威定义 + 指针引用。
- 决定（“常见误判”三分机制，2026-09-06 复核确认）：不再统一“删除或进 evals”，按内容重复程度和用途三分：
  1. 跨文件内容真重复（同一定义/规则在两处几乎原文重复）→ 留一处权威定义，其余改为一句指针引用；
  2. 结构性重复但内容独特、且是主控做判断时用得上的（req-align 7 处、impl-planning 9 处、execution-boundaries 2 处逐步“常见误判”提示，彼此互不重复，但形式上每步一条造成密度过高）→ 降级进该 Skill 已有的 `references/*.md`（按需读取，例如 req-align 已有的 `references/package-lifecycle.md` 一类文件），主流程只在真正高风险步骤保留一句指针，不逐步都挂；
  3. 只有“验证模型行为是否还正确”的回归测试价值、不需要主控执行前预先知道 → 才进 evals。
  三者互不替代：evals 不能充当运行时提醒（主控实际执行时不会读 evals.json），降级进 references 的内容才能在需要时被读到；同一条失败案例可以既降级进 reference（教主控）又留一条 eval（测回归），不是二选一。
- 内容独特不等于值得保留：只有确实帮助执行判断的内容才进入有明确读取条件的 reference，避免把冗余整体搬家。
- 保留：Luna 实际收到的任务必须自足，不让 worker 为理解一个任务追读整套 harness。
- 用户依据：本轮讨论中用户同意尝试“规则去重、案例退出常驻正文”；2026-09-06 复核阶段确认三分机制并将“常见误判”落点扩大到 req-align/impl-planning/execution-boundaries（用户回复“同意这个三分机制”）。

## T8 · 合同与证据粒度（已确认）

- 落点：[Ticket 模板][ticket-template] 的到达路径/mock 限制，对齐 [progressive-system-evidence.md][system-evidence] 的“最早忠实边界”；[impl-planning][impl-planning] 的 stable claim 拆分职责和 [req-align][req-align] 的行为合同职责保留。模板当前位于旧 `to-tickets` 目录，语义 owner 已是 impl-planning。
- 决定：保留稳定 claim、完整证据覆盖和真实环境专属验证；按证据是否保留当前 claim 的关键机制判断有效性，取消对所有 mock 的一刀切。
- 边界：与当前 claim 无关的依赖可以模拟；模拟不得替代该 claim 所承诺的真实行为或移除关键因果机制。
- 保留：真实 UI、provider、完整用户旅程自身的验收要求不降低。
- 后续修改关注：统一 Ticket 模板的 mock 限制与 progressive-system-evidence 的忠实证据原则。
- 确认依据：用户对该建议回复“同意”。

## T9 · dev-with-track 的 fact 声明入口（本轮取舍已确认，8 项暂缓）

- 落点：[situation.py][situation-cli] 的 `FACT_KEYS` 白名单、对应计算函数及 fallback；[situations.yaml][situations] 的消费者；[situation-inputs.md][situation-inputs] 的输入合同。2026-09-06 AST 核对：32 个 key，其中 2 个为 `review.*`，其余 30 个；原分类表只有 28 行，漏列 `trail.reviewer_unavailable` 和 `finding.closure_review_pending`，已补入清单。

### 已核事实与统计限制

- `FACT_KEYS` 是允许显式声明的键集合，不是“全部必须由主控主动声明”的清单。部分计算函数可读取 state、dispatch、review 或 Git 等已有信号，也可能有显式覆盖值或默认值。例如 `attempt.in_flight` 有 dispatch 推导，`ticket.release_edge_rechecked` 在适用情况下缺省为 `false`。不能把“没有声明”统一解释为 `unknown` 或 situation 永不命中。
- 原调研声称“336 个 trail 文件、19,547 行、6 个真实 package”，但没有保存可复现的采样路径、排除规则与去重方法；复查发现跨 worktree 的同内容副本及 fixture/历史副本，该总量未能复现，保留为历史统计口径，不作为当前有效样本量。
- 最早的 `2026-08-15-datev-tax-advisor-import-workbench` 样本中 16 个非 `review.*` key 的显式声明可以复核。后续若干大包未见同类独立声明是值得追查的线索，但仍需区分显式声明、自动推导、其他结构化输入和实际主控行为；缺少声明不能证明机制未运行或主控没读文档。
- 在指定银行对账 patch 的两份 trail 中，可核到 108 行、7 条 escape、12 条 `review.canonical_summary` 和 4 条 `review.terminal_summary`。canonical summary 由主控按 [do-review][do-review] 的要求调用脚本写入；terminal summary 按 [output-templates.md][review-output] 由 parent 直接执行 `trail append`。两者都已接入 review 完成步骤，但不能统称为完全自动写入的副产物。
- 因此，“8 个入口都没有声明时机指导”过于笼统：do-review 已对上述两种 summary 明确规定时机与动作；其他 key 的实际输入路径需要逐项核对。
- 最早样本与 `situation-inputs.md` 的 fixture 示例同日，只能作为一次性验证的线索，尚不能证明两者来自同一次操作或该机制从未在实际任务中发挥作用。

### 当前决定：先看运行中的行为，再判断字段是否必要

- 用户明确要求：先从实际运行日志判断哪些字段有必要；“如果当前没有用上但主控的行为已经差不多符合预期了，就不需要这些字段了”。目的在于减少没有实际作用的机制，不是先设法让每个现有字段都被填写。
- 先确定字段原本要促成什么动作，再检查相应场景出现时主控实际做了什么：是否主动完成预期动作，是否由其他现有机制承接，还是需要 Owner 提醒后才补做。
- 若场景已出现、该声明入口未参与，而主控已基本符合预期，优先判定额外字段无必要；若出现真实遗漏或反复纠偏，再判断是否存在值得保留的提醒需求。自动推导已经参与的情况不能当成“字段没用上”。
- 日志中未出现相应场景或无法归因时，暂留未判定，不把零声明次数当成必要性结论。调查使用现有 ER、trail 和按需任务记录，不新增持久监控机制。
- 仅对确认仍有必要的提醒，再讨论机械推导、随既有动作记录或其他处理；此前“强制绑定为必填参数”的方案，以及审阅意见 4、5 中的具体字段处置建议，当前均未成为实施决定。

### 首批运行必要性结论（T9-A–C，6 个字段已确认删除）

- 核查范围：上述 Astra 四票 patch 的两份现存 trail。以下 6 个字段的 typed fact 和结构化别名均未出现；对应业务动作在 ER/trail 中有直接记录。
- T9-A：删除 `attempt.handoff_or_long_task`、`trail.checkpoint_refresh_needed`、`trail.judgment_unfiled`。没有这些声明仍写了 10 次 checkpoint，并持续记录 ER 判断与恢复入口。曾发生的错误结束是主控把调度询问当作结束节点（ER-018），并非忘记写 checkpoint；这三个声明没有体现额外价值。保留直接写 checkpoint/ER 的职责。
- T9-B：删除 `attempt.manual_verification_owner`、`attempt.manual_verification_result_present`。ER-035 保留未收到 Owner 九态验收结果的缺口，没有默认批准；ER-036 收到确认后才记录结果。保留 Plan/Ticket 中的人工验收责任及真实结果证据。
- T9-C：删除 `attempt.completion_claim_pending`。ER-035/037 已开展逐 claim 盘点、补证和正式 review，44 项 supporting 并未直接变成终审通过。保留现有完成前审计与 Gate 要求。
- 删除范围为这 6 个额外声明字段及仅依赖它们的提醒；checkpoint、ER、人工验收和完成审计的现有职责保留，不改成另一组必填参数。
- 确认依据：用户对上述 A/B/C 三组建议回复“同意”。

### 第二批运行必要性结论（T9-D–F，3 个字段已确认删除）

- 核查范围同首批。以下 3 个字段的 typed fact 和结构化别名均未出现；分别核对来源裁决、环境可用性和证据充分性，不把后两者混为一谈。
- T9-D：删除 `evidence.sources_uniquely_decide`。ER-038/039 中主控先独立复核 F205/F206 的来源，确认现有合同能够唯一裁决后再派发修复；review/ER 已保存结果。保留按合同判断修复或询问 Owner 的职责，删除额外布尔声明。
- T9-E：删除 `attempt.integration_carrier_available`。ER-002 核验默认端口不可用与实际测试库目标，ER-007 恢复既有容器，ER-020 明确 API 尚不可达而不称环境就绪；均未使用该字段。运行检查继续按 D2 已确认方案承接。
- T9-F：删除 `attempt.integration_evidence_available`。ER-035 对 47 项 claim 分为 38 项充分、5 项技术缺口、4 项 Owner 待答，随后补证，没有把局部通过当整体验收。保留逐 claim 证据判断，删除整体可用性的额外声明。
- 确认依据：用户对上述 D/E/F 三项建议回复“同意”。

### 第三批运行必要性结论（T9-G–H，保留 2 个、删除 1 个）

- T9-G：保留 `review.canonical_summary`、`review.terminal_summary`。本次 patch 分别有 12 条、4 条，携带 finding 集合、ReviewRun、HEAD 和各轨结果；canonical summary 供追踪与统计，terminal summary 由程序核对审查版本、必需轨道及独立报告。保留依据是实际结果及其消费者，不只是出现频次；保持现有写入流程，不增加填写要求。
- T9-H：删除 `ticket.no_longer_needed`。initial 与 patch 的 trail 均没有该字段或结构化别名，但 `execution/initial/retirement.md` 明确记录按 Owner 的双池方向将 TKT-13 waived、initial defer，保留旧票证据且不冒充验收通过。保留业务取舍、退役理由、授权和状态操作，删除额外的“不再需要”声明。
- 确认依据：用户对“G 保留，H 删除”回复“同意”。

### 第四批运行必要性结论（T9-I–J，删除 4 个声明入口）

- T9-I：删除 `attempt.session_resumed`、`attempt.in_flight`、`attempt.terminal_coverage_complete` 的显式声明入口或手工覆盖，保留现有自动判定。三项在 patch trail 中均无声明或结构化别名；恢复状态已有 checkpoint/动作结构判定，在途状态已有未完成 dispatch 判定，terminal coverage 已核对实际 review summary 的 HEAD、必需轨道和报告。这是移除重复输入，不是新增自动化，也不删除这些运行条件。
- T9-J：随 D1 删除 `trail.bookkeeper_partial_write`。patch 未使用该声明；专属 bookkeeper 已决定移除，异常由主控对账，复杂时只读调查，不再保留该角色专用信号。
- 确认依据：用户对 I/J 建议回复“同意”。累计删除 14 个声明入口，其中 11 个整体删除、3 个保留现有自动判定；保留 2 个 review summary，剩余 16 个待判断。

### 第五批运行必要性结论（T9-K–M，删除 5 个声明入口）

- T9-K：删除 `git.comparison_head_fixed`。patch 未声明该字段，但 ER-031/037 已用具体 HEAD 固定正式审查对象；保留真实 comparison point 与审查记录，删除重复布尔声明。
- T9-L：删除 `ticket.review_required`、`ticket.review_trigger` 及仅依赖它们的提醒。patch 未声明这些字段，Ticket 中也未出现对应备用触发标记，但 ER-004 已完成 Core 四轨正式审查，后续继续执行正式审查。保留正式 review 的要求；此判断依据正式审查实际发生，不以 delta review 替代正式审查。
- T9-M：删除 `finding.closure_review_pending`、`ticket.post_fix_regression_pending`。patch 未声明这些字段，亦无供旧 fallback 读取的 execution-findings 文件；ER-006 记录独立 finding closure，ER-039 记录修复后专项测试、真实 PG 验证及独立复核派发，并明确当时尚未取得 closure 结论。保留修复后回归、独立复核及其真实结论。
- 确认依据：用户对“K/L/M 删除”回复“同意”。累计删除 19 个声明入口（其中 3 个保留现有自动判定）、保留 2 个，剩余 11 个待判断。

### 第六批运行必要性结论（T9-N–P，删除 3 个声明入口、8 项暂缓）

- T9-N：删除 `package.validate.projection_drift`、`git.accepted_seam_changed` 的手工声明入口或覆盖，保留现有判定路径。前者已有结构化 validation result 输入，后者已有 acceptance revision 与当前 Git 比较；不增加每轮必填要求，也不扩展现有比较算法。这两项基于已有输入减少重复入口，不据此声称实例已验证所有异常分支。
- T9-O：删除 `trail.handoff_in_flight`。ER-019 已记录明确交接、当前 HEAD、WIP、剩余范围与被停止的 worker，ER-020 随后恢复执行，未使用该声明；交接职责继续由 `handoff-to-new-session` 承担。
- T9-P：下列 8 项暂缓判断，本轮不改。不新增填报要求，不为清空清单继续泛搜大量日志；后续遇到对应实例再判断。暂缓不等于已证明字段必要。

| 暂缓字段 | 尚缺的对应场景或证据 |
| --- | --- |
| `ticket.blocker_maybe_resolved` | 正式 BLOCKED Ticket 解除阻塞；普通工作被解锁不等于该状态迁移 |
| `ticket.release_edge_rechecked` | Ticket 放行边被实际复核；依赖条件满足不等于已经复核 |
| `trail.envelope_valid` | 真正的 worker 返回格式无效；报告内容失实属于另一类问题 |
| `trail.reviewer_unavailable` | 正式 ReviewRun 的 reviewer 不可用后的处理；当前明确案例主要是 delta reviewer 启动受限 |
| `trail.anchor_mismatch` | 交接 anchor 不匹配；旧 Attempt Gate 导航误报不属于此场景 |
| `trail.handoff_recovery_needed` | 交接失败后的恢复；正常交接不能证明该异常分支无必要 |
| `trail.handoff_target_corrected` | 交接目标或顺序被纠正后的续接 |
| `trail.checkpoint_projection_race` | 实际 checkpoint 竞态；旧 Gate 误报不属于此场景 |

- 确认依据：用户对“N/O 删除、P 暂缓”回复“同意”。本轮 32 项均有处置：22 个声明入口删除（17 个整体删除、5 个保留现有判定）、2 个 review summary 保留、8 个暂缓。Skill/代码落地另行统一执行。

### 先前处理设想（已暂停，不作为实施依据）

原调研提出“机械推导 / 强制绑定 / 直接砍”。以下保留 30 个非 `review.*` key 的先前设想，便于追溯；原理由不视为已核实事实，当前处置以上述 T9-A–P 为准。`review.*` 两项的实际输入方式已在上文说明。

| key | 先前处理设想（暂停） | 原理由或待查事项（非实施结论） |
| --- | --- | --- |
| `package.validate.projection_drift` | 机械/半机械 | 已有 `--validation-result` CLI 参数；应改成控制循环里跑 `package validate` 后固定传入，而不是可选路径 |
| `attempt.session_resumed` | 已经机械化，无需处理 | 实际计算是 S+R 结构判断（`activeCheckpoints.attempt` + trail marker），不读声明；closed-key 表把它列进去可能是文档过期 |
| `attempt.in_flight` | 已经机械化，无需处理 | 主要靠 `_open_dispatch` 的 dispatch/decision 结构推导，fact 只是可选优先输入 |
| `attempt.handoff_or_long_task` | 强制绑定 | 直接关系 T5 的“何时写 checkpoint”；可做成 `recovery checkpoint` 命令的必填前提 |
| `attempt.integration_carrier_available` | 直接砍，并入 D2 | 与 D2 承接的“真正运行前检查”（progressive-system-evidence.md）重合 |
| `attempt.integration_evidence_available` | 直接砍，并入 D2 | 同上 |
| `attempt.manual_verification_owner` | 强制绑定 | 对应 dev-with-track 已有的 manual-acceptance-readiness 规则；绑定到写 Planned Verification/Gate 时的必填字段 |
| `attempt.manual_verification_result_present` | 强制绑定 | 同上，同一处绑定 |
| `attempt.completion_claim_pending` | 强制绑定 | 直接对应 execution-boundaries 的“收口”整节；做成该审计流程本身的第一步产物 |
| `attempt.terminal_coverage_complete` | 已经机械化，无需处理 | 实际主要靠 `review.terminal_summary` 自动 fact 推导 |
| `ticket.blocker_maybe_resolved` | 直接砍 | 从未使用；判断后主控会直接调用 `ticket` 状态命令，声明这个中间 fact 无增量价值 |
| `ticket.no_longer_needed` | 直接砍 | 同上，判断后直接 `ticket retire` 即可 |
| `ticket.release_edge_rechecked` | 机械化候选 | 文档自述“不再从 dependency 状态推导”——曾经能机械算，后来换成纯声明，建议恢复机械推导 |
| `ticket.review_required` | 待 T4 落地后重估 | T4 已把“默认都及时派审”定为规则，这个判断的价值可能被削弱 |
| `ticket.review_trigger` | 待 T4 落地后重估 | 同上 |
| `ticket.post_fix_regression_pending` | 证据不足，待补读 | 未在已读的 situation-inputs.md 部分找到该 key 的合同细节，从未使用 |
| `evidence.sources_uniquely_decide` | 强制绑定 | 唯一被真实使用过 3 次的判断型 key，说明场景真实存在；应绑定到 `ticket.route.*` 对应的路由裁决动作上 |
| `git.comparison_head_fixed` | 机械化候选 | do-review 创建 ReviewRun 时已经 fix 一个 comparison SHA，可直接从该 ledger 推导 |
| `git.accepted_seam_changed` | 证据不足，待补读 | 未在已读部分找到合同细节，从未使用 |
| `trail.anchor_mismatch` | 待 E1 落地后重估 | E1 已经在修 `_when_gate_terminal` 的锚点判断，机械化程度会提高，这个声明的必要性会下降 |
| `trail.bookkeeper_partial_write` | 直接砍，随 D1 一起 | D1 已删除专用 bookkeeper 角色，这个 key 存在的前提已经不成立 |
| `trail.checkpoint_projection_race` | 直接砍 | 从未使用；真出现这种边缘竞态，走 T6 保留的 escape 记录即可 |
| `trail.checkpoint_refresh_needed` | 直接砍 | 无清晰机械路径；判断后主控应直接刷新，不需要先声明 |
| `trail.envelope_valid` | 机械化候选 | 已有“读取 worker-return payload 结构化字段”的 fallback；应在 worker-briefs.md 里要求 worker 固定带这个字段 |
| `trail.handoff_in_flight` | 待 D3 落地后重估 | D3 已削减自动换 session 的触发场景，需要重新评估 |
| `trail.handoff_recovery_needed` | 待 D3 落地后重估 | 同上 |
| `trail.handoff_target_corrected` | 待 D3 落地后重估 | 同上 |
| `trail.judgment_unfiled` | 直接砍 | 曾有自由文本扫描后来被换成纯声明，从未使用；judgment 归档动作本身就是唯一动作 |
| `trail.reviewer_unavailable` | 原表漏列 | 先核实际 reviewer 不可用场景中的恢复行为和现有承接 |
| `finding.closure_review_pending` | 原表漏列 | 先核 finding 修复后的复核行为及现有记录 |

- 确认依据：用户同意审阅意见 1、2、3 的文档校正，并将后续顺序明确为“先看实际运行是否需要，再决定字段处理”。原三分类不再是下一步直接执行的方案；尚未修改 situation.py/situations.yaml/situation-inputs.md。

## 2026-09-07 补充排查：do-review、backfill-stable-docs

- **do-review 的 Loop/N-rounds 上限**：用户直接确认这个上限（最多十轮）是拍脑袋定的数字，没有真实用量依据；实际行为是 initial review → 有 finding 就 closure review → terminal review → 如果 terminal 还有 finding 继续 closure，循环直到全部关闭，不是"设定 N 轮跑满"这种模式。本轮不深入调查、不改 do-review 实现，只记录这个观察，供以后需要调整轮次上限或 Loop 语义时参考。
- **backfill-stable-docs 核查（未发现问题，无需改动）**：这是本轮唯一一个"查完发现machinery 是健康的、不是过度设计"的结果。KaiSpan 仓库里能找到真实的 `.stable-docs-backfill.json` 配置和一次真实 audit 输出（`.progress-record/pool-resume-stable-docs-audit.md`）：针对 F101-F110 六组修复逐条给出 `already-covered`/`no-delta` disposition、引用具体 spec 章节、明确写"当前没有 terminal Gate，不代表整包收口"、没有在证据不足时抢先下结论。这说明 audit/apply/verify 三段式和背后的脚本机械操作是真的在被使用，且用得谨慎、克制，跟 T9 的 fact 声明机制是完全相反的结果。
  - 唯一两处小问题，优先级低：(1) 5 个阶段共 8 处"常见误判"，跟 req-align/impl-planning/execution-boundaries 是同一密度模式，已并入 T7 三分机制处理范围；(2) 该 skill 没有 `evals/` 目录（其他 skill 大多有），可以补，但因为机制本身已被真实验证有效，不紧急。

## T10 · 用 Codex Hook 接入运行检查（已确认，2026-09-07 复核后大幅收窄）

- 落点：[Codex hook 配置][codex-hooks-config]、[hook 实现][codex-hooks-code]及其[输入与 fallback 说明][codex-hooks-reference]；按职责对齐 [dev-with-track][dev-with-track]、[SDD worker 返回合同][worker-briefs]与[语义 CLI 的状态校验][state-engine]。
- 当前基础（已核对源码确认）：`codex-hooks.json` 目前只注册了两个事件——`PreToolUse`（matcher 精确匹配 `^apply_patch$`，拦截直接改 `.impl-package/state.json` 的补丁）与 `SessionStart`（matcher `^(startup|resume|compact)$`，跑 `situation.py render` 拼一段 resume capsule 注入上下文）。原表格的 `PostToolUse`、`SubagentStop` 和"关键状态转换前"三行，2026-09-07 复核后全部撤销，理由分别记在下面。

### 撤销的三行

- **`PostToolUse`（撤销）**：主控自己跑的语义 CLI 命令本身就设计成会自我校验、失败就非零退出（例如 `_evidence_coverage` 检查、`package validate` 拒绝非法状态），主控在同一轮 Bash 结果里已经能看到失败信息；hook 再包一层等于重复这个已经存在的反馈，没有增量。
- **`SubagentStop`（撤销）**：原方案是"worker 返回后检查其自报的信封格式、引用路径是否存在"。这类检查是纯格式核对，不产生 Astra 自己核实证据、diff 时不会顺带知道的新信息——如果 Astra 认真做了 SDD Step 5 的消费结果职责，格式问题会作为核实证据的副产品自然暴露；如果 Astra 没有认真核实，hook 报"格式通过"反而会造成假的安心感，不解决真正的问题（Astra 有没有真的去看）。撤销后改为在 worker 派发阶段（brief/[worker-briefs.md][worker-briefs]）把返回格式要求写清楚，属于既有流程加强，不是新增 hook。
- **"关键状态转换前"硬拦截（撤销，已确认重复劳动）**：查证 [`engine.py:1329-1339`][state-engine] 的 `command_set_state`——`ticket satisfy` 已经在写入前调用 `_evidence_coverage` 核对每个 claim 是否有真实支撑证据、有无矛盾，以及 implementation/acceptance 依赖是否已放行，任一不满足直接 `raise StateError`，命令失败、状态不会被写坏。[`engine.py:1611-1629`][state-engine] 的 `command_gate` 在 `pass` verdict 时同样会重新核对每个 SATISFIED Ticket 的证据是否对得上当前 commit、依赖是否放行、terminal verdict 是否有 durable-delta 理由。这条设想的硬拦截已经在语义 CLI 里实现，不需要另建 hook。

### 保留的部分

- 决定：只保留 `SessionStart` capsule 的扩展方向——现有实现已经在 session 启动/恢复/compact 时自动跑 `situation.py render` 补上下文（这是 Astra 真的拿不到的信息，不是格式检查），可以考虑让同一套逻辑在更多衔接点（如 handoff）触发，内容不变，只是触发时机增加。这不是新机制，是扩展已经工作的现有 capsule。
- 与 T9 的关系：不为使用 hook 而保住旧字段。T9-P 八项的逐字段处置仍为暂缓，本节收窄不改变 T9 的结论。
- CLI 命令面核查（2026-09-07 新增）：搜索 `engine.py`/`command_groups.py`/`situation.py` 未发现任何专属于 D1（bookkeeper）、D2（Ticket 激活 preflight）的 CLI 命令或参数——这两项从一开始就是纯 SKILL.md/角色文字层面的协议，没有写成语义 CLI 的命令，因此退休它们不涉及代码层改动。旧的自由文本 marker 扫描代码也已经在更早的重构中清理干净，没有遗留死代码。T9 的 22 个删除项（`FACT_KEYS` 常量、对应 `_when_*` 函数、situations.yaml 消费 slug）已经是这部分代码变更的完整范围，没有发现额外需要退休的 CLI 命令面。
- 确认依据：用户同意 hook 接入方案框架；2026-09-07 复核阶段，用户直接指出 `PostToolUse`"范围广、没有实际收益"、`SubagentStop` 的格式检查"没有新信息"，两点均查证成立并撤销；"关键状态转换前"经查证已在 `engine.py` 实现，同样撤销。

## 后续统一修改范围

- 调整：T1 步骤合并条件、T3 并行收益判断、T7 规则去重与案例位置、T8 证据有效性标准。
- 保持：T2 impl-planning 的复用/依赖/接线/验证判断职责、T4 Dispatcher/SDD 的逐步派审、T5 SDD/Dispatcher 的等待兜底与生命周期策略。
- 实例补充已确认：E1 修复导航误报并保留 escape；E2 用剩余业务交付判断并行收益；E3 允许主控直接承担难以拆开的跨线接线。
- 删除及承接：D1 execution-boundaries 专用 bookkeeper 流程、D2 Ticket 激活环境检查、D3 situations.yaml 中按 Ticket 自动交接的 legacy 触发；具体承接见下文。
- 观察项：E4 全量检查协调、E5 terminal-final 时机。用户已同意先保留观察，不在本轮新增相关规则或门槛。
- T9：T9-A–P 确认删除 22 个声明入口（其中 5 个保留现有计算或结构化输入判定）、保留 2 个 review summary、暂缓 8 个。本轮取舍结束；暂缓项不改，原分类表不作为实施依据。
- T10（2026-09-07 收窄）：只保留 `SessionStart` capsule 扩展；`PostToolUse`、`SubagentStop`、"关键状态转换前"硬拦截三项已撤销（分别因为重复 CLI 自带校验、纯格式检查无新信息、已在 `engine.py` 实现）。DSH 不在范围内。CLI 命令面核查未发现 D1/D2 有专属命令需要退休，T9 的代码变更范围已完整。
- 补充排查（2026-09-07）：backfill-stable-docs 核查健康，无需改动，其"常见误判"密度并入 T7；do-review 的 Loop 轮次上限确认为拍脑袋数字，本轮不改，留作观察。
- 复核补充（2026-09-06）：T7 采用真重复/执行提醒/纯测试价值三分，独特但无决策价值的内容不搬进 references。D1 清理旧 bookkeeper evals、intake-backlog 悬空路由及 bound writer 转交；to-tickets 的活跃模板和检查先保留，如迁移到 impl-planning，须同步更新消费者引用。落地时同步更新受影响 skill 的 rubric，避免已确认决定与偏好记录脱节。

## 实例研究 · 2026-09-06（E1–E3 已确认，E4–E5 保留观察）

### 来源与结论限制

- 实例包：`D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups`；读取时 KaiSpan HEAD 为 `06e28d24c1e4f431aecd896007a99507888febbc`，包内只有现存 trail lock 为 untracked，本轮未修改该包。
- 用户提供模型归属：前 11 票 Sol/High，后四票 patch Astra/High。initial 材料还含 TKT-12/13；对照仅采信可归属 TKT-01–11 的事件，不把整个 initial 等同于用户的 11 票。
- 主控检查 patch Plan、Progress、ER、现存两份 trail 和相关规划回执；两位 Luna 分别核查 initial 实例和 patch 执行摩擦。对“KS-银行流水N-M对账10”（01a0712d-64be-7c93-befd-d529fd220d84）及“KS-银行流水N-M对账11”（01a07392-cc6d-70c0-96e4-19bd560f64fa）的任务记录只按需抽取用户纠偏、相关消息和命令，未通读完整历史。
- 两阶段合同、复用基础、Owner 输入和规则版本均不同；记录条数不等于实际调用次数或时间成本。这不是 Sol 与 Astra 的受控性能比较。
- 当前 patch Progress 为四票 SATISFIED / Gate pass；历史 ER 的 PENDING 和失败记录只用于解释当时过程。

### E1 · 保留 escape，先修导航误报（已确认）

- 修改落点同 T6：[situation.py][situation-cli] 对当前 Attempt 的判断与 [runtime engine][state-engine] 一致；不重做 [situations.yaml][situations] 的整套策略。
- 现存 patch 两份 trail 共 108 行，其中 7 条 escape：3 条处理历史 Gate 误报，4 条补齐 Topic 与 Ticket 的进度显示关联。它们不是 7 次普通调度偏好选择，不能据此支持普遍取消 escape。
- [ER-001](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:22) 记录 canonical validate 为当前 attempt active、gate=null，但 situation 误把旧 initial/defer 当 terminal；escape 留下权威依据并允许业务继续，无需把插件修复塞进业务包。
- [trail 第 2 行](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/trail.jsonl:2) 与[第 82 行](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/trail.jsonl:82) 在恢复时引用既有 ER，而非重新设计处理机制；[第 62 行](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/trail.jsonl:62) 起四条修复进度关联。
- 核对 workbench 当前源码仍有同一差异：`situation.py:_parse_gate` 只解析 verdict/commit，`_when_gate_terminal` 按 verdict 判断；runtime engine 的 `_lifecycle` 先匹配 Attempt。因此优先统一当前 Attempt 的事实判定，减少错误建议的触发，保留 escape 的提醒与审计用途。
- 初次偏离写明依据；相同原因再次出现时，可像本实例一样引用已记录判断并核实当前事实。暂不新增豁免缓存、例外 registry 或另一套状态。
- 确认依据：用户回复“同意 E1～E3”，替代 T6 的暂缓决定；尚未执行代码修复。

### E2 · 补强 T3：把并行收益落实到尚未完成的交付（已确认）

- 落点：[dev-with-track 的业务动作选择][dev-with-track]、[Dispatcher 的返回后补派][dispatcher]；SDD 保留逐步 review 与任务边界。
- [ER-016](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:268) 明确记载“5 个 Delta 占用而实施停派”，[ER-017](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:284) 又在 Owner 提醒主线不足后补到六条实施线。任务记录有对应用户纠偏，说明不只是缺少槽位。
- 决定：消费返回后，优先看仍未接通的业务路径，释放已就绪、能推进交付的实施；不要只围绕最近 findings 循环安排局部修复。保留 T4 及时派审、必要依赖与 review 积压处理，不设固定实施/review 槽位配额。

### E3 · 主控可直接完成难以拆开的跨线接线（已确认）

- 落点：[dev-with-track 的主控职责与执行选择][dev-with-track]；按 [Dispatcher][dispatcher] 和 [SDD][sdd] 的修改范围、资源与独立 review 规则执行。
- [ER-014](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:234) 在 Owner 允许后，由主控处理跨 Lane 的 Job claim 传播及 source caller 接线，并得到独立检查；[ER-015](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:251) 将 context 隔离置于 Lane 名称复用之前。
- 决定：有清晰边界的工作继续由 Luna 承担；强依赖主控已有综合上下文、拆分交接成本更高的接线，允许主控直接实现。明确当次 write ownership，保留独立 delta review；不把主控直接编码变成另一套执行流程。

### E4 · 全量检查作为共享资源协调（观察项，本轮不新增规则）

- 观察归属：[SDD 的资源协调 reference][resource-admission] 和 [progressive-system-evidence.md][system-evidence]。后续实例再判断是否需要改动。
- [ER-012](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:202) 的全 API typecheck 混入其他 Lane WIP，不能归因固定 HEAD；[ER-017](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:284) 因 worker 改写中的文件暂缺触发 TS6053。
- [ER-013](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:217) 记录 cutover 149.51 秒、collect 97.31 秒，随后停止各 Lane 重复全量 tsc。该记录表明争用被观察到，但不能单独证明全部耗时由 tsc 造成。
- 建议：worker 保留 focused checks；全量 typecheck/build/跨包检查由一个 owner 协调，在相关输入稳定时执行。WIP 上的探索检查可用于定位，但不能冒充固定 revision 的完成证据。复用现有 resource/verification 语义，不增加全局矩阵或新 gate。

### E5 · terminal-final 时机（观察项，本轮不新增门槛）

- 观察归属：[dev-with-track 的 Review/Gate][dev-with-track] 与 [do-review][do-review] 的 terminal-final 入口；以下保留实例和原建议，不作为本轮实施要求。
- [ER-031](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:512) 在 retained 业务范围未决、claim 审计进行中时已启动四轨 terminal-final；[ER-036](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/20260905-0903-pool-centric-settlement/execution-record.md:589) Owner 随后确定范围并取消旧库兼容，47 claims 变为 44 且删除旧实现。此前比较点无法直接代表最终候选。
- 后续终审仍发现真实恢复、传播和并发问题，不能把反复终审全部归为浪费，也不支持取消 review。
- 建议：已知会改变代码/合同的决定未闭合、或已知实现仍未完成时，继续 delta/必要范围审查；完整 terminal-final 等最终候选基本稳定再运行。不新增 fingerprint、approval 或 readiness 状态。

### 保留的保护，以及不再叠加的流程

- initial [TKT-01 纠偏](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/initial/execution-record.md:55) 防止单组模型冒充多组；[TKT-05 验收回退](/D:/CodeSpace/kaispan-dev/.worktrees/260824-finance-assistant-mvp-implementation/docs/domains/finance-assistant/implementations/2026-08-31-bank-reconciliation-nm-settlement-groups/execution/initial/execution-record.md:217) 暴露真实 race、source-CAS 和 Office failed-state 缺证，阻止释放下游。这支持保留合同精度与 claim/evidence 审计。
- 真实入口复用假设失效、Node/profile/DI/测试 schema 载体失败确有实例；现有 planning、环境与渐进证据指导已覆盖，不再据此新增逐 producer 台账、固定 preflight 清单或一套 fingerprint。
- 用户已确认 E1–E3，并在本轮收口时同意 E4–E5 保留观察；其余 T1–T8 决定不变。D1–D3 的删除与承接决定见下文。

## 整项删除讨论

### D1 · 专用 bookkeeper 角色与回执循环（已确认删除）

- 落点：[execution-boundaries 的异常流程][execution-boundaries]、[bookkeeper 角色 reference][bookkeeper-role]；联动清理 [impl-planning][impl-planning]、[plan-review][plan-review] 的 bound writer 转交和 [dev-with-track/Runtime Protocol][runtime-protocol] 的专用角色路由。
- 删除专用角色、correction event 往返、专用回执记录要求，以及 impl-planning 残留的 bound writer 转交；日常文档由 owning-stage 主控写入，runtime state 仍走语义 CLI。
- 异常只留一句提示：主控直接核对状态与证据；复杂时委派只读调查，主控依据结果完成修复并记录必要判断。
- 用户明确同意，并要求异常情况“只需要提一下即可”；不把异常重新展开成另一套流程。
- 2026-09-06 复核补充（Claude Code 审阅，需在落地时一并处理，原落点未覆盖）：
  1. [`skills/standing-bookkeeper/`][standing-bookkeeper] 在仓库源码里已经只剩 `evals/evals.json`，没有 `SKILL.md`（`git log` 确认 `14eef49 refactor(impl-package): demote standing bookkeeper to a slow path` 已把内容并入 execution-boundaries，只是没清理这个目录）。这份孤儿 evals 测的还是“bookkeeper 负责物理写入 spec.md/execution-record”的旧架构，跟现在 execution-boundaries 里“主 thread 保留…`state.json` 的唯一写入权”“bookkeeper 不独占 package 物理写入”直接矛盾，不只是孤儿、内容也已过期，需要删除或按新模型重写，不能留着当死档案。
  2. [situations.yaml 的 `package.record.intake-backlog`][situations] 默认动作仍是 `"/impl-package:standing-bookkeeper drain intake queue"`，指向一个源码里已经没有 `SKILL.md` 的 skill；需要同步改指向（例如改为提示主控直接处理）或删除该 situation。
  3. [`skills/to-tickets/`][to-tickets] 虽无 `SKILL.md`，但 Ticket 模板和有效 evals 仍有消费者，例如 [规划合同检查脚本][planning-contract-check] 直接读取其中的模板；不能作为死目录顺手删除。若后续整理目录，可迁移到 impl-planning 并同步更新引用，否则保留现有落点。
  4. impl-planning/plan-review 的“bound writer”落点比原描述更具体：execution-boundaries 现有 `SKILL.md` 全文（preflight / 异常 / 收口三段）并没有一段描述自己执行“物理写入 Plan/Ticket 文件”，[impl-planning][impl-planning] 第 8、45 行和 [plan-review 的 Apply boundary 整节][plan-review]（第 55-57 行）里“由 bound execution-boundaries 写入”已经是指向空气的过期交接。目标状态是对齐 [req-align 的 rubric][req-align-rubric] 里已经确认的模式（“owning-stage 主 thread 直接更新业务文档…不引入记账 subagent 作为第二个 writer”，2026-09-05 已确认），三处一起改成主 thread 直写，runtime state 仍走语义 CLI。

### D2 · Ticket 首次激活环境 preflight（删除及承接方案已确认）

- 删除落点：[dev-with-track 的“Ticket 激活 preflight”][dev-with-track]、[execution-boundaries 的“Ticket 首次激活”及重复限定][execution-boundaries]；检查承接到以下两个现有 reference。
- 用户要求结合实例明确检查的承接位置。删除以 Ticket 激活为触发的固定环境检查，保留 package 授权确认和真实操作前的环境保护。
- 调度资源由 [SDD 的 references/parallel-work-admission.md][resource-admission] 承接：当前步骤实际使用共享环境时，确定资源 owner、隔离/串行安排与 cleanup owner；纯代码步骤不等待数据库或浏览器启动。该 reference 的读取条件覆盖实际运行资源使用，而非仅多 worker 并行。
- 真正运行前由 [插件共享 references/progressive-system-evidence.md][system-evidence] 的现有运行前检查承接：按 Planned Verification 和项目既有 runner/runbook，核实命令实际使用的目标、身份/配置、必要健康状态、应用/测试库隔离；适用范围包含真实 DB/browser/provider 操作，不只按“昂贵”判断。运行者检查，主控保留授权与资源协调责任；主控自行执行 E3 工作同样适用。
- `dev-with-track` 删除“Ticket 激活 preflight”小节，只在实际运行动作处指向上述方法；`execution-boundaries` 保留 package 授权和完成证据边界，移除 Ticket 环境四项和相关重复限定。Planned Verification 继续保存项目特定目标，不新增检查表、状态、角色或 receipt。
- 实例：ER-002 的纯 Core/UI 实现不依赖默认 5433 端口可用；PG 实跑时应由项目 runner 核验 overlay 加载后的 55433/kaispan_test，并与应用库 15433 区分。ER-008/020 的 profile 覆盖 APP_ENV 由项目已有运行 guard 捕获，不能用先前 Ticket 激活时的判断代替。
- 原四项覆盖：目标身份及库分离在实际运行前核实；端口/资源 owner 在调度时明确，运行时复核目标归属；cleanup owner 在调度时确定，运行后回收结果或残留。环境失败只暂停依赖它的动作，其他已就绪工作继续。
- 同一配置的运行可复用已核实事实，命令保留项目已有目标 guard；环境、身份或配置变化时重核受影响部分，不因换 Ticket 重做一轮。
- 确认依据：用户在看到资源调度、实际运行前检查及实例映射后回复“OK”。

### D3 · Ticket 完成自动触发主控换 session（已确认删除）

- 落点：[situations.yaml][situations] 的 `attempt.record.ticket-boundary-handoff` 及耦合的 `attempt.record.trail-rotation-due` 指引；核对 [dev-with-track Restore][dev-with-track]、[Runtime Protocol][runtime-protocol] 中真实交接的承接。
- 用户确认属于 legacy，删除 Ticket 完成自动触发主控换 session 的规则。
- 保留 Owner 主动交接和实际上下文压力下的 checkpoint/handoff；worker 等待兜底及 Topic 生命周期不变。
- 检查与该 legacy 触发耦合的 trail 轮换指引，不删除历史 trail 或实际交接所需的恢复能力。

[req-align]: ../../plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md
[impl-planning]: ../../plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md
[dev-with-track]: ../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md
[dispatcher]: ../../skills/dispatcher/SKILL.md
[sdd]: ../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/SKILL.md
[execution-boundaries]: ../../plugin-marketplace/plugins/impl-package/skills/execution-boundaries/SKILL.md
[do-review]: ../../plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md
[plan-review]: ../../plugin-marketplace/plugins/impl-package/skills/plan-review/SKILL.md
[situation-cli]: ../../plugin-marketplace/plugins/impl-package/scripts/situation.py
[situations]: ../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml
[state-engine]: ../../plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py
[system-evidence]: ../../plugin-marketplace/plugins/impl-package/references/progressive-system-evidence.md
[worker-briefs]: ../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/worker-briefs.md
[sdd-evals]: ../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/evals/evals.json
[plan-template]: ../../plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/plan.md
[ticket-template]: ../../plugin-marketplace/plugins/impl-package/skills/to-tickets/assets/templates/ticket.md
[runtime-protocol]: ../../plugin-marketplace/plugins/impl-package/skills/dev-with-track/references/runtime-protocol.md
[resource-admission]: ../../plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/references/parallel-work-admission.md
[bookkeeper-role]: ../../plugin-marketplace/plugins/impl-package/skills/execution-boundaries/references/role.md
[standing-bookkeeper]: ../../plugin-marketplace/plugins/impl-package/skills/standing-bookkeeper/
[to-tickets]: ../../plugin-marketplace/plugins/impl-package/skills/to-tickets/
[req-align-rubric]: ../../plugin-marketplace/plugins/impl-package/skills/req-align/rubric.md
[situation-inputs]: ../../plugin-marketplace/plugins/impl-package/references/situation-inputs.md
[codex-hooks-config]: ../../plugin-marketplace/plugins/impl-package/hooks/codex-hooks.json
[codex-hooks-code]: ../../plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py
[codex-hooks-reference]: ../../plugin-marketplace/plugins/impl-package/references/codex-hooks.md
[review-output]: ../../plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md
[planning-contract-check]: ../../plugin-marketplace/plugins/impl-package/skills/impl-planning/evals/step4_composition_contract.py
[backfill-stable-docs]: ../../plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md
