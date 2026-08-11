# Contract Surface Design

当 Spec Design Preflight 识别出至少一个 API operation、persistence model、cross-module seam 或 public read model 时读取。以下是按信号使用的完成下限，不是每项必填的 checklist：只冻结会改变可观察行为、跨模块兼容或正确性的维度，不为不适用的迁移、恢复、分页等事项制造合同。使用等价的 table、typed pseudocode、schema 或 prose 均可；Gate 判断规范语义是否闭合，不强制一种表示法。

## 共用完成判据

两个独立实施者只读取当前 Spec contract ensemble，可以选择不同文件、类、库与物理实现，但不得因此产生不同的 API、data identity、permission result、concurrency result、recovery behavior 或 public shape。若仍有两种合理且可观察结果，Spec 必须先选择其一。

Plan 只拥有实现位置、代码组织、library/provider、migration SQL、普通性能索引、执行顺序与验证策略。正确性依赖的 uniqueness、atomicity、compatibility、backfill/reject/read-only behavior 仍属于 Spec。

## API operation

每个 operation 按适用性冻结：

- caller、业务动作与成功结果；
- delivery path；HTTP 场景的 method/route；
- authentication、permission 与 resource scope；
- request/response DTO 的字段名、类型、required/nullability、enum 与 validation boundary；
- idempotency key、optimistic concurrency token/CAS 与重复/stale 请求结果；
- stable error code、safe details 与需要稳定时的 HTTP/status mapping。

Controller/service 名称、framework decorator、mapper 组织与文件布局属于 Plan。

## Persistence model

每个 aggregate/entity/value object 按适用性冻结：

- stable identity、tenant/ownership key 与业务唯一性；
- normative fields、types、required/nullability、enum、default 与 normalization；
- relationship、cardinality、lineage、组合约束与跨 owner 引用边界；
- lifecycle、mutable/immutable boundary、revision/CAS 与状态转换；
- correctness 所需的 atomic boundary、delete/retention、legacy compatibility、backfill/reject/read-only semantics；
- hash 的用途、canonical input coverage 与 version；algorithm 只有在 interoperability/security contract 需要时才冻结。

Prisma/model code、table/column physical naming、migration SQL、repository class 与非语义性能索引属于 Plan。

## Cross-module seam

每个 seam 按适用性冻结：

- owner、producer、consumer 与允许调用的 operation；
- typed input/output/event payload、authority 与 private-field exclusion；
- sync/async、ordering、deduplication/idempotency 与 delivery guarantee；
- version/compatibility admission、caller/callee failure surface、retry/compensation/recovery owner；
- permission、tenant、trust 与 external side-effect boundary。

SDK、adapter class、queue/provider 与内部 serialization implementation 属于 Plan，除非它们本身是外部兼容合同。

## Public read model

每个 projection 按适用性冻结：

- consumer、查询/订阅入口与 authoritative source；
- state variants、field presence/nullability、enum 与 discriminant；
- visibility、permission scope、sensitive-field exclusion 与 safe diagnostics；
- ordering、pagination/cursor、freshness/staleness 与 compatibility behavior；
- stable blocking/error shape，以及 partial/unknown state 时 consumer 可以相信什么。

Query、mapper、cache、component 与 internal aggregation strategy 属于 Plan。
