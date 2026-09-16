# impl-package 插件移植 zcode 计划（修订版）

原则：功能尽量移植，zcode 有原生形式就用原生的。版本保持 `0.4.2`。已按官方文档（zcode.z.ai/cn/docs/plugin、/cn/docs/subagents）修正此前的两个误判：**manifest `agents` 字段原生执行**（4 个 review-track 子代理随插件移植）；zcode marketplace.json 按约定放发布根目录。

## 1. 新增 `plugin-marketplace/plugins/impl-package/.zcode-plugin/plugin.json`

- zcode manifest 探测优先级最高（`.zcode-plugin` → `.claude-plugin` → `.codex-plugin`），必须新增才能让 zcode 读到 hooks/agents（否则读到 claude 版）。
- 字段：identity 字段与 claude 版对齐，`version: "0.4.2"`；
  - `skills: "./skills/"`
  - `hooks: "./hooks/zcode-hooks.json"`（显式指向独立文件，见 §2）
  - `agents: ["./agents/review-track-code.md", "./agents/review-track-standards.md", "./agents/review-track-spec.md", "./agents/review-track-safety.md"]`（zcode agents 注册为子智能体，出现在 Settings → 子智能体 Plugin 分组）

## 2. 新增 `hooks/zcode-hooks.json`（zcode schema；不改名 hooks/hooks.json 以免被 Claude Code 自动发现，codex-hooks.json 不动）

- `PreToolUse`：matcher `^(Edit|Write|ApplyPatch)$`，`type: "process"`（参数向量、跨平台），`command: "python"`，args 含 `${ZCODE_PLUGIN_ROOT}/hooks/impl_package_hooks.py pre-tool-use`，`timeoutMs: 5000`，`statusMessage`。
- `SessionStart`：matcher `^(startup|resume|compact)$`，同上，`timeoutMs: 10000`。
- 丢弃 zcode 不认的 `commandWindows`/`additionalContextLimit`。

## 3. 修改 `hooks/impl_package_hooks.py`（增量，Codex 行为不变）

1. `_session_id()` 环境变量顺序扩展：`CODEX_SESSION_ID` → `CODEX_THREAD_ID` → `ZCODE_SESSION_ID` → `CLAUDE_SESSION_ID`。
2. `_pre_tool_use()` 加 zcode 分支：`tool_name ∈ {Edit, Write, ApplyPatch}` 时取 `tool_input.file_path`（及 `edits[].file_path` 若有），逐段比对最后两段 `.impl-package/state.json`（大小写不敏感、沿用 fixture 豁免），命中输出同款 deny；`apply_patch` 分支保留。
3. 仓库级默认绑定（已确认）：`activate` 无 session 环境变量时写 `session_id: "default"` 绑定（文件 `default.json`）；`_load_binding` 对 `default` 绑定放行任意事件 session；`deactivate` 可删 default。显式 session 语义不变。

## 4. 新增 `plugin-marketplace/marketplace.json`（zcode 市场清单，放发布根目录）

```json
{ "name": "agent-workbench", "plugins": [{ "name": "impl-package", "source": "./plugins/impl-package", "version": "0.4.2", "description": "…", "category": "Developer Tools" }] }
```
- zcode 官方约定是市场根目录的 `marketplace.json`；claude/codex 各自探测自己的子目录，互不影响。

## 5. review-track agents 的 zcode 兼容性

- 4 个文件 frontmatter `name`/`description`/`tools` 与 zcode 必填/可选字段兼容，正文即 system prompt，**不改共享文件**。
- 文件里 Claude 扩展字段（`agents_md: true`、`skills:`）zcode 文档未定义——实机验证时若 zcode 报诊断或忽略异常，再决定是否需要 zcode 专用副本（默认预期是宽容忽略）。

## 6. Skill 与文档同步

- `skills/dev-with-track/SKILL.md` L28/L32：activate/deactivate 表述改为宿主无关（Codex/ZCode 调用；zcode 无 session 环境变量时自动落仓库级默认绑定）；其他宿主跳过。
- `README.md`：插件安装节加 zcode 方式（Discover → `+` 添加 `plugin-marketplace` 本地目录）。
- `docs/workbench-design/04-install-spec.md`：manifest/marketplace 矩阵加 zcode；宿主清单同步。
- `AGENTS.md`：首句宿主列表加 `zcode`。
- `plugin-marketplace/plugins/impl-package/references/codex-hooks.md`：加 zcode hooks 差异小节。

## 7. 测试扩展

- `tests/test_impl_package_plugin.py`：
  - manifest 一致性测试加 zcode 版（version/skills/hooks 路径/agents 四条路径存在）。
  - marketplace 测试加根目录 `marketplace.json`（name、source 指向 impl-package）。
  - `zcode-hooks.json` 结构测试：仅七个合法事件、process 类型字段匹配、无 `commandWindows`/`additionalContextLimit` 之类未知字段。
- `tests/test_impl_package_hooks.py`：
  - zcode PreToolUse：Edit/Write `file_path` 指向 `.impl-package/state.json` → deny；普通路径放行。
  - 仓库级默认绑定：无 session 环境时 activate 写 `default`、任意事件 session 的 session-start 恢复 capsule、deactivate 清除；显式 session 语义回归不变。
- 校验：`python -m pytest tests/test_impl_package_plugin.py tests/test_impl_package_hooks.py -q`，加 `tests/test_impl_package_agents.py -q` 兜底（manifest 属跨模块变更）。

## 8. 实机验证（zcode 客户端，我用 computer-use 操作）

1. Settings → 插件管理 → Discover → `+` 添加本地目录 `D:\CodeSpace\agent-workbench\plugin-marketplace`，安装 impl-package。
2. 核对详情页：skills 出现、两个 hook runnable、4 个 review-track 子代理出现在 Plugin 分组。
3. 在本仓库开 zcode 会话实测：SessionStart capsule 注入、Edit 指向 `.impl-package/state.json` 被 deny、`activate` 无 session 变量时落 default 绑定。
4. GUI 受阻时输出手工步骤。

## 不移植项（明确记录）

- `additionalContextLimit`：zcode 无对应字段，丢弃（脚本内已有 1200 字节预算逻辑，影响小）。
- 其余全部原生移植：skills、hooks（适配后）、agents（原生支持，修正此前误判）。
