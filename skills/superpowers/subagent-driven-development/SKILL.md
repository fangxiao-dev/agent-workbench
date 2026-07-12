---
name: subagent-driven-development
description: Use when an approved plan or DAG contains bounded implementation units that can be delegated while the main agent retains coordination and integration ownership.
---

# Subagent-Driven Development

主 agent 负责授权、调度、seam、集成和最终判断；subagent 负责边界清楚的执行单元。委派不能转移最终责任。

## 适用条件

使用前确认：

- 已有批准的 plan、ticket 或 DAG；
- 每个执行单元有稳定输入、scope 和验收条件；
- ownership 不重叠，或已有明确的 seam owner；
- subagent 不需要自行决定产品、架构或外部副作用边界。

紧密耦合、仍在设计或需要共享写入的工作由主 agent 直接处理，或先重新分解。

## 调度

1. 主 agent 先读取完整计划，解析依赖、权限和集成点。
2. 给每个 subagent 提供任务正文、必要上下文、工作目录、允许的读写范围、验证要求和返回格式。
3. subagent 遇到未决 contract、越权动作或无法可靠完成的部分时应停止并返回，不自行扩大范围。
4. 独立单元可以并行；共享 seam 或相同运行资源必须串行或隔离。

## 返回状态

subagent 使用以下状态之一：

- `DONE`：实现和约定验证均已完成；
- `DONE_WITH_CONCERNS`：完成但存在需要主 agent 判断的风险；
- `NEEDS_CONTEXT`：缺少继续所需的信息；
- `BLOCKED`：当前授权或方案下无法完成。

返回内容至少包括变更摘要、验证证据、涉及文件和未决问题。主 agent 不只读取状态标签，还要检查实际产物。

## Review 与集成

- 高风险、跨 seam 或容易偏离规格的单元，先检查 spec compliance，再检查 code quality。
- 普通机械单元可以合并 review，不强制为每个微任务派发两名 reviewer。
- reviewer 发现问题后必须修正并复核；不能只记录意见就继续集成。
- 所有单元完成后，主 agent 检查 diff 冲突、接口衔接和整体验证，再由项目正式 gate 判断是否收口。

本 skill 不拥有 worktree、plan revision、runtime ledger、Git 或发布流程；这些由项目规则及对应 owner 管理。
