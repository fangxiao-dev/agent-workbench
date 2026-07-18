---
name: codex-harness
description: Use when explaining, designing, prototyping, validating, or operating a Codex Harness built on Codex App Server, especially a parent-agent harness where the outer harness assigns and validates one parent execution role while that parent independently chooses whether and how to use native subagents. Also use for parent thread lifecycle, structured-result validation, retries, timeouts, boundary enforcement, Impl-Package integration, and Codex CLI harness feasibility work. 当前为介绍与设计驱动的 POC 雏形，不代表生产就绪。
---

# Codex Harness

把 Codex Harness 视为围绕一个父 Codex agent 的确定性控制层：Harness 为父 agent 绑定执行角色，控制其 thread/turn、输入、外部验证与生命周期；父 agent 自主选择完成任务的方式，包括是否以及如何使用原生 subagents，并向 Harness 返回可校验的最终结果。

本 Skill 是 Codex Crew/Harness 体系的入口。它提供共同语言、已验证边界、设计入口、Sources Index、parent 生命周期和 early-runner 的 package adapter/parent-stage 入口；parent thread 是唯一的执行编排者，主会话只负责面向用户的交付、转发和模式确认。`codex-crew-lite` 与 `codex-crew` 是同一 parent 的两种 execution profile，复用底层 dispatcher，但不把 POC 误报为生产级 verifier catalog、跨版本兼容、长期 cleanup 或生产级隔离。

## 必读设计资产

处理 Codex Harness 的设计、实现或验证任务前，完整阅读 [assets/codex-harness-poc-design.md](assets/codex-harness-poc-design.md)。它是当前架构语义与证据事实源，包含目标、实测证据、已接受决策、App Server Sources Index、风险和路线图。涉及上下文复用、委派授权、任务分区、决策路由、验收或生命周期策略时，还要读取 [assets/codex-harness-runtime-policy.v0.json](assets/codex-harness-runtime-policy.v0.json) 及其 [JSON Schema](assets/codex-harness-runtime-policy.schema.json)；具体策略值以该 canonical policy 为准，不在 Markdown 中维护第二份配置。

当该资产与此文件重复处不一致时，以资产中的最新明确决策为准，并同步收敛本文件中的入口性表述，避免长期维护两份设计正文。

## 当前控制边界

- Harness 只为父 agent 绑定角色并直接控制它的 thread/turn、work package 和外部执行环境。
- 父角色由 thread-level developer instructions、模型/推理强度、适用的 Skill/AGENTS.md 和任务契约共同定义。
- 父 agent 在已声明的任务与授权边界内自行决定实现、委派和协作方式，包括是否以及如何 spawn、steer、wait 和 close 原生 subagents；Harness 不逐操作审批、不为 child 绑定角色，也不规定 child 数量、模型、prompt 或拓扑。
- 不同任务使用新上下文；同一 work package 内的 correction、retry 或进程恢复才可延续既有 thread，而且一个持久 thread 同时只能由一个 controller 驱动。
- 子 thread id、`subAgentActivity`、`agentPath` 和状态只属于可选 telemetry，不是当前硬验收门。
- 当前 Codex `0.144.4` 的 `thread/start`/`thread/read` thread projection 只返回 `modelProvider`，但 `config/read(includeLayers=true)` 可返回 effective model/effort；涉及 resume/fork 时必须结合 effective-config projection、canary 和 history continuity 验证，若该 seam 缺失或漂移仍要 fail closed，不能把请求参数当成实际配置。
- Harness 只接受父 agent 的结构化最终结果，并用独立的外部检查验证其中的 artifact、测试和断言。
- 当前只优先固定父 agent 的 `model` 与 `model_reasoning_effort`；MCP 白名单、token/time budget 留到后续风险驱动阶段。
- 只有父 agent 触及明确边界时 Harness 才介入，包括权限/沙箱、允许路径与 mutation authority、外部副作用、deadline/cancel、并发/成本上限以及结果契约。

## 使用流程

1. 读取设计资产，先区分“官方接口事实”“本地实测事实”“GitHub issue 风险信号”和“尚未验证的设计假设”。
2. 明确本次工作属于介绍、设计、POC 实现还是验证；不要把前一阶段的完成表述成生产 Harness 已完成。
3. 若进入实现，先加载并校验 canonical runtime policy，再通过 App Server v2 的 thread/turn API 控制父 agent，并保持父 agent 对实现方法和 subagents 的所有权。
4. 若进入验收，解析父 agent 的结构化结果，再独立检查文件、命令、测试或其他 gate；不要只相信自然语言结论。
5. 若要将新的 Impl-Package 接入 Harness，先固定 approved commit，再运行 adapter preparation；把输出当作草案，逐项完成 verifier 与 ownership review 后才可执行。
6. 若涉及 retry、timeout、resume、fork 或 cleanup，按父 stage/turn 粒度设计，记录 Codex 版本和恢复策略，并重新核验 Sources Index 中的生命周期风险。
7. 将新的稳定结论、反例和版本差异先写回设计资产，再据此改进 Skill 的执行规则或添加脚本、references 和 evals。

