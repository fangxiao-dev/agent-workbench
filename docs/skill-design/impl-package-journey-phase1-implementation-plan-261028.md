# impl-package Journey 验收第一期实现计划

本计划只覆盖已批准提案的第一期：§2、§3、§5 的第一期表和 §7 第 1–3 步；不实现第二期 seam 放行、存疑传播或 review 批次。Owner 已于 2026-10-28 批准本计划及 §11 全部决策。Journey 包落为新的数据格式 `formatVersion: "3.6"`，让既有 `3.5` Ticket/claim 包继续走原校验路径且不迁移；实现分四个提交阶段，治理小修可先行，3.6 runtime、合同、技能和 fixture 必须在最后一个阶段一起上线。

## 1. 新旧包共存方式

### 1.1 现有运行时基线

| 事实 | 当前实现 | 计划边界 |
| --- | --- | --- |
| 版本选择 | `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:43` 固定 `FORMAT_VERSION = "3.5"`；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:795-812` 要求顶层键精确匹配、`tickets=true`、`dag=false` | 3.6 增加显式分支，不在 3.5 校验中加 Journey 例外 |
| Ticket 解析 | `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:465-515` 要求每个 Ticket 有 Stable claim ID；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:858-868` 以 claim/evidence 交叉校验 | 3.5 原样保留；3.6 改为 Journey step/负责套件解析 |
| `ticket satisfy` | `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1370-1380` 要求当前 revision/environment 覆盖全部 claim，并检查 implementation/acceptance 边 | 3.6 改为合入、负责套件、required review；依赖释放函数不变 |
| `gate pass` | `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1819-1852` 要求当前 HEAD、Ticket/release 边、当前 evidence，并以 `terminal_coverage_fact` 收口 | 3.6 增加 Journey、套件、review、Amendment、发布顺序和 fail-closed 检查；3.5 路径不改语义 |
| 初始化 | `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1079-1121` 只生成 3.5 state；`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py:128-138` 负责 package 命令 | 新 plan 写 `Acceptance: journey` 标记时生成 3.6；无标记的旧 plan 仍生成/读取 3.5 |

### 1.2 推荐方案

采用 `formatVersion: "3.6"` 作为 Journey 数据格式选择器，不另加重复的 `acceptanceMode` state 字段。原因是新格式不仅替换 Ticket 的完成依据，还增加有序 Journey run、套件结果、Amendment 和发布顺序，已经是持久化数据格式变化；单独增加模式字段而继续声称 3.5 会让当前严格顶层 schema 变成隐式双语义。插件版本和四个宿主 manifest 的 `0.4.2` 保持不变，`formatVersion` 只属于 package 数据格式。

`package init` 先解析 plan 的 `Acceptance: journey`；有该标记时只创建 3.6 state，无标记时创建现有 3.5 state。`package validate`、`status`、所有 mutation 和 `gate` 先按 `formatVersion` 分流：3.5 调用现有 Ticket/claim 路径，3.6 调用 Journey 路径；3.5 state 不自动补字段、不迁移、不读取 Journey 字段，3.6 state 也不回落到 claim 覆盖。3.4 仍只能通过现有一次性 migration validator，不能因为本期增加 3.6 而恢复 runtime dual-read。

旧包行为回归必须证明以下事实：现有 `tests/fixtures/impl-package-ticket-first/` 仍初始化为 3.5；3.5 的 Stable claim、evidence timing、contradictory evidence、implementation/acceptance/release 边和 Ticket archive 仍按原测试通过；将 3.6 专属字段加入 3.5 state 会被拒绝；3.5 package 不会因为 Journey situation 行或 package-local ledger 改动而改变 ready/blocked/satisfy 结果。3.5 当前 Gate 对未知 terminal coverage 的既有行为保持不变；本期只在 3.6 分支要求 unknown fail closed，旧行为的独立修复留给另一个明确授权的兼容性变更。

## 2. 数据模型

### 2.1 `spec.md §7` 的权威结构

将 `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md:85-91` 的单一 AC 表改为三类固定列的 Markdown 表：每条 Journey 一张步骤表（`### J<n> <终态>` 标题下），一张规则矩阵表，一张必需套件表。Journey 是 Owner 审批和阅读的对象，必须保持 Owner 可读，因此不用 JSON；runtime 沿用现有 Ticket Markdown 解析方式按固定标题与列名解析，列名缺失或多出即 validate 失败。不再维护同一 Journey 的第二份表。

| 对象 | 最小字段 | 校验 |
| --- | --- | --- |
| Journey | `id`、`terminalResult`、有序 `steps` | ID 唯一；至少一个 step；step 顺序固定 |
| Journey step | `id`、`enabledTickets`、`operationEntry`、`observationSurface`、`expected` | Ticket 必须存在；操作入口和观察表面非空；页面承诺的 step 必须声明 browser/真实入口证据 |
| Rule matrix row | `ruleId`、`suiteId`、`oracle`、`required` | `suiteId` 必须出现在 requiredSuites；一个规则不能无 oracle |
| Required suite | `id`、`kind`、`scope`、`entry`、`environment` | `kind` 为 `rule|safety`；`scope` 为 `ticket|package`；每个新 Ticket 至少启用一个 Journey step 或负责一个套件（二者满足其一即可，harness/migration/加固类 Ticket 合法） |
| Package safety suite | 普通 required suite 的 `kind=safety`、`scope=package` | 由 Spec 按风险声明，触及 tenant、RBAC/privacy、幂等/数据完整性时必须存在，未触及时可省略并写明理由；不再复制到每个 Ticket 的 INV claim |

