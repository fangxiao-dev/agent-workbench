---
target: plugin-marketplace/plugins/impl-package/skills/review-code
updated: 2026-07-22
---

## 原则

- [已验证] 调整 reviewer role 的偏重时保留原有有效审查知识；热路径保留指导思想、profile、边界与输出合同，详细 checklist 以原意下沉到只在 full behavior review 读取的 reference。（证据: R1-R3）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-22
- 修正「以运行风险为主就删除原 `review-code` 设计」— 用户原话：大量优秀例子应放到 reference；吸收的是 idea 和指导思想，`SKILL.md` 不应承载所有示例。

### R2 · 2026-07-22
- 采纳「恢复原设计并以移动代替改写」— 用户原话：恢复和充足，尽量不要改写；更多的是移动，避免擅自压缩或者曲解原本的设计意思。

### R3 · 2026-08-12
- 采纳「按加载频率分层而不是不断给主路径加规则」— 保留完整审查知识，把详细 checklist、工具与实践下沉到 `references/review-checklist.md`，仅 full behavior review 条件加载。
