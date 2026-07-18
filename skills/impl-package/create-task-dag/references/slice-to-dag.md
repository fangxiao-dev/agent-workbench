# 输入路由：从宽输入到执行 DAG

当来源不是已批准的当前 attempt plan（以及 tickets=true 时同 Attempt ID 的 Approved ticket 子集）时，按下表路由；不要从 spec、历史 plan 或单个 ticket 猜测 Composition/seam。

## 路由原因

| 观察到的输入状态 | 路由 | create-task-dag 的边界 |
| --- | --- | --- |
| 当前 plan 为 tickets=true, dag=true，且无同 Attempt ID 的 Draft/Approved ticket | to-tickets mode=draft | 不切 slice、不发布 tracker |
| 缺当前 attempt plan | impl-planning | 不从 spec 生成 DAG |
| 缺 gated spec / AC 或 D/S revision 不一致 | req-align | 不伪造 contract 或 acceptance target |
| 当前 tickets=true, dag=true plan 的 tickets 全为 Draft | owner 批准后 to-tickets mode=publish | 不把 Draft 自行标为 Approved |
| 当前 plan 为 tickets=false, dag=true，且 spec:AC-n 齐备 | 直接创建 attempt DAG | 不进入 to-tickets |
| 当前 plan 为 tickets=true, dag=false 或 tickets=false, dag=false | 不创建 DAG | no-DAG attempt 不通过 plan checklist制造 task 状态 |
| 当前 plan Composition 与同 Attempt ID artifacts 不一致 | impl-planning | 通过新 P revision修正 Composition/artifact relocation |
| 单一 ticket 被要求推断跨 ticket seam | 请求当前 plan + 相关 Approved ticket 子集 | seam contract 只从 spec 读取 |

## 返回 DAG 的条件

- 当前 plan 的 dag=true；
- Attempt ID、D/S/P revision 可解析；
- tickets=true 时相关 Approved tickets 属于同一 Attempt ID；
- spec 提供稳定 AC、interface 与 seam contract；
- plan 提供本次执行顺序和具体 integration strategy。

## 交接信息

路由时说明原因、缺失 artifact、当前 Attempt ID 与恢复条件。Ticket/spec 保存验收语义；DAG Task 只通过 `contributes-to` 记录多对多执行贡献，不得复制 spec seam contract、把 Task 变成 Ticket 子项，或从 Task 状态推断 acceptance。