### 2.2 3.6 state 的最小 schema

3.6 仍保留 `attempt`、`attemptHistory`、`predecessors`、`tickets`、`activeCheckpoints` 和当前唯一 writer 规则；不引入 Task、DAG 或第二条状态轴。新增一个 `acceptance` 对象，最小形状如下，字段名在实现时固定并由 `package validate` 严格校验：

| state 区域 | 最小内容 | 权威用途 |
| --- | --- | --- |
| `acceptance.journeyRuns[]` | `runId`、`journeyId`、`status`、`steps[]`；每个 step 有 `stepId`、`observation`、`evidenceKey`、`validity` | 保存一次从第一个 step 开始的连续走通结果；`status` 为 `PASS|BLOCKED|NEEDS-REVALIDATION`，不允许跳步拼接 |
| `evidenceIndex` | 3.6 使用 `evidenceKey` 索引；记录继续复用 `timing`、`artifact`、`revision`、`environment`、`conclusion`、`invalidatedBy`，增加 `kind` | 复用 `evidence add` 的原子校验、幂等、批量全量校验、artifact 相对路径和失效机制；`kind` 为 `journey-step|suite|review` |
| `acceptance.suiteResults[]` | `suiteId`、`kind`、`scope`、`ticketIds`、`evidenceKey`、`result` | 登记规则套件和唯一包级安全套件；`result` 为 `PASS|FAIL|BLOCKED`，不按 claim 逐项记账 |
| `acceptance.reviewResults[]` | `reviewRunId`、`ticketIds`、`resolvedHead`、`result`、`evidenceKey` | 绑定 Ticket 所需的 review 结果和 package-local ledger/report；不改变 do-review 的 per-Ticket review 强度和现有 terminal summary |
| `acceptance.amendments[]` | `id`、`summary`、`affected`、`artifact`、`status`、`confirmedBy`、`confirmedRevision` | `status` 为 `PENDING|CONFIRMED`；内容变化必须使用新 ID，确认绑定具体修订版本 |
| `acceptance.releaseOrder[]` | `seq`、`action`、`ticket`、`revision`、`environment`、`artifact` | 保存计划声明的合入/发布顺序；`seq` 从 1 连续递增，Gate 只接受完整顺序 |

Journey step、suite 和 review 的具体 revision/environment/artifact 只在对应 `evidenceIndex[evidenceKey]` 记录中保存一次，`acceptance` 只保存连续性、绑定和状态引用；这样不是另建 Journey evidence store。Amendment confirmation 和 release order 仍需小型专用数组，因为现有 evidence record 无法表达确认人、确认版本、序号和前后顺序；它们的 artifact 仍通过同一 `evidence add` 机制登记并由 `package validate` 交叉核对。

走通记录必须从 Journey 的第一个 step 开始，同一 `runId`、同一 revision/environment、按 spec 顺序逐步存在 supporting observation 和 artifact；上一步的 artifact 或业务结果成为下一步输入。失败时不覆盖旧 run，追加 `NEEDS-REVALIDATION`/新 run，不能以两次局部记录组成一次 PASS。

## 3. CLI 与运行时语义

不新增顶层命令组；新语义只放现有 `package`、`ticket`、`evidence`、`recovery`、`gate` 五组。当前 `plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py:17-24` 实际还暴露低层 `trail` 组，而 `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md:61` 仍写五组，这是文档与代码的既存不一致；本期不删除 `trail`，但 Journey/Suite/Amendment 不直接依赖新的顶层组。

