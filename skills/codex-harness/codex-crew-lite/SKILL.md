---
name: codex-crew-lite
description: Explicitly invoked Lite assurance profile for Codex Crew assignments. Use only when the user names $codex-crew-lite or directly asks to run a bounded issue through Crew Lite; do not implicitly invoke it because a task mentions worktrees, workers, or parallel fixes.
disable-model-invocation: true
user-invocable: true
---

# Codex Crew Lite

> **Invocation gate:** This Skill is opt-in. Do not continue reading it or its shared contract/assets merely because it is discoverable. Continue only after the user explicitly invokes `$codex-crew-lite` or directly asks to run Crew Lite; otherwise stop here.

Lite 是 Orchestrator 分配给一个或多个 bounded assignment 的 assurance profile，不是第二个顶层 scheduler，也不要求整次 run 的所有 assignment 都使用 Lite。主会话仍是 Broker；Orchestrator 负责拆分、路由、创建 Worker assignment、纠偏和验收；Worker 自主完成实现并管理自己的 Subagent。

先阅读共享 [continuation contract](../references/codex-crew-continuation-contract.md)、当前 [运行指南](../references/codex-harness-guide.md)、[runtime policy v1](../assets/codex-harness-runtime-policy.v1.json)、[execution profiles](../assets/codex-harness-execution-profiles.v0.json) 和 [control schema](../assets/codex-crew.control.v0.1.schema.json)。旧 dispatch v2 示例仅用于迁移兼容；不要从 Markdown prompt 复制配置值。

## 适用边界

Orchestrator 可将 assignment 标为 Lite，前提是目标和验收已理解，且不需要 redesign、接口/数据迁移、权限变化、不可逆外部副作用或改变验收口径。Worker 在执行中发现这些边界时，通过 `ask_owner` 或控制协议请求 promotion 到 Full；不能自行放宽 assignment 或静默改变目标。

## 运行方式

1. Broker 将需求交给 Orchestrator；Orchestrator 先建立 assignment，再为该 assignment 选择 Lite profile、context 和最小 topology。`fresh context`、是否 dispatch、write worktree 数量和 assurance 是必须分别记录的运行时事实。
2. 纯分析或确定性检查使用 `orchestrator_read_only`；写入严格有序或并行收益未证实时使用 `worker_serial`，由一个 Worker 按顺序交付，最多一个活跃写 worktree，也可顺序调用 dispatcher primitive；只有写 ownership 互斥且有明确收益才使用 `worker_parallel`。
3. Orchestrator 以 `dispatch` 启动或继续有界 Worker；普通纠偏使用 `control` 的 continue，Owner 边界使用 `ask_owner`，Owner decision 返回后在同一个持久 Orchestrator controller identity 下继续同一 run，可进行多轮 continuation；最终用 `finish` 返回结构化结果。Subagent 仅由 Worker 调用。
4. Orchestrator 检查 Worker 的 assignment、允许路径、commit/diff、声明的验证命令和结果状态；确定性证据充分时接受 Lite assignment。它不自动 merge、release、cleanup 或扩大权限。

严格串行的多个 assignment 可以使用 fresh Worker context，并在提交、clean、祖先连续和独立验证 handoff gate 全部满足时复用一个 worktree；fresh context 不要求新 worktree。Orchestrator 的 read-only 只禁止直接写业务交付物，assignment、lease、dispatch、acceptance 等控制面记录仍由它管理。未 ready 或 `needs_owner` 的下游不预建、不启动。

Lite assignment 的 Worker 数量、精确拆分、Subagent 数量和 turn 顺序都不是硬验收门；只要授权、ownership、依赖和事实验收满足，Orchestrator/Worker 可以自主选择更简单的实现。没有代码 diff 的外部 mutation 必须进入 Owner gate 并 fail closed，不得用空 commit、自然语言或伪造 artifact 标记完成。代码 handoff 与外部 operator/promotion gate 分开表达，未授权 gate 只阻断显式依赖它的下游；当前 Orchestrator 无网络，外部 API read-only preflight 只能作为人工/operator evidence。没有有效 `finish` 的 timeout run 只能报告观察到的事实，不能当成权威 dispatch 结论或笼统称为 `interrupted`。Lite Eval 同样是 Skill 行为回归，区分 `hard_invariants`、`forbidden_actions` 和 `advisory_quality` 三层，资产版本按 `0.1` 步进。

## 最小命令入口

```powershell
$runRoot = Join-Path $env:TEMP "codex-harness\lite-run"
$state = Join-Path $runRoot "run.json"
$artifactRoot = Join-Path $runRoot "artifacts"
python scripts/codex_harness_orchestrator.py start --repository-root . --issue-file issue.md --state $state --artifact-root $artifactRoot
python scripts/codex_harness_orchestrator.py message --state $state --message "继续处理当前 Lite assignment"
python scripts/codex_harness_orchestrator.py advance --state $state
python scripts/codex_harness_orchestrator.py status --state $state
```

命令参数、状态字段和 envelope 以 [control schema](../assets/codex-crew.control.v0.1.schema.json) 为准；脚本不替 Orchestrator 决定拆分、prompt、Subagent 数量或调用顺序。

## Legacy 说明

`codex_harness_crew.py`、`codex_harness_dispatch.py` 和 `codex-crew-dispatch.v2.schema.json` 是 legacy/transition adapter，保留用于已有 fixture 或迁移中的 worker/worktree primitive。新 Lite assignment 应由 Orchestrator 入口驱动，主会话不直接调用 dispatcher，也不通过伪造 worker task 模拟串行执行。
