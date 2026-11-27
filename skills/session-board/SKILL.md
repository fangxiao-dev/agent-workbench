---
name: session-board
description: 启动、重启或排查本地 Session 看板（127.0.0.1:43188，把本机 Claude / Desktop 会话显示成“进行中 / 最近 / 已完成 / 暂不关注”四栏卡片，带标签、AI 摘要和 token 用量）。用户说“打开 / 启动 / 重启看板”“看板打不开了”“看板端口多少”时使用。
---

# Session Board

看板是本地单进程服务：`scripts/session_board.py` 起一个只监听 127.0.0.1 的 HTTP 服务，页面是单文件 `scripts/session_board.html`，数据全在看板库 `D:\vibe-code-life\SessionBoard\board.sqlite3`（会话文本、状态、标签、摘要、用量）。

## 启动 / 重启

用 [scripts/board.ps1](scripts/board.ps1)，它自己找仓库里的 `scripts/session_board.py`、停旧进程、等端口就绪：

```powershell
powershell -ExecutionPolicy Bypass -File skills\session-board\scripts\board.ps1 -Action start
```

`-Action` 可选 `start` / `stop` / `restart` / `status`，默认 `status`。可选参数：

- `-Port 43188`（默认）
- `-Db <sqlite 路径>`（默认 `D:\vibe-code-life\SessionBoard\board.sqlite3`）
- `-Model deepseek-v4-flash`（默认；摘要走 DeepSeek）
- `-NoSummary`：不开摘要，不向任何模型服务发送会话文本
- `-Script <session_board.py 路径>`：从别的工作区启动时使用

启动后浏览器打开脚本打印的 `http://127.0.0.1:43188`。日志在同目录的 `server.log` / `server.err.log`。

## 出问题先看这三件事

- **页面空白 / 打不开**：先 `-Action status`。进程在但 HTTP 不通，多半是启动时用的那份工作区被切走了——看板代码只在 `main` 和 `feat/session-board` 上，仓库切到别的分支后服务读不到 HTML。切回 `main` 再 `restart`。
- **端口被占**：`-Action stop` 会按命令行里的 `session_board.py` 找 python 进程，不按端口乱杀；确认只停看板进程。
- **改了代码没生效**：HTML 每次请求都从磁盘读，改完刷新页面即可；`.py` 改动必须 `restart`。

## 开发时再读

[`references/dev-log.md`](references/dev-log.md) 是这块看板的开发记录（分层、过滤规则为什么长这样、历史坑）。**平时不要读它**，只在用户要求修改看板、调整过滤 / 摘要 / 标签规则，或排查“某会话为什么没出现 / 为什么出现两张卡”时才读。
