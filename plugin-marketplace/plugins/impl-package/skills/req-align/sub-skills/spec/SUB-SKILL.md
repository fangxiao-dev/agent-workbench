---
name: req-align-spec
description: req-align 内部的 Spec 阶段；先做 Spec Design Preflight，再冻结行为与 canonical contracts，并执行 implementation-ready Spec Gate。
---

# Specification Design

只在 `req-align` 路由到 full 或 spec-only 且 Decision 前置有效时执行。本 SUB-SKILL 拥有 Spec 内容、从属 contract-design 与 initial bundle Spec Gate；package lifecycle 与 Plan 由各自 owning skill 管理；同一 package 的 follow-up 只更新 current Spec contract ensemble。

## 前置输入

- current Passed Decision evidence 与 selected direction；
- canonical package、current Spec/contract-design；未触及的 legacy Spec 允许暂缺从属文件；
- current requirement delta、repository authority、相关 code/tests 与安全边界。

initial spec-only 必须验证 Decision evidence 对当前 delta 适用；同一 package 的 follow-up 沿用 initial bundle approval，直接更新 current Spec。

## Spec Design Preflight

在创建或更新 formal artifact 前完成以下判断：

1. 读取 current `spec.md`、存在时的 `contract-design.md`、repository facts 与 [Spec Gate](../../references/spec-gate.md)；本次创建或修订 Spec 时补齐从属文件。
2. 重建当前完整的 Spec 设计范围，逐项列出 API operations、persistence models、cross-module seams 与 public read models；结果是 current truth，不是本轮 delta 日志。
3. 对非空 contract surfaces 执行 contract coherence check：调用方能取得每个 required input；有副作用、并发或重试语义的 operation 已逐项关闭 identity、重复/stale 结果与恢复；每个可观察字段都有唯一 authority 与实际 producer。使用现有 `spec.md` 或 disposition 为 `detailed` 的 `contract-design.md` 表达；命中以下任一触发时，该 contract surface 必须用结果矩阵，均不命中时维持散文，避免固定 artifact 或矩阵膨胀：幂等键 / CAS / 版本号、多个来源写同一个目标字段、替换 / 撤回 / 恢复语义、跨存储提交（两个 store 各自提交）、声明值 vs 检测值。
   - 矩阵必须有“禁止残留”一列，逐个失败点列出禁止留下的 source、draft、lineage、audit 或 pending object。
4. 关闭会影响 authority、identity、permission、delivery、nullability、CAS、recovery 或 public shape 的选择。能在当前对话解决的 blocker 只保留在 working output；必须暂停、跨 session 或等待外部条件时才持久化简短的 `Spec Gate Blocked`。
5. 选择 `contract-design.md` disposition。默认 `detailed`；只有所有精确语义都已由 `spec.md` 完整承担时才使用 `not-required` 并写明理由。结构会遮蔽行为/验收主线，或同一 canonical model 被多个 operation/module 消费时保持 `detailed`。

完成标准：正式写入前，每个 current contract surface、所需规范设计与唯一承载位置都已确定，交互输入、operation 语义与字段 authority/producer 已闭合。

## 设计与写入

本 sub-skill 拥有 Spec contract ensemble 的语义、Status 与 Gate 条件；主 thread 将已确认的内容和批准交给 bound `/impl-package:standing-bookkeeper`，由 bookkeeper 写入 canonical artifact 并运行 focused validation。

1. 使用 [Spec Template](../../assets/templates/spec.md)，首先写回完整的“Spec 设计范围”，再更新其他章节。
2. 任一 contract surface 非空时读取 [Contract Surface Design](../../references/contract-surface-design.md)，把适用的 implementation-ready 下限冻结在唯一 owner 中。
3. 使用 [Contract Design Template](../../assets/templates/contract-design.md)。`detailed` 时，`spec.md` 拥有行为、状态、权限、不变量、恢复与 Acceptance Semantics，`contract-design.md` 只拥有精确 API/DTO、canonical persistence、seam payload 与 read-model shape；`not-required` 时只保留从属关系、disposition 与理由，不制造空合同章节。
4. 设计中发现新 surface 时立即返回 Preflight，先更新设计范围与承载判断，再继续；不等最终 Gate 才补分类。
5. detailed contract 不再需要时，把仍有效的精确合同吸收回 `spec.md`，更新引用并把 disposition 改为 `not-required`；保留从属文件，Git 保存历史。
6. 仅当信号适用时评估 evidence-integrity contract 与 risk-driven Grill；它们不成为普通变化的固定流程。

Formal artifact 的内容、Status 与 Gate result 必须反映当前已记录事实。initial bundle 完成 owner approval；follow-up 将 current truth 交给 bookkeeper 写入并沿用该 approval。主 thread 不直接编辑当前 package artifact。

## Spec Gate（仅初始 bundle）

Gate 只在 initial bundle 验证前置承诺是否完整兑现：设计范围中的每个对象都有规范合同；contract coherence 已闭合；两个 artifact authority 无重复/冲突；八个行为合同章节内部一致；每个 promise/constraint 映射到 observable evidence；blocking owner decision 与 ambiguity 为零。follow-up 更新直接沿用 initial approval。

若两个独立实施者仍可能因 Spec 留白而产生不同 API、data identity、permission、concurrency、recovery 或 public shape，Gate 必须 `BLOCKED`。Gate 可以发现明显漏分类，但不在此首次设计 DTO、CAS 或 persistence boundary。

## 返回 router

返回 initial Spec Gate result，或 follow-up 更新后的 `spec.md`、`contract-design.md` disposition、Acceptance evidence 与 planning readiness。bookkeeper 回报物理写入与 focused validation；主 thread 采信后再进入 planning。initial PASSED 授权 contract ensemble 进入 planning；implementation、verification、merge 与 release 由后续阶段处理。
