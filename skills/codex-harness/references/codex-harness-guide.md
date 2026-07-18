# Codex Harness/Crew 当前运行指南

本指南适用于显式调用 `$codex-harness`、`$codex-crew` 或 `$codex-crew-lite` 的任务。当前 Orchestrator/Worker 闭环仍是 POC/early-runner；下述流程描述推荐的薄控制面边界，不代表生产级隔离、跨版本恢复、cleanup 或外部 mutation 已闭合。

## 用户视角的职责链

```text
Owner <-> Broker <-> Orchestrator <-> Worker <-> Subagent
              ^             |
              +--全局状态---+
```

- Broker 是用户侧入口，传递 issue、普通纠偏和 Owner decision，并呈现全局状态；它不做业务拆分、不直接 steer Worker，也不管理 Subagent。
- Orchestrator 是一次 run 的唯一业务 controller，负责拆分 assignment、选择每个 assignment 的 Lite/Full、profile 和 topology，分配 Worker，验收结果并决定继续、暂停或请求 Owner。
- Worker 是 assignment 的唯一交付责任人，在自己的 workspace 内完成设计、实现、自验和证据整理，可自主调用 Subagent。
- Subagent 只属于 Worker；其内部调用不成为顶层通信入口或独立验收主体。必要时 Worker 汇总活动是否发生、是否有外部 mutation 和 evidence provenance。

Broker 只有在线程失联、controller 冲突、取消失效或资源泄漏等控制面事故中，才可执行有记录的 break-glass 线程管理；这不等于取得业务验收或重新分配权限。

Orchestrator 的 read-only 只针对业务交付物：它不能直接改代码、配置或文档，但可以写 run snapshot、assignment、依赖、Worker lease、workspace 记录、dispatch/continuation 结果和 acceptance。控制面状态写入不等于业务交付物写入。

## 推荐运行流程

1. 用户显式调用入口 Skill；主会话作为 Broker 将需求交给 Orchestrator，Orchestrator 在只读 turn 中确认目标、非目标、Owner 边界和当前可执行的 assignment。
2. Orchestrator 为每个 assignment 独立选择 `assurance_mode`（Lite/Full）、canonical execution profile、是否使用 fresh Worker context 和最小 execution topology；这些是分别记录的运行时事实，不要从 Issue 数量、profile 或 fresh context 推导其他字段。
3. Orchestrator 用 `dispatch` 创建或继续有界 Worker assignment。`worker_serial` 允许按 ready 顺序调用 dispatcher primitive，但同一时刻最多一个活跃写 Worker/worktree；需要普通纠偏时使用 `control` 的 continue，需要范围、权限、不可逆副作用或验收口径决定时使用 `ask_owner`，Broker 转交 Owner 原文后在同一持久 Orchestrator controller identity 下继续同一 run，可进行多轮 continuation。
4. Worker 提交绑定 assignment 和 commit/diff 的结构化结果。Orchestrator 用 `control` 的 accept/continue/cancel 做状态推进；拒绝验收或要求返工统一通过 continue 表达，并检查允许路径、工作树、验证命令、artifact 和必要的独立 verifier 证据。
5. Orchestrator 用 `finish` 汇总交付状态、未解决决定、验证事实和 terminal disposition 返回 Broker；只有同一 run 的有效结构化 `finish` 才产生权威调度结论。merge、release、cleanup 和 Owner 最终 promotion 仍由既有流程决定。

## Topology 决策表

| 条件 | 最小 topology | 一级 Worker | 活跃写 worktree | dispatcher |
| --- | --- | --- | --- | --- |
| 只读分析、审查或确定性验证 | `orchestrator_read_only` | 0 | 0 | 不调用 |
| 写入严格有序、单写者，或并行收益尚未证明 | `worker_serial` | 按 ready assignment 顺序启动 | 最多 1 | 可顺序调用 dispatcher primitive，不启动并发 cohort |
| 至少两个 ready assignment 的写 ownership 互斥，且并行有明确收益 | `worker_parallel` | 按 Orchestrator 的 ready 集合启动 | 由 canonical 上限约束 | 仅此时调用 dispatcher |

一个 DAG 允许并行不等于默认并行；一个 fresh Worker context 也不等于 fresh worktree。串行 handoff 可在前一 assignment 已提交、工作树 clean、提交祖先连续、验证证据存在且仍属同一交付程序时复用一个 worktree；未 ready 的下游不得预建 workspace。

Worker 数量、Issue 到 assignment 的精确拆分、是否在某一 turn 调用 Subagent 以及具体 turn 顺序都不是硬验收门；只要角色边界、写 ownership、依赖、授权和事实验收满足，Orchestrator/Worker 可以自主选择更简单的交付方式。

## Assignment 与模式

Lite/Full 是 assignment 级 assurance，不是整次 run 永久绑定的 top-level mode。Lite 适用于目标明确、不需要 redesign、接口/迁移/权限/不可逆副作用或验收口径变化的 assignment；Full 适用于需要 Impl-Package binding、独立 review/verifier、持续恢复或更强证据的 assignment。Worker 发现 Lite 边界不够时，应通过 Orchestrator 请求 promotion；不能自行放宽权限或把任务悄悄改成另一个目标。

每个写 assignment 至少要能机械检查 run/assignment 标识、目标和非目标、允许路径、Worker thread/workspace、依赖、验收命令、commit/diff 和结果状态。拆分粒度、prompt、是否调用 Subagent 和实现方案由 Orchestrator/Worker 自主决定，控制面只验证硬边界。

## 四个控制动作

