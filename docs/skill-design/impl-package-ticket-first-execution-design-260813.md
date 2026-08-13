# Impl-Package：Ticket-first 与 Agent 动态执行 Skill Design

- 日期：2026-08-13
- 状态：方向已收敛，尚未实施
- 范围：Impl-Package 的 planning、Ticket、DAG、执行调度、状态投影与相关 Skill
- 触发实例：DATEV Mandant Profile Import 执行中出现“核心导入纵切迟迟不可见、后半程 Task DAG 串行化”的问题

## 1. 问题

现行 Impl-Package 同时把 Ticket 和 Task 作为持久化的一等对象：Ticket 表达纵向验收切片，Task DAG 表达横向执行依赖。这个模型在概念上区分了 acceptance 与 execution，但实际运行产生了三个结构性问题。

### 1.1 Ticket 没有真正拥有执行主线

计划发布后，下一动作主要由 Task dependency 和 Task state 决定。Ticket 虽然拥有 AC 和最终验收状态，却通常要等贡献 Task 全部完成后才进入实质验收，因此逐渐退化为末端 acceptance label。

结果是 package 对外显示多个 Task `DONE`，却无法直接回答最重要的问题：核心业务旅程是否已经运行并形成可观察结果。

### 1.2 静态 Task DAG 把局部依赖放大为整段串行

planning 阶段试图预先确定 ownership、并行边界、seam 和实现依赖。局部依赖一旦被表达成 Task 边，就会形成完整节点 barrier：后继 Task 必须等待前驱 Task `DONE`，即使真正依赖的部分只占约 10%。

DATEV 实例前半段存在若干并行 Task，后半段却收敛为近似单通道的 `T6 → T7 → T8 → T9`。这不是临时调度失误，而是静态 DAG 按设计生效的结果：它优化了预先可描述的 ownership，却没有持续发现运行期才显现的并行面。

### 1.3 完整生产合同压过了核心纵切

planning 以最终安全闭包组织执行顺序：数据隔离、文件安全、revision/CAS、幂等、approval、publication、恢复、API、Web、真实数据库和竞态验证共同占据关键路径。

这些约束本身成立，但“XLSX/CSV → 解析 → 规范化 → tenant-scoped staging 入库 → 读回”没有被提升为最早可验收的核心旅程。数据模型、parser 和 persistence 被分散到多个横向 Task，完整 producer-to-consumer evidence 又被推迟到最终集成阶段。局部 Task 可以陆续完成，owner 却一直看不到产品核心是否成立。

## 2. 被否定的承重假设

本设计不再接受以下默认前提：

1. Ticket 与 Task 都必须是持久化的一等规划对象。
2. 实现并行结构可以在 planning 阶段充分预知，并应冻结为 Task DAG。
3. 最终生产合同的依赖顺序应直接决定第一条可见交付路径。

这三个前提叠加后，把 Ticket 的纵向价值、Agent 的运行期判断和核心旅程的早期验证都让位给了静态执行图。

## 3. 收敛思路

### 3.1 Ticket 是唯一持久化的交付与验收单元

当一个 package earned Tickets 时，Ticket 同时承担：

- 一个可独立理解的纵向业务或系统结果；
- 可观察 acceptance criteria；
- acceptance evidence；
- 与其他 Ticket 的必要硬依赖；
- runtime acceptance state。

不再为同一个 attempt 另外创建持久化 Task、Task DAG、Task state 或 Task Handoff。复杂度、跨文件修改或需要多个 worker，都不能单独使一个工作项成为 Ticket。

小而线性的 package 可以没有 Ticket，由 Plan 直接承载目标、边界和验证；它同样不需要为了调度而创建 Task DAG。

### 3.2 DAG 提升到 Ticket 级，只表达硬依赖

Ticket DAG 只保存满足以下判断的边：没有前驱 Ticket 的某个稳定结果，后继 Ticket 的主体工作无法安全开始。

局部 seam、少量 foundation 或约 10% 的前置工作不形成整 Ticket dependency。执行 Agent可以先完成必要 seam，再让多个 Ticket 继续并行。共享生成目录、数据库、浏览器或其他单写资源只约束相应执行时段，不自动升级为 Ticket 依赖。

