---
name: import-third-party-skill
description: 搜索并推荐第三方 skill，先审查 GitHub 内容，再安装或复制到仓库 skills/ 或显式 bundle 并登记到 registry/third-party-skills.md。
user-invocable: true
---

# import-third-party-skill

用于把第三方 skill 纳入当前 workbench。

## 用途

当用户提供 skill 名称，并希望把它正式纳管时，执行这个 workflow：

1. 先使用 `find-skills` 搜索并推荐候选 skill
2. 等用户确认具体 package
3. 访问 GitHub 审查上游内容，先看 `SKILL.md` 与关键目录摘要
4. 用户确认后，默认安装或复制到仓库 `skills/<name>/`；同一上游的成组能力可显式指定 `skills/<bundle>/<name>/`
5. 更新 `registry/third-party-skills.md`
6. 若同名 skill 已存在，则跳过并输出对比摘要，交给用户决策

## 输入

- `skill name`：用户想找的能力或 skill 名称
- `package`：用户确认后的包标识，例如 `owner/repo@skill-name`
- `mode`：`install` 或 `vendor`，默认 `install`
- `target dir`：默认 `skills`；成组能力可显式设为 `skills/<bundle>`

## 约束

- 搜索与推荐阶段必须使用 `find-skills`
- 不把 `.agents/`、仓库根 `.claude/` 之类的本机安装态目录提交到仓库
- 第三方 skill 的正式内容默认放在 `skills/<name>/`；同一上游的成组能力可放在 `skills/<bundle>/<name>/`
- 人工清单统一写入 `registry/third-party-skills.md`
- 不再维护旧的 skills lock JSON
- 默认不覆盖同名 skill；先比较再由用户决定
- 默认先审查，不在未确认前安装

## Windows

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/import-third-party-skill.ps1 `
  -SkillName "<skill-name>" `
  -Package "<owner/repo@skill-name>" `
  -Mode install
```

审查通过后再继续：

```powershell
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/import-third-party-skill.ps1 `
  -SkillName "<skill-name>" `
  -Package "<owner/repo@skill-name>" `
  -TargetDir "skills/<bundle>" `
  -Mode install `
  -Approve
```

## Linux / macOS

```bash
bash skills/import-third-party-skill/scripts/import-third-party-skill.sh \
  --skill-name "<skill-name>" \
  --package "<owner/repo@skill-name>" \
  --approve
```

## 预期结果

- 第三方 skill 位于默认的 `skills/<name>/`，或显式指定的 `skills/<bundle>/<name>/`
- `registry/third-party-skills.md` 记录 skill 名称、来源、获取方式和备注
- 如发现同名冲突：输出元数据与文件摘要，不自动覆盖
