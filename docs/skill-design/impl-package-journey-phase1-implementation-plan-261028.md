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

### 1.3 3.6 分流点

`FORMAT_VERSION` 常量在 `engine.py:43,799,873,1106,1817,1869` 被多处直接引用，改为按 `state.formatVersion` 取值的 helper，不新增第二个常量。3.6 必须在以下位置显式分流，否则 3.6 `package init` 即失败：

| 位置 | 3.5 现状 | 3.6 行为 |
| --- | --- | --- |
| `_ticket_documents`（`engine.py:479-484`） | Ticket 无 Stable claim 即抛错 | 解析 Ticket 的 Coverage 区块（启用的 Journey step、负责的套件、required review），`_claims/_claimTimings` 置空 |
| `_validate_state`（`engine.py:858-868`） | SATISFIED Ticket 强制 claim 覆盖 | 按 §4 校验；evidenceIndex 按 `evidenceKey` 形状校验 |
| `_render_progress`（`engine.py:893`） | 按 claim 渲染 | 按 Journey reach、套件结果、Ticket 状态渲染 |
| `_validate_projections` / `_uniform_ticket_timing_findings` | 读 claim timing | 3.6 跳过 claim timing 检查 |
| `scripts/situation.py` `_parse_state`（`situation.py:812-816`）与 evidenceIndex 解析（`situation.py:878-908`） | 硬编码 3.5 与 ticket→claim→list 形状 | **阶段 1 的前置项**：先支持 3.6 解析；`terminal_coverage_fact`（`situation.py:677-684`）依赖它，未支持时 3.6 Gate 恒为 unknown |

`ready_tickets` / `_ticket_released`（`engine.py:773-791`）与 claim 无关，原样复用。

## 2. 数据模型

### 2.1 `spec.md §7` 的权威结构

将 `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md:85-91` 的单一 AC 表改为三类固定列的 Markdown 表：每条 Journey 一张步骤表（`### J<n> <终态>` 标题下），一张规则矩阵表，一张必需套件表。Journey 是 Owner 审批和阅读的对象，必须保持 Owner 可读，因此不用 JSON；runtime 沿用现有 Ticket Markdown 解析方式按固定标题与列名解析，列名缺失或多出即 validate 失败。

Spec 只写 Journey、step 与套件，**不写 Ticket ID**：现有 `contract-doc-names-ticket` 规则（`engine.py:948-976`）禁止合同文档点名 Ticket。step→Ticket、套件→Ticket 的归属只写在 Ticket 的 Coverage 区块，runtime 反查，保证单一来源。

| 对象 | 最小字段 | 校验 |
| --- | --- | --- |
| Journey | `id`、`terminalResult`、有序 `steps` | ID 唯一；至少一个 step；step 顺序固定 |
| Journey step | `id`、`operationEntry`、`observationSurface`、`expected` | 操作入口和观察表面非空；每个 step 至少被一个 Ticket 的 Coverage 区块认领 |
| Rule matrix row | `ruleId`、`suiteId`、`oracle` | `suiteId` 必须出现在必需套件表；一个规则不能无 oracle |
| Required suite | `id`、`kind`、`scope`、`entry`、`environment` | `kind` 为 `rule|safety`；`scope` 为 `ticket|package`；ticket 级套件至少被一个 Ticket 认领 |
| Package safety suite | 普通 required suite 的 `kind=safety`、`scope=package` | 由 Spec 按风险声明，触及 tenant、RBAC/privacy、幂等/数据完整性时必须存在，未触及时可省略并写明理由；不再复制到每个 Ticket 的 INV claim |

Ticket Coverage 区块：`Journey steps`（如 `J1-S2`）、`Suites`、`Required review`（`none` 或 review 范围）。每个 Ticket 至少启用一个 Journey step 或负责一个套件；harness、migration、加固类 Ticket 合法。

### 2.2 3.6 state 的最小 schema

3.6 保留 `attempt`、`attemptHistory`、`predecessors`、`tickets`、`activeCheckpoints` 和唯一 writer 规则；不引入 Task、DAG 或第二条状态轴。证据一律复用 `evidenceIndex`，只新增两个小结构：

