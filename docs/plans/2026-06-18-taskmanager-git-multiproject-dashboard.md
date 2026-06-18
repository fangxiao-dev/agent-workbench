# TaskManager Git 化与多项目 Dashboard 改造计划

## Summary

- `D:\CodeSpace\TaskManager` 升级为独立 Git 仓，作为跨项目任务中控仓；项目 repo 继续只管源码和正式文档。
- 项目 ID 改为 `00_Config/projects.yml` 中的显式稳定 ID：本次使用 `prj-supplyer-webapp` 和 `bills_analysis`。
- 任务文件不再把绝对路径作为 source of truth；任务保存 `项目ID` + `来源类型` + `来源相对路径`，项目本机根路径只存在 ignored 的本地配置。
- Dashboard 展示用 `项目名称`，由脚本从 `00_Config/projects.yml` 的 `name` 同步；`项目ID` 与 `项目` 保持为机器校验字段。
- 仍采用“一级按功能、二级按项目、三级按材料类型”；所有初始化、迁移、Base 生成、导入动作都通过模板和脚本完成。
- 根 `Task Dashboard.md` 保留为兼容入口，旧 `30_Bases/任务面板.base` 迁移为 `30_Bases/global-tasks.base`。

## Key Changes

- 扩展 `task_manager.py`：
  - `init-vault-repo --vault [--apply]`：初始化 Git 仓、生成 `.gitignore`、检查建议 track/ignore 清单。
  - `baseline-commit --vault [--message "chore: baseline taskmanager vault"] [--apply]`：在迁移前提交原始 vault 快照，作为可 diff、可 revert 的安全网。
  - `write-design --vault --input <json> [--apply]`：把本次多项目设计写入 `20_Sources/_design/`，不创建任务、不从 Dashboard/README 链接。
  - `init-project --vault --project <id> --repo <path> --name <name> --source-root docs/impl-plans [--apply]`：写 tracked `projects.yml` 元数据和 ignored `projects.local.yml` 本机 root，创建项目目录，生成项目 Base 和 Dashboard。
  - `import-impl-plans --vault --project <id> --limit 5 --default-status 计划中 [--apply]`：按 `projects.local.yml` 的 root + `projects.yml` 的 sourceRoot 找 impl plan，非递归导入 source root 直接子文件。
  - `validate --vault [--project <id>]`：递归扫描 `10_Tasks/**/*.md`，校验项目字段、相对来源、枚举和完成态规则。
  - `refresh-project-metadata --vault [--project <id>] [--apply]`：从 `projects.yml` 同步现有项目任务的 `项目名称`，不改任务正文。
  - `refresh-bases --vault [--project <id>] [--apply]`：从模板重建 Global Base 和项目 Base，避免手工维护视图 YAML。
  - `refresh-dashboards --vault [--project <id>] [--apply]`：从模板重建 Dashboard Markdown，项目 Dashboard 显式嵌入 `#进行中` 和 `#已完成` 两个 Base view。
- 新增/调整模板：
  - `.gitignore` 模板：track dashboard 必需资源，ignore 缓存、移动端 workspace、插件本地状态。
  - `projects.yml` 模板：保存项目 ID、显示名、sourceRoot、task/source/base/dashboard 路径，不保存本机绝对 root。
  - `projects.local.yml` 模板：保存本机绝对 root，加入 `.gitignore`，clone 后由 `init-project` 或专门的 local-config 命令生成。
  - `task-note.md`：增加 `项目ID`、`项目`、`项目名称`、`来源相对路径`、`来源类型`；保留旧 `来源` 作为可选派生显示字段或迁移兼容字段。
  - `task-base.base`：复用现有 `任务面板.base` 的视图格式、排序、颜色和 view 名称；Global Base 显示 `项目名称` 为“项目”，项目 Base 隐藏 `项目` 和 `来源相对路径`，但展示 `来源类型`。
  - `project-dashboard.md`：Dashboard 文件名和标题带项目区分，显式嵌入 `![[30_Bases/<project-id>.base#进行中]]` 和 `![[30_Bases/<project-id>.base#已完成]]`，避免 Obsidian 默认只显示第一个 Base view。
