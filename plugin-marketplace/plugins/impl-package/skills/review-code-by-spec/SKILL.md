---
name: review-code-by-spec
description: >
  当需要依据 issue、Decision、Spec、Plan 或 DAG 审查固定 comparison point 的完整代码 diff 时使用；
  检查实现忠实度、遗漏需求、scope creep、兼容性、状态机和跨模块 seam。
---

# Review Code by Spec

审查调用者已固定的完整 diff 是否忠实实现其提供的 issue、Decision、Spec、Plan、DAG 与其他适用合同。范围/diff/合同 evidence 缺失、矛盾或不足 → 明确报告 evidence gap/UNCERTAIN；不要以 branch 名或工作树重新推导范围、比较点或合同来源。

## 判断维度
逐项对照合同与完整 diff，报告：缺失/部分实现的需求；未被要求的 scope creep；看似实现但行为错误的需求；implementation interface 与 seam 是否忠实遵守声明合同；module boundary 是否忠实；兼容窗口、状态机、跨 slice/跨模块 seam 是否偏离声明合同。
每条 finding 必须同时有稳定合同来源（章节级引用：合同原文或稳定来源）与 diff 证据；合同未规定某项行为时，不得以仓库规范、Fowler smell 或个人设计偏好代替合同报告为 Spec finding。

## 输出合同（leaf 结构化输出）
≤400 words：每条 finding 给需求/合同项、类型（缺失/部分/scope creep/错误行为/contract drift）、合同原文或稳定来源、文件/行或稳定 hunk、可观察的不忠实行为、建议动作。无 finding 不得只写 `PASS`，必须含精简 Coverage record（对照的合同来源/关键条款、检查过的 diff module/interface/seam、未形成 finding 的结论、无法验证的边界）。返回 `verdict | coverage | findings` 紧凑索引；不要以 repository conventions、Fowler smell、deep module design、代码组织或实现约定替代合同证据。
