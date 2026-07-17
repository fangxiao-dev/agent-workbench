# Impl-Package 体系优化分析（基于 DATEV 实例）

- 日期：2026-07-17
- 分析对象：`skills/impl-package/`（入口 SKILL、composition contract、各 stage skill）
- 参照实例：`D:\CodeSpace\kaispan-dev\.worktrees\datev-accounting-rules-implementation\docs\domains\finance-assistant\implementations\2026-07-16-datev-accounting-rules`（D5/S9/P6，7 tickets，9-task DAG，40 条 ER，T1–T6 DONE，T7/T8/T9 待外部输入，尚无 gate.md）
- 性质：分析报告 + 已确认方向的实施 handoff。分析轮未修改 SKILL/契约；「结构化状态层」方向已获 owner 确认并记入 `skills/impl-package/rubric.md`（R7，2026-07-17），实施交由后续 session（见文末"新 session 实施指引"）。候选项已按该 rubric 与 global rubric 的已确认原则过滤（见文末报备）。

## 实例总体判断

体系的核心机制在这个高压实例里是成立的：append-only ER、非实现者 task review、fail-closed 验收语义、外部证据 hash 绑定、"task DONE ≠ package closed" 的边界纪律都被严格执行，而且多次真实拦截了 false PASS（Prüfprogramm PASS 不冒充导入成功、mock 不冒充 OCR 能力、materialized 不冒充 validated）。以下发现是体系在真实负载下暴露的缝隙，不是方向性问题。

## 维度一：效率与冗余（agent 读者视角）

### 1.1 体量与重复度基线

一个 stage 执行会话的必读集 ≈ 入口 SKILL（10.8KB）+ composition contract（27KB）+ 对应 stage skill（7–17KB），合计 40–55KB，可接受。但同一语义存在三份平行表述：impact signals 出现在 contract §2、入口 SKILL 正向路由、req-align fast path；findings 分流规则在 contract §6 与 dev-with-track "Findings curation" 几乎全文重复；gate entry 语义在 contract §7 与 dev-with-track 各写一遍。对 agent 读者，就地重述省一次跳转，有导航价值；代价是增量维护时三份措辞已开始出现细微差异（分流规则的措辞在两处不完全一致）。这违反体系自己"不复制正文、只给指针"的原则——契约是 normative shared contract，stage skill 应引用加最小操作化补充，而不是近全文重述。

### 1.2 过度 canonical 的最典型证据：revision-blob binding 在实例中失守且反噬

这套机制是为"防止 alias 与内容脱节"设计的机器校验，但实例给出两个信号：

- **机制未被维护也没有阻碍执行**：spec 升到 S9，sidecar `current.spec` 指向 S9，但 `bindings[]` 只登记到 S7——按契约 §2 这是 P2 capture gap，实例在这个状态下继续跑了十几条 ER 无人发现。登记步骤只写在 req-align workflow 第 8 步（面向 gate 刚通过的时点），而 S8/S9 是执行期 review remediation 触发的升级（ER-32/ER-34），发生在 dev-with-track 的循环里，没有任何检查点会再碰 sidecar。
- **机制反过来制造了正文漂移**：plan header 仍声明 S7。因为更新 header 的 S 引用会改变 plan blob → 破坏 plan-contract-v1 binding → 按规则要升 P，而 impl-planning 又规定"只有 plan-owned 语义变化才升 P"。agent 被夹在中间，选择不更新 header，然后用一整条 ER-35 来合理化"plan header 是历史发布绑定，不是 current contract"。同文件内 ER-32 起写 D5/S8/P6、ER-34 起写 D5/S9/P6，header 却是 S7——ER 的 Revision set 到底指"当时 current"还是"plan 发布声明"，契约未定义，实例两种用法都出现了。

