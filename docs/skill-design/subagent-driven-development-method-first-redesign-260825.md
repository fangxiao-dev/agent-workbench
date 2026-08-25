# `subagent-driven-development` 方法优先重设计

## 1. 文档状态

- 日期：2026-08-25。
- 状态：已实施；本轮补充 caller-selected worktree isolation，并收紧正向 ownership 表达。
- 目标：`plugin-marketplace/plugins/impl-package/skills/subagent-driven-development/`。
- 修订：`unified-subagent-worker-strategy-refactor-plan-260813.md` 中仍在使用的 worker-centric strategy、fresh invocation 和 resolver 合同。
- 实施边界：后续只修改 agent-workbench 的 Skill、references、evals、直接调用方、处境协议和合同测试；不修改业务项目代码，不修改用户级 Codex/Claude/Grok 状态，不直接编辑已安装 plugin cache。

## 2. 核心决定

`subagent-driven-development` 以以下方法主轴组织内容：

```text
Topic → dependency class → execution lane → lifecycle
```

具体 executor、model、provider 或 agent profile 由 Owner 显式选择或宿主原生能力解析。Skill 提供这些方法判断：

1. 当前 bounded work 属于哪个 Topic；
2. 哪些依赖是真正的实现地基，哪些只是验收结论点；
3. 什么可以现在执行，什么可以作为下一步前置并行准备；
4. 当前或新隔离 worktree 如何分开文件 ownership，以及哪些运行资源要求隔离或串行；
5. 同 Topic 的 worker 何时复用、何时退役；
6. 哪些局部结果可以交给主 session 集成，哪些仍需 review 或验证。

原生 subagent 提供派发、消息、等待、中断和恢复等基本控制；SDD 聚焦 Topic、dependency、lane 与 lifecycle。

## 3. Owner 已批准的原则

### 3.1 Acceptance 是结论点，不天然是阻断点

Acceptance Gate 和 Checkpoint 阻止的是正式验收、evidence 采信与状态宣称，不自动阻止下一步的隔离准备。

环境启动、fixture、权限、身份、数据准备和 test carrier 在满足以下条件时可以提前并行：

- 不依赖尚未稳定的业务语义；
- 资源与当前工作隔离，或有明确串行顺序；
- 结果可回收且有 cleanup owner；
- 不把准备结果提前宣称为 acceptance evidence。

主控在等待 worker 或 Gate 时应做一次 look-ahead scan，寻找下一步可安全准备的前置，而不是把所有验收依赖解释成 dispatch blocker。

### 3.2 Foundation dependency 优先稳定

实现或材料 seam 是硬地基。下游实现会绑定其语义、数据形状或持久化合同的，必须先等待地基稳定，避免大规模返工。

依赖判断分为：

| 类型 | 阻止的动作 | 可提前进行的工作 |
| --- | --- | --- |
| Foundation dependency | 依赖该语义的下游实现 | 与结果无关且资源隔离的准备 |
| Acceptance dependency | 正式验收、evidence 采信、Ticket/Gate 状态宣称 | 环境、fixture、权限、数据和测试载体准备 |
| Resource dependency | 同时执行 | 可隔离则并行，不可隔离则串行 |
| Authorization dependency | 未获授权的 mutation 或外部副作用 | 只读调查和不越权准备 |

### 3.3 Worker 复用以 Topic lane 为边界

Worker 不是常驻角色。复用只服务于一个仍在进行的 Topic 或 test campaign：

| Lane | 可复用范围 | 独立性 | 退役条件 |
| --- | --- | --- | --- |
| Work lane | investigate → implement → fix | 拥有同一 Topic 的实现上下文与 write ownership | Topic closure、scope 实质变化、ownership 变化、上下文污染或持续卡住 |
| Review lane | initial review → finding recheck | 必须独立于 work lane；同 Topic 内可复用 reviewer | Topic closure、review scope 实质变化或 reviewer 失去独立性 |
| Test lane | 同一 test campaign 的长脚本、重跑与异常收集 | 不承担业务判断或修复 | campaign 结束、环境/比较点变化或结果已交付 |

新 Topic 使用 fresh worker；同一 Topic/lane 连续且上下文可信时复用。

独立 review 由 reviewer 与 implementer 的 lane 隔离保证；同一 Topic 的 reviewer 可以承担 recheck。Fix finding 默认回到同 Topic work lane；上下文不可采信、方向需要全新视角或 ownership 变化时换 fresh fixer。

### 3.4 Worktree 是 caller-selected isolation

每个 bounded Topic 可以使用当前 worktree，也可以使用新隔离 worktree。caller 根据文件 ownership 与资源交叉决定选择、创建和生命周期；能用独立 worktree 消除的文件交叉继续派发。

Worktree 只隔离文件写入。DB、端口、测试数据、输出目录和外部记录分别验证；仍共享可变运行资源时保持串行并指定 cleanup owner。

## 4. 当前合同腐化审计

### 4.1 Strategy 过度绑定 executor

