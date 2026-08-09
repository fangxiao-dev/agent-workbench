# 安装器规范

独立 skill 的主安装入口是 **`scripts/link_skill.py`**：把 workbench 里**单个（或全部顶层）skill 目录** link 到宿主的 `skills/<name>`。`plugin-marketplace/` 下的多-skill 套件使用宿主原生 marketplace/plugin 流程，不进入该脚本。

## Plugin 安装

独立发布根位于 `plugin-marketplace/`。其中 Codex marketplace 位于 `.agents/plugins/marketplace.json`，Claude marketplace 位于 `.claude-plugin/marketplace.json`；两者均以 `agent-workbench` 为 marketplace 名，并从 `./plugins/<plugin>` 读取同一份插件 payload。

```powershell
codex plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
codex plugin add impl-package@agent-workbench

claude plugin marketplace add D:\path\to\agent-workbench\plugin-marketplace
claude plugin install impl-package@agent-workbench --scope project
```

插件目录就是安装产物，不执行 build。安装和更新会进入宿主缓存；manifest/marketplace 版本必须同步，更新后开启新会话。Workbench 不包装这些命令，也不在验证时修改用户级宿主状态。

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
python3 /path/to/agent-workbench/scripts/link_skill.py verify-registry-state --unlink --host claude
python3 /path/to/agent-workbench/scripts/link_skill.py verify-registry-state --uninstall --host claude grok
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
