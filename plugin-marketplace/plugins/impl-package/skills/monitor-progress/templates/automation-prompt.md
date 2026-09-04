运行监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，已加载固定 hash=`{{STATIC_HASH}}`。

每轮：
1. 调 `read-cycle`；按 source/turn/时间结合同批前序消息和 observations 分类 `ownerInputs`；用 `read_thread` 补状态，`items: []`=不可见。
2. 应用全部 confirmed observations；工具调试不入 sidecar，candidate 不授权动作；dry-run 禁发 target。
3. `observationDiff` 逐条报新增/更新/删除、ID/topic/完整内容；`rendererDiff` 为 dead/missing/mismatch 时报告 PID、43187、影响和“未自动重启”。
4. 应纠偏且原因/全文不同于 `lastSimulationCorrection` 时，报告“模拟纠偏（未发送）”、原因和全文；相同省略，无触发写 null。
5. 报告成形后复制 `nextRolloutCursors`、`rendererStatus`→runtime.rendererState 和 `lastSimulationCorrection`；stdin 调 `write-cycle`，失败重放。其余无语义变化则 `DONT_NOTIFY`。
6. static 异常时只调一次 `read-static`。

只读两个 task 并运行 CLI；不改目标、任务包、数据库、环境或 Git。按 heartbeat XML contract 返回。
