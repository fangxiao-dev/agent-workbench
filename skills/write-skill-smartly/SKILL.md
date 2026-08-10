---
name: write-skill-smartly
description: 创建、修改或评测 Skill 的薄调度入口。用户要求把流程沉淀为 Skill、新建或重写 SKILL.md、调整 Skill 的触发、工作流或资源，或者验证和优化 Skill 时使用；按风险选择轻量流程或内部 creator 方法。
---

# Write Skill Smartly

用户提出创建、修改、评测或优化 Skill 时自动使用，也接受显式调用 `$write-skill-smartly`。请求足够清楚时直接产出 Skill；用户只要求评审时才停在建议层。

本 Skill 只负责选择合适的创建深度。始终读取 [`../writing-for-agents/SKILL.md`](../writing-for-agents/SKILL.md)，用它约束信息层级、渐进式披露、完成标准和文字精度。本入口拥有依赖材料的加载路由：只有本次创建或改变 invocation、frontmatter、router 结构时，才读取 [`../writing-for-agents/SKILL-MECHANICS.md`](../writing-for-agents/SKILL-MECHANICS.md)。

## 默认约定

- 新写或改写的正文、说明和最终汇报默认使用简体中文；代码、标识符、frontmatter key 和既有 Skill 的主语言保持原样，除非用户另有要求。
- 优先检查仓库事实和现有 Skill，不向用户追问仓库可以回答的问题。
- 第三方原件默认只读。需要定制时创建本地 wrapper、fork 或 companion；只有用户明确授权时才直接修改 vendored copy。
- 本地自建 Skill 不登记到第三方 registry；保留第三方内容时同步其来源、许可与 registry 状态。
- v1 默认只有一个 `SKILL.md`；只有分支专用参考、可复用脚本或随交付使用的资产真正减少重复工作时才拆文件。
- Skill 依赖其他 Skill 时，在正文中用可解析路径说明何时读取；不要假定内部依赖能被 Agent 自动触发。
- 实验性或个人 Skill 默认采用显式调用；只有 Agent 必须自行发现时才承担常驻 description 的 context load。

## 1. 选定模式

编辑前从以下模式中选一个，并明确目标路径与受保护文件：

- **新建**：创建新的 Skill。
- **本地修改**：原地修改非第三方 Skill。
- **本地分叉**：提取现有行为，以新名称建立本地版本。
- **第三方伴生**：用本地入口包裹或收窄第三方 Skill，不改原件。

完成标准：模式、目标路径、写入范围和不改范围都已确定。

## 2. 建立合同

先检查目标是否已存在、相邻 Skill 的命名与 invocation/layout、可复用脚本，以及对话中的示例和用户修正，再提炼六项合同：

- **Job**：它让 Agent 完成什么工作。
- **Trigger**：用户显式调用还是 Agent 自动发现，以及原因。
- **Inputs**：需要的提示、文件、工具、仓库或外部来源。
- **Outputs**：产物、修改和最终回复形态。
- **Boundaries**：副作用、宿主差异、第三方内容和越权边界。
- **Evidence**：什么证据能证明 Skill 改变了行为。

只有产品意图、风险偏好、命名或范围取舍仍不明确时才询问用户。

完成标准：六项都能用一句话说明，没有隐含的高影响选择。

## 3. 选择创建深度

默认走**轻量路径**：检查相邻 Skill → 写合同 → 创建或修改 → 用 2–3 个真实提示做 dry run，或让一个有边界的 subagent 试用 → 根据发现修订。

遇到下列任一情况才进入**重型路径**：

- 用户要求 benchmark、触发描述优化或版本对比；
- 变更脚本、工具集成、外部副作用或多文件资源；
- 改变 invocation、核心 workflow 或 output contract；
- 有竞争版本、高不确定性或明确的回归风险。

进入重型路径时，先确认目标宿主，再读取 [`sub-skills/skill-creator/SUB-SKILL.md`](sub-skills/skill-creator/SUB-SKILL.md)，只执行与当前风险对应的阶段。父 Skill 决定范围；内部 creator 不把轻量修改自动升级成完整 eval、baseline、benchmark 或 viewer。其 `claude -p` 和 description optimizer 只为兼容的 Claude Code 目标提供证据；Codex、Grok 等宿主复用测试集、盲评和迭代方法，但使用目标宿主原生的 invocation 配置与验证方式。

完成标准：验证成本与变更风险匹配，未执行无助于当前判断的流程。

## 4. 写 Skill

按以下顺序写：

1. 稳定的 `name`、精确的 `description` 和明确的 invocation 配置；
2. Agent 实际执行的主路径；
3. 每个重要步骤可观察、可穷尽的完成标准；
4. 只在对应分支触发的 reference pointer；
5. 必要的输出合同。

使用命令式表达，并解释会影响行为的原因。每条规则只保留一个权威位置；环境中容易查到的事实不复制成文档缓存。

修改已有 Skill 时，先列出旧文件里所有会改变行为的约束，再做渐进式披露。压缩行数不是安全证据；旧语义已被保留、替换或有意删除才是。

完成标准：未来 Agent 不需要发明主流程，且每个保留段落都会改变其执行。

## 5. 自举验证

用第 3 步选择的深度验证成品。至少检查：

- 真实提示是否走到正确分支；
- pointer 指向的文件存在，且只在需要时加载；
- invocation 配置与用户期望一致；
- 输出和边界在实际运行中可观察；
- 新版本是否出现遗漏、重复、沉积或无动作规则。

把发现直接用于修订 Skill，再重新跑最小相关检查。若验证暴露新的高影响选择，暂停并交给用户决定。

完成标准：至少一个真实场景已检查且发现已处理，或已明确说明无法验证的原因。

## 输出

用简短中文汇报：

- 创建或修改的 Skill 路径；
- 所选模式、invocation 和轻量/重型路径；
- 现在会驱动的关键行为；
- 实际验证及发现；
- 仍需用户决定的事项。

Skill 文件是交付物，长篇方法论报告不是。
