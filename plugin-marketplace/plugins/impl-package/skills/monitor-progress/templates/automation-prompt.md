监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，static=`{{STATIC_HASH}}`。

每轮：
1. `read-cycle`；按 source/turn/时间结合同批前序消息和 observations 分类 `ownerInputs`；`read_thread` 补状态，`items: []`=不可见。
2. 应用 confirmed observations；工具调试不入 sidecar，candidate 不授权动作，dry-run 禁发 target。
3. evaluation 四字段只写 target；无改进则 `improvements=[]`，`next` 仍写 target 下一步；监控自身动作不得混入。
4. `observationDiff` 逐条报新增/更新/删除、ID/topic/完整内容；`monitorHealthDiff` 异常时单列“监控健康”。
5. 新“模拟纠偏（未发送）”报原因和全文；相同省略，无触发写 null。
6. 复制 `nextRolloutCursors`、`rendererStatus`→runtime.rendererState、`monitorHealthStatus`→runtime.monitorHealthState、`lastSimulationCorrection`；`write-cycle` 失败重放。无语义变化 `DONT_NOTIFY`；static 异常调一次 `read-static`。

只读两个 task；仅 CLI 可写监控状态。按 heartbeat XML 返回。
