# Impl-Package Composition Contract

## 1. 权威边界

- Decision 与 Spec contract ensemble 定义要交付的行为、跨模块数据/API 合同与验收语义。Spec ensemble 至少包含 `spec.md`，并可包含其“Spec 设计范围”声明为 earned 的 `contract-design.md`。
- Plan 定义一个 attempt 的执行策略、验证和 Composition。
- Ticket 定义纵向验收切片，是新 package 唯一持久实施与验收单元；DAG/Task 只作为旧 package 的迁移与恢复输入。
- `.impl-package/state.json` 只保存当前执行状态与恢复入口。
- `progress.md` 是 current Attempt 的统一恢复投影；Execution Record 保存公共执行判断，active checkpoint 是跨 session 的正常恢复入口。Task Handoff 只为旧 package 保留，不能成为新 package 的默认执行轴。
- `gate.md` 保存当前 gate 判决；历史由 Git 保存。

D/S/P 仅是可选的人类可读别名，不是新 artifact 的必填字段，也不绑定文件内容。不要为了小改动升级别名；需要固定比较点时只使用 Git commit ID。

`contract-design.md` 从属 `spec.md` 并共用 Status、审批和 Spec Gate；它没有独立 alias、revision、状态或生命周期。Plan 可以引用其中稳定章节，但不得复制或补设计另一套 DTO/schema。

Ticket 与 Task 引用 Decision/Spec/contract-design/Plan 中的合同或验收语义时，必须使用仓库相对路径并定位到具体一级或二级大章节（Markdown heading/anchor 或 `§章节名`）；不得只裸指整份文档，也不使用易漂移的行号。恢复、派发和验收默认读取这些章节及其直接引用，而不是把整份合同文档作为无差别上下文。

## 2. Composition

新 package 的 Plan 必须声明 Ticket-only Composition：

```text
Composition：tickets=true, dag=false
```

阶段 A 保留 `dag=false` 作为当前 3.4 state engine 的兼容占位；它不表示创建 Task、DAG 或 Task Handoff。新 package 只有 Ticket-only 组合：

| tickets | dag | 用途 |
| --- | --- | --- |
| true | false | 需要独立验收切片的 Ticket-only package，依赖只写在 Ticket 上 |

`dag=true` 仅用于已有 3.4/Task package 的恢复、迁移或只读审计；新 planning 路径不得选择它。阶段 A 期间旧 state engine 可能仍写出空的 `tasks` 对象，但新 package 不产生 Task 行或 Task runtime projection；阶段 B 删除该兼容字段。

新 package 始终创建 Ticket；不要为了完整感创建 Task、DAG 或 Task Handoff。

## 3. 固定位置

- initial plan：`plan.md`
- patch plan：`<attempt-id>.patch-plan.md`
- Tickets：`tickets/` 的直接 Markdown 子文件
- initial/patch DAG：仅旧 package 的 `dag.md` 或 `<attempt-id>.patch-dag.md`
- current state：`.impl-package/state.json`
- current progress：`progress.md`
- Attempt Execution Record：`execution/<attempt-id>/execution-record.md`
- Task Handoff：仅旧 package 的 `execution/<attempt-id>/task-handoffs/<task-id>-handoff.md`
- current gate：`gate.md`

外部引用一律保存为仓库相对路径。现役流程只访问这些固定位置和显式路径。

## 4. 生命周期

1. req-align 产出并批准 Decision/Spec contract ensemble。
2. impl-planning 创建 plan 并选择 Composition。
3. Plan 冻结后，Ticket-only Composition 只创建 Draft Ticket；联合检查 coverage、typed dependency、证据可行性与集成顺序后取得一次 bundle approval。旧 package 的 DAG 只读，不重新发布。
4. `init` 发布当前 Attempt 的 Ticket，初始化 state 和完整 Progress 层，进入执行；3.4 兼容字段不代表 Task execution。
5. dev-with-track 从 `progress.md` 与 active checkpoint 恢复，根据 Ticket canonical dependency 选择下一动作，通过 CAS 更新状态并写 checkpoint/judgment。
6. verification-before-completion 审计 completion claim。
7. gate 写入当前判决；`pass` 才支持默认的 merge-ready 结论。
8. durable delta 按需回刷稳定文档。

owner approval 绑定当时明确展示的 bundle；跨 session 恢复时用批准所在的 Git commit 加当前 diff 判断是否仍适用，不创建额外 receipt。

Plan、Ticket 或 DAG 的语义变化只使受影响范围的 approval/validation 失效；修正后只重审受影响部分。terminal Gate 冻结整个 Attempt，后续实现进入 patch Attempt，不改写旧记录。

## 5. Readiness

- 新 package 的 readiness 只由 Ticket typed dependency 与 Ticket state 判断。
- Ticket acceptance 由 Ticket AC、typed dependency 和 Ticket state 判断。
- 旧 package 的 Task `DONE` 不等于 Ticket `SATISFIED`，迁移时必须重新映射真实 evidence。
- `BLOCKED` 必须有直接原因和 evidence；checkpoint 只提供恢复上下文，不释放依赖。
- terminal gate 后若继续实现，创建新 patch attempt；不要改写旧 commit 来伪装原判决仍适用。
- Ticket dependency 必须拒绝未知 dependency 和 cycle，只允许 `implementation | acceptance | release`。
- 旧 DAG 的 `READY/RUNNING` 不得越过未释放 Task dependency；新 package 不创建这条状态轴。

## 6. Ticket-only 运行边界

- 新 package 严格使用 Ticket barrier：未释放 `implementation` 边的 Ticket 不进入 `readyTickets`；`acceptance` 边允许实施但阻止最终 `SATISFIED`；`release` 边只在发布/Gate 前复核。
- early evidence 只能索引真实产物，不能把 Ticket 推进到中间 acceptance 状态。Ticket 仍需覆盖全部 required claims 才能最终满足。
- Ticket AC 必须显式编号 stable claim ID；early falsification evidence 与 remaining completion evidence 分开描述。
- 第一条可执行路径必须保持 tenant、RBAC、privacy、幂等和数据完整性不变量；早期路径可以窄，但不能薄。
- 跨 session 续接沿用既有默认：交接前写 active checkpoint，长期判断写 ER judgment；compact 只作异常兜底，不是正常恢复权威。
- package task session 主线程是 `state.json` 唯一 writer；worker 只返回结构化 evidence。未来 broker 的协调 ledger 不属于本阶段。

`RETIRED` 是新合同中原 `WAIVED`/`SUPERSEDED` 的统一 terminal 状态，必须带 `disposition: waived | superseded`。3.4 runtime 只作为一次性迁移输入；3.5 runtime 只接受 Ticket/evidence/checkpoint 状态。