另外 plan-contract-v1 的校验算法（读 baseline blob → 把两边 ER 替换为固定 marker → 逐字比较）是让 agent 手工模拟程序，实例 40 条 ER 中没有任何一条记录真的执行过这个比较（ER-1 只做了 blob 相等核对）。为程序设计的精确算法在 agent 执行下只会得到名义遵守。

**候选 A（护栏，高优先级）**：契约 §2 加一条——升级 alias 与登记 binding 是同一动作不可分离；`current` 指向无 binding 的 alias 时不得追加 ER 或 gate entry，先修复。嵌入既有表面，不新增阶段或 artifact。

**候选 B（消除歧义，高优先级）**：把"机械 revision 引用更新"明确为 plan 的同 alias rebinding 路径（即把 rubric R5 已采纳的 editorial rebinding 从 design/spec 扩展到 plan），同时定义 ER Revision set 的语义（建议：写入时的 current revision set）。二者配合后 plan header 可以随 S 升级机械刷新而不升 P。

**候选 C（降成本，中优先级）**：plan-contract-v1 校验允许等价的 Git 层判断（例如"自 baseline commit 以来对 plan 的 diff 仅落在 ER 区间"），或明确该比较由脚本执行；不要求 agent 手工模拟 blob 替换比较。

### 1.3 ER 承载了不属于它的高流失数据

ER-24/26/30/38/39 每条重述 4–8 个 SHA-256 并宣布上一批全部 superseded，五次换血。这些 hash 的事实源是 manifest 文件；ER 里的全量重述是重复投影，与 rubric R4"最小事实"偏好直接冲突，也是 plan 膨胀到 70KB（读取需分页）的主因之一。

**候选 D（中优先级）**：契约 §6 或 dev-with-track Verification record 加一句——ER 记录 delta 与指向 hash SoT（manifest/交付清单）的指针，不重复投影可从权威 artifact 读出的完整 hash 清单。

## 维度二：面向人的可用性

### 2.1 分层设计意图正确，但 owner 视角的"当前状态"仍散落

talk-to-boss 先行、canonical handoff 后置、gate.md 顶部一行可变状态——这些设计是对的。实例中真正好用的人读界面是 **DAG 的 Runtime State 表**（每个 task 一行：状态 + 一句话证据 + 指针），owner 关心的"到哪了、还差什么"在这张表里最完整。相比之下 plan 对人不可读：同样的信息要从第 40 条 ER 的残余风险段落里挖。这不需要新 artifact——体系已经有正确答案（Runtime State 表 + gate.md 状态行），问题只在 no-DAG 的 attempt 没有等价物，以及 handoff 模板没有明确把"当前状态一览"放在最前。观察项，暂不提案。

### 2.2 约束条目吸收 review finding 后膨胀成不可读长句

spec §6 的 tenant/授权约束条目在历轮 remediation 中被逐次追加，现在是一条 200+ 字、含七八个分号的 run-on 句子。体系对"约束吸收多轮 finding 后应重组"没有任何引导——而 editorial rebinding（R5）恰好是承接这种零语义重写的通道，只是没人提示这么用。

**候选 E（低优先级，可并入 B）**：在 req-align 或契约的 editorial correction 定义处加半句：条目膨胀损害可读性时，鼓励做零语义重组并走 editorial rebinding，不必等下一次语义 revision。

### 2.3 面向人的 hash 洪水

同 1.3。owner 需要的是"当前有效的两个交付包是哪个、各验证到什么程度"，而不是新旧 hash 对照。候选 D 同时解决人读问题。

## 维度三：设计与计划本身的质量

### 3.1 spec 的异常边界：业务层完备，机制层是返工黑洞

你之前的观察是"spec/design 漏异常边界导致返工"。这个实例的证据更精确：spec §5 在**业务层**非常完备——22 个失败模式，每个有稳定错误码、可观察影响、隔离方式、恢复路径和 owner，负向 AC（AC-05/19/20/21/22）覆盖也好。返工集中在另一层：**机制级 fail-closed 不变量**。ER-25 到 ER-36 六轮 safety/Standards review 挖出来的 P1 全是同一形状：

