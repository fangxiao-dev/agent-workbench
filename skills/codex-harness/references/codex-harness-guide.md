# Codex Harness/Crew 当前运行指南

本指南适用于显式调用 `$codex-harness`、`$codex-crew` 或 `$codex-crew-lite` 的任务。当前 Orchestrator/Worker 闭环仍是 POC/early-runner；下述流程描述推荐的薄控制面边界，不代表生产级隔离、跨版本恢复、cleanup 或外部 mutation 已闭合。

## 用户视角的职责链

```text
Owner <-> Broker <-> Orchestrator <-> Worker <-> Subagent
              ^             |
              +--全局状态---+
```

- Broker 是用户侧入口，传递 issue、普通纠偏和 Owner decision，并呈现 canonical Crew 全景与 Orchestrator notification；它不做业务拆分、不直接 steer Worker，也不管理 Subagent。Broker 推演只能作为非权威建议交回同一 Orchestrator，不能自行固定 run、assignment、assurance、依赖、Crew intent 或 workspace。
- Orchestrator 是一次 run 的唯一业务 controller，负责拆分 assignment、选择每个 assignment 的 Lite/Full、profile、Worker cohort、执行次序和 workspace/branch，显式调用 Worker、Verifier、acceptance 与 finish 能力，并决定继续、暂停或请求 Owner。
- Worker 是 assignment 的唯一交付责任人，在 Controller授予的只读仓库或独立写 workspace 中完成分析、设计、实现、自验和证据整理，可自主调用 Subagent。
- Subagent 只属于 Worker；其内部调用不成为顶层通信入口或独立验收主体。必要时 Worker 汇总活动是否发生、是否有外部 mutation 和 evidence provenance。

Broker 只有在线程失联、controller 冲突、取消失效或资源泄漏等控制面事故中，才可执行有记录的 break-glass 线程管理；这不等于取得业务验收或重新分配权限。

Orchestrator 的 read-only 只针对业务交付物：它不能直接改代码、配置或文档，但可以写 run snapshot、assignment、依赖、Worker lease、workspace 记录、dispatch/continuation 结果和 acceptance。控制面状态写入不等于业务交付物写入。

## Orchestrator 能力地图

Controller 提供可组合能力，不规定固定调用顺序。Orchestrator 可以按事实跳过、重复或交错其中任意项：读取 Crew panorama；用 `dispatch` 定义或修订 assignment；用 `control start_workers` 启动明确列出的 Worker cohort；用 `continue_worker` 在同一责任边界内纠偏；用 `run_verifier` 显式复核 Full 结果；用 `accept` 接受 assignment；用 `ask_owner` 创建局部或 run-scoped request；用 `finish` 提交 run terminal。任一 turn 可以更新 Crew intent 或通知 Broker 重大调整，但通知不等于 Owner approval。

`dispatch` 只改变 canonical assignment，不创建 worktree、不启动 Worker。`start_workers` 只处理 Orchestrator 明确列出的 cohort；controller 在执行前统一检查 assignment eligibility、依赖、Owner gate、profile、访问方式、完整 write ownership、资源冲突和资源上限，任一失败都保持整个 cohort 零 worktree、零 Worker。`repository_read_only` Worker 绑定运行前 repository HEAD 与 porcelain，使用只读 sandbox、零 branch、零 worktree、零 write lease，并在返回后复核相同边界；`workspace_write` Worker 才 materialize Orchestrator指定的 workspace。Worker `succeeded` 只进入 submitted；Full Verifier 只在 Orchestrator 显式调用时启动；assignment acceptance 不自动 finish。

## Crew 全景

| 投影 | 表达什么 | 不表达什么 |
| --- | --- | --- |
| `crew.capabilities` | 当前可调用的 Worker/Verifier、assurance/profile、workspace 策略、cohort 能力及其可用性证据 | 不替 Orchestrator 选择 assignment 或 Worker |
| `crew.intent` | Orchestrator 当前期望的只读、单写者或多写者形态及自然语言理由 | 不创建 workspace，不启动 Worker，不证明实际并发 |
| `crew.observed` | 从 assignment、Worker、Verifier、Owner request 和 lease 派生的当前事实 | 不自动触发下一项动作 |
| `broker_notifications` | 重大调整的 identity、时间、摘要和关联 assignment | 不是 Owner request，也不构成 approval |
| `terminal` | 显式 `finish` 后的 disposition、摘要和事实引用 | 不由 assignment acceptance 自动生成 |

