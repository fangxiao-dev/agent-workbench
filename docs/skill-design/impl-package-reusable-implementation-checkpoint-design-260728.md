# Impl-Package 可复用实现检查点的提前派发规则设计

- 日期：2026-07-28
- 适用范围：`dev-with-track` 的 Ticket/Task dependency readiness 与主 session 并行派发
- 文档性质：已吸收 Blind Opening 意见并经 owner 确认的设计提案
- 当前阶段：设计已 apply 到共享 contract、主 `SKILL.md`、runtime reference 与 eval；结构校验和两轮只读 subagent review 已完成，定向 unittest 仍受 3 个既有基线失败阻断
- 核心原则：不要过度设计；在主 `SKILL.md` 强调原则 router，将低频判断条件放入 reference，并相信主 session 基于实际 seam、diff 与证据作出判断

## 1. 背景

当前 `dev-with-track` 已区分 worker 做完实现与 Ticket acceptance，但 implementation dependency 的释放条件仍偏绝对：只要上游尚未正式验收，下游就容易被一概视为不可启动。

实际执行中，上游可能已经提交下游所需的稳定接口或行为，并取得局部测试证据，只剩真实调用链测试、review closure、观测性或其他不触及共享 seam 的尾项。此时继续串行等待会损失安全的并行机会，也会把“尚未正式验收”误写成“尚无任何可复用实现”。

## 2. 目标语义

Ticket 和 Task 使用同一原则，仅默认终态名称不同：

- 默认情况下，下游 Ticket implementation 等待上游 Ticket `SATISFIED`；下游 Task 等待上游 Task `DONE`。
- 作为低频例外，上游 Ticket 仍为 `IN_PROGRESS` 或 Task 仍为 `RUNNING`，但已形成可复用实现检查点时，主 session 可以提前派发仅依赖该检查点的下游 Ticket/Task implementation。
- 提前派发不改变上游状态，不把检查点伪装成 `SATISFIED` 或 `DONE`。
- 该例外只影响 implementation readiness；acceptance 和 release dependency 均不因该例外释放，继续按各自既有 gate 与语义判断。
- 上游若改变下游正在复用的合同、行为或其他关键依赖事实，受影响的下游 Ticket/Task 转为 `NEEDS-REVALIDATION`。

这是一项由主 session 裁量的调度原则，不是新的 dependency 状态或自动派发算法。

## 3. 可复用实现检查点的判断条件

提前并行必须同时满足：

1. 下游实际依赖的接口或行为已经提交并有局部测试证据，且下游执行基线能够使用该实现。
2. 主 session 根据实际剩余工作、open findings、diff 与风险，确认它们不会改变下游依赖的合同或可观察行为；不能仅因剩余项属于测试覆盖、review closure 或观测性就认定安全。
3. 派发前，主 session 根据当前 diff 与证据在既有 plan Execution Record 追加一次记录，说明共享 seam、工作边界与回退条件；不要求上游事先已经写好专用检查点记录。如果上游改变下游依赖的合同、行为、错误语义、时序、兼容性或其他关键事实，主 session 停止沿用受影响的下游工作与旧证据，将相关 Ticket/Task 转为 `NEEDS-REVALIDATION`，完成 scoped revalidation 后再继续。
4. 只提前启动 implementation；acceptance 和 release dependency 不提前释放。
5. ER 如实说明并行派发理由，不将检查点表述为上游已经通过验收；下游 implementation 启动也不表示原 dependency edge 已正式释放，不能反向支持上游或下游 acceptance。

这些条件用于帮助主 session 判断，不形成机器可执行 checklist。ER 只保存必要理由与恢复上下文，不成为新的授权 artifact。

## 4. 文档落点

### 4.1 共享 Composition contract

在 `impl-package-composition-contract.md` 的 typed blocker 章节定义 Ticket/Task 共用的默认规则、检查点例外、implementation-only 边界和关键依赖事实变化后的 `NEEDS-REVALIDATION`。这里保存跨 skill 的规范性语义，不展开运行时判断过程。

### 4.2 `dev-with-track/SKILL.md`

在 `Restore and dispatch` 主路径加入醒目的原则 router：

> 默认等待上游 Ticket `SATISFIED` 或 Task `DONE`；若主 session 判断上游已形成可复用实现检查点，可按 runtime protocol 提前派发仅依赖该检查点的下游 Ticket/Task implementation。该例外不释放 acceptance 或 release dependency。

主文档不复制五项判断条件，避免低频分支扩张主路径。

### 4.3 `runtime-protocol.md`

在 restore/readiness 部分承载第 3 节的判断条件、派发时 ER 记录和 scoped revalidation 要求。reference 不定义 checkpoint ID、固定 commit 字段、固定记录格式、自动恢复算法、worker 通知协议或额外审批。

### 4.4 Review/revise 中的机会判断