| 命令 | 改造内容 | 成功判据 |
| --- | --- | --- |
| `package init` / `package validate` / `package status` | 按 plan 的 `Acceptance: journey` 生成或读取 3.6；validate 解析 §7 固定列表、Ticket coverage、acceptance schema、artifact/package 路径和当前 revision | 3.6 通过完整 schema；3.5 继续原 exact schema |
| `evidence add` | 保留 stdin 单对象/数组和现有字段校验；3.6 接受 `kind`、`evidenceKey`、`ownerTicket`/`owner=package`，把 journey step、suite、review、Amendment artifact 写入同一 evidenceIndex | 重复记录幂等；批量任一非法整批不写；artifact、revision、environment、conclusion 可解析且在 package 内 |
| `recovery mark-revalidation` | 新增按 `evidenceKey` 或 Journey/Suite ID 标记待复验；旧记录保留，不能删除或重写；新 revision 的 evidence 才能恢复 `valid` | 标记后 Ticket/Gate 不释放；同一标记幂等；只影响指定记录 |
| `package amendment add/confirm` | `add` 登记不可变 Amendment；`confirm` 使用 expected status/version 和确认人/确认 revision 做 CAS | 未确认进入 `PENDING`；同一内容重复确认幂等；内容改写必须产生新 ID；确认后不再阻塞 Gate |
| `package validate`（Amendment 漏登检测） | 以 Plan `Bundle Review & Approval` 记录的 approval commit 为基线，对 `decision.md`、`spec.md`、`contract-design.md` 自基线以来的 Git diff 与已登记 Amendment 的 `artifact`/revision 对账 | 有合同 diff 但无对应 Amendment 时报告 gap，`gate pass` 拒绝；防止执行者只写 ER judgment 就改变合同。是否属于用户可见仍由登记者分类，runtime 不做语义判断 |
| `package release-order append` | 通过 CLI 追加下一序号并校验 Ticket、revision、environment、artifact | 只能追加 `previous.seq+1`；错序、未知 Ticket、非 package artifact 拒绝 |
| `ticket satisfy` | 3.6 分支不再调用 claim coverage；检查本 Ticket 已合入、负责套件 PASS/valid、required review PASS/valid，再保留现有 CAS `--expect` 和 acceptance revision/environment 写入 | 满足三项才进入 `SATISFIED`；implementation 边释放算法不变 |
| `gate pass` / `gate blocked` | pass 执行两层核对并生成 Owner Summary；blocked 记录缺口且保持 active | pending Amendment、stale record、unknown required result 或缺 artifact 时 pass 被拒；blocked 可记录并继续实施 |

“已合入”机械判定为 `--revision` 可解析且是当前 HEAD 的 ancestor；负责套件和 review 的 evidence 必须绑定同一 `--revision`/environment 并且 artifact 存在、未失效。`gate pass` 最终再要求所有被采信记录的 revision 等于 comparison commit，避免 Ticket 在早期合入后被后续修改掩盖。`implementation` 边仍由 `ready_tickets`/`_ticket_released` 判断：只有上游 `SATISFIED`、`RETIRED/waived` 或 successor 已释放时才放行；`acceptance` 边仍阻止 `ticket satisfy`，`release` 边仍只在 Gate 前复核。

## 4. Ticket `SATISFIED` 依据替换

3.6 `ticket satisfy` 的校验顺序固定为：

1. 读取 state 并用 `--expect` 做 CAS；冻结 Attempt 和非 PENDING 目标仍按旧规则拒绝。
2. 解析 `--revision`，确认它是当前 HEAD 的 ancestor；这代表实现已进入当前集成线，不把 worker return、未合入分支或临时 artifact 当成已合入。
3. 从 Ticket 的 Journey/Suite Coverage 区块读取负责套件和 required review 引用，确认每个规则/安全套件都有同 revision/environment 的 `PASS` evidence，review receipt 的 resolved head 覆盖该 Ticket 且无未关闭 blocker/fail/uncertain。
4. 写入现有 `tickets[id] = {"state":"SATISFIED","acceptance":{"revision":...,"environment":...}}` 形状，不把运行进度回写 Ticket；状态写入后继续刷新 progress 和 trail。

3.5 仍走 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1370-1380` 的 claim/evidence 分支；3.5 Ticket 仍必须有全部 Stable claim supporting evidence。这个分支不迁移、不读取 3.6 acceptance 数组，也不因为新模板存在 Journey 字段而改变 implementation 边。

## 5. 两层 Gate 与 Owner 视图

### 5.1 `gate pass` 的 3.6 清单

| 层 | Gate pass 必须核对 |
| --- | --- |
| Journey 产品层 | 每个 required Journey 有同一 run 从第一个 step 到最后一个 step 的 PASS；step 数、顺序、enabled Ticket、operation entry、observation surface、expected/observed 和 artifact 均可追溯；页面承诺必须有真实页面/浏览器 evidence，API 或 lower-level evidence 不能替代 |
| 规则/安全层 | Spec rule matrix 的所有 required suite 有 PASS；唯一 package safety suite PASS；suite artifact 存在、未 invalidated、revision/environment 有效；不能用多个局部 claim 记录拼成一个缺失的 suite |
| Ticket 与合入 | 所有 required Ticket SATISFIED；implementation/acceptance/release 边按原规则释放；Ticket acceptance 和 suite/review evidence 在最终 comparison commit 有效 |
| Review | 最终 HEAD 的 review 由现有 terminal-final（含其 C/Safety 复用 admission）承担，terminal review coverage 必须是明确 known true，缺失、unknown、错误 HEAD、错误 run、缺轨或 incomplete 都拒绝；per-Ticket review receipt 只用于 `ticket satisfy`，不要求其 revision 等于 comparison commit，避免收口时重跑全部 per-Ticket review；不能用 dispatch 行或 Gate 终态代替 review result |
| Amendment | `acceptance.amendments` 没有 PENDING；每个 CONFIRMED 记录确认人、确认 revision 和 package-local artifact；确认后再次改变语义必须有新 Amendment |
| 发布顺序与 revision | `releaseOrder` 完整、连续、与计划声明一致，所有记录的 revision 等于 comparison commit；comparison commit 必须等于当前 HEAD；所有 artifact 路径存在且在 package 内 |
| 既有终态条件 | Durable Delta 或 `--no-durable-delta-reason`、live package reference 和 terminal lifecycle 继续按现有 Gate 规则检查 |

新增的 fail-closed 规则只作用于 3.6：所需 Journey、suite、review、Amendment 或 release-order 事实只要 unknown 就不能 pass。现有 `command_gate` 在 `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1846-1852` 只拒绝 known false，3.6 分支必须改成只有 known true 才通过；3.5 分支保持现有行为以满足不迁移兼容边界。

### 5.2 Gate 第一屏

`plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py:1858-1862` 当前会直接重写 `gate.md`，因此只改 `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/gate.md` 不足以生效。3.6 Gate writer 在 header 后、技术 Evidence 前生成 `## Owner Summary`，至少展示：`Journey J1: 4/4 PASS`、`Suites: 3/3 PASS`、`Risk review: 2/2 PASS`、`Amendment: 1 pending`、`Release order: 5/5`、`Final revision: <short SHA>` 和一句 blocked/pass 理由。技术报告、suite artifact、review ledger、Amendment 和发布细节继续放在后续章节；3.5 Gate 文本保持现有结构。

