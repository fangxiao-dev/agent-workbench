---
name: impl-planning
description: 当已有批准的 Decision/Spec，需要创建 initial/patch plan、决定 Composition 或验证计划时使用；当已批准 plan 判定需要至少两个独立跟踪 acceptance 结论的交付切片时也使用（合并原 to-tickets）；不维护长期行为合同或运行状态。
---

# Impl Planning（含 Ticket 拆分）

为一个 implementation attempt 创建 plan 并把验收拆成可独立验收的 Ticket 合同；语义由本 Skill 与主 thread 拥有，主 thread 不直接编辑当前 package 的 Plan 或 runtime state；Ticket 文件的物理写入与运行时 state 更新由 bound `/impl-package:execution-boundaries` 执行。D/S gate 已通过才继续；未触及的 legacy Spec 可暂缺。

## 前置判定（admission backstop）

若下一步仍需决定可观察行为、data identity、permission、concurrency、recovery 或 public shape，或 contract surface 命中幂等键/CAS/版本号、多来源写同一目标字段、替换/撤回/恢复语义、跨存储提交、声明值 vs 检测值而 Spec 只有规则没有结果矩阵：停止 planning，明确缺失合同并路由 /impl-package:req-align；不得创建或更新 Plan/state，不得在 Plan 中补第二套 DTO/schema。

## 计划与切片判定

- initial 写 plan.md，patch 写 <attempt-id>.patch-plan.md 且只描述相对上次 terminal gate 的实际 delta；新 package 固定 tickets=true, dag=false（dag=true 仅限旧 package 迁移/恢复，只读）；D/S/P 仅可选旧别名。

- 每个 Decision/Spec 约束映射到实现范围与 Ticket：写执行顺序、修改边界、依赖、集成/回滚方式与足以区分正确/错误实现的验证，每项验证明确 evidence owner；early falsification、remaining completion 与不可延后安全不变量分开写。纵向切片装不下一个 worker 时把 seam 冻得更细，不改成横向切分。

- Ticket 按可独立验收的纵向交付切片拆，不按文件、层或 worker 拆；AC 必须可观察、用稳定 claim ID，early falsification 与 remaining completion 证据分开描述；contract references 用仓库相对路径定位到具体章节，不裸指整份文档或行号；与当前 plan/spec 联合检查 coverage、重叠、依赖与 AC feasibility 后由 bookkeeper 发布并原子推进状态。

- 新 package 不调用 `create-task-dag`；`dag=true` 只在旧 package 迁移/恢复时作为只读输入。

- 初始 bundle 冻结 plan candidate 后调用 /impl-package:plan-review 的 bundle-admission；full-review 时处理 material findings，联合校验 coverage、typed dependency、ownership、证据可行性、Gate 边界与集成顺序，再请求一次完整 bundle approval；后续 patch/update 直接沿用。

## 机制

- 机械操作一律走现有语义 CLI；Plan/Ticket 必填字段、Composition 写法与固定文件位置由 composition contract 与模板承接；运行时验收状态只写 .impl-package/state.json，不回写 Ticket 正文。

- 获批后进入 /impl-package:execution-boundaries，再交给 /impl-package:dev-with-track。完成条件：plan 与 D/S 语义一致且无 TBD；Coverage 覆盖全部 active 约束、验证可执行且有 owner；新 package Ticket 与当前 Attempt 一致；state.json 已初始化并通过 validate。
