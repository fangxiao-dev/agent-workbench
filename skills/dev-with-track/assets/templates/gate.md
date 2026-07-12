# Gate Ledger

> Newest-first、append-only。每次 evaluation 在本说明之后插入新 entry；已存在 entry 不得修改。完整验证过程在对应 plan 的 Execution Record，gate 只保存判决摘要与 Durable Deltas。

## <attempt-id>-G<n> · <pass|fail|blocked|defer>

- Attempt ID:
- Supersedes: <gate-entry-id | none>
- Evaluated at:
- Design revision: D<n>
- Spec revision: S<n>
- Plan revision: P<n>
- Composition: tickets=<true|false>, dag=<true|false>
- Comparison point:
- Evidence: <one or more plan path#ER-n>
- Unresolved blocker / deferred item:
- Verdict reason:

### Durable Deltas

<!-- Retain exactly one form. terminal verdict（pass/fail/defer）写入前必须完成 _pending registration、module truth pointer 与必要 stub；blocked 如实记录 capture gap，后续用新 entry 补齐。 -->

| Delta ID | Destination | Source | Statement | Affected modules | Authority | Evidence | Pending registration | Truth pointer / stub verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

或：

- none
- Reason:
