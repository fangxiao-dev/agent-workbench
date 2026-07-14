# Gate Ledger

> Newest-first、append-only。每次 evaluation 在本说明之后插入新 entry；已存在 entry 不得修改。完整验证过程在对应 plan 的 Execution Record，gate 只保存判决摘要与 Durable Deltas。正文必须让 owner 直接读懂 revision 与校验结论；精确 blob 从内部 sidecar 解析并用 `git rev-parse HEAD:<path>` 复核，不符先按 impl-package-composition-contract.md §2 处理 drift。

## <attempt-id>-G<n> · <pass|fail|blocked|defer>

- Attempt ID:
- Supersedes: <gate-entry-id | none>
- Evaluated at:
- Revision set: D<n> / S<n> / P<n>
- Binding validation: <passed | failed>
<!-- Machine audit metadata: sidecar=.impl-package/revision-bindings.json; D=<oid>; S=<oid>; P=<oid> -->
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
