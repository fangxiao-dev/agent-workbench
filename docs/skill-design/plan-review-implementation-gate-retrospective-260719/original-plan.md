# Customer Lexware 预校验与审批 Resolution Implementation Plan

执行尝试 ID（Attempt ID）：initial
<!-- impl-package:projection revision-set begin -->
决策修订（Decision Revision）：D4
规格修订（Spec Revision）：S4
计划修订（Plan Revision）：P4
<!-- impl-package:projection revision-set end -->
执行组合（Composition）：tickets=true, dag=true
目标分支：develop
集成顺序：gate-before-merge

## Coverage And Change Map

| Spec acceptance | Execution strategy | Planned verification |
| --- | --- | --- |
| AC-1, AC-5, AC-7, AC-11, AC-13 | 建立 Application Revision、Redis precheck/只读 Binding Scan projection、renewable Customer resolution lock 与 fresh candidate query | store/lock/service unit + integration + Redis readiness negative cases |
| AC-2, AC-6, AC-8, AC-9, AC-13 | 抽出共享 Contact candidate/mapping/resolution primitives，建立 operation journal、Lexware-first mutation、已绑定 ID 的 fresh active 校验、application-guarded Lark commit/readback 与 reconciler；收缩 generic ensure bypass | workflow/action/backend adapter tests + partial-success/bound-contact fault matrix |
| AC-3, AC-4, AC-10, AC-12, AC-13 | Customer Detail 唯一 resolution dialog、Customers 状态/待同步差异投影、ERP handoff、三语言 copy 与 legacy recovery | component/route/i18n + Playwright desktop/constrained/keyboard matrix |

预计责任地图：

- `web/lib/lexware/`：共享 candidate matcher/comparison、explicit Contact resolution、mapping allowlist、operation reconciliation；保留现有 client/rate gate/checkpoint source。
- `web/lib/customer/`、`web/lib/backend/` 与 `web/lib/lark/customers-source.ts`：Application Revision、precheck/只读 Binding Scan/operation store interface、approval/profile guarded commit + readback、现有 checkpoint 写入、local/Lark adapter 传播。
- `web/app/actions/`：Registration/Profile submit 后 `after()` 调度，prepare/commit/reconcile Server Actions，旧 blind approve/retry fail closed。
- `web/components/admin-console/customers/`、ERP Contact panel 与 `web/lib/admin-i18n.ts`：状态、待同步差异、完整候选列表、radio 高亮、单一安全 CTA、归档绑定错误、entry-control handoff 和三 locale。
- `test-cases/` 与 Lexware stub：Admin E2E、negative/fault cases、entry-control contract 与 UI verification evidence。

关键依赖顺序：Application Revision/store/lock/DTO 必须先稳定；resolution orchestration 与 UI 可在共享 DTO 后并行；Lark guarded commit/reconciler 与 UI 接线完成后才能做集成 E2E；Production 不执行真实 Lexware mutation。

本计划只拥有执行顺序、文件责任和验证选择；下文出现的状态名、TTL、候选规则、字段语义与 mutation 禁令均是对当前 S4 对应章节/AC 的路由标签，不形成独立合同。若表述与 S4 有差异，一律以 S4 为准并先修订计划绑定后执行。

## Execution Strategy

### 1. 建立共享 precheck 与 runtime evidence seam

- 抽取 normalized exact-email matcher 和完整 paginated candidate projection，扩展 `LexwareContact` 的 archived/business collections display typing；建立复用现有 `lexwareContactId` 的只读 Binding Scan DTO，不改变 provider payload authority，也不新增 schema。
- 定义 `ContactPrecheckStore`、`ContactResolutionOperationStore` 与 local/Redis adapters，并实现 S4 §2/§6 的 projection freshness、retention、revision isolation 与 current-pointer 约束。
- 以现有 renewable Redis lock 模式建立 Customer-scoped lock，覆盖 precheck/Binding Scan current-pointer publish、resubmit、prepare/commit/reconcile；Production 配置/Redis缺失 fail closed，local/test 使用明确 local adapter。只读 scan 可在 rollout 前和后台按需运行，用于确认重复绑定和展示待同步差异；不建设 Contact reservation 或 binding transfer。
- Registration、pending/rejected resubmit 与 Profile Change submit 在持久化成功后使用 Next `after()` 调度只读 precheck；后台读取 missing/failed/stale 时可重新调度并轮询，不把 `after()` 当 durable queue。

### 2. 建立 explicit resolution、提交点与恢复

