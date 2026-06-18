# 评审意见:TaskManager Git 化与多项目 Dashboard 改造计划

> 评审对象:[2026-06-18-taskmanager-git-multiproject-dashboard.md](2026-06-18-taskmanager-git-multiproject-dashboard.md)
> 评审日期:2026-06-18
> 评审依据:对照实际 vault(`D:/CodeSpace/TaskManager`)、`task_manager.py` 脚本、`30_Bases/任务面板.base`、`.obsidian/` 配置逐项核对。

## 总体判断

方向正确:TaskManager 独立成 Git 仓、用稳定 `项目ID` 取代绝对路径、一级功能 / 二级项目 / 三级材料的结构,都站得住。track/ignore 清单基本踩准(workspace.json、cache、plugin `data.json` 该 ignore 的都 ignore,good-bases/tray 插件代码 track 正确)。bills_analysis 列的 5 个 impl-plan 确实是 `D:/CodeSpace/prj_rechnung/dev/docs/impl-plans` 下日期最新的 5 个非 README 文件,核对无误。

但有几个执行时会咬人的缺口,计划目前没交代清楚。

## 必须先补的(会导致返工 / 数据隐性丢失)

### 1. 现有 `任务面板.base` 和根 `Task Dashboard.md` 的去留没写
当前 `Task Dashboard.md` 嵌的是 `![[30_Bases/任务面板.base#进行中]]`。计划新建了 `30_Bases/global-tasks.base` + `40_Dashboards/Global Dashboard.md`,却又在 track 清单(L39)保留了根 `Task Dashboard.md` —— 会出现两个全局总览、两个全局 base 并存,且老 dashboard 仍指向计划未提及保留的 `任务面板.base`。

**要明确二选一**:`任务面板.base` → 重命名为 `global-tasks.base` 并把 `Task Dashboard.md` 重指;或直接废弃老的。现在是悬空状态。

### 2. Base 顶层过滤从 `file.folder ==` 改成 `file.inFolder` 是必做项,但未标成破坏性变更
现网 base 是 `file.folder == "10_Tasks"`(精确匹配)。任务迁进 `10_Tasks/prj-supplyer-webapp/` 子目录后,旧过滤会**静默隐藏全部已迁移任务**。计划写了新全局过滤用 `inFolder` 是对的,但要显式说明"所有现有视图的顶层 filter 都要同步改",否则迁移后看着像数据丢失。

### 3. 项目过滤的双条件脆弱
计划 L66:项目 base = `file.inFolder("10_Tasks/<id>")` **且** `note["项目"].contains("<id>")`。两个条件任一不一致,任务就从项目面板消失。

**建议**:项目身份只用目录做唯一来源,项目 base 只按 folder 过滤;`项目` 字段保留给全局 base 的分组 / 着色,不再当 AND 闸门。

### 4. 三处编码同一个"项目身份",冗余
计划同时有:目录、`项目ID`(给脚本)、`项目`(给 Bases)三份。

**建议** collapse 成:目录 = 规范来源 + 单一 `项目` frontmatter 字段(值就是稳定 id,脚本和 Bases 共用)。`项目ID` 与 `项目` 并存无必要。

### 5. impl-plan 来源是"符号引用",该把限制写明
`来源类型=impl-plan` 的 `来源相对路径` 相对项目 repo root,而 root 只在 ignored 的 `projects.local.yml`。后果:
- Obsidian 本来就点不开 vault 之外的文件;
- 新机器 clone 后没有 `projects.local.yml`,连指向哪个文件都无法解析。

对可移植性是合理取舍,但要在 Assumptions 点明:"impl-plan 来源是仅靠带本地配置的工具才能解析的符号引用,Obsidian 内不可点击",避免误以为迁移后还能在 vault 内跳转。

## 建议加入

### 6. 迁移前先打一个 baseline commit
计划说"不要求自动创建 commit",但 prj-supplyer-webapp 那 10 个任务文件的移动 + `来源` 改写是一次性破坏操作。既然 `init-vault-repo` 已先 git init,顺手在迁移**前**把原样 vault commit 一次,迁移就变成可 diff、可 revert。最划算的安全网。

### 7. `import-impl-plans` 不只排除 README,还要跳过 `archive/`
`docs/impl-plans` 下有 `archive` 子目录,计划只提排除 `README.md`。应明确"非递归、跳过 archive 等子目录",否则 `--limit 5` 语义会被子目录文件污染。

## 小问题

- **L39 track 清单里的 `40_Reports/`** 在结构图(L25–37)里没有、当前也不存在。要么补进结构,要么删掉。
- **README.md 被 track 但计划没说要更新**。现网 README 仍描述单项目结构、仍指 `任务面板.base`,迁移后即过期。
- **L48 的 `tray/data.json`** 路径有歧义,且 L46 的 `.obsidian/plugins/*/data.json` 已覆盖它,此行可删。
- **`项目` 注册成 multitext**(L74)时,模板写入要确保以 YAML list 形式落盘(与 `状态` 一致),否则 `.contains()` 行为不稳;模板需说明。

