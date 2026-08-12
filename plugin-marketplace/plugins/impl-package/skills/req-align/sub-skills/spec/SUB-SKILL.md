---
name: req-align-spec
description: req-align 内部的 Spec 阶段；先做 Spec Design Preflight，再冻结行为与 canonical contracts，并执行 implementation-ready Spec Gate。
---

# Specification Design

只在 `req-align` 路由到 full 或 spec-only 且 Decision 前置有效时执行。本 SUB-SKILL 拥有 Spec 内容、optional detailed contract 与 Spec Gate，不拥有 package lifecycle 或 Plan。

## 前置输入

- current Passed Decision evidence 与 selected direction；
- canonical package、current Spec/optional detailed contract；
- current requirement delta、repository authority、相关 code/tests 与安全边界。

spec-only 必须重新验证 Decision evidence 对当前 delta 仍适用。delta 若改变 business outcome、selected direction、critical authority、delivery path 或 Acceptance Semantics，返回 Decision 阶段；不得在 Spec 内补作新的方向选择。

## Spec Design Preflight

在创建或更新 formal artifact 前完成以下判断：

1. 读取 current `spec.md`、存在时的 `contract-design.md`、repository facts 与 [Spec Gate](../../references/spec-gate.md)。
2. 重建当前完整的 Spec 设计范围，逐项列出 API operations、persistence models、cross-module seams 与 public read models；结果是 current truth，不是本轮 delta 日志。
3. 关闭会影响 authority、identity、permission、delivery、nullability、CAS、recovery 或 public shape 的选择。能在当前对话解决的 blocker 只保留在 working output；必须暂停、跨 session 或等待外部条件时才持久化简短的 `Spec Gate Blocked`。
4. 判断精确合同是否继续留在 `spec.md`。当结构会遮蔽行为/验收主线，或同一 canonical model 被多个 operation/module 消费时，earned `contract-design.md`；否则保持单文档。

完成标准：正式写入前，每个 current contract surface、所需规范设计与唯一承载位置都已确定。

## 设计与写入

1. 使用 [Spec Template](../../assets/templates/spec.md)，首先写回完整的“Spec 设计范围”，再更新其他章节。
2. 任一 contract surface 非空时读取 [Contract Surface Design](../../references/contract-surface-design.md)，把适用的 implementation-ready 下限冻结在唯一 owner 中。
3. earned detailed contract 使用 [Contract Design Template](../../assets/templates/contract-design.md)。`spec.md` 拥有行为、状态、权限、不变量、恢复与 Acceptance Semantics；`contract-design.md` 只拥有精确 API/DTO、canonical persistence、seam payload 与 read-model shape，另一侧只引用不复制。
4. 设计中发现新 surface 时立即返回 Preflight，先更新设计范围与承载判断，再继续；不等最终 Gate 才补分类。
5. detailed contract 不再 earned 时，把仍有效的精确合同吸收回 `spec.md`，更新引用后删除 current `contract-design.md`；Git 保存历史。
6. 仅当信号适用时评估 evidence-integrity contract 与 risk-driven Grill；它们不成为普通变化的固定流程。

Formal artifact 的内容、Status 与 Gate result 必须反映当前已记录事实。若输出仍是待 owner 接受的 proposal，只报告 candidate assessment 与待办，不得提前写成实际 `Spec Gate Passed` 或 `ready for implementation planning`；不为此引入第三种 Gate 状态。

## Spec Gate

Gate 只验证前置承诺是否完整兑现：设计范围中的每个对象都有规范合同；两个 artifact authority 无重复/冲突；八个行为合同章节内部一致；每个 promise/constraint 映射到 observable evidence；blocking owner decision 与 ambiguity 为零。

若两个独立实施者仍可能因 Spec 留白而产生不同 API、data identity、permission、concurrency、recovery 或 public shape，Gate 必须 `BLOCKED`。Gate 可以发现明显漏分类，但不在此首次设计 DTO、CAS 或 persistence boundary。

## 返回 router

返回 Spec Gate result、`spec.md`、存在时的 `contract-design.md`、exact blockers/owner decisions、Acceptance evidence 与 planning readiness。PASSED 只表示 contract ensemble 可进入 planning，不表示 implementation、verification、merge 或 release 完成。