- 把现有 Contact mapping/fingerprint/checkpoint/GET-latest-version 能力组合到一个共享 resolution service；generic `ensureLexwareContact` 对无 persisted Contact ID 的 0/1/N 搜索不得再自动 create/adopt，ERP recovery 转为显式 resolution。
- prepare action按 S4 §2/§3 fresh load完整查询域、provider版本/指纹，返回稳定 DTO；commit action只接收冻结的decision合同并重复authoritative validation。首次绑定必须从后台只读 scan/预检差异进入，由 Supplier Operator 明确点击同步；scan 本身零写。
- commit 按 S4 `Resolution Operation` 状态机持久化 intent 与 provider-call boundary；payload组装只消费 `Effective Resolution Snapshot`/overwrite allowlist合同；provider readback 后先写journal evidence。
- provider success 后调用专用 Lark/local application-guarded commit/readback adapter；失败与恢复严格路由 S4 §3/§5 的 nonterminal state，不在plan重定义状态语义。
- reconciler 对 provider_succeeded 只补 checkpoint/approval/notification；unknown create 通过 requery、unknown update 通过 GET+target fingerprint判定，无法证明时保持人工对账。现有 approved/manual_review record 使用 active revision走相同 explicit resolution但不重复 approval。Lieferschein 和既有 linked mirror sync 在 provider call 前只 fresh GET 已绑定 ID；归档时返回 `bound_contact_archived`，不搜索、创建或重新绑定，Supplier 在 Lexware 恢复同一 Contact 后直接重试。

### 3. 落 Supplier Operator 安全交互与 ERP handoff

- Customers list/detail 显示 checking、ready-to-create、matched count、failed/stale/reconciliation 与 Binding Scan 待同步/duplicate 状态；approve 在 precheck 未就绪时不可直接 blind submit。
- 复用 `AdminDialog`、`Button`、`AdminInlineActionResult` 与 ERP diff primitives，建立 domain wrapper：Header 显示 Customer 与匹配 email；body 完整渲染 N 个候选 radio rows；初始不选；选中后以 border/background/check state 持久高亮；raw provider ID 不作为普通文本。
- 候选比较组件完整消费 S4 `Candidate Summary` 与 AC-4/AC-13，不在 UI 层重新定义字段或候选可选性；归档候选只提示且不可选，归档绑定的 Lieferschein 错误必须说明“在 Lexware 恢复同一 Contact 后重试”。
- Footer 在桌面右对齐、constrained viewport纵向排列，只有 Cancel 和一个明确主 CTA；Cancel 零写；未选/加载/不可选时 disabled并说明；pending 时禁关闭/切换/重复提交；stale 结果保持 Dialog 打开、清除选择并刷新列表。
- ERP Master Data manual-review 行移除死循环 Retry并链接 `/supplier/customers/{customerId}#lexware-contact-resolution`；Customer Detail 是唯一 resolution surface。
- 新 copy 归入 `customers.detail.lexwareResolution.*`：Lexware/Kundennummer/VAT 等 Class 1 复用 proper-nouns；Customer/状态为 Class 2；说明、CTA、错误为 Class 3；三个 locale 独立 author，不使用 locale spread。

### 4. 集成、rollout 与回滚

- 更新 local fixtures、BackendServices contract、Lexware stub 和 Customer/Profile action tests，保证 required fields 从 producer 到 adapter/consumer完整传播，mock 不预填理想 operation evidence。
- 默认验证只使用 local/mock、Redis stub 与 Lexware stub，不进行真实 Lexware create/update；可选 Production 仅做 read-only candidate query，需另行明确授权。
- 部署前执行 S4 AC-11/AC-13 及 archived query-scope readiness gate；后者必须有官方语义与受控 read-only integration evidence，不能以 stub 代替。
- 上线后通过后台首次打开或只读脚本为现有 pending requests 建 projection，并做一次性 existing `lexwareContactId` duplicate/binding scan；当前没有绑定的空字段不回刷、不批量写入。扫描发现的差异在 Supplier Admin Console 显示，只有 Operator 显式同步才走 resolution mutation；当前 approved/manual_review incident 由 legacy resolution UI人工选择处理，禁止自动 mutation。
- 回滚代码时先关闭新 prepare/commit入口并保留 operation journal/reconciler读能力；存在 `provider_succeeded|needs_reconciliation|provider_outcome_unknown` 时不得恢复旧 generic Retry或删除 journal。只有所有非终态 operation清零后才可完全移除新 orchestrator。
- #217 改为本 package 的 tracker 指针，删除 create-distinct/auto-adopt旧方向，记录 0-vs-N contract、Lexware-success-before-approval、legacy recovery 与 no-real-mutation默认验证。

