# Skills 规范

## 基本结构

每个 skill 是 `skills/` 下的一个目录，最简结构：

```
skills/
└── my-skill/
    └── SKILL.md          ← 必须，且必须是这个文件名
```

扩展结构（按需添加）：

```
skills/
└── my-skill/
    ├── SKILL.md
    ├── scripts/           ← 该 skill 专属的可执行脚本
    │   └── do-something.sh
    └── reference.md       ← 补充参考文档（SKILL.md 里用 @ 引用）
```

---

## SKILL.md 格式

每个 SKILL.md 必须以 YAML frontmatter 开头：

```markdown
---
name: skill-name              ← 用于 /skill-name 触发，kebab-case
description: >
  一句话说清楚这个 skill 做什么，以及"何时"使用它。
  Claude 靠这段描述决定是否自动加载，要写得足够具体。
---

## 正文内容

具体的指令、流程、参考资料。
```

### description 写法要点

- 说明**触发场景**，不只是功能描述
- 包含用户可能说的关键词

❌ 差：`Helps with code quality.`

✅ 好：`审查代码质量和结构。当用户要求 code review、检查代码规范、或提交前审查时使用。`

---

## 共用脚本

如果多个 skills 需要共用脚本，放在顶层 `scripts/` 目录下，不要在每个 skill 里重复。

skill 内部引用时使用相对于仓库根目录的路径，并在 SKILL.md 里注明依赖关系：

```markdown
## 依赖
- 需要 `scripts/utils.sh`（由 install.sh 安装到 ~/.claude/scripts/）
```

---

## 安装行为

`install.sh` 执行时，`skills/` 下所有 skill 目录会被复制到 `~/.claude/skills/`（全局），在所有项目里均可使用。

自定义 skills 不安装到目标项目的 `.claude/skills/`，原因：这些是个人通用能力，不与具体项目耦合。

---

## 现有 skill 内容的迁移原则

如果当前仓库里已有 skill 相关内容（无论目录名或结构如何），迁移时：

1. 保留所有现有内容
2. 调整目录名为 kebab-case 风格
3. 如果已有类似 SKILL.md 的文件但 frontmatter 不规范，补全 frontmatter，不修改正文
4. 如果 frontmatter 里没有 `name`，根据目录名推断补全
