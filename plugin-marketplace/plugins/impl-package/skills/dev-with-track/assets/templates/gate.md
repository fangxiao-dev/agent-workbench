# Gate

- Verdict: <pass|fail|blocked|defer>
- Attempt: <attempt-id>
- Revision aliases: D<n> / S<n> / P<n>
- Comparison commit: <Git commit ID>
- Reason: <直接说明判决理由>

## Evidence

- <repo-relative-path#anchor>

## Durable Deltas

- <delta-id>: <事实增量及 truth pointer；没有增量时写 none>
- Reason: <无增量时必须填写>

`delta-id` 必须稳定、可读、无空白（例如 `DD-1`），与 item ID 规则一致：`<package-path>::<delta-id>`。不要用 hash。`none` 表示本轮无 durable delta 候选。

terminal Gate 前：已有 `execution-findings.md` 必须完成 Decision/Spec/Execution Record/Durable Delta 分流；Planned Verification 中的 manual 项必须有 readiness 与结果证据。
