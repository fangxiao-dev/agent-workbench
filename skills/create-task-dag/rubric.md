---
target: skills/create-task-dag
updated: 2026-07-08
---
## 原则

- [待验证] 示例应泛化为通用逻辑，不保留项目专名（Inventory/Lark 等）
  （证据: R2）

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08（三 skill 互相对齐轮）
- 采纳「持久化映射补 spec.md 路由（验收语义变化先补 spec）、补 patch-dag 目标，并收敛为 SKILL.md 单一映射来源」— 契约级冲突，用户整批同意
- 采纳「dag-and-ownership 补任务编号续编 + Retired 时写 patch-dag」
- 采纳「worker 返回状态 ↔ DAG 板状态映射表」
- 采纳「Ground The Slice 点名 feature-impl-planning 为 plan/spec 生产者」
- 采纳「SKILL.md 与全部 references 中文化，状态 token 保留英文」

### R2 · 2026-07-08（偏好确认轮）
- 否决「含项目专名的真实示例值得保留」— 用户原话：最好泛化，抽出通用逻辑。
  已把 Inventory Item UI Slice 示例和状态示例改写为通用领域表述。
