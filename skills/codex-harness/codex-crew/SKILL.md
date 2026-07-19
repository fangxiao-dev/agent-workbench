---
name: codex-crew
description: Explicitly invoked Full assurance profile for Codex Crew assignments. Use only when the user names $codex-crew or directly asks to run the complete Crew flow; do not implicitly invoke it because a task mentions Impl-Package, review, gates, or parallel agents.
disable-model-invocation: true
user-invocable: true
---

# Codex Crew

> **Invocation gate:** This Skill is opt-in. Do not continue reading it or its shared contract/assets merely because it is discoverable. Continue only after the user explicitly invokes `$codex-crew` or directly asks to run the Full Crew flow; otherwise stop here.

Full 是 Orchestrator 为特定 assignment 选择的高保证 assurance profile，不是一个接管用户会话的 scheduler。Broker 只面向用户；Orchestrator 是唯一业务 controller，负责分配 Worker、处理 Owner boundary、验收和交付汇总；Worker 负责 assignment 的设计、实现、自验和自己的 Subagent；Subagent 不进入顶层通信。

先阅读共享 [continuation contract](../references/codex-crew-continuation-contract.md)、当前 [运行指南](../references/codex-harness-guide.md)、[runtime policy v1.3](../assets/codex-harness-runtime-policy.v1.3.json)、[execution profiles v0.2](../assets/codex-harness-execution-profiles.v0.2.json)、[control schema v0.5](../assets/codex-crew.control.v0.5.schema.json) 和 [Orchestrator turn schema v0.3](../assets/codex-crew.orchestrator-turn.v0.3.schema.json)。Impl-Package、review 和 gate 的具体事实以其 canonical schema/工具输出为准，不在本 Skill 复制配置值。

## 何时使用 Full assignment

Orchestrator 可为 approved work package、需要独立 review/verifier、revision binding、持续恢复或更强证据的 assignment 选择 Full。`impl-package` 仍负责需求、D/S/P binding 和执行资格；它是输入与 gate 来源，不是 Crew 的第二 scheduler。S Composition 仍是组合路径，不等于“必然创建多个 Worker”。

Full 不要求并行。Orchestrator 观察 Crew capabilities 和 observed panorama，自主决定是否定义 assignment、启动哪个 Worker cohort、何时串行或并行，以及使用什么 workspace/branch；controller 不从 ready 集合自动 dispatch，也不因 Worker `succeeded` 自动启动 Verifier。`fresh context`、Worker dispatch、活跃 write worktree 和 assurance 是必须分别记录的运行时事实；一个 DAG 允许并行不构成并行事实，同时活跃写入者仍必须有完整互斥 ownership 和独立 write lease。

Full 的 assignment 数量、Issue 到 Worker 的精确映射、Subagent 数量和 turn 顺序都不是硬验收门；Package、implementation、review loop 和内部 T-step 在 ownership、权限、交付责任与独立 acceptance boundary 不变时属于同一个 Worker。Broker 不得自行固定 run/assignment/assurance 或把候选计划升级为 canonical dispatch；Orchestrator/Worker 可以在不改变授权、ownership、依赖和验收边界的前提下选择更简单的拆分。

## 运行方式

Orchestrator 先用 `dispatch` 定义或修订完整责任边界；该动作只写 canonical assignment，不创建 worktree、不启动 Worker。它随后按自己的判断用 `control start_workers` 启动明确列出的 cohort；controller 在任何物理创建前统一校验依赖、Owner gate、profile、workspace、完整 write ownership、资源冲突和并发上限，任一预检失败时整个 cohort 保持零 worktree、零 Worker。

Worker 提交绑定 assignment、commit/diff、artifact、验证命令和风险的结构化结果后只进入 submitted。需要同一契约内纠偏时，Orchestrator 用 `control continue_worker`；责任或授权边界实质变化时修订或新建 assignment；范围、权限、不可逆副作用或验收歧义则用 `ask_owner`。Assignment-scoped Owner request 只阻断自身及严格依赖者，Orchestrator 仍可继续无依赖工作。

当 Full 证据已适合复核时，Orchestrator 显式调用 `control run_verifier`，controller 使用 canonical profile 启动 fresh、只读、非递归 Verifier。Worker 管理的 Subagent 不能充当 Verifier；Verifier 只复核固定 assignment revision、base/head commit、Worker result digest、acceptance criteria 和 evidence，不继续派生 verifier-of-verifier。最新匹配 attempt 通过后，Orchestrator 才能显式 `control accept`；acceptance 不自动关闭 run。

Orchestrator 在没有活跃 Worker/Verifier 且 terminal claim 与 canonical 事实一致时显式 `finish`，向 Broker 汇总结果、verifier disposition、未决 Owner decision、commit 范围和 terminal disposition；merge、release、cleanup 和 Owner 最终 promotion 仍由既有流程决定。任一 turn 可附带重大调整 notification；notification 只用于展示和审计，不构成 Owner approval。

一个 run 可以顺序或并行交付多个 branch/worktree；Crew intent 中的单写者或多写者只是 Orchestrator 意图，observed panorama 才显示实际 Worker、workspace、Verifier、Owner request 和 write lease。Workspace 的 path、branch、base ref 和 `new`/`reuse` 由 Orchestrator 明确给出；新建项必须落在 run-owned 根和受控 branch namespace，复用只有绑定同 run accepted handoff 且 commit 一致、clean、祖先连续和独立验证证据存在时才通过。Orchestrator 的 read-only 只禁止直接写业务交付物，不禁止它写 assignment、lease、Worker result、verifier、acceptance、intent 或 notification 等控制面状态。上游 Owner gate、失败或未验收时，严格依赖的下游不预建、不启动。

没有代码 diff 的外部 mutation 必须进入 Owner gate 并 fail closed；不得用空 commit、自然语言或伪造 artifact 通过 Full acceptance。代码 handoff 与外部 operator/promotion gate 分别记录，未授权的外部操作只阻断显式依赖它的下游；当前 Orchestrator 无网络，真实外部 API 的 read-only preflight 只能作为人工/operator evidence。正常 turn 不因时长自动 interrupt，Broker 每三分钟仅观察；只有明确 cancel 才原子写 sidecar，由 active runner interrupt 当前 turn，停止未证实时 quarantine。Worker/Verifier 启动前必须以 canonical `model/list` 选择实际 profile，catalog 不可用时 fail closed。没有同一 run 的有效 `finish` 时只能报告观察到的事实。Full Eval 是 Skill 行为回归：`hard_invariants` 验证结构化控制面事实，`forbidden_actions` 捕获越权或危险动作，`advisory_quality` 只评价拆分和交付质量，资产版本按 `0.1` 步进。

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
python scripts/codex_harness_orchestrator.py cancel --state $state --reason "Owner requested cancellation"
```

命令、状态和结构化 envelope 以 [control schema v0.5](../assets/codex-crew.control.v0.5.schema.json)、[Orchestrator turn schema v0.3](../assets/codex-crew.orchestrator-turn.v0.3.schema.json)、[Verifier result v0.1](../assets/codex-crew.verifier-result.v0.1.schema.json)、[cancel request v0.1](../assets/codex-crew.cancel-request.v0.1.schema.json) 与 canonical runtime policy 为准；控制面不规定 Worker 的内部 prompt、Subagent 数量或调用顺序。

## Legacy 说明

Full assignment 只从 Orchestrator controller 进入；不保留旧 parent/dispatch/topology 协议兼容入口。Package stage runner 保持独立适配职责，但不构成 Crew 的第二个 scheduler；主会话不得直接调用 Worker adapter，controller 也不得从 ready 状态自动补造 Worker。