- decision commit point 信任了 caller 传入的 policy revision / approved fact，未在事务内复验持久化快照（ER-27/29）；
- capability token 可重放、未绑定不可变内容（ER-29/30）；
- final claim 未回查 fact 仍 active、reviewed hash 未漂移（ER-32/33）；
- `null === null` 让 unit scope 校验退化通过（ER-34）。

这些在 S7 里都不存在，是 review 逐层挖出后以 S8/S9 补录进 spec 的。conditional evidence-integrity contract 其实问对了问题（commit point、post-side-effect failure、投影完整性），但它只要求"写出 commit point"，没有引导深度与风险成比例——"commit point 是 decision 事务提交"一句话就能过 Spec Gate，而 review 追问的是"commit point 之前，每个被信任的输入是否在同一事务内对权威源复验"。

**候选 F（高优先级，通用判断约束而非新结构）**：evidence-integrity contract 触发时，Spec Gate 增加一条判断约束——每个 commit point 须列出它信任的输入（caller 声明、持久化快照、外部证据、上游 hash）及各自的复验来源；无法列出即视为 contract ambiguity。一条约束对应了本实例六轮返工的共同根因，符合 R6"可跨场景复用的判断约束，不引入新分类法/表格/artifact"。

### 3.2 review 反复的两个层面：task 级已有 in-flight 修复，正式 review 级还没有

你说 subagent-driven-development 对 spec review 的规则不完善导致反复 review。实例证据分两层：

- **Task 级**：T1 四轮 spec-compliance + 两轮 quality（拒绝码 → decimal 递归 → treatment evidence → controlled label），每轮 reviewer 只审"上轮 finding 修没修 + 顺手再发现一个"，没有首轮完整覆盖承诺。工作区未提交的 review basis + closure review + coverage gap 改动直接命中这个问题（basis 先行、closure 只复查受影响行、基线外新发现必须补基线后完整重审），方向正确，且 prompts.md 已把覆盖对照表写进三个模板。**这层不需要再提案，建议按现状落地并用下一个实例验证。**
- **正式 review 级（缺口仍在）**：module-review/safety-review 的 fixed-range 循环没有 basis 概念——ER-25 到 ER-36 每轮都是全量三轴重审，发现 1–2 个 P1，修完换 fixed head 再全量来一轮，六轮才收敛，且 subagent quota 正是被这个循环烧穿的。**候选 G（中高优先级）**：把同一方法论推广到正式 review 层——首轮建立风险行基线；后续轮只复查受修复影响的行加相邻边界；出现基线外新发现才升级为全量重审。

- **配套缺口**：quota 耗尽后 agent 临场发明了 "main-session read-only fallback review"，并以它作为 T1/T2 的最终释放依据。记录得诚实，但这是未定义行为且独立性弱化是真实风险。**候选 H（中优先级）**：subagent-driven-development 定义降级规则——允许的 fallback 形式、必须的标注方式、是否需要后续补独立复核。

### 3.3 执行期 S 升级没有端到端 owner

S8/S9 暴露的流程缝隙：req-align 拥有 Spec Gate，impl-planning 拥有 P binding，dev-with-track 在执行现场——执行期由 review finding 触发的 spec 升级恰好落在三家交界处，结果是 gate 记录写了、binding 没登记、plan/ticket 引用没 reconcile。候选 A + B 能机械堵住后两个洞；更完整的做法是在 dev-with-track 的 findings 分流段（"规范性行为 → req-align 更新 spec revision"）补一句回程要求：req-align 完成升级返回后，执行方按 impact-scoped routing 完成下游引用 reconciliation 再继续。属于既有表面上的一句话补丁。

### 3.4 plan/design 的质量与篇幅分配

实例 plan 的重点篇幅分配是对的：Coverage And Change Map、执行数据流图、测试覆盖图、false-PASS 反例清单、性能边界都在承载真实判断，没有仪式性内容。两个瑕疵：