## Planned Verification

| Verification | Expected result | Evidence owner |
| --- | --- | --- |
| Focused unit/service suites for revision, store, lock, candidate matcher/comparison, mapping, journal and reconciler | 0/1/N、TTL/out-of-order、renewal、preservation 与 typed state cases green | implementation workers |
| Backend/action integration for registration, resubmit, profile change, guarded approval commit and legacy recovery | required-field propagation、mutation ordering、readback 与 no-bypass cases green | integration owner |
| Fault-injection matrix | stale/forged/archived candidate均0写；bound Contact archived阻断且恢复同一 ID 后可重试；provider success + Lark failure重放0 provider writes；unknown outcome不 false-pass | safety reviewer |
| Component/route/i18n tests and `npm run check:i18n` | dialog/a11y/entry control与三 locale structural/semantic coverage green | UI/i18n owner |
| Admin Playwright with Lexware stub at 1366×900 and 390×844 | N candidates全展示、radio高亮、footer、focus trap、keyboard、无 clipping/overflow、ERP handoff到达稳定 anchor | browser verification owner |
| Focused regression plus `npx tsc --noEmit --pretty false` and `git diff --check` | Customer approval/Profile Change/ERP existing linked sync无回归；workspace clean enough for gate | integration owner |
| Optional real-provider evidence | 默认 not run；只有 Owner批准精确 read-only target后才查询 candidates，绝不 create/update | Owner/manual |

最小 false-PASS matrix：

- precheck 0、commit前变1：create必须拒绝并返回候选。
- candidate version/fingerprint/set变化：overwrite必须拒绝且0 PUT。
- create response丢失：普通 retry不得再次 POST；requery不能唯一证明时保持 unknown。
- update response丢失：GET target不一致时保持 unknown，不得把请求发送过等同成功。
- provider调用完成后、journal evidence写入前进程退出：恢复不得增加provider call count；provider success后Lark guarded commit/readback任一点失败也不得错误显示完成。
- provider明确无side-effect failure后允许新revision；从provider_call_started起，resubmit/profile replacement与commit竞争必须由同一Customer lock阻断。
- legacy/异常snapshot缺company/contact/email/phone/完整address任一required值：resolution必须在provider call前阻断，不能把空值变成清空操作。
- Redis lock/journal不可用：在 provider mutation前失败，不能退化到单进程锁。
- 已绑定 Contact fresh GET 为 archived：Lieferschein 返回明确恢复指引且 Lexware/Lark 均0写；将同一 ID 恢复 active 后重试不做邮箱搜索或重新绑定。
- Binding Scan 发现空绑定、差异或重复：后台可见且扫描0写；只有 Operator 明确点击同步才可进入 prepare，首次 rollout 不批量回刷。

## Integration Order And Composition

- Composition：`tickets=true, dag=true`，因为至少三个独立验收 Slice 且共享 DTO/store contract 后存在可并行的 orchestration 与 UI 工作线。
- 第一波：共享 revision/precheck/store/lock/candidate contract。
- 第二波：resolution/approval/reconciler 与 Admin UI/i18n/ERP handoff并行。
- 第三波：adapter propagation、Lexware stub、integration/E2E、risk review 与 gate evidence。
- 默认 `gate-before-merge`；不得以 task/ticket局部绿替代当前 D4/S4/P4 的集成 gate。

## Execution Record

当前无执行记录；implementation 开始前必须先通过 committed binding validation。后续检查只追加稳定 `ER-n` entry，不回改历史证据。

### ER-1 — T5 read-only probe restore (2026-07-19)

- Attempt / revision：`initial` / D3-S3-P3；Comparison point：`ff429973d0e62822ee1b339300cb73c696aa8868`，基于 package baseline `7c9551d1b9229f8751d68983a9783dc58b5e677a`。
- Scope：恢复 Lexware Contact read-only probe、read-only runtime、combined wrapper 与 Article `--supplier-code` parser；Contact email gate 使用 normalized exact-email filter、full `listContacts` pagination result、Contact ID 去重与 active/archived bounded evidence；默认多候选仍 fail closed，`--require-active-and-archived` 是显式 query-scope readiness mode。
- Owner authorization：当前会话 owner 已批准“修复/恢复该只读 probe”，并允许主 session 调度 bounded subagent；本 ER 未授权或执行任何 Lexware/Lark/Redis mutation。
- Local verification：5 focused test files / 120 tests passed；`npx tsc --noEmit --pretty false` passed；targeted ESLint passed；`npm run check:test-cases`、`npm run check:case-status` 和 task-scoped synthetic-env `npm run check:lexware` passed。
- Review：code review 与 safety review 均未发现 P0/P1；read-only runtime 只暴露 `GET` methods，并在 mutation boundary 设置 defense-in-depth rejection；无 POST/PUT/外部写入证据。
- Findings / remaining evidence：P2 provider-scope evidence gap 仍开放，原因是 Lexware 官方文档未明确承诺 email-filtered query 覆盖 archived，且本 ER 未运行 live read-only query；`npm run test:test-cases` 的 existing wrong-index unit failure 在当前 develop/main workspace 同样复现，未归因于本 delta。
- Runtime state：T1–T5 仍为 `PENDING`，4 个 Ticket 仍为 `UNRECORDED`，未创建 artifact 或 gate entry；局部产出与下一动作见 `tasks/T5-progress.md`。