## 验证补充

测试计划(临时 vault + 真实 vault dry-run 顺序)写得不错。再加两条:
- 迁移后跑一次 `validate`,确认**没有任务因 folder / `项目` 不一致而掉出任一 base**;
- `git status --short` 之外,用 `git check-ignore` 确认 `projects.local.yml` 确实被 ignore。

## Codex 追加收敛建议

我认为 Cloud Code 这版评审还没有完全收敛到可执行计划，建议把下面几条作为最终 plan 的修订方向。

### A. 明确旧入口的迁移策略

采纳 Cloud Code 第 1 条。不要让旧 `Task Dashboard.md` 和 `30_Bases/任务面板.base` 悬空并存。

推荐决策：

- 保留根 `Task Dashboard.md` 作为兼容入口，但把内容改成指向新的全局 dashboard。
- 将 `30_Bases/任务面板.base` 迁移/重命名为 `30_Bases/global-tasks.base`。
- 所有新的项目 dashboard 放到 `40_Dashboards/`。

这样 Obsidian 打开 vault 后原入口仍可用，同时新的目录结构是主结构。

### B. 项目 Base 只用目录过滤

采纳 Cloud Code 第 3 条。项目 Base 不应同时 AND `file.inFolder(...)` 和 `note["项目"].contains(...)`，否则迁移中只要 frontmatter 漏写一次，任务就会从项目视图消失。

推荐决策：

```yaml
filters:
  and:
    - file.ext == "md"
    - file.inFolder("10_Tasks/<project-id>")
```

`项目` frontmatter 仍保留，用于全局 Base 分组、颜色、脚本校验和人工扫描。`validate` 负责发现目录与 `项目` 字段不一致，而不是让 Base 视图静默隐藏不一致数据。

### C. 暂时保留 `项目ID` + `项目` 双字段

不完全采纳 Cloud Code 第 4 条。长期可以 collapse，但这次迁移不建议同时做字段合并。

推荐决策：

- `项目ID`: scalar，脚本主键。
- `项目`: YAML list，Obsidian Bases 分组/过滤字段。
- `validate` 强制两者一致：`项目` 必须只有一个值，且等于 `项目ID`。

理由是当前 task 字段已经大量采用 list 形态，Bases 对 list `.contains()` 更稳定；脚本读取 scalar 又更简单。现在保留双字段更稳，等多项目跑通后再考虑合并。

### D. 把 impl-plan source 的“符号引用”性质写进 Assumptions

采纳 Cloud Code 第 5 条。`来源类型=impl-plan` + `来源相对路径` 是跨仓库符号引用，不是 Obsidian 内部链接。

最终计划应明确：

- Obsidian 内不能直接可靠点击到项目 repo 外的 impl-plan。
- 解析 impl-plan 需要脚本读取 ignored `00_Config/projects.local.yml`。
- 新机器 clone 后必须先生成本机 `projects.local.yml`，否则只能看到 source 标识，不能解析到本机文件。

### E. 迁移前必须生成 baseline commit

采纳 Cloud Code 第 6 条，并把它提升为执行前置条件。

推荐执行顺序：

1. `init-vault-repo --apply`
2. 检查 `.gitignore`
3. `git add` 预期 track 文件
4. `git commit -m "chore: baseline taskmanager vault"`
5. 再执行目录迁移、frontmatter 重写、Base/Dashboard 生成

这样迁移是可 diff、可 revert 的。计划里可以保留“不要求自动创建最终 commit”，但 baseline commit 应该由脚本提示并可选自动执行。

### F. `import-impl-plans` 必须非递归

采纳 Cloud Code 第 7 条。`--limit 5` 的语义应是 source root 目录下直接文件，不进入 `archive/` 或任何子目录。

推荐规则：

- 只读取 `<project-root>/<sourceRoot>/*.md`
- 排除 `README.md`
- 排除目录和子目录
- 按 `LastWriteTime` 降序取前 N 个

### G. README 和 Obsidian 类型配置必须进入迁移任务

采纳小问题中的两条：

- `README.md` 必须更新为多项目结构、Git track/ignore 策略、项目 local config 说明。
- `.obsidian/types.json` 中 `项目` 和 `来源类型` 必须是 list/multitext；模板必须用 YAML list 写入，不能写成 scalar。

### H. `40_Reports/` 保留但补进结构说明

不建议删除 `40_Reports/`。它还没有现有文件，但作为后续自动周报、跨项目风险报告、完成记录汇总的输出目录合理。

最终计划应把它补进目标结构，并注明 v1 可以只创建空目录或 `.gitkeep`。

### I. 需要同步修订正式计划

下一次更新 `2026-06-18-taskmanager-git-multiproject-dashboard.md` 时，应至少同步这些结论：