- **模板污染**：plan 尾部混入项目本地 plan-review 制度的残留（GSTACK REVIEW REPORT、工程评分、"Implementation Tasks" checkbox 列表）——最后一项直接违反契约"plan 不保存 task checklist"。impl-planning 的 Review Checklist 已有对应禁止条款，属执行瑕疵而非体系缺口；但它提示体系对"项目已有自己的 plan 模板/评审制度"如何融合没有说法。观察项，暂不提案。
- **findings.md 双重身份**：契约定义它是"逐项可分流的发现 inbox"，实例里它是一份 Design Gate 前的资料权威清单（表格化、长期 reference 性质，对人反而好读）。到 gate 时分流硬性前置将面对一份不匹配其定义的文档。**候选 I（低优先级）**：在既有分流规则里说清研究期"权威输入清单"类内容的归宿（按 section 视为已验证调查事实，gate 时只判断其中哪些是 durable delta 走 Stage 7），不新增 artifact。

### 3.5 路径与 ID 约定和项目现实冲突

契约规定 `docs/implementations/<package-id>/` 与 `YYMMDD-slug`；实例是 `docs/domains/finance-assistant/implementations/2026-07-16-datev-accounting-rules`。legacy 豁免救了 ID，但存储路径本身是体系硬编码的前提，与 rubric 待验证原则"不得把存储结构固化为体系前提"自相矛盾。**候选 J（低优先级）**：package root 改为"项目约定的 implementations root（默认 `docs/implementations/`）"；package-id 要求"不可变、日期前缀 slug"而不锁死 YYMMDD 格式。

## 候选优化清单（汇总，2026-07-17 随 R7 方向确认更新）

R7「结构化状态层」方向确认后，原 10 项候选的格局从并列变为"一个载体 + 剩余独立项"：A/C 被载体完全吸收，B/D 的执行面被吸收、各剩一句契约层澄清，其余保持独立。

### 载体：结构化状态层（R7 已确认，待实施）

| 原候选 | 吸收方式 | 剩余部分 |
| --- | --- | --- |
| A 升级 alias 与登记 binding 原子化 | `register-revision` 原子动作 + `validate` 挂 restore/ER/gate 三个时点 | 无 |
| C plan-contract-v1 校验脚本化 | `validate` 直接执行比较 | 无 |
| B plan 机械引用刷新 | `rebind` + `refresh-projections` | 契约仍需一句话定义 ER Revision set 语义（建议：写入时的 current revision set） |
| D hash 清单 SoT 化 | `record-artifact` / `supersede-artifact` 维护交付物清单 | 契约/dev-with-track 仍需一句行为约束：ER 只写 delta 与指针，不重复投影 hash 清单 |
| J package root 项目化 | 脚本以 package 目录为操作单元、路径参数化（测试即显式指定路径），天然不绑默认 root | 契约措辞同步放宽（root 交项目约定；ID 只要求不可变、日期前缀） |

新增配套项：**backfill gate 识别三态升级**（`collect_sources._read_gate_verdict()` 改为 JSON index → heading 解析 → 人工，三处文档描述同步），随载体实施。

### 独立候选（不受 R7 影响）

| # | 候选 | 维度 | 优先级 | 与 rubric 偏好关系 |
| --- | --- | --- | --- | --- |
| F | evidence-integrity 触发时要求列出每个 commit point 的信任输入及复验来源 | 质量 | 高 | 符合 R6"通用判断约束，不加新结构" |
| G | review basis 方法论推广到 module/safety 的 fixed-range review 循环 | 质量/效率 | 中高 | 延续 subagent rubric R1 方法论化偏好 |
| H | 定义独立 review 资源耗尽时的降级规则与标注要求 | 质量 | 中 | 方法论化；消除临场发明 |
| E | 鼓励对膨胀约束条目做零语义重组并走 editorial rebinding（执行面即 `rebind` 脚本） | 人读 | 低 | R5 的应用引导 |
| I | 分流规则明确研究期权威清单类内容的归宿 | 质量 | 低 | 不新增 artifact（R6） |

