---
name: codex-harness
description: Explicitly invoked entry point for operating or changing the Codex Harness/Crew system. Use only when the user names $codex-harness, $codex-crew, or $codex-crew-lite, or directly asks to operate this Harness; do not implicitly invoke it because a task mentions agents, worktrees, App Server, or Harness concepts. 当前为介绍与设计驱动的 POC 雏形，不代表生产就绪。
disable-model-invocation: true
user-invocable: true
---

# Codex Harness

> **Invocation gate:** This Skill is opt-in. Do not continue reading this file or its assets, references, or scripts merely because it is discoverable or a task mentions Harness/Crew. Continue only after the user explicitly invokes `$codex-harness`, `$codex-crew`, or `$codex-crew-lite`, or directly asks to operate this system; otherwise stop here.

Codex Harness 是一个薄控制面：它把用户侧对话、一次 run 的编排、一级 Worker assignment 和 Worker 内部 Subagent 分开，并只机械守住权限、单写者、写入隔离、Owner 决策、事实验收和取消收口等边界。Agent 自主决定问题拆分、Lite/Full、串行/并行、修复策略和是否使用 Subagent；控制面不把这些策略细节变成逐动作审批或 worker 数量验收门。

## 角色与通信

- Broker 面向用户，传递需求和 Owner decision，呈现全局状态；正常业务消息不绕过 Orchestrator。只有线程失联、控制权冲突或取消失效等线程管理场景，Broker 才以有记录的 break-glass 管理员身份介入。
- Orchestrator 是一次 run 的唯一业务编排者：分析需求，创建有界 assignment，选择 assurance/profile/topology，分配和验收 Worker，并在同一 run 内继续、暂停或请求 Owner 决策。Orchestrator 不直接修改业务交付物，也不管理 Worker 的 Subagent。
- Worker 是 assignment 的交付责任人：在声明的目标、非目标、允许路径和验收条件内自主分析、设计、实现和整理证据，可调用自己的 Subagent。Worker 不直接联系 Broker/Owner，不扩大权限或范围。
- Subagent 只受所属 Worker 控制；顶层不向它发送业务指令，也不把它的单独输出当作验收主体。Worker 只需向 Orchestrator 汇总必要的活动和证据 provenance。

## 四个独立运行时事实

以下是控制面必须分别记录和审计的运行时事实，不是可选偏好，也不能互相推导：`fresh context` 表示是否创建新的 parent/Worker 对话上下文；`worker dispatch` 表示是否启动一级 Worker；`write worktree` 表示同时有多少个写入者；`assurance` 表示 assignment 采用 Lite 还是 Full。fresh context 不等于 fresh worktree，不等于需要 dispatch，也不由 Issue 数量或 DAG 理论并行性推导。

Orchestrator 默认选择最小拓扑：只读使用 `orchestrator_read_only`；严格有序或并行收益未证实时使用 `worker_serial`；只有写 ownership 互斥且确有并行收益时才使用 `worker_parallel`。串行 Worker 可在满足提交、clean、祖先关系和独立验证的 handoff gate 后顺序复用一个 worktree；并行 Worker 才需要多个独立 worktree。具体字段、配置值和协议版本以 canonical JSON/Schema 为准。

## 四个控制动作

运行时只需表达四类意图：`dispatch`（创建或继续一个有界 assignment）、`control`（继续、接受或取消）、`ask_owner`（把越过授权边界的决定连同 provenance 交回 Broker）、`finish`（提交结构化结果和事实验收）。控制面不新增 child scheduler；Worker 的 Subagent 由 Worker 自主管理。

## 必读运行指南

处理 Codex Harness 的设计、实现或验证任务前，完整阅读 [references/codex-harness-guide.md](references/codex-harness-guide.md)。涉及 assignment、角色边界、上下文复用、委派授权、验收或生命周期策略时，还要读取 [runtime policy v1](assets/codex-harness-runtime-policy.v1.json)、[execution profiles](assets/codex-harness-execution-profiles.v0.json) 和 [control schema](assets/codex-crew.control.v0.1.schema.json)；配置与协议值只从结构化资产读取，不在 Markdown 中维护第二份配置。旧 runtime policy v0 和 parent/dispatch schema 只作为 migration/legacy 依据，历史设计提案仅供回顾，不是当前运行契约。

## 进入路径

- 推荐入口是 Orchestrator controller：`scripts/codex_harness_orchestrator.py`。主会话只做 Broker，不直接创建 Worker 或管理 Subagent。
- 底层 Codex CLI/App Server 客户端是 `scripts/codex_harness_cli.py`；它只提供命令发现、JSON-RPC stdio session 和 thread/turn 原语，可被轻量 caller 复用，不自动加载 Harness policy 或验收。
- `scripts/codex_harness_dispatch.py` 以及 `codex-crew-parent.v2`、`codex-crew-dispatch.v2` 是 legacy/transition primitive：保留既有调用和测试的兼容性，但不再作为新的业务编排入口，也不应被主会话当作 scheduler。
- `codex-crew-lite` 和 `codex-crew` 是 assignment 级 assurance profile，不是两个并行的顶层 scheduler；它们共享 Orchestrator、Worker communication、canonical profiles 和 runtime policy。
- Impl-Package adapter 仍是需求和验收输入来源，不是第二个 scheduler 或状态事实源；Package runner 的 legacy parent-stage 职责保持独立，迁移时只复用确定性检查。

