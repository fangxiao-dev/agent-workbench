# Improve-Skill Preference Loop Skill Plan

日期：2026-07-08
状态：已实现（2026-07-08，包含 skill、rubric 模板、轻量 eval、continuous-learning 退役）

## Goal

设计一个维护期 skill `improve-skill`，管理"优化偏好"的完整闭环：

1. **提案前（读）**：用户对某个被维护 skill 索要优化建议时，先读取该 skill 的 rubric（偏好档案），用已沉淀的偏好过滤、排序候选优化项。
2. **选择时（理解）**：用户挑选/舍弃优化项时，分析取舍背后的原因。
3. **写回（记）**：将推断出的偏好经用户口头确认后，写入对应 skill 的 rubric。

偏好随每轮优化累积、修正、收敛，使后续优化提案越来越贴合用户真实意图——有反馈的优化，而不是每次自由发挥。

## Non-Goals

- 不负责执行优化本身。用户挑选后的实际修改由当前会话（或 skill-creator 等）完成；improve-skill 只旁观决策、维护偏好档案。
- 不做"从会话孵化新 skill"（该职责属于已退役的 continuous-learning 的 hook 流水线，不迁移）。
- 不把 rubric 内容放进被维护 skill 的 SKILL.md 正文；rubric 是维护期文档，运行时不加载。
- 不急于归纳全局人格画像：偏好默认 skill 级，升全局有明确门槛（见下）。

## Proposed Skill

```text
skills/improve-skill/
  SKILL.md
  global-rubric.md              # 跨 skill 通用偏好（分层读取的全局层）
  assets/
    templates/
      rubric.md                 # per-skill rubric 模板
  evals/
    evals.json                  # 轻量 prompt eval
```

per-skill rubric 位置：`skills/<目标>/rubric.md`，不存在时按模板创建。

兜底规则：被维护对象不在本仓库（如 plugin cache 中的第三方 skill）时，rubric 放 `docs/rubrics/<slug>.md`，frontmatter 标注目标路径。此为例外路径，不影响主设计。

### Frontmatter（建议）

```yaml
---
name: improve-skill
description: 当用户对某个 skill 索要优化建议、在多个优化项之间做挑选/舍弃、或要求"分析我为什么这么选"时使用。本 skill 读取并维护每个被维护 skill 的 rubric 偏好档案（skills/<name>/rubric.md），在提案前用已确认偏好过滤候选项，在用户做出取舍后推断偏好、经口头确认写回 rubric，实现有反馈的持续优化。不负责执行优化修改本身。
---
```

## Rubric 结构

原则区 + 滚动证据区（决策记录），中文书写：

```markdown
---
target: skills/dev-with-track
updated: 2026-07-08
---
## 原则
- [已确认] 不接受为边缘 case 增加流程步骤的优化
- [待验证] 偏好删减章节而非新增（证据: R3）

## 决策记录（滚动，最近 ≤5 轮）
### R3 · 2026-07-08
- 采纳「合并 gate 模板重复段」— 用户原话：维护两份必然漂移
- 否决「增加回滚演练小节」— 推断：收益只覆盖罕见场景
```

`global-rubric.md` 同构，frontmatter 固定为 `target: global`。

### 运行规则（回收与升级，写入时静默顺手做）

- 新原则默认 `[待验证]`；被后续 2 轮选择印证 → 升级 `[已确认]`，并删除名下证据条目（原则即结论，不再需要论据）。
- 证据区只保留最近 5 轮决策记录；更早的要么已沉淀进原则，要么不构成稳定偏好，直接丢弃。
- skill 级原则与全局原则冲突时，skill 级优先。
- 偏好默认写 skill 级；仅当同样的推断在**第二个不同的 skill** 上再次得到用户确认时，才提升为全局。
- 证据区是"原则的试用期观察记录"，不是历史档案：转正即删材料，不转正连原则带材料一起清退。稳态大小有界。

## 两个工作流程

### 提案阶段（用户问"有什么可优化的点"）

1. 叠加读取 `global-rubric.md` + `skills/<目标>/rubric.md`。
2. 生成候选优化项。
3. 与 `[已确认]` 原则冲突的候选直接过滤，但用一句话报备被过滤的类别（防止原则记错后用户永远看不到某类建议）。
4. `[待验证]` 原则只用于排序与标注，不用于过滤。
5. 呈现候选时注明"此项符合/试探你的某偏好"。

### 记录阶段（用户挑选/舍弃后）

1. 分析取舍，推断偏好。
2. **写前口头确认**：用一两句话向用户复述推断（"我理解你否决 X 是因为……记为待验证原则，对吗？"），引导用户补充"为什么"——用户陈述的理由本身是最高质量的素材。
3. 用户确认或纠正后，判断适用范围（skill 级 / 满足升全局门槛）。
4. 写入 rubric，同时静默执行回收与升级规则。

机械性回收操作不需要确认；只有"推断出的偏好"需要写前确认。

## 退役 continuous-learning

- `skills/continuous-learning/` 整体移入 `skills-deprecated/`。
- 检查 `~/.claude/settings.json` 是否配置了其 Stop / UserPromptSubmit hook（`evaluate-session.sh`、`check-pending-before-task.sh`），有则摘除。
- 更新 `registry/third-party-skills.md` 中 continuous-learning 条目状态（标注已退役）。
- `skills-lock.json` 中无其条目，无需处理。

理由：其 hook 驱动的"会话→新 skill 孵化"流水线与用户实际工作方式（对话驱动、人在环挑选）不重合，pending 目录长期空置，保留只会造成触发词干扰。

## 已确认的设计决策记录

| 决策点 | 选择 |
| --- | --- |
| 闭环归属 | improve-skill 全包读写两侧 |
| rubric 内容 | 原则 + 滚动证据，带回收规则 |
| rubric 位置 | `skills/<name>/rubric.md`（安装为 symlink，仓库即唯一真源） |
| 写入纪律 | 推断写前口头确认；机械回收静默 |
| 通用偏好 | 全局 rubric 分层读取，第二 skill 确认才升全局 |
| continuous-learning | 移入 skills-deprecated/ |
| 命名 | `improve-skill`（不叫 learning） |
| rubric 语言 | 中文，与用户决策语言一致 |