- 迁移现有入口：
  - `30_Bases/任务面板.base` 重命名/迁移为 `30_Bases/global-tasks.base`，并把所有顶层任务过滤从 `file.folder == "10_Tasks"` 改为 `file.inFolder("10_Tasks")`。
  - 根 `Task Dashboard.md` 改为兼容入口，嵌入或链接 `40_Dashboards/Global Dashboard.md`，不再直接指向旧 base 文件。
  - 更新 `README.md`，说明多项目结构、Git track/ignore 策略、`projects.local.yml` 本机配置和 source 解析限制。
- Vault 目标结构：
  - `00_Config/projects.yml`
  - `10_Tasks/prj-supplyer-webapp/`
  - `10_Tasks/bills_analysis/`
  - `20_Sources/prj-supplyer-webapp/{discussions,specs,references,handoffs}/`
  - `20_Sources/bills_analysis/{discussions,specs,references,handoffs}/`
  - `20_Sources/_design/`
  - `30_Bases/global-tasks.base`
  - `30_Bases/prj-supplyer-webapp.base`
  - `30_Bases/bills_analysis.base`
  - `40_Dashboards/Global Dashboard.md`
  - `40_Dashboards/prj-supplyer-webapp Dashboard.md`
  - `40_Dashboards/bills_analysis Dashboard.md`
  - `40_Reports/.gitkeep`
- Git track 默认清单：
  - `00_Config/`, `10_Tasks/`, `20_Sources/`, `30_Bases/`, `40_Dashboards/`, `40_Reports/`, `90_Archive/`, `Templates/`, `README.md`, `Task Dashboard.md`
  - `.obsidian/community-plugins.json`, `.obsidian/core-plugins.json`, `.obsidian/templates.json`, `.obsidian/types.json`, `.obsidian/app.json`, `.obsidian/appearance.json`
  - `.obsidian/snippets/`
  - `.obsidian/plugins/good-bases/`, `.obsidian/plugins/tray/` 的插件代码、manifest 和样式文件
- Git ignore 默认清单：
  - `.obsidian/workspace-mobile.json`, `.obsidian/cache/`, `.obsidian/logs/`, `.trash/`
  - `.obsidian/plugins/*/data.json`
  - `.obsidian/workspace.json`, `.obsidian/hotkeys.json`
  - `00_Config/projects.local.yml`

## Implementation Details

- tracked `projects.yml` 首批内容：
  - `prj-supplyer-webapp`: name `Supplyer Webapp`, sourceRoot `docs/impl-plans`
  - `bills_analysis`: name `Bills Analysis`, sourceRoot `docs/impl-plans`
- ignored `projects.local.yml` 首批内容：
  - `prj-supplyer-webapp`: root `D:/CodeSpace/prj-supplyer-webapp`
  - `bills_analysis`: root `D:/CodeSpace/prj_rechnung/dev`
- 任务 frontmatter 标准：
  - `项目ID` 是 scalar，给脚本解析。
  - `项目` 是 YAML list，作为 Bases 分组/着色字段；模板必须写成单值 list。
  - `项目名称` 是 scalar，作为 Global Dashboard 的展示列；脚本从 `projects.yml` 的 `name` 生成和刷新，不作为项目身份 source of truth。
  - 目录名是规范项目身份；`validate` 强制 `10_Tasks/<project-id>/`、`项目ID`、`项目[0]` 三者一致，且 `项目` 只能有一个值。
  - `来源类型` 表示 source 命名空间：`impl-plan`、`source-note`、`discussion`、`handoff`。
  - `来源相对路径` 的解释依赖 `来源类型`：`impl-plan` 相对项目 repo root；`source-note`、`discussion`、`handoff` 相对 vault root，通常落在 `20_Sources/<project-id>/...`。
  - `来源` 可保留为派生显示/迁移兼容字段，但脚本解析优先使用 `项目ID + 来源类型 + 来源相对路径`。
- Base 过滤：
  - 全局：`file.ext == "md"` + `file.inFolder("10_Tasks")`
  - 项目：只用 `file.ext == "md"` + `file.inFolder("10_Tasks/<project-id>")`
  - `项目` 字段不作为项目 Base 的 AND 过滤条件；字段与目录不一致时由 `validate` 报错，避免 Base 静默隐藏任务。
  - Global Base 使用 `项目名称` 显示“项目”；项目 Base 不显示 `项目` 和 `来源相对路径`，因为目录已经提供项目隔离，来源追踪仍保留在 frontmatter。