## 控制面写入边界

Orchestrator 的 read-only 只禁止它直接修改业务交付物（代码、配置、文档等 assignment 产物）；它可以并且必须写控制面状态、run snapshot、assignment、依赖、Worker lease、workspace 记录、dispatch/continuation 结果和 acceptance 记录。Broker 只写用户侧消息或 break-glass 管理记录，Worker 才能在允许的 workspace/path 内写业务交付物，Subagent 只受所属 Worker 控制。

## 当前硬边界

- 业务写入只能由有界 Worker 在允许的 workspace/path 内执行；Orchestrator、Broker 和 Subagent 不越过各自控制域。
- 同一 run 只有一个持久 Orchestrator controller identity，但允许在 `needs_orchestrator`、`needs_owner`、返工或验证反馈后进行多轮 continuation；发现控制权或 state 不一致时 fail closed，不创建第二个业务 controller。
- Worker result 必须绑定 assignment、commit/diff、验证命令和结构化 disposition；自然语言“完成”不能替代事实验收。Full assignment 还需要独立的只读 verifier，且 verifier 不递归派生 verifier。
- 上游未 ready、`needs_owner` 或取消未确认时，不得预建或启动严格依赖的下游 Worker/worktree；停止不确定时 quarantine 资源并等待人工收口。
- 不自动扩大权限、merge、release、清理或执行不可逆外部写入；没有代码 diff 的外部 mutation 必须进入 Owner gate 并 fail closed，不得用空 commit、自然语言或伪造 artifact 标记完成；这些动作仍由既有流程和 Owner 授权决定。

## 终态、证据与外部边界

`blocked` 或 `quarantine` run 只能报告 controller snapshot、terminal reconciliation、通知与 git 边界中已经观察到的事实；没有同一 run 的有效结构化 `finish`，不得把自然语言计划、候选 assignment 或 Broker 推导当作权威 dispatch 结论。等待 `turn/completed` 超时的终态是未知，除非存在独立 interrupt acknowledgement 或 terminal envelope，否则不得笼统称为 `interrupted`。

代码 delivery 依赖与外部 operator/promotion 依赖分别表达。未授权的外部 mutation 进入独立 Owner gate，只阻断明确依赖该操作的下游；它不自动使同一 Issue 内无依赖的纯代码 handoff 失效。当前 Orchestrator 网络关闭，真实 Lark、Lexware 等 API 的 read-only preflight 只能作为人工/operator evidence；在出现受控的 read-only external assignment 前，不能宣传为自动化 Orchestrator 能力。

## Skill 行为回归 Eval

`codex-harness` 的 Eval 是 Skill 行为回归，不是第二个调度器或运行时状态源。每个案例同时区分三层：`hard_invariants` 是必须从 snapshot、assignment、lease、result 或 acceptance 证据中满足的控制面不变量；`forbidden_actions` 是一旦发生即失败的越权或危险动作；`advisory_quality` 只评价拆分理由、沟通质量和交付表达，不把 Worker 数量、精确 assignment 拆分或 turn 顺序变成硬门。当前 Eval 资产版本按 `0.1` 步进；结构化断言以 canonical JSON/Schema 为准，Markdown 只解释行为边界。

## Canonical 资产

- Runtime policy、execution profiles、control/assignment envelope、run snapshot 和 legacy schema 位于 `skills/codex-harness/assets/`；当前推荐事实源是 `codex-harness-runtime-policy.v1.json`、`codex-harness-execution-profiles.v0.json` 和 `codex-crew.control.v0.1.schema.json`。
- Skill 行为回归 Eval 的事实源是 [Eval v0.2 schema](assets/codex-harness-eval.v0.2.schema.json) 以及 `codex-crew/evals/evals.json`、`codex-crew-lite/evals/evals.json`；Eval 只验证 Skill 应守住的行为边界，不成为第二个 runtime scheduler。
- `references/codex-crew-continuation-contract.md` 只解释共享的角色、通信和 continuation 边界；`references/codex-harness-guide.md` 只解释当前用户视角流程和迁移入口。
- `references/codex-crew-orchestrator-worker-design.md` 是设计存档，不是运行必读项；若它与 canonical Schema 或当前 controller 不一致，以后者为准。

这些文件仍处于 POC/early-runner 阶段，不是稳定公开 API。任何新的稳定结论先进入结构化资产和测试，再决定是否提升 runtime maturity；当前 maturity 仍以 canonical policy 声明为准。
