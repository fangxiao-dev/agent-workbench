# agent-workbench

面向持续开发和维护的多宿主 Agent 工程工作台。把需求探索、软件设计、开发协作、验证审查和知识积累组织为可按需组合的能力，支持从一个具体问题到跨模块、跨会话的复杂项目。

你可以用它理清调研材料、推进前后端协作、验证业务路径、改善界面与多语言体验，也可以处理 Azure、Lark、DATEV 等专项问题，或将完成的工作沉淀为文档和经验。

**了解能做什么、各类能力如何配合 → [仓库能力介绍](docs/capabilities.md)**

本页说明安装与维护。仓库提供的方法不等同于当前机器已安装或已连接对应外部服务。

---

## 设计总览

`agent-workbench` 的目标是把可复用的 agent 能力集中维护，然后以非破坏方式暴露给不同宿主：

- `skills/` 保存独立安装的正式 skill，包括自建 skill、审查过的第三方 skill、以及本地工作流知识库
- `plugin-marketplace/` 是独立的插件发布根；其中 `plugins/` 保存多 skill 套件，并分别提供 Codex 与 Claude manifest
- `plugin-marketplace/plugins/impl-package/` 包含共享调查与委派入口、Claude review agents，以及投影到 Codex 全局 role 的安装脚本；`skills/` 仍保留可选的通用 `reviewer`
- `agents/` 保存可安装到宿主的 subagent 定义，包括 Grok 运行监控、本地 Codex role（顶层 `.toml`，投影到 `$CODEX_HOME/agents`）与同名 ZCode 子智能体（顶层 `.md`，复制到 `~/.zcode/agents`）；`frontend-worker`/`backend-worker` 的方法唯一源是同名 skill，宿主 agent 定义只是引用它的薄壳
- `commands/` 保存宿主 command 提示文件；是否能用 `/...` 唤出取决于具体宿主
- `scripts/link_skill.py` 把单个（或全部顶层）skill **link** 到 `~/.agents` / `~/.claude` / `~/.codex` / `~/.grok` 的 `skills/`（Windows junction，Unix/macOS symlink）
- `registry/` 只记录第三方资产来源和重装方式，不记录宿主本机状态
- `docs/workbench-design/` 保存当前实现规范，README 只做入口说明
- `tests/` 保存安装器和核心脚本测试

仓库根目录下的 `.agents/`、`.claude/`、`.pytest_cache/`、`skills-lock.json` 等属于本机运行态、工具状态或缓存，不作为规范源。正式插件索引位于 `plugin-marketplace/` 发布根内部。

---

## 安装（skill link）

薄安装器：`scripts/link_skill.py`。Agent 日常只需 **skill 名 + host**。

```bash
# 单个 skill
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude

# 多个宿主
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude codex grok

# 全部顶层 skills/*
python3 /path/to/agent-workbench/scripts/link_skill.py --all --host claude

# 卸载宿主 link（不删 workbench 源头）
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --unlink --host claude codex grok
```

| 平台 | 机制 |
|------|------|
| Windows | 每个 skill 目录 **junction**（通常无需开发者模式） |
| Linux / macOS / Unix | 每个 skill 目录 **symlink** |

默认行为：

- 非破坏：冲突则跳过并报告，不覆盖
- 仅链接**有效 skill 目标**：目录树内递归存在 `SKILL.md`（可在子目录）；无 `SKILL.md` 的空壳不链接
- 若宿主 `skills` 仍是「整树指向本 workbench `skills/`」的旧 junction/symlink，会先拆掉并建成真实目录，再写 per-skill link
- 支持宿主：`agents`（`~/.agents/skills`，跨宿主共享的 Agent Skills 约定目录）、`claude`、`codex`、`grok`
- 不安装 `agents/` / `commands/`；不改项目 `.gitignore`

`skills/` 支持 bundle（如 `skills/lark-skills/`）：按**顶层目录**链一次，内部子 skill 随目录暴露。

