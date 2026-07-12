---
target: skills/module-review
updated: 2026-07-10
---
## 原则

- 两个 reviewer 始终独立：Standards 审查仓库规范与设计基线，Spec 审查来源需求和
  contract fidelity；不得合并 findings 或新增第三个 drift reviewer。
- Standards 必须引用 `/codebase-design` 的 module、interface、seam、depth、
  leverage、locality 和 adapter 词汇，且把它们当 judgement baseline，不伪装成
  仓库未声明的硬规则。
- Spec 必须检查 interface/seam、兼容窗口、状态机和跨 slice seam 是否偏离
  spec/plan/dag；每个 finding 要有来源合同与 diff 证据。
- Implementation package 只在 composition 或契约信号命中时强制触发；任何 diff
  审查都必须由调用者给 fixed point。

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-10（替换 review 模型）
- 采纳「删除原 module-review，改用 Matt code-review 的 Standards / Spec
  双轴模型，并以 module-review 名称纳入本仓库」— 用户明确要求。
