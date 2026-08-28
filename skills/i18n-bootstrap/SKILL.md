---
name: i18n-bootstrap
description: 把零 i18n 应用自举到有明确 ownership 的 messages catalog，并在首个代表 surface 验证后按 gate 放开规模化抽取/迁移；覆盖 Inspect、Decide、Classify、Dedup、Scaffold、值不变 Migrate 与 Locale-format。用于首次引入 i18n、next-intl、messages 目录，或已有 bootstrap seam 后向更多 app/surface 铺开；审计、browser 验收和翻译质量交给后续流程。
---

# i18n Bootstrap

把项目从散落字面量迁到可运行的 message catalog 边界，同时保持当前 copy 不变。基础设施、message ownership、迁移证据和后续翻译质量必须分开。

默认先做只读规划；只有用户授权后才修改。保留已有 dirty files，并在实跑记录中区分运行前已有 scaffold 与本轮改动。

## 分类权威

执行 Classify 前读取同级 [`../i18n-advisor/SKILL.md`](../i18n-advisor/SKILL.md)。Class 0–3 只以 advisor 为权威，本 skill 不建立第二套分类。

确认 advisor 使用以下边界：

- Class 0：内部机器身份，不承载面向用户的领域含义。
- Class 1：用户可见、必须保持稳定的身份，即便它看起来像代码。

`dynamic/business data`、`locale-sensitive value`、`needs_context` 与 Class 0–3 正交。若 advisor 缺失或仍只有旧名 `i8n-advisor`，停止并报告依赖不一致。

## 七步主流程

### 1. Inspect

识别框架、当前 locale 行为、authored copy surface、已有 catalog 或半成品 scaffold、组件 ownership、render/test 模式、硬编码 display locale，以及必须排除的 carrier。

静态数字只能称为 **candidate inventory**，不能称最终 key 数；同时记录 under-count 与 over-count 边界。AST 已知属性清单容易漏掉 UI config arrays、label maps、fallback helpers 和 transport error 映射，必须补一次按 surface 的人工扫尾。扩大 extraction glob 前，先区分 UI copy、API error、wire value、fixture、generated source、冻结 contract 和运行时 business data。

完成条件：Inspect 记录明确 candidate scope、排除项、message owner、测试入口、locale-sensitive display、运行前 dirty paths 与未决 `needs_context`。

### 2. Decide

显式决定并记录：

- supported、default 与 test locale；
- locale resolver 和非法 locale 行为；
- routing 或 without-routing 架构；
- 缺 key 行为，以及如何避免跨 locale 的 wrong-language fallback；
- provider 与 request-config 边界；
- app-owned 和 shared messages 的唯一 owner；
- 值不变迁移的证据，以及切换器加入时点。

任何一项仍是隐含假设时，不开始抽取。

完成条件：实施者能够明确说出 locale 来源、fallback、message loader、每个 shared namespace 的 owner、测试 locale，以及值不变阶段与新增 UI 的边界。

### 3. Classify

按 referent 使用 advisor 分类：

- Class 0 machine value 跳过；
- Class 1 登记稳定拼写或批准的 canonical locale value；
- Class 2 领域词和 Class 3 UI copy 进入 messages；
- dynamic/business data 不进 catalog；
- 日期、数字、金额、单位进入 locale-aware formatting；
- 不确定项保持 `needs_context`，查证前不猜。

单条 mixed literal 内逐 token/referent 判断，只保护已确认的 Class 1；不能因为含 Latin 字符就整条保留。

完成条件：每个候选都有 Class 或正交处理路径，没有未查证值被猜进 catalog。

### 4. Dedup

在 key 命名和 catalog 建立之前独立做 semantic dedup。只有同一 surface 上指向同一概念的跨语言 literal 才合并。建立 catalog 前，为 authored copy 使用稳定 semantic key，不生成由行号或文件位置派生的 position key。exact duplicate 只是线索，先按 referent 审核，确认相同后才共用 deliberate key；字面相同但 referent 不同不合并。启发式概念组必须逐 referent 复核。key rename 必须同步所有调用点及术语、证据引用。

在 key 结构仍可调整时登记 ICU plural、插值、词序和句子碎片风险；business data 不参与 dedup。

完成条件：每个范围内概念只有一个 deliberate key，或有保留多个 key 的明确原因；歧义继续留在 `needs_context`。

### 5. Scaffold

只建立 runtime 和 tests 真实需要的基础设施。可复用 locale 常量、cookie 名、request-config factory、ICU formats 和同步测试 provider 归基础设施；messages 跟组件或 app owner 走。

不要把 feature messages 放进基础设施包，也不要给每个 consumer 复制一份 shared namespace。

request config 与 test provider 显式固定产品 `timeZone`，避免 server render 因宿主机时区不同而漂移。测试 wrapper 必须接入实际的 `renderToStaticMarkup` call sites；仅创建一个未被调用的 helper 不算完成。

