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
- `-AllowOrigin https://host[:port]`：只在该来源不是本机 tailscale 节点名时才需要传（见下节），否则自动发现

启动后浏览器打开脚本打印的 `http://127.0.0.1:43188`。日志在同目录的 `server.log` / `server.err.log`。

## 手机远程访问（Tailscale）

看板只监听 127.0.0.1，远程访问靠 `tailscale serve` 在 tailnet 内反向代理，不暴露公网：

```powershell
# 一次性：把 443 反代到本机看板（配置存在 tailscaled 里，重启后仍然有效）
tailscale serve --bg 43188
```

启动时看板会问本机 tailscale 自己叫什么（`tailscale status --json` 的 `Self.DNSName`），把 `https://<节点名>.ts.net` 加进允许来源，所以不用手填节点名，改名也不用改配置；启动日志会打印 `远程：https://...`。tailscale 没装、没登录或没在跑时跳过这一步（本机访问不受影响），用别的反代地址则显式传 `-AllowOrigin`。

手机装 Tailscale、登录同一账号后访问同一个地址。`tailscale serve` 只对 tailnet 内设备开放。电脑睡眠 / 关机 / 退出登录时远程不可用。

登录自启：`%APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\SessionBoard.vbs` 会静默跑**运行目录**里的 `board.ps1 -Action start`；删掉该文件即取消自启。

## 运行目录（服务跑的是哪份代码）

服务不从开发仓库跑，固定跑 `D:\vibe-code-life\SessionBoard\app`：本仓库的 git worktree，分支 `board-live`，跟踪 `origin/main`，只用来运行、不在里面开发。

- 启停都用那份脚本：`powershell -ExecutionPolicy Bypass -File D:\vibe-code-life\SessionBoard\app\skills\session-board\scripts\board.ps1 -Action restart`
- 更新用 `-Action update`：代码目录有已跟踪的未提交改动就拒绝，否则 `pull --ff-only` 后自动重启。开发仓库改的代码要先 commit → push 才会被拉到
- `-Action status` 会打印当前 HEAD 和脏改动数，用来确认跑的是哪一份
- 开发仓库随便切分支都不影响它（反过来也不生效，这是刻意的）
- 数据库与日志仍在 `D:\vibe-code-life\SessionBoard\`，不在代码目录里

## macOS / Linux

同一个脚本在 PowerShell 7（`pwsh`）下可直接跑，`brew install --cask powershell` 装好后：

```powershell
pwsh -File skills/session-board/scripts/board.ps1 -Action start
```

脚本按系统自行切换：macOS 用 `python3`、看板库默认落在 `~/SessionBoard/board.sqlite3`（`-Db` 可覆盖）、进程查找改用 `ps -axo pid=,command=`，不再传 `-WindowStyle`（macOS 没有隐藏窗口）。

机器上没有 pwsh 时，用等效的原生命令（在仓库根目录执行）：

```bash
python3 -m scripts.session_board --db ~/SessionBoard/board.sqlite3 --port 43188 --deepseek-model deepseek-v4-flash
```

停止：`pkill -f scripts.session_board`。健康检查：`curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:43188/`。

## 出问题先看这三件事

- **页面空白 / 打不开**：先 `-Action status`。进程在但 HTTP 不通，多半是手动从开发仓库启动的——那份工作区被切走后服务读不到 HTML。自启跑的是运行目录，不受影响；切回 `main` 再 `restart` 即可。
- **端口被占**：`-Action stop` 会按命令行里的 `session_board.py` 找 python 进程，不按端口乱杀；确认只停看板进程。
- **改了代码没生效**：HTML 每次请求都从磁盘读，改完刷新页面即可；`.py` 改动必须 `restart`。
- **手机打开是 `{"error":"请求来源不允许"}`**：看板启动时没拿到 ts.net 来源——多半是那一刻 tailscale 没在跑（没登录 / 服务没起），自动发现失败。确认 `tailscale status` 正常后 `-Action restart` 即可；改动过节点名或用了别的反代地址，重启也会重新发现。

## 开发时再读

[`references/dev-log.md`](references/dev-log.md) 是这块看板的开发记录（分层、过滤规则为什么长这样、历史坑）。**平时不要读它**，只在用户要求修改看板、调整过滤 / 摘要 / 标签规则，或排查“某会话为什么没出现 / 为什么出现两张卡”时才读。