| state 区域 | 最小内容 | 用途 |
| --- | --- | --- |
| `evidenceIndex` | 3.6 按 `evidenceKey` 索引；记录沿用 `timing`、`artifact`、`revision`、`environment`、`conclusion`、`invalidatedBy`，新增 `kind`（`journey-step|suite|review|release`）、`entry`（journey-step 必填） | 复用 `evidence add` 的原子校验、幂等、批量、相对路径与失效机制；PASS/FAIL 用 `conclusion` 表达 |
| 走通进度（派生，不存储） | 由 `kind=journey-step` 记录的 `runId`、`journeyId`、`stepId` 派生 | `reach` = 同一 run 从第 1 步起连续有效的步数，只用于 Owner 视图和进度；PASS = 全部 step 都在同一 run 内且 evidence 有效。不另存 journeyRuns，保持单一来源 |
| `acceptance.amendments[]` | `id`、`summary`、`affected`、`artifact`、`status`、`confirmedBy`、`confirmedRevision` | `status` 为 `PENDING|CONFIRMED`；内容变化必须使用新 ID，确认绑定具体修订版本 |
| `acceptance.releaseOrder` | Plan 中 `Release order: required \| none` | 决定 Gate 是否要求 `kind=release` evidence |
| `acceptance.contractBaseline` | `package init` 时 `decision.md`、`spec.md`、`contract-design.md` 的 Git blob hash 与 init HEAD | Amendment 漏登检测的机械基线（见 §3） |

不设 `suiteResults`、`reviewResults`、`releaseOrder` 专用数组：套件和 review 结果就是 `kind=suite|review` 的 evidence，Ticket 归属从 Coverage 区块反查；发布顺序是一条 `kind=release` 的 evidence，artifact 为 package 内的 Markdown 发布顺序表。

走通记录必须从 Journey 第 1 步开始、同一 `runId`、同一 environment、按 Spec 顺序逐步登记；journey-step evidence 的 `entry` 必须与 Spec 该步的 `operationEntry` 字符串精确一致（不做语义判断），以此保证页面承诺的步骤用的是页面入口。失败不覆盖旧 run，另起新 run。**runtime 无法机械验证"上一步输出是下一步输入"**，这一点由执行者在 artifact 中记录、由 review 和 Owner 抽查，Gate 不宣称能保证它。

## 3. CLI 与运行时语义

不新增顶层命令组；新语义只放现有 `package`、`ticket`、`evidence`、`recovery`、`gate` 五组（`impl_package_state.py:17-24` 另有低层 `trail` 组，`references/impl-package-current-state.md:61` 仍写五组，属既存不一致，本期在文档中更正，不删 `trail`）。hooks 只拦直写 `state.json`，无需改动。

| 命令 | 改造内容 | 成功判据 |
| --- | --- | --- |
| `package init` / `validate` / `status` | 按 plan 的 `Acceptance: journey` 生成或读取 3.6；init 写入 `contractBaseline`；validate 解析 §7 固定列表、Ticket Coverage、acceptance schema、artifact 路径 | 3.6 通过完整 schema；3.5 继续原 exact schema |
| `evidence add` | 3.6 接受 `kind`、`evidenceKey`、`entry`、`ownerTicket`/`owner=package`；journey-step 记录可带 `runId` 写入 `journeyRuns` | 重复幂等；批量任一非法整批不写；artifact 在 package 内 |
| `evidence invalidate` | 扩展为接受 `evidenceKey`（不新增 mark-revalidation 命令） | 旧记录保留并带失效原因；幂等 |
| `package amendment add/confirm` | `add` 登记不可变 Amendment；`confirm` 带 expected status、确认人、确认 revision 做 CAS | 未确认为 `PENDING`；重复确认幂等；内容改写须新 ID |
| Amendment 漏登检测（`package validate` / `gate pass`） | 比较当前合同文件 blob 与 `contractBaseline`；有变化但没有覆盖该文件的 Amendment 时报告 gap | `gate pass` 拒绝；runtime 不判断是否用户可见，分类由登记者负责 |
| `ticket satisfy` | 3.6 不做 claim coverage，按 §4 校验；保留 `--expect` CAS 与 acceptance revision/environment 写入 | implementation 边释放算法不变 |
| `gate pass` / `gate blocked` | pass 执行两层核对并生成 Owner Summary；blocked 记录缺口且保持 active | pending/漏登 Amendment、stale 记录、unknown 结果或缺 artifact 时 pass 被拒 |