`gate blocked` 不新增 `pass-pending-owner-ack` 状态；它写当前 Attempt 的 blocked Gate、Owner Summary 和 next action，生命周期保持 active，已授权且不依赖待确认 Amendment 的工作继续。`gate pass` 只在 Amendment 已确认和所有上述核对 known true 时终结 Attempt。

## 6. 走通记录时效与待复验

采用最小、保守、机械规则：Journey step、suite 和 release-order evidence 的 `revision` 必须等于 Gate comparison commit（review 的最终版本有效性由 terminal-final 承担，见 §5.1）；不做路径 diff、代码影响推断或“文档变更可复用”推断。当前 HEAD 与记录 revision 不同即为 `NEEDS-REVALIDATION`，artifact 缺失或被 `invalidatedBy` 标记也为待复验；environment 必须匹配 Spec 对该 suite/Journey 声明的环境，不做环境等价推断。

`package validate` 和 `gate pass` 只计算有效记录，不自动抹掉旧记录；`recovery mark-revalidation` 追加明确失效原因，新的 `evidence add` 在新 revision 写入新记录。Amendment 的 `affected` 列表只用于 Owner 可见性和缩小 revalidation 范围，不能放宽 revision 规则；Amendment 确认后，受影响 Journey/Suite 仍需在最终 revision 重新登记。失败恢复仍从 Journey 第一个 step 连续重跑，不允许只重跑失败 step 后把两轮结果合并。

## 7. 三项治理

### 7.1 review ledger 迁入 package

当前 `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py:25-40` 把默认目录固定在系统 Temp，`plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py:154-169` 在该目录创建 ledger；一期改为带 `--package` 时默认写入 `execution/<attempt>/reviews/<YYMMDDHHMM>-<slug>-<shortsha>.md`，并返回 package-relative `ledgerRelativePath`。`plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:35-43,55-70`、`plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md:19-30` 和 `plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md` 同步使用该路径；leaf report、closure、terminal summary 的 artifact 都必须是 package-relative。

兼容规则：不带 `--package` 的旧调用仍可读取/更新既有 Temp ledger，但不再为 3.6 package 创建新的 Temp ledger；带 `--package` 的 create/write/show 只接受当前 package 的 `execution/<attempt>/reviews/` 路径。3.5 旧 package 不迁移，旧 ledger 可读但不成为 3.6 Gate 的唯一证据；3.6 `package validate` 发现 Temp-only 引用时报告 evidence gap。

### 7.2 资源 lease 前置

两侧都改：`skills/dispatcher/SKILL.md` 和 `skills/dispatcher/references/resource-isolation.md` 写明 Dispatcher 必须在 worker 进程启动前取得 lease；`recovery lease acquire/release` 提供最小互斥机制。lease 文件放在当前 package 的 `execution/<attempt>/leases/`，使用原子创建和 owner token，资源 key 仍由 Dispatcher 声明，不能由 runtime 从业务 Ticket 推断。

固定时序为：`lease acquire` → `trail append dispatch`（记录 `lease_id` 与 resource_keys）→ 启动 worker；dispatch/worker 启动失败立即 release；worker 返回后由 cleanup owner 完成进程、数据库/schema、端口和临时文件清理，再 `lease release`。release 必须 owner 校验、可重复调用，未释放或清理失败作为 residue 返回并阻止相关 acceptance；trail 只记录实际结果，不承担互斥。第一期不做自动 TTL 抢占、不做 seam 级 lease、不把相同 resource key 自动视为冲突，无法隔离的资源仍按唯一串行顺序执行。

### 7.3 证据落 package

3.6 的 `package validate` 对 `evidenceIndex`、Journey/Suite/Review/Amendment/release-order 的所有 artifact 做相同检查：必须是仓库相对或 package-relative 的规范路径、解析后位于当前 package、文件存在、revision 可解析；出现 `%TEMP%`、`$env:TEMP`、绝对 Temp 路径、package 外路径或缺失文件即报告 gap。旧 3.5 仅保留原有 evidence/checkpoint 校验，不因为旧 package 历史记录不在 package 而强行迁移。

