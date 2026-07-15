# Apply Runbook

Apply 只接受同一 config、当前 method activation、固定 Source HEAD 的 audit/report，以及 owner 明确批准的 item ID。先验证 report baseline；evidence、目标权威或 Source HEAD 漂移时停止该 item 并保留 pending。禁止把“将报告全部处理”解释为批准。

每个批准 item 只写入唯一 canonical owner；跨 module 只写指针。首次创建 module PRD 必须满足 [module PRD 惰性创建门](constraint-extraction-and-routing.md#module-prd-惰性创建门)。仅当条目完整应用或 owner 明确 supersede 才清 pending。watermark 最多推进到 audit 的 Source HEAD，未处理 package 保持 carry-forward。

完成后记录 apply result，并运行项目规定验证和 `scripts/verify_stable_docs.py`。任何未批准、冲突或不可验证的内容都不写入。
