---
name: review-code-by-spec
description: >
  当需要依据 issue、Decision、Spec、Plan 或 DAG 审查固定 comparison point 的完整代码 diff 时使用；
  检查实现忠实度、遗漏需求、scope creep、兼容性、状态机和跨模块 seam。
---

# Review Code by Spec

审查调用者已固定的完整 diff 是否忠实实现其提供的 issue、Decision、Spec、Plan、DAG 与其他适用合同，并返回可验证的 Spec evidence。

## 输入合同

调用者必须提供已经解析为不可变 SHA 的 base/head comparison point、完整 diff 与 commit 列表，以及全部适用的 contract evidence。使用调用者给定范围和来源审查；不要以 branch 名、当前工作树或局部文件重新推导范围、比较点或合同来源。若范围、diff 或合同 evidence 缺失、互相矛盾或不足以形成有证据的结论，明确报告 evidence gap/UNCERTAIN。

## 审查内容

逐项对照收到的合同与完整 diff，报告：

- 缺失或部分实现的需求。
- diff 中未被要求的 scope creep。
- 看似实现但实际行为错误的需求。
- implementation interface 与 seam 是否忠实遵守声明合同。
- module boundary 是否忠实遵守 issue、Decision、Spec、Plan 或 DAG。
- 兼容窗口、状态机、跨 slice seam 与跨模块 seam 是否偏离声明合同。

每个 finding 必须同时有稳定的合同来源与 diff 证据。若合同没有规定某项行为，不要以仓库规范、Fowler smell 或个人设计偏好代替合同并把它报告为 Spec finding。

## 输出合同

在不超过 400 words 内输出 Spec evidence。对每个 finding 写明：需求或合同项、缺失/部分实现/scope creep/错误行为/contract drift 的类型、合同原文或稳定来源、文件/行或稳定 hunk、可观察的不忠实行为，以及建议动作。

无 finding 时不得只写 `PASS`。输出必须包含精简的 Coverage record：列出已对照的合同来源或关键条款、对应检查过的 diff module/interface/seam、未形成 finding 的结论，以及无法验证的边界。Coverage record 是本轮 Spec 审查证据；它不得以仓库规范或个人偏好替代合同证据，也不得修改既有 400 words 上限。

不要以 repository conventions、Fowler code-smell baseline、deep module design quality、代码组织或实现约定替代合同证据。
