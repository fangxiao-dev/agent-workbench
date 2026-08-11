# [执行尝试名称] 实施计划

创建时间（Created）：
Attempt ID：<initial | YYYYMMDD-HHMM-patch-topic>
Decision Revision：D<n>
Spec Revision：S<n>
Plan Revision：P<n>
Composition：tickets=<true|false>, dag=<true|false>

> D/S/P 是便于沟通的别名，不绑定文件内容。Git commit ID 是唯一允许持久化的版本锚点。

## 摘要

## 输入

- 决策：decision.md 或 spec.md 内的轻量 Decision
- 规格：spec.md + Spec 设计范围声明为 earned 的 contract-design.md（若存在）
- 需求 / patch 来源：
- 已检查的当前代码、测试和稳定文档：

## 执行组合决策

- Tickets：yes | no
- 理由：
- DAG：yes | no
- 理由：

## 执行策略

- 实施顺序：
- 预计修改范围：
- 依赖与前置条件：
- rollout / rollback：
- 目标分支：
- 集成顺序：gate-before-merge | owner-approved pre-gate integration
- pre-gate integration 授权：<不适用时填 N/A>

## Coverage & Change Map

| Decision/Spec 约束 | 实现范围 | Ticket/Task | 风险或 seam |
| --- | --- | --- | --- |

只列实际受影响范围；后续 P revision 依据本表决定局部重新验证，不机械清空整个 Attempt。

## 计划验证

| 场景 / 约束 | 检查 | 预期结果 | 证据 owner |
| --- | --- | --- | --- |

## 交接

- Ticket 集合：<tickets/ | N/A>
- DAG：<dag.md 或 patch-dag 路径 | N/A>
- 下一动作：
- 剩余 owner 决策：<none | 具体事项>

## Bundle Review & Approval

- Plan freeze：<pending | frozen>
- Joint validation：<Ticket coverage / typed dependency / DAG ownership / evidence feasibility / integration order>
- Review result：<cleared | revise | owner-decision | N/A>
- Owner approval：<same-session statement | Git commit ID | pending>
- Progress：progress.md（`init` 后生成）

## Patch 增量

<!-- initial attempt 删除本节。 -->

- 上一个 terminal gate：
- 变化分类：implementation-only | behavior-contract | decision-direction
- 复用或更新的 D/S：
- 相对已验收行为的增量：
- 回归范围：
