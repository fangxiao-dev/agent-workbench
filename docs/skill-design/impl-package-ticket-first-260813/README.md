# Impl-Package Ticket-first 重构

- 日期：2026-08-13
- 状态：证据复核完成，方向已定，未实施
- 性质：**本目录是后续优化的权威文档。**实施与再讨论以本页为准；原始设计文档降为背景材料
- 适用范围：Impl-Package 的 Composition、Ticket、执行调度、状态机、Execution Record、会话交接

## 本目录

| 文件 | 内容 |
| --- | --- |
| 本页 | 结论、归因、必做项、改动清单、验收指标 |
| [evidence/measurements.md](evidence/measurements.md) | 全部实测数字与口径 |
| [evidence/codex-session-analysis.md](evidence/codex-session-analysis.md) | Codex 对 5 个 rollout 的 Q1–Q8 分析与「与设计假设的对照」 |
| [evidence/mattpocock-philosophy.md](evidence/mattpocock-philosophy.md) | Matt Pocock 公开理念调研，逐条附出处，区分「他说过的」与「推断的」 |
| [scripts/](scripts/) | 复现全部测量的脚本 |

背景材料：[原始设计文档](../impl-package-ticket-first-execution-design-260813.md)（问题陈述与初版方案，其中三处归因由本页修正）。

相邻方案：`docs/skill-design/unified-subagent-worker-strategy-refactor-plan-260813.md`（worker 与调度合同，与本页不冲突，但「source unit」的定义需按本页的 Ticket-first 重新对齐）。

## 1. 结论与必做项

Ticket-first 方向成立。Matt Pocock 的 `to-tickets` 独立到达同一位置（纵切、边写在票上、work the frontier、无第二层执行对象），收敛证据可信。

原始设计文档有三处归因错位：把「Ticket 退化」归给 Ticket 定位、把「核心旅程晚」归给 plan 排序、把「后半段串行」归给静态 DAG。实测显示三者的真实位置是 Ticket×Task 稠密二部图、Ticket AC 的完整性要求、以及一条被自己废弃的边释放规则。

**必做三项，顺序不能换：**

1. **AC 分期**——每张 Ticket 有一条不依赖后续层的 core AC。唯一能让核心旅程早出现的改动。
2. **边的分级释放**——恢复「上游 seam 稳定即可提前派发下游实施」，并保留三型边而非退回二元硬依赖。后半段串行的解法。
3. **删 Task 层**——前两项在横切 Task 存在时会被重新覆盖。它是使前两项生效的条件，不是独立收益。

**工作量比预期小。**`tickets=true, dag=false` 不是要新造的配置：AccountingScope 包已用它跑完两个 attempt、gate `pass`、`tasks: {}` 全空。Ticket-first 的主体是**把这个已验证分支设为默认并删掉另外三种 Composition**，删除多于新建。

## 2. 证据摘要

完整数字见 [evidence/measurements.md](evidence/measurements.md)。

- DATEV 包终点：**Task 7/9 `DONE`，Ticket 0/5 `SATISFIED`**，44 小时内没有一次端到端证据。
- 读文档 : 实现动作 = **3.2–3.5 : 1**（两套独立分类法收敛）。
- **36–48% 的模型请求发生在 150k 上下文以上**；自动压缩在约 226k（87%）才触发。
- 产出量与占用峰值不相关：5 个 patch 达 213k，68 个 patch 达 234k。
- 完成包中 **ER 是最大单项产物**（16,575 tokens > spec.md 14,611）。

## 3. 三处归因错位

### 3.1 不是「Ticket 退化为末端 label」，是两个正交切法叠加

Ticket 本身是合格纵切。但 Task 按 ownership 横切之后，每条纵切被打散到整条横向链：

| Ticket | 贡献 Task | 最深 Task 链深 |
| --- | --- | ---: |
| DMI-01 确定性 source admission | T1, T2, T3, **T7** | 4 |
| DMI-02 版本化 gap form 与批准 | T1, T3, T4, T5 | 2 |
| DMI-03 verified canonical publication | T3, T5, T6 | 3 |
| DMI-04 安全 onboarding API/Web | T4, T6, T7, **T8** | 5 |
| DMI-05 完整旅程与回归 | T1–T9 | 6 |

编号最靠前的核心 Ticket 排在第三位才可能验收——Task 图把 Ticket 顺序倒了过来。

