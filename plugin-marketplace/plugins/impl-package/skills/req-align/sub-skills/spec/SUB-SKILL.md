---
name: req-align-spec
description: req-align 内部的 Spec 阶段；先做 Spec Design Preflight，再冻结行为与 canonical contracts，并执行 implementation-ready Spec Gate。
---

# Specification Design

只在 `req-align` 路由到 full 或 spec-only 且 Decision 前置有效时执行。本 SUB-SKILL 拥有 Spec 内容、从属 contract-design 与 initial bundle Spec Gate；package lifecycle 与 Plan 由各自 owning skill 管理，同一 package 的 follow-up 只更新 current Spec contract ensemble。

## 前置输入

- current Passed Decision evidence 与 selected direction；canonical package、current Spec/contract-design（未触及的 legacy Spec 允许暂缺从属文件）；
- current requirement delta、repository authority、相关 code/tests 与安全边界。

initial spec-only 必须验证 Decision evidence 对当前 delta 适用；同一 package 的 follow-up 沿用 initial bundle approval，直接更新 current Spec。

## Spec Design Preflight

在创建或更新 formal artifact 前完成以下判断：

1. 读取 current `spec.md`、存在时的 `contract-design.md`、repository facts 与 [Spec Gate](../../references/spec-gate.md)；本次创建或修订 Spec 时补齐从属文件。
   - 常见误判：只读本轮 delta 或漏读从属文件，会把旧的 current truth 当成完整 Spec。
2. 重建当前完整的 Spec 设计范围，逐项列出 API operations、persistence models、cross-module seams 与 public read models；结果是 current truth，不是本轮 delta 日志。
   - 常见误判：把 delta 日志当设计范围，会让未变化但仍被实现消费的 surface 从 Gate 覆盖中消失。
3. 对非空 contract surfaces 执行 contract coherence check：调用方能取得每个 required input；有副作用、并发或重试语义的 operation 已逐项关闭 identity、重复/stale 结果与恢复；每个可观察字段，以及行为/状态机/工作流表与错误边界表中每一个用户可见结果，都有唯一 authority，并能指到承载它的 read-model 字段与实际 producer。使用现有 `spec.md` 或 disposition 为 `detailed` 的 `contract-design.md` 表达；命中幂等键 / CAS / 版本号、多个来源写同一个目标字段、替换 / 撤回 / 恢复语义、terminal/finalized 状态被再次进入、materialize 或 replay、跨存储提交（两个 store 各自提交）、final authority 与 editable projection 共用同一 identity、声明值 vs 检测值任一触发时，该 contract surface 必须用结果矩阵，均不命中时维持散文，避免固定 artifact 或矩阵膨胀。
   - 矩阵必须有“禁止残留”一列，逐个失败点列出禁止留下的 source、draft、lineage、audit 或 pending object。
   - 常见误判：coherence 只覆盖字段或 happy-path 规则，会遗漏行为/状态机/工作流表与错误边界表中的用户可见结果，以及 identity、stale/retry 或残留对象，两个实施者就能得到不同的恢复结果。
4. 关闭会影响 authority、identity、permission、delivery、nullability、CAS、recovery 或 public shape 的选择；能在当前对话解决的 blocker 只保留在 working output，必须暂停、跨 session 或等待外部条件时才持久化简短的 `Spec Gate Blocked`。
   - 常见误判：把可在当前对话解决的 blocker 持久化，或把必须等待外部条件的 blocker 留在 working output，会分别污染 durable artifact 或让下一个 session 看不到真实阻塞。
5. 选择 `contract-design.md` disposition：默认 `detailed`；只有所有精确语义都已由 `spec.md` 完整承担时才使用 `not-required` 并写明理由；结构会遮蔽行为/验收主线，或同一 canonical model 被多个 operation/module 消费时保持 `detailed`。
   - 常见误判：为了少一个文件而选择 `not-required`，会把多个 operation 共享的精确 shape 藏进行为散文，实施者仍需猜测。

完成标准：正式写入前，每个 current contract surface、所需规范设计与唯一承载位置都已确定，交互输入、operation 语义与字段 authority/producer 已闭合。

## 设计与写入