排序（2026-07-17 外部评审后确认）：F 作为载体完成后的第一个小改动（对应六轮机制级返工，收益/改动比最高）；G/H 等 task 级 review basis 在下一个实例验证后再决定推广与降级方式，不与载体同批；E/I 维持低优先级。

已在工作区、无需重复提案：subagent-driven-development 的 review basis / closure review / coverage gap 改动（覆盖 task 级反复 review 问题），建议落地后用下一个实例验证效果。

另：1.1 的三层重复表述收敛，随载体实施时的契约 procedure 段改写一并做（升级 alias、校验、投影等 prose 流程被脚本调用点替代，正是收敛时机），不再单独排期。

## 结构化状态层：设计方向评估（owner 提议并已确认采纳 = rubric R7，2026-07-17）

Owner 提议：把 canonical 的过程性状态从 Markdown 挪进专门的结构化文件（JSON 等），用轻量脚本做登记/更新/删除；Markdown 只保留人要看的叙述与索引投影。评估结论：**方向正确，且被本实例的失败模式直接验证；但边界必须收窄为"结构化状态与指针"，不能扩大到"规则与判断"。** Owner 已确认采纳该方向（记入 impl-package rubric 决策记录 R7）；确认时约定当轮只沉淀偏好，实施由后续 session 按本节与"采纳路径建议"执行。

### 实例证据：失守的全是状态簿记，守住的全是判断

本报告发现的四个机械性失败——S8/S9 binding 漏登记（1.2）、plan header 过期与 ER-35 的自圆其说（1.2）、plan-contract-v1 手工比较算法从未真正执行（1.2）、hash supersede 链靠 ER prose 重述（1.3）——全部属于"要求 agent 在 Markdown/prose 流程里手工维护结构化状态"。与此相对，判断性内容（fail-closed 语义、review verdict、验收边界、"task DONE ≠ package closed"）在 Markdown 里维护得很好。这说明失败的不是体系的语义设计，而是把机器状态的维护责任交给了 prose 纪律。prose 纪律的遵守率永远小于 1，脚本的遵守率是二值的：要么执行了要么没执行，而"没执行"可以被 validate 机械发现。

### 事实分层：什么进 JSON，什么留 Markdown

- **JSON（`.impl-package/` 下，机器 SoT）**：identity（package-id、attempt）、revision alias 与 blob binding、current selection、task/ticket runtime state、外部交付物清单（artifact/manifest/report hash 及 superseded 链）、gate entry 索引（G id、verdict、supersedes 指针）。全部是"值"，没有一句话是需要理解语义才能维护的。
- **Markdown（人与 agent 的判断层）**：design rationale、spec 合同语义、plan 策略与 Coverage Map、ER 的证据叙述与残余风险、gate entry 的 verdict reason 与 Durable Deltas、review findings。这些不进 JSON——否则违反 rubric R4"最小事实"红线，且会制造第二个语义 SoT。
- **投影（Markdown 中的结构化片段，由脚本刷新或校验）**：plan/dag/spec header 的 revision 声明行、DAG Runtime State 表、gate.md 顶部状态行、machine audit metadata HTML comment。人只读投影，agent 只改 JSON，投影由脚本回写——plan header 过期问题从此在机制上不可能发生。

### 脚本命令草图（单文件、零第三方依赖、以 package 目录为操作单元）

