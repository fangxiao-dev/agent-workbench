---
name: subagent-driven-development
description: 在主 session 与 subagent 之间安排调研、实现或独立 review 时使用；尤其适用于 handoff、长任务、多阶段工作和可并行执行。默认采用 default-long，任务较聚焦时可由 agent 判断采用 ordinary。
---

# Subagent-Driven Development

本 skill 只拥有通用的主 session / subagent 调度方式与行为路由，不拥有业务流程、模型配置、Task/Ticket、package、gate 或验收标准。

## 选择调度方式

始终默认 `default-long`。agent 判断任务较聚焦时可以选择 `ordinary`，记录一句具体理由即可；本 skill 不定义“聚焦”的机械判据。host 不支持 subagent 时，说明能力限制并由主 session 继续，不伪装成已委派。

| 模式 | 主 session | Subagent |
| --- | --- | --- |
| `default-long` | 保留调度、授权与决策、跨工作协调、共享验证、最终集成和结果判断 | 承担边界明确、互不重叠且可独立复核的执行工作 |
| `ordinary` | 可直接完成聚焦或紧耦合工作，同时保留最终责任 | 按实际收益承担 bounded work |

两种模式都不扩大授权，不改变主 session 的最终责任，也不允许多个 worker 抢占同一 primary ownership 或未串行化的共享资源。

## 行为路由

- investigate / implement：读取并遵循 `$investigate-before-implement`；它定义先调查再实现的行为方式，本 skill 决定如何在主 session 与 subagent 之间安排工作。
- independent review：读取并遵循 `$reviewer`；reviewer 自己决定适用的 reviewer 路由，本 skill 不复制其规则。

## 派发与回收

1. 从当前目标中选择可独立启动且 ownership 不重叠的 bounded work；依赖未满足或授权不清时先留在主 session。
2. caller 为每个 subagent 提供目标、cwd/worktree、primary ownership、禁改范围、必要输入、授权边界、验证要求和返回格式；不要让 worker 从聊天历史猜。
3. worker 遇到未决语义、共享 seam、越权动作、重叠写入或无法可靠继续时返回 blocker，不自行扩大范围。
4. 主 session 收回结果后复核实际 diff / evidence，处理跨工作 seam 与冲突，再完成共享验证、最终集成和结果判断。
