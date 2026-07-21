# 优化建议：把 Plan Eng Review 变成可执行 Implementation Gate

## 设计目标

优化重点不应只是“再审一遍 plan”，而应让工程审查产出可以被执行流程消费、可以被测试证明、缺失时能够阻止实施启动的 gate。`plan-eng-review` 负责提前发现技术歧义和恢复漏洞；`execution-preflight` 负责验证 gate 已具象化；实施与 seam review 负责证明代码遵守 gate；`do-review` 保留为最终跨域收口，而不是首次发现系统设计问题的地方。

## 何时强制使用完整审查

满足任一高风险特征时应进入完整 engineering plan review：存在外部 mutation；横跨两个及以上持久化系统；使用 distributed lock；存在 operation journal 或显式状态机；有 partial-success/unknown-outcome 恢复；涉及权限、资金、通知发送或不可逆业务动作；计划预计修改超过八个文件且跨两个以上服务边界。

为控制流程成本，可分三级：

- L0：文案、typo、样式修补和机械重构，不触发 engineering review。
- L1：单模块、无外部写入、无并发状态机，使用精简 authority/test checklist。
- L2：跨系统 mutation、并发、journal、partial-success 或高风险任务，强制完整 review 和 gate manifest。

本复盘任务属于 L2。虽然范围大，但复杂度来自业务正确性，单纯拆小或删减需求不能消除风险；应先建立完整工程合同，再按 seam 分阶段实施。

## Plan Eng Review 必须产出的四份核心工件

### 1. Mutation Authority Matrix

矩阵必须穷举每个入口、目标系统和操作类型，说明 GET/POST/PUT/DELETE 是否允许、由谁授权、在哪把锁下执行、失败后谁可以重试。任何单元格存在两种合理解释，都必须在实施前升级为 Owner 或 architecture decision。

最低字段建议：`flow_id`、`entrypoint`、`system`、`operation`、`allowed`、`authority`、`lock_scope`、`idempotency_key`、`retry_owner`、`decision_source`。

### 2. State Transition And CAS Matrix

每条 transition 必须写明合法 predecessor、触发者、CAS predicate、并发冲突后的动作、是否 terminal、是否允许重新进入，以及它对 latest pointer 或其他索引的原子性要求。必须给出全局不变量：普通 update API 不得修改 state；所有 state transition 必须使用条件更新；状态和 pointer 不得回退；冲突后必须 reread 并分类，不能 blind retry。

最低字段建议：`from`、`to`、`actor`、`guard`、`atomic_writes`、`conflict_behavior`、`replay_behavior`、`terminal`。

### 3. Failure And Recovery Matrix

对每个外部 side effect 列出 call-before-evidence、response-lost、evidence-before-next-system、next-system failure、notification prepare/send/finalize failure 等边界。每个边界都要定义用户可见状态、durable evidence、允许的自动动作、禁止重放的 mutation，以及需要人工对账的条件。

最低字段建议：`failure_point`、`durable_evidence`、`provider_outcome`、`visible_state`、`automatic_recovery`、`forbidden_replay`、`manual_action`、`fault_injection`。

### 4. Codepath And Browser Test Diagram

测试图必须把验收语句展开为可执行分支，而不是只写测试类别。对本任务，最低图应为：

```text
Browser confirm
├─ fresh overwrite
│  ├─ exactly 1 PUT
│  ├─ exact provider readback
│  ├─ checkpoint + approval readback
│  └─ notification success
├─ revision changed after dialog open
│  ├─ dialog remains open
│  ├─ selection clears
│  ├─ current precheck refreshes
│  └─ 0 POST / 0 PUT
├─ PUT succeeded, success-journal write crashes
│  ├─ first result = outcome unknown
│  ├─ reconciliation only GETs
│  └─ total PUT count remains 1
├─ provider success, Lark approval fails
│  ├─ state = needs_reconciliation
│  └─ retry performs 0 provider writes
└─ approval succeeds, notification prepare/send fails
   ├─ approval remains visible
   ├─ warning survives route refresh
   └─ notification retry is independent
```

每个叶节点还必须绑定测试文件或 scenario ID、fixture 构造方式、fault injection 点、精确 call count、durable store 断言和 UI 断言。若无法写出这些内容，说明架构尚未达到可验证状态。

## 把 prose 输出升级为 Gate Manifest

建议 `plan-eng-review` 在保留人类可读报告的同时，生成结构化 manifest，供 `execution-preflight` 和 `dev-with-track` 检查。格式可以是 YAML，也可以是带固定 marker 的 Markdown generated block；关键是字段稳定、可机检，而不是具体扩展名。

示意：

