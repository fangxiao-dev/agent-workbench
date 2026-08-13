# 输入路由：旧 package 的 DAG 只读审计

本 reference 只服务已有 3.4/Task package 的恢复或迁移。新 package 的 Composition 统一为 `dag=false`，不从 plan、spec 或 Ticket 创建 DAG。来源不是当前 attempt 的 existing DAG 时，按下表路由；不要从 spec、历史 plan 或单个 Ticket 猜测新的 Task 图。

## 路由原因

| 观察到的输入状态 | 路由 | create-task-dag 的边界 |
| --- | --- | --- |
| 旧 package 为 tickets=true, dag=true，且无同 Attempt ID 的完整 Draft/Approved ticket | to-tickets mode=draft | 只补读迁移所需的 Ticket evidence，不发布新 tracker |
| 缺当前 attempt plan | impl-planning | 不从 spec 生成 DAG |
| 缺 gated spec / AC 或当前合同不一致 | req-align | 不伪造 contract 或 acceptance target |
| 旧 package 的 tickets=true, dag=true plan 的 tickets 全为 Draft | 只读已有 DAG；联合校验结果交 owner | 不创建或更新 DAG，不把 Draft 自行标为 Approved |
| 旧 package 为 tickets=false, dag=true，且 spec:AC-n 齐备 | 读取 existing attempt DAG | 不创建新的 Task |
| 新 package 为 tickets=true, dag=false | 不创建 DAG | no-DAG attempt 不制造 Task 状态 |
| 当前 plan Composition 与同 Attempt ID artifacts 不一致 | impl-planning | 通过当前 Attempt 修正 Composition/artifact relocation |
| 单一 ticket 被要求推断跨 ticket seam | 请求当前 plan + 相关同 Attempt Draft/Approved ticket 子集 | seam contract 只从 spec 读取 |

## 返回 DAG 的条件

- 当前 plan 的 dag=true 且 package 已存在 legacy DAG；
- Attempt ID 与当前 plan 可解析；
- tickets=true 时相关 Draft/Approved tickets 属于同一 Attempt ID，且 Draft 集合已完整覆盖 earned slices；
- spec 提供稳定 AC、interface 与 seam contract；
- plan 提供本次执行顺序和具体 integration strategy。

## 联合校验与复审

旧 Tickets 与 DAG 进入迁移/审计报告前，必须联合验证 earned-ticket coverage、typed blockers 与 Task dependencies 的一致性、primary ownership 不重叠、`contributes-to` 多对多映射、AC evidence 可行性，以及同一 Attempt、gate/preflight 边界和 binding。DAG 不复制 Ticket AC、worker ownership 或 Task→AC 验收映射；Task `DONE` 也不表示 Ticket accepted。

若 Ticket 的 acceptance boundary、typed edge、Task contribution/ownership、执行顺序、evidence feasibility、Composition 或 gate binding 发生实质变化，旧 bundle approval 对受影响范围失效。按影响范围修订或重建 DAG 片段，重新联合校验并提交一次 review；未受影响 artifacts 可以 batch reconciliation。纯格式、引用或分类变化不触发重新审批，但必须留有 handoff/evidence 记录。

## 交接信息

路由时说明原因、缺失 artifact、当前 Attempt ID 与恢复条件。Ticket/spec 保存验收语义；legacy DAG Task 只通过 `contributes-to` 记录多对多执行贡献，不得复制 spec seam contract、把 Task 变成 Ticket 子项，或从 Task 状态推断 acceptance。handoff 只能作为迁移线索，必须另找真实产物；只有 owner 明确批准迁移后才路由 execution preflight。
