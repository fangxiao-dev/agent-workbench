# Guarded Apply

只在 owner 已对唯一候选授权 `apply` 且即将执行写入时读取本文件。

先在 OS temp 生成完整 proposed plan，不修改目标；随后运行 `verify --apply-output <proposed-plan>`。脚本在 ledger 与目标锁内重新核验完整 baseline hash、当前 authorization 与 evidence freshness，先持久化可恢复的 `applying` receipt，再以 create-if-absent 安装 proposal 并保留同目录、run-bound 的 preimage backup。

baseline 不匹配时目标零写入停止。若进程在目标写入与最终 ledger 落盘之间中断，下一次 `resume` 只按 target/backup 的 preimage/output hash 收敛状态，不猜测意图；已有 backup 不覆盖，重试使用新的 run-bound 后缀。写入后逐 hunk 对照授权 manifest；语义超出授权时不得宣称 Apply 成功，并报告 backup 供人工恢复。

Backup 是持久恢复物，只有 owner 确认目标内容且无需恢复迟到写入后才清理，skill 不自动删除。多目标 package 的首次写入不使用 guarded Apply，保持未写入并请求 owner 拆分或选择明确 target。默认不要向持久 plan 追加 ledger 路径或 review report；仅在模板要求、ledger 已导出到稳定位置或 owner 明确要求时写摘要。
