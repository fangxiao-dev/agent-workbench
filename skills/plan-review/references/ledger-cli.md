# Ledger CLI

只在实际执行或恢复 ledger 时读取本文件。CLI 保护审查输入与写入安全，不负责编排 reviewer 角色。

```text
python <skill-dir>/scripts/review_ledger.py discover --target <path> [--include-closed]
python <skill-dir>/scripts/review_ledger.py init --target <path> --skill-version <version>
python <skill-dir>/scripts/review_ledger.py resume --ledger <ledger.json> --target <plan-path>
python <skill-dir>/scripts/review_ledger.py supersede --ledger <ledger.json> --reason <internal-reason> [--replacement-run <run-id>]
python <skill-dir>/scripts/review_ledger.py abandon --ledger <ledger.json> --source <abandonment.json>
python <skill-dir>/scripts/review_ledger.py record --ledger <ledger.json> --input <record.json>
python <skill-dir>/scripts/review_ledger.py status --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py finalize-clearance --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py verify-clearance --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py present-candidate --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py authorize-contextual --ledger <ledger.json> --source <owner-apply-message.json>
python <skill-dir>/scripts/review_ledger.py verify-applied-evidence --ledger <ledger.json>
python <skill-dir>/scripts/review_ledger.py authorize --ledger <ledger.json> --manifest-hash <hash> --source <authorization.json>
python <skill-dir>/scripts/review_ledger.py verify --ledger <ledger.json> [--manifest-hash <hash>] [--apply-output <proposed-plan>]
```

开始完整 review 时先以 candidate plan 运行 `discover`，仅作内部诊断。`init` 自动复用最新的同 candidate active run，并把候选或 baseline 不匹配的 unfinished run 标为 `superseded`；`resume` 发现漂移也自动 supersede。`superseded` 默认不在 discover 中出现，`--include-closed` 保留完整审计历史；其 clearance 与 authorization 不可复用。`applying` 先按 target/backup hash 自动恢复，无法安全恢复时 fail closed 并保留 recovery files，不把恢复动作升级为 owner approval。

`supersede` 是内部、非破坏性的生命周期动作：记录原因、时间、旧 bundle baseline hash 与可选 replacement run，清除 authorization 并使 clearance 失效，不删除 temp 文件。只有 owner 明确取消整个 stage 才使用 `abandon`；它同样保留审计记录。不要恢复角色编制、问题树、消息往返或隐藏推理。