多公开 skill 套件不走 junction/symlink 递归发现；它们放在 `plugin-marketplace/plugins/` 并使用宿主原生 plugin 安装。

> **约定**：workbench 路径尽量固定——link 使用绝对路径。

## 安装（plugin marketplace）

`impl-package` 是 Codex/Claude/ZCode 共用插件。插件目录本身就是安装产物，不需要 build；marketplace 只负责告诉宿主插件名称、版本和来源位置。

```powershell
# Codex
codex plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
codex plugin add impl-package@agent-workbench

# Claude（项目级启用）
claude plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
claude plugin install impl-package@agent-workbench --scope project

# ZCode（客户端 Discover → + 添加本地目录）
# marketplace 目录：D:\path\to\agent-workbench\plugin-marketplace（根目录 marketplace.json）

# Codex 全局 review-track agent profiles（按需刷新）
python plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py --global
```

ZCode 侧 manifest 位于 `.zcode-plugin/plugin.json`（skills + hooks + agents 全量移植）；hooks 使用 `hooks/zcode-hooks.json`（不占用 Claude Code 自动发现的 `hooks/hooks.json` 文件名）。安装或升级后开启新会话，使宿主从插件缓存重新加载 skills；Codex 的全局 review roles 需要在插件升级后重新运行上面的投影脚本。面向用户和 agent 的文档统一使用 `/impl-package:dev-with-track` 形式显式调用；宿主内部 registry/discovery 仍可显示不带 `/` 的 skill key。`link_skill.py --all` 不处理 `plugin-marketplace/`。

### Codex 更新诊断与 bootstrap

`codex_setup.py` 只盘点本仓库管理的 plugin、skills 和 agents，并以 SHA-256 比较当前仓库与全局 Codex 安装态；`agents/` 顶层目录由 inventory 扫描，子目录作为 agent link，顶层 `.toml` 作为 Codex role 文件投影。UTF-8 文本先统一换行为 LF，避免 Windows/macOS 换行差异造成假 drift，二进制仍按原始字节计算。用户自行安装的内容不进入报告。`pull-diff` 应在 `git pull` 后尽快运行，默认使用 `ORIG_HEAD..HEAD`：

```powershell
python scripts/codex_setup.py pull-diff
python scripts/codex_setup.py audit --output codex-audit.md
python scripts/codex_setup.py apply --expect-report <codex-audit.md 中的审计 SHA> --output codex-apply.md
# Owner 明确批准删除报告中的旧受管 link 时
python scripts/codex_setup.py apply --expect-report <audit-sha> --prune-stale
```

`apply` 不能直接运行：它会重新计算当前审计 SHA，只有与上一份报告一致时才更新 plugin cache、skills links、agents links、inventory 中的 role files 和 managed review roles。首次接管已有的未受管顶层 role 文件时，在确认 audit 报告后追加 `--adopt-agents`；Owner 明确批准删除报告中的旧受管 skill/agent link 时追加 `--prune-stale`，真实目录、用户目标、已变化或未被审计的 link 一律拒绝删除。报告后状态发生变化时必须重新运行 `audit`。脚本支持 Windows 与 macOS，优先使用 `CODEX_HOME`，否则检查 `~/.codex`；可用 `--codex-home` 显式指定目标。

### Claude 安装态审计

`claude_setup.py audit` 只读盘点 Claude 宿主：通过 `claude plugin --json` 读取 marketplace 登记与插件安装项，对插件缓存目录（CLI 报告的 `installPath`）与 `plugin-marketplace/` 源树做 SHA-256 快照对比，并审计 `~/.claude/skills` 里的 workbench skill 链接与陈旧链接。退出码：`0` 一致、`2` 有差异、`1` 运行错误。它不提供 `apply`：插件修复走原生 `claude plugin` CLI（见安装器规范），skill 链接修复走 `link_skill.py --host claude`。脚本优先使用 `CLAUDE_CONFIG_DIR`，否则检查 `~/.claude`；可用 `--claude-home` 显式指定目标。

