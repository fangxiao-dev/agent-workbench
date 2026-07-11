---
target: skills/dev-with-track
updated: 2026-07-11
---
## 原则

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08（三 skill 互相对齐轮）
- 采纳「删除本地 spec/plan 模板，canonical 归 feature-impl-planning，模板清单改为跨 skill 指针」— 用户在单一模板来源 (a) 与双模板分工 (b) 中选 (a)
  - **Superseded（2026-07-11 Impl-Package Step 1）：**仅其中“spec canonical 归
    feature-impl-planning”已被 R3 取代；本条保留历史 provenance，plan ownership
    与删除重复模板的方向不变。
- 采纳「dag/progress 模板 ownership 升级为三车道（Primary owned / Conditional seam / Forbidden），对齐 create-task-dag 的 ownership lanes」
- 采纳「dag 模板状态补 Retired（gate passed）、编号检查清单补 *.patch-dag.md」— 承接用户手工加入的 patch 模式语义

### R2 · 2026-07-08（偏好确认轮）
- 采纳「findings 模板示例泛化，去掉 preview/fixture 等项目味表述」— 延伸自
  用户对 create-task-dag 示例的泛化纠正

### R3 · 2026-07-11（Impl-Package Step 1 ownership 收口）
- `design.md` / `spec.md` canonical ownership 与模板归 `requirement-alignment`；
  `plan.md` / patch plan 归 `feature-impl-planning`；`dev-with-track` 只消费已过门
  design/spec 与当前 plan，不创建或重定义它们。
- 删除 `dev-with-track` 的 design 模板副本与 `feature-impl-planning` 的 spec 模板
  副本，保持每类 artifact 单一 canonical 模板来源。
