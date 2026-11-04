# Impl-Package Journey 验收与依赖重构提案

- 日期：2026-10-28
- 状态：Owner 已同意方向；第一期待写实现计划，第二期为观测后的决策点
- 范围：`plugin-marketplace/plugins/impl-package/` 的 req-align、impl-planning、plan-review、dev-with-track、do-review、`scripts/impl_package_runtime`，以及 `$dispatcher` 的相关规则
- 来源：KaiSpan `2026-10-27-sachkonto-memory-reuse` 包的运行复盘（9 Ticket、108 stable claim、44 次 dispatch、gate pass）

## 1. 要解决的问题

| # | 现象 | 根因 |
| --- | --- | --- |
| P1 | gate pass，但 Owner 最关心的两条旅程从未在真实页面连贯跑过；acceptance map 用两段局部证据拼成"满足"，gate 报告看不出缺口 | 验收单元是 Ticket claim，而"一个 Ticket = 一个用户终态"把跨终态的旅程切碎，旅程没有归属单元；Final Gate 只要求 Spec AC "能定位到 Ticket claim"（可追溯，不是执行）；composition contract 明确允许"较早证据与真实 E2E 组合支持同一 claim"；gate 模板只有技术 Reason |
| P2 | 44 次 dispatch 中 verify 23、fix 8、implement 12；前 2 小时耗在两张低风险 Ticket；包内文档约占总改动的四分之一到三分之一 | 开销 ∝ claim 数 × Ticket 数 × review 轨道数，不随风险变化；claim 原子化规则推高 claim 数（108 个，其中 20 个是每票重复的 INV）；formal review 触发清单在 SaaS 财务域几乎每票命中；`implementation` 边要求上游整票 `SATISFIED` 才放行下游，基础票的 review 循环卡住整包 |
| P3 | 并行 worker 共用测试库导致至少 4 次 PG 失败；执行者把改变用户可见结果的合同澄清写进 ER 后继续推进；截图日志在系统 Temp | Plan 已写"PG 串行"、Dispatcher 已有"会改变他人 oracle 的资源要隔离"，但只是散文，trail 的 `resource_keys` 是事后记录；合同修订没有独立台账，gate 不呈现；`do-review/scripts/review_ledger.py` 把 ledger 硬编码到 `%TEMP%` |

保留不动的做法：证据诚实（未运行写未运行、人工走查不冒充自动化）、finding 分级与 closure、source recheck、真实环境走查、本地资源清理纪律。

## 2. 总体方案：分两期交付

旧 package 兼容：不做迁移，本设计面向未来新包。既有 package 继续使用原规则，两期设计的兼容边界也不以迁移旧包为前提。

| 期 | 目标 | 交付内容 | 明确不等待的内容 |
| --- | --- | --- | --- |
| 第一期 | 尽早看到真实产品结果，最终不漏验收 | Journey 验收与走通记录、walking skeleton 排序、Gate 的 Owner 视图、按测试套件登记规则/安全证据并替代旧 claim 检查、资源 lease 前置、Amendment 复用 `blocked`、证据落 package | seam 状态机重构、按 seam 放行、review 批次化 |
| 第二期（决策点） | 改善放行粒度 | seam 放行重构、review 触发改为 seam/风险批次、closure 文档批次化 | 第一期的 Journey、Gate、套件证据和治理不回退 |

当前 `implementation` 边要求下游等待上游整票 `SATISFIED`，其中包含 review、fix、closure 和全部证据；本次包在 SMR-03 开始实现前，SMR-01/02 已消耗 17/44 次 dispatch。第一期保留这条现有边，靠 impl-planning 排序、够用的 harness 和每次合入后的走通记录先交付产品结果。

第一期的各项必须同时上线：只加 Journey 不退 claim 会增加记账，只退 claim 不加套件核对会留下 Gate 缺口。第二期不是承诺路线，而是决策点：第一期在 1～2 个真实新包上运行后，依据 §4.3 的观测指标与回放验证决定是否实施；回放验证不阻塞第一期。

可先于第一期单独落地的治理小修：`review_ledger.py` 默认路径从系统 Temp 改到 package 内；资源 lease 前置到启动 worker 之前（§3.5）。

## 3. 第一期：先建立真实产品闭环

### 3.1 Journey 与走通记录

