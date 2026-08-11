---
name: dispatch-bounded-task
description: 当批准的 plan、Ticket 或 DAG 已给出边界明确、依赖已释放且可委派的实现或只读验证 Task 时使用；负责派发和收回局部产出或压缩验证证据，不设计 Task 或验收 Ticket。
---

# Dispatch Bounded Task

本 skill 是有界 Task 的派发接口。Task 的目标、依赖、primary ownership、贡献 Ticket 与局部验证必须已经由批准的计划或 DAG 给出；缺失时退回 owning stage，不在执行期重新设计 Task。

## 派发

1. 只选择已知依赖满足、且不与活跃 Task 的 primary ownership 重叠的 Task。
2. 调度模式按 `/impl-package:subagent-driven-development` 执行；未另行选择时默认使用 `default-long`。
3. 派发前读取 [Task 模板](references/task-templates.md)，按 Task 是否产生实现变更选择 Implementer 或 Verifier；只填当前 Task 真正需要的字段。
4. 集成性 Task 只需额外写明冻结接口、允许修改的连接层、不得修改的核心实现及必须证明的正反向行为。
5. worker 不扩大 scope 或 primary ownership；遇到未决 contract、共享 seam、越权动作、重叠写入或无法可靠继续时返回 `BLOCKED`。

## 回收

- Implementer 的 `DONE` 表示局部产出与证据已返回；Verifier 的 `DONE` 表示既定命令已执行并返回 red/green 证据。两者都不表示 Ticket accepted。
- `BLOCKED` 必须包含最小原因、建议动作和受影响 Ticket。
- Working Branch owner 负责集成产出、处理实际 seam / 冲突，拥有共享验证的范围、资源顺序与证据采信，并由 `/impl-package:dev-with-track` 完成正式 review、Ticket acceptance 与 package 收口。

本 skill 不拥有 Task/Ticket 设计、plan revision、runtime state、Attempt ER、gate、Git 或发布流程。