```powershell
python scripts/claude_setup.py audit
python scripts/claude_setup.py audit --claude-home D:\custom\.claude
```

### Impl-Package review agents

`plugin-marketplace/plugins/impl-package/agents/*.md` 是 Claude 插件的原生 agent 定义，安装后可在 `/agents` 中看到 `review-track-code`、`review-track-standards`、`review-track-spec` 和 `review-track-safety`。Claude manifest 显式声明了这四个 Markdown 文件。

Codex 当前插件 manifest 不支持 `agents` 字段，因此不能通过 `codex plugin add` 自动安装这些 role。`install_codex_agents.py --global` 会从同一组 Markdown 定义生成 Codex `.toml` role，并写入全局 `$CODEX_HOME/agents`（未设置时为 `~/.codex/agents`）。Code role 固定使用 `gpt-5.6-sol/high`，Safety、Spec 和 Standards role 固定使用 `gpt-5.6-sol/medium`；该配置同时适用于 `initial` 和 `terminal-final`，`finding-closure` 仍使用独立 `luna-worker`。四个 role 使用与 `do-review` 相同的稳定名称，供 parent 的 leaf dispatch 解析；脚本默认拒绝覆盖非同内容文件，只有明确传入 `--force` 才更新带有本包管理标记（或本包旧格式）的已知文件，并拒绝写入符号链接或 Windows reparse point。

个人 Codex role 放在仓库根目录 `agents/*.toml`，由 `codex_setup.py` inventory 扫描并投影到 `$CODEX_HOME/agents`；当前 `agents/luna-worker.toml` 使用标准 `service_tier`，不走 Fast 处理。它与上述 impl-package review role 的生成和安装流程分开。

### 插件生命周期（Codex / Claude / Grok）

