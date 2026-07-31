# Dev With Track Runtime Protocol

仅在当前分支触及对应阶段时读取本文件；它是 `dev-with-track/SKILL.md` 的详细执行规则，而不是独立 skill。

## Restore and readiness

1. 用 delta-first restore：读取仓库规则、两个 sidecar、current plan、最新 gate、最近可靠 ER/comparison point 与后续 diff；只有冲突或 provenance 缺口才回扫历史。
2. 从 registry current attempt 和 canonical gate resolver 推导唯一 lifecycle。无 Active attempt 或多个 Active attempt 都停止并路由，不按时间猜测。
3. 运行 `impl_package_state.py --package <path> validate --committed`。它是 revision binding、append-only ER、earned record、projection 和 gate binding 的唯一可信检查。
4. 确认 current Composition 的 tickets/DAG 已发布、对齐且有同一 bundle 的联合 review/approval；缺任一项不能执行。
5. evidence 胜过 stale status。P revision 变化时只重验受影响 subset；不逐项重跑未受影响的验收。
6. 新 attempt 要核对 Module Knowledge Watermark；随后校验 typed edges、DAG dependency、contribution 和 cycles，再按 plan 顺序选第一个 actionable unit。

高风险 unit（持久化、权限、并发、外部 mutation、recovery 等）开始前必须已能定位 spec/AC、可执行场景或入口、oracle 与 ER owner。缺 spec/AC 路由 `req-align`；缺 plan verification 路由 `impl-planning`；只有 ticket/DAG 引用错才路由其 owning skill。

目标分支已包含 comparison point 但 attempt 仍 Active 时，只能报告 `Integrated, gate open`。没有 plan 预先记录的 owner-approved pre-gate integration，不得把已合入当成完成或 merge-ready，也不得事后补写授权来清除该事实；最终 pass/closed 仍须来自目标分支 evidence。

若 decomposition/readiness defect 不改变业务结果，只涉及 typed edge、Task 顺序、contribution 或 artifact 引用，调用 owning skill 机械修正并做受影响 subset 验证即可。若改变 Ticket acceptance boundary、planned evidence、ownership、执行顺序或 gate，bundle approval 失效，必须回 planning/review；只有改变业务结果、Acceptance Semantics、安全/外部 authority、Composition earned artifact，或存在多个不同业务结果的方案时才请求 owner。

低频情况下，上游 Ticket 仍为 `IN_PROGRESS` 或 Task 仍为 `RUNNING`，但已形成可复用实现检查点时，主 session 可提前派发仅依赖该检查点的下游 Ticket/Task implementation。主 session 按实际 seam、diff、证据与 open findings 判断，不新增状态、artifact、checklist 或自动算法。提前派发必须同时满足：

- 下游实际依赖的接口或行为已经提交并有局部测试证据，且下游执行基线能够使用该实现。
- 主 session 确认实际剩余工作与 open findings 不会改变下游依赖的合同或可观察行为；不能仅按测试覆盖、review closure、观测性等类别认定安全。
- 派发前，主 session 根据当前 diff 与证据在既有 plan Execution Record 追加一次记录，说明共享 seam、工作边界与回退条件；不要求上游预先写好专用检查点记录。
- 只提前启动 implementation；acceptance 和 release dependency 均不因该例外释放，继续按各自既有 gate 与语义判断。下游 implementation 启动也不表示原 dependency edge 已正式释放，不能支持任何 acceptance 结论。
- 上游若改变下游依赖的合同、行为、错误语义、时序、兼容性或其他关键事实，主 session 停止沿用受影响的下游工作与旧证据，将相关 Ticket/Task 置为 `NEEDS-REVALIDATION`，完成 scoped reconciliation 后再继续。

## Runtime state and evidence

- dag=true 时，runtime-state 是 task SoT，Ticket acceptance 同样由 ticket record 投影；状态只能经 `set-state --expect --evidence` 变更。
- 只在 BLOCKED、handoff、retry 或并行派发时写 task progress；它不复制 Ticket AC 或第二套状态。
- 返工上游输出时将依赖标为 `NEEDS-REVALIDATION`；DONE 只有在 Done-when 证据存在时释放依赖，WAIVED/SUPERSEDED 必须有替代证据和 impact note。
- 每次实际检查前先通过 committed validate，再在 plan Execution Record 追加 append-only ER，记录 command/check、结果、证据位置与残余风险。外部 artifact hash 用 artifact CLI 维护。
- 手工验收前，按 `assets/templates/manual-acceptance-readiness.md` 将必要 readiness packet 追加到最新 ER 或 canonical handoff；只填写适用 optional 项，不输出 N/A；它不替代验收证据。

ER 不复制通用 checklist 或完整 hash 清单，只记录本次 delta；旧 ER 不得修改。可把真实调查材料写入 `investigations/<topic>.md`，但它不拥有 authority、不绑定 revision、不维护 adoption/backlink，Decision/Spec 必须脱离它仍自足。

## Progressive system evidence

仅当当前 attempt 有跨模块业务链、`material seam`、昂贵验证或已发生系统性 failure 时，读取 [`../../references/progressive-system-evidence.md`](../../references/progressive-system-evidence.md) 并按以下最小动作执行；低风险局部改动继续走轻量路径。这不是 E2E admission gate、新 artifact、runtime state 或 approval。