一个 DAG 允许并行不等于已选择并行；一个 fresh Worker context 也不等于 fresh worktree。Run、branch 和 worktree 不建立一一映射：同一 run 可以顺序产生多个独立 branch/worktree，也可以在 ownership 互斥和资源边界内同时持有多个写 lease。Workspace 的 path、branch、base ref 和 `new`/`reuse` 由 Orchestrator 显式给出；新 workspace 必须位于 run-owned 根并使用受控 branch namespace，复用必须绑定同 run accepted `handoff_from` 且通过提交一致、clean、祖先连续和验证证据检查。未 ready 的 assignment 不得 materialize；controller 不因 Issue 数量、ready 集合或 Crew intent 自动预建 workspace。

新 Worker branch 使用 assignment-scoped namespace `codex/crew/<run-id>/<assignment-id>/...`。Linked worktree 的提交除了业务工作区外还需要 Git metadata 写权限；controller 只把 linked worktree 专属 Git dir、object database 和该 assignment 的 ref/log 目录加入 writable roots，不放开整个 common `.git`。直接使用底层 CLI 的轻量调用方如果要求 Agent 自行 commit，也必须自行提供等价的最小 Git metadata roots；仅提供 worktree path 不足以完成 linked-worktree commit。

Worker 数量、Issue 到 assignment 的精确拆分、是否在某一 turn 调用 Subagent 以及具体 turn 顺序都不是硬验收门；只要角色边界、写 ownership、依赖、授权和事实验收满足，Orchestrator/Worker 可以自主选择更简单的交付方式。

## Assignment 与模式

Lite/Full 是 assignment 级 assurance，不是整次 run 永久绑定的 top-level mode。Lite 适用于目标明确、不需要 redesign、接口/迁移/权限/不可逆副作用或验收口径变化的 assignment；Full 适用于需要 Impl-Package binding、独立 review/verifier、持续恢复或更强证据的 assignment。Worker 发现 Lite 边界不够时，应通过 Orchestrator 请求 promotion；不能自行放宽权限或把任务悄悄改成另一个目标。

每个 assignment 至少要能机械检查 run/assignment 标识、目标和非目标、自然语言 acceptance criteria、Worker access mode、依赖、验收命令、固定 revision 与结果状态；写 assignment 还需允许路径、workspace strategy、commit/diff 和 write lease，读 assignment 则必须保持空写 ownership 和一致的 pre/post Git 边界。Assignment 表示完整责任边界，不把 package、implementation、review loop 或内部步骤机械拆成顶层节点；拆分粒度、prompt、是否调用 Subagent 和实现方案由 Orchestrator/Worker 自主决定，控制面只验证硬边界。

## 四个控制动作

| 动作 | 谁发起 | 作用 |
| --- | --- | --- |
| `dispatch` | Orchestrator | 定义或修订一个有界 assignment；不 materialize、不启动 Worker |
| `control` | Orchestrator | 显式启动 selected cohort、继续 Worker、运行 Verifier、接受或取消 assignment |
| `ask_owner` | Orchestrator | 创建 assignment-scoped 或 run-scoped request，将超出当前授权的决定交给 Broker/Owner |
| `finish` | Orchestrator | 显式提交结构化 run 摘要、证据、风险和 terminal disposition |

Worker 的 Subagent 调用不暴露为顶层动作；dispatcher 只是 Worker/workspace primitive，不是 child scheduler。

## 验收和异常

Lite assignment 可以由 Orchestrator 基于允许路径、commit/diff 和确定性检查验收；Full assignment 在 Worker 自验之外，必须由 Orchestrator 显式请求 controller 通过 canonical profile 启动一个 fresh、独立、只读、非递归 Verifier。Verifier attempt 绑定 assignment revision、base/head commit 和 Worker result digest；只有 controller-owned、绑定仍一致的最新 passed attempt 才支持 Orchestrator accept。Worker 的自然语言完成说明、Subagent 输出、Orchestrator 自报 verdict 和 worktree 存在本身都不能替代事实证据。

`needs_orchestrator` 表示当前契约内的纠偏、证据澄清或资源协调；`needs_owner` 表示四类 Owner 边界之一。Assignment-scoped Owner request 只阻断自身及现有依赖图中的严格下游；只有 run-scoped request 才阻断整个 run。顶层 `awaiting_owner` 只在存在开放 request 且没有其他可执行工作时派生。上游未 ready、Owner decision 未返回、取消未确认或控制权不一致时，严格依赖的下游不得启动；无法证明停止时进入 blocked/quarantine，不能复用同一资源。

没有代码 diff 的外部 mutation 不能用空 commit、自然语言或伪造 artifact 标记完成；必须记录 Owner gate 并保持 fail closed（通常为 `awaiting_owner`），直到既有流程提供授权和可验证的外部证据。当前 Orchestrator 没有网络能力，真实 Lark、Lexware 等外部 API 的 read-only preflight 只能是人工/operator evidence；在受控 read-only external assignment 出现前，不能把它叙述为自动化 Orchestrator 工作。

