# Dev With Track Control Flow

## 接入已有 package

1. 读取 design/spec 当前 revision、所有 plan、gate.md 顶部最新 entry 与 module knowledge/code。
2. 最新 attempt 没有 terminal gate 时恢复该 attempt；已有 terminal gate 且有新工作时路由 impl-planning 创建 patch。
3. 当前 plan 是 Attempt ID、P revision 与 Composition 的事实源；spec 只提供当前 contract 与 AC。

## 接入 patch plan

1. 确认 patch Attempt ID 与文件名、D/S/P revision、Composition 一致。
2. 只读取属于该 Attempt ID 的 tickets/DAG/progress；历史 artifacts 不追加状态。
3. no-DAG attempt 没有 task checklist；恢复需要时创建 attempt progress ledger。
4. 实际验证 append 到该 patch plan 的 Execution Record。
5. gate evaluation 始终写同一个 gate.md，不创建 patch-gate 文件。

## Gate evaluation

1. 固定 comparison point并确认 plan ER anchor。
2. 分流 findings，完成必要 D/S revision 与 re-gate。
3. 计算同 Attempt ID 的下一个未使用 G<n>；terminal verdict 先用该保留 ID 完成 Stage 7，再在 Gate Ledger 说明后一次性插入新 block。
4. status 变化用新 entry和 Supersedes 表达，不修改旧 block。
5. pass/fail/defer 冻结 plan；blocked 保持 active。

## 结束语义

- planned：attempt plan 已建立；
- running：runtime artifact 已有活动状态；
- verified：plan Execution Record 已有选定检查证据；
- gate blocked：最新 entry 为 blocked，attempt 仍 active；
- terminal：最新 entry 为 pass/fail/defer，对应 plan frozen；
- backfilled：terminal Durable Deltas 已进入稳定知识路径。