Ticket dependency 的目标是防止错误启动，不是提前描述全部实现顺序。

### 3.3 并行判断属于执行 Agent

planning 只定义纵向结果、硬依赖、边界与验证，不预先拥有实现拆分权。

执行时，Agent 基于当前 Ticket、实际代码事实和共享资源决定：

- 哪些工作留在主 session；
- 是否分发一个或多个 worker；
- 哪些 seam 需要先闭合；
- 哪些验证必须串行；
- worker 结果如何集成回 Ticket。

这里不引入 `Dynamic Work Unit`、`Subtask` 或其他新的 package 对象。一次 worker dispatch 只是运行时动作：没有编号、类型、状态机、持久文件或独立生命周期。必要的执行判断继续记录到既有 Execution Record；结果证据归属 Ticket 或 Gate。

### 3.4 核心纵切与 foundation 双轨推进

每个 material implementation plan 必须先指出最小核心旅程，以及它第一次产生真实可观察证据的位置。核心旅程按用户或系统价值组织，不能按 controller、service、repository、schema 等代码层组织。

执行时允许两条线并行：

- 核心线尽快跑通最小纵向结果；
- foundation 线补齐安全、权限、隔离、幂等、并发、契约和可维护性。

两条线通过最小稳定 seam 多次汇合，而不是等所有 foundation 完成后才第一次验证核心旅程。核心 evidence、受控集成 evidence 和最终 acceptance 可以逐步进入 Ticket 证据链；只有全部 AC 满足时 Ticket 才进入 `SATISFIED`，不新增中间 Ticket 状态。

### 3.5 Foundation 默认不 Earn Ticket

Foundation 只有同时满足下列条件时才成为独立 Ticket：

- 具有独立、稳定的使用者；
- 不依赖某一个业务纵切才能解释其价值；
- 有自己的端到端可观察验收结果；
- ownership 与生命周期确实独立；
- 已有实际消费者，而不是仅推测未来复用。

否则，foundation 由 Agent 在相关 Ticket 执行中安排 worker 完成，并把验证证据归入消费它的 Ticket。实现困难、修改面广或多人参与都不是独立 Ticket 的充分理由。

## 4. 收敛后的模型

### 4.1 物理状态

新模型只要求以下持久化执行表面：

```text
Implementation Package
├─ Plan
├─ Ticket set + Ticket DAG（仅 earned 时）
├─ Ticket acceptance state/evidence
├─ Execution Record / Progress projection
└─ Terminal Gate
```

没有 Task、Task DAG、Task runtime state、Task Handoff，也没有动态执行单元的物理表示。

### 4.2 执行流程

```text
选择已释放 Ticket
→ Agent 判断当前可并行面与必要 seam
→ 直接执行或分发 worker
→ 集成结果并取得阶段性 evidence
→ 满足全部 AC 后验收 Ticket
→ 所有 package claim 通过后写 Terminal Gate
```

物理状态回答“交付了什么、证据是什么”；Agent 调度回答“这一次怎么做”。二者不再通过 Task 层绑定。

## 5. Planning Skill 的行为变化

### 5.1 Core-first

`impl-planning` 必须先回答：

1. 用户真正要得到的核心结果是什么；
2. 最小哪条纵向旅程能够证明它成立；
3. 第一份真实 evidence 何时出现；
4. 哪些 foundation 必须先行，哪些可以并行加固；
5. 是否存在把完整生产闭包误当成第一交付物的风险。

计划不能只给出最终完整性地图；还必须让 owner 看见最早的核心价值检查点。若核心旅程只能在所有外围层完成后验证，planning 必须证明这是不可避免的硬依赖，而不是按架构层拆分造成的结果。

### 5.2 Ticket-first

需要多个独立 acceptance 结论时，planning 创建少量纵向 Ticket，并在 Ticket 之间只登记硬依赖。不再选择 `tickets/Task DAG` 四种 Composition，也不再把 coverage 映射到两套执行对象。

不需要 Ticket 时，Plan 直接进入 Agent 执行，不为并行或 ownership 创建持久化 Task。

### 5.3 Progressive evidence