同一现象在 ER 上也可见：DATEV 的 25 条记录里 `subject: ticket:*` **一条都没有**（13 条 `attempt` + 12 条 `task:*`）。执行判断天然挂在正在做的那个单元上，而那个单元一直是 Task。

### 3.2 核心旅程晚不在 plan 排序，在 AC 写法

DMI-01 无阻塞依赖、是 Ticket #1，正是设计文档说「没有被提升为核心旅程」的那条。把它拖到链深 4 的是它自己的 AC-3：要求 opaque `uploadToken` 的 create→PUT→confirm producer/consumer 闭环与 real PostgreSQL RBAC zero-read proof——那是 T7 的 ownership。

它是**纵切，但不是最小纵切**：六条 AC 含 token 传播、privacy sentinel、CAS 竞态、hash 冻结、RBAC 证明。

所以在 `impl-planning` 加 core-first 五问修不好——核心旅程早就被识别成 Ticket #1 了，识别不是瓶颈，AC 的完整性要求才是。

### 3.3 后半段串行来自返工与一条被废弃的规则

DAG 前半段是真并行：T1/T2/T3 依赖全为 `none`，实测三路重叠。后半段串行有两个来源，都不是「静态 DAG 按设计生效」：

**其一，返工。**`dag.md` 记录 `P5 recovery 顺序固定为 T3→T4→T6→T7→T8→T9`——Spec S5→S6 改动 publication 语义后 affected-scope 重开，六个横切 Task 依序返工。若单元是纵切 Ticket，同一改动只失效 DMI-03。

**其二，边的释放规则被自己删掉了。**`docs/skill-design/impl-package-reusable-implementation-checkpoint-design-260728.md` 已标记废弃：

> 已由 Impl-Package contract 3.3 取代。当前 checkpoint 只保存恢复上下文，不授权提前派发。

该规则原本允许上游仍 `RUNNING` 时提前派发只依赖已提交 seam 的下游 implementation。删除后边只剩「上游整体 `DONE`」一种释放方式，即完整节点 barrier。

实测支持：T6→T7 的真实依赖只是 public projection / application seam，T6 的事务与私有表不是 T7 的输入。

## 4. 已验证有效、不得移除

| 机制 | 实测价值 |
| --- | --- |
| ready 集门禁 | S2 `readyTasks [T1,T2,T3]`、S3 `[T6]`、S4 `[T7]`、S5 `[T8]`，挡住过早启动 |
| 局部证据 ≠ 完成 | T6 有 9 files/64 tests 绿证据仍判 `INCOMPLETE`；T7 因缺 idempotency/read projection 被 `BLOCKED` |
| Ticket 轴独立 | 7/9 `DONE` 对应 0/5 `SATISFIED`，如实暴露「局部完成 ≠ 旅程验收」 |
| ER 跨 session 锚点 | S2→ER-003、S3→ER-011、S4→ER-015、S5→ER-019，四次续接均未越过阻塞 |
| **三型 Ticket 边** | 见 §5.2，AccountingScope 完成包提供直接证据 |

重构后这五项必须逐项确认仍然成立，不能默认继承。

## 5. 改动清单

### 5.0 排序依据

两个目标排出不同顺序，分开看才不会互相掩盖：

| 改动 | 解决「核心旅程看不见、后半段串行」 | 纸面与读取的直接节省 |
| --- | --- | --- |
| AC 分期 | 直接命中 | 几乎为零 |
| 边的分级释放 | 直接命中 | 间接（少一次 session 恢复） |
| 删 Task 层 | 保证前两项不被覆盖 | 小，但改动量最大 |
| 砍 Task Handoff | 无关 | 最大且可测 |
| 会话交接阈值 | 无关 | 避免在退化区工作 |
| ER 重构 | 无关 | 主要收益是把 ER 移出恢复路径 |

本节按第一个目标排序。删 Task 层排第三不是因为不重要，而是它的收益要靠前两项才兑现——AC 仍是整块生产合同时第一张票照样等整条链；边仍要求上游整体 `DONE` 时照样串行。

### 5.1 AC 分期

每张 Ticket 至少一条 **core AC**，其取证不依赖后续层；加固类 AC（并发、privacy sentinel、幂等、RBAC 证明、跨版本兼容）单独成组，允许后补。Ticket 仍需全部 AC 满足才 `SATISFIED`，但 core AC 的证据必须能在链深 1 取得。