## 护栏

- 新集成使用 App Server v2；不要以 `codex exec --json` 作为可靠的 child provenance 或 durable session 控制面。
- 不在核心 Harness 中复制一个 child scheduler，除非后续证据证明父 agent 自编排不能满足已定义的验收语义。Crew 的外部 worktree worker dispatcher 是 parent 显式调用的底层能力，不是主会话的 scheduler，也不得把 worker 拓扑当作通过条件。
- 不把 child 角色绑定、数量或调用顺序加入验收；父 agent 是否使用 subagents 是其内部实现选择。
- 不跨独立任务复用 thread 上下文，也不允许两个 controller 并发驱动同一持久 thread。
- 不因能力被 sandbox 或 policy 阻断而自动扩大权限；可在既有授权内解决的纠偏由 parent 继续，涉及范围、权限、不可逆外部副作用或验收歧义时经主会话交给 owner。
- 不把未实现的 retry、timeout、resume、cleanup 或 version probe 描述成现有能力。
- 不把 GitHub issue 当成接口契约；它们只用于识别需要防御、回归测试或版本复核的风险。
- 对写密集并发保持保守；在没有 worktree/ownership 隔离前，POC 优先只读探索、审查和验证。

## 当前仓库入口

- Codex CLI / App Server 基础客户端：`scripts/codex_harness_cli.py`；它只提供可执行文件发现、App Server 命令构造、版本查询和 JSON-RPC stdio session，可被独立的小任务/worktree 调用，不加载 Harness policy、ledger 或 Impl-Package。
- Harness 生命周期与验收控制器：`scripts/codex_harness_controller.py`；它负责父 turn 生命周期、Parent Result/消息提取、外部 artifact 检查和 pilot verdict，不承载底层进程协议。
- App Server POC 场景薄壳：`scripts/run-codex-app-server-pilot.py`；只解析场景参数并转交 controller。
- Impl-Package adapter preparation：`scripts/prepare-codex-harness-package.py`；从固定 approved package snapshot 生成待 review 的 manifest 和 readiness report，不会自动授予 verifier 或推断路径写权限。
- Impl-Package parent-stage runner：`scripts/run-codex-harness-package.py`；用已审核 manifest 校验固定 D/S/P binding、投影 ready stage，并在显式 execute 时控制一个父 App Server session。
- 早期 `codex exec` 对照脚本：`scripts/run-codex-subagent-pilot.ps1`
- 传统 Harness 父角色 profile：`.codex/harness/parent.toml`；Crew parent profile：`.codex/harness/crew-parent.toml`；两者都由 controller 显式读取并映射到 parent thread，不是 native child catalog。
- 统一 parent controller：`scripts/codex_harness_crew.py`；主会话通过它启动/恢复同一 parent、确认 Lite/Full 模式和转发 owner/纠偏消息。
- Canonical runtime policy：`assets/codex-harness-runtime-policy.v0.json` 及其 JSON Schema；当前 `maturity` 为 `design_baseline`，其内部术语定义位于设计资产。App Server/package/resume 入口已形成部分 loader、lease/ledger seam，但尚未证明所有字段、失败路径和入口均被强制采用。
- 项目级运行边界：`.codex/config.toml`

### 底层调用入口

需要复用 Codex 协议而不使用 Crew 时，可以直接导入 `codex_harness_cli.py`；每个调用方自行决定 worktree、并发和结果处理，不会自动启用 Harness policy、lease、ledger 或 Parent Result 验收：

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

调用方如果需要结构化验收或可恢复 parent 生命周期，再进入 `codex_harness_crew.py`、`codex_harness_controller.py`、`codex_harness_runtime.py` 和 package adapter；不要把这些 Harness 语义复制回底层 caller。

这些文件仍处于 POC/early-runner 阶段，不是稳定公开 API。package adapter 的生成、manifest、敏感原件按需授权、worktree 边界与 verifier 要求见 `docs/workbench-design/codex-harness-package-runner.md`；设计变化先进入资产文档，确认后再决定是否把可复用能力迁入稳定 API。

### Crew 工作流入口

- `codex-crew-lite`：parent 确认后的轻量 execution profile，适用于明确、小范围、非 redesign 问题；parent 通过 dispatcher 创建 worktree 和 fresh worker。
- `codex-crew`：parent 确认后的完整 execution profile，适用于 Impl-Package、revision binding、独立验证、review/gate 或持续恢复要求；parent 在 dispatcher 之上组合现有 Harness/Package controls。
- 主会话通过 `scripts/codex_harness_crew.py` 先启动 routing turn，确认 parent 的模式建议后再恢复同一 thread；不要由主会话直接调用 worker dispatcher。
- 两者共享 `references/codex-crew-continuation-contract.md`、`assets/codex-crew-dispatch.schema.json` 和 `assets/codex-crew-parent.schema.json`。canonical 配置值放在结构化 manifest/state，不在两个 Skill 中复制。