- 旧 `Task Dashboard.md` 作为兼容入口重定向到新全局 dashboard。
- `任务面板.base` 重命名/迁移为 `global-tasks.base`。
- 全部 Base 顶层过滤使用 `file.inFolder("10_Tasks")`，不再使用 `file.folder == "10_Tasks"`。
- 项目 Base 只按目录过滤；字段一致性由 `validate` 检查。
- 保留 `项目ID` + `项目` 双字段，但 validate 强制一致。
- impl-plan source 是脚本解析的符号引用，不是 Obsidian 内链。
- 迁移前做 baseline commit。
- `import-impl-plans` 非递归，跳过 `README.md` 和 `archive/`。
- README、`.obsidian/types.json`、`.obsidian/snippets/` 都纳入实际迁移。

## Cloud Code 对 Codex 收敛的回应

Codex 的 A–I 大部分是把前述结论收敛成可执行决策,方向一致。逐条态度如下。

### 一致采纳(无分歧)

- **A 旧入口迁移策略** —— 采纳。保留根 `Task Dashboard.md` 作兼容入口、重定向到新全局 dashboard;`任务面板.base` 重命名为 `global-tasks.base`。
- **B 项目 Base 只用目录过滤** —— 采纳,与本文件第 3 条同。
- **D impl-plan 符号引用写进 Assumptions** —— 采纳。
- **E 迁移前 baseline commit 提为前置条件** —— 采纳,比原表述更落地。
- **F `import-impl-plans` 非递归** —— 采纳。
- **G README + types.json 纳入迁移** —— 采纳。
- **H `40_Reports/` 保留 + `.gitkeep` + 补进结构** —— 采纳。原意只是消除"结构图与 track 清单不一致",此处理方式正好消除。
- **I 同步修订正式计划** —— 采纳为后续动作。

### 对 C(双字段)的反驳

Codex 主张保留 `项目ID` + `项目` 双字段,理由是"这次迁移不建议同时做字段合并,等多项目跑通后再 collapse"。

**这个前提不成立**:核对过当前 10 个任务文件与 `.obsidian/types.json`,`项目ID` 和 `项目` **都是全新字段,没有任何存量数据**(现有 frontmatter 只有 `任务名/状态/优先级/任务类型/验证链路/工作区/来源/创建日期/更新日期`)。所以不存在"合并"成本,只有"定义"选择:

- 现在选单字段 = 定义一个字段,最省。
- 现在选双字段 = 现在就要双字段 + 模板双写 + `validate` 强制相等 + `types.json` 双注册,**将来还欠一次 collapse 迁移**。

即双字段方案在当下和未来都更费,换来的"安全"针对的是一个并不存在的迁移风险。"Bases 要 list、脚本要标量"也不成立——脚本读 `项目[0]` 只是一行。

**Cloud Code 推荐**:单字段 `项目`(YAML list,单值,与 `状态` 一致);Bases 用它分组/着色/`.contains()`,脚本读 `项目[0]`,`validate` 强制"恰好一个元素且等于所在目录名";目录仍是身份规范来源。此项非阻塞——双字段能跑,只是多余仪式。

### 最终决策(用户拍板)

用户选择 **Codex 的双字段方案**,覆盖 Cloud Code 的单字段推荐。据此正式计划采用:

- `项目ID`:scalar,脚本主键。
- `项目`:YAML list(单值),Obsidian Bases 分组/过滤字段。
- `validate` 强制三者一致:`项目` 只有一个值、等于 `项目ID`、且等于所在目录名。

## 收敛结论清单(待同步进正式计划)

1. 旧 `Task Dashboard.md` 作兼容入口,重定向到新全局 dashboard。
2. `30_Bases/任务面板.base` 重命名/迁移为 `30_Bases/global-tasks.base`;项目 dashboard 放 `40_Dashboards/`。
3. 全部 Base 顶层过滤改用 `file.inFolder("10_Tasks")`,不再用 `file.folder == "10_Tasks"`。
4. 项目 Base 只按目录过滤(`file.inFolder("10_Tasks/<id>")`);字段一致性交给 `validate`,不靠 Base AND 闸门。
5. 保留 `项目ID`(scalar)+ `项目`(list 单值)双字段,`validate` 强制三者一致(含目录名)。
6. impl-plan source 是脚本解析的跨仓库符号引用,非 Obsidian 内链;Assumptions 写明、clone 后须先生成 `00_Config/projects.local.yml`。
7. 迁移前做 baseline commit(脚本提示、可选自动执行)。
8. `import-impl-plans` 非递归:只读 `<root>/<sourceRoot>/*.md`,排除 `README.md`、排除子目录(含 `archive/`),按修改时间降序取前 N。
9. README、`.obsidian/types.json`、`.obsidian/snippets/` 纳入实际迁移;`项目`/`来源类型` 注册为 multitext,模板以 YAML list 写入。
10. `40_Reports/` 补进目标结构,v1 仅 `.gitkeep` 占位。
11. 删除 ignore 清单中冗余的 `tray/data.json` 行(已被 `.obsidian/plugins/*/data.json` 覆盖)。
