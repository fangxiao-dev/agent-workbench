---
target: plugin-marketplace/plugins/impl-package/skills/standards-review
updated: 2026-07-20
---

## 原则

- Standards reviewer 只审查 repository conventions、Fowler code-smell baseline 与 codebase-design 设计基线；不得审查 Spec/Plan/DAG 的合同忠实度，也不得创建额外 drift reviewer。
- 仓库规范优先于通用 baseline；Fowler smell 和 deep module vocabulary 都是 judgement baseline，不能伪装成仓库未声明的硬性规则。
- 调用者负责固定 comparison point、准备完整 diff 与规范来源；leaf 只使用收到的不可变范围和共享上下文。
- leaf 不调用 `do-review`、不调度 subagent、不重新决定 topology/capacity，也不做跨轨 ledger、分类或最终 verdict。
- 输出最多 400 words；硬性违规引用规则文件，judgement finding 点名 baseline 并引用 diff 证据。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-20（三轨 Ownership 迁移）

- 从原 `module-review` 保真迁移 Standards 轴；比较点、共享上下文、调度和汇总 Ownership 统一收归 `do-review`。