- `validate`：共享 checklist 的机械可判定子集——current 唯一且可解析、blob 匹配、plan-contract-v1 比较、ticket/DAG 的 P 引用一致、投影与 JSON 一致、gate G id 单调。作为 dev-with-track restore、ER 追加、gate entry 写入三个时点的前置调用。
- `register-revision <design|spec|plan> <alias>`：hash-object + 追加 binding + 更新 current + 复核，一个原子动作（候选 A 从 prose 纪律变成脚本行为）。
- `rebind <alias>`：editorial/机械 rebinding（候选 B 的执行面）。
- `refresh-projections`：从 JSON 回写各 Markdown header 与 Runtime State 表，并对 plan 做同 alias rebind。
- `set-state <task|ticket> <id> <state> --evidence <pointer>`：更新 runtime state 并刷新投影。
- `record-artifact` / `supersede-artifact`：维护外部交付物清单（候选 D 的 SoT 落点，ER 里只剩指针）。
- `new-gate-entry`：递增单调计数保留 G id、生成含 machine metadata 的 entry 脚手架（reservation，不写 verdict）。
- `finalize-gate-entry`：校验完整 entry、计算 entry-block hash、追加 immutable gate index（见 Schema gate 边界 4）。

候选 A、B、C、D 在这个方案下全部从"契约 prose 约束"降级为"脚本行为 + validate 检查"，契约 §2/§7 的 procedure 段可以大幅缩短为"schema 定义 + 调用时点"。

### 风险与守界

- **双 SoT 漂移**（JSON 新、投影旧或反之）：这是新引入的失败模式，必须由 `validate` 覆盖"投影一致性"检查来封住；规则定为"投影不一致 = validate 失败 = 不得追加 ER/gate"。
- **schema 膨胀**：最大的长期风险。守界清单（禁止入 JSON）：Acceptance Semantics、verdict reason、review findings、设计选择、任何需要读懂语义才能维护的字段。JSON 字段的准入测试：能否由脚本在不理解业务的情况下写入和校验。
- **脚本不可用时的 fallback**：schema 是契约，脚本是执行手段；允许手工编辑 JSON，但之后必须跑 `validate`（或手工执行其检查项并留证据）。避免"没有脚本就整个体系停摆"。
- **语义判断不进 v1 脚本**：readiness satisfiability、semantic cycle、impact-scoped routing 是判断，不是校验；v1 只做机械可判定子集，不要试图把路由规则写成代码。
- **分发与跨平台**：脚本随 skill 目录走（体系已声明 skill 目录是分发单位），零第三方依赖，Windows/POSIX 均可运行；workbench 已有同风格 Python 脚本先例。
- **数据策略与安全内核解耦（实施期 owner 补充，2026-07-17）**：状态 vocabulary、artifact discovery、字段及 gate heading grammar、marker 名称与投影格式收敛到 Impl-Package skill 内单一版本化 JSON 配置；backfill 直接复用 canonical resolver。append-only、CAS、active chain、package-local path、完整 gate entry span/content hash、HEAD/worktree 两相校验与 earned-artifact bijection 仍是不可配置安全内核，避免通过配置弱化证据完整性。CLI 不开放任意 `--config`，测试通过内部 seam 注入配置验证数据驱动行为。

### 对 backfill-stable-docs 的影响（调查于 2026-07-17，只列有影响项）

- **gate 终态机械识别链路（需同步改）**：`collect_sources.py` 的 `_read_gate_verdict()` 抓取 gate.md 顶部 `## <attempt-id>-G<n> · <verdict>` heading，识别失败进 `needsManualGateReview`；同一判定方式还写在 retirement runbook、audit-json-contract 的 gap-catching 前提、verify 报告字段三处。gate entry 索引进 `.impl-package/` JSON 后，识别升级为四类结果：JSON index 且 entry binding 核验通过 → heading 解析（无 JSON 的 legacy）→ JSON 与 Markdown mismatch（缺 entry、binding 不符或 JSON 陈旧）标 manual → 两者都无标 manual；"JSON 优先"不无条件成立，mismatch 不信任陈旧 JSON（见 Schema gate 边界 4）。backfill 侧改动面就是这一个函数加三处文档描述。
- **边界澄清**：`_pending.md`（项目级登记表，dedup key `<destination>|<delta-id>`）是同类"prose 纪律维护结构化状态"风险——Stage 7 漏登记正是 gap-catching 兜底存在的原因——但不在本次 package 内 scope，维持现状；它是该方向的天然下一站，schema 设计不要堵死 Stage 7 登记脚本化的路。
- 已查无影响：watermark（backfill 不消费）、revision-bindings（脚本零引用）、design/spec 存在性探测、retirement 目录删除与 `retired.json` provenance。