基础设施包必须保持 client/server import graph 分离。依赖 `next/headers`、`next-intl/server` 的 request config 只从 server-only 子路径导出；client provider 只能导入 locale、format 和 fallback 等 client-safe 模块。TypeScript 和 Vitest 不足以证明这条边界，至少跑一次受影响 app 的 production build。

完成条件：每个 app 都能从既定 request boundary 解析 supported locale；shared messages 只有一个 owner；所有受影响的 render 入口实际使用 provider；production build 没有 client/server import 错误；没有时区告警，也没有引入无关路由或 runtime 层。

### 6. Migrate

先做值不变迁移：

- source/test catalog 原样收录当前 literal，包括现存外语残留；
- 只改变取值方式；
- dynamic data 与 Class 0 留在 messages 之外；
- mixed 句中的 Class 1 token 原样保留；
- count 和可变词序使用完整 ICU message；禁止把一句话拆成前后 fragment key，因为插值边界的空格和标点很容易漂移；
- 现有测试要求同步 render 时，组件保持同步。

改 lookup 前先保存 exact render output。迁移后用同一 fixture 和显式 test locale 做 exact comparison，再跑 focused render specs；仅有 substring assertion 全绿不能证明完整输出相同。

完成值不变证据后再做 Locale-format 或新增语言切换器，因为这些改动会合法改变输出，需要独立证据。

若 exact comparison 失败，先检查 fragment、插值两侧空格、标点和条件分支；不得更新 baseline 来掩盖迁移漂移。

完成条件：选定 fixture 的 exact comparison 通过；focused specs 报告真实结果；每个迁移值可追溯到迁移前 literal；迁移验收检查 `(?:^|\\.)l\\d+_\\d+$` position key 为 0。

### 7. Locale-format

把用户可见日期、时间、数字、金额和单位的硬编码 locale 换成 active locale，并保持 display value 与 canonical value 分离。

ISO input、wire date、filename、ID、status code、payload decimal、hash 等机器格式保持不变。不能通过写入 messages 来“本地化”运行时 business data。

完成条件：已知用户可见硬编码 locale 都有 active-locale 来源，并在至少两个 locale 下做 targeted verification；wire/identity value 未被误改。

## 规模化铺开快路径

一个代表性 app 或完整 surface 已跑通七步并关闭机械风险后，停止重复 tracer batch。后续把 **抽取/规范化** 与 **翻译校准** 分成两条 lane：前者在 gate 稳定后全量放开，后者先用一个完整 catalog 标定质量，再决定放开程度。

### 抽取/规范化放行

同时满足以下条件时，后续 owner scope 可按 namespace 全量抽取，不再逐个小页面试跑：

- shared namespace 的唯一 owner 和所有 consumer loader 已跑通；seam correctness 与已迁移 authored-copy coverage 分别计数；
- 抽取器直接产出 deliberate semantic key，position key 为 0；exact duplicate 已按 referent 复核，preserve 的 carrier 排除、Class 1 token 保护和 dynamic/business-data 旁路均生效；
- exact comparison、source-adjacent focused specs、shared consumer specs 和受影响 app production build 已通过；
- 至少一次实跑已记录 candidate inventory 与 actual leaf 的偏差，并用实际密度重估剩余范围。

大范围执行时按 owner/namespace 划互斥 scope。并行 worker 产出 mapping、调用点修改和局部证据，不同时写同一正式 catalog；主控统一集成一次。每次集成先跑便宜的 catalog gate，完整 typecheck/lint/build 以 owner batch 为单位运行，不在每个机械 shard 重复。

以下任一项失败就收回机械放行，修规则后从失败 scope 重跑：position key 回归、未登记 duplicate、Class 0/runtime identity 进入 `t()`、ICU 参数漂移、shared messages 出现第二 owner、exact comparison 漂移。

### 翻译校准交接

翻译不属于 bootstrap，但 bootstrap 必须给后续本地化流程提供可判定的输入：

1. 在翻译前完成 P0 术语表，按 referent 记录推荐词、禁用词和 occurrence 边界；
2. 选择一个已 100% 抽取并规范化的完整 catalog 做最后一次校准，不再用零散小样本；
3. 术语约束覆盖率只以“应受术语约束的 leaf”为分母；独立复核修正率以本轮新译 leaf 为分母；
4. 默认以修正率 `<5%` 作为可全量放开的强信号，`5%–20%` 由错误类型和 owner 裁定，`>=20%` 先补术语表或翻译规则；项目可设置更严格阈值；
5. 后续翻译 shard 只写互斥 draft/overlay，独立语义复核后由单一 owner 合并正式 catalog。

### 独立 gate 与常见弯路

