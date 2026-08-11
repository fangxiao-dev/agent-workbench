---
name: subagent-driven-development
description: 在主 session 与 subagent 之间安排调研、实现、机械执行、验证或独立 review 时使用；尤其适用于 handoff、长任务、多阶段工作、可并行执行，或边界已定的工作需要独立执行并压缩回报。默认采用 default-long，任务较聚焦时可由 agent 判断采用 ordinary。
---

# Subagent-Driven Development

本 skill 只拥有通用的主 session / subagent 调度方式与行为路由，不拥有业务流程、模型配置、Task/Ticket、package、gate 或验收标准。

## 选择调度方式

始终默认 `default-long`。agent 判断任务较聚焦时可以选择 `ordinary`，记录一句具体理由即可；本 skill 不定义“聚焦”的机械判据。host 不支持 subagent 时，说明能力限制并由主 session 继续，不伪装成已委派。

| 模式 | 主 session | Subagent |
| --- | --- | --- |
| `default-long` | 拥有调度、授权与决策、跨工作协调、资源顺序、最终集成、证据采信和结果判断 | 承担边界明确、互不重叠且可独立复核的执行工作，并生成支持下一步判断的压缩证据 |
| `ordinary` | 可直接完成聚焦或紧耦合工作，同时保留最终责任 | 按实际收益承担 bounded work |

两种模式都不扩大授权，不改变主 session 的最终责任，也不允许多个 worker 抢占同一 primary ownership 或未串行化的共享资源。

## 行为路由

- investigate / implement：读取并遵循 `/impl-package:investigate-before-implement`；它定义先调查再实现的行为方式，本 skill 决定如何在主 session 与 subagent 之间安排工作。
- independent review：派发一个独立只读 subagent；如果 active skill catalog 中存在 `reviewer`，优先使用它的 reviewer 路由，否则由 caller 提供 review scope、comparison point、证据要求和返回合同。可选 skill 缺失不构成 blocker，也不得伪装成已调用。

## 执行与裁决分层

按决策密度调度工作：主 session 集中拥有目标解释、授权、跨工作取舍、资源顺序、证据采信与最终裁决；subagent 集中执行边界已定、过程信息量大而新增判断少的 bounded work。该分层适用于调查、实现、命令运行、验证、生成、只读诊断和 review，不以任务类型或工具名称为边界。

- 当目标、输入、workdir、授权边界、资源合同和返回标准均已确定时，优先把连续执行过程交给一个 subagent。主 session 用返回证据推进下一项判断。
- 当工作触及共享数据库、环境、browser/provider、生成物或其他单写资源时，主 session 先确定资源键、唯一顺序和 cleanup owner，再把该资源的一段连续执行交给同一个 subagent。
- subagent 返回 decision-grade evidence：完成的动作或命令、结果或 exit code、关键计数、首个失败、cleanup/residue 和 artifact pointer。原始过程输出保留在 subagent 上下文，主 session 在需要诊断时索取最小相关片段。
- 常规过程在 subagent 上下文内收敛；授权变化、合同判断、资源重排、scope 扩张或跨 ownership 冲突构成回到主 session 的决策点。
- 主 session 基于压缩证据完成跨产出整合、失效判断与最终 claim audit；需要正式 Task 合同时，转到 `/impl-package:dispatch-bounded-task`。

## 派发与回收

1. 从当前目标中选择可独立启动且 ownership 不重叠的 bounded work；依赖未满足或授权不清时先留在主 session。
2. caller 为每个 subagent 提供目标、cwd/worktree、primary ownership、禁改范围、必要输入、授权边界、验证要求和返回格式；不要让 worker 从聊天历史猜。
3. worker 遇到未决语义、共享 seam、越权动作、重叠写入或无法可靠继续时返回 blocker，不自行扩大范围。
4. 主 session 收回结果后复核实际 diff / evidence，处理跨工作 seam 与冲突，再完成验证证据整合、最终集成和结果判断。
