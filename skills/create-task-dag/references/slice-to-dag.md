# 输入路由：从宽输入到执行 DAG

当来源是宽泛的 implementation request、spec、PRD 或 handoff，而不是已批准的
package plan（及需要时的相关 Approved ticket 子集）时，读本文件。

不要把宽来源画成一张 DAG，也不要在此 skill 内切 delivery slice。根据缺失
前提选择下列唯一对应的路由；不要一律重开 `to-tickets mode=draft`。

## 路由原因

| 观察到的输入状态 | 路由 | create-task-dag 的边界 |
| --- | --- | --- |
| gated spec 明确 `tickets=true, dag=true` + package `plan.md` 已存在，且无 Draft/Approved ticket | `to-tickets mode=draft` | 不切 slice、不发布 tracker |
| 缺 package `plan.md` | `feature-impl-planning` | 不把缺 plan 的输入转给 `to-tickets` |
| 宽泛/未成 package 输入、缺 gated spec / 两道 gate 证据，或 Composition 未决 | `requirement-alignment` | 不创建 ticket 或 DAG |
| gated `tickets=true, dag=true` 的 plan 已存在，相关 ticket 都是 `Draft` | 等明确 owner approval 后 `to-tickets mode=publish` | 不把 Draft 变为 Approved |
| gated `tickets=false, dag=true`，且 plan 与稳定 `spec:AC-n` 齐备 | 直接使用 plan DAG | 不进入 `to-tickets` |
| gated `tickets=false, dag=true` 但 spec/AC 缺失，或任意 Composition/现有 artifact 不一致 | `requirement-alignment` | 不猜测 composition、AC 或替代 spec |
| `tickets=true, dag=false` 或 `tickets=false, dag=false` | 不创建 DAG | no-DAG 规则仅引用 shared contract 第 4 节 |
| 单一 Approved ticket 被要求推断跨 ticket seam | 请求 package plan + 相关 Approved ticket 子集 | 不从单 ticket 推断或补写 seam |

`to-tickets` 仍拥有 delivery-slice 的验收切分判断。create-task-dag 不创建或
发布 tracker work item；只有相应上游输入就绪后才返回执行分解。

## 返回 DAG 的条件

仅在以下输入齐备时开始 execution decomposition：

- `tickets=true, dag=true`：`plan.md` + 相关 Approved tickets 子集；
- `tickets=false, dag=true`：`plan.md`，且可从 package spec 读取 `spec:AC-n`；
- plan 中的 seam contract 足以理解跨 ticket work。

单一 ticket 不是跨 ticket seam contract 的替代品。若调用者只能提供单一 ticket，
要求补齐 plan 与相关 Approved ticket 子集；不得自行推断或补写 seam。

## 交接信息

路由时交代：

- 所用的原因对应路由（draft、publish、requirement-alignment、plan 或补齐输入）；
- 当前 skill 将在 plan 和相关 Approved tickets 到位后，只做 task DAG；
- 不会创建或发布 tracker work item；
- ticket 的验收语义仍属于 ticket/spec，task 只通过共享 contract 的
  `contributes-to` / `enables` 字段建立贡献关系。
