# Impl-Package Journey 验收与依赖重构提案

- 日期：2026-10-28
- 状态：Owner 已同意方向，待落地设计
- 范围：`plugin-marketplace/plugins/impl-package/` 的 req-align、impl-planning、plan-review、dev-with-track、do-review、`scripts/impl_package_runtime`，以及 `$dispatcher` 的相关规则
- 来源：KaiSpan `2026-10-27-sachkonto-memory-reuse` 包的运行复盘（9 Ticket、108 stable claim、44 次 dispatch、gate pass）

## 1. 要解决的问题

| # | 现象 | 根因 |
| --- | --- | --- |
| P1 | gate pass，但 Owner 最关心的两条旅程从未在真实页面连贯跑过；acceptance map 用两段局部证据拼成"满足"，gate 报告看不出缺口 | 验收单元是 Ticket claim，而"一个 Ticket = 一个用户终态"把跨终态的旅程切碎，旅程没有归属单元；Final Gate 只要求 Spec AC "能定位到 Ticket claim"（可追溯，不是执行）；composition contract 明确允许"较早证据与真实 E2E 组合支持同一 claim"；gate 模板只有技术 Reason |
| P2 | 44 次 dispatch 中 verify 23、fix 8、implement 12；前 2 小时耗在两张低风险 Ticket；包内文档约占总改动的四分之一到三分之一 | 开销 ∝ claim 数 × Ticket 数 × review 轨道数，不随风险变化；claim 原子化规则推高 claim 数（108 个，其中 20 个是每票重复的 INV）；formal review 触发清单在 SaaS 财务域几乎每票命中；`implementation` 边要求上游整票 `SATISFIED` 才放行下游，基础票的 review 循环卡住整包 |
| P3 | 并行 worker 共用测试库导致至少 4 次 PG 失败；执行者把改变用户可见结果的合同澄清写进 ER 后继续推进；截图日志在系统 Temp | Plan 已写"PG 串行"、Dispatcher 已有"会改变他人 oracle 的资源要隔离"，但只是散文，trail 的 `resource_keys` 是事后记录；合同修订没有独立台账，gate 不呈现；`do-review/scripts/review_ledger.py` 把 ledger 硬编码到 `%TEMP%` |

保留不动的做法：证据诚实（未运行写未运行、人工走查不冒充自动化）、finding 分级与 closure、source recheck、真实环境走查、本地资源清理纪律。

## 2. 核心模型

### 2.1 两层验收

验收从"Ticket claim"改为两层：

- **Journey**：Owner 语言写的有序步骤，承担产品验收。每个步骤边界有一个可观察点，每个步骤标注由哪些 Ticket 启用。一个 package 通常 2–5 条，只按最终形态定义一次。
- **规则矩阵**：解析表、状态矩阵、边界反例等细粒度规则，由测试文件直接承担，Spec 引用测试，不再逐条登记成 claim。

安全不变量（tenant、RBAC/privacy、幂等/完整性）提到 package 级，由 Safety review 与对应测试承担，不在每张 Ticket 重复登记。

Ticket 降为**施工单元**：负责建设内容、产出/消费的 seam 和自测，不再有验收状态。

### 2.2 走通进度（Journey reach）

- **走通进度**：在当前 HEAD 上，一条 Journey 从第 1 步开始能连续真实走通到第几步，写作"J1 走通 3/4"。
- **走通记录（reach run）**：一次从第 1 步起连续执行到当前可达步骤的运行，记录 revision、environment、每步观察结果和 artifact 路径。
- **只截断、不替换**：走通记录中的每一步都必须是真实入口、真实数据链，上一步的输出就是下一步的输入；不可达的后续步骤不跑，但中间任何一步不得用低层测试、mock 或另一次运行的结果代替。
- **观察点必须是产品已有的真实读取入口**（UI、API 或已有只读 inspector），不是直接查库或单元断言。
- 部分 Journey 不单独定义或登记，一律由最终 Journey 截断得到；不得按 Ticket 组合另行设计"小 journey"。

示例（J1：纠正后下一张账单用新科目）：

| 步骤 | 可观察点 | 启用 Ticket |
| --- | --- | --- |
| 1 税务端 final 一张账单 | 门店答案可经真实读取入口看到 | SMR-02 |
| 2 下一张同类账单 | 工作台预填该科目并显示"本门店记忆" | SMR-03 |
| 3 改为 4983 并 final | final 成功 | SMR-02/03 |
| 4 第三张同类账单 | 工作台预填 4983 | SMR-03 |

### 2.3 触发与用途

- Ticket 合入后若某条 Journey 的可达步骤前移，就跑一次走通记录。
- 走通记录是过程证据和早期证伪，同时作为执行中给 Owner 的进度视图；**Gate pass 只认最终形态的完整走通记录**。
- 人工浏览器走查只用于最终形态和 Owner 验收；过程中的走通记录应可自动重放（API 级或 Playwright），否则频繁重跑不可持续。

## 3. 依赖重构

取消 Ticket 之间的 `implementation | acceptance | release` 三种边，改为三个互相独立的结构：