```yaml
risk_level: L2
owner_decisions:
  - id: AUTH-GENERIC-BOUND-PUT
    status: resolved
mutation_authorities:
  - flow: explicit_overwrite
    operation: PUT
    allowed: true
    authority: resolution_operation
state_transitions:
  - from: provider_call_started
    to: provider_succeeded
    cas_required: true
failure_modes:
  - id: PROVIDER_SUCCESS_EVIDENCE_CRASH
    forbidden_replay: PUT
verification_gates:
  - id: AC8-CRASH-BOUNDARY
    test: path/to/test::scenario
    fault_injection: after_provider_before_evidence
    expected_provider_calls: 1
```

`execution-preflight` 应 fail closed 检查：L2 任务是否有四类工件；所有 owner decision 是否 resolved 或明确标记 blocked；每个 mutation flow 是否有 authority；每个状态是否有 transition rule；每个 partial-success acceptance 是否有 fault injection；每个 gate 是否映射到具体测试入口。

## 实施前必须先红的关键测试

对本类任务，以下 tests 应在主要实现之前建立并确认因缺少实现而失败：

1. stale transition 不能降级较新状态。
2. latest pointer 在交错 writer 下不能回退。
3. provider 成功、journal evidence 写入崩溃后，恢复不得重放 provider mutation。
4. 非 exact provider readback 不能通过，包含 ID 不同、private/extra collection 命中和多余 customer-owned values。
5. generic bound PUT 的允许或禁止行为被测试固定到已批准 authority decision。
6. notification journal prepare 或 provider factory 失败时，真实邮件 provider call count 为零。
7. profile/revision 在等待 lock 期间变化时，lock 内 authoritative eligibility revalidation 必须阻断 mutation。

这些测试不是追求形式上的 TDD 覆盖率，而是把最昂贵的分布式不变量先变成机器可判定事实。

## 建议的工作流

```text
Decision / Spec approved
        ↓
Plan Eng Review + risk classification
        ↓
Four engineering artifacts + gate manifest
        ↓
Execution Preflight: fail-closed validation
        ↓
Key red tests + isolated fixtures/fault injection
        ↓
Implementation by task/seam
        ↓
Authority/store/provider/approval/browser seam reviews
        ↓
Integrated E2E and gate evidence
        ↓
Do Review final convergence
```

关键变化是把 review 左移并分层：计划审查负责“设计是否可安全实施”，seam review 负责“局部实现是否遵守合同”，最终 review 负责“集成后是否仍满足完整合同”。最终 review 不再承担第一次画状态图或第一次决定谁能 PUT 的职责。

## 对 plan-eng-review skill 的候选修改

1. 在开场先做 risk classifier，只有 L2 强制完整流程，避免小任务被过度治理。
2. Data flow review 必须同时追踪 happy path、stale writer、partial-success、reconcile 和 notification subflow。
3. State-machine 章节要求产出 transition/CAS 表，不接受只有状态枚举。
4. Test review 要求 branch-level diagram，并将每个高风险叶节点绑定 fixture、fault injection 和 exact side-effect count。
5. 所有可由两种合理方式解释的 mutation authority 自动登记为 owner decision，不允许 reviewer 静默替 Owner 选择。
6. 审查完成条件从“报告已生成”改为“所有 required gate 都具备证据或明确 blocked”。
7. 输出同时包含人类可读报告和结构化 manifest，使下游 skill 可以 fail closed 消费。
8. 对跨系统任务可保留 outside voice/独立 reviewer，但它是增强项；核心 gate 不应依赖是否能启动额外 agent。

## 对执行流程的候选修改

`execution-preflight` 应验证 manifest 与批准 revision 绑定，防止 plan 修改后沿用旧审查；`dev-with-track` 应在每个 task 开始前显示该 task 拥有的 authority、transition 和 verification gates；task 完成时必须附测试证据和 side-effect count；共享 seam 合并前触发一次局部 review；若 implementation 改变 authority、state graph 或 failure recovery，必须回到 plan revision，而不是只在代码中悄然改变合同。

## 如何评价优化是否有效

建议连续观察若干 L2 任务，记录：实施开始后新增的 Owner decision 数量、最终 review 才发现的 authority 反转数量、状态机/恢复类 blocker 数量、E2E fixture 重做次数、从首次 implementation 到 review convergence 的轮次和时间、同一 mutation path 的重复修复次数，以及 escaped production defect。目标不是让 review finding 归零，而是让高成本 finding 从最终阶段迁移到 plan/preflight 阶段。

## 风险与约束

完整 `plan-eng-review` 本身会增加前置时间，所以不应对 typo、纯样式和简单单模块变更一刀切。结构化 manifest 也可能退化成填表主义，因此字段必须服务于实际 codepath/test gate，并由执行工具读取。最重要的 fail-closed 规则应保持简洁：没有 mutation authority matrix、state transition/CAS matrix、failure/recovery matrix 或 branch-level test diagram的 L2 计划，不进入 implementation。

## 本次不实施的内容

本文件只提供下一次优化分析的输入。本次不修改 `plan-eng-review`、`execution-preflight`、`dev-with-track`、`do-review` 或任何业务仓库文件，不创建 gate schema，也不验证候选流程的运行效果。
