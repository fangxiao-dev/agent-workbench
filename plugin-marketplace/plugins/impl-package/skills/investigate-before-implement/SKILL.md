---
name: investigate-before-implement
description: 当实施前仍不清楚失败原因、影响面、既有方案或必要前置事实时使用；只建立实施判断依据，不承担 Task 设计、授权或调度。
---

# Investigate Before Implement

本 skill 只回答一个问题：现有证据是否足以确定真实实施边界。调研产出是会改变下一步决定的事实，不是过程记录。

## 何时调查

- 还说不出失败或违约发生在哪个边界；
- 不知道改动会影响哪些直接调用方或状态；
- 不确定现有实现是否已经提供等价方案；
- 共享状态、外部服务或迁移所需的前置事实尚未建立。

改动位置、影响面和验证方式均已明确，且可以低成本试错并回滚时，直接使用既有实施流程。

## 建立依据

1. 写出一个能被证据回答的具体问题。
2. 核对原因、影响面、既有方案和必要前置事实；只沿当前问题的直接边界调查。
3. 保留会改变实施范围或下一动作的事实，省略过程日志和无决策价值的发现。
4. 按下方合同返回证据判断。

```text
Investigation: EVIDENCE_SUFFICIENT | EVIDENCE_GAP
cause: <已证实原因或缺口>
blast radius: <直接受影响边界>
existing solution: <可复用方案或 none>
boundary facts: <实施必须保留的事实>
unresolved facts: <none 或下一项最小取证动作>
```

`EVIDENCE_SUFFICIENT` 只表示事实足以交给调用者决定下一步，不表示授权、实施、验证或验收已经完成。Plan/Ticket/DAG、执行授权和运行状态继续由各自 owning stage 维护。