Journey 用 Owner 语言描述有序业务步骤，按最终形态定义一次；2–5 条是经验值，不设上限。每个步骤必须声明必经的操作入口和观察表面。承诺落在页面上的步骤必须有浏览器证据，允许用 Playwright 自动化；API 级重放只证明它实际覆盖的部分，不能替代页面承诺。

走通记录从第 1 步开始连续执行，记录 revision、environment、每一步的预期与实际观察、artifact 路径；上一步输出必须成为下一步输入，不用低层测试、mock 或另一轮运行结果拼接不可达步骤。代码受影响后，旧走通记录标为待复验，Gate 只接受最终实现版本的有效记录。失败恢复必须从第 1 步重新连续跑通，不能只重跑失败步骤。

### 3.2 Walking skeleton 与 Ticket 排序

walking skeleton 的目标是首个完整、可见的业务结果，不是先交付一套基础设施。impl-planning 将首张 Ticket 排成窄而完整，并尽早走通到第一个用户可见步骤；第一期继续使用现有 `implementation` 边即可实现，不依赖 seam 状态机重构。每次合入后都追加一次走通记录，可达步骤前移时更新 reach。

harness 是支撑工具，不得先膨胀成庞大的基础设施 Ticket。优先复用现有登录、fixture 和测试入口，只建设能跑通第一条窄路径的部分。Ticket 的拆分判据改为“启用某个 Journey 步骤，或保障某条已登记的规则/安全测试”；harness、migration、安全加固类 Ticket 均合法，不因层次相近而强行合票。

### 3.3 两层 Gate

Spec 保留规则含义和必需测试套件清单，套件清单属于 req-align 审批内容。每个规则或安全套件登记其入口、覆盖范围、revision、environment、结果和 artifact，按套件登记，不恢复逐 claim 记账；安全不变量由包级安全套件承担。

Gate 在最终实现版本上同时核对四类结果：Journey 完整走通记录、规则与安全测试套件结果、有效的风险 review 结果、发布顺序记录。Gate 第一屏使用 Owner 语言，例如“J1 走通 4/4、J2 走通 3/4、1 条用户可见修订待确认”，技术明细和套件 artifact 放在后面。

### 3.4 旧 claim 检查的退出关系

第一期定义替代关系，既不与旧检查叠加，也不直接删除旧检查。替代只适用于新 package；既有 package 继续走原规则。

| 旧检查 | 新 package 的接替方式 |
| --- | --- |
| Ticket AC stable claim | Journey 完整走通记录与规则测试套件结果 |
| Safety Invariants claim | 包级安全测试套件结果 |
| per-claim evidence record | 按套件登记结果及其 artifact |
| acceptance map | Journey、规则套件、安全套件的覆盖表 |
| Ticket `SATISFIED` 的 claim 覆盖要求 | 已合入、所负责套件通过、所需 review 通过 |
| Final Gate“Spec AC 能定位到 Ticket claim” | Gate 两层核对：Journey/套件覆盖，加最终版本的 review、发布顺序和安全结果 |

第一期 Ticket 仍保留 `SATISFIED`，以驱动现有 `implementation` 边放行；其完成依据从 claim 覆盖改为“已合入 + 所负责套件通过 + 所需 review 通过”。

### 3.5 三项治理

1. **资源 lease 前置。** 独占资源必须在启动 worker 之前取得；派发失败立即释放；worker 结束并完成清理后释放。隔离优先于 lease，每个 lane 优先使用独立 schema/库。trail 只记录结果，不承担互斥；现有 trail dispatch 要求真实 receipt、`outcome=RUNNING` 且 `returned=false`，不能把事后记账当成资源保护。
2. **Amendment 复用非终态 `blocked`。** 不新增 `pass-pending-owner-ack`。批准后的合同修订进入 Amendment 台账，Gate 第一屏列出待确认修订；`blocked` 只阻止最终收口，不让 package 停工，已授权且不依赖待确认语义的工作继续。Owner 确认绑定具体修订版本；确认后再次发生语义修改，重新进入待确认列表。
3. **证据落 package。** 走通记录、套件结果、风险 review、closure 和 review ledger 都保存到 package 的约定目录；禁止以系统 Temp 作为唯一证据来源。验证时发现 Temp 引用就报告缺口。

## 4. 第二期：重构放行粒度与 review 触发

