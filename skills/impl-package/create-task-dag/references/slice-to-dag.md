# 输入路由：从计划拆解到执行 DAG

当来源不是当前 attempt 的 approved plan（以及 `tickets=true` 时同 Attempt ID 的完整 Draft/Approved Ticket 集合）时，按下表路由；不要从 spec、历史 plan 或单个 ticket 猜测 Composition/seam。Draft Ticket 是合法的 DAG 输入，Ticket publication 延后到 Tickets + DAG 联合 review 之后。

## 路由原因

| 观察到的输入状态 | 路由 | create-task-dag 的边界 |
| --- | --- | --- |
| 当前 plan 为 tickets=true, dag=true，且无同 Attempt ID 的完整 Draft/Approved ticket | to-tickets mode=draft | 不切 slice、不发布 tracker |
| 缺当前 attempt plan | impl-planning | 不从 spec 生成 DAG |
| 缺 gated spec / AC 或 D/S revision 不一致 | req-align | 不伪造 contract 或 acceptance target |
| 当前 tickets=true, dag=true plan 的 tickets 全为 Draft | 直接创建 DAG；联合校验通过后交 owner 一次 review，再由 to-tickets mode=publish | 不把 Draft 自行标为 Approved，不设置独立 Ticket approval 门 |
| 当前 plan 为 tickets=false, dag=true，且 spec:AC-n 齐备 | 直接创建 attempt DAG | 不进入 to-tickets |
| 当前 plan 为 tickets=true, dag=false 或 tickets=false, dag=false | 不创建 DAG | no-DAG attempt 不通过 plan checklist制造 task 状态 |
| 当前 plan Composition 与同 Attempt ID artifacts 不一致 | impl-planning | 通过新 P revision修正 Composition/artifact relocation |
| 单一 ticket 被要求推断跨 ticket seam | 请求当前 plan + 相关同 Attempt Draft/Approved ticket 子集 | seam contract 只从 spec 读取 |

## 返回 DAG 的条件

- 当前 plan 的 dag=true；
- Attempt ID、D/S/P revision 可解析；
- tickets=true 时相关 Draft/Approved tickets 属于同一 Attempt ID，且 Draft 集合已完整覆盖 earned slices；
- spec 提供稳定 AC、interface 与 seam contract；
- plan 提供本次执行顺序和具体 integration strategy。

## 联合校验与复审

Tickets 与 DAG 进入 `ready-for-review` 前，必须联合验证 earned-ticket coverage、typed blockers 与 Task dependencies 的一致性、primary ownership 不重叠、`contributes-to` 多对多映射、AC evidence 可行性，以及同一 Attempt/D-S-P revision、gate/preflight 边界和 binding。DAG 不复制 Ticket AC、worker ownership 或 Task→AC 验收映射；Task `DONE` 也不表示 Ticket accepted。

若 Ticket 的 acceptance boundary、typed edge、Task contribution/ownership、执行顺序、evidence feasibility、Composition 或 revision/gate binding 发生实质变化，旧 bundle approval 对受影响范围失效。按影响范围修订或重建 DAG 片段，重新联合校验并提交一次 review；未受影响 artifacts 可以 batch reconciliation。纯格式、引用、分类或机械 Plan Revision rebinding 不触发重新审批，但必须留有 handoff/evidence 记录。

## 交接信息

路由时说明原因、缺失 artifact、当前 Attempt ID 与恢复条件。Ticket/spec 保存验收语义；DAG Task 只通过 `contributes-to` 记录多对多执行贡献，不得复制 spec seam contract、把 Task 变成 Ticket 子项，或从 Task 状态推断 acceptance。handoff 同时列出联合校验结果和 owner review 状态；只有 bundle 获批后才路由 execution preflight。
