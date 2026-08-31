# [实施名称] 合同设计

Owning Spec：[spec.md](spec.md)
Disposition: detailed | not-required
Reason:

本文是当前 `spec.md` 的从属 artifact，只承载 `spec.md` 的“Spec 设计范围”明确委托的精确合同。它没有独立 Status、revision、approval 或 Gate；行为、状态、权限、不变量、恢复与 Acceptance Semantics 仍由 `spec.md` 拥有。

<!-- 默认使用 detailed。只有全部精确语义已由 spec.md 完整承担时才使用 not-required，并在 Reason 说明依据；not-required 删除下方全部详细合同章节，不制造 N/A 矩阵。 -->

下游（Ticket/Plan）按 entry point 引用本文件、不整节加载；因此每个 Operation、Aggregate、Seam、Projection 必须有稳定、可搜索的名称（表格首列或小节标题内命名），供 `path#section-anchor · <entry point 名>` 格式引用。

## Detailed contracts

## API operations 与 DTO

| Operation | Caller / permission / scope | Transport / route | Request | Response | Idempotency / concurrency | Stable errors |
| --- | --- | --- | --- | --- | --- | --- |

### Normative schemas

## Canonical persistence model

### Aggregate / entity / value object

### Identity、fields 与 nullability

### Relations、uniqueness 与 lineage

### Lifecycle、immutability、CAS 与 atomicity

### Compatibility、delete 与 retention

## Cross-module seams

| Seam | Owner / producer / consumer | Typed payload / authority | Delivery / ordering / deduplication | Compatibility | Failure / recovery owner |
| --- | --- | --- | --- | --- | --- |

## Public read models

### Normative projections

### State variants、visibility 与 freshness