"已合入"机械判定为 `--revision` 可解析且是当前 HEAD 的 ancestor。`implementation` 边仍由 `ready_tickets`/`_ticket_released` 判断；`acceptance` 边仍阻止 `ticket satisfy`，`release` 边仍只在 Gate 前复核。

## 4. Ticket `SATISFIED` 依据替换

3.6 `ticket satisfy` 的校验顺序：

1. 读取 state 并用 `--expect` 做 CAS；冻结 Attempt 和非 PENDING 目标仍按旧规则拒绝。
2. 确认 `--revision` 是当前 HEAD 的 ancestor。
3. 按 Ticket Coverage 区块：每个负责套件都有有效的 `kind=suite`、`conclusion=supporting` evidence（revision 满足 §6）；`Required review` 非 `none` 时有覆盖该 Ticket、无未关闭 blocker 的 `kind=review` evidence。Journey step 不是 Ticket 的满足条件（Journey 归 Gate），避免下游未合入时上游无法满足。
4. 写入现有 `tickets[id] = {"state":"SATISFIED","acceptance":{...}}` 形状并刷新 progress。

3.5 仍走 `engine.py:1370-1380` 的 claim 分支，不读取 3.6 字段。

## 5. 两层 Gate 与 Owner 视图

### 5.1 `gate pass` 的 3.6 清单

| 层 | Gate pass 必须核对 |
| --- | --- |
| Journey 产品层 | 每个 Journey 至少一个 run 覆盖全部 step 且各 step evidence 有效（§6）、`entry` 与 Spec 一致 |
| 规则/安全层 | 必需套件表中每个套件有有效的 supporting evidence；包级安全套件（若声明）同样 |
| Ticket 与合入 | 所有 required Ticket SATISFIED；三类边按原规则释放 |
| Review | 最终 HEAD 由现有 terminal-final（含 C/Safety 复用 admission）承担，coverage 必须 known true，unknown 一律拒绝；per-Ticket review 只用于 `ticket satisfy` |
| Amendment | 无 PENDING；无漏登；CONFIRMED 绑定确认 revision 与 package 内 artifact |
| 发布顺序 | 有效的 `kind=release` evidence，其 artifact 中的条目与 Plan 声明一致 |
| 既有终态条件 | Durable Delta、live package reference、terminal lifecycle 按现有规则 |

fail-closed 只作用于 3.6：任何必需事实 unknown 即不能 pass。3.5 分支保持现状（其 unknown 放行问题另行修复）。

### 5.2 Gate 第一屏

`engine.py:1858-1862` 直接重写 `gate.md`，因此 Owner Summary 必须由 runtime 生成，而非只改模板。3.6 在 header 后、Evidence 前生成 `## Owner Summary`：`J1 走通 4/4`、`套件 3/3 通过`、`待确认修订 1 条`、`发布顺序已记录`、`最终版本 <short SHA>`，以及一句 pass/blocked 理由。Summary 行不得以 `- Verdict:`、`- Attempt:`、`- Comparison commit:` 开头，以免破坏 `_gate_info` 的正则（`engine.py:570-574`），并加 gate.md 回读测试。3.5 Gate 文本保持原结构。

`gate blocked` 不新增状态；写 blocked Gate、Owner Summary 和 next action，Attempt 保持 active，已授权且不依赖待确认语义的工作继续。

## 6. 走通记录时效

记录有效的机械规则：记录 `revision` 等于 Gate comparison commit，**或**两者之间的 diff 只涉及本 package 目录（`git diff --quiet <revision> <commit> -- . ':!<package>'`）。这是纯 Git 事实，不做代码影响推断，避免 ER、ledger、gate 等 package 内文档提交迫使人工 Journey 重跑。不满足即为待复验；artifact 缺失（仅对 active Attempt 检查）或带 `invalidatedBy` 同样待复验；environment 按 Spec 字符串精确匹配。

`package validate` 和 `gate pass` 只计算有效记录，不抹旧记录。Amendment 的 `affected` 只用于 Owner 可见性，不放宽上述规则。失败恢复从第 1 步起另起 run，不合并两轮结果。

## 7. 三项治理

### 7.1 review ledger 迁入 package