- 当前 `prj-supplyer-webapp` 迁移：
  - 现有 `10_Tasks/*.md` 移入 `10_Tasks/prj-supplyer-webapp/`。
  - 现有正式 source note 归入 `20_Sources/prj-supplyer-webapp/discussions/`；本次设计归入 `20_Sources/_design/`。
  - 指向 `D:/CodeSpace/prj-supplyer-webapp/...` 的旧绝对 `来源` 迁移为 `来源类型=impl-plan` + repo-relative `来源相对路径`。
  - 指向 `D:/CodeSpace/TaskManager/20_Sources/...` 的旧绝对 `来源` 在移动 source note 后迁移为 `来源类型=source-note` 或 `discussion` + vault-relative `来源相对路径`。
  - 无法相对化的路径保留为兼容显示字段并在 validate 中提示。
- Obsidian 类型配置：
  - 更新 `.obsidian/types.json`，把 `项目ID`、`项目名称`、`来源相对路径` 注册为 text，把 `项目`、`来源类型` 注册为 multitext。
- `bills_analysis` 导入最近 5 个非 README impl plan：
  - `2026-06-16-production-durable-runtime-migration.md`
  - `2026-06-15-demo-manager-cash-seed-card.md`
  - `2026-06-15-production-durable-cutover.md`
  - `2026-06-15-filiale-misc-pdf-backup.md`
  - `2026-06-14-worker-observability-timeouts-smoke.md`
  - 默认 `状态=计划中`、`验证链路=不涉及`、`工作区=主工作区`。
  - 导入规则必须非递归：只读取 `<project-root>/<sourceRoot>/*.md`，排除 `README.md`，不进入 `archive/` 或其他子目录，按 `LastWriteTime` 降序取前 N。

## Test Plan

- 临时 vault 单元/集成测试：
  - `init-vault-repo` dry-run 不写文件，apply 后创建 `.gitignore` 并初始化 Git。
  - `baseline-commit` 在迁移前能提交当前 vault 快照；迁移后可以通过 git diff 看到目录移动、frontmatter 改写和 Base/Dashboard 变化。
  - `init-project` 生成目录、tracked `projects.yml`、ignored `projects.local.yml`、Base、Dashboard，重复运行幂等。
  - `upsert/import` 写入 `10_Tasks/<project-id>/`，不同项目允许同名任务。
  - `import-impl-plans --limit 5` 排除 `README.md`，不进入 `archive/`，只导入 source root 直接文件中的 5 个最近 Markdown。
  - `validate` 能递归校验目录、`项目ID`、`项目` 一致性，来源类型命名空间、来源相对路径、枚举和完成态优先级清理。
  - `git check-ignore 00_Config/projects.local.yml` 确认本机 root 配置确实被 ignore。
- 真实 vault 执行顺序：
  - dry-run `init-vault-repo`，确认 track/ignore 清单。
  - apply `init-vault-repo` 后先创建 baseline commit：`chore: baseline taskmanager vault`。
  - dry-run 写设计参考。
  - dry-run 初始化并迁移 `prj-supplyer-webapp`。
  - apply 后运行 `validate --project prj-supplyer-webapp`。
  - dry-run 初始化 `bills_analysis` 并导入最近 5 个 impl plan。
  - apply 后运行 `validate --project bills_analysis` 和全局 `validate`。
  - 用 `git status --short` 检查 TaskManager 仓只出现预期文件。

## Assumptions

- `TaskManager` 会作为独立 Git 仓初始化；迁移前 baseline commit 是前置安全网，迁移完成后的最终 commit 可由用户决定是否立即创建。
- 项目 ID 不再由远端名或本地目录名自动决定；以 `projects.yml` 显式配置为准。
- 任务与 source 通过 `项目ID + 来源类型 + 来源相对路径` 连接，不通过绝对路径连接。
- `来源类型=impl-plan` 是脚本解析的跨仓库符号引用，不是 Obsidian 内链；clone 后必须先生成本机 `00_Config/projects.local.yml`，否则只能看到 source 标识，不能解析到本机文件。
- Obsidian UI 工作区 tab 状态默认不 track，避免机器状态污染仓库；dashboard 还原必需的 app/appearance/snippets/types/plugin 配置会 track。