当前入口要求每次启动前显式填写 `worker`，并通过 `worker-resolver.md` 定义 `$grok-worker`、`@luna-worker`、直接 model/profile、prompt 和 fallback。这些是用户或宿主 policy，不是主控开发方法论。

终态不再要求 SDD strategy 输出具体 worker。调用后可以在 trail/result 中记录实际 executor，作为追踪事实；只有 Owner 显式 override 时才保留 executor constraint。

### 4.2 Mode 合同互相矛盾

- `SKILL.md` 只列 `investigate | implement | fix | review`；
- `AGENTS.md` 与 `dev-with-track/situations.yaml` 使用 `verify`；
- 当前 `review` 同时表示测试命令、普通检查和独立代码审查；
- `mode-contracts.md` 又单独定义 reviewer，职责与 `do-review` 重叠。

终态使用 `investigate | implement | fix | verify` 描述 worker 执行。独立审查由 `do-review` 拥有；SDD 只判断是否需要 review 及其局部/收口边界，不复制 reviewer 输出合同。

### 4.3 Fresh 规则违背 Topic 上下文管理

当前正文、resolver、review gate、protocols 和 evals 多处要求：每个 slice fresh、每个 finding fresh fixer、每次 reviewer fresh。这把进程独立性误当成质量保证，丢弃了同 Topic 的有效上下文，并容易形成永久换人但没有生命周期管理的 worker 流水线。

终态以 Topic lane 决定复用；fresh 是新 Topic、上下文失效或独立性要求的结果，不是每一步的默认仪式。

### 4.4 Worker envelope 多数没有消费者

`fallback_from`、`session_id`、`finding_origin`、完整 artifacts 数组和 resolver-specific status 主要由字符串测试保护，没有 runtime parser 消费。真正被处境表和 state 投影使用的是：

- `DONE | BLOCKED | INCOMPLETE`；
- `EVIDENCE_SUFFICIENT | EVIDENCE_GAP`；
- `PENDING_REVIEW | PASSED`；
- `checkpoint | closure`。

终态只保留这些稳定事实，由主 session 把原生 worker 结果归一化后写入 trail。Skill 不再要求 worker 手工返回一份完整 YAML envelope。

### 4.5 固定输出格式是无消费者合同

Investigate 的固定六行、reviewer 的固定三段、implement brief 的精确字段数量都没有 parser 消费。保留 cause、boundary、unresolved fact、ownership 和 verification 等语义要求即可，不再固定版式。

### 4.6 Progress File 重复宿主能力

当前源码 `SKILL.md` 引用 `assets/templates/progress-file.md`，但该 asset 尚未纳入 tracked source；提交态存在断 pointer。模板还包含 `subagent_codex`、`subagent_grok`、background job、轮询和 kill 等宿主操作，并要求 worker 写 `<package>/.impl-package/progress/`。

终态从 SDD 删除 Progress File。宿主原生进度消息、任务状态和中断能力直接使用；若 DSH 仍需要文件式 tick，由 DSH 自己拥有为可选观察机制，不成为所有 worker 的写入合同。

### 4.7 Parallel admission 只认 ready Ticket

当前 `parallel-work-admission.md` 明确拒绝发现候选，只在 `readyTickets` 已释放后判断资源。这无法表示“Ticket 尚未可验收，但下一步 fixture 可以先准备”。

终态仍由 `dev-with-track` 拥有 Ticket 发现和依赖状态，但 SDD 对调用者给出的当前工作与一步前瞻准备执行 dependency classification 和 resource admission。

### 4.8 Evals 与测试正在保护旧文案

当前 evals 硬编码 `$grok-worker`、fresh fixer、每 slice fresh 和固定输出字段；合同测试主要断言字符串存在。DSH 文档已经登记 provider 断言过时。

终态测试行为，不保护具体措辞或 provider 名称。

## 5. 目标主流程

新的 `SKILL.md` 应保持短小，并让主控按以下顺序判断：

### Step 1 · 定义 Topic

确定 bounded outcome、ownership、禁改范围、当前 comparison point 和 Topic closure 条件。完成标准：主控能够判断某个后续动作是否仍属于同一 Topic。

### Step 2 · 分类依赖

区分 foundation、acceptance、resource 和 authorization dependency。完成标准：明确哪些工作现在不可开始，哪些只是不能验收，哪些可以提前准备。

### Step 3 · 形成当前批次

优先调度 foundation；并行加入不会绑定未稳定语义的一步前瞻准备。共享资源能隔离则并行，不能隔离则串行，并记录 ownership 与 cleanup owner。完成标准：不存在两个 worker 同时拥有同一可变资源。

### Step 4 · 选择 lane 与生命周期

为当前动作选择 work、review 或 test lane；判断 fresh、同 Topic 复用或退役。完成标准：复用理由来自 Topic 连续性，不来自 worker 空闲或角色名称。

### Step 5 · 消费结果并重排

主 session 核对可归因 diff、evidence、residue 和 review requirement，完成集成后重新扫描 foundation 与下一步准备。完成标准：局部 DONE 不被解释为 Ticket 或 package 完成，等待前已执行 look-ahead scan。

