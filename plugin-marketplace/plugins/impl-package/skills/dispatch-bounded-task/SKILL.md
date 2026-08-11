---
name: dispatch-bounded-task
description: 当批准的 Plan、Ticket 或 DAG 已提供已释放的实现/只读验证单元、授权边界和 scheduling contract 时使用；选择具体 worker、派发并回收局部证据。
---

# Dispatch Bounded Task

本 skill 把一个已释放 bounded unit 适配为具体派发。单元设计、调度和正式验收仍由各自 owner 负责。

## 派发

1. 确认调用者给出批准来源、已释放单元、授权边界和完整 scheduling contract。
2. 产生实现变更时选择 Implementer；只执行既定检查并返回证据时选择 Verifier。
3. Implementer 在 `luna-worker` 可用且符合 bounded contract 时默认使用；fallback 到其他 subagent 时记录不可用或不适配原因。Verifier 使用调用者指定或当前宿主适配的验证 worker。
4. 读取 [Bounded Task 模板](references/task-templates.md)，填入当前单元，并原样传递 scheduling contract 后派发。

## 返回合同

- Implementer `DONE` 返回变更、文件和局部验证；Verifier `DONE` 返回既定动作的 red/green 证据。两者都不表示 Ticket accepted。
- 输入缺失或 worker 遇到未决 contract、共享 seam、越权、ownership 重叠或无法可靠继续时返回 `BLOCKED`，包含 source unit、原因、建议动作和可选 Ticket ID。
- Working Branch owner 集成产出、处理 seam/冲突并采信共享验证；`/impl-package:dev-with-track` 负责正式 review、Ticket acceptance 与 package 收口。
