---
name: codex-crew
description: Explicitly invoked Full assurance profile for Codex Crew assignments. Use only when the user names $codex-crew or directly asks to run the complete Crew flow; do not implicitly invoke it because a task mentions Impl-Package, review, gates, or parallel agents.
disable-model-invocation: true
user-invocable: true
---

# Codex Crew

> **Invocation gate:** This Skill is opt-in. Do not continue reading it or its shared contract/assets merely because it is discoverable. Continue only after the user explicitly invokes `$codex-crew` or directly asks to run the Full Crew flow; otherwise stop here.

Full 是 Orchestrator 为特定 assignment 选择的高保证 assurance profile，不是一个接管用户会话的 scheduler。Broker 只面向用户；Orchestrator 是唯一业务 controller，负责分配 Worker、处理 Owner boundary、验收和交付汇总；Worker 负责 assignment 的设计、实现、自验和自己的 Subagent；Subagent 不进入顶层通信。

先阅读共享 [continuation contract](../references/codex-crew-continuation-contract.md)、当前 [运行指南](../references/codex-harness-guide.md)、[runtime policy v1](../assets/codex-harness-runtime-policy.v1.json)、[execution profiles](../assets/codex-harness-execution-profiles.v0.json) 和 [control schema](../assets/codex-crew.control.v0.1.schema.json)。Impl-Package、review 和 gate 的具体事实以其 canonical schema/工具输出为准，不在本 Skill 复制配置值。

## 何时使用 Full assignment

Orchestrator 可为 approved work package、需要独立 review/verifier、revision binding、持续恢复或更强证据的 assignment 选择 Full。`impl-package` 仍负责需求、D/S/P binding 和执行资格；它是输入与 gate 来源，不是 Crew 的第二 scheduler。S Composition 仍是组合路径，不等于“必然创建多个 Worker”。

Full 不要求并行。Orchestrator 先选择最小 topology：只读分析使用 `orchestrator_read_only`；严格有序或并行收益未证实时使用 `worker_serial`；只有至少两个 ready assignment 的写 ownership 互斥且有明确并行收益时使用 `worker_parallel`。`fresh context`、Worker dispatch、活跃 write worktree 和 assurance 是必须分别记录的运行时事实；一个 DAG 允许并行不构成默认并行理由。`worker_serial` 可以按 ready 顺序调用 dispatcher primitive，但任何时刻最多一个活跃写 Worker/worktree。

Full 的 assignment 数量、Issue 到 Worker 的精确映射、Subagent 数量和 turn 顺序都不是硬验收门；Orchestrator/Worker 可以在不改变授权、ownership、依赖和验收边界的前提下选择更简单的拆分。

## 运行方式

1. Broker 将需求和 Owner decision 交给 Orchestrator；Orchestrator 为每个 assignment 记录目标、非目标、允许路径、依赖、Full assurance、canonical profile、context 和验收条件。
2. Orchestrator 用 `dispatch` 建立或继续有界 Worker；同一契约内的纠偏用 `control` continue，范围、权限、不可逆副作用或验收歧义用 `ask_owner`。Owner decision 返回后在同一个持久 Orchestrator controller identity 下继续同一 run，可进行多轮 continuation，不静默替换成新的顶层 controller。
3. Worker 提交绑定 assignment、commit/diff、artifact、验证命令和风险的结构化结果。Orchestrator 机械检查路径、工作树、提交范围和命令证据，并用 `control` accept/continue/cancel；拒绝验收或要求返工统一通过 continue 表达。
4. Full assignment 在 Worker 自验之外使用独立、只读、非递归 verifier 或等价独立检查；Worker 管理的 Subagent 不能充当 verifier。Verifier 只复核固定 assignment/commit/evidence，不继续派生 verifier-of-verifier。
5. Orchestrator 用 `finish` 向 Broker 汇总结果、verifier disposition、未决 Owner decision、commit 范围和 terminal disposition；merge、release、cleanup 和 Owner 最终 promotion 仍由既有流程决定。

严格串行 handoff 可让不同 assignment 使用 fresh Worker context，并在前一 assignment 已提交、clean、祖先连续和独立验证证据存在时顺序复用一个 worktree。Orchestrator 的 read-only 只禁止直接写业务交付物，不禁止它写 assignment、lease、dispatch 或 acceptance 等控制面状态。上游 `needs_owner`、失败或未验收时，严格依赖的下游不预建、不启动。

没有代码 diff 的外部 mutation 必须进入 Owner gate 并 fail closed；不得用空 commit、自然语言或伪造 artifact 通过 Full acceptance。代码 handoff 与外部 operator/promotion gate 分别记录，未授权的外部操作只阻断显式依赖它的下游；当前 Orchestrator 无网络，真实外部 API 的 read-only preflight 只能作为人工/operator evidence。没有同一 run 的有效 `finish` 时，timeout run 只能报告观察到的事实，不得作为权威 dispatch 结论或笼统称为 `interrupted`。Full Eval 是 Skill 行为回归：`hard_invariants` 验证结构化控制面事实，`forbidden_actions` 捕获越权或危险动作，`advisory_quality` 只评价拆分和交付质量，资产版本按 `0.1` 步进。

## Review 边界

代码已存在且明确 base..head 后，再调用 `$do-review` 对整个变更范围做独立 review loop。只在当前 assignment/Owner scope 内处理确认的 P0/P1；P2 和 scope 外建议作为后续事项报告。Review agent 提供证据，不替代 Orchestrator acceptance 或 Impl-Package gate。

## 最小命令入口

```powershell
$runRoot = Join-Path $env:TEMP "codex-harness\full-run"
$state = Join-Path $runRoot "run.json"
$artifactRoot = Join-Path $runRoot "artifacts"
python scripts/codex_harness_orchestrator.py start --repository-root . --issue-file issue.md --state $state --artifact-root $artifactRoot
python scripts/codex_harness_orchestrator.py message --state $state --message "返回当前 Full assignment 的 verifier 结果"
python scripts/codex_harness_orchestrator.py advance --state $state
python scripts/codex_harness_orchestrator.py status --state $state
```

命令、状态和结构化 envelope 以 [control schema](../assets/codex-crew.control.v0.1.schema.json) 与 canonical runtime policy 为准；控制面不规定 Worker 的拆分、prompt、Subagent 数量或调用顺序。

## Legacy 说明

旧 `parent v2`、`dispatch v2`、`codex_harness_crew.py` 和 Package parent-stage runner 保留为 transition/compatibility path。新 Full assignment 推荐从 Orchestrator controller 进入；不要让主会话直接调用 dispatcher、把 legacy parent 当作业务实现者，或用伪造 parallel task 模拟 `worker_serial`。