本 sub-skill 拥有 Spec contract ensemble 的语义、Status 与 Gate 条件；主 thread 直接写入 canonical artifact 并运行 focused validation。运行状态由主 thread 直接通过语义 CLI 更新。

1. 使用 [Spec Template](../../assets/templates/spec.md)，首先写回完整的“Spec 设计范围”，再更新其他章节。
   - 常见误判：先改行为章节再补范围，会漏记新 surface，后面的 contract coherence 检查也失去全集。
2. 任一 contract surface 非空时读取 [Contract Surface Design](../../references/contract-surface-design.md)，把适用的 implementation-ready 下限冻结在唯一 owner 中。
   - 常见误判：跳过 surface design reference，会把 implementation-ready 下限分散到多个 owner 或留给 Plan 临时决定。
3. 使用 [Contract Design Template](../../assets/templates/contract-design.md)：`detailed` 时，`spec.md` 拥有行为、状态、权限、不变量、恢复与 Acceptance Semantics，`contract-design.md` 只拥有精确 API/DTO、canonical persistence、seam payload 与 read-model shape；`not-required` 时只保留从属关系、disposition 与理由，不制造空合同章节。
   - 常见误判：让两个 artifact 同时拥有同一 DTO/状态语义，或为 `not-required` 制造空章节，会形成平行 authority 和伪合同。
4. 设计中发现新 surface 时立即返回 Preflight，先更新设计范围与承载判断，再继续，不等最终 Gate 才补分类。
   - 常见误判：把新 surface 留到最终 Gate 才分类，后续步骤会在错误的 owner 或遗漏的 coherence 检查上继续。
5. detailed contract 不再需要时，把仍有效的精确合同吸收回 `spec.md`，更新引用并把 disposition 改为 `not-required`；保留从属文件，Git 保存历史。
   - 常见误判：只改 disposition、不吸收有效精确合同，会留下引用看似完整但实际无 owner 的 shape。
6. 仅当信号适用时评估 evidence-integrity contract 与 risk-driven Grill；它们不成为普通变化的固定流程。
   - 常见误判：把高成本检查固定到所有普通变化，会稀释真正 risk signal；完全跳过适用信号，又会让高风险 surface 没有额外审问。

Formal artifact 的内容、Status 与 Gate result 反映当前已记录事实；initial bundle 完成 owner approval，follow-up 由主 thread 写入 current truth 并沿用该 approval。

## Spec Gate（仅初始 bundle）

Gate 只在 initial bundle 验证前置承诺是否完整兑现：

1. 设计范围中的每个对象都有规范合同。
   - 常见误判：范围中漏掉一个 object，后面的 coherence 和 evidence 检查都会对着不完整的集合通过。
2. contract coherence 已闭合。
   - 常见误判：只确认章节存在而不确认 required input、identity、stale/retry 与恢复语义，Spec 仍可产生多种实现。
3. 两个 artifact authority 无重复/冲突。
   - 常见误判：两个文件都能改同一字段或状态，后续修订会产生不可判定的 canonical meaning。
4. 八个行为合同章节内部一致。
   - 常见误判：单章节看似完整但章节之间冲突，实施者会选择自己更容易实现的一条解释。
5. 每个 promise/constraint 映射到 observable evidence。
   - 常见误判：只写“已覆盖”而没有可观察证据，Gate 会把信心或邻近测试误当兑现证明。
6. blocking owner decision 与 ambiguity 为零。
   - 常见误判：把未决 owner decision 留到 Plan，Plan 就会被迫替 Spec 发明行为或数据合同。

follow-up 更新直接沿用 initial approval。

若两个独立实施者仍可能因 Spec 留白而产生不同 API、data identity、permission、concurrency、recovery 或 public shape，Gate 必须 `BLOCKED`；Gate 可以发现明显漏分类，但不在此首次设计 DTO、CAS 或 persistence boundary。
   - 常见误判：把明显留白当成“实现时再决定”，会让两个 worker 各自选择不同的 API、identity 或 recovery 语义。

## 返回 router

返回 initial Spec Gate result，或 follow-up 更新后的 `spec.md`、`contract-design.md` disposition、Acceptance evidence 与 planning readiness；主 thread 完成文档写入与 focused validation。initial PASSED 授权 contract ensemble 进入 planning；implementation、verification、merge 与 release 由后续阶段处理。
