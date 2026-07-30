---
name: grilling-waves
description: 以 recommendation-led decision waves 编排现有 grilling skill，用明确的 upper-level product context 约束 PRD、MVP、产品决策或 Spec 的批量对齐，并在收敛后统一 writeback。用户希望分 wave 推演、批量裁决而非逐题问答，尤其需要控制 overdesign 时使用。
---

# Grilling Waves

## 依赖边界与交互优先级

开始时读取并使用 [`../grilling/SKILL.md`](../grilling/SKILL.md)。只复用其中的问题质量、推荐答案、决策依赖遍历和本地事实调查规则，不继承 `one-question-per-turn` 交互格式。基础规则中的 `one-by-one` 只表示按逻辑依赖解析 decision tree，不表示每个 assistant turn 只呈现一个问题。

本 skill 定义用户可见的交互单位：一个 wave 必须在一次 assistant 输出中完整呈现该 wave 的所有 Decisions，然后只等待一次用户批量回复。遇到基础 `grilling` 的逐题等待要求时，以这里的 wave 合同为准；其余规则继续有效。

保留下列完整生命周期：先对齐 upper-level product context，再调查事实并遍历 decision tree，以 waves 收敛 Decisions，持续维护 decision ledger，最后统一 writeback。

## 1. 对齐 upper-level product context

开始 waves 前需要具备：

1. 一份基础 PRD、plan、Decision 草案或同等问题陈述；
2. 一份说明持久产品意图的 upper-level product context，用来判断具体选择。

upper-level product context 不是第二份 PRD，只记录必要的决策过滤器：

- 目标用户与产品价值；
- 为什么现在要做；
- MVP 必须证明或解锁什么；
- MVP 应主动避免什么；
- 哪些未来兼容性值得保留，但不授权当前实现。

如果用户尚未提供这些内容，先根据已有证据给出一份短的推荐草案，明确标注假设，请用户确认或修改，不让用户从空白开始撰写。对齐后保持其稳定；只有后续选择暴露真实冲突或缺失原则时才重新打开。

## 2. 调查 decision tree 并划定 wave

遵循 `grilling` 调查代码、文档和其他可用证据；能够从事实回答的问题直接调查，不转交用户。沿依赖关系识别当前主题的 material Decisions，再决定哪些可以一起理解和裁决。

wave 不设硬性或默认问题数量，数量由真实 decision tree 决定。一个主题有 3 个 material Decisions 就完整呈现 3 个；有 10 个且可以一起理解和裁决，就完整呈现 10 个。不得为了控制篇幅而忽略、压缩、合并或静默延后 material Decisions。

只有真实依赖才构成拆 wave 的理由，例如前一个答案会决定后续问题是否存在、改变后续选项，或暴露 upper-level context conflict。若同一主题因此拆成连续 waves，先说明当前已发现的 Decisions、本轮覆盖范围、留待下一 wave 的 Decisions，以及后者依赖什么答案。新分支只能在获得前置答案后发现时，在下一 wave 补充并说明来源。

单问题 wave 是依赖结构造成的例外，不是默认交互方式。只有当前 Decision 会改变后续问题是否存在、暴露 upper-level context conflict，或后续 Decisions 的内容与选项确实依赖它的答案时，才单独呈现。不能仅因为某个问题重要、不确定性高、解释较长或想简化输出，就退化为逐题询问；高不确定性应通过补足事实、失败例子、选项差异与恢复影响来处理。输出可能过长时，按真实依赖拆 wave，不缩短每个 Decision 应有的说明。

## 3. 一次完整呈现 wave

> Wave 批处理的是用户回复轮次，不是问题数量、背景、推理、例子或推荐理由的详细程度。

每个 wave 先说明主题及为什么现在需要裁决，然后在同一次 assistant 输出中呈现该 wave 的全部 Decisions。为每项分配稳定 ID，如 `W2-D1`、`W2-D2`；后续追问、修改、ledger 和 writeback 都沿用该 ID，避免编号漂移。

每个 Decision 都应自然地给出足够信息，使用户无需追问基本背景即可裁决：为什么现在需要这个决定；必要的具体场景、边界或失败例子；真正有差异的选项；推荐选择及其证据或判断依据；以及实质性的 MVP 成本、风险、失败恢复或未来兼容影响。没有实际差异的选项不要为了形式完整而制造出来。

这些是内容完整性要求，不是固定输出模板。根据问题使用连贯段落、少量 bullets、表格或例子；不要机械拆成“背景、例子、选项、推荐、理由、成本”等固定小节，也不要因为同一 wave 中 Decisions 较多而把任何一项缩成一两句话。

完整呈现后只等待一次批量回复，并明确回复合同。用户可以说“全部采纳”“除 `W2-D3` 外全部采纳”“`W2-D4` 选 B”或“展开 `W2-D5`”。在收到这次回复前，不逐项停顿等待确认。

## 4. 校验回复并维护 decision ledger

收到用户的批量回复后，一次性处理整组采纳、修改、否决和展开请求，更新 working decision ledger，并将变化与 upper-level product context 和已接受 Decisions 对照：

- **Aligned：**吸收选择，继续下一 wave。
- **Trade-off：**说明具体代价；用户选择清楚时继续。
- **Context conflict：**暂停后续依赖分支，请用户选择修改具体 Decision，或有意修订 upper-level product context。
- **Context gap：**推荐对 upper-level product context 做最小补充，请用户裁决是否采纳。

只为真实 conflict 或 gap 中断。不要把 context 检查变成每轮仪式，也不要把未来兼容性解释为构建推测性抽象或扩大 MVP 的许可。用户的明确修改保持权威，除非它与用户尚未选择修改的上层约束冲突。

working decision ledger 持续记录：

- 已对齐的 upper-level product context；
- 已接受的 Decisions 及后续修订；
- 明确的 non-goals 与 deferrals；
- 未解决的 Decisions；
- 被取代含义及其预期处置。

## 5. 收敛后统一 writeback

在 grilling 期间不编辑目标 PRD、Decision、Spec、plan 或实现文档。所有 material branches 都已解决、有意延期或明确保留为 open 后，向用户呈现一份完整的 consolidated decision ledger 供确认。

如果最初调用已经明确授权“收敛后 writeback”，展示 ledger 后即可执行；否则在修改目标文档前请求一次最终确认。

将已接受 Decisions 一次性应用到所有获授权的目标文档，并保持产品意图、需求、合同和实现细节之间的区别。删除或弱化既有文本前，将每项受影响含义明确归入以下一种处置：

- 原位保留；
- 迁移到具名目标；
- 被已接受的 Decision 取代；
- 由用户明确 deprecated。

不能因为新结构更短就静默删除旧的产品承诺。除非用户另行授权，不运行 approval gates、不发布、不绑定 revisions、不实现代码，也不扩大修改范围。

writeback 后报告修改了哪些文档、吸收了哪些 Decision groups、仍有哪些 unresolved 或 deferred items，以及哪些阶段有意未执行。
