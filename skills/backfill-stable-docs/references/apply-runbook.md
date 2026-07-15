# Apply Runbook

Apply 只接受 schema v2、同一项目 repository、同一 config 与 owner 明确批准的 item ID。Plugin-era audit/state、不同 method repository、不同项目 repository 或 config context 一律 fail closed；同 repository 的 method commit 漂移不要求重做整份 audit。禁止把“将报告全部处理”解释为批准。

先用 `scripts/verify_stable_docs.py --audit-json <path> --source-head <current-head>` 验证 report。当前 Source HEAD 必须等于或是 audit Source HEAD 的 descendant；逐项重算 item-scoped fingerprint。只有 fingerprint、唯一 canonical owner 与 evidence 仍可验证的批准 item 可以写入，受影响 item 停止并保留 pending。不要因为 method commit 或其他 item 的 Source HEAD 漂移而阻止未受影响 item。

每个批准 item 只写入唯一 canonical owner；跨 module 只写指针。首次创建 module PRD 必须满足 [module PRD 惰性创建门](constraint-extraction-and-routing.md#module-prd-惰性创建门)。仅当条目完整应用或 owner 明确 supersede 才清 pending。watermark 最多推进到 audit 的 Source HEAD，未处理 package 保持 carry-forward。

完成后记录 apply result，并运行项目规定验证和 `scripts/verify_stable_docs.py`。任何未批准、冲突或不可验证的内容都不写入。
