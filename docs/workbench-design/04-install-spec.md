# 安装器规范

独立 skill 的主安装入口是 **`scripts/link_skill.py`**：把 workbench 里**单个（或全部顶层）skill 目录** link 到宿主的 `skills/<name>`。`plugin-marketplace/` 下的多-skill 套件使用宿主原生 marketplace/plugin 流程，不进入该脚本。

## Plugin 安装

独立发布根位于 `plugin-marketplace/`。其中 Codex marketplace 位于 `.agents/plugins/marketplace.json`，Claude marketplace 位于 `.claude-plugin/marketplace.json`；两者均以 `agent-workbench` 为 marketplace 名，并从 `./plugins/<plugin>` 读取同一份插件 payload。manifest 使用宿主各自支持的字段，但版本字段必须保持一致；Codex marketplace entry 本身不复制 plugin version。

```powershell
codex plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
codex plugin add impl-package@agent-workbench

claude plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
claude plugin install impl-package@agent-workbench --scope project
```

插件目录就是安装产物，不执行 build。安装和更新会进入宿主缓存；manifest/marketplace 的版本元数据必须同步，更新后开启新会话。除下述 Codex 一次性诊断/bootstrap 外，Workbench 不包装插件生命周期命令，也不在未授权时修改用户级宿主状态。

## Plugin 生命周期：Agent 直接执行

安装、升级、重装或刷新缓存时，Agent 直接调用目标宿主的原生 CLI。仓库不提供 lifecycle Skill、其他包装脚本或机器专属配置。

执行前先读取插件的 Codex/Claude manifest 与 marketplace entry，确认名称、source 和版本一致；再用宿主的 `plugin list` 查看当前安装状态。读取状态和 `--help` 是只读操作；只有用户明确要求安装、升级、重装或刷新时才修改用户级宿主状态。

```powershell
codex plugin list
claude plugin list
grok plugin list
```

### Codex

```powershell
# 首次登记 marketplace（已登记时跳过）
codex plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace

# 安装、升级或刷新本地 cache
codex plugin add impl-package@agent-workbench

# 重装
codex plugin remove impl-package@agent-workbench
codex plugin add impl-package@agent-workbench
```

### Claude

沿用当前安装 scope（`user`、`project` 或 `local`），不要默认为另一个 scope。

```powershell
# 升级或刷新
claude plugin marketplace update agent-workbench
claude plugin update impl-package@agent-workbench --scope <scope>

# 重装
claude plugin uninstall impl-package@agent-workbench --scope <scope> --yes
claude plugin install impl-package@agent-workbench --scope <scope>
```

### Grok

Grok 直接使用本地 plugin 目录，不经 marketplace。

```powershell
# 升级或刷新
grok plugin update impl-package

# 重装
grok plugin uninstall impl-package --confirm
grok plugin install D:\path\to\agent-workbench\plugin-marketplace\plugins\impl-package --trust
```

一个宿主的命令失败后停止该宿主的后续步骤，并准确报告已发生的状态；不要把卸载成功、安装失败写成重装成功。执行后用对应的 `plugin list` 核对 enabled/version，检查宿主报告的 cache 或 installed root 是否包含目标版本；必要时比较 manifest 和关键 Skill 的哈希。最后开启新会话，让宿主重新加载插件内容。

## Codex 一次性更新诊断/bootstrap

`scripts/codex_setup.py` 是唯一允许包装 Codex plugin CLI 的 lifecycle 入口。它只盘点当前仓库管理的 plugin、skills 和 agents；SHA-256 是内容一致性的唯一依据，UTF-8 文本统一换行为 LF 后计算，二进制使用原始字节，plugin version 只作说明。用户自行安装内容、`plugins/data`、staging 和宿主二进制不在范围内。

```powershell
# 查看 pull 前后的仓库增量；默认 ORIG_HEAD..HEAD
python scripts/codex_setup.py pull-diff

# 先生成全局安装态报告和审计 SHA
python scripts/codex_setup.py audit --output codex-audit.md

# 只有当前状态仍匹配该报告 SHA 时才允许 apply
python scripts/codex_setup.py apply --expect-report <audit-sha> --output codex-apply.md
```

`audit` 永远只读；`apply` 没有上一份报告 SHA 时不能启动。apply 前重新计算 SHA，状态变化即阻断并要求重新 audit。通过门禁后，脚本按 marketplace/plugin → skills → agents → managed review roles 的顺序执行；任一步失败就停止后续写操作，最后重新只读审计并报告残余差异。外国链接、真实目录、用户文件和非本工具管理的 TOML 不覆盖、不删除。

脚本优先使用 `CODEX_HOME`，否则使用 `~/.codex`；Windows 使用 junction，macOS/其他 Unix 使用 symlink。`--codex-home` 只在用户显式指定目标或测试时使用。

## Impl-Package agent profiles