当前 `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py:25-40` 把默认目录固定在系统 Temp，`plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py:154-169` 在该目录创建 ledger；一期改为带 `--package` 时默认写入 `execution/<attempt>/reviews/<YYMMDDHHMM>-<slug>-<shortsha>.md`，并返回 package-relative `ledgerRelativePath`。`plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md:35-43,55-70`、`plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md:19-30` 和 `plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md` 同步使用该路径；leaf report、closure、terminal summary 的 artifact 都必须是 package-relative。

兼容规则：不带 `--package` 的旧调用仍可读取/更新既有 Temp ledger，但不再为 3.6 package 创建新的 Temp ledger；带 `--package` 的 create/write/show 只接受当前 package 的 `execution/<attempt>/reviews/` 路径。3.5 旧 package 不迁移，旧 ledger 可读但不成为 3.6 Gate 的唯一证据；3.6 `package validate` 发现 Temp-only 引用时报告 evidence gap。

### 7.2 资源 lease 前置

两侧都改：`skills/dispatcher/SKILL.md` 和 `skills/dispatcher/references/resource-isolation.md` 写明 Dispatcher 必须在 worker 进程启动前取得 lease；`recovery lease acquire/release` 提供最小互斥机制。lease 文件放在当前 package 的 `execution/<attempt>/leases/`，使用原子创建和 owner token，资源 key 仍由 Dispatcher 声明，不能由 runtime 从业务 Ticket 推断。

固定时序为：`lease acquire` → `trail append dispatch`（记录 `lease_id` 与 resource_keys）→ 启动 worker；dispatch/worker 启动失败立即 release；worker 返回后由 cleanup owner 完成进程、数据库/schema、端口和临时文件清理，再 `lease release`。release 必须 owner 校验、可重复调用，未释放或清理失败作为 residue 返回并阻止相关 acceptance；trail 只记录实际结果，不承担互斥。第一期不做自动 TTL 抢占、不做 seam 级 lease、不把相同 resource key 自动视为冲突，无法隔离的资源仍按唯一串行顺序执行。

### 7.3 证据落 package

3.6 的 `package validate` 对 `evidenceIndex` 与 Amendment 的所有 artifact 做相同检查：必须是仓库相对或 package-relative 的规范路径、解析后位于当前 package、revision 可解析；文件存在性只对 active Attempt 检查（沿用 `engine.py:803-870` 的 `live` 规则）；出现 `%TEMP%`、`$env:TEMP`、绝对 Temp 路径、package 外路径或缺失文件即报告 gap。旧 3.5 仅保留原有 evidence/checkpoint 校验，不因为旧 package 历史记录不在 package 而强行迁移。

## 8. Skill、reference、模板和运行时改动清单

