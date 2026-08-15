# Plain Language 判断实例

这些实例是 Plain Language Core 的首次加载材料，用于判断自创术语、中文硬译、中英混搭、标题和文件名。当前上下文第一次加载 skill 时阅读，已经加载过时直接复用；遇到新短语时，比较它和实例中“为什么清楚/为什么含糊”的相似性，不把本文件当作固定词表。

## 可以保留的实例

这些短语在当前校准中被认为足够清楚，或具有稳定技术含义：

- `manifest`：常见的清单/描述文件概念。
- `Contract Coherence`：表示合同之间的一致性检查，语义可直接理解。
- `lifecycle authority`：表示生命周期规则的权威来源，项目语境清楚。
- `Execution Readiness`：表示实施前置条件是否满足。
- `POC schema cutover`：表示 POC 阶段的数据结构切换。
- `Whole-Slice Review`：项目已明确用来表示完整功能链路审查。
- `Real Route Safety`：项目已明确用来表示真实业务路由安全检查。
- `Cutover-Only Guard Scripts`：表示仅在切换阶段使用的保护脚本。
- `Stable Docs Backfill`：如果它是 skill 名称，应作为正式名称保留。

这些实例说明：多词、标题式大小写或包含抽象名词，并不自动等于问题。

## 高疑似实例

这些短语在当前校准中被认为有明显的临时拼接或伪标准感：

- `reference adoption`：把复用或接入验证写成一个未经定义的架构名。
- `Business Event Runtime`：没有说明究竟是记录、持久化、投递、查询还是追踪能力。
- `runtime evidence seam`：`runtime`、`evidence`、`seam` 连续堆叠，无法直接判断边界。
- `Readiness Satisfiability`：把“前置条件是否满足”包装成形式化阶段名。
- `authority cleanup`：没有说明清理的是规则来源、数据来源还是写入责任。
- `Gate Ledger`：不清楚是验收清单、门禁状态还是审计记录。
- `Task Ledger Index`：`ledger` 没有比“任务清单索引”增加明确含义。
- `Integration Seams`：用隐喻代替具体的集成边界或衔接点。
- `Open Seams`：没有说明哪些集成边界尚未解决。
- `Catalog Reset-Then-Copy Dry Run`：把操作顺序硬拼成阶段名称。
- `Gate Synthesis And Execution Checklist`：`synthesis` 没有比“门禁汇总”提供更多信息。
- `SSOT Ops Consolidation And Cleanup`：`Ops`、`consolidation`、`cleanup` 叠加，读者难以判断具体动作。

这些实例说明：问题不是某个单词绝对不能用，而是组合后制造了“大家都知道这个架构名”的错觉，却没有让读者知道实际对象和动作。

## 只部分怀疑的实例

- `Existing Plan / Spec Adoption`：`Plan / Spec` 正常；当前问题集中在 `adoption`。优先考虑“复用现有计划/规格”。
- `Production Runtime Residue Clear Plan`：`Production` 和 `Plan` 本身正常；需要单独判断 `Runtime Residue Clear` 是否能明确表达“生产环境运行残留清理”。
- `Typed Domain Event`：工程师通常能理解，但它不是必须大写的统一业界术语；根据语境优先写“具有固定名称和字段的领域事件”。

## 保留专业 token、改成中文主体的实例

- `session exchange`：`session` 可以保留，但 `exchange` 容易让人误解成 OAuth token exchange。若实际动作是解析登录会话并重验身份，写“从 session 解析并重验当前身份”。
- `environment identity`：`identity` 可以保留，但必须说明它标识什么。若实际含义是部署连接的测试资源，写“环境 identity 与 Supabase、对象存储、Worker 等实际资源绑定”。
- `Actor Context`：若项目已经用它表示服务端验证后的当前调用者身份与权限，可以保留名称；首次出现用中文说明其对象和可信来源，不机械翻译成新专名。

这些实例属于“保留并说明”，不是“直接替换”。判断关键是 token 是否准确、稳定，以及中文句子能否说清动作和边界。

## 涉及合同决策的实例

- `四个参考接入必须在同一 snapshot 验证`：`snapshot` 的表达可能含糊，但删除“同一”会改变验收条件和集成方式。先把它标成合同决策，向 Owner 说明它把四项证据绑在同一 commit、迁移和环境；只有 Owner 否决该条件后，才能改写成各项独立固定版本和证据。
- `single writer`：它可能是清楚的并发约束，也可能被误用为所有工作必须串行。先确认它限制的是数据面写入者、迁移发布者还是开发分支，再判断是否只是语言问题。

合同决策项可以出现在说人话报告中，但不能以“建议替换”的方式替 Owner 改变行为合同。

## 中文直译词与文件名实例

- `参考接入`：即使已经翻成中文，仍可能是 `reference adoption` 的直译，读者无法判断它是示例、测试还是真实迁移。可按实际用途写“最小业务接入验证”。
- `reference-adoption-design-input.md`：如果正文已经决定弃用该术语，文件名也应列为候选；获得重命名授权后同步更新链接和旧路径引用。

## 概念边界实例

- `Domain Event`：领域中已经发生、且业务关心的事实，例如 `OrderSubmitted`。
- `Typed Domain Event`：可以作为解释性工程用语，但不要把它写成公认标准名称。
- `Business Event`：项目可以自行定义，但要说明它是业务事实、流程事件、审计记录还是可观测性记录。
- `Business Event Runtime`：不要直接保留为架构名，拆开写明业务事件的记录、持久化、投递、查询和追踪能力。
- `Audit Record`：不要因为都记录动作就和 `Business Event` 合并；审计记录要表达谁、以什么权限、做了什么，以及所需的合规证明。

## 如何从实例迁移到新短语

看到新短语时，先问三个问题：

1. 它具体指什么对象？
2. 它描述什么动作、责任或结果？
3. 如果删掉这个大写短语，读者能否用普通语言复述原意？

如果三个问题不能回答，且短语同时有名词堆叠或伪专名感，就列为候选；如果问题能回答，就保留或只要求补充定义，不要机械替换。
