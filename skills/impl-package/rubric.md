---
target: skills/impl-package
updated: 2026-07-14
---

## 原则

- [已确认] Manual acceptance handoff 保持轻量：只固定真正必须的信息，把环境、身份、mock 边界和 teardown 等列为 optional，由 agent 按场景选择，不为低复杂度验收新增重型 artifact。
- [待验证] 优先用少量明确护栏消除高影响误判，不为内部依赖修正增加新阶段、artifact 或审批步骤。（证据: R2）
- [待验证] 通用护栏以风险语义触发，项目技术名称只能作为例子；不得把某一项目的 provider、schema、archive、CLI 或存储结构固化为体系前提。（证据: R3）

## 决策记录（滚动，最近 ≤5 轮）

### R1 · 2026-07-14

- 采纳「外部 revision binding」— 用 package-local manifest 消除 artifact 自身记录自身 commit SHA 的循环依赖。
- 采纳「派生 attempt lifecycle」— 不再手工维护 plan 的 Draft / Active / Frozen 状态，并显式识别 integrated-but-gate-open。
- 采纳「轻量 manual readiness 模板」— 用户原话：分 optional 和真正必须的，让 agent 自行挑选，不要做太重。
- 采纳「JSON 内部化、Markdown 自足交付」— JSON 可作为机器处理中间态或 sidecar；owner-facing Markdown 按职责提供可读投影，canonical handoff 无需打开 JSON 即可读懂当前 revision、lifecycle、integration 与 verification 结论。
- 采纳「本地 skill 中文行文」— 保留英文术语 token，不改 vendored 第三方 skill。
- 暂不实施「planning review 批量决策」— 用户将单独规划后续工作。

### R2 · 2026-07-14

- 采纳「readiness satisfiability 语义环检查」— 防止 AC evidence producer 被自身 ticket acceptance 阻塞。
- 采纳「机械修正自动继续」— typed edge、顺序与 evidence 投影修正不改变业务结果时不重复请求 owner 授权。
- 采纳「owner decision 业务结果测试」— 只有能说明选项导致不同业务结果时才暂停请求决定。
- 暂不实施「module-review finding 分类扩展」— 用户选择保持轻量，先用前三项护栏解决高影响误判。

### R3 · 2026-07-14

- 采纳「条件化 evidence-integrity 护栏」— 用户确认把本次返工模式沉淀进体系，但明确要求 external provider proof、`current`、原子发布、schema compatibility、CLI 等只能作为触发示例，不能成为其他项目的前提。
- 采纳「嵌入既有门禁」— 不新增阶段、artifact 或 owner 审批；规则分别进入 Spec、Plan、task review 与 dependency-release 的现有表面。
