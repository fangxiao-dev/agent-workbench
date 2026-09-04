监控 `{{AUTOMATION_ID}}`；root=`{{WORKSPACE_ROOT_JSON}}`，cli=`{{MONITOR_CLI_PATH_JSON}}`，static=`{{STATIC_HASH}}`。

每轮：
1. `read-cycle`：`packageStatus` 定状态，`targetUpdates` 定进展，`ownerInputs` 按 observations 顺序分类；`read_thread items: []`=不可见。
2. confirmed 生效。实例替换后仍约束同类则 kind=pattern，否则 specific；混合拆分，topic 单轴。正式状态/工具调试不入 sidecar，candidate 不授权，dry-run 禁发 target。
3. evaluation 只写 target 语义变化；`packageDiff`/`observationDiff`/新模拟纠偏/健康变化触发 NOTIFY。
4. `observationDiff` 写 kind、新增/更新/删除；更新含 before→after 和全文。
5. NOTIFY 必含“模拟纠偏”：触发写原因、全文、未发送，否则写“无”；空值不触发。
6. 保存 nextRolloutCursors、rendererStatus→runtime.rendererState、monitorHealthStatus→runtime.monitorHealthState、lastSimulationCorrection；write-cycle 成功才确认。无变化 `DONT_NOTIFY`；static 异常调 `read-static`。

只读两 task；仅 CLI 写。