| 文件 | 改动到的节/位置 | 改成什么意思 |
| --- | --- | --- |
| `plugin-marketplace/plugins/impl-package/skills/req-align/SKILL.md` | Ownership、主路径第 4–6 步、完成条件 | Spec Gate 必须批准 Journey 表、规则矩阵、必需套件清单；套件清单是合同，不由 Plan 临时补造 |
| `plugin-marketplace/plugins/impl-package/skills/req-align/assets/templates/spec.md` | §7 `85-91` 及 Spec Gate 相关注释 | 用 §2.1 的三类固定列表替换逐 AC 表；不写 Ticket ID；保留 rule oracle、安全不变量语义，不复制 contract-design |
| `plugin-marketplace/plugins/impl-package/skills/req-align/sub-skills/spec/SUB-SKILL.md`、`plugin-marketplace/plugins/impl-package/skills/req-align/references/spec-gate.md` | Spec acceptance coverage 与 Gate checklist | 检查 step entry/surface、suite completeness、package safety suite 和 machine-readable shape；不把“能定位到 Ticket”当作完整执行证据 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/SKILL.md` | Ticket 拆分 1、2、6、8、完成条件 | 拆票依据改为启用 Journey step 或保障已登记 suite；首票排序为窄而完整的 walking skeleton；harness 只建设第一条窄路径；3.6 不做 claim coverage |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/plan.md` | 摘要、输入、全局调度、Planned Verification、Final Gate | 增加 `Acceptance: journey`、首个可见 step、Journey/suite 顺序、package safety、release order、连续走通和 Gate 两层判据 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/assets/templates/ticket.md` | 验收标准、安全不变量、依赖 | 增加 Coverage 区块（Journey steps、Suites、Required review）；3.6 不写 stable claim 与三条 INV claim，3.5 legacy block 保留为兼容模板分支 |
| `plugin-marketplace/plugins/impl-package/skills/impl-planning/references/common-misjudgments.md`、`plugin-marketplace/plugins/impl-package/skills/impl-planning/evals/evals.json` | admission、拆票、验证误判 | 加入“局部 evidence 拼不成连续 Journey”“harness 先于 walking skeleton”“无 suite 责任的 Ticket”等负例 |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/SKILL.md` | 完整性、顺序、验证、验收检查 `24-41` | 增加首个用户可见 step 何时可走通、每 step entry/surface、suite 清单覆盖、无 Journey/suite 责任 Ticket、Owner Gate 证据和 release order 检查；不引入第二期 seam/review batch |
| `plugin-marketplace/plugins/impl-package/skills/plan-review/references/test-review.md`、`plugin-marketplace/plugins/impl-package/skills/plan-review/evals/evals.json` | Planned Verification 和 bundle admission | 检查连续 Journey 的 oracle、套件环境/入口、Amendment/Gate blocked 场景；保持按风险选择 review，不把 Journey 变成每个 step 的 review batch |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/SKILL.md` | State/ER/Trail `36-40`、Review `42-62`、Verify and Gate `64-78` | 增加每次合入后登记走通记录（reach）、套件与 review evidence、Amendment、发布顺序和时效规则；按新 `SATISFIED` 依据工作；blocked 不停工、只阻止最终 Gate |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/gate.md` | header 后、Evidence 前 | 增加机器生成的 Owner Summary；技术 artifact 后置；模板与 runtime writer 同步 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/manual-acceptance-readiness.md`、`plugin-marketplace/plugins/impl-package/skills/dev-with-track/assets/templates/execution-findings.md` | manual readiness、package-local provenance | manual Journey 记录必须有 entry/surface/环境/清理/readback；closure 和 finding 只引用 package-local artifact |
| `plugin-marketplace/plugins/impl-package/skills/do-review/SKILL.md` | Create ReviewRun、Dispatch、Report `35-70` | 3.6 传入 package-local ledger/report 路径；保留 per-Ticket topology、terminal-final 和 fail-closed review，不设计第二期批次化 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/references/output-templates.md`、`plugin-marketplace/plugins/impl-package/skills/do-review/references/subagent-briefs.md` | leaf report、terminal summary、canonical ledger | ledger path、reviewed head、ticketIds/required review 绑定可机器读取；artifact 始终 package-relative；现有 `review.terminal_summary` 继续复用 |
| `plugin-marketplace/plugins/impl-package/references/impl-package-composition-contract.md` | 权威边界、固定位置、Readiness、Ticket-only 运行边界 | 说明 3.6 的 Journey、套件、Amendment 与发布顺序 evidence 是新 acceptance contract；3.5 claim/evidence contract 原样保留；不引入 Task/DAG/seam 状态 |
| `plugin-marketplace/plugins/impl-package/references/impl-package-current-state.md` | format、State schema、Ticket/evidence、CLI | 增加 3.6 schema、路径和命令；明确 `evidenceIndex` 仍是 artifact index、state 仍唯一 writer；保留 3.5 文档和 migration boundary |
| `plugin-marketplace/plugins/impl-package/references/progressive-system-evidence.md` | 核心判断 `32`、completion evidence boundary | 删除“较早证据与真实 E2E 可组合支持同一 claim”对 Journey 的适用表述；改为局部/套件 evidence 可诊断规则风险，但不能替代一次从第一步开始的连续 Journey |
| `plugin-marketplace/plugins/impl-package/references/situation-inputs.md` | state schema、acceptance/evidence key、unknown 规则、路径输入 | 描述 3.6 的 journeyRuns、typed evidence、amendments、contractBaseline、package-local artifact 和 U/F/HF；继续说明 3.5 inputs 不变 |
| `plugin-marketplace/plugins/impl-package/skills/dev-with-track/situations.yaml`、`scripts/impl_package_runtime/protocols.json` | acceptance/Gate priority rows 和协议 | 增加 Journey 未走通、套件未通过、记录待复验、Amendment 待确认或漏登、发布顺序缺失的动作；Amendment pending 只阻断 Gate，不加入 `GLOBAL_BLOCKING_SLUGS` |
| `plugin-marketplace/plugins/impl-package/scripts/situation.py` | `_parse_state`、StateView、FactContext、`FACT_KEYS`/`WHEN_PARSERS` | **阶段 1 前置**：`_parse_state` 与 evidenceIndex 解析支持 3.6（见 §1.3）；3.6 facts 从 journeyRuns/evidence 派生，unknown 不压成 false；3.5 situation facts 和 legacy trail 兼容保持不变 |
| `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/engine.py` | format dispatch、state validate/init、evidence、Ticket satisfy、Gate writer | 实现 §1.3 分流点、3.6 schema、typed evidence、时效规则、Amendment 与 contractBaseline、Owner Summary；不修改 3.5 分支 |
| `plugin-marketplace/plugins/impl-package/scripts/impl_package_runtime/command_groups.py`、`impl_package_state.py` | package/ticket/evidence/recovery/gate parser | 注册新子命令和 typed stdin；保留旧参数和低层 trail 入口，不新增顶层命令组 |
| `plugin-marketplace/plugins/impl-package/skills/do-review/scripts/review_ledger.py` | `ledger_directory`、`validate_ledger_path`、create/write/show | `--package` 时写 `execution/<attempt>/reviews/`；旧无 package Temp 路径只读/兼容，不作为 3.6 新建默认 |
| `skills/dispatcher/SKILL.md`、`skills/dispatcher/references/resource-isolation.md` | 执行循环第 3–5 步、实际资源/完成标准 | 增加 lease acquire → worker start → cleanup → release 约束、owner/cleanup/residue 返回字段；`resource_keys` 仍不是锁 |
| `plugin-marketplace/plugins/impl-package/hooks/impl_package_hooks.py`、hooks manifest | 本期不改行为 | 只用现有 hook 回归验证 direct `state.json` 编辑仍受阻、CLI 写入仍可用；不把 hook 变成 Journey 状态 writer |