对 DMI-01：core AC = 受支持 M1/M2 确定性生成 snapshot 并可读回；AC-3 的 uploadToken 公共传播与 zero-read proof 归入加固组。

不新增 Ticket 状态，只在 AC 列表内分组。

### 5.2 边的分级释放

恢复 `impl-package-reusable-implementation-checkpoint-design-260728.md` 的语义：上游 Ticket 仍在执行但下游依赖的 seam 已提交且有局部证据时，主 session 可提前派发下游 implementation，不改上游状态、不释放 acceptance/release、上游改合同则下游转 `NEEDS-REVALIDATION`。

当时废弃它的理由（checkpoint 不应授权派发）在新语义下依然成立：授权来自主 session 判断并记入 ER，不来自 checkpoint 本身。Ticket-first 下单元更少且纵向，这个判断比在 9 个横切 Task 之间做容易得多。

**同时：不要把边收敛为二元的「只保存硬依赖」。**AccountingScope 完成包给出直接反例：

| Ticket | Typed dependencies |
| --- | --- |
| ASP-01 | None |
| ASP-02 | `implementation: ASP-01` |
| ASP-03 | `implementation: ASP-01` · `acceptance: ASP-02` |
| ASP-04 | `implementation: ASP-03` · `acceptance: ASP-02` |
| ASP-05 | `implementation: ASP-01/03` · `acceptance: ASP-02/04` |
| ASP-06/07/08 | None |

**ASP-02 被引用三次，全部是 `acceptance` 型，无一次 `implementation` 型。**三张票的实施都不需要等 ASP-02 验收，只有它们自己的验收要等。二元收敛只有两条出路：变成完整 barrier（过度串行化三张票），或消失（丢掉验收约束）——两个都错。

判断题应从「这条边要不要」改为「这条边挡的是实施、验收、还是发布」。B2B 场景另需注意：共享同一张授权表或同一次迁移的两张票，frontier 上看似可并行、数据完整性上不可并行；这类应表达为真实边而非仅靠运行期发现。

### 5.3 Ticket-first：删 Task 层

前两项在当前结构下会被重新覆盖，这是删 Task 的真实理由：

- Ticket 的三型边只作用于 Ticket；Task 边一律二值。执行跑在 Task 层，纵切上的精细边被横切的粗边盖住。
- Ticket 由横切 Task 贡献（§3.1），任何一张票的验收都要等横向链走到足够深，AC 分期收益被吃掉。
- 合同变更沿层链扇出：一次 publication 语义变更导致六个 Task 返工；纵切只会失效一张票。

Ticket DAG 不是新文件——阻塞边已在 ticket 模板的「阻塞依赖 / Typed dependencies」字段里，那就是全部的图，`dag.md` 不再创建。

### 5.4 Task 承载物的吸收去向

| Task 承载的 | 去处 |
| --- | --- |
| execution boundary | Ticket 的「建设内容」，已有，重复 |
| contributes-to tickets | 删除（病根本身） |
| `READY` / `RUNNING` | 会话层 claim（见 §5.7），不进 Ticket 状态 |
| `DONE` evidence | 指向真实产物（测试报告、commit、DB diff），不指向流程文档 |
| section-level contract references | 派发 brief（运行时）。Task 的引用比 Ticket 更窄，这个「更窄」有价值但属于一次派发 |
| known seam / risk | 拆两半：属于合同的进 Ticket AC / spec；属于本次执行判断的进 ER judgment |
| **primary ownership（单写资源部分）** | **进 Plan，见下** |

ownership 有一半必须持久化。DATEV 的 DAG 里「单一 migration owner」「单一 authority-code owner」「独占 OpenAPI/generated client」「独占 real-PG runner」不是某次派发的局部决定，而是**跨单元的排他性约束**。两张票都要改 migration 时，先后必须有人裁决，让运行期 Agent 每次重新发现既贵又易漏。

分界线是**单写资源**：migration、生成产物、真实 DB runner、端口、共享测试数据。这个概念已存在于 `subagent-driven-development/references/parallel-work-admission.md`。

**建议：单写资源清单进 Plan，不进 Ticket，不做新对象。**Plan 本来就拥有执行策略，这些资源在 planning 时基本已知；运行期 Agent 读这张小表决定串并行。

### 5.5 随之而来：砍 Task Handoff

合同写明 handoff 是条件式产物，实测 7 个完成 Task 全部创建，且每个 Task 的 `DONE` evidence 指针就是它自己的 handoff——证据要求把条件产物静默升级成了必需产物。

