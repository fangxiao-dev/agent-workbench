# Skills 规范

每个 skill 是 `skills/` 下含有 `SKILL.md` 的独立目录。`skills/` 是仓库内唯一正式来源；自建 skill 和第三方 skill 都使用同一结构。

## 基本结构

最小结构：

```text
skills/
└── my-skill/
    └── SKILL.md
```

成组能力可以使用 bundle 结构：

```text
skills/
└── my-bundle/
    └── my-skill/
        └── SKILL.md
```

按需扩展：

```text
skills/
└── my-skill/
    ├── SKILL.md
    ├── scripts/
    │   └── do-something.ps1
    ├── references/
    ├── rules/
    ├── templates/
    └── assets/
```

## `SKILL.md`

`SKILL.md` 必须以 YAML frontmatter 开头：

```markdown
---
name: skill-name
description: >
  一句话说清楚这个 skill 做什么，以及何时使用它。
---

# skill-name

具体指令、流程、参考资料。
```

`description` 要写触发场景，而不只是功能描述：

- 差：`Helps with code quality.`
- 好：`审查代码质量和结构。当用户要求 code review、检查代码规范、或提交前审查时使用。`

## 脚本放置

skill 专属脚本放在该 skill 自己的 `scripts/` 目录内。安装后路径随 skill 一起稳定暴露，不需要顶层脚本目录参与。

只有在多个 skill 确实需要共享同一个脚本时，才考虑单独设计共享位置；默认不要把脚本提前抽到仓库顶层。

## 安装行为

安装器把 `workbench/skills` 暴露到已选宿主的 `skills/`：

- Windows PowerShell 使用 junction。
- Bash/Unix 使用符号链接。
- 遇到已有不同目标时跳过并报告冲突，不删除、不覆盖。

因为 `skills/` 是共享来源，新增或修改 `skills/<name>/` 或 `skills/<bundle>/<name>/` 后，链接型宿主通常会立即看到变化。仓库辅助脚本按 `SKILL.md` 递归识别 bundle 内的 skill；没有 `SKILL.md` 的 bundle 根目录不视为 skill。

## 第三方 Skills

第三方 skill 也直接进入 `skills/`。`registry/third-party-skills.md` 只记录哪些 skill 是第三方、来自哪里、如何重新获取。

修改第三方 skill 时：

1. 修改 `skills/<name>/` 或 `skills/<bundle>/<name>/` 中的正式副本。
2. 保留 `registry/third-party-skills.md` 中的来源信息。
3. 未来需要更新时，用 `npx skills` 拉取上游新版本到临时位置。
4. 人工对比临时副本和 `skills/<name>/`，确认后再更新正式副本。

`.agents/`、仓库根 `.claude/` 和根目录 `skills-lock.json` 都不是第三方 skill 的仓库内规范源。
