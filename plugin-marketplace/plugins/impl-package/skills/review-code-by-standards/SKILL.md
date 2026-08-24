---
name: review-code-by-standards
description: >
  当需要依据仓库规范和可维护性基线审查固定 comparison point 的完整代码 diff 时使用；检查 repository conventions、
  Fowler code-smell baseline，以及 module interface、depth、leverage、locality 和代码组织。
---

# Review Code by Standards

审查调用者已固定的完整 diff 是否符合仓库已有的编码规范与 Standards 设计基线，并返回可验证的 Standards evidence。调用者必须提供已解析为不可变 SHA 的 base/head comparison point、完整 diff、commit 列表和适用的规范来源；使用给定范围逐 file/hunk 审查，不以 branch 名、当前工作树或局部文件重新推导范围。范围、diff 或 Standards 来源缺失、矛盾或不足以形成有证据的结论时，明确报告 evidence gap/UNCERTAIN。

## 判断维度

- **仓库规范优先**：收集并应用调用者提供的所有仓库规则（如 AGENTS.md/CODING_STANDARDS.md/CONTRIBUTING.md）；仓库认可的写法覆盖通用 baseline，与仓库规范冲突的 smell 不作 finding；工具已可靠执行的规则不重复报告。
- **Fowler code-smell baseline**（启发式与 judgement call，不是仓库未声明的硬规则）：Mysterious Name（名称无法说明职责/内容→重命名，无法诚实命名则指出设计含糊）、Duplicated Code（多个 hunk/file 出现相同逻辑形状→抽取共享形状）、Feature Envy（访问其他对象的数据多于自身数据→把行为移到数据侧）、Data Clumps（相同字段/参数组合反复同行→提炼类型）、Primitive Obsession（primitive/string 代替值得命名的领域概念→小型领域类型）、Repeated Switches（同一类型的 switch/条件链重复→多态/共享映射）、Shotgun Surgery（一个逻辑变化迫使许多文件分散修改→共同 module）、Divergent Change（一个文件因多个无关原因被修改→按变化原因拆分）、Speculative Generality（加入未被需求要求的抽象/参数/hook→删除并收回真实需求）、Message Chains（调用者依赖很长导航链→在起点隐藏导航）、Middle Man（class/function 主要只转发→移除中间层）、Refused Bequest（子类/实现者忽略或覆盖大部分继承合同→放弃继承改用组合）；每条建议落到具体 hunk。
- **codebase-design vocabulary**：active skill catalog 有 `codebase-design` 则优先读其 deep module vocabulary，否则用内置基线——module interface 以小表面承载足够行为（depth/leverage）；知识/验证留在合适 seam 维持 locality；新增 adapter 有真实可变性依据；interface 含调用方必须知道的 invariant、错误模式和顺序约束，不缩窄为类型签名。这些判断仍是 judgement baseline，不伪装成仓库未声明的硬规则；可选 skill 缺失不阻塞 Standards review。
  - **深度选择**：
    1. 先完成规范、smell 与 design 基线；普通局部 diff 不默认进行重构式“code judo”搜索。先完成可验证基线，避免 reviewer 被重构偏好带走而漏掉直接的 Standards evidence。
    2. 用户明确要求深度/严格可维护性审查时开启深挖。只有明确的深度信号才扩大检查面，避免把局部 diff 的普通形状误报为 finding。
    3. reviewer 也可根据完整 diff、共享上下文和仓库规范自行选择深度。深度由实际证据决定，不由固定行数或个人偏好决定。
- shared path 出现 feature-specific 分支、同一概念的条件/flag/mode 跨 hunk 或 module 增长、adapter/wrapper/loosely shaped type boundary 增加、知识离开 canonical layer、模块明显膨胀，或存在可删除整层间接的机会时，可按需读取 [strict-maintainability.md](references/strict-maintainability.md)；这些是非穷尽启发式，约 1000 行只提示结构复核，不自动成为 finding 或 blocker。

结构性可维护性是本 skill 的首要深挖方向，但不是排他能力边界；发现其他风险时仍可如实给出证据、风险和建议。涉及状态/轨迹机制时，以语义 CLI 的 `--help`、`choices`、校验/错误输出和处境注入尾注作为机械证据，不把工具已执行的规则重复写成 smell。

## 证据指引

形成严格可维护性建议时，应尽可能说明 changed hunk 中新增或放大的复杂度、可解释的维护风险、可行的简化或集中方向，以及它是仓库规则 hard violation 还是 judgement call；证据不足时可在 Coverage record 中记录担忧或 evidence gap；不要只因“还能更优雅”、单一文件行数或个人偏好产生 finding。

## 输出合同（leaf 结构化输出）
≤400 words：每个 finding 写明严重性或 hard/judgement 分类、文件/行或稳定 hunk、违反的仓库规则（必须引用规则文件）或点名的 baseline smell、具体证据与建议动作；仓库规范硬性违规必须引用规则文件，smell 必须引用相关 hunk，明确区分 hard violation 与 judgement call。严格可维护性建议还应尽可能说明维护风险与可行方向；不要把这些当固定门槛。

无 finding 时不得只写 `PASS`；输出必须包含精简 Coverage record：列出实际检查的新增/变更模块、public API、adapter、persistence/state entry point 及各自的 Standards 维度（如 interface depth、locality、vendor containment、重复逻辑）；对高风险但未形成 Standards finding 的区域写明“已检查、无 Standards 证据”或 evidence gap，不得把它伪装为 Standards PASS；写出无法从 diff 或调用者共享上下文验证的边界。返回 `verdict | coverage | findings` 紧凑索引；Coverage record 是审查证据，不替代合同忠实度审查，也不修改 400 words 上限。

## 边界

issue、Decision、Spec、Plan 或 DAG 的合同忠实度、遗漏需求、scope creep、兼容窗口、状态机或跨模块 seam 不属于本 skill 的首要审查内容；发现有证据的相关风险时，如实报告其 evidence gap 或风险，不以它们替代 Standards 基线。