## 8. Skill、reference、模板和运行时改动清单

| 文件 | 改动到的节/位置 | 改成什么意思 |
| --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md` | Ownership、主路径第 4–6 步、完成条件 | Spec Gate 必须批准 Journey 表、规则矩阵、必需套件清单；套件清单是合同，不由 Plan 临时补造 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md` | §7 `85-91` 及 Spec Gate 相关注释 | 用单一机器可解析 Journey/规则/套件结构替换逐 AC 表；保留 rule oracle、安全不变量和 evidence owner，不复制 contract-design |
| `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/spec/SUB-SKILL.md`、`plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md` | Spec acceptance coverage 与 Gate checklist | 检查 step entry/surface、suite completeness、package safety suite 和 machine-readable shape；不把“能定位到 Ticket”当作完整执行证据 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md` | Ticket 拆分 1、2、6、8、完成条件 | 拆票依据改为启用 Journey step 或保障已登记 suite；首票排序为窄而完整的 walking skeleton；harness 只建设第一条窄路径；3.6 不做 claim coverage |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/plan.md` | 摘要、输入、全局调度、Planned Verification、Final Gate | 增加 `Acceptance: journey`、首个可见 step、Journey/suite 顺序、package safety、release order、连续走通和 Gate 两层判据 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/ticket.md` | 验收标准、安全不变量、依赖 | 增加 Journey steps、负责 suites、required review、入口/观察表面和产出/消费；3.6 不复制三条 INV claim，3.5 legacy block 保留为兼容模板分支 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/references/common-misjudgments.md`、`plugin-marketplace/plugins/impl-package/skills/impl-planning/evals/evals.json` | admission、拆票、验证误判 | 加入“局部 evidence 拼不成连续 Journey”“harness 先于 walking skeleton”“无 suite 责任的 Ticket”等负例 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/SKILL.md` | 完整性、顺序、验证、验收检查 `24-41` | 增加首个用户可见 step 何时可走通、每 step entry/surface、suite 清单覆盖、无 Journey/suite 责任 Ticket、Owner Gate 证据和 release order 检查；不引入第二期 seam/review batch |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/test-review.md`、`plugin-marketplace/plugins/impl-package/skills/plan-review/evals/evals.json` | Planned Verification 和 bundle admission | 检查连续 Journey 的 oracle、套件环境/入口、Amendment/Gate blocked 场景；保持按风险选择 review，不把 Journey 变成每个 step 的 review batch |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md` | State/ER/Trail `36-40`、Review `42-62`、Verify and Gate `64-78` | 增加登记 Journey、suite、review、Amendment、release order 和 revision freshness；按新 `SATISFIED` 依据工作；blocked 不停工、只阻止最终 Gate |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/gate.md` | header 后、Evidence 前 | 增加机器生成的 Owner Summary；技术 artifact 后置；模板与 runtime writer 同步 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/manual-acceptance-readiness.md`、`plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/execution-findings.md` | manual readiness、package-local provenance | manual Journey 记录必须有 entry/surface/环境/清理/readback；closure 和 finding 只引用 package-local artifact |
| `plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md` | Create ReviewRun、Dispatch、Report `35-70` | 3.6 传入 package-local ledger/report 路径；保留 per-Ticket topology、terminal-final 和 fail-closed review，不设计第二期批次化 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md`、`plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md` | leaf report、terminal summary、canonical ledger | ledger path、reviewed head、ticketIds/required review 绑定可机器读取；artifact 始终 package-relative；现有 `review.terminal_summary` 继续复用 |
| `plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md` | 权威边界、固定位置、Readiness、Ticket-only 运行边界 | 说明 3.6 Journey/Suite/Amendment/release-order 是新 acceptance contract；3.5 claim/evidence contract 原样保留；不引入 Task/DAG/seam 状态 |
| `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md` | format、State schema、Ticket/evidence、CLI | 增加 3.6 schema、路径和命令；明确 `evidenceIndex` 仍是 artifact index、state 仍唯一 writer；保留 3.5 文档和 migration boundary |
| `plugin-marketplace/plugins/impl-package/references/progressive-system-evidence.md` | 核心判断 `32`、completion evidence boundary | 删除“较早证据与真实 E2E 可组合支持同一 claim”对 Journey 的适用表述；改为局部/套件 evidence 可诊断规则风险，但不能替代一次从第一步开始的连续 Journey |
| `plugin-marketplace/plugins/impl-package/references/situation-inputs.md` | state schema、acceptance/evidence key、unknown 规则、路径输入 | 描述 3.6 acceptance records、suite/review/amendment/release-order、package-local artifact 和 U/F/HF；继续说明 3.5 inputs 不变 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`、`scripts/impl_package_runtime/protocols.json` | acceptance/Gate priority rows 和协议 | 增加 Journey incomplete、suite incomplete、revalidation pending、Amendment pending、release-order gap 的动作；Amendment pending 只阻断 Gate，不加入 `GLOBAL_BLOCKING_SLUGS` |
| `plugin-marketplace/plugins/impl-package/scripts/situation.py` | `_parse_state`、StateView、FactContext、`FACT_KEYS`/`WHEN_PARSERS` | 按 3.5/3.6 解析；3.6 facts 从 acceptance/evidence 派生，unknown 不压成 false；3.5 situation facts 和 legacy trail 兼容保持不变 |
| `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py` | format dispatch、state validate/init、evidence、Ticket satisfy、Gate writer | 实现 3.6 schema、typed evidence、stale check、suite/review/amendment/release-order CLI 语义和 Owner Summary；不修改 3.5 分支 |
| `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py`、`impl_package_state.py` | package/ticket/evidence/recovery/gate parser | 注册新子命令和 typed stdin；保留旧参数和低层 trail 入口，不新增顶层命令组 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py` | `ledger_directory`、`validate_ledger_path`、create/write/show | `--package` 时写 `execution/<attempt>/reviews/`；旧无 package Temp 路径只读/兼容，不作为 3.6 新建默认 |
| `skills/dispatcher/SKILL.md`、`skills/dispatcher/references/resource-isolation.md` | 执行循环第 3–5 步、实际资源/完成标准 | 增加 lease acquire → worker start → cleanup → release 约束、owner/cleanup/residue 返回字段；`resource_keys` 仍不是锁 |
| `plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py`、hooks manifest | 本期不改行为 | 只用现有 hook 回归验证 direct `state.json` 编辑仍受阻、CLI 写入仍可用；不把 hook 变成 Journey 状态 writer |

