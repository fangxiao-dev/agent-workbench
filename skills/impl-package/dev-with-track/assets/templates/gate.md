# 门禁账本（Gate Ledger）

<!-- impl-package:projection gate-status begin -->
状态：<最新 finalized entry 的 verdict 人话摘要；这一行不是 ledger 本身，不能单独携带 entry 里没有的判断或证据>
<!-- impl-package:projection gate-status end -->

> 最新记录在前、仅允许追加。每次 evaluation 在本说明之后插入新 entry；已存在 entry 不得修改。完整验证过程在对应 plan 的 Execution Record，gate 只保存判决摘要与 Durable Deltas。正文必须让 owner 直接读懂 revision 与校验结论；精确 blob 从内部 sidecar 解析并用 `git rev-parse HEAD:<path>` 复核，不符先按 impl-package-composition-contract.md §2 处理 drift。

## <attempt-id>-G<n> · <pass|fail|blocked|defer>

- 执行尝试 ID（Attempt ID）：
- 取代（Supersedes）：<gate-entry-id | none>
- 评估时间（Evaluated at）：
- 修订集合（Revision set）：D<n> / S<n> / P<n>
- 绑定校验（Binding validation）：<passed | failed>
<!-- 机器审计元数据：sidecar=.impl-package/revision-bindings.json; D=<oid>; S=<oid>; P=<oid> -->
- 执行组合（Composition）：tickets=<true|false>, dag=<true|false>
- 比较点（Comparison point）：
- 证据（Evidence）：<一个或多个 plan path#ER-n>
- 未解决 blocker / deferred item：
- 判决理由（Verdict reason）：

### 长期增量（Durable Deltas）

<!-- 只保留一种形式。terminal verdict（pass/fail/defer，全部三种）写入前必须完成：findings.md 已分流、_pending registration、module truth pointer 与必要 stub；blocked 如实记录 capture gap，后续用新 entry 补齐。 -->

| 增量 ID | 目标位置 | 来源 | 事实陈述 | 受影响模块 | 权威来源 | 证据 | Pending 登记 | Truth pointer / stub 校验 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |

或：

- 无
- 原因：
