---
name: codex-crew-lite
description: Explicitly invoked Lite assurance profile for Codex Crew assignments. Use only when the user names $codex-crew-lite or directly asks to run a bounded issue through Crew Lite; do not implicitly invoke it because a task mentions worktrees, workers, or parallel fixes.
disable-model-invocation: true
user-invocable: true
---

# Codex Crew Lite

> **Invocation gate:** This Skill is opt-in. Do not continue reading it or its shared contract/assets merely because it is discoverable. Continue only after the user explicitly invokes `$codex-crew-lite` or directly asks to run Crew Lite; otherwise stop here.

Lite 是 Orchestrator 分配给一个或多个 bounded assignment 的 assurance profile，不是第二个顶层 scheduler，也不要求整次 run 的所有 assignment 都使用 Lite。主会话仍是 Broker；Orchestrator 负责拆分、路由、创建 Worker assignment、纠偏和验收；Worker 自主完成实现并管理自己的 Subagent。

先阅读共享 [continuation contract](../references/codex-crew-continuation-contract.md)、当前 [运行指南](../references/codex-harness-guide.md)、[runtime policy v1.3](../assets/codex-harness-runtime-policy.v1.3.json)、[execution profiles v0.2](../assets/codex-harness-execution-profiles.v0.2.json)、[control schema v0.5](../assets/codex-crew.control.v0.5.schema.json) 和 [Orchestrator turn schema v0.3](../assets/codex-crew.orchestrator-turn.v0.3.schema.json)。旧 dispatch/topology 示例仅用于历史参考；不要从 Markdown prompt 复制配置值。

## 适用边界

Orchestrator 可将 assignment 标为 Lite，前提是目标和验收已理解，且不需要 redesign、接口/数据迁移、权限变化、不可逆外部副作用或改变验收口径。Worker 在执行中发现这些边界时，通过 `ask_owner` 或控制协议请求 promotion 到 Full；不能自行放宽 assignment 或静默改变目标。

## 运行方式

Orchestrator 用 `dispatch` 定义或修订 Lite assignment，记录目标、非目标、acceptance、profile、context、完整 write ownership 和明确 workspace intent；该动作不创建 worktree、不启动 Worker。`fresh context`、是否 dispatch、活跃 write worktree 和 assurance 是必须分别记录的运行时事实，不能从 Crew intent、Issue 数量或 ready 状态互相推导。

需要执行时，Orchestrator 用 `control start_workers` 明确列出本次 cohort。Controller 在任何物理创建前统一检查依赖、Owner gate、profile、workspace、完整 ownership、lease 冲突和资源上限；通过后才启动 selected Worker，未被选中的 ready assignment 保持不变。普通纠偏使用 `control continue_worker`，Owner 边界使用 `ask_owner`，Subagent 仅由 Worker 调用。

Orchestrator 检查 Worker 的 assignment、允许路径、commit/diff、声明的验证命令和结果状态；确定性证据充分时显式 `control accept` Lite assignment。Acceptance 不自动关闭 run；Orchestrator 在 canonical 事实支持时显式 `finish`。任一 turn 可更新 Crew intent 或附带重大调整 notification，但 notification 不等于 Owner approval。Controller 不自动 merge、release、cleanup、扩大权限、启动 Worker 或推进下一个 assignment。

严格串行的多个 assignment 可以使用 fresh Worker context，并在同一 run 内顺序使用多个 branch/worktree；串行只描述一个时刻的活跃写 lease，不约束 run 内累计 workspace 数量。Workspace path、branch、base ref 和 `new`/`reuse` 由 Orchestrator 显式决定；只有 `reuse` 与同 run accepted `handoff_from` 在 commit、clean、祖先连续和验证 gate 全部满足时才通过。Orchestrator 的 read-only 只禁止直接写业务交付物，assignment、lease、Worker、acceptance、Crew panorama 和 notification 等控制面记录仍由它管理。未 ready 或存在局部 Owner gate 的 assignment 及其严格下游不预建、不启动，无依赖工作可以继续。

Lite assignment 的 Worker 数量、精确拆分、Subagent 数量和 turn 顺序都不是硬验收门；Package、implementation、review loop 和内部步骤在责任边界不变时留给同一 Worker，Broker 不能自行拆成 canonical assignment。没有代码 diff 的外部 mutation 必须进入 Owner gate 并 fail closed，不得用空 commit、自然语言或伪造 artifact 标记完成。代码 handoff 与外部 operator/promotion gate 分开表达，未授权 gate 只阻断显式依赖它的下游；当前 Orchestrator 无网络，外部 API read-only preflight 只能作为人工/operator evidence。正常 turn 不因时长自动 interrupt，Broker 每三分钟仅观察；只有明确 cancel 才原子写 sidecar，由 active runner interrupt，停止未证实时 quarantine。Worker materialize 前必须从 canonical `model/list` 候选得到实际 profile，否则不建 worktree。没有有效 `finish` 的 run 只能报告观察到的事实。Lite Eval 同样是 Skill 行为回归，区分 `hard_invariants`、`forbidden_actions` 和 `advisory_quality` 三层，资产版本按 `0.1` 步进。

## 最小命令入口

```powershell
$runRoot = Join-Path $env:TEMP "codex-harness\lite-run"
$state = Join-Path $runRoot "run.json"
$artifactRoot = Join-Path $runRoot "artifacts"
python scripts/codex_harness_orchestrator.py start --repository-root . --issue-file issue.md --state $state --artifact-root $artifactRoot
python scripts/codex_harness_orchestrator.py message --state $state --message "继续处理当前 Lite assignment"
python scripts/codex_harness_orchestrator.py advance --state $state
python scripts/codex_harness_orchestrator.py status --state $state
python scripts/codex_harness_orchestrator.py cancel --state $state --reason "Owner requested cancellation"
```

命令参数、状态字段和 envelope 以 [control schema v0.5](../assets/codex-crew.control.v0.5.schema.json)、[Orchestrator turn schema v0.3](../assets/codex-crew.orchestrator-turn.v0.3.schema.json) 与 [cancel request v0.1](../assets/codex-crew.cancel-request.v0.1.schema.json) 为准；脚本不替 Orchestrator 决定拆分、prompt、Subagent 数量或调用顺序。

## Legacy 说明

Lite assignment 由 Orchestrator 显式能力调用驱动；`codex_harness_dispatch.py` 只执行已批准 assignment 的 Worker/worktree primitive。主会话不直接调用 adapter，controller 也不从 ready 状态自动补造 Worker；旧 parent/dispatch/topology 协议不再保留兼容入口。