计划验证应把核心 evidence 放在最早可执行的位置，并允许同一 Ticket 的 evidence 逐步累积。最终 Gate 仍要求同 revision、同环境和完整 claim coverage，但不能把“最终才可关闭”误写成“最终才能首次验收任何核心行为”。

## 6. Skill 影响面

| Surface | 目标变化 |
| --- | --- |
| `impl-package-composition-contract` | 移除 Ticket/Task 双轴 Composition；定义 Ticket-only 或 Plan-direct 模型；DAG 改为 Ticket 硬依赖 |
| `impl-planning` | 增加 core-first 判断；不再规划横向 Task DAG；验证计划必须给出最早核心 evidence |
| `to-tickets` | 拥有 Ticket set 与 Ticket DAG；强化纵向、独立验收和 hard-dependency admission |
| `create-task-dag` | 对 fresh package 退役；不再创建 Task 或 Task DAG |
| `subagent-driven-development` | 从当前 Plan/Ticket 和实际代码状态动态判断串并行；不依赖 Task artifact |
| `dispatch-bounded-task` | 保留为一次性 worker dispatch 路由；其 bounded input 不成为 package 对象或状态层 |
| `dev-with-track` | 以 Ticket/Plan 为恢复和推进单位；移除 Task state、Task readiness 与 Task Handoff 主路径 |
| state CLI / `progress.md` | fresh package 删除 Task execution axis，只投影 Ticket acceptance、checkpoint、blocker 与 Gate |
| templates / evals | 删除 Task/DAG 生成要求；增加 core-first、soft-dependency 并行与 foundation admission 场景 |

## 7. 验证设计

Skill 变更至少用以下提示验证行为是否真的改变，而不只是换术语：

1. **核心导入场景**：面对“定义数据模型、解析 XLSX/CSV 并加载”的需求，第一条 Ticket/evidence 必须覆盖文件到数据库读回；publication、Web 和竞态加固不能占据第一条可见路径。
2. **局部 foundation 场景**：两个 Ticket 只有少量 shared schema/seam 时，不建立整 Ticket barrier；Agent 先闭合 seam 后并行推进。
3. **复杂横向工作场景**：一个纵向 Ticket 涉及 schema、API、Web 和 tests 时，不据此创建四个持久化 Task；执行 Agent 可以并行分发 worker并把结果集成回同一 Ticket。
4. **Foundation admission 场景**：复杂但只有单一业务消费者的 foundation 不 Earn Ticket；具备独立消费者和端到端验收的共享能力才可成为 Ticket。
5. **小型改动场景**：无需多个 acceptance 结论时，不创建 Ticket 或 Task，Plan 直接驱动执行和 Gate。

失败信号包括：生成 Task ID/Task state/Task Handoff、把局部 seam 写成整 Ticket dependency、把核心旅程推迟到 terminal integration、或创建没有独立验收结果的 Foundation Ticket。

## 8. 迁移边界

- 新模型先用于 fresh package，不要求原地迁移正在执行的旧 package。
- 已发布 Task DAG 的 package 继续按其批准合同完成或在新的 patch attempt 显式升级；不能静默删除现有状态与证据。
- 首轮实施不新增兼容层之外的抽象，不把 worker dispatch 重新包装成另一种 Task。
- 先修改 composition、planning、Ticket 与 execution 主路径，再更新 state CLI、模板和 eval；只有端到端 fresh-package fixture 通过后才把新模型设为默认。

## 9. 收敛结论

Impl-Package 的持久化规划单元应从“Ticket + Task 双层”收敛为“Ticket-first”：

- Ticket 是唯一可持续跟踪的纵向交付与验收单元；
- DAG 只存在于 Ticket 级，只表达硬依赖；
- planning 先保护最小核心纵切和最早 evidence；
- foundation 与核心纵切并行推进，并阶段性汇合；
- Agent 在运行时自行判断 worker 分发与串并行；
- worker dispatch 不形成新的物理对象；
- Terminal Gate 继续负责 package 整体结论。

这次优化的目标不是减少一个文件名，而是把权力边界重新摆正：planning 拥有业务交付边界与验收合同，Ticket 拥有可观察结果，Agent 拥有实现拆分和并行调度。
