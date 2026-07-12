---
name: backfill-stable-docs
description: Use when auditing or applying durable deltas from completed work, pending registers, or unowned commits into an evergreen module-knowledge layer.
---

# Backfill Stable Docs

维护项目的常青 module-knowledge 快照。把 implementation event、pending、漏登 gate 和无主 commit 压实成当前意图或行为合同，同时避免把历史过程和可替换实现细节沉积进常青层。

## 输入合同

开始前解析并记录：

- 项目根目录与 `docs/module-knowledge/`；
- 模式：`report` 或 `apply`；
- 当前 branch、HEAD、dirty 状态；
- Method Activation Ref（可移植 repository identity + commit）与本地 invocation-only method root；
- Project Source Watermark、carry-forward sources 与本次固定 Source HEAD；
- module 清单、`_pending.md`、`_compaction/` 约定；
- apply 时 owner 已批准的 report 路径与 item ID。

Method Activation Ref 只证明方法版本，不参与目标项目 Git range。Project Source Watermark 必须是目标项目内、可验证为 Source HEAD ancestor 的 commit。缺少可信 project watermark 时不得猜测扫描下界；report 把它列为 blocker，bootstrap 必须使用用户明确给出的有界 source manifest。

完整双锚点、source selection、carry-forward 和 collector 合同见 [双锚点与来源选择](references/source-selection-and-dual-anchor.md)。

完成标准：输入基线可由 commit SHA 和路径复现，模式边界明确。

## 模式边界

### report

report 对 source 只读。允许的唯一写入是 `_compaction/` 下的新报告文件；不得 改 module spec/PRD、清 pending、推进 watermark、修复链接或提交业务仓库。

### apply

apply 只处理 owner 明确批准的 report item。批准必须指向具体 report 和 item ID；“把报告都处理了”也要先解析成确定清单。未批准、冲突或 evidence 变化的 item 保持 pending。

完成标准：本轮动作没有越过所选模式。

## Report 工作流

1. **冻结基线**：记录 HEAD、dirty paths、watermark、module 清单和报告目标。
2. **收集 delta**：eligible source 是 Project Source Watermark 后的新 package activity 与未处置 carry-forward package 的并集。package 默认只把 `design.md` 与 `spec.md` 作为 semantic sources；所有 tracked `findings.md` 只登记为 supplemental evidence，只有 design/spec 明确引用或 item 出现 evidence gap / authority conflict 时才读取并记录触发理由。`gate.md`、`_pending.md` 和 commits 只做 closure/coverage 对账；plan、DAG、tickets、progress 与 command logs 默认不作为语义输入。
3. **逐模块约束清扫**：除描述型合同外，强制扫描禁止事项、信任边界、数值 精度与归一化、外部 provider 义务、负依赖。完整方法见 [约束提取与分流](references/constraint-extraction-and-routing.md)。
4. **应用 litmus**：先判断 durable 意图，再判断可验证行为；双是时优先作为 module spec 候选。含 why/how 的句子拆成两个 delta，避免 PRD/spec 复制。
5. **去重与裁决**：同 authority、触发条件、要求/禁止结果才可合并。检查现有 常青文档、代码/测试、批准设计和 owner 决策；冲突不得自行选边。
6. **遵从 tombstone**：旧路径已有重定向时读取最终目标，不重新扫描被替代的 全量旧树。断链、循环或语义不等价只列报告，不在 report 修复。
7. **生成报告**：使用 [报告模板](assets/report-template.md)，每个 module 都要有 `candidate`、`already covered`、`conflict` 或 `no delta` 结论，不能只写有发现的模块。

报告候选必须给出 source、destination、statement、constraint class、authority、 精确 evidence、现有覆盖、风险、建议动作和置信度。仅有代码事实、没有 durable 理由的条目不得提升；仅有旧设计、没有 current authority 的条目不得提升。

完成标准：所有 module、pending、合格 gate 和无主 commit 均有处置；报告能让 owner 按 item ID 独立批准或拒绝。

## Apply 工作流

1. 重新核对 report baseline 与当前 HEAD；source evidence 漂移时停止该 item。
2. 只应用已批准 item，把规则写入唯一 owner module；跨 module 仅放指针。
3. 更新现有 module PRD 时保留 intent/contract 边界。首次创建 PRD 必须通过 [最小内容门](references/constraint-extraction-and-routing.md#module-prd-惰性创建门)。
4. 仅清除已完整应用或被 owner 明确 supersede 的 pending 行；部分应用不清行。
5. tombstone 指向已迁移目标时遵从重定向；除非批准项明确要求，不重写历史源。
6. 运行项目规定的文档、链接和 module contract 验证。
7. 所有批准项已应用、明确 deferred 或记录冲突后，watermark 最多推进到 report 审计的 source HEAD；不得吞掉 report 之后的新 commit。
8. 使用 [Apply 模板](assets/apply-template.md) 在 `_compaction/` 记录 apply 结果、验证证据、新 watermark、未处理 item 与 carry-forward。watermark 推进不能隐式吞掉未处置 source；未处置 package 必须保留为 carry-forward，直到后续 report/apply 明确 dispose 或 supersede。

完成标准：批准项与实际 diff 1:1；pending、验证和 watermark 可追溯；未批准 内容没有被顺手修改。

## Module PRD 惰性创建门

首次 `prd.md` 必须同时具备：Purpose、用户或 journey、Outcomes、 Scope/Non-goals，以及到 top-level PRD 和 module spec 的上下链接。authority 只能 来自 top-level PRD、批准 design、owner 决策或 confirmed gate，不能从代码反推 意图。任一项不足就保留 `_pending.md`，不创建薄弱文件。

## Watermark 与职责边界

- 稳态方法基线使用 Method Activation Ref；目标项目扫描下界使用 Project Source Watermark。二者不得互换，也不得持久化本机绝对 method path。
- Bootstrap 只处理用户明确列出的 sources；它不是全量迁移。
- watermark 后新 activity 与 carry-forward sources 的并集才是稳态 eligible source；推进 watermark 不代表 carry-forward 已处理。
- Git 历史和 migration ledger 承担 provenance；常青层只保存当前快照。
- Point-in-time design 留在 implementation package；调试陷阱进入 hands-on； module spec/PRD 不承担事件时间线。
- 本 skill 不决定新 module taxonomy，也不绕过 owner conflict gate。

## 输出

最终回复报告：模式、双锚点、Source HEAD、报告或 apply 记录路径、候选/已覆盖/冲突计数、carry-forward、Project Source Watermark 状态、验证结果和仍需 owner 决策的 item ID。
