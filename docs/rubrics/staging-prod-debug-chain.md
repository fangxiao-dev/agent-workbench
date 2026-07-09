---
target: staging-prod-debug-chain
target_path: D:/CodeSpace/prj-supplyer-webapp/.agents/skills/staging-prod-debug-chain/SKILL.md
updated: 2026-07-09
---

## 原则

- [待验证] 聚合型 debug skill 应保持薄入口，只负责安全边界、事实建立、分类和路由；平台/集成细节应拆成专用 skill，避免入口 skill 越写越厚、降低执行稳定性。（证据: R1）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-09
- 采纳「拆出 Vercel debug skill，把 staging/prod debug chain 打薄」— 用户原话：同意，而且我认为应该单独拆出 vercel debug SKILL，把原skill打薄。
- 采纳「principle + router SKILL 配合 reference」— 用户原话：vercel 里应该是principle + router SKILL 配合 reference 的方式。