Task 消失后大部分 handoff 自然消失。剩余场景把 evidence 指针改为指向真实产物。

注意与 §5.7 的区别：被砍的是**每 Task 的记账产物**，保留的是**跨 session 的续接产物**，两者目的不同，不可合并。

### 5.6 补 `to-tickets` 缺失的两条上游规则

本地 fork 相对上游 `mattpocock/skills` 缺失两条，且都正对本次问题：

**尺寸判据。**上游：`Each slice is sized to fit in a single fresh context window`。注意上游的可执行版本（总 token ÷ 150k = 票数）是**规划时估算**，实测不可靠（§2：产出量与占用峰值不相关），应改为运行时观测，见 §5.7。但「一张票应能在一个 fresh context 内从开始走到 core AC 证据」这条尺寸意图要保留。

**wide refactor 例外。**blast radius 横扫全仓的机械变更（改列名、给共享符号换类型、给既有表加租户维度）不能硬塞成纵切，走 expand–contract：先 expand，再按 blast radius 分批迁移（每批一票，blocked by expand），最后 contract（blocked by 全部批次）。B2B 的租户化改表与 schema 迁移属于此类；没有这条例外，「foundation 默认不 earn Ticket」要么被违反，要么被迫做成巨型 Ticket。

### 5.7 会话交接：观测而非预测

单元大于一个 session 无法在规划时预测（§2），但可以在运行时观测。触发形状应为：

```
警告线 = 智能区上限 − 收尾预算
```

- 智能区上限：frontier 约 150k；便宜档位更低（此项自动适配模型档位）
- 收尾预算 = 典型收尾请求数 × 每请求增量 ≈ 20 × 1,720 ≈ 34k

代入得约 **116k**（在 258k 窗口上约 45%）。

**不要用窗口百分比表达。**智能区不随窗口放大：60% 在 258k 窗口上是 155k（勉强），在 1M 窗口上是 600k（深度退化区）。规则会在换模型当天静默失效。

「不打断未完成任务」不是独立约束，而是 headroom 这一项的来源：正因为必须收尾完当前单元才能交接，警告线才要预留空间。实测 60% 的警告线只要收尾还需 10 次请求就已越过 150k；70% 更甚。

**配套：警告同时进入低消耗收尾模式。**p90 增量 4,379、p95 7,441——一次大文档读取或一个 worker 的大量回显就能吃掉三分之一 headroom。警告后不再读新的大文档、不再派新 worker、不开新探索，否则 p75 估算不成立，会在收尾途中撞上自动压缩。

现有 `skills/handoff-to-new-session/SKILL.md` 已具备所需能力：两阶段 anchor/continuation、clean local session、一次性理解审计，且**两个 prompt 合计约 900 汉字上限并禁止复述 plan/DAG/AC/历史**——「只指不抄」已是硬约束。需要处理的是其 Scope 明确排除 rolling handoff，与同 Ticket 内多次交接的用法冲突；应通过它已有的 downstream protocol extension 分支接入，而非放宽 Scope。

`skills/thread-harness/` 是早期大调度实验，**不作为本次权威**。可借用的只有三个概念，不含其 ledger/registry/seam 机器：controller 不写业务代码、只在轮边界交接、自交接是一等事件（主控提示、退休线自己建继任者）。

### 5.8 状态机与 Execution Record 重构

**现状澄清：**`state.json` 已经是唯一可写事实源，`progress.md` / ticket 内嵌 Runtime Acceptance / `dag.md` 内嵌 Runtime State 都是只读投影，三处都还在运行。`command_set_state` 没有转换表，只有五道守卫（词汇表、CAS `--expect`、非 `PENDING` 必须带 evidence、两条依赖守卫）。**不建议改成真正的转换表**——转换表会逼你穷举合法性，而实际约束只有「依赖释放了没」和「有没有证据」。

**投影收到一处。**`_refresh_projections` 每次重写全部 ticket 文档 + `dag.md` + `progress.md`，DATEV 为一次 `set-state` 写 7 个文件，`projection mismatch` 面同样是 7 个。

- `dag.md` 投影随 Task 消失
- **删掉 ticket 内嵌的 runtime-acceptance 段**：ticket 是合同文档应当稳定，把运行状态嵌进去意味着每次状态变化都在改合同文件，git diff 全是噪音；而这份信息 `progress.md` 里本来就有，且 `progress.md` 是恢复入口本来就要读

