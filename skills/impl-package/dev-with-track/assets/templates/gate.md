# Gate Ledger

> Newest-first、append-only。每次 evaluation 在本说明之后插入新 entry；已存在 entry 不得修改。完整验证过程在对应 plan 的 Execution Record，gate 只保存判决摘要与 Durable Deltas。revision 号是别名，commit SHA 才是权威；写入前用 `git log -1 --format=%H -- <path>` 重新核对，不符先按 impl-package-composition-contract.md §2 处理 drift。

## <attempt-id>-G<n> · <pass|fail|blocked|defer>

- Attempt ID:
- Supersedes: <gate-entry-id | none>
- Evaluated at:
- Design revision: D<n> (commit <sha>)
- Spec revision: S<n> (commit <sha>)
- Plan revision: P<n> (commit <sha>)
- Composition: tickets=<true|false>, dag=<true|false>
- Comparison point:
- Evidence: <one or more plan path#ER-n>
- Unresolved blocker / deferred item:
- Verdict reason:

### Durable Deltas

<!-- Retain exactly one form. terminal verdict（pass/fail/defer，全部三种）写入前必须完成：findings.md 已分流、_pending registration、module truth pointer 与必要 stub；blocked 如实记录 capture gap，后续用新 entry 补齐。 -->

| Delta ID | Destination | Source | Statement | Affected modules | Authority | Evidence | Pending registration | Truth pointer / stub verification |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

或：

- none
- Reason:
