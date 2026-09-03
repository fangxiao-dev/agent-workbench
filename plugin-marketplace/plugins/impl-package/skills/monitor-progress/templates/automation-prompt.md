运行 Impl-Package 监控 `{{AUTOMATION_ID}}`。

- root: `{{WORKSPACE_ROOT_JSON}}`
- cli: `{{MONITOR_CLI_PATH_JSON}}`
- 已加载固定文档 hash: `{{STATIC_HASH}}`

固定文档已在本 chat 加载。每轮：

1. 运行 `python <cli> read-cycle --root <root> --automation-id <id>`，取得完整 observations、runtime、最新评价和 `staticRef`。
2. status/hash 正常时不读固定文档；hash 变化或无法恢复合同时才运行一次 `read-static`。
3. 用返回的 ID 增量读两个 task；`items: []` 表示不可见。每轮应用全部 confirmed observations；工具调试不入任务 sidecar，candidate 不授权动作。
4. 只生成相对上次评价的语义变化。无变化 `DONT_NOTIFY`；否则只写状态变化、下一步变化和新增 Owner 决策，不用内部术语。
5. 仅由条件匹配的 confirmed observation 授权 target 消息，并按 turn ID 去重。
6. 用 `put-observation` / `remove-observation` 更新观察；从 stdin 调 `write-cycle` 写回，最后以 `read-cycle` 验证。

只读两个 task 并运行上述 CLI；不改目标代码、任务包、数据库、环境或 Git。按 heartbeat XML contract 返回。