### Schema gate 六项边界（2026-07-17 外部评审吸收，实施前必须在 schema 与守界清单中定死）

外部（Codex）评审确认方向与 scope，提出六项边界；全部采纳，其中三项按体系既有原则校准：

1. **发布边界**：不宣称跨 Git/JSON/Markdown 原子；承诺为"单命令幂等 + 临时文件替换 + 失败后 validate 可发现并恢复"。校准：不新增存储的 published/unpublished 字段（那是新的可过期机器状态）；沿用契约既有两相事实——worktree 时 `hash-object` 写入 binding，验证状态由 validate 现场推导，不落盘。validate 必须区分两个上下文：pre-commit 校验 binding 与当前 worktree 内容一致（`register-revision` 刚写完时 HEAD 不匹配是正常态）；restore/ER/gate 等 committed 时点校验 binding 与 `HEAD:<path>` 一致。形式可以是 `validate --working-tree` / `--committed` 或按调用点隐含模式；合法的 pre-commit 状态不得被无上下文的 validate 误判为失败。
2. **写入安全与 stale-transition 防护**（不是并发控制）：v1 做原子文件替换（只防 torn write，不防 lost update）、重复调用幂等、`--expect` 前置条件（同时核对 current attempt 与 previous state，主要防 stale-agent 误写）。multi-writer concurrency 显式不在 v1 contract 内——执行模型本就是单写者（subagent 不拥有 runtime ledger），package-local lock 文件不进 v1。
3. **投影区域与 rebinding 权限**：投影使用 machine-owned markers；`refresh-projections` 只能改 allowlist 区域，marker 外存在 diff 时拒绝执行并报告——`refresh-projections → rebind` 不得成为把语义变化包装成 mechanical rebinding 的通道，marker 外变化一律路由回 P/S revision 判断。
4. **gate 索引可信度**：JSON 是带 entry pointer + content binding（entry 块 hash 或 anchor+blob）的索引，verdict reason 留在 Markdown entry；索引不可脱离 entry 独立改 verdict。reservation 与 finalized index 分开：`new-gate-entry` 只递增单调计数并生成 scaffold，崩溃可留 G id 空洞（空洞号不复用，与契约"取已有最大编号加一"兼容）；`finalize-gate-entry` 校验完整 entry、计算 entry-block hash 后追加 immutable index。finalize 前 JSON 不保存 verdict；Markdown 已有 verdict 而 index 未 finalize、缺对应 entry、binding 不匹配或 JSON 陈旧时，消费方（含 backfill）一律进 mismatch/manual，不信任陈旧 JSON——与"evidence 胜过 stale status"同构，未完成 scaffold 不能冒充有效 gate。
5. **按实体定义可变性**：revision binding、artifact supersede 链、gate index 为 append-only，修正走 supersede/tombstone，不提供物理删除；task/ticket current state 可更新。校准：JSON 内只留 current + 最后一次 transition 的 evidence pointer——理由不是"Git 提供完整历史"（Git 只保存已提交快照，commit 之间的多次 transition 不可见），而是体系不要求 runtime state 的逐 transition 审计：必要的执行判断与证据由 ER/gate 承载，JSON 不复制审计日志，也不为此要求每次 transition 单独 commit。
6. **迁移与兼容验收**：仓库内先建独立 fixtures，至少覆盖 legacy package 无新 JSON、旧 sidecar schema 升级、损坏/部分写入 JSON、projection drift、重复命令、错误 `--expect` 拒绝、并发写入（仅验证不产生半截 JSON，不宣称防 lost update）、路径含空格、Windows/POSIX 换行、backfill 的 JSON/heading/mismatch/manual 四类结果；DATEV 演练继续作为可选后续。

