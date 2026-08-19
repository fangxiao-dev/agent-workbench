---
name: review-code-by-standards
description: >
  当需要依据仓库规范和可维护性基线审查固定 comparison point 的完整代码 diff 时使用；检查 repository conventions、
  Fowler code-smell baseline，以及 module interface、depth、leverage、locality 和代码组织。
---

# Review Code by Standards

审查调用者已固定的完整 diff 是否符合仓库编码规范与 Standards 设计基线，返回可验证的 Standards evidence。范围/diff/Standards 来源缺失、矛盾或不足以形成结论 → 明确报告 evidence gap/UNCERTAIN；不要以 branch 名或工作树重新推导范围。

## 判断维度
- **仓库规范优先**：调用者提供的仓库规则（AGENTS.md/CODING_STANDARDS.md/CONTRIBUTING.md）覆盖通用 baseline；与仓库规范冲突的 smell 不作 finding；工具已可靠执行的规则不重复报告。
- **Fowler code-smell baseline**（启发式与 judgement call，不是仓库未声明的硬规则）：Mysterious Name、Duplicated Code、Feature Envy、Data Clumps、Primitive Obsession、Repeated Switches、Shotgun Surgery、Divergent Change、Speculative Generality、Message Chains、Middle Man、Refused Bequest——每条建议落到具体 hunk。
- **codebase-design vocabulary**：active skill catalog 有 `codebase-design` 则优先读其 deep module vocabulary，否则用内置基线——module interface 以小表面承载足够行为（depth/leverage）；知识/验证留在合适 seam 维持 locality；新增 adapter 有真实可变性依据；interface 含 invariant/错误模式/顺序约束，不缩窄为类型签名。可选 skill 缺失不阻塞 Standards review。
- **深度选择**：先完成规范+smell+design 基线，普通局部 diff 不默认重构式深挖。用户明确要求深度/严格可维护性审查，或出现 feature-specific 分支扩张、同概念 flag/mode 跨 hunk 增长、adapter/loosely-shaped boundary 增加、知识离开 canonical layer、模块显著膨胀（约 1000 行只是提示）、可删整层间接的机会时，按需读 [strict-maintainability.md](references/strict-maintainability.md)——非穷尽启发式，不是固定触发链。

## 证据指引
严格建议尽可能说明 changed hunk 新增/放大的复杂度、可解释维护风险、可行简化/集中方向，以及是仓库规则 hard violation 还是 judgement call；不能只因"还能更优雅"、单文件行数或个人偏好产生 finding。合同忠实度/遗漏需求/scope creep 不属于首要内容；有证据时如实报告 evidence gap 或风险。

## 输出合同（leaf 结构化输出）
≤400 words：每条 finding 给严重性或 hard/judgement 分类、文件/行或稳定 hunk、违反的仓库规则（必须引用规则文件）或点名的 baseline smell、证据与建议动作。无 finding 不得只写 `PASS`，必须含精简 Coverage record（已检查的新增/变更模块、public API、adapter、persistence/state entry point 及各自检查维度；高风险但无 finding 区域写"已检查、无 Standards 证据"或 evidence gap；无法验证的边界）。返回 `verdict | coverage | findings` 紧凑索引。