| 动作 | 谁发起 | 作用 |
| --- | --- | --- |
| `dispatch` | Orchestrator | 建立或继续一个有界 assignment，并按 ready 条件绑定 Worker/context/workspace |
| `control` | Orchestrator | 对同一 assignment 继续（包括返工）、接受或取消 |
| `ask_owner` | Orchestrator | 将超出当前授权的范围、权限、不可逆外部副作用或验收歧义交给 Broker/Owner |
| `finish` | Orchestrator | 提交结构化 run 摘要、证据、风险和 terminal disposition |

Worker 的 Subagent 调用不暴露为顶层动作；dispatcher 只是 Worker/workspace primitive，不是 child scheduler。

## 验收和异常

Lite assignment 可以由 Orchestrator 基于允许路径、commit/diff 和确定性检查验收；Full assignment 在 Worker 自验之外，需要一个独立、只读、非递归 verifier 或等价的独立检查。Worker 的自然语言完成说明、Subagent 输出和 worktree 存在本身都不能替代事实证据。

`needs_orchestrator` 表示当前契约内的纠偏、证据澄清或资源协调；`needs_owner` 表示四类 Owner 边界之一。上游未 ready、Owner decision 未返回、取消未确认或控制权不一致时，严格依赖的下游不得启动；无法证明停止时进入 attention/quarantine，不能复用同一资源。

没有代码 diff 的外部 mutation 不能用空 commit、自然语言或伪造 artifact 标记完成；必须记录 Owner gate 并保持 fail closed（通常为 `awaiting_owner`），直到既有流程提供授权和可验证的外部证据。当前 Orchestrator 没有网络能力，真实 Lark、Lexware 等外部 API 的 read-only preflight 只能是人工/operator evidence；在受控 read-only external assignment 出现前，不能把它叙述为自动化 Orchestrator 工作。

## 预演证据与双依赖图

controller snapshot 可证明已持久化的控制面状态与已观察到的 assignment/lease/workspace 数量；App Server terminal/history evidence 才能证明 turn 的有效终态；pre/post git evidence 才能证明工作区写入边界；Broker 或审计员根据输入重建的计划只是候选建议。`turn/completed` 超时后，controller 应先收集 history/terminal evidence；若仍无法取得有效 terminal envelope，则该 run 是 `blocked/quarantine` 的终态未知，只能报告已观察到的事实，不能称为已 `interrupted`、已完成或可 dispatch。

代码 delivery 图表达 commit、验证和 assignment handoff 的真实依赖；外部 operator/promotion 图表达 schema write、provider write、Bot 操作、merge/release 等 Owner-gated 行为。外部 gate 仅阻断显式依赖它的节点，不能因为同属一个 Issue 而隐式锁死无依赖的纯代码工作。两张图的证据与 disposition 分别汇总，避免把已验收的代码 handoff 误报为外部操作已完成。

## Eval 与 Skill 反馈

Eval 是本 Skill 的行为回归：它检查 Agent 是否遵守角色、授权、写入隔离、依赖阻断和事实验收，而不是检查是否采用固定的 Worker 数量或 turn 顺序。每个案例应区分 `hard_invariants`（结构化证据必须满足的不变量）、`forbidden_actions`（发生即失败的越权或危险动作）和 `advisory_quality`（拆分理由、沟通和交付表达的质量建议）。Eval 资产版本按 `0.1` 步进；JSON/Schema 是事实源，指南只解释边界。

## Canonical 与 legacy

推荐的结构化事实源是 [runtime policy v1](../assets/codex-harness-runtime-policy.v1.json)、[execution profiles](../assets/codex-harness-execution-profiles.v0.json)、[Orchestrator control/assignment schema](../assets/codex-crew.control.v0.1.schema.json) 和 [Skill Eval v0.2 schema](../assets/codex-harness-eval.v0.2.schema.json)；本指南只解释边界，不复制配置值。入口 Skill、Lite/Full Skill、continuation contract 和 Eval case 应保持语义一致。

`codex-crew-parent.v2.schema.json`、`codex-crew-dispatch.v2.schema.json`、旧 parent controller 和旧 topology primitive 保留为 legacy/transition 兼容路径；新需求推荐经过 Orchestrator assignment 入口，不再把 legacy parent/dispatch 当成用户侧 scheduler。Package runner 继续负责其独立 parent-stage adapter，不成为 Crew 的第二状态源。

## 底层调用入口

需要复用 Codex 协议而不使用 Crew 时，可以直接导入 `scripts/codex_harness_cli.py`；调用方自行决定 worktree、并发和结果处理，不会自动启用 Harness policy、assignment、lease 或验收。只有需要 Broker/Orchestrator/Worker 角色、结构化验收或可恢复业务 run 时，才进入 Orchestrator controller 和对应 canonical assets。

以下是底层 JSON-RPC 调用的最小示意；具体参数和版本能力以本地 App Server schema/canary 为准：

```python
from pathlib import Path

from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params

worktree = Path(r"D:/tmp/task-a-worktree")
with JsonRpcSession(app_server_command(), worktree / ".codex-app-server.stderr.log") as session:
    session.request(1, "initialize", initialize_params("lightweight-caller"), 30)
    started, _ = session.request(2, "thread/start", {"cwd": str(worktree), "sandbox": "workspace-write", "approvalPolicy": "never", "ephemeral": True}, 30)
    thread_id = started["thread"]["id"]
    session.request(3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": "处理这个 worktree 中的小问题"}]}, 30)
    session.collect_until_turn_complete(thread_id, 120)
```
