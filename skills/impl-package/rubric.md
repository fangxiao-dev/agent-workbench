---
target: skills/impl-package
updated: 2026-07-16
---

## 原则

- [已确认] Manual acceptance handoff 保持轻量：只固定真正必须的信息，把环境、身份、mock 边界和 teardown 等列为 optional，由 agent 按场景选择，不为低复杂度验收新增重型 artifact。
- [已确认] 优先用少量明确护栏消除高影响误判，不为内部依赖修正增加新阶段、artifact 或审批步骤。
- [待验证] 通用护栏以风险语义触发，项目技术名称只能作为例子；不得把某一项目的 provider、schema、archive、CLI 或存储结构固化为体系前提。（证据: R3）
- [待验证] JSON 与跨环节 contract 只承载追踪真正需要的最小事实；容易从单一权威输入可靠推理、且错误推理不会造成高影响 false PASS 的内容，不要求重复投影、严格 binding 或额外审批。（证据: R4）
- [待验证] 变更失效范围必须与实际影响面一致：调整方向、证据修正和能力减法只复验直接受影响的 contract/artifact；只有业务结果、Acceptance Semantics、执行策略、Composition、安全约束或 mutation authority 发生实质变化时才重新规划或扩大复验。（证据: R4）
- [待验证] exact-blob 只保护 contract 语义而非排版噪声：可证明零语义影响的 editorial correction 更新同 alias binding evidence；无法证明时保守升级 revision 与 Gate。（证据: R5）
- [待验证] 优化优先增加可跨场景复用的判断约束，不以单一案例引入分类法、表格或新 artifact；只有现有语言无法表达真实高影响差异时才增加结构。（证据: R6）

## 决策记录（滚动，最近 ≤5 轮）

### R2 · 2026-07-14

- 采纳「readiness satisfiability 语义环检查」— 防止 AC evidence producer 被自身 ticket acceptance 阻塞。
- 采纳「机械修正自动继续」— typed edge、顺序与 evidence 投影修正不改变业务结果时不重复请求 owner 授权。
- 采纳「owner decision 业务结果测试」— 只有能说明选项导致不同业务结果时才暂停请求决定。
- 暂不实施「module-review finding 分类扩展」— 用户选择保持轻量，先用前三项护栏解决高影响误判。

### R3 · 2026-07-14

- 采纳「条件化 evidence-integrity 护栏」— 用户确认把本次返工模式沉淀进体系，但明确要求 external provider proof、`current`、原子发布、schema compatibility、CLI 等只能作为触发示例，不能成为其他项目的前提。
- 采纳「嵌入既有门禁」— 不新增阶段、artifact 或 owner 审批；规则分别进入 Spec、Plan、task review 与 dependency-release 的现有表面。

### R4 · 2026-07-15

- 采纳「分布式减负」— 用户明确选择把简化规则下沉到各 owning Skill/配置，中央只保留最小影响语义，不新建统一 Micro 阶段、模式或 artifact。
- 采纳「轻量 JSON contract」— 用户原话：JSON 用于环节间 contract 和追踪，应尽量轻量；容易推理的内容不需要过度严格。
- 采纳「影响范围内失效」— 用户明确反对环环相扣、轻微变动导致全量推倒重来；方向调整、证据修正和能力减法应局部复验，只有较大变动才重新规划。

### R5 · 2026-07-15

- 采纳「editorial rebinding」— 用户明确要求 exact-blob 区分 semantic revision 与 editorial correction：后者仅更新 binding evidence，不重跑 Gate；语义不明或实质变化仍按 Gate 路由。

### R6 · 2026-07-16

- 否决「输入角色分类」— 用户原话：太复杂、太 specific；优化应面向通用的方法论和约束。
- 采纳「交付路径与验证路径不得混同」— 在既有 Design Gate 增加一条通用判断约束，避免为单一案例新增分类法、表格或 artifact。