### 4.1 Seam 放行

第二期不再要求“下游第一步已经用上 seam”。放行循环改为：

1. 冻结接口、数据身份、语义和合同，并完成针对 seam 承诺的形状检查。
2. 经产品已有的真实读取入口观察该 seam；没有现成入口时，把最小消费路径纳入 seam 自己的交付范围。
3. 合入后才标记 seam 可放行。

读取入口观察只证明该入口实际覆盖的承诺，读得到不等于消费者用对了；消费端转换、权限、事务等风险仍需判断是否需要最小消费路径。

放行判据是 finding 是否破坏 seam 的承诺或安全不变量，不是下游是否需要改代码。相关缺陷必须在放行前闭合，无关缺陷可以后补。F-SMR01-2 的内部分页截断可能让本不应通过的 final 被封存，说明“内部修正”也可能破坏安全边界。F-SMR02-1 的 ConfirmMemory 形状修正发生在 SMR-02 内部，不能作为跨票提前放行样本。

Journey 某一步失败时，将该步骤经过的 seam 标为“存疑”，消费该 seam 的 Ticket 暂停新的实现；恢复时仍从第 1 步重新连续跑通，不能只重跑失败步骤。受影响代码变化同样使旧“存疑解除”记录待复验。

### 4.2 Review 批次

formal review 的触发从“每张 Ticket 命中清单”改为 seam 合入时的形状 review，以及按共享风险组织的 review 批次；finding closure 与 closure 文档随批次复用。review 强度不降低，风险不相关的 Ticket 不因同批次而获得无证据放行。

### 4.3 决策依据：观测指标与回放验证

第一期运行的前 1～2 个新包记录三项指标：

1. **关键路径等待**：首个下游 Ticket 开始实现前，上游已消耗的 dispatch 次数与时间（本次基线 17/44）。
2. **上游 finding 性质**：上游 review finding 中破坏 seam 承诺或安全不变量的比例。比例高说明严格放行有效，第二期价值低。
3. **走通记录成本**：单次走通记录的耗时与稳定性。成本高则"尽早走通 + 失败即冻结消费者"的兜底不成立。

排序优化后等待已不明显，或上游 finding 多数触及 seam 承诺时，不实施第二期。否则再完成以下两项回放：

1. **覆盖回放。** 完成 Spec AC-01～AC-21 到 Journey/规则测试的覆盖对应，保留冻结文件字节、双端 UI、权限、并发和事务回滚的真实验证要求，确认细粒度规则没有因退出 claim 记账而失去 oracle。
2. **放行与 review 回放。** 以本次包的真实 Ticket、finding、review、closure 和发布顺序重放 seam 放行及风险批次，判断哪些 finding 实际破坏 seam 承诺/安全不变量，验证提前放行不会把错误传给消费者，并核对关键路径、review 次数和 closure 文档是否确实减少。

两项回放均支持后再实现第二期的 seam 状态机和 review 批次；在此之前第一期按现有 `implementation` 边执行。

## 5. 各组件改动

### 第一期

| 组件 | 改动 |
| --- | --- |
| req-align | Spec 分为 Journey、规则矩阵和必需测试套件清单；套件清单随 req-align 一起审批，保留规则含义与安全不变量语义。 |
| impl-planning | 按“启用 Journey 步骤或保障已登记套件”拆票；首张 Ticket 窄而完整，排序尽早到达第一个用户可见步骤；harness 只建设第一条窄路径所需部分，继续使用现有 `implementation` 边。 |
| plan-review | 检查第一条用户可见步骤何时可走通、每个步骤的操作入口/观察表面、套件清单是否完整、是否存在不推进 Journey 也不保障套件的 Ticket。 |
| Ticket 模板 | 写建设内容、启用的 Journey 步骤或负责的规则/安全套件、产出/消费 seam、自测与所需 review；保留 `SATISFIED`，但不再以 claim 覆盖作为完成依据。 |
| composition contract / current-state | 为新 package 定义 Journey 走通、套件结果、包级安全证据、Amendment 和 package 内 artifact；旧 package 不迁移。 |
| runtime（engine） | 保留现有 Ticket/`implementation` readiness 和 `SATISFIED` 驱动方式；Gate 增加两层核对、最终 revision 有效性、发布顺序和 Amendment 首屏信息，不引入 seam 状态机。 |
| dev-with-track | 合入后记录走通结果，维护记录时效、套件结果、风险 review、Amendment 和 Gate；完成依据按“合入 + 套件通过 + review 通过”判断。 |
| do-review | 第一期保持 per-Ticket review 强度，review ledger 和 closure 证据迁入 package，不以 claim 账本扩张 review 范围。 |
| gate 模板 | 第一屏展示 Journey 进度、完整走通 artifact、套件结果、风险 review、发布顺序和待确认 Amendment，使用产品语言。 |
| `$dispatcher` | 派发前取得资源 lease，失败释放，worker 清理后释放；独立 schema/库优先，trail 只记录结果。 |