Claude 插件根目录的 `agents/` 由 Claude 原生扫描；`impl-package/.claude-plugin/plugin.json` 显式声明四个 Markdown agent 文件。安装后可在 `/agents` 中确认四个 `review-track-*` profile。

Codex 当前插件 manifest 不支持 `agents` 字段，不能把它加入 `.codex-plugin/plugin.json`；否则不能保证插件通过宿主校验。Codex 角色使用全局 `$CODEX_HOME/agents`（未设置时 `~/.codex/agents`），由插件内的显式投影脚本安装：

```powershell
python plugin-marketplace/plugins/impl-package/scripts/install_codex_agents.py --global
```

脚本只生成 `review-track-code.toml`、`review-track-standards.toml`、`review-track-spec.toml` 和 `review-track-safety.toml` 四个已知文件；默认拒绝覆盖不同内容，`--force` 只更新带有本包管理标记（或本包旧格式）的这些目标，并拒绝符号链接或 Windows reparse point。四个 Codex role 与 `do-review` 的 leaf-agent 名称一致，插件升级后需重新运行脚本；项目级 `.codex/agents` 不属于本安装目标。

| Codex role | Model | Reasoning effort |
|------|------|------|
| `review-track-code` | `gpt-5.6-sol` | `high` |
| `review-track-spec` | `gpt-5.6-sol` | `high` |
| `review-track-standards` | `gpt-5.6-sol` | `medium` |
| `review-track-safety` | `gpt-5.6-sol` | `medium` |

这些固定档位同时用于 `initial` 和 `terminal-final`；`finding-closure` 不使用四个 track role，仍由独立 `luna-worker` 处理。

| 平台 | 链接类型 |
|------|----------|
| Windows | 目录 **junction**（`mklink /J`） |
| Linux / macOS / 其它 Unix | 目录 **symlink** |

支持宿主：

- `claude` → `~/.claude/skills`
- `codex` → `~/.codex/skills`
- `grok` → `~/.grok/skills`（可用 `GROK_HOME` 覆盖 grok 根）

## 调用方式

```bash
# 单个 skill → 一个或多个宿主
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --host claude codex grok

# 全部顶层 skills/*
python3 /path/to/agent-workbench/scripts/link_skill.py --all --host claude

# 自定义目标 skills 目录
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --to /path/to/skills

# 只拆整树 link、建真实目录，不装 skill
python3 /path/to/agent-workbench/scripts/link_skill.py --migrate-only --host claude

# 卸载宿主侧 link（不删除 workbench skills/ 源头）
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --unlink --host claude
python3 /path/to/agent-workbench/scripts/link_skill.py call-grok --uninstall --host claude grok
```

stdout 末行是 JSON summary（含 `platform`、`link_kind`、各 host 的 `linked|skipped|conflict`）。
`--json` 时只打印该对象（仍不混入其它噪音）。

退出码：`0` 成功/仅 skip；`2` 有 conflict；`1` 参数错误或拒绝操作。

## 安装粒度

| 来源 | 目标 | 机制 |
|------|------|------|
| `skills/<name>/` 或顶层 bundle 目录 | `<host>/skills/<name>` | Win junction / Unix symlink |
| `--all` | 每个**有效**顶层 `skills/*` 目录一项 | 同上 |

- **有效目标**：目录树内递归存在至少一个 `SKILL.md`（可在子目录；根目录可以没有）。无 `SKILL.md` 的空壳目录不链接、`--all` 会跳过。
- Bundle（如 `skills/lark-skills/`）按**顶层目录**链一次，内部子 skill 随目录暴露。
- 多公开 skill 套件应迁入 `plugin-marketplace/plugins/`；`impl-package` 不通过本表的 junction/symlink 暴露。
- **不**再把整个 `skills/` 挂成一个 junction。
- v1 **不**安装 `agents/`、`commands/`，不改项目 `.gitignore`。

## 整树迁移

若 `<host>/skills` 本身是指向**本 workbench `skills/` 根**的 junction/symlink：

1. 删除该 reparse/symlink 节点（不删 workbench 内容）
2. 创建真实目录
3. 再写入 per-skill link

若 link 指向**其它**路径：拒绝修改并报错。

## 冲突策略

非破坏：

- 目标不存在：创建 link
- 目标已是指向同一源的 link：`skipped`
- 目标存在且不同：`conflict`，不覆盖（无 `--force`）

## 独立 MCP 注册脚本

`discuss-ledger` MCP 仍用独立脚本，与 `link_skill.py` 无关：

```bash
bash /path/to/agent-workbench/scripts/install-discuss-ledger-mcp.sh /path/to/project codex claude
```

```powershell
powershell -ExecutionPolicy Bypass -File D:\path\to\agent-workbench\scripts\install-discuss-ledger-mcp.ps1 D:\path\to\project codex claude
```

## 维护要求

新增宿主时同步更新：

- `scripts/link_skill.py` 的 `HOST_NAMES` / `host_skills_dir`
- `tests/test_link_skill.py`
- `README.md`
- 本文件