## 9. 落地阶段与提交序列

| 阶段/提交 | 变更范围 | 完成判据 | 主要验证 |
| --- | --- | --- | --- |
| 0. `fix(impl-package): package-local review ledger and pre-dispatch lease` | review ledger package path/compatibility；Dispatcher lease contract；recovery lease CLI、trail lease binding、清理测试 | 新 package 不再创建 Temp-only ledger；第二个相同 lease 不能取得；dispatch/start failure 和 worker cleanup 都释放；旧 Temp ledger show/write 兼容 | L0：`plugin-marketplace/plugins/impl-package/skills/do-review/tests/test_review_ledger.py`、新增 lease tests、`tests/test_impl_package_state.py`；L1：`tests/test_dispatcher_contract.py`、`tests/test_impl_package_plugin.py` |
| 1. `feat(impl-package): add 3.6 Journey state and runtime gates` | 先做 situation.py 的 3.6 解析，再做 engine 的 §1.3 分流点、3.6 state、typed evidence、Ticket satisfy、Gate、Amendment、时效规则 | 3.5 fixture 全部原测试通过；3.6 fixture 能 init、登记 typed evidence、satisfy、blocked/pass；Gate unknown、stale、pending Amendment 负例均 fail closed | L0：`tests/test_impl_package_state.py`、新增 Journey runtime tests、`tests/test_situation_render.py`；L1：`tests/test_ticket_first_contract.py`、`tests/test_impl_package_migration.py`、`tests/test_review_track_stats.py` |
| 2. `docs(impl-package): align Journey contracts and execution skills` | req-align、impl-planning、plan-review、dev-with-track、do-review、composition/current-state/progressive/situation references/templates/evals、Dispatcher 文案 | 所有 3.6 合同只保留一个 Journey source；旧 claim contract 明确为 3.5；技能能从 plan→init→verify→Gate 指向同一 CLI/路径；无第二期 seam/review batch 规则 | L0：各变更 Skill 的 `quick_validate.py`、`tests/test_skill_validator.py`、对应 evals/contract tests；L1：`tests/test_req_align_contract.py`、`tests/test_ticket_first_contract.py`、`tests/test_dev_with_track_verify_gate_contract.py`、`tests/test_dev_with_track_situations_review_vocabulary.py`、`tests/test_subagent_driven_development_contract.py` |
| 3. `test(impl-package): exercise Journey phase1 fixture and release bundle` | 新增最小 3.6 fixture、runtime E2E、旧包回归矩阵和 package evidence validation；不新增第二期实现 | 阶段 0–2 全部通过；最小 E2E 能得到一次 blocked 和一次 pass；旧 3.5 与新 3.6 可并存；review/evidence/lease 无 package 外唯一证据 | L0：新增 `tests/test_impl_package_journey.py` 和相关 engine/situation tests；L1：上述 runtime/skill/dispatcher 聚焦套件；最后执行 `git diff --check` 和仅相关 tests |