### 第二期

| 组件 | 改动 |
| --- | --- |
| req-align | 根据两项回放固定 seam 承诺、最小消费路径和风险批次边界；不把下游首次使用写成放行条件。 |
| impl-planning | 将 seam 产出/消费和最小消费路径纳入计划；按 seam 可放行状态安排下游，不再把上游整票 `SATISFIED` 作为唯一开工条件。 |
| plan-review | 审查 seam 观察入口、消费端转换/权限/事务风险、finding 与 seam 承诺的关系，以及 review 批次是否覆盖实际风险。 |
| Ticket 模板 | 增加 seam 放行所需的形状/真实读取观察和存疑影响；区分阻断 seam 的 finding 与无关后补项。 |
| composition contract / current-state | 增加 seam 放行、存疑传播和恢复时效的状态/边界；保留 Ticket 状态用于收口，不把 trail 当互斥或放行事实。 |
| runtime（engine） | `readyTickets` 改为按已放行 seam 判断；实现 seam 放行循环、存疑传播、从第 1 步恢复复验和批次 review 结果核对。 |
| dev-with-track | 按 seam 承诺和安全不变量判断 finding 是否阻断放行；存疑解除只接受最终版本的连续走通记录。 |
| do-review | 在 seam 合入和共享风险批次触发 review，批次复用有效 comparison point、finding closure 和 closure 文档。 |
| gate 模板 | 增加 seam 放行矩阵、存疑项和批次 review 结果；Owner 视图仍置于第一屏。 |
| `$dispatcher` | 沿用第一期 lease/隔离规则；按 seam 和风险批次编排 review，不为无关 Ticket 建立额外 review 轨道。 |

## 6. 收益预期

### 第一期

- 记账分为两块：验收记账从本次的 108 claim、190 evidence record、`evidence/` 约 34 个文件、`state.json` 2033 行大幅减少；review 记账（`execution/initial/` 约 35 个文件）基本不变，只迁入 package。第一期整体记账预计约减半，第二期再随 review 批次化减少。
- 效率上，减少为补 claim 证据而派的 verify；本次 23 次 verify 中约 13 次是证据运行、约 10 次是 review。PG 隔离消除互相污染重跑（本次至少 4 次），harness 前置避免中途摸索 fixture，Amendment 不再使 package 停工。基础票上的串行等待不变，排序只能缓解，根治在第二期。
- 拦截能力上，拼接在规则上不成立；两三张票合入即可开始走通，基础票形状错误早暴露；页面承诺必须有浏览器证据，规则/安全套件在最终版本核对，Gate 第一屏直接显示产品结果和待确认修订。
- 质量上，跨票返工减少，合同修订对 Owner 可见，review 强度不变。新增风险是细粒度规则覆盖依赖 Spec 把必需套件清单写全，因此套件清单必须作为审批内容。

### 第二期

- 下游可按已放行 seam 开工，缩短关键路径上的串行等待。
- review 从每票触发转为 seam/风险批次，减少 review 次数和 closure 文档重复，同时保留对破坏 seam 承诺或安全不变量的 finding 阻断能力。

## 7. 落地顺序

1. 可先行落地治理小修：review ledger 迁入 package、资源 lease 前置。
2. 按第一期规则编写实现计划：选定代表性 Journey、必需规则/安全套件、首个 walking skeleton、观察入口、资源隔离和 package 内证据目录；第一期各项同时上线。
3. 用现有 `implementation` 边在 1～2 个真实新包上运行第一期，记录 §4.3 三项指标；最终 Gate 按两层核对，既有 package 不迁移。
4. 依据指标与回放验证决定是否实施第二期 seam 放行与 review 批次化。
