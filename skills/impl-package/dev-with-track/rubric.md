---
target: skills/impl-package/dev-with-track
updated: 2026-08-02
---
## 原则

- 当前 attempt plan 是 Attempt ID、P revision 与 Composition 的事实源；spec 只提供当前 D/S contract 与 AC。
- no-DAG attempt 不建立 task checklist 或独立 progress ledger；tickets=false 时恢复事实进入 Execution Record 或 handoff，tickets=true 时 Ticket 自身保存最小 Phase/Next/Progress 恢复摘要。
- 实际 review/verification 证据 append 到 plan Execution Record；gate 只保存 newest-first append-only 判决摘要与 Durable Deltas。
- blocked→pass 通过新 G entry 与 Supersedes 表达，旧 entry 不修改；pass/fail/defer terminal 后冻结 plan。
- gate evaluation 前分流 execution findings，禁止 decision/spec、长期知识与过程证据互相回流。
- [待验证] 高风险执行前只检查既有 contract 到可执行验证与 ER owner 的语义可追踪性；能复用 AC anchor、场景名或测试名时不强制 invariant/case ID、固定矩阵或新 artifact。（证据: R5）

## 决策记录（滚动，最近 ≤5 轮）
### R1 · 2026-07-08（三 skill 互相对齐轮）
- 采纳「删除本地 spec/plan 模板，canonical 归 impl-planning，模板清单改为跨 skill 指针」— 用户在单一模板来源 (a) 与双模板分工 (b) 中选 (a)
  - **Superseded（2026-07-11 Impl-Package Step 1）：**仅其中“spec canonical 归 impl-planning”已被 R3 取代；本条保留历史 provenance，plan ownership 与删除重复模板的方向不变。
- 采纳「dag/progress 模板 ownership 升级为三车道（Primary owned / Conditional seam / Forbidden），对齐 create-task-dag 的 ownership lanes」
  - **Superseded（2026-07-18）：**普通 DAG 改为最小 primary ownership 与 known seam/risk；不再要求三车道 ownership 或完整 Task contract。
- 采纳「dag 模板状态补 Retired（gate passed）、编号检查清单补 *.patch-dag.md」— 承接用户手工加入的 patch 模式语义

### R2 · 2026-07-08（偏好确认轮）
- 采纳「findings 模板示例泛化，去掉 preview/fixture 等项目味表述」— 延伸自用户对 create-task-dag 示例的泛化纠正

### R3 · 2026-07-11（Impl-Package Step 1 ownership 收口）
- `decision.md` / `spec.md` canonical ownership 与模板归 `req-align`；`plan.md` / patch plan 归 `impl-planning`；`dev-with-track` 只消费已过门 decision/spec 与当前 plan，不创建或重定义它们。
- 删除 `dev-with-track` 的 design 模板副本与 `impl-planning` 的 spec 模板副本，保持每类 artifact 单一 canonical 模板来源。

### R4 · 2026-07-12（Artifact lifecycle 与 append-only gate）

- dev-with-track 追加 plan Execution Record，但不拥有 plan 的策略或结构定义。
- package 只保留一个 gate.md；每次 evaluation 顶部插入不可变 entry，完整验证不复制进 gate。
- terminal entry 写入前完成 Stage 7；blocked capture gap 由后续 entry 补齐。
- findings 成为 package 级 inbox，每条记录 Attempt ID，gate 前按 decision/spec/backfill/ER 分流。

### R5 · 2026-07-26（轻量高风险验证就绪）

- 采纳「执行前检查既有设计边界到测试与 ER evidence owner 的可追踪性，但不为格式对齐强制 invariant/case ID 或固定矩阵」— 用户原话：轻量化运作，不要总是在对齐格式。
