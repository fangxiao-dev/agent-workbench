# 看板开发记录

只在修改看板代码、调整过滤 / 摘要 / 标签规则，或排查“某个会话为什么没出现 / 为什么冒出两张卡”时读。平时启动、重启、查端口不需要读。

## 分层

- `scripts/session_board_hosts.py`：宿主适配层。transcript 怎么解析、rewind / 分叉 / 压缩怎么识别、哪些会话算后台、注入消息怎么过滤，都只在这里；加一个宿主写一个 adapter。
- `scripts/session_board.py`：核心。同步、条目、摘要调度、HTTP 路由，只通过适配层接口工作，不读宿主目录格式。
- `scripts/session_board.html`：单文件页面（内联 CSS/JS），每次请求从磁盘读。
- `scripts/session_board_summary.py`：摘要轮次（排期 → 调模型 → 记录用量 → 报进度）。
- `scripts/session_board_chat.py` / `session_board_cli.py`：看板助手的工具面与 CLI。

## 规则与其来由

1. **活动时间取最后一条真实消息**，不取文件 mtime：宿主会不断重写记账行，mtime 一直在变（`parse_activity`）。
2. **续写合并**：rewind / 压缩 / 应用内分叉都会新开 transcript 并指回上一段（`requestSessionId`）；Desktop 的 `hostSessionId` 作为兜底（压缩换文件 id 但保留对话 id）。续写段继承父条目的状态、备注、标签、`human`、`entrypoint`——它重放的历史首条不代表谁发起的。
3. **多次 rewind 只留最新**：同一个父、同一个标题的兄弟转写按 mtime 只保留最新一张（`_dead_ids`）；标题不同（用户重命名的分支）各自保留。
4. **后台 / 子会话过滤**（适配层 `is_background`）：入口是 SDK、没有标题且首条消息不是人发起的、cwd 在系统临时目录或 `--worker-path` 下。首条消息是别的 agent 粘进来的整段 brief（剥掉粘贴壳后以 `Human:` 或 `<conversation_history` 开头）虽然带 human 来源标记，也不算人发起。`entrypoint` 晚写的转写每 10 分钟补读一次（`reclassify_at`）。
5. **首次扫描只读尾部 128KB**：大文件不整读。若尾部一条消息都没读到，再回读文件头部（不移动增量游标）；已存在的无消息卡片在同步时补一次重读。
6. **摘要轮次**：先排期（本轮最多 8 条、跳过没有新消息和还在 min_gap 内的），再逐条调模型；`active / done / total` 通过 `/api/items` 暴露。一次刷新 = 同步 + 队列清空，页面在队列跑完前显示“摘要 d/t”，清空后才盖同步时间。
7. **标签**：`tags` + `item_tags` 多对多，12 个预设色只用来区分身份，不参与运行中 / 需关注这些状态语义；每个会话最多 3 个；删标签只解关联；旧的自由文本 `group_name` 在首次打开库时迁移成标签。
8. **需关注**：摘要的 `attention` 字段 + 按摘要版本确认（`attention_generation/position`），打开抽屉即确认，之后同一对话的新摘要若仍要拍板会再次出现。
9. **用量**：每次模型调用入库（`usage` 表，kind 分 summary / chat），按近 1 小时 / 今天 / 近 7 天汇总。
10. **Desktop 深链**用 `hostSessionId` 拼 `claude://…`：它是对话最早那段 transcript 的 id，分叉后不变也仍然有效，不要改成当前 sessionId。
11. **页面交互约束**：hover 不能改变行高或列宽（贴底按钮用绝对定位叠加）；预览固定两行；空区域收起；卡片倾斜只用 `transform`。

## 已知限制

- “进行中”的 30 分钟窗口在页面（`ACTIVE`）和助手（`column_of`）各写死一份。
- `--claude-home` 参数名仍是 Claude 专用，加宿主时需要改。
- `usage` 表没有清理策略，长期会一直增长。
- 扫描窗口 7 天；超出窗口的条目保留用户设置，但缓存文本与摘要会被清掉。
- 头部回读只覆盖 256KB：消息夹在文件中间、头尾都没有时会截断。

## 验证

```powershell
python -m pytest tests/test_session_board.py tests/test_session_board_chat.py -q
```

页面改动在 127.0.0.1:43188 刷新即可；`.py` 改动需要 `board.ps1 -Action restart`。