- **candidate 不是承诺数**：AST dry-run 容易漏 config arrays、helper maps 和 fallback copy；排期只在首个真实 surface 后重估。
- **semantic key 前置**：先去重和命名，再翻译。翻译后再清理 position key 会同时重做 catalog、调用点、术语引用和 review 证据。
- **占位符与错语言分开**：`CJK = 0` 只证明目标 catalog 没有源语言泄漏；同时报告 placeholder count。默认 locale 仍有 placeholder 时可以是 bootstrap 中间态，但不是 demo-ready。
- **seam 不等于 coverage**：consumer 能从唯一 owner 加载少量 shared messages，只证明 ownership；必须另报 shared surface 已迁移 leaf/候选总量。
- **机械 gate 不证明语义质量**：key parity、snapshot 和 build 全绿不能替代 occurrence、德语自然度和术语复核。
- **语言选择器先看 layout ownership**：加入 switcher 前列出 root layout、auth/status route 和业务 shell 的预留位置；每个渲染页面只保留一个交互式 switcher。复用同一行为组件的 inline/floating variant，选项显示 endonym，accessible label 本地化；不能同时保留全局挂载和 shell 假标签。

完成条件：抽取 lane 有明确放行/收回条件，翻译 lane 有完整 catalog 校准和阈值，remaining forecast 使用 actual density；没有把 bootstrap runtime、demo readiness、翻译质量或 browser acceptance 混成一个结论。

## KaiSpan Next.js 固定合同

当仓库是 KaiSpan 或任务明确给出本 profile 时，执行以下已定决策：

- Next.js App Router + `next-intl`，使用 **without-i18n-routing**。不新增 `app/[locale]`、locale middleware 或 locale matcher。
- locale 只从 `NEXT_LOCALE` cookie 读取。request cookie 缺失或非法时使用 `de-DE`；不从 search params 或 `Accept-Language` 推断。
- 切换器通过 server action 校验并写 cookie，client 随后调用 `router.refresh()`；不使用 `?lang=de`、`document.cookie` 或 `window.location.reload()`。
- runtime 默认 locale 是 `de-DE`。德语缺 key 不回落 `zh-CN`：开发期显式失败，运行期显示 namespace/key 或其他明确标记。
- tests 和值不变 render snapshot 显式固定 `zh-CN`。
- 组件 copy 使用同步 `useTranslations()`。禁止用 async `getTranslations()` 迁移组件；本仓库的 `renderToStaticMarkup` specs 无法渲染 async Server Component。provider 装配可以使用 `getLocale()` / `getMessages()`。
- 阶段 A = scaffold + 值不变迁移 + exact comparison。随后独立执行 Locale-format。阶段 B 再加入 server-action switcher，避免新 UI 污染阶段 A 证据。
- `packages/i18n` 只放 locale 常量、cookie 名、request-config factory、ICU formats 和测试 render wrapper。
- KaiSpan request config 与测试 provider 显式使用 `Europe/Berlin`，保证 server render 确定性。
- app 自有 messages 留在 `apps/*/messages/`。共享 accounting workbench namespace 只留在 `apps/web/messages/`；tax-web 沿现有跨 app seam 加载，不复制。
- `de-DE.json` authored catalog value 出现任何 CJK 字符即失败；该 gate 不扫描 runtime business data。
- `[de-DE:...]` placeholder 与 CJK 分别计数；placeholder 非零时明确标记为不可演示中间态，不能用 `0 CJK` 宣称德语已就绪。
- 德语措辞暂时拿不准时，先给德语草案或明确标记，不把中文留在德语 catalog；翻译质量复核不属于 bootstrap。

Finance/DATEV surface 存在时，读取仓库当前的 `docs/implementations/2026-08-28-de-localization/preserve-list.md` 与 `extraction-inventory.md`。不要把其中的候选数量、行号、Mandant 数据或完整术语表复制进本 skill。

执行已记录的 owner 裁定：

- `SKR03` 是 Class 1；`domestic_vat`、`reverse_charge` 是 Class 0。
- `Kontierung` 是 locked Class 1 token。
- `Description` 是 Class 2，不得进入 token allowlist。
- `Reinigung` 按 occurrence 判断。
- mock 科目标签是 dynamic/fixture data，不是 Class 1。
- 银行对账使用 `Abgleich`，单据归属使用 `Zuordnung`；两者是不同概念和不同 key。
- `Category`、`Sachkonto`、`Kreditor` 是不同概念，禁止 dedup。

## 交接与证据

报告：

- scope 与运行前 dirty paths；
- 实际动作和 exact command；
- 本轮拥有的 changed paths；
- exact comparison 与 focused-test 结果；
- locale-format、missing-key 检查；
- placeholder count、默认 locale 的 demo readiness，以及 shared seam correctness / migrated coverage 两个独立结论；
- 未运行项与未证明边界；
- 只在真实实跑中发现的事项；
- plan/preserve 已知约束；
- 因实跑产生的 skill 修订。

不能把 focused component test 升级成 browser acceptance、catalog 状态、package Gate 或 release readiness。localized catalog 存在后，由 `i18n-advisor` 执行客观 catalog gate 与 scoped browser verification。