阶段 2 的 Skill/reference 正文由 Sonnet 按 `writing-for-agents` 起草，主 session 审核；Codex 只负责模板、evals 与测试的机械同步。审核同时看覆盖与表达：runtime 会强制的事实、边界与交接用确定规则写一次；流程内判断用启发式和正向目标表达；不堆叠"不得/禁止/必须"式防御条款，不为每种误用预设条款，同一含义只在一处出现。

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
2. 3.6 init 需要 `Acceptance: journey`；Journey 表缺 step、重复 step、空 operationEntry/observationSurface、step 或 ticket 级套件无 Ticket 认领、Ticket Coverage 引用未知 step/套件、触及安全风险却缺包级安全套件均拒绝；Spec 中出现 Ticket ID 仍按 `contract-doc-names-ticket` 报告。
3. `evidence add` 的 journey-step/suite/review/release typed record 支持单条、批量、重复幂等、批量原子失败、artifact 外部路径拒绝、invalidatedBy 和 revision/environment 校验。
4. Journey run 必须从第一个 step 连续登记；跳步、跨 run 拼接、用另一环境结果补当前 run、`entry` 与 Spec `operationEntry` 不一致均拒绝；部分 run 正确计算 `reach`。
5. `ticket satisfy` 缺合入 ancestor、缺负责 suite、suite 结果非 PASS、suite revision/environment 不匹配、required review 缺失/FAIL/UNCERTAIN 时拒绝；没有 claim evidence 但三项满足时可以通过；implementation 边释放结果与 3.5 相同。
6. 时效规则：revision 与 comparison commit 之间有 package 外 diff 时记录待复验、pass 被拒；只有 package 内 diff 时仍有效；artifact 缺失（active）、Temp-only、package 外路径同样拒绝。
7. Amendment add/confirm 的 pending、重复确认、错误 expected status、内容改变后旧 ID 确认、确认 revision 绑定和“确认后再修改生成新 pending”均有正负例；合同文件相对 `contractBaseline` 变化却无 Amendment 时 pass 被拒；pending Amendment 不阻止无关 Ticket 实施，但阻止 pass。
8. Gate blocked 保持 active、保留 next action 并渲染 Owner Summary；Owner Summary 写入后 gate.md 可被 `_gate_info` 正确回读；Gate pass 要求 Journey/套件/review/Amendment/发布顺序全部 known true；3.6 terminal coverage unknown 必须拒绝，3.5 既有路径不改变。
9. package-local review ledger 的 create/write/show、旧 Temp ledger 兼容、重复文件名拒绝、报告和 closure 引用校验；lease 双领、dispatch 前置、启动失败释放、cleanup 后释放、owner mismatch 和残留报告。
10. Situation renderer 能解析 3.6 state，并新增 Journey 未走通、套件未通过、待复验、Amendment 待确认/漏登、发布顺序缺失 fixture；3.5 `situations/` 和 `situations-a2/` 全部 expected 不变。

### 10.3 最小端到端演练

新增一个最小 `tests/fixtures/impl-package-journey/`，只包含一份两步 Journey、两个 Ticket（各认领一步并各负责一个套件）、一个包级安全套件、一个 review receipt、一个发布顺序表和一个 Amendment，不复用参考运行包的业务复杂度。测试在临时 Git repo 中执行以下序列：