| 决策 | 新结构 | 说明 |
| --- | --- | --- |
| 现在能派什么活 | **产物边**：Ticket 声明产出/消费的跨票 seam，名字复用 contract-design 的 entry point | 下游就绪 = 消费的 seam 已放行（见下），不等上游整票完成；只登记跨票交接的 seam |
| 何时算验收、失败波及谁 | **Journey 步骤映射** | 验收见 §2；走通记录在第 k 步失败时，第 k 步经过的 seam 标为**存疑（suspect）**，消费存疑 seam 的 Ticket 暂停新实现，其他 lane 照常；第 k 步重新走通后解除 |
| 上线前的执行顺序 | **发布顺序**：写在 Plan 全局执行边界，Gate 前本地执行一次并留记录 | 有用户可见后果的发布顺序写成一条 Journey |

### 3.1 seam 放行条件

基础件值得多花时间，但时间应花在下游真正依赖的部分。seam 放行需同时满足：

1. **形状冻结**：接口、数据身份、语义与合同一致；review 聚焦该 seam 的合同面。
2. **至少被真实走通一次**：下游第一步经真实入口用上它并可观察。
3. **已合入**。

不要求：内部边界矩阵全覆盖、全部 finding closure、PG 字节级证据齐全。这些仍是该 Ticket 自身的完成条件，只是不挡下游。

## 4. 共用治理改动

1. **环境隔离优先于串行**：每个 lane 按约定获得独立 PG schema/库，Dispatcher brief 必须携带；无法隔离时用独占 lease，持有期间 trail 拒绝记录冲突 dispatch。
2. **合同修订台账（Amendment）**：approval 后对 Decision/Spec/contract-design/Journey 文本的任何修改登记一条，执行者分类为"仅技术"或"用户可见"。用户可见修订可继续推进，但 Gate 只能给出 `pass-pending-owner-ack`，并在报告第一屏逐条列出。
3. **证据落在 package 内**：package 内设 artifacts 目录（可 gitignore），do-review ledger 默认写到该处；`package validate` 发现引用 Temp 路径时报 finding。

## 5. 各组件改动

| 组件 | 改动 |
| --- | --- |
| req-align（spec 模板 §7） | 拆成 Journey 与规则矩阵两部分；Journey 由 Owner 语言书写并随 Spec 审批 |
| impl-planning | 拆票判据从"终态计数"改为"每张 Ticket 推进某条 Journey 的可达步骤，并声明产出/消费的 seam"；第一个产物是 Journey harness（多租户 fixture、种子数据、测试身份、登录、可重放脚本）；排序优先让 Journey 尽早走通到第一个用户可见步骤，再横向补宽；删除 typed dependency 误判提醒 |
| plan-review | 新增检查：第一个用户可见步骤最早何时可走通；是否存在不推进任何 Journey 的 Ticket（应并入他票，或缺一条 Journey） |
| Ticket 模板 | 删除 AC stable claim、Safety Invariants 与 Blocking Dependencies；改为建设内容、产出/消费 seam、所推进的 Journey 步骤、自测 |
| composition contract / current-state | 删除"组合证据支持同一 claim"；Ticket 状态简化为 `PENDING → IMPLEMENTED`（已合入、自测与 delta review 通过）加 `RETIRED`；`evidenceIndex` 改为按 Journey 走通记录与风险评审索引；新增 seam 放行、存疑状态与 Amendment 记录 |
| runtime（engine） | `readyTickets` 改为基于 seam 放行；新增 Journey 可达步骤计算、走通记录、存疑传播；Gate 检查最终走通记录、发布顺序记录与 Amendment ack |
| dev-with-track | Verify and Gate 改为核对 Journey 与风险评审；formal review 触发从"每票命中清单"改为"seam 放行时的形状 review + 按风险的批次 review" |
| do-review | 触发点从每张 Ticket 改为 seam 合入或高风险批次；ledger 默认路径改到 package artifacts |
| gate 模板 | 第一屏为 Owner 验收视图：每条 Journey 的走通结果与 artifact、用户可见 Amendment、未覆盖边界；技术细节在后 |
| `$dispatcher` | 删除"主控核实后可把 implementation 边降为 acceptance"特例；资源按 lease/隔离键判断 |

## 6. 取舍

- **代价**：runtime schema 与状态机改动大，需决定旧 package 的兼容方式；harness 前置增加首日成本；Spec AC 粒度的逐条追溯变弱，由测试引用承担。
- **主要风险**：seam 已放行但语义错误，下游建在错误之上。新设计以"尽早走通 + 失败即冻结消费者"兜底，代价是偶发少量返工；旧设计以"等上游整票验收"兜底，代价是串行化。前提是 harness 已就绪、走通记录足够便宜；harness 未就绪时机制退化。

## 7. 落地前待验证

1. **seam 放行条件能否兜住**：把本次包 SMR-01/02 的全部 finding 逐条判断"若下游提前开工，修复是否迫使下游改代码"，并对照下游实际 diff。粗看 F-SMR01-1/2/3 属内部修正或证据缺口，F-SMR02-1（ConfirmMemory 输入形状）属形状问题；需完整分析后定稿 §3.1。
2. **旧 package 兼容**：不做迁移，本设计面向未来新包。
3. **Journey 数量与粒度**：用本次包回放，验证 2–5 条 Journey 加规则矩阵能否覆盖原 Spec AC-01～AC-21 且不遗漏 Owner 关心的结果。
