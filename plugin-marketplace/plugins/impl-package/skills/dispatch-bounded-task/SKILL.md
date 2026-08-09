---
name: dispatch-bounded-task
description: 当批准的 plan、Ticket 或 DAG 已给出边界明确、依赖已释放且可委派的 Task 时使用；只负责派发和收回局部产出，不设计 Task 或验收 Ticket。
---

# Dispatch Bounded Task

本 skill 是有界 Task 的派发接口。Task 的目标、依赖、primary ownership、贡献 Ticket 与局部验证必须已经由批准的计划或 DAG 给出；缺失时退回 owning stage，不在执行期重新设计 Task。

## 派发

1. 只选择已知依赖满足、且不与活跃 Task 的 primary ownership 重叠的 Task。
2. 调度模式按 `$subagent-driven-development` 执行；未另行选择时默认使用 `default-long`。
3. 使用下方 implementer 模板，填写真实目标、工作目录、primary ownership、禁改范围、已知依赖、贡献 Ticket、必要上下文与局部验证。
4. 集成性 Task 只需额外写明冻结接口、允许修改的连接层、不得修改的核心实现及必须证明的正反向行为。
5. worker 不扩大 scope 或 primary ownership；遇到未决 contract、共享 seam、越权动作、重叠写入或无法可靠继续时返回 `BLOCKED`。

### Implementer 模板

```text
角色：你负责一个横向执行 Task，不负责改变需求、架构或外部副作用边界，也不负责 Ticket 正式验收。

目标：<Task 目标>

执行边界：
- 工作目录：<绝对路径>
- Primary ownership：<模块、目录或共享 seam>
- 禁止越界：<不得修改的文件、模块、公共 seam、生成物或外部状态>
- Known depends on：<Tn / none>
- Contributes to tickets：<Ticket ID 列表；无则说明>
- 必要上下文：<只列完成工作所需的 spec、ticket、plan、contract 或文件>
- 局部验证：<命令或人工检查；无法运行时说明原因>
- 若为集成性 Task：冻结接口、允许修改的连接层、不得修改的核心实现及必须证明的正反向行为

执行规则：
- 先读取必要上下文和当前工作区状态，再在 Primary ownership 内执行。
- 不扩大 scope 或 primary ownership；保留无关改动，不提交、不发布，除非明确授权。
- 发现共享 seam、未决 contract、越权动作、重叠 ownership 或无法可靠继续时，返回 BLOCKED。

返回：
- 状态：DONE / BLOCKED
- 变更摘要、涉及文件、局部验证证据
- 若 BLOCKED：最小原因、建议动作、受影响 Ticket
```

## 回收

- `DONE` 只表示局部产出与证据已返回，不表示 Ticket accepted。
- `BLOCKED` 必须包含最小原因、建议动作和受影响 Ticket。
- Working Branch owner 负责集成产出、处理实际 seam / 冲突、运行共享验证，并由 `dev-with-track` 完成正式 review、Ticket acceptance 与 package 收口。

本 skill 不拥有 Task/Ticket 设计、plan revision、runtime state、Attempt ER、gate、Git 或发布流程。
