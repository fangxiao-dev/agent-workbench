# IndelibleVivi/oracle：用途与 Windows/WSL 可用性

> 调研日期：2026-08-31
> 调研对象：[`IndelibleVivi/oracle`](https://github.com/IndelibleVivi/oracle) `main` 分支
> 资料范围：仅使用该仓库的 README、文档、配置、源代码和测试；未把第三方文章当作依据。

## 先给结论

- **它不是 Oracle 数据库工具。** 这是一个 Node.js 命令行工具和 MCP server：把 prompt 与指定的代码/文件打包，交给 ChatGPT 的 GPT-5.6 Pro 做第二模型审查、研究或架构咨询，并把会话、回答、产物和恢复 lineage 保存在本地。
- **Windows 原生可用，但浏览器路径不是“完全无条件稳定”。** 仓库的安装文档把 Windows 列为 CLI 支持平台；代码还包含 Windows Chrome 路径、Windows 进程查询和 Windows 路径身份匹配。另一方面，仓库自己的 Windows 备注明确说 browser engine 已允许在 Windows 上运行，但应预期更多 flaky。最稳妥的判断是：**CLI/API 原生使用可行；ChatGPT 浏览器自动化也可尝试，但要先做 smoke，失败时切 API 或远程 Chrome。**
- **WSL 可行，但应视为跨 Linux/Windows 浏览器边界的部署方式，而不是独立的一键 WSL 安装包。** 仓库检测 WSL，并根据 `/etc/resolv.conf`、`WSL_HOST_IP` 或显式 host 决定连接本地 Linux Chrome 还是 Windows 主机上的 Chrome；跨边界时需要正确的 CDP 地址、端口和 Windows 防火墙配置。

## 它具体做什么

### 普通咨询/审查

默认的 canonical lane 是 dedicated Chrome for Testing + loopback CDP：Oracle 使用独立的持久化浏览器 profile，不读取日常 Chrome profile 的 cookies；人工首次登录 ChatGPT 后，后续命令通过 CDP 驱动 ChatGPT 页面，发送 prompt/选定文件，等待回答并保存 transcript/artifacts。它还保存 conversation receipt、target identity 和 timing evidence，使断线后能重新连接原会话，而不是盲目重复提交。

入口与依据：[`README.md`（产品边界与两条主路径）](https://github.com/IndelibleVivi/oracle/blob/main/README.md#L200-L219)、[`docs/browser-mode.md`（执行路径与 dedicated profile）](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L194-L208)、[`docs/dedicated-chrome.md`（CDP、隔离 profile 与恢复）](https://github.com/IndelibleVivi/oracle/blob/main/docs/dedicated-chrome.md#L194-L223)。

### Batch Oracle

Batch Oracle 用于一个复杂决策中至少两个相互独立的问题：每个问题成为一个有 mandate、falsification target、证据文件、精确 prompt 和输出合同的 lane；先密封同一份 source snapshot，再并行派发，等 durable barrier 关闭后才可选做 synthesis。它不是把同一 prompt 发给多个模型后投票。

入口与依据：[`docs/batch-oracle.md`（定义与流程）](https://github.com/IndelibleVivi/oracle/blob/main/docs/batch-oracle.md#L4-L16)、[`docs/batch-oracle.md`（命令）](https://github.com/IndelibleVivi/oracle/blob/main/docs/batch-oracle.md#L101-L135)。v1 明确只支持一个独立并行阶段加一个可选 synthesis 阶段；Batch 不走 API、OpenCLI、remote Chrome 或 MCP dispatch：[`docs/batch-oracle.md`（v1 boundary）](https://github.com/IndelibleVivi/oracle/blob/main/docs/batch-oracle.md#L259-L265)。

### 其他路径

- **API mode**：显式使用 OpenAI、Azure OpenAI、Anthropic 或 OpenRouter 的 API key，适合 provider automation、多模型 fan-out 或不想依赖浏览器账户状态的场景。ChatGPT Pro 订阅不等于 API credits。
- **OpenCLI Browser Bridge**：可显式选择的替代 transport，不是 CDP 失败后的自动 fallback。
- **Render**：只在本地生成/查看 bundle，不联系模型。
- **MCP server**：构建后会提供 `oracle-mcp` 入口。

依据：[`docs/quickstart.md`（模式选择）](https://github.com/IndelibleVivi/oracle/blob/main/docs/quickstart.md#L194-L204)、[`docs/install.md`（API key 与本地状态）](https://github.com/IndelibleVivi/oracle/blob/main/docs/install.md#L226-L246)、[`docs/browser-mode.md`（OpenCLI 不自动 fallback）](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L231-L247)、[`docs/cli-reference.md`（CLI/MCP 命令）](https://github.com/IndelibleVivi/oracle/blob/main/docs/cli-reference.md#L194-L210)。

## Windows 原生使用

### 支持证据

安装文档明确要求 Git、Node.js 24+、Corepack/仓库锁定的 pnpm，并把 `macOS, Linux, or Windows for the CLI` 列为支持平台；只有可选的 native notifier helper 要求 macOS：[`docs/install.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/install.md#L197-L217)。`package.json` 也声明 `node >=24`，包管理器为 `pnpm@11.20.0`：[`package.json`](https://github.com/IndelibleVivi/oracle/blob/main/package.json#L108-L119)。

代码层面也不是只按 Unix 写的：

- Windows 下会搜索常见 Chrome/Edge `chrome.exe`/`msedge.exe` 安装路径：[`src/browser/detect.ts`](https://github.com/IndelibleVivi/oracle/blob/main/src/browser/detect.ts#L246-L316)。
- Windows 下用 `powershell.exe` + CIM 查询 Chrome 进程，而非只调用 `ps`：[`src/browser/dedicatedChromeSupervisor.ts`](https://github.com/IndelibleVivi/oracle/blob/main/src/browser/dedicatedChromeSupervisor.ts#L427-L555)。
- 测试覆盖 Windows 路径大小写/斜杠匹配，并在 Windows runner 上验证进程身份读取：[`tests/browser/dedicatedChromeSupervisor.test.ts`](https://github.com/IndelibleVivi/oracle/blob/main/tests/browser/dedicatedChromeSupervisor.test.ts#L110-L227)。

因此，“Windows 能否安装并运行 CLI”答案是**能**；“浏览器自动化是否等同于 macOS 的成熟度”答案是**不能这样保证**。仓库自己的 Windows 工作笔记写明 browser engine 已允许在 Windows 上运行，但应预期更多 flakiness；失败时建议 `--engine api --wait`，或把 `--remote-chrome` 指向已经开启远程调试的 Chrome：[`docs/windows-work.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/windows-work.md#L1-L10)。

### 原生 Windows 最小安装

在 PowerShell 中按仓库的 source-only 流程：

```powershell
git clone https://github.com/IndelibleVivi/oracle.git
cd oracle
corepack enable
pnpm install --frozen-lockfile
pnpm build
npm link
oracle --help
```

该 fork 不发布自己的 npm package、Homebrew formula 或预构建 release，必须从源码安装：[`docs/install.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/install.md#L197-L217)。

想走 ChatGPT 浏览器 lane，再执行 `oracle browser install`、`oracle browser setup`（人工登录并关闭整个 Chrome for Testing）和 `oracle browser smoke`；`--use-mock-keychain` 是文档特别标注的 macOS unattended-mode 选项，Windows 不应照搬该 macOS 专用设置：[`docs/quickstart.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/quickstart.md#L218-L244)。

### Windows 侧的实际限制

- `browser.hideWindow`/`--browser-hide-window` 的窗口隐藏目前只在 macOS 实现，Linux/Windows 会忽略该 flag：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L558-L568)。
- 仓库内 `scripts/browser-tools.ts` 是 macOS-oriented，依赖 `killall`、`mkdir -p` 和可选 `rsync`，不是合法的 Windows launcher；Windows 应使用 Oracle 自己的 dedicated-browser lifecycle：[`docs/windows-work.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/windows-work.md#L5-L10)。
- `--copy-profile` 的临时 profile 路径明确标注为 macOS/Linux 且要求 `rsync`，不应把它当作 Windows 方案：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L341-L342)。
- 浏览器依赖 ChatGPT 当前 UI/model picker；页面 DOM 漂移、登录/Cloudflare challenge、请求频率限制都会让运行失败（认证/页面探测和 picker 逻辑见 [`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L298-L318)）。browser run 不能流式输出 token，只会输出 heartbeat/status：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L558-L568)。
- 默认 dedicated profile 最多允许三个并发 ChatGPT tab；过多并发可能让 UI 不稳定或触发账户侧 throttling：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L468-L473)。

## WSL 方案与边界

### 仓库已有的 WSL 适配

`src/browser/wslHost.ts` 会识别 WSL（`WSL_DISTRO_NAME` 或 Linux release 中的 `microsoft`），并从 `WSL_HOST_IP`、`ORACLE_BROWSER_REMOTE_DEBUG_HOST` 或 `/etc/resolv.conf` 解析 Chrome host。解析到非 loopback host 时，launcher 使用 `0.0.0.0` 绑定并连接该 host；解析到 `127.*` 时回到本地 `127.0.0.1` launcher：[`src/browser/wslHost.ts`](https://github.com/IndelibleVivi/oracle/blob/main/src/browser/wslHost.ts#L3-L55)。对应的单元测试明确区分 `127.0.0.53`（本地 Chrome）与 `172.28.x.x`（Windows/外部 host）：[`tests/browser/wslHost.test.ts`](https://github.com/IndelibleVivi/oracle/blob/main/tests/browser/wslHost.test.ts#L7-L77)。

仓库还提醒：systemd-resolved 的 `nameserver 127.0.0.53` 是 WSL guest loopback，不是 Windows host；Windows Chrome compatibility 应使用解析出的非 loopback host，或把显式 host/port 传给 Oracle：[`docs/windows-work.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/windows-work.md#L10-L14)。CLI 也提供专门适合 WSL/Windows 防火墙的 `--browser-port`：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L313-L318)。

### 实际可选拓扑

1. **Oracle 与 Chrome 都在 WSL/Linux 内**：在 WSL 内安装/使用 Chromium 或 Chrome，使用 dedicated CDP；这是最接近普通 Linux 的路径，但仍要先登录并通过 `oracle browser smoke`。
2. **Oracle 在 WSL，Chrome 在 Windows 主机**：Windows Chrome 需使用独立 profile 并开启可达的 CDP 端口，WSL 侧用 `--remote-chrome <windows-host>:<port>` 或显式 `ORACLE_BROWSER_REMOTE_DEBUG_HOST`/`WSL_HOST_IP`；必须处理 Windows 防火墙。仓库的 remote Chrome 文档说明可连接 Windows VM 上保持登录的 Chrome，并要求把调试端口限制在 VPN/SSH/private network 内：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L474-L514)。
3. **CLI 在 Windows，浏览器在另一台机器**：使用同一 `--remote-chrome` 机制；Oracle 只复用远端 CDP target，不复制 cookies。远端模式下本地 browser lifecycle flags 会被忽略，远端 Chrome 由其所在主机负责关闭：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L502-L514)。

因此 WSL 可以作为“Linux CLI + Windows Chrome”桥接层，但不是为了规避所有 Windows browser flakiness 的保证；跨主机 CDP 会增加端口、防火墙、WebSocket 和远端生命周期的故障面。

## 安全、账户与数据边界

- 这是非官方、unsupported automation boundary 的公开 fork，不隶属于或获 OpenAI 认可；ChatGPT UI、账户策略和 platform terms 可能变化，使用者需自行判断账户风险：[`README.md`](https://github.com/IndelibleVivi/oracle/blob/main/README.md#L202-L207)。
- 本地 `~/.oracle/config.json`、`~/.oracle/sessions/<id>/`、cookies（若显式启用）会包含账户、会话、prompt、回答或产物数据，不应上传到 issue/PR：[`docs/install.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/install.md#L238-L246)。
- 远程 Chrome/CDP 不应直接暴露到公网；仓库要求使用 VPN/SSH/private tunnel，并强调 bearer token 本身不等于公网安全：[`docs/browser-mode.md`](https://github.com/IndelibleVivi/oracle/blob/main/docs/browser-mode.md#L489-L514)。

## 给 Windows 用户的建议

| 目标 | 建议 |
| --- | --- |
| 只想做代码审查/问答，接受 API 费用 | 原生 Windows 安装后显式 `--engine api`，减少浏览器/CDP 变量。 |
| 想使用 ChatGPT 账户中的 GPT-5.6 Pro | 原生 Windows 先跑 dedicated browser setup + smoke；成功后再做真实咨询，失败则试 `--engine api --wait` 或 `--remote-chrome`。 |
| 已习惯 WSL、想把浏览器 UI 留在 Windows | WSL 跑 CLI，Windows Chrome 用独立 profile + CDP，显式配置 Windows host/port，并锁好防火墙。 |
| 想运行 Batch Oracle | 注意 v1 强制 local dedicated-profile direct CDP；Windows/WSL 的 dedicated CDP 先单独验证，再运行 batch。 |

总的来说：**Windows 可以用，适合把它看成“本地可恢复的 ChatGPT 第二模型审查 CLI”，而不是一个传统的跨平台桌面应用。API 路径最省心；要用 ChatGPT Pro 浏览器路径，则需要接受登录、UI 漂移、CDP 网络和账户策略带来的运维成本。**
