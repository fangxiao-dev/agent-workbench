# Codex Harness 内部设计基线

## 文档定位

本文是 Codex Harness/Crew 的内部 POC 存档，用于快速理解产品目标、脚本分层和成熟度原则。它不作为运行时入口，也不复制配置值；机器事实以当前 runtime policy、execution profiles、control、verifier result、cancel request 和 Eval Schema 为准。

## PRD

Codex Harness 为高能力 Agent 提供一个由 Orchestrator 驱动的薄能力宿主。Owner 通过 Broker 与持久 Orchestrator交流；Orchestrator 维护直属 Worker、assignment、workspace/branch、lease、Verifier 和 Owner gate 的全景，自主调用底层能力并向 Broker 通知重大调整；Worker 独立完成完整交付并自主管理 Subagent；Full assignment 由 Orchestrator按需调用独立只读 Verifier。目标是在相信 Agent 判断力的同时，让权限、写入隔离、依赖、Owner gate、事实验收和取消收口可审计。

成功结果具备以下特征：Broker 不越权产生 canonical 计划；assignment 对应完整责任边界而非每个流程步骤；run、fresh context、branch、worktree、Worker dispatch 和 assurance 相互独立；workspace/branch 是否新建或复用由 Orchestrator 显式决定，同时写入者数量只约束活跃写 lease 和隔离要求；Full acceptance 绑定独立 verifier；只有明确 cancel 才 interrupt，停止不确定时 fail closed。

系统不以固定 Worker 数量、固定 DAG、固定 topology 流程、固定 action 数量、固定 prompt 或逐节点工作流控制 Agent；不根据 ready、Worker success、acceptance 或局部 Owner request 自动串接下一项业务动作；不新增 child scheduler、daemon、跨 worktree promotion 系统；不自动 merge、release、cleanup、提权或执行不可逆外部 mutation。Orchestrator 主动通知影响 Owner 预期的重大调整，普通实现策略不逐项上报，只有越过授权边界才需要 Owner 批准。

## 脚本层设计

| 层 | 职责 |
| --- | --- |
| CLI/App Server transport | Codex command discovery、JSON-RPC、thread/turn、notification 和 interrupt；不理解 Crew 业务角色 |
| Role-turn runner | 统一启动、观察和取消 Orchestrator、Worker、Verifier turn；不做业务拆分 |
| Orchestrator controller | 唯一 canonical 业务 controller；向 Orchestrator提供全景、assignment、Worker、Owner、Verifier、acceptance、finish 与 cancel 能力，不自动编排它们 |
| Worker/workspace primitive | 按 Orchestrator 选择绑定 Worker 与 workspace，并做路径、branch、clean、ancestor、lease、ownership 和 handoff 检查 |
| Package adapter | 把 Impl-Package canonical 结果作为 assignment 输入与 gate，不创建第二状态源 |
| Canonical assets | 保存可机械维护的角色、状态、证据和协议事实；Markdown 只解释边界 |

Orchestrator 使用可组合能力查看全景、定义或修订 assignment、启动或继续 Worker、调用 Verifier、接受 assignment、请求或应用 Owner decision、finish 和 cancel。自然语言负责目标、拆分理由、调度策略、设计、内部步骤、纠偏和重大调整通知；DTO 只负责 identity、authority、dependency、workspace/lease、commit、verification、verifier、Owner decision、acceptance、cancel 和 terminal disposition。

## 核心原则

1. **角色单一控制权**：Broker 面向 Owner，Orchestrator 控制 run，Worker 控制 assignment，Subagent 只属于 Worker，Verifier 只提供独立证据。
2. **责任边界优先**：Package、implementation、review 和内部 T-step 在 ownership、权限和 acceptance 不变时保持一个 assignment。
3. **全景可见但不驱动**：Orchestrator 和 Broker 能看到直属 Worker 与执行布局；观察到的 topology 不自动决定下一步。
4. **运行维度独立**：fresh context、dispatch、worktree、branch、run 和 assurance 不能互相推导；物理 workspace/branch 由 Orchestrator决定，reuse 必须越过 committed、clean、ancestor、verification 和 accepted handoff gate。
5. **Git 写入最小授权**：Worker commit 只获得 linked worktree Git dir、object database 和 assignment-scoped branch ref/log；不放开整个 common `.git`，也不允许改写 sibling branch。
6. **结构化事实胜过自述**：Worker result、Git facts、验证结果、controller-owned verifier 和 acceptance 构成证据链。
7. **明确取消才 interrupt**：观察窗口和静默不是 timeout；sidecar cancel 由 active runner 处理，停止未知即 quarantine。
8. **Fail closed**：版本不兼容、profile 不可用、状态漂移、证据缺失、权限不明或资源未停止时不乐观继续。
9. **宿主中立和可复用**：基础 thread/turn 与 Git guard 可以被轻量 caller 复用，不强制加载完整 Harness policy。

## 可组合能力示例

以下是能力关系，不是固定六步流程。Orchestrator 可以按事实跳过、重复、交错或回退；controller 只在能力被显式调用时执行对应副作用。

| Orchestrator 意图 | Controller 提供的底层能力 | 不自动发生的后续 |
| --- | --- | --- |
| 建立或调整交付责任 | 定义/修订 assignment，更新 Crew intent 与 Broker notification | 不创建 workspace，不启动 Worker |
| 执行选定工作 | 对明确列出的 cohort 做全量 preflight 后 materialize 并启动 Worker | 不补齐其他 ready assignment，不后台调度下一批 |
| 纠偏或边界升级 | 继续同一 Worker、修订 assignment 或创建 Owner request | 局部 request 不阻断无依赖工作，notification 不等于批准 |
| 复核与验收 | 显式运行 Full Verifier，消费 controller-owned attempt，接受 assignment | Worker success 不自动 verifier，acceptance 不自动 finish |
| 收口或取消 | 显式 finish；或通过 sidecar 请求 active runner interrupt | 没有 terminal evidence 不宣称结束，停止未知即 quarantine |

Crew panorama 持续展示 capabilities、intent、observed Worker/workspace/lease/Verifier/Owner 状态和重大通知。它让 Orchestrator、Broker 与 Owner 看到全局，但不把 Worker 数量、workspace 数量或动作顺序固化成流程。单写者只限制同时活跃写 lease，一个 run 仍可累计多个 branch/worktree；多写者只有在 Orchestrator 显式选定 cohort 且 controller 验证 ownership 与隔离后才成立。

## Maturity vocabulary

`design_baseline` 表示策略语义已编码到 canonical asset 并通过 Schema/测试检查，但尚未证明所有声明入口、failure path 和真实后端都完整强制执行。

`runtime_enforced` 表示同一 policy version 在所有声明入口加载和拒绝，Full verifier、cancel、workspace handoff、failure evidence 与 terminal disposition 均由可复核运行证据闭合。

Maturity 是整份 policy 的 Owner-approved 原子状态；局部实现、文档更新、单测或 canary 通过都不能单独提升。当前仍保持 `design_baseline`；显式 selected cohort 并发、Full Verifier、finish 和 cancel 已接入 controller，跨 worktree promotion、外部 API assignment 和跨版本恢复继续作为未闭合边界。