## 预演证据与双依赖图

controller snapshot 可证明已持久化的控制面状态与已观察到的 assignment/lease/workspace 数量；App Server terminal evidence 才能证明 turn 的有效终态；pre/post git evidence 才能证明工作区写入边界；Broker 或审计员根据输入重建的计划只是候选建议，不能成为 canonical dispatch。正常 turn 没有基于时长的终止：Broker 每三分钟只做一次只读观察，普通 `wait_agent` 的轮询结束不改变 run 状态，也不应发送“尽快收口”消息或 interrupt。只有用户明确 `cancel` 才原子写入 sidecar 请求；持有 session 的 runner 停止新 dispatch、interrupt 当前受控 turn 并收集 terminal evidence。确认停止才写 `cancelled`；CLI 等待结束只能报告 pending，停止未知则 `blocked/quarantine` 且资源不得复用。

代码 delivery 图表达 commit、验证和 assignment handoff 的真实依赖；外部 operator/promotion 图表达 schema write、provider write、Bot 操作、merge/release 等 Owner-gated 行为。外部 gate 仅阻断显式依赖它的节点，不能因为同属一个 Issue 而隐式锁死无依赖的纯代码工作。两张图的证据与 disposition 分别汇总，避免把已验收的代码 handoff 误报为外部操作已完成。

## Eval 与 Skill 反馈

Eval 是本 Skill 的行为回归：它检查 Agent 是否遵守角色、授权、写入隔离、依赖阻断和事实验收，而不是检查是否采用固定的 Worker 数量或 turn 顺序。每个案例应区分 `hard_invariants`（结构化证据必须满足的不变量）、`forbidden_actions`（发生即失败的越权或危险动作）和 `advisory_quality`（拆分理由、沟通和交付表达的质量建议）。Eval 资产版本按 `0.1` 步进；JSON/Schema 是事实源，指南只解释边界。

## Canonical 与 legacy

推荐的结构化事实源是 [runtime policy v1.3](../assets/codex-harness-runtime-policy.v1.3.json)、[execution profiles v0.2](../assets/codex-harness-execution-profiles.v0.2.json)、[control/assignment schema v0.5](../assets/codex-crew.control.v0.5.schema.json)、[Orchestrator turn schema v0.3](../assets/codex-crew.orchestrator-turn.v0.3.schema.json)、[Verifier result v0.1](../assets/codex-crew.verifier-result.v0.1.schema.json)、[cancel request v0.1](../assets/codex-crew.cancel-request.v0.1.schema.json) 和 [Skill Eval v0.6](../assets/codex-harness-eval.v0.6.schema.json)；模型选择在实际执行前以 `model/list` 的有序候选结果记录到 assignment state，catalog 失败或所有候选不可用时不建 worktree、不启 Worker/Verifier。本指南只解释边界，不复制配置值。入口 Skill、Lite/Full Skill、continuation contract 和 Eval case 应保持语义一致。

旧 parent/dispatch/topology 协议和旧 parent controller 已物理删除；新需求必须经过 Orchestrator assignment 入口，不提供 compatibility run。Package runner 继续负责其独立 parent-stage adapter，不成为 Crew 的第二状态源。显式 selected cohort 并发已由同一 controller 进程托管，但跨 worktree promotion 仍未闭合；并发能力不等于自动 integration 或 merge。

## 底层调用入口

需要复用 Codex 协议而不使用 Crew 时，可以直接导入 `scripts/codex_harness_cli.py`；调用方自行决定 worktree、并发和结果处理，不会自动启用 Harness policy、assignment、lease 或验收。只有需要 Broker/Orchestrator/Worker 角色、结构化验收或可恢复业务 run 时，才进入 Orchestrator controller 和对应 canonical assets。

以下是底层 JSON-RPC 调用的最小示意；具体参数和版本能力以本地 App Server schema/canary 为准：

```python
import tempfile
from pathlib import Path

from scripts.codex_harness_cli import JsonRpcSession, app_server_command, initialize_params

worktree = Path(r"D:/tmp/task-a-worktree")
artifact_root = Path(tempfile.gettempdir()) / "codex-harness-runs" / "lightweight-caller"
with JsonRpcSession(app_server_command(), artifact_root / "app-server.stderr.log") as session:
    session.request(1, "initialize", initialize_params("lightweight-caller"), 30)
    started, _ = session.request(2, "thread/start", {"cwd": str(worktree), "sandbox": "workspace-write", "approvalPolicy": "never", "ephemeral": True}, 30)
    thread_id = started["thread"]["id"]
    session.request(3, "turn/start", {"threadId": thread_id, "input": [{"type": "text", "text": "处理这个 worktree 中的小问题"}]}, 30)
    session.collect_until_turn_complete(thread_id, None)
```
