# Gate

- Verdict: <pass|fail|blocked|defer>
- Attempt: <attempt-id>
- Revision aliases: D<n> / S<n> / P<n>
- Comparison commit: <Git commit ID>
- Reason: <直接说明判决理由>

## Evidence

- <repo-relative-path#anchor>

## Durable Deltas

- <事实增量及 `_pending.md` / truth pointer；没有时写 none>
- Reason: <无增量时必须填写>

terminal Gate 前：已有 `execution-findings.md` 必须完成 Decision/Spec/Execution Record/Durable Delta 分流；Planned Verification 中的 manual 项必须有 readiness 与结果证据。