刷新缓存、重装或升级插件时，Agent 按 [安装器规范](docs/workbench-design/04-install-spec.md#plugin-生命周期agent-直接执行) 直接执行 Codex、Claude 或 Grok 的原生 CLI。唯一例外是上面的 Codex 一次性 `codex_setup.py` bootstrap；仓库只额外提供只读安装态审计（`codex_setup.py audit` 与 `claude_setup.py audit`），不包装其他 lifecycle 命令或机器专属配置。修改用户级宿主状态仍需用户明确要求，执行后必须核对安装结果与缓存。

发布 Impl-Package 与 standalone Dispatcher 的组合前，运行 `python -m pytest tests/test_impl_package_plugin.py -q`，验证仓库源码组合及旧 Dispatcher 错配回归；错配诊断包含两侧内容指纹。安装后的实际加载路径与内容仍在宿主安装验收时核对。

### Discuss Ledger MCP 注册

`discuss-ledger` MCP **不**由 `link_skill.py` 注册，需单独运行：

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

Codex 写入项目内 `.codex/config.toml`；Claude 优先 `claude mcp add --scope project`。无 `claude` CLI 时只打印 `.mcp.json` 片段。

---

## 日常使用

### Codex Session Prune

`codex_session_prune.py` 通过 Codex App Server 枚举 session，并按 project、archive state 和更新时间生成安全的删除计划。默认只做 inventory；候选计划也是 dry-run，不会读取或直接删除 rollout JSONL。需要磁盘占用时加 `--disk-size`，工具只枚举 `sessions/` 和 `archived_sessions/` 下的 rollout 文件并读取文件大小元数据，不解析文件内容。

```powershell
python scripts/codex_session_prune.py

python scripts/codex_session_prune.py `
  --project D:\CodeSpace\agent-workbench `
  --archive-state archived `
  --take 20 `
  --max-affected 100 `
  --disk-size
```

审阅输出中的 `plan_id` 后，只有显式同时传入 `--apply --expect-plan <plan_id>` 才会调用 App Server 的 `thread/delete`。apply 会重新枚举并校验计划；Owner 未单独批准具体 plan ID 时不要执行 apply。

### 修改和同步

宿主 `skills/<name>` 是指向 workbench 的 **per-skill** junction（Win）或 symlink（Unix）。新增顶层 `skills/<name>/` 后执行：

```bash
python3 scripts/link_skill.py <name> --host claude
# 或
python3 scripts/link_skill.py --all --host claude
```

仅新增 bundle **内部**子目录时，若顶层 bundle 已 link，通常立即可见。

### 核对宿主最终可见 skills

```bash
bash scripts/list-visible-skills.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File scripts/list-visible-skills.ps1
```

它会按宿主分别列出：

- `installed by workbench`
- `superpowers`
- `personal/global`
- `Merged visible set`

### 按当前问题选择能力

从 [仓库能力介绍](docs/capabilities.md) 了解需求探索、复杂开发、验证排障、产品体验、知识沉淀和专项集成。相关方法可以单独使用，也可以与 Impl-Package 配合；具体触发条件、产物和授权以对应 Skill 为准。

仓库内容分工见上方“设计总览”，安装与宿主差异见 [安装规范](docs/workbench-design/04-install-spec.md)。

---

## 添加新 Skill

1. 独立能力在 `skills/<name>/` 下创建 `SKILL.md`；需要多个公开 skill 和共享资源的套件放在 `plugin-marketplace/plugins/<plugin>/skills/<name>/SKILL.md`（frontmatter 格式见 [docs/workbench-design/02-skills-spec.md](docs/workbench-design/02-skills-spec.md)）
2. skill 专属脚本放进该 skill 自己的 `scripts/` 目录，不要默认提取到仓库顶层

新增顶层 skill 后需要再跑 `link_skill.py`（或 `--all`）才会出现在宿主 `skills/`。

第三方 skill 通过 `npx skills add <pkg> -g -y` 安装，独立能力默认落入本仓库 `skills/<name>/`；插件内能力落入 `plugin-marketplace/plugins/<plugin>/skills/<name>/`。是否需要重跑安装器取决于上面的平台安装态，安装后在 `registry/third-party-skills.md` 补登记实际路径。

---

## 第三方资产登记

第三方资产统一登记到 `registry/`，方便换机器时查阅和重装。对于第三方 skills，正式内容直接放在仓库 `skills/` 下，再由安装器暴露到已选宿主的 skills 目录。

当前按资产类型拆分：

- `registry/third-party-skills.md`：第三方 skills 的人工清单，记录名称、来源、获取方式和备注
- `registry/plugins.md`：第三方 plugins / MCP 的人工清单

记录原则：

- 只登记第三方资产，不登记本仓库自建 skill
- 以”安装单位”记录，不展开插件内每个附带文件
- skills 清单不记录宿主路径和安装状态；plugins 清单可记录启用状态

## 验证安装是否正常

```bash
ls -la ~/.claude/skills/
ls -la ~/.claude/agents/
ls -la ~/.codex/skills/
ls -la ~/.codex/agents/
# Windows PowerShell：确认四个全局 review roles
Get-ChildItem "$env:USERPROFILE\.codex\agents\review-track-*.toml"

ls -la ~/.grok/skills/
```

如果某个宿主识别不到 skill，优先用上面命令确认目录链接是否指向正确路径，以及 `commands/` 文件是否已复制。

## 冲突策略

- skill 目标不存在：创建 per-skill junction（Win）或 symlink（Unix）
- 目标已是指向同一 skill 源的 link：跳过（`skipped`）
- 文件目标不存在：复制
- 文件目标内容相同：跳过并提示 `already copied, skipped`
- 目标已存在但不匹配：跳过并提示 `conflict, skipped`
- 安装器不会删除已有同名目录、文件或其他链接

## 扩展新宿主

- 在 `scripts/link_skill.py` 的宿主映射里增加新宿主名和根目录
- 同步更新 `tests/test_link_skill.py`、`README.md` 和 `docs/workbench-design/04-install-spec.md`
- 其余安装流程复用现有 `skills/agents/commands` 逻辑，无需重写主流程

安装器变更后运行：

```powershell
python -m pytest tests/test_link_skill.py -q
```

第三方 registry 逻辑变更后额外运行：

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1
```