## 9. 落地阶段与提交序列

| 阶段/提交 | 变更范围 | 完成判据 | 主要验证 |
| --- | --- | --- | --- |
| 0. `fix(impl-package): package-local review ledger and pre-dispatch lease` | review ledger package path/compatibility；Dispatcher lease contract；recovery lease CLI、trail lease binding、清理测试 | 新 package 不再创建 Temp-only ledger；第二个相同 lease 不能取得；dispatch/start failure 和 worker cleanup 都释放；旧 Temp ledger show/write 兼容 | L0：`plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_review_ledger.py`、新增 lease tests、`tests/test_impl_package_state.py`；L1：`tests/test_dispatcher_contract.py`、`tests/test_impl_package_plugin.py` |
| 1. `feat(impl-package): add 3.6 Journey state and runtime gates` | engine/command groups/state parser/situation/protocols；3.6 state、evidence、Ticket satisfy、Gate、Amendment、release order、revalidation | 3.5 fixture 全部原测试通过；3.6 fixture 能 init、登记 typed evidence、satisfy、blocked/pass；Gate unknown、stale、pending Amendment 负例均 fail closed | L0：`tests/test_impl_package_state.py`、新增 Journey runtime tests、`tests/test_situation_render.py`；L1：`tests/test_ticket_first_contract.py`、`tests/test_impl_package_migration.py`、`tests/test_review_track_stats.py` |
| 2. `docs(impl-package): align Journey contracts and execution skills` | req-align、impl-planning、plan-review、dev-with-track、do-review、composition/current-state/progressive/situation references/templates/evals、Dispatcher 文案 | 所有 3.6 合同只保留一个 Journey source；旧 claim contract 明确为 3.5；技能能从 plan→init→verify→Gate 指向同一 CLI/路径；无第二期 seam/review batch 规则 | L0：各变更 Skill 的 `quick_validate.py`、`tests/test_skill_validator.py`、对应 evals/contract tests；L1：`tests/test_req_align_contract.py`、`tests/test_ticket_first_contract.py`、`tests/test_dev_with_track_verify_gate_contract.py`、`tests/test_dev_with_track_situations_review_vocabulary.py`、`tests/test_subagent_driven_development_contract.py` |
| 3. `test(impl-package): exercise Journey phase1 fixture and release bundle` | 新增最小 3.6 fixture、runtime E2E、旧包回归矩阵和 package evidence validation；不新增第二期实现 | 阶段 0–2 全部通过；最小 E2E 能得到一次 blocked 和一次 pass；旧 3.5 与新 3.6 可并存；review/evidence/lease 无 package 外唯一证据 | L0：新增 `tests/test_impl_package_journey.py` 和相关 engine/situation tests；L1：上述 runtime/skill/dispatcher 聚焦套件；最后执行 `git diff --check` 和仅相关 tests |

第二期决策所需的三项指标（提案 §4.3）不新增埋点：关键路径等待由 trail 的 dispatch 顺序与时间戳导出，上游 finding 性质由 `review.canonical_summary` 与人工分类得出，走通记录成本由 Journey evidence 的时间与重跑次数得出；必要时扩展现有 `plugin-marketplace/plugins/impl-package/scripts/dispatch_audit.py` 或 `plugin-marketplace/plugins/impl-package/scripts/review_track_stats.py` 的只读报表，不改 state schema。

阶段 0 可以先独立落地；阶段 1–3 的提交只是实现顺序，不是可分别发布的产品能力。只有阶段 3 的 fixture、L0/L1 和 Gate 负例全部通过后，才把第一期作为一次完整上线；不实现或预留第二期 seam 状态机、存疑传播和 review 批次的接口。

## 10. 验证计划

### 10.1 按 AGENTS.md 分层

