# Patch 与 Follow-Up 规则

Patch 只属于 package 已有 terminal gate 之后的生命周期，并继续复用 owning package-id。尚未 terminal 的工作只修订当前 attempt，不创建 patch plan。

## 进入 patch 前

1. 读取 gate.md 顶部最新 entry，确认前一 attempt 已 pass、fail 或 defer。
2. 将 package design/spec 与当前 module knowledge 和代码对账。
3. 分类 drift：
   - implementation-only：复用 D/S revision；
   - behavior contract：升级 S revision并重跑 Spec Gate；
   - design direction：升级 D revision并重跑 Design Gate，再升级 S revision并重跑 Spec Gate。
4. 所需 gate 未通过时停止，不创建 patch plan。

## Patch plan

- 文件名为 YYYYMMDD-HHMM-<patch-topic>.patch-plan.md，Attempt ID 与文件名前缀一致。
- plan 独立声明 P1 与 Composition，不继承历史 plan 的 tickets/dag。
- 不覆盖 plan.md，不向历史 DAG/ticket/task 追加本 attempt 状态。
- 简单 no-DAG patch 不建立 executable task checklist；需要恢复时按 progress-ledger 触发条件处理。
- Planned Verification 引用权威 policy；实际证据 append 到 Execution Record。

## Patch artifacts

- tickets=true 时创建属于本 Attempt ID 的新 ticket files；ticket id 在 package 内保持唯一。
- dag=true 时创建 YYYYMMDD-HHMM-<patch-topic>.patch-dag.md；旧 dag.md / patch DAG 保留历史。
- package 永远只有一个 gate.md；每次 evaluation 在顶部插入新的 <attempt-id>-G<n> entry，不创建 patch-gate 文件。

## Freeze

pass、fail、defer gate entry 使对应 patch plan terminal/frozen。后续变化创建新的 patch attempt；blocked entry 不冻结 plan，补证通过新的 P revision、Execution Record 与 gate entry 表达。