### ER-2 — controlled Lexware Contact read-only query (2026-07-19)

- Attempt / scope：使用 `prod-like` profile 对 owner-supplied safe email target 执行 `smoke:lexware-contacts-readonly`，先运行显式 `--require-active-and-archived` gate，再运行默认摘要模式；tracked evidence 不保存目标邮箱或联系人明细。
- Provider result：默认摘要返回 `providerMatchCount=1`、`duplicateProviderResultCount=0`、`matchCount=1`、`activeMatchCount=1`、`archivedMatchCount=0`；唯一 exact candidate 的 bounded `archived` 值为 `false`。显式双态 gate 以 `active=1, archived=0` fail closed。
- Read-only boundary：请求通过 read-only runtime 的 Contacts list GET 路径；本次未执行或授权任何 `POST /v1/contacts`、`PUT /v1/contacts/{id}`、Lark、Redis 或邮件写入。
- Interpretation / state：本次仅证明该 tenant/target 当前返回一个 active exact candidate，不能证明 email-filtered query 覆盖 archived Contact，也不能关闭 archived query-scope readiness gate；T5 仍为 `PARTIAL`，T1–T5 仍为 `PENDING`，4 个 Ticket 仍为 `UNRECORDED`，未创建 gate entry。

### ER-3 — second controlled Lexware Contact read-only query (2026-07-19)

- Attempt / scope：使用同一 `prod-like` profile 对第二个 owner-supplied safe email target 执行 `smoke:lexware-contacts-readonly --require-active-and-archived`；tracked evidence 不保存目标邮箱或联系人明细。
- Provider result：显式双态 gate 返回 `active=2, archived=0` 并 fail closed；该结果未提供任何 archived exact candidate。
- Read-only boundary / state：请求仍通过 Contacts list GET 路径，未执行或授权任何 Lexware、Lark、Redis 或邮件写入；T5 仍为 `PARTIAL`，T1–T5 仍为 `PENDING`，4 个 Ticket 仍为 `UNRECORDED`，未创建 gate entry。

### ER-4 — D4/S4/P4 approved bundle revalidation (2026-07-19)

- Owner approval：Owner 已批准核心合同与初始计划，包含现有 `lexwareContactId` 绑定、归档 Contact 在 Lexware 恢复同一 ID 后直接重试、只读 Binding Scan/显式同步，以及不新增 schema、reservation 或 binding transfer。
- Joint validation：4/4 Approved Tickets 与 T1–T5 DAG 已按 D4/S4/P4 更新；Ticket 覆盖、typed implementation edges、Task primary ownership、contributes-to 映射、AC evidence feasibility 和无环依赖均复核通过。
- Runtime boundary：该记录只确认计划 bundle；T1–T5 仍为 `PENDING`，4 个 Ticket 仍为 `UNRECORDED`，没有代码实施、外部 mutation 或 terminal gate。

## Revision History

| Previous | Current | Change | Impact |
| --- | --- | --- | --- |
| none | P1 | 初始实施策略、Composition、验证与 rollout | 被 P2 取代 |
| P1 | P2 | 纳入 Effective Resolution Snapshot、required field 阻断与 no-clear 验证策略 | 全部 initial tickets/tasks 需按 S2 执行 |
| P2 | P3 | 收口终审 P1/P2：provider-call crash、archived query gate、guarded commit、resubmit lock、a11y与evidence anchor | 全部 initial tickets/tasks 需按 S3 执行 |
| P3 | P4 | 落实既有 binding、只读差异扫描/显式同步与归档绑定恢复；移除 Contact reservation/occupancy 流程 | T1-T5 与全部 tickets 按 S4/AC-13 重验证 |