最关键三项：发布边界（1）、写入安全（2）、gate 索引可信度（4）。

### 采纳路径建议

1. 定 schema：扩展 `.impl-package/`（沿用 `revision-bindings.json` 的 schemaVersion 机制，新增 runtime-state 文件），先写 schema 与守界清单，后写脚本。
2. 脚本落地：开独立 worktree 修改 SKILL/脚本；测试时显式指定测试 SKILL 路径运行，不走默认路径，也不借用既有 package（如 `260716-codex-harness-pilots`，那属于另一任务）做试验场。
3. 契约与 stage skill 改写：procedure prose 替换为调用点（"升级 revision = 运行 register-revision"），这也是收敛 1.1 三层重复表述的合适时机。
4. DATEV 实例可作为迁移演练：现状 sidecar 缺 S8/S9 binding，正好用 `register-revision` 补登 + `validate` 收敛，验证工具对存量包的适配。

## 偏好过滤报备

按 improve-skill 纪律，以下类别候选已被已确认原则过滤，未列入清单：新增独立校验阶段或 preflight artifact、为 hash 生命周期新建 ledger 文件、新增 owner 审批点（均与"不为内部修正新增阶段、artifact 或审批步骤"冲突）。两个实例瑕疵判定为执行问题不值得体系改动：plan 尾部模板残留（契约已有禁止条款）、ER 时间戳乱序。三层平行表述（1.1）未单独立项——按候选清单的结论，随载体实施时的契约 procedure 段改写一并收敛。

## 新 session 实施指引

**本次 scope**：结构化状态层载体（schema + 脚本 + 契约/stage skill 的 procedure 段改写 + 投影机制）、吸收表中 B/D/J 的剩余契约措辞、backfill gate 识别四类结果升级、1.1 重复表述收敛。**不在本次 scope**：独立候选 F/G/H/E/I（排序已定且均不与载体同批：F 在载体完成后第一个做，G/H 等 task 级 review basis 实例验证后再定，E/I 低优先级）、`_pending.md` 脚本化（明确后置，schema 别堵死）、DATEV 实例迁移演练（可选，属另一仓库）。

**执行方式约束（owner 已定）**：开独立 worktree 改 SKILL；测试时显式指定测试 SKILL 路径运行，不走默认路径，不借用既有 package 做试验场。

**关键文件**（相对 agent-workbench 根）：

- 契约：`skills/impl-package/references/impl-package-composition-contract.md`（§2 revision-blob binding、§7 gate ledger 是主要改写对象）
- sidecar 模板：`skills/impl-package/assets/templates/revision-bindings.json`（有 schemaVersion 机制，扩展基点）
- stage skills：`skills/impl-package/{req-align,impl-planning,dev-with-track}/SKILL.md`（procedure prose → 脚本调用点）
- 偏好档案：`skills/impl-package/rubric.md`（R7 决策记录与守界原则；实施决策与其冲突时以 rubric 已确认原则为准）
- backfill 侧：`skills/backfill-stable-docs/scripts/collect_sources.py` 的 `_read_gate_verdict()`，及 `references/package-retirement-runbook.md`、`references/audit-json-contract.md`、`scripts/verify_stable_docs.py` 三处描述
- 实例参照（只读）：本报告头部的 DATEV package 路径，含现成的 capture gap 样本（sidecar 缺 S8/S9 binding、plan header 停在 S7）可用作 validate 的负向测试素材

**实施顺序**：按"采纳路径建议"四步；第 1 步 schema 与守界清单先行并请 owner 过目——schema 提案必须显式回答"Schema gate 六项边界"节的全部六项（重点是发布边界、写入安全、gate 索引可信度三项），再动脚本与契约。
