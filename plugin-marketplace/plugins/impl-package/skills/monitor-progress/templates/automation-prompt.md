运行监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，已加载固定 hash=`{{STATIC_HASH}}`。

每轮：
1. 调 `read-cycle`。按 source/turn/时间顺序，结合完整 observations 与同批前序消息分类 `ownerInputs`，再按返回 ID 用 `read_thread` 补 task 状态/assistant 结果；`items: []` 仅表示不可见。
2. 应用全部 confirmed observations；工具调试不入 sidecar，candidate 不授权动作。仅匹配的 confirmed observation 可授权 target 消息，并按 turn ID 去重。
3. `observationDiff` 非空时必须 `NOTIFY`，逐条报告新增/更新/删除、ID、topic 和完整当前内容；否则仅在评价有语义变化时通知，无变化 `DONT_NOTIFY`。
4. 完成分类和通知内容后，才把 `nextRolloutCursors` 的 offset/hash 写入 runtime 并以 stdin 调 `write-cycle`；成功才确认 observation diff，失败则全部重放。cursor reset/unseeded 属异常。
5. static 正常时不读固定文档；变化或无法恢复合同时只调一次 `read-static`。

只读两个 task 并运行上述 CLI；不改目标代码、任务包、数据库、环境或 Git。按 heartbeat XML contract 返回。
