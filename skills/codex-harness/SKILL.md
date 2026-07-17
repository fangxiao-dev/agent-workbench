---
name: codex-harness
description: Use when explaining, designing, prototyping, validating, or operating a Codex Harness built on Codex App Server, especially a parent-agent harness where the outer harness assigns and validates one parent execution role while that parent independently chooses whether and how to use native subagents. Also use for parent thread lifecycle, structured-result validation, retries, timeouts, boundary enforcement, Impl-Package integration, and Codex CLI harness feasibility work. 当前为介绍与设计驱动的 POC 雏形，不代表生产就绪。
---

# Codex Harness

把 Codex Harness 视为围绕一个父 Codex agent 的确定性控制层：Harness 为父 agent 绑定执行角色，控制其 thread/turn、输入、外部验证与生命周期；父 agent 自主选择完成任务的方式，包括是否以及如何使用原生 subagents，并向 Harness 返回可校验的最终结果。

本 Skill 当前提供共同语言、已验证边界、设计入口、Sources Index，以及 early-runner 的 package adapter/parent-stage 运行入口。它不是完整运行器，也不宣称已经解决生产级 verifier catalog、跨版本兼容、长期 cleanup 或生产级隔离。

## 必读设计资产

处理 Codex Harness 的设计、实现或验证任务前，完整阅读 [assets/codex-harness-poc-design.md](assets/codex-harness-poc-design.md)。它是当前设计事实源，包含目标、实测证据、已接受决策、App Server Sources Index、风险和路线图。

当该资产与此文件重复处不一致时，以资产中的最新明确决策为准，并同步收敛本文件中的入口性表述，避免长期维护两份设计正文。

## 当前控制边界

- Harness 只为父 agent 绑定角色并直接控制它的 thread/turn、work package 和外部执行环境。
- 父角色由 thread-level developer instructions、模型/推理强度、适用的 Skill/AGENTS.md 和任务契约共同定义。
- 父 agent 自行决定是否以及如何 spawn、steer、wait 和 close 原生 subagents；Harness 不为 child 绑定角色，也不规定 child 数量、模型、prompt 或拓扑。
- 子 thread id、`subAgentActivity`、`agentPath` 和状态只属于可选 telemetry，不是当前硬验收门。
- 当前 Codex `0.144.4` 的 `thread/start`/`thread/read` thread projection 只返回 `modelProvider`，但 `config/read(includeLayers=true)` 可返回 effective model/effort；涉及 resume/fork 时必须结合 effective-config projection、canary 和 history continuity 验证，若该 seam 缺失或漂移仍要 fail closed，不能把请求参数当成实际配置。
- Harness 只接受父 agent 的结构化最终结果，并用独立的外部检查验证其中的 artifact、测试和断言。
- 当前只优先固定父 agent 的 `model` 与 `model_reasoning_effort`；MCP 白名单、token/time budget 留到后续风险驱动阶段。
- 只有父 agent 触及明确边界时 Harness 才介入，包括权限/沙箱、允许路径与 mutation authority、外部副作用、deadline/cancel、并发/成本上限以及结果契约。

## 使用流程

1. 读取设计资产，先区分“官方接口事实”“本地实测事实”“GitHub issue 风险信号”和“尚未验证的设计假设”。
2. 明确本次工作属于介绍、设计、POC 实现还是验证；不要把前一阶段的完成表述成生产 Harness 已完成。
3. 若进入实现，优先通过 App Server v2 的 thread/turn API 控制父 agent，并保持父 agent 对 subagents 的所有权。
4. 若进入验收，解析父 agent 的结构化结果，再独立检查文件、命令、测试或其他 gate；不要只相信自然语言结论。
5. 若要将新的 Impl-Package 接入 Harness，先固定 approved commit，再运行 adapter preparation；把输出当作草案，逐项完成 verifier 与 ownership review 后才可执行。
6. 若涉及 retry、timeout、resume、fork 或 cleanup，按父 stage/turn 粒度设计，记录 Codex 版本和恢复策略，并重新核验 Sources Index 中的生命周期风险。
7. 将新的稳定结论、反例和版本差异先写回设计资产，再据此改进 Skill 的执行规则或添加脚本、references 和 evals。

## 护栏

- 新集成使用 App Server v2；不要以 `codex exec --json` 作为可靠的 child provenance 或 durable session 控制面。
- 不在 Harness 中复制一个 child scheduler，除非后续证据证明父 agent 自编排不能满足已定义的验收语义。
- 不把 child 角色绑定、数量或调用顺序加入验收；父 agent 是否使用 subagents 是其内部实现选择。
- 不把未实现的 retry、timeout、resume、cleanup 或 version probe 描述成现有能力。
- 不把 GitHub issue 当成接口契约；它们只用于识别需要防御、回归测试或版本复核的风险。
- 对写密集并发保持保守；在没有 worktree/ownership 隔离前，POC 优先只读探索、审查和验证。

## 当前仓库入口

- App Server POC 客户端：`scripts/run-codex-app-server-pilot.py`
- Impl-Package adapter preparation：`scripts/prepare-codex-harness-package.py`；从固定 approved package snapshot 生成待 review 的 manifest 和 readiness report，不会自动授予 verifier 或推断路径写权限。
- Impl-Package parent-stage runner：`scripts/run-codex-harness-package.py`；用已审核 manifest 校验固定 D/S/P binding、投影 ready stage，并在显式 execute 时控制一个父 App Server session。
- 早期 `codex exec` 对照脚本：`scripts/run-codex-subagent-pilot.ps1`
- 父角色 profile：`.codex/harness/parent.toml`；由 Harness 读取并映射到父 thread，Codex 不会把它当作 native child catalog。
- 项目级运行边界：`.codex/config.toml`

这些文件仍处于 POC/early-runner 阶段，不是稳定公开 API。package adapter 的生成、manifest、敏感原件按需授权、worktree 边界与 verifier 要求见 `docs/workbench-design/codex-harness-package-runner.md`；设计变化先进入资产文档，确认后再决定是否把可复用能力迁入稳定 API。