1. 写入并 commit `plan.md`（含 `Acceptance: journey`）、`spec.md`、两个 Ticket、Journey/suite/review fixture 和 artifact，运行 `package init --attempt initial --plan <plan>`，断言 state 为 3.6、Ticket 为 PENDING、Journey/suite/review 尚未满足。
2. 使用 `evidence add` 登记套件与 required review；先只登记 `J1-S1`，断言 reach 为 1/2；再在同一 run 登记 `J1-S2`，断言 reach 为 2/2，state/progress/package validate 可读。
3. 对负责 Ticket 运行 `ticket satisfy`，断言不需要逐 claim evidence，且 implementation edge 仍按现有 Ticket 释放；为第二个 Ticket 补齐负责 suite/review 后满足。
4. 使用 `package amendment add` 留下一条 PENDING Amendment，运行 `gate pass`，断言命令非零、Gate/Owner Summary 显示 pending、Attempt 仍 active；随后运行 `gate blocked`，断言 blocked 记录不冻结 Ticket/Attempt。
5. 使用 `package amendment confirm`，登记 `kind=release` evidence，运行 `gate pass`，断言 `gate.md` 第一屏显示走通进度、套件、Amendment 与发布顺序，state frozen 且 `.impl-package/attempts/initial.json` 生成。
6. 负例一：提交一个 package 外代码 commit 后 `gate pass`，断言记录待复验、被拒；重新登记后才允许 pass。负例二：只提交 package 内文档后 `gate pass`，断言记录仍有效。负例三：改动 `spec.md` 不登记 Amendment，断言 pass 被拒。这个演练不访问外部系统、不启动真实浏览器/provider，真实新 package 的页面 Journey 仍由 Owner 按 Spec 的 operationEntry/observationSurface 记录 package-local artifact。

## 11. Owner 决策

2026-10-28 Owner 全部采纳下表"决定"列。

| 事项 | 决定 | 边界 |
| --- | --- | --- |
| 新包分流采用 3.6 还是 3.5+模式字段 | 采用 3.6；它是数据格式变化，不改插件版本 | 若 Owner 选择模式字段，必须另行批准 3.5 顶层 schema 放宽、缺省模式和旧包误分流的兼容合同；本计划不同时实现两套方案 |
| 第一批真实新包的 required Journey 与 suite 清单 | 每个包先选 1–2 条最关键连续 Journey，规则 suite 只覆盖 Spec rule matrix，package safety suite 按 §2.1 依风险声明 | Owner 必须在 req-align Spec Gate 中批准清单；不能由 impl-planning 或 Gate 临时补套件 |
| 生产/测试 environment 标识 | 每个 Journey/Suite 在 Spec 中列出明确字符串，记录按字符串精确匹配，不做环境相似推断 | 这决定哪些旧记录可以复用；默认不允许“同类环境”自动复用 |
| required review 的最小绑定 | Ticket 声明 required review；同一 package 的 terminal-final 仍由 do-review 完整覆盖；per-Ticket receipt 只证明该 Ticket 的 required review | 不把 review batch、seam 放行或降级 topology 放入第一期 |
| Amendment 的 Owner 身份与确认 artifact | 用 package-local `confirmedBy`、`confirmedRevision` 和 Owner confirmation artifact；不接入外部审批系统 | 未确认只能阻断最终 Gate，不阻止不依赖该语义的合法实施 |
| release order 覆盖范围 | 只记录 Spec/Plan 明确的合入、fixture/backfill、开关/发布和清理动作，作为一条 `kind=release` evidence 的 Markdown 表 | 不把每个 worker dispatch 当 release step，避免把 trail 再造一份流水账 |
| lease 残留恢复 | 第一阶段不自动 TTL 抢占；由 Owner/Dispatcher 显式 release 并留下 cleanup residue | 自动回收需要明确崩溃恢复和资源 owner 合同，属于后续风险，不在本期猜测 |
| Spec §7 的书写格式 | 固定列 Markdown 表（Owner 可读、runtime 可解析） | 若选 JSON block，解析更简单但 Owner 审批可读性下降，需另配渲染视图 |
| 3.5 Gate unknown 的 fail-open 风险（已核实：`engine.py:1846-1847` 仅在 `coverage.known and value is False` 时拒绝，无法判定时放行） | 本期只让 3.6 fail closed；另开兼容性变更修复 3.5 | 若 Owner 要一期同时修 3.5，必须把它作为独立 behavior change 增加回归和发布批准，不能悄然共用 3.6 分支 |

本计划不把参考运行包的人工 Journey 补验收直接当成新 runtime schema：它证明了 package-local 的连续步骤、API/浏览器观察、artifact 和清理记录是可落地的样例，但当前 state 仍是 3.5、原 Gate 已冻结，必须通过本期新格式 fixture 和真实新包运行验证后才可作为第一期验收依据。