写放大降到 1:2。

**checkpoint 收进 `state.json`，ER 只留 judgment。**

```json
{
  "checkpoints": {
    "attempt":       {"next": "...", "evidence": "..."},
    "ticket:DMI-01": {"next": "...", "evidence": "..."}
  }
}
```

每 subject 一条、覆盖写，`Supersedes` 概念消失；`progress.md` 的 Active Checkpoints 直接从 `state.json` 渲染，恢复路径不再解析 ER。

**收益不是省体积**（checkpoint 仅占 ER 的 29%，波动 9%–52%），而是：恢复路径从三个文件降到两个、ER 增长与恢复成本脱钩、`_parse_execution_record` 撤出恢复路径。judgment 那部分（71%，约 15k）是包的真实记忆，不该砍。

被取代的历史 checkpoint 不再留在文件里，代价接近零：它们是「曾经的下一步」，一旦被取代既无恢复价值也无决策价值（决策价值全在 judgment），且 Git 保着历史；`impl-package-current-state.md` 本就声明这套不使用 seal、内容身份、receipt 或审计链。

**Ticket 没有「正在做」状态是有意的。**Task 的 `READY`/`RUNNING` 不要迁移到 Ticket——那会把 Ticket 从验收单元污染成执行单元。单 session 用 `resume.next` 表达；controller + 多 session 时用会话层 claim（Matt 的 claim = assignment 模型）。认领是调度事实，不是验收事实，两者改变的是不同的下一动作，不该挤进同一字段。

**`WAIVED` / `SUPERSEDED` 保留。**这两个包都没用到，但删除后 owner 决定不做某张票、或 patch attempt 取代旧票时需要在 gate 里写特例；保留成本是词汇表两个词。

**交接时应额外写 judgment。**同一张 Ticket 多次换 session 时每次覆盖同一条 checkpoint，中间过程不留痕。checkpoint 回答「下一步做什么」，judgment 回答「你需要知道什么」——交接场景下这不是一回事。

### 5.9 两个已知洞

**跨 package acceptance 边没有一等表示。**DATEV 五张票中三张有「外部验收前置」散文段落（ASP-07/ASP-08），票内自注「这不是本包运行状态中的本地 Ticket 依赖键」。真实存在的跨包验收依赖 `validate` 检查不到、`progress.md` 投影不出来。

**跨 attempt 的交付全貌不可见。**`state.json` 只保存当前 attempt 的 Ticket。AccountingScope 完成后其 state 只有 ASP-06/07/08，`progress.md` 只显示 3 张票，看不到 ASP-01~05。「这个包最终交付了什么」要去翻上一个 attempt 的 ER 或 git 历史。Ticket-first 之后 Ticket 是唯一单元，这个洞会更明显。

### 5.10 Spec 完整性 gate 的分期

`req-align` 要求「ready 状态只在 planning 不再需要发明行为或数据合同后成立」，`impl-planning` 的 admission backstop 会因任何未决 permission/concurrency/recovery/public shape 打回。DATEV 的 spec + contract-design 因此达到 33k tokens 且必须先于 planning 完整。

Spec 完整 → plan 按完整合同组织 → 第一条可见路径是完整生产闭包。建议允许核心纵切所需合同先行封闭、加固类合同以 delta 跟进。

此项独立于必做三项，可后续单独评估。

## 6. 做完之后会怎样

把同一个 DATEV 包按 §5.1–5.3 重放：

**包的形状。**5 张 Ticket（切法不变，原来切得对），无 Task、无 `dag.md`、无 `task-handoffs/`。阻塞边在各自 Ticket 的字段里。纸面从 76k 降到约 57k，去掉的全部是流程产物而非合同。

**第一个 session 的结局改变。**DMI-01 的 core AC 不依赖 API 层，链深 1 可取证。核心假设在第一个 session 成立或被证伪，而不是 44 小时后仍然未知。

**后半段不再是单通道。**DMI-02 的边是 `implementation: DMI-01`，DMI-01 的 parser 接口一旦提交并有局部证据即可开始。原 T6→T7→T8→T9 四级链在 Ticket 层只剩 DMI-03→DMI-04 一级，且该边可按 seam 提前释放。

**合同变更的爆炸半径收敛。**S5→S6 的 publication 语义变更只使 DMI-03 进入 `NEEDS-REVALIDATION`，DMI-01/02 已取得的证据保留。原为六个横切 Task 依序返工。

