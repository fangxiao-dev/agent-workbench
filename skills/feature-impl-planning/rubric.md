---
target: skills/feature-impl-planning
updated: 2026-07-08
---
## 原则

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08（三 skill 互相对齐轮；已由 R2 的 Impl-Package ownership/shape 契约取代）
- 采纳「plan/spec 模板升级为三 skill 共享的 canonical：并入 Existing Plan/Spec Adoption、Current Next、Temporary Decisions、Safety/mutation 边界、功能合同表提示、配套账本链接行」— 用户选单一模板来源方案

### R2 · 2026-07-11（Impl-Package Step 4）
- `req-align` 成为 design/spec 的唯一 owner；本 skill 只消费双 gate
  已通过的厚 `spec.md`，不得维护第二份 spec 模板或自行改写 `Composition:`。
- plan 按 `tickets ⊥ dag` 的已过门 Composition 选择形态：仅
  `tickets=false, dag=false` 可含 T<n> executable checklist；所有 `tickets=true` 或
  `dag=true` 的 package 都填写 Package Engineering Contract。`tickets=true, dag=false`
  是 ticket AC evidence/status 的 tickets-only 形态，不建立 task artifact，seam 为
  `none`/`N/A`；只有 `tickets=true, dag=true` 才将本 plan 与相关 approved tickets
  子集交给 DAG。`dag=true` 的 seam execution owner 只记录在 DAG，plan 记录 contract、
  Seam ID、Contract owner、Acceptance owner 和 affected targets。任务、ticket 正文与
  实时状态不能回流 plan。
- 新 package 的顺序为 `plan → to-tickets draft → cross-check plan`；Composition
  升级走 shared contract 的受控迁移，不用 per-ticket patch。patch 仅在 package
  gate closed 后成立。