`Review and gate entry` 主路径只提醒一个低频机会：存在受阻下游，且新证据表明其依赖 seam 已稳定时，主 session 可重新判断可复用实现检查点。详细条件继续放在 runtime protocol；满足时上游 review/closure 与下游 implementation 可以并行，相关 review 尚未完成且可能改变 seam 时继续等待。该判断不交给 `do-review` 或 leaf reviewer，也不形成固定触发、必经步骤或新 stage。

## 5. 非目标

- 不新增 JSON 状态、sidecar 字段、artifact、模板或 CLI 行为。
- 不新增 checkpoint registry、授权 token、自动有效性计算或 scheduler。
- 不把 Execution Record 变成第二份 Ticket/Task 状态源。
- 不提前释放 Ticket acceptance、release dependency、正式 review 或 gate。
- 不把下游 implementation 启动解释成原 dependency edge 已正式释放，或作为任何 acceptance 证据。
- 不要求所有并行派发都创建新的 checklist、矩阵或结构化记录。
- 不用本规则掩盖仍可能修改下游依赖 seam 的上游工作。

## 6. 示例

### 6.1 可提前派发

LARK-01 已提交 typed mutation-unknown 与 cache-clear 接口并有局部测试证据，LARK-02 的执行基线能够使用该实现。主 session 检查实际剩余工作和 open findings 后，确认补充真实 caller 并发测试不会改变 LARK-02 依赖的合同或可观察行为。

主 session 可以在 ER 记录复用 seam、剩余项为何不影响它、工作边界和 revalidation 条件，然后提前派发 LARK-02 implementation。LARK-01 仍保持 `IN_PROGRESS`；LARK-02 的 acceptance 与 release dependency 均不因该例外释放，继续按各自既有 gate 与语义判断。

### 6.2 不可提前派发

如果 LARK-01 仍在修改 cache-clear callback、deadline 或错误分类，而 LARK-02 会直接使用这些 seam，则尚未形成可复用实现检查点。主 session 应继续保留 blocker，不提前派发 LARK-02。

### 6.3 检查点失效

如果并行开始后 LARK-01 必须改变已经声明可复用的合同、行为、错误语义、时序、兼容性或其他关键依赖事实，主 session 停止沿用受影响的 LARK-02 工作与旧证据，将相关 Ticket/Task 转为 `NEEDS-REVALIDATION`，完成 scoped revalidation 后再继续。

## 7. 实施与验证

本设计已新增两个 `dev-with-track` eval：ID 33 覆盖检查点正反例与失效处理，ID 34 覆盖 review/revise 中的检查点机会判断：

- 正例确认主 session 能基于已提交 seam 和局部证据提前派发 Ticket/Task implementation。
- 反例确认 seam 仍可能变化时不提前派发。
- 断言下游执行基线能够使用已提交实现，且 ER 可以由主 session 在派发时根据当前 diff 与证据补写。
- 断言 ER 如实记录理由，不伪造 `SATISFIED` / `DONE`，不释放 acceptance/release，不新增状态或 artifact。
- 断言关键依赖事实变化后，主 session 不再沿用受影响工作与旧证据，并对相关下游使用 `NEEDS-REVALIDATION` 和 scoped revalidation。
- 断言相关 review 未完成且可能改变 seam 时继续等待；相关 review 已收口到不影响 seam 的尾项时，上游 closure 与下游 implementation 可以并行。

验证结果：

- eval JSON 可解析，新增 ID 33 与 34 唯一。
- `git diff --check` 通过。
- `python -m unittest tests.test_impl_package_step8_evals` 仍有 apply 前已经存在的 3 个基线失败：`req-align` 缺旧断言标题、decision 模板缺旧字段、`dev-with-track` 既有 review token 与测试不一致；本次 apply 未新增失败，也不在本轮顺手修复这些旁支。
- 两轮只读 subagent review 已完成：design review 的 2 个 P2 和 apply review 的 1 个 P2 均已修正，实际检查点语义无剩余 finding。

## 8. Blind Opening 结论与 owner 取舍

2026-07-28 使用 `discuss-ledger --mode blind --agents codex,claude` 对本设计做独立审视。两位参与者均认可“规范性例外 + 主 session 裁量 + 不新增状态”的整体方向，并提出以下收紧点；owner 已确认全部吸收：

- 用实际剩余工作、open findings、diff 和风险判断安全性，不按“review closure / 观测性”等类别自动放行。
- 确认下游执行基线能够使用已提交实现，但不要求 checkpoint ID 或固定 commit 字段。
- 允许主 session 在派发时根据当前 diff 与证据补写 ER，不把既有 ER 质量变成新的前置 gate。
- 将失效条件从文件或接口变化扩展到合同、行为、错误语义、时序、兼容性及其他关键依赖事实变化。
- 关键依赖事实变化后停止沿用受影响工作与旧证据，使用现有 `NEEDS-REVALIDATION` 和 scoped reconciliation，不新增 scheduler 或通知协议。
- 明确下游 implementation 启动不表示原 dependency edge 已正式释放，也不能支持任何 acceptance 结论。

这些调整只收紧主 session 的判断输入与失效后果，没有改变原设计的文档分层或引入新机制。
