# [Implementation Name] Gate

> Implementation-level closure record. Stage 7 semantics and all durable-delta checks are
> normative in the shared
> [Impl-Package Composition Contract](../../skill-design/references/impl-package-composition-contract.md).

状态：[开放 / 等待人工确认 / 已通过 / 未通过 / 阻塞 / 延期]
创建：[YYYY-MM-DD]
Spec：[spec.md](spec.md)
Plan：[plan.md](plan.md)
DAG：[dag.md / N/A by composition]
Findings：[findings.md](findings.md)

## Closure Evidence

- Composition checked: [tickets=<true|false>, dag=<true|false>]
- Acceptance evidence checked per AC: [path/link or N/A]
- Seam acceptance checked: [path/link or N/A]
- Review / verification evidence: [path/link]
- Unresolved blocker or deferred item: [none / detail]

## Durable Deltas

Retain exactly one of the two subsections below. The only capture path is this table →
project `_pending.md` → backfill report/apply. Before gate closure, every table row must
have the matching `_pending.md` record under `<destination>|<delta-id>`, every affected
module spec must have its `Pending deltas: <package-id>` truth pointer, and any missing target
module-spec stub must be created before that pointer.

### Durable Deltas Table

| Delta ID | Destination | Source | Statement | Affected modules | Authority | Evidence | Pending registration | Truth pointer / stub verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| [delta-id] | [destination] | [path/package-id] | [durable statement] | [module / N/A] | [authority] | [path/link] | [`<destination>|<delta-id>`] | [pointer + stub path] |

### No durable delta

`none`

Reason：[required when no durable delta exists]

## Gate Decision

Decision：[pass / fail / blocked / defer]

Reason：[why the implementation-level gate has this result]

Next step：

1. [next action]
