# Skills 规范

公开 skill 使用相同的 `SKILL.md` 合同，但按交付单位分为两类正式来源：独立 skill 位于 `skills/<name>/`，多-skill 套件位于 `plugin-marketplace/plugins/<plugin>/skills/<name>/`。

## 基本结构

最小结构：

```text
skills/
└── my-skill/
    └── SKILL.md
```

需要多个公开入口的成组能力使用 plugin 结构：

```text
plugin-marketplace/plugins/my-plugin/
├── .codex-plugin/plugin.json
├── .claude-plugin/plugin.json
└── skills/
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

同一 plugin 的多个 skill 确实共享脚本时，放在 plugin 根 `scripts/`，并从当前已加载插件根解析路径；不要依赖 workbench 源路径或宿主缓存位置。独立 skill 默认不把脚本提前抽到仓库顶层。

## 安装行为

`link_skill.py` 把 `workbench/skills` 下的独立 skill 暴露到已选宿主的 `skills/`：

- Windows PowerShell 使用 junction。
- Bash/Unix 使用符号链接。
- 遇到已有不同目标时跳过并报告冲突，不删除、不覆盖。

新增或修改 `skills/<name>/` 后，链接型宿主通常会立即看到变化。单公开入口的 router 可以保留内部 `SUB-SKILL.md`；多个公开入口应组成 plugin，不依赖 junction/symlink 的递归发现。

Plugin 通过 `plugin-marketplace/` 内的 Codex/Claude marketplace 和宿主原生 install 命令安装。安装会复制到宿主缓存，更新 manifest/marketplace 版本后需要重新安装并开启新会话。

## 第三方 Skills

独立第三方 skill 进入 `skills/`；plugin-owned 第三方 skill 进入 `plugin-marketplace/plugins/<plugin>/skills/`。`registry/third-party-skills.md` 只记录哪些 skill 是第三方、来自哪里、如何重新获取。

修改第三方 skill 时：

1. 修改 `skills/<name>/` 或 `plugin-marketplace/plugins/<plugin>/skills/<name>/` 中的正式副本。
2. 保留 `registry/third-party-skills.md` 中的来源信息。
3. 未来需要更新时，用 `npx skills` 拉取上游新版本到临时位置。
4. 人工对比临时副本和对应正式路径，确认后再更新正式副本。

`.agents/`、仓库根 `.claude/` 和根目录 `skills-lock.json` 都不是第三方 skill 的仓库内规范源。
