---
target: plugin-marketplace/plugins/impl-package/skills/spec-review
updated: 2026-07-20
---

## 原则

- Spec reviewer 只审查 issue、Decision、Spec、Plan、DAG 与其他提供合同的 faithful implementation；缺失需求、scope creep、interface/seam drift、兼容窗口、状态机和跨模块 seam 都属于本轴。
- 每项 finding 必须同时有来源合同和 diff 证据；不能把仓库规范、Fowler smell 或主观代码组织偏好冒充合同违背。
- 调用者负责固定 comparison point、准备完整 diff 与合同 evidence；leaf 只使用收到的不可变范围和共享上下文。
- leaf 不调用 `do-review`、不调度 subagent、不重新决定 topology/capacity，也不做跨轨 ledger、分类或最终 verdict。
- 输出最多 400 words；Spec evidence 独立返回，不与其他轨道预合并。

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-20（三轨 Ownership 迁移）

- 从原 `module-review` 保真迁移 Spec 轴；比较点、合同来源定位、调度和汇总 Ownership 统一收归 `do-review`。