| 阶段 | L0：变更直接入口 | L1：直接引用/相邻契约 | 额外边界 |
| --- | --- | --- | --- |
| 0 | `python -m pytest plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_review_ledger.py -q`；`python -m pytest tests/test_impl_package_state.py -q`；`python -m py_compile plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py` | `python -m pytest tests/test_dispatcher_contract.py tests/test_dispatch_fix_contract.py tests/test_impl_package_plugin.py -q` | 重点检查 no Temp-only、新旧 ledger path、lease cleanup residue |
| 1 | `python -m pytest tests/test_impl_package_state.py tests/test_situation_render.py tests/test_review_track_stats.py tests/test_impl_package_journey.py -q`；`python -m py_compile plugin-marketplace/plugins/impl-package/scripts/impl_package_state.py plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py plugin-marketplace/plugins/impl-package/scripts/situation.py` | `python -m pytest tests/test_ticket_first_contract.py tests/test_impl_package_migration.py tests/test_live_package_reference.py -q` | 3.5 exact schema/claim/Gate 回归必须通过；3.6 unknown 和 stale 负例必须通过 |
| 2 | 对每个修改 Skill 运行 `python skills/write-skill-smartly/sub-skills/skill-creator/scripts/quick_validate.py <skill-directory>`，并运行 `python -m pytest tests/test_skill_validator.py plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_three_track_contract.py -q` | `python -m pytest tests/test_req_align_contract.py tests/test_ticket_first_contract.py tests/test_dev_with_track_verify_gate_contract.py tests/test_dev_with_track_situations_review_vocabulary.py tests/test_impl_package_step8_evals.py tests/test_subagent_driven_development_contract.py -q` | 静态检查确认没有把第二期 seam/review batch 写进第一期文本 |
| 3 | `python -m pytest tests/test_impl_package_journey.py tests/test_impl_package_state.py tests/test_situation_render.py -q` | `python -m pytest plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_review_ledger.py tests/test_dispatcher_contract.py tests/test_impl_package_plugin.py tests/test_ticket_first_contract.py tests/test_dev_with_track_verify_gate_contract.py -q` | 不运行无关全仓测试；完成后 `git diff --check` |

未修改插件 manifest，因此按 AGENTS.md 不要求 manifest 专项变更校验，也不修改 `plugin.json` 版本。若实现阶段误触 `.codex-plugin/plugin.json`、`.claude-plugin/plugin.json`、`.grok-plugin/plugin.json` 或 `.zcode-plugin/plugin.json`，必须追加 `python -m pytest tests/test_impl_package_plugin.py -q`，并核对四宿主的 name/version/skills/agents/hooks 入口一致；不得通过改版本掩盖路径或合同变化。

### 10.2 必须新增的测试用例

1. `formatVersion=3.5` 的旧 fixture 初始化、validate、evidence add、claim conflict、`ticket satisfy`、implementation/acceptance/release edge、terminal archive 和旧 trail 读取全部保持原结果；3.5 state 加 Journey 字段被拒绝，3.6 state 不被旧 claim validator 接管。
2. 3.6 init 需要 `Acceptance: journey`；Journey 表缺 step、重复 step、未知 Ticket、空 operationEntry/observationSurface、缺 required suite 或缺 package safety suite 均拒绝。
3. `evidence add` 的 journey-step/suite/review typed record 支持单条、批量、重复幂等、批量原子失败、artifact 外部路径拒绝、invalidatedBy 和 revision/environment 校验。
4. Journey run 必须从第一个 step 连续到最后一个 step；跳步、跨 run 拼接、用另一环境结果补当前 run、只重跑失败 step 均拒绝或标记待复验。
5. `ticket satisfy` 缺合入 ancestor、缺负责 suite、suite 结果非 PASS、suite revision/environment 不匹配、required review 缺失/FAIL/UNCERTAIN 时拒绝；没有 claim evidence 但三项满足时可以通过；implementation 边释放结果与 3.5 相同。
6. `package validate` 和 `gate pass` 对最终 HEAD 不同的 Journey/Suite/Review/Release record 标记 `NEEDS-REVALIDATION`/拒绝 pass；artifact 缺失、Temp-only、package 外路径、未知 validity 同样拒绝。
7. Amendment add/confirm 的 pending、重复确认、错误 expected status、内容改变后旧 ID 确认、确认 revision 绑定和“确认后再修改生成新 pending”均有正负例；pending Amendment 不阻止无关 Ticket 实施，但阻止 pass。
8. Gate blocked 保持 active、保留 next action 并渲染 Owner Summary；Gate pass 要求 Journey/Suite/Review/Amendment/Release Order 全部 known true；3.6 terminal coverage unknown 必须拒绝，3.5 既有路径不改变。
9. package-local review ledger 的 create/write/show、旧 Temp ledger 兼容、重复文件名拒绝、报告和 closure 引用校验；lease 双领、dispatch 前置、启动失败释放、cleanup 后释放、owner mismatch 和残留报告。
10. Situation renderer 新增 Journey incomplete、suite incomplete、revalidation pending、Amendment pending、release-order gap fixture；3.5 `situations/` 和 `situations-a2/` 全部 expected 不变。