## 6. 保留、迁移和删除

### 6.1 `SKILL.md` 保留

- Topic boundary；
- 四类 dependency；
- foundation-first 与 acceptance-not-blocker；
- work/review/test lane 生命周期；
- 共享资源隔离或串行；
- material risk 需要独立 review；
- 主 session 最终集成、evidence、Ticket acceptance 和 Gate 归属。

### 6.2 删除或退休

- `references/worker-resolver.md`；
- `references/mode-contracts.md`；
- `assets/templates/progress-file.md` 及 SDD pointer；
- provider-specific Grok/Luna/default fallback；
- 固定 Worker envelope；
- 固定 investigate/reviewer 输出版式；
- 每 slice、每 finding、每 recheck 必须 fresh 的规则。

### 6.3 收缩或迁移

- `parallel-work-admission.md`：重写为 dependency/resource admission，或压回 `SKILL.md`；
- `review-gate.md`：只保留 material-risk 与 `PENDING_REVIEW` 两条不变量，review topology/finding closure 归 `do-review`；
- provider 解析和 executor fallback：归宿主原生能力、preset 或实际 worker Skill；
- DSH progress tick：如仍有价值，由 DSH plugin 自己拥有，不从 SDD 强制写 package。

## 7. 直接调用方迁移

已同步的直接合同：

- `AGENTS.md`：Dispatcher 与 SDD 作为平级指导；worktree 选择在 SDD 内由 caller 决定；
- `dev-with-track/SKILL.md`：业务控制循环前置，拥有 Ticket readiness、state 和 Gate，并消费 Dispatcher/SDD 结果；
- `scripts/impl_package_runtime/protocols.json`：finding 回到同 Topic work lane，保留 `PENDING_REVIEW` 和真实 outcome；
- `dispatch-fix`：按 Topic grouping 和 lane 生命周期工作；
- `do-review`：拥有 reviewer topology、comparison point、finding closure 和 terminal review。

## 8. Evals 与验证

### 8.1 新行为场景

旧 14 个 provider/字段 eval 缩为以下核心场景：

1. foundation 未稳定时，下游语义实现等待，但无关 fixture/environment prep 可隔离并行；
2. acceptance edge 未释放时，不允许 SATISFIED/正式验收，但允许一步前瞻准备；
3. 同 Topic work lane 在 implement 后收到 finding，复用原 implementer 修复；
4. 独立 reviewer 在同 Topic recheck 中复用，且始终独立于 work lane；
5. 新 Topic 使用 fresh worker，旧 Topic worker 退役；
6. 同一 test campaign 可有限复用 wrapper，campaign 结束退役；
7. 共享 DB/端口/worktree 无法隔离时串行，有独立 worktree/run-owned DB 时并行；
8. worker 局部 DONE 或 review checkpoint PASS 不得提升为 Ticket/package completion。

### 8.2 合同测试

测试应验证：

- Skill 不包含具体 provider 默认或原生调用教程；
- mode 集合与 situations/callers 一致；
- 不存在 tracked file 指向 untracked/missing resource；
- Topic lane reuse/retire 和 dependency classification 存在；
- runtime 真正消费的 outcome/review state 保持；
- 不再断言无消费者的 envelope 字段或固定文案；
- L0 运行 SDD focused tests/evals/Skill validator；
- L1 运行 dev-with-track、do-review、dispatch-fix、thread-harness 与 DSH 直接合同测试后停止。

## 9. Rubric 更新

`subagent-driven-development/rubric.md` 已记录：

- 将“每个 finding fresh fixer”和“每个 bounded unit 默认 fresh”改为 Topic/lane 生命周期；
- 删除或退休默认 Grok→Luna fallback 的方法论偏好；
- 将显式 worker strategy 改为 provider-neutral、method-first；
- 记录 Acceptance Gate 是结论点、不是自动 dispatch blocker；
- 记录 Topic closure 后 worker 必须退役，不形成常驻班底。
- 记录 caller 可选择当前或新隔离 worktree，并逐项判断运行资源。

这些是 Owner 本轮直接确认的原则，不作为模型推断写入。

## 10. 实施完成标准

只有同时满足以下条件才算本重设计实施完成：

1. `SKILL.md` 已以 Topic/dependency/lane/lifecycle 为主路径；
2. provider-specific resolver、固定 envelope 和 Progress File 已从 SDD 移除；
3. acceptance-not-blocker 与 foundation-first 在真实 eval 中均可观察；
4. implement/fix、review/recheck、test campaign 的复用与退役边界均有行为测试；
5. `dev-with-track`、situations、protocols、dispatch-fix 和 do-review 不再复制或冲突；
6. runtime 仍能正确识别 `DONE/BLOCKED/INCOMPLETE` 与 `PENDING_REVIEW/PASSED`；
7. 所有 Skill pointer 指向 tracked、存在且按条件加载的资源；
8. L0/L1 通过，未用全仓测试替代聚焦证据；
9. plugin source、DSH/preset 和后续安装产物由正常版本发布流程同步，不直接手改用户 cache。
