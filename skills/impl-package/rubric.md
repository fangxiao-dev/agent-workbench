---
target: skills/impl-package
updated: 2026-07-17
---

## 原则

- [已确认] Manual acceptance handoff 保持轻量：只固定真正必须的信息，把环境、身份、mock 边界和 teardown 等列为 optional，由 agent 按场景选择，不为低复杂度验收新增重型 artifact。
- [已确认] 优先用少量明确护栏消除高影响误判，不为内部依赖修正增加新阶段、artifact 或审批步骤。
- [待验证] 通用护栏以风险语义触发，项目技术名称只能作为例子；不得把某一项目的 provider、schema、archive、CLI 或存储结构固化为体系前提。（证据: R3）
- [待验证] JSON 与跨环节 contract 只承载追踪真正需要的最小事实；容易从单一权威输入可靠推理、且错误推理不会造成高影响 false PASS 的内容，不要求重复投影、严格 binding 或额外审批。（证据: R4, R7）
- [待验证] 机器可校验的过程状态（revision/binding/current、runtime state、交付物 hash 清单、gate 索引）归 `.impl-package/` 结构化文件，由轻量脚本原子维护并可 validate；Markdown 只保留判断、证据叙述与由脚本刷新或校验的投影，不用 prose 纪律维护结构化状态。JSON 字段准入测试：脚本能否在不理解业务语义的情况下写入和校验。（证据: R7）
- [待验证] 结构化状态引擎的数据策略应收敛到 skill-owned 版本化配置，便于后续解耦调整；append-only、CAS、active chain、package-local path、完整 content binding、HEAD/worktree 两相校验与 earned-artifact bijection 保持不可配置，避免策略调整弱化证据完整性。（证据: R8）
- [待验证] 变更失效范围必须与实际影响面一致：调整方向、证据修正和能力减法只复验直接受影响的 contract/artifact；只有业务结果、Acceptance Semantics、执行策略、Composition、安全约束或 mutation authority 发生实质变化时才重新规划或扩大复验。（证据: R4）
- [待验证] exact-blob 只保护 contract 语义而非排版噪声：可证明零语义影响的 editorial correction 更新同 alias binding evidence；无法证明时保守升级 revision 与 Gate。（证据: R5）
- [待验证] 优化优先增加可跨场景复用的判断约束，不以单一案例引入分类法、表格或新 artifact；只有现有语言无法表达真实高影响差异时才增加结构。（证据: R6）

## 决策记录（滚动，最近 ≤5 轮）

### R4 · 2026-07-15

- 采纳「分布式减负」— 用户明确选择把简化规则下沉到各 owning Skill/配置，中央只保留最小影响语义，不新建统一 Micro 阶段、模式或 artifact。
- 采纳「轻量 JSON contract」— 用户原话：JSON 用于环节间 contract 和追踪，应尽量轻量；容易推理的内容不需要过度严格。
- 采纳「影响范围内失效」— 用户明确反对环环相扣、轻微变动导致全量推倒重来；方向调整、证据修正和能力减法应局部复验，只有较大变动才重新规划。

### R5 · 2026-07-15

- 采纳「editorial rebinding」— 用户明确要求 exact-blob 区分 semantic revision 与 editorial correction：后者仅更新 binding evidence，不重跑 Gate；语义不明或实质变化仍按 Gate 路由。

### R6 · 2026-07-16

- 否决「输入角色分类」— 用户原话：太复杂、太 specific；优化应面向通用的方法论和约束。
- 采纳「交付路径与验证路径不得混同」— 在既有 Decision Gate 增加一条通用判断约束，避免为单一案例新增分类法、表格或 artifact。

### R7 · 2026-07-17

- 采纳「结构化状态层」方向 — 用户确认：机器可校验的过程状态进结构化文件并由轻量脚本登记/更新/校验，Markdown 只保留人要看懂的判断与索引投影；依据是 DATEV 实例中失守的全是 prose 纪律维护的状态簿记（S8/S9 binding 漏登记、plan header 过期、plan-contract-v1 比较从未执行、hash 链 prose 重述），判断性内容均维护良好。本轮只沉淀偏好，SKILL 与契约暂不修改。
- 同轮印证「轻量 JSON contract」原则 — 方案守界以最小事实为红线，语义与判断内容禁止入 JSON。
- 详细设计评估与采纳路径见 `docs/skill-design/impl-package-optimization-analysis-260717.md`。

### R8 · 2026-07-17

- 采纳「数据驱动状态引擎」— 用户要求脚本优化为数据驱动、配置收进 Impl-Package skill，方便后续解耦调整。状态 vocabulary、artifact discovery、字段/heading grammar、marker 与 projection format 进入单一版本化 JSON；CLI interface 不变，backfill 直接复用 canonical resolver。
- 校准「配置不越过安全内核」— 完整 gate entry span/content hash、append-only、CAS、active chain、package-local path、HEAD/worktree 两相校验与 earned-artifact bijection 不开放配置，配置 loader 对 schema、placeholder、capture group 与 heading 单行范围 fail closed。