**主要风险。**单元从 14 个（9 Task + 5 Ticket）降到 5 个，单元变大。若不同时执行 §5.7 的交接机制，一张 Ticket 会跨多个 session，把节点 barrier 换成 context barrier。**§5.7 不是可选项，是 §5.3 的配套条件。**

## 7. 不从 Matt Pocock 取用的部分

| 他的主张 | 本项目的处置 |
| --- | --- |
| 第一枪必须含最小可 demo UI | 不适用。B2B 高风险工作停在权限、租户边界、账本、审计、后台 job。核心旅程横切「规则层 + 数据层 + 测试」即可，不为 demo 加皮。原设计已正确。 |
| 实现默认 AFK / `ready-for-agent` | 收紧。多租户隔离、授权、财务一致性、删除导出应默认 `ready-for-human`。 |
| 票上禁止路径与行号 | 只适用于**代码**路径。section-level **合同**引用服务于限定 context 载入量，是有意的优化而非 staleness 负债，保留。 |
| 缝越少越好、理想为一 | 不适用。租户、授权、审计是真实独立的缝。`progressive-system-evidence.md` 的处理优于扁平规则。 |
| tracker 是唯一状态源 | 他没有公开论证过这一点，且明确允许本地 markdown 与自建 tracker。他反对的是**第三套过程所有权**。`state.json` 不违背其理念。 |
| 人可以不读 spec | 失效。合规审查需要可追责的决策记录。 |
| 规划时按 token 估算切票数 | 失效。实测产出量与占用峰值不相关，估算不可靠；改为运行时观测（§5.7）。 |

可低成本借用的：wayfinder 的 HITL/AFK 单元分型（一个词写在 Ticket 上，告诉执行者能否无人值守）。另注：本地 `skills/ask-matt/SKILL.md` 仍路由到 `/wayfinder`，而该 skill 未安装，是条断链。

## 8. 验收指标

不以「删掉 Task 对象」为验收标准。

**行为判据（决定重构是否成功）**

1. 核心纵切的首份端到端证据出现在第一个执行 session，而非全程缺席。
2. 只改动某一纵切语义的合同变更，只使该 Ticket 进入 `NEEDS-REVALIDATION`，不沿层链扩散。
3. 后半段存在可并行或可提前释放的边，不再是单通道。
4. §4 五项机制逐项确认仍然成立。
5. ER 中出现 `subject: ticket:*` 记录。AccountingScope 无 Task 时该 subject 占 13/21，DATEV 有 Task 时为 0；若重构后 judgment 仍全部写在 `attempt` 上，说明 Ticket 没有真正成为执行单元，Ticket-first 只做了一半。

**成本判据（辅助，基线见 [evidence/measurements.md](evidence/measurements.md)）**

6. 读文档 : 实现动作从 3.2–3.5 : 1 下降。
7. 每 session 到首次真实 dispatch 的调用数低于 16–31 区间。
8. 150k 以上的请求占比从 36–48% 下降。
9. 任务包纸面低于 76k，且下降部分来自流程产物而非合同。

## 9. 影响面

| Surface | 变化 |
| --- | --- |
| `references/impl-package-composition-contract.md` | 四种 Composition 收敛为 Ticket-only / Plan-direct；Ticket 边保留三型 |
| `references/impl-package-current-state.md` | 删 Task 状态词汇与依赖守卫；`state.json` 增 `checkpoints`；投影收到 `progress.md` 一处 |
| `skills/to-tickets/` | 加 AC 分期、尺寸意图、wide refactor 例外；删 `dag=true` 分支 |
| `skills/impl-planning/` | 删 Composition 四选一；加单写资源表；不再调用 `create-task-dag` |
| `skills/create-task-dag/` | 退役 |
| `skills/dev-with-track/` | 以 Ticket 为恢复与推进单位；删 Task state / Task Handoff 主路径；加边的提前释放与交接触发 |
| `skills/handoff-to-new-session/` | 通过 downstream protocol extension 接入同 Ticket 内的滚动交接 |
| `scripts/impl_package_state.py` | 删 Task 轴；checkpoint 进 state；投影收敛；ER 撤出恢复路径 |
| templates / evals / tests | 删 Task/DAG 生成要求；新增 core AC、三型边、交接触发、单写资源场景 |

删除多于新建：`create-task-dag` 整体退役，Task 轴、`dag.md` 模板、Task Handoff 层、两处投影均为删除。
