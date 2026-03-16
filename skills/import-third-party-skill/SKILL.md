---
name: import-third-party-skill
description: 搜索并推荐第三方 skill，安装后把默认落在 .agents / .claude 下的 skill 迁移到指定目录，并登记到 registry。
user-invocable: true
---

# import-third-party-skill

用于把第三方 skill 纳入当前仓库管理。

## 用途

当用户提供 skill 名称，并希望把它正式收录到当前仓库时，执行这个 workflow：

1. 先使用 `find-skills` 搜索并推荐候选 skill
2. 等用户确认具体 package
3. 安装该 skill
4. 把默认落在 `.agents` 或 `.claude/skills` 下的目录迁移到用户指定目录
5. 更新 `registry/third-party-skills.md`
6. 更新 `registry/skills.lock.json`
7. 运行 `verify-registry-state` 刷新状态

## 输入

- `skill name`：用户想找的能力或 skill 名称
- `target dir`：迁移后的目标目录，相对仓库根目录，例如 `skills`
- `package`：用户确认后的包标识，例如 `owner/repo@skill-name`

## 约束

- 搜索与推荐阶段必须使用 `find-skills`
- 不把 `.agents/`、仓库根 `.claude/` 之类的本机安装态目录提交到仓库
- 上游元数据统一写入 `registry/skills.lock.json`
- 人工清单统一写入 `registry/third-party-skills.md`

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/import-third-party-skill.ps1 `
  -SkillName "<skill-name>" `
  -Package "<owner/repo@skill-name>" `
  -TargetDir "skills"
```

## Linux / macOS

```bash
bash skills/import-third-party-skill/scripts/import-third-party-skill.sh \
  --skill-name "<skill-name>" \
  --package "<owner/repo@skill-name>" \
  --target-dir "skills"
```

## 预期结果

- 第三方 skill 被复制到指定目录下
- `registry/third-party-skills.md` 新增或更新对应条目
- `registry/skills.lock.json` 新增或更新上游元数据
- 可继续通过 `install.sh` 暴露给 `~/.claude/skills/`