1. 声明当前要证明的 system assumption。用 reference 的四问和反例保留排除不忠实边界；在忠实候选中比较总证据成本，成本接近才优先更早反馈。
2. 已知确定性内部前置缺证据时默认先补便宜且忠实的证据。真实环境独有、探索诊断或边界未知时可有界运行 E2E/provider/browser/native tool；每次写明候选假设、决定性 checkpoint/artifact 和结果分流，重复运行必须有新假设、环境/修复 delta 或观测能力。
3. checkpoint 优先复用现有 inspector、业务日志、test probe 或外部 artifact，并足以定位最后成立与首个失效假设。证明 authority 提交或副作用时必须直接观察 authority 或可机械追溯 provenance；UI、cache、日志副本和派生投影只用于定位。
4. failure 分类是可修订、可多因的工作假设。只有可稳定复现、保留关键因果机制、有更便宜稳定 oracle、无 production fixture 特判且与当前风险相关时才下沉；否则记录 readiness、runbook、observability、residual risk 或真实验证。
5. 现有 contract 能唯一裁决时按 implementation defect 修复；不能裁决时停止受影响单元并路由 `req-align`。沿当前业务动作修复首个违反既有 contract 的边界；worker、adapter 或测试不得临时发明共享语义。
6. 只在版本兼容、序列化/映射、authority 切换、跨 consumer 解释分歧或静默信息丢失时做 seam sweep。范围限于当前业务动作中共享受损表示或 authority fact 的语义相邻边界，不做全仓扫描或 consumer registry。
7. 已批准策略内的候选假设、控制变量、checkpoint 与有信息增量的重跑理由只 append ER，不升级 P revision。只有 claim、验证策略、required evidence、覆盖范围或外部 mutation authority 改变时才回 `impl-planning`；ER 和 `execution-findings.md` 不形成第二份 Planned Verification 合同。

completion claim 仍由 `verification-before-completion` 审计。复用 evidence 时，除 revision/worktree/environment 外，按当前 claim 检查协议版本、feature flag、schema、部署配置、共享数据前置或认证策略等关键因果输入；相关变化只使受影响 evidence stale，无关变化不触发机械重跑或 freshness registry。

## Review, finding and acceptance routing

Task `DONE` 不是 Ticket acceptance。主 session 负责跨 Task 集成和 acceptance，但不自行代替 task worker 或 leaf reviewer。Ticket 候选前先检查所有 contributes-to 的 BLOCKED task；固定 comparison point，按实际 diff、contract impact 和定向证据做风险判断。

Review/revise 期间，只有“存在受阻下游”和“新证据表明其依赖 seam 已稳定”同时成立时，主 session 才进入可复用实现检查点分支。相关未完成 review 或 open finding 仍可能改变该 seam 时继续等待；否则复用上面的既有条件记录 ER 并派发，下游 implementation 与上游 review/closure 可并行。`do-review` 与 leaf reviewer 不作调度判断；这不是新的 stage、状态或 checklist，也不改变 acceptance/release gate。

- 局部、可逆、无共享 contract/状态/外部副作用的 diff 可直接记录理由与证据后进入 claim audit。
- 普通实现需要正式 review 时默认选择 `code-review`；interface、状态机、模块 seam 倾向 `standards-review` / `spec-review`；数据完整性、证据 authority、auth、外部 mutation、并发等必须 `safety-review`。
- 一旦需要正式 review，主 session 只把明确 reviewer selection 交给 `do-review`；`do-review` 是范围固定、leaf 调度、ledger 与 finding 分类的唯一编排器，不能由本 skill 或 worker 直接替代。
- 正式 review 的 P1/P2 必须修复并 closure verify，才可验收 Ticket。
- conditional evidence-integrity contract 要有适用 false-PASS 与失败/失效路径证据；绿色正向测试不能单独释放依赖。

执行 finding 的分流：decision/rationale → `req-align` decision；行为/接口/约束/acceptance semantics → `req-align` spec；长期知识 → gate Durable Deltas 与 `_pending.md`；验证事实 → ER；其余 confirmed finding → `execution-findings.md`。发现 D/S revision 升级后，先 `refresh-projections`，再按影响范围 reconcile。

存在未完成的规范性分流时不得写 terminal pass/fail/defer entry；blocked entry 可以记录当前缺口。

## Claim and gate

terminal `pass` 前必须调用 `verification-before-completion`，以当前 revision/worktree/environment 审计拟声明、ER/review/smoke evidence。证据 stale、跨 revision/environment 或不足时只补受影响检查；commit、merge 或相关环境变化后，对外 completion claim 前再次审计。

初始 attempt 不要求预建 `gate.md`；不存在只表示 open/no-verdict。terminal pass/fail/defer entry 才冻结 attempt，blocked entry 保持 Active。

gate 使用 `new-gate-entry` 分配 ID，正文必须包含 attempt、supersedes、时间、D/S/P、binding validation、Composition、comparison point、ER、blocker/deferred、verdict reason、Durable Deltas；写完立即 `finalize-gate-entry`。旧 entry 不修改。blocked 保持 Active；pass/fail/defer 才 terminal/frozen。

blocked 后补证要新增并 supersede；D/S 改变后旧 gate 只证明旧 revision。terminal 前全局确认没有 BLOCKED task、所有 task 为 DONE 或有已批准的 WAIVED/SUPERSEDED 理由、Ticket AC 与 active Spec 全覆盖。terminal metadata、相关 commit、target merge 或环境变化后，对外 completion claim 前重新跑 claim audit。

GO 后必须自动完成适用验证、review、finding 分流、claim audit 与 gate verdict；不能把它们变成二次 owner approval。仅 push、合入、生产/共享可变操作、未预授权的 pre-gate integration 或会改变业务结果的方案仍需要 owner。

## Stage 7

terminal entry 有 durable delta 时，先写 gate delta、在 `_pending.md` 注册 `<destination>|<delta-id>`、在受影响 module spec 写 pending truth pointer（缺 spec 先建 stub），再 finalize gate。无 delta 时明确写 none 和理由。terminal 后可非阻塞提示 `$backfill-stable-docs`，但不自动运行或作为当前 gate blocker。
