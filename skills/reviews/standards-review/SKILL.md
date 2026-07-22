---
name: standards-review
description: >
  当调用者已提供固定 comparison point、完整 diff 与仓库规范上下文时，审查 repository conventions、
  Fowler code-smell baseline，以及 module interface、depth、leverage、locality 和代码组织。
---

# Standards Review

审查调用者已固定的完整 diff 是否符合仓库已有的编码规范与 Standards 设计基线，并返回可验证的 Standards evidence。

## 输入合同

调用者必须提供已经解析为不可变 SHA 的 base/head comparison point、完整 diff 与 commit 列表，以及适用的仓库规范来源。使用调用者给定范围逐 file/hunk 审查；不要以 branch 名、当前工作树或局部文件重新推导范围。若范围、diff 或 Standards 来源缺失、互相矛盾或不足以形成有证据的结论，明确报告 evidence gap/UNCERTAIN。

## 审查基线

### 仓库规范优先

收集并应用调用者提供的所有描述代码应如何编写的仓库规则，例如 `AGENTS.md`、`CODING_STANDARDS.md`、`CONTRIBUTING.md`。仓库明确认可的写法覆盖通用 baseline；不要把与仓库规范冲突的 smell 当作 finding。工具已可靠执行的规则不重复报告。

### Fowler code-smell baseline

下列 smell 是启发式和 judgement call，不是仓库未声明的硬规则：

- **Mysterious Name**：名称无法说明职责或内容。建议重命名；若无法诚实命名，指出设计仍含糊。
- **Duplicated Code**：多个 hunk 或文件出现相同逻辑形状。建议抽取共享形状。
- **Feature Envy**：方法访问其他对象的数据多于自身数据。建议把行为移到它依赖的数据一侧。
- **Data Clumps**：相同字段或参数组合反复同行。建议提炼为一个类型。
- **Primitive Obsession**：primitive/string 代替值得命名的领域概念。建议建立小型领域类型。
- **Repeated Switches**：同一类型的 `switch` 或条件链重复出现。建议用多态或共享映射集中表达。
- **Shotgun Surgery**：一个逻辑变化迫使许多文件分散修改。建议把共同变化收进一个 module。
- **Divergent Change**：一个文件因多个无关原因被修改。建议按变化原因拆分。
- **Speculative Generality**：加入未被需求要求的抽象、参数或 hook。建议删除并收回到真实需求。
- **Message Chains**：调用者依赖很长的导航链。建议在起点隐藏导航细节。
- **Middle Man**：class/function 主要只向后转发。建议移除中间层并直接调用真正目标。
- **Refused Bequest**：子类或实现者忽略、覆盖大部分继承合同。建议放弃继承并使用组合。

### Codebase-design vocabulary

使用 `/codebase-design` 的 deep module vocabulary 作为 Standards 设计基线：检查 module interface 是否以小表面承载足够行为（depth / leverage）；检查知识与验证是否留在合适 seam 以维持 locality；检查新增 adapter 是否有真实可变性依据。interface 包含调用方必须知道的 invariant、错误模式和顺序约束，不得缩窄为类型签名。这些判断仍是 judgement baseline，不伪装成仓库未声明的硬规则。

## 审查深度选择

先完成仓库规范、Fowler smell 与 codebase-design 基线审查；普通局部 diff 不默认进行重构式“code judo”搜索。用户明确要求深度/严格可维护性审查时开启深挖；此外，reviewer 可根据完整 diff、共享上下文和仓库规范自行选择深度。

当 shared path 出现 feature-specific 分支、同一概念的条件/flag/mode 跨 hunk 或 module 增长、adapter/wrapper/loosely shaped type boundary 增加、知识离开 canonical layer、模块明显膨胀，或存在可删除整层间接的机会时，可按需读取 [strict-maintainability.md](references/strict-maintainability.md)。这些是非穷尽启发式，不是固定触发链；约 1000 行只提示结构复核，不自动成为 finding 或 blocker。

结构性可维护性是本 skill 的首要深挖方向，但不是排他能力边界。发现其他风险时仍可如实给出证据、风险和建议。

## 严格 finding 的证据指引

形成严格可维护性建议时，应尽可能说明 changed hunk 中新增或放大的复杂度、可解释的维护风险、可行的简化或集中方向，以及它是仓库规则 hard violation 还是 judgement call。这些是形成可验证建议的证据指引，不是逐项打勾的准入门槛。证据不足时，可以在 Coverage record 中记录担忧或 evidence gap；不要只因“还能更优雅”、单一文件行数或个人偏好产生 finding。

## 输出合同

在不超过 400 words 内输出 Standards evidence。对每个 finding 写明：严重性或硬性/判断性分类、文件/行或稳定 hunk、违反的仓库规则或点名的 baseline smell、具体证据与建议动作。仓库规范硬性违规必须引用规则文件；smell 必须引用相关 hunk。明确区分 hard violation 与 judgement call。严格可维护性建议还应尽可能说明维护风险与可行方向；不要把它当作固定门槛。

无 finding 时不得只写 `PASS`。输出必须包含精简的 Coverage record：

- 列出本 diff 中已实际检查的新增或变更模块、public API、adapter、persistence/state entry point；每项写出检查的 Standards 维度（例如 interface depth、locality、vendor containment、重复逻辑）和结果。
- 对高风险但未形成 Standards finding 的区域，写明“已检查、无 Standards 证据”或 evidence gap；不得把它伪装为 Standards PASS。
- 写出无法从 diff 或调用者共享上下文验证的边界。

Coverage record 是审查证据；它不得替代合同忠实度审查，也不得修改既有 400 words 上限。

issue、Decision、Spec、Plan 或 DAG 的合同忠实度、遗漏需求、scope creep、兼容窗口、状态机或跨模块 seam 不属于本 skill 的首要审查内容；发现有证据的相关风险时，如实报告其 evidence gap 或风险证据。