### 10.3 最小端到端演练

新增一个最小 `tests/fixtures/impl-package-journey/`，只包含一份 Journey、两个 Ticket、一个 rule suite、一个 package safety suite、一个 review receipt、一个 package-local artifact 和一个 Amendment，不复用参考运行包的业务复杂度。测试在临时 Git repo 中执行以下序列：

1. 写入并 commit `plan.md`（含 `Acceptance: journey`）、`spec.md`、两个 Ticket、Journey/suite/review fixture 和 artifact，运行 `package init --attempt initial --plan <plan>`，断言 state 为 3.6、Ticket 为 PENDING、Journey/suite/review 尚未满足。
2. 使用 `evidence add` 登记 rule suite、package safety suite 和 required review；使用 typed Journey evidence 从 `J1-S1` 到 `J1-S2` 连续登记同一 run，并断言 state/progress/package validate 可读。
3. 对负责 Ticket 运行 `ticket satisfy`，断言不需要逐 claim evidence，且 implementation edge 仍按现有 Ticket 释放；为第二个 Ticket 补齐负责 suite/review 后满足。
4. 使用 `package amendment add` 留下一条 PENDING Amendment，运行 `gate pass`，断言命令非零、Gate/Owner Summary 显示 pending、Attempt 仍 active；随后运行 `gate blocked`，断言 blocked 记录不冻结 Ticket/Attempt。
5. 使用 `package amendment confirm`，在同一 final HEAD 下重读所有有效 Journey/Suite/Review/Release records，追加完整 release order，运行 `gate pass`，断言 `gate.md` 第一屏显示 Journey/Suite/Review/Amendment/Release order，state frozen 且 `.impl-package/attempts/initial.json` 生成。
6. 在单独负例中再提交一个代码 commit 后直接 `gate pass`，断言旧 records 全部待复验；重新以新 HEAD 登记最小 required evidence 后才允许 pass。这个演练不访问外部系统、不启动真实浏览器/provider，真实新 package 的页面 Journey 仍由 Owner 按 Spec 的 operationEntry/observationSurface 记录 package-local artifact。

## 11. Owner 决策

2026-10-28 Owner 全部采纳下表"决定"列。

| 事项 | 决定 | 边界 |
| --- | --- | --- |
| 新包分流采用 3.6 还是 3.5+模式字段 | 采用 3.6；它是数据格式变化，不改插件版本 | 若 Owner 选择模式字段，必须另行批准 3.5 顶层 schema 放宽、缺省模式和旧包误分流的兼容合同；本计划不同时实现两套方案 |
| 第一批真实新包的 required Journey 与 suite 清单 | 每个包先选 1–2 条最关键连续 Journey，规则 suite 只覆盖 Spec rule matrix，package safety suite 按 §2.1 依风险声明 | Owner 必须在 req-align Spec Gate 中批准清单；不能由 impl-planning 或 Gate 临时补套件 |
| 生产/测试 environment 标识 | 每个 Journey/Suite 在 Spec 中列出明确字符串，记录按字符串精确匹配，不做环境相似推断 | 这决定哪些旧记录可以复用；默认不允许“同类环境”自动复用 |
| required review 的最小绑定 | Ticket 声明 required review；同一 package 的 terminal-final 仍由 do-review 完整覆盖；per-Ticket receipt 只证明该 Ticket 的 required review | 不把 review batch、seam 放行或降级 topology 放入第一期 |
| Amendment 的 Owner 身份与确认 artifact | 用 package-local `confirmedBy`、`confirmedRevision` 和 Owner confirmation artifact；不接入外部审批系统 | 未确认只能阻断最终 Gate，不阻止不依赖该语义的合法实施 |
| release order 覆盖范围 | 只记录 Spec/Plan 明确的合入、fixture/backfill、开关/发布和清理动作，序号连续 | 不把每个 worker dispatch 当 release step，避免把 trail 再造一份流水账 |
| lease 残留恢复 | 第一阶段不自动 TTL 抢占；由 Owner/Dispatcher 显式 release 并留下 cleanup residue | 自动回收需要明确崩溃恢复和资源 owner 合同，属于后续风险，不在本期猜测 |
| Spec §7 的书写格式 | 固定列 Markdown 表（Owner 可读、runtime 可解析） | 若选 JSON block，解析更简单但 Owner 审批可读性下降，需另配渲染视图 |
| 3.5 Gate unknown 的 fail-open 风险（已核实：`engine.py:1846-1847` 仅在 `coverage.known and value is False` 时拒绝，无法判定时放行） | 本期只让 3.6 fail closed；另开兼容性变更修复 3.5 | 若 Owner 要一期同时修 3.5，必须把它作为独立 behavior change 增加回归和发布批准，不能悄然共用 3.6 分支 |

本计划不把参考运行包的人工 Journey 补验收直接当成新 runtime schema：它证明了 package-local 的连续步骤、API/浏览器观察、artifact 和清理记录是可落地的样例，但当前 state 仍是 3.5、原 Gate 已冻结，必须通过本期新格式 fixture 和真实新包运行验证后才可作为第一期验收依据。
