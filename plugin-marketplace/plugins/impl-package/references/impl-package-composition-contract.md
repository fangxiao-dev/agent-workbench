# Impl-Package Composition Contract

## 1. 权威边界

- Decision 与 Spec contract ensemble 定义要交付的行为、跨模块数据/API 合同与验收语义。Spec ensemble 至少包含 `spec.md`，并可包含其“Spec 设计范围”声明为 earned 的 `contract-design.md`。
- Plan 定义一个 attempt 的执行策略、验证和 Composition。
- Ticket 定义纵向验收切片；DAG 定义横向执行依赖。
- `.impl-package/state.json` 只保存当前执行状态与恢复入口。
- `progress.md` 是 current Attempt 的统一恢复投影；Execution Record 保存公共执行判断，Task Handoff 只保存局部接手上下文。
- `gate.md` 保存当前 gate 判决；历史由 Git 保存。

D/S/P 仅是可选的人类可读别名，不是新 artifact 的必填字段，也不绑定文件内容。不要为了小改动升级别名；需要固定比较点时只使用 Git commit ID。

`contract-design.md` 从属 `spec.md` 并共用 Status、审批和 Spec Gate；它没有独立 alias、revision、状态或生命周期。Plan 可以引用其中稳定章节，但不得复制或补设计另一套 DTO/schema。

## 2. Composition

Plan 必须声明：

```text
Composition：tickets=<true|false>, dag=<true|false>
```

四种组合都合法：

| tickets | dag | 用途 |
| --- | --- | --- |
| false | false | 小而线性的单人改动 |
| true | false | 需要独立验收切片，但执行无需并行图 |
| false | true | 需要执行依赖/ownership，但没有独立 Ticket 验收 |
| true | true | 同时需要纵向验收与横向执行图 |

不要为了完整感创建 Ticket 或 DAG。只有它们能减少验收、ownership 或依赖歧义时才 earned。

## 3. 固定位置

- initial plan：`plan.md`
- patch plan：`<attempt-id>.patch-plan.md`
- Tickets：`tickets/` 的直接 Markdown 子文件
- initial DAG：`dag.md`
- patch DAG：`<attempt-id>.patch-dag.md`
- current state：`.impl-package/state.json`
- current progress：`progress.md`
- Attempt Execution Record：`execution/<attempt-id>/execution-record.md`
- Task Handoff：`execution/<attempt-id>/task-handoffs/<task-id>-handoff.md`
- current gate：`gate.md`

外部引用一律保存为仓库相对路径。现役流程只访问这些固定位置和显式路径。

## 4. 生命周期

1. req-align 产出并批准 Decision/Spec contract ensemble。
2. impl-planning 创建 plan 并选择 Composition。
3. Plan 冻结后按 Composition 创建 Draft Ticket/DAG；联合检查 coverage、typed dependency、ownership、证据可行性与集成顺序后取得一次 bundle approval。
4. `init` 发布当前 Attempt 的 Ticket、初始化 state 和完整 Progress 层，进入执行。
5. dev-with-track 从 `progress.md` 恢复，根据 canonical dependency 选择下一动作，通过 CAS 更新状态并写 checkpoint/judgment。
6. verification-before-completion 审计 completion claim。
7. gate 写入当前判决；`pass` 才支持默认的 merge-ready 结论。
8. durable delta 按需回刷稳定文档。

owner approval 绑定当时明确展示的 bundle；跨 session 恢复时用批准所在的 Git commit 加当前 diff 判断是否仍适用，不创建额外 receipt。

Plan、Ticket 或 DAG 的语义变化只使受影响范围的 approval/validation 失效；修正后只重审受影响部分。terminal Gate 冻结整个 Attempt，后续实现进入 patch Attempt，不改写旧记录。

## 5. Readiness

- Task 依赖由 DAG 与 Task state 判断。
- Ticket acceptance 由 Ticket AC、typed dependency 和 Ticket state 判断。
- Task `DONE` 不等于 Ticket `SATISFIED`。
- `BLOCKED` 必须有直接原因和 evidence；checkpoint 只提供恢复上下文，不释放依赖。
- terminal gate 后若继续实现，创建新 patch attempt；不要改写旧 commit 来伪装原判决仍适用。
- DAG 必须拒绝未知 dependency、cycle 和 ownership 缺口。Ticket dependency 只允许 `implementation | acceptance | release`。
- `READY/RUNNING` 不得越过未释放 Task dependency；Ticket acceptance 不得越过 implementation/acceptance dependency。
