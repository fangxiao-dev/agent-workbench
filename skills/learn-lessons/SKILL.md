---
name: learn-lessons
description: 当需要从已完成工作、复盘、findings、进度、测试或当前代码中提炼可复用的实现、集成、验证、迁移、审查或排障经验时使用；发现非显然陷阱、症状、恢复路径或反向检索入口时自动触发，不从仅有设计材料制造经验。
---

# Learn Lessons：沉淀经验

独立运行 hands-on knowledge 回刷通道，与产品、架构和行为合同回刷分开。只保留能帮助未来 Agent 更快实现、验证、诊断、迁移或恢复的非显然经验。

## 合同

- 在任何路由前先读取目标仓库自己的指令和文档治理规则。不要假定仓库布局、owner 分类或 metadata schema。
- 用户明确要求沉淀经验、保留实践或复盘已完成工作，即授权在本通道范围内直接应用非破坏性文档修改。移动、重命名、删除、退休或其他破坏性操作必须先询问 Owner。
- 任务包状态、Gate 状态、manifest 是否存在以及 schema 版本都只是审计信号，不是前置条件。读取现有证据并继续；只有证据本身冲突或不足时才暂停。
- 稳定的产品意图、架构、词汇、模块行为和用户可见合同归 `backfill-stable-docs`；不要在 hands-on 文档中重复定义。
- 本通道不负责任务包生命周期、Gate 关闭、需求验收或退休。

## 先建立上下文

1. 读取仓库根目录的 `AGENTS.md` 或 `CLAUDE.md`，再沿其指针读取文档治理、canonical knowledge entry map、owner 路由和 metadata 规则。
2. 确定来源范围和 Source Revision。检查 working tree，避免把未提交改动误认为已验证的当前行为。
3. 找到能够确认或否定候选的当前代码、测试和 canonical 文档。历史会话、任务包、审查和日志只用于发现候选，不作为当前指导。

当仓库指令来源、文档目的地、来源范围和当前证据位置均已明确，或已明确报告其不可用时，这一步才算完成。

## 发现候选

按以下顺序读取来源；前三类最容易暴露真实摩擦：

1. findings、reviews、audits 和 investigations：非显然陷阱、错误假设、安全边界和反复失败；
2. progress notes、implementation records、repair 和 recovery notes：偏离、错误尝试以及真正恢复进度的动作；
3. verification reports、tests、browser/debug evidence 和 failure drills：可复用检查、失败分支和停止条件；
4. current code 和 tests：确认候选今天仍成立，并删除历史 workaround 或未实现承诺的影响。

Decision、Design、PRD、Spec 和 Architecture 材料只用于确认 owner、稳定合同是否已吸收以及边界。只有设计材料、没有 findings、progress、verification 或当前实现证据时，标记为 `source-insufficient`；不要据此创建 hands-on lesson。

## 拆分并执行耐久性门槛

按未来检索问题、维护 owner、source of truth 和行动形态拆分材料。即使实现指导和症状/根因/恢复指导来自同一事件，也要分开。

只有同时满足以下条件才保留候选：

- 非显然，且可能节省未来调查、返工或失败验证；
- 有当前代码、测试或 canonical owner 文档支持。

按以下规则路由：

- implementation、integration、migration、verification、reuse 和 implementation-reference lessons：读取 [`impl-knowledge-maintainer`](../impl-knowledge-maintainer/SKILL.md)；
- symptoms、diagnosis、root causes、known failures、recovery、runbooks 和 debug entry paths：读取 [`debug-knowledge-maintainer`](../debug-knowledge-maintainer/SKILL.md)；
- 混合材料：同时使用两个 maintainer，并将实现 lesson 与 debug lesson 分开；
- 稳定的 product/system/module/context 语句、behavior contract 或 canonical vocabulary：交给 `backfill-stable-docs`，不写入 hands-on 文档；
- requirements、future design、temporary plans 和 mandatory repository rules：使用仓库指定的 requirement、design、planning 或 agent-rule 归档位置。

忽略一次性日志、普通状态、显而易见的代码结构、未完成计划以及已由 canonical contract 完整覆盖的事实，除非来源额外暴露了陷阱或恢复路径。

## 整理并验证

1. 创建文档前先搜索最窄的现有 hands-on 文档及其 entry map。未来检索问题和 owner 相同，就更新已有归档位置。
2. 按反向检索写作：开头写触发条件或症状、错误假设、根因、推荐动作和停止条件。不要写任务或事件时间线。
3. `source_of_truth` 只指向当前代码、测试或 canonical owner 文档。历史 provenance 留在报告中，不要把任务包或会话变成长期 current reference。
4. 遵守仓库已有的 metadata 和语言约定。不要为本通道发明新的 manifest、sidecar、registry 或 schema。
5. 只有出现新的重要搜索主题、owner 路由或失效检索路径时才更新 hands-on entry map；单纯新增一篇文档不够。
6. 检查链接、metadata、当前证据和最终 diff。候选与 canonical facts 冲突、证据不足或会扩大范围时，停止并交给 Owner 决策。

当每个候选都已分类、每个已应用 lesson 都有维护中的目的地和当前 source of truth、每个稳定合同候选都已离开 hands-on 路由，并且所有未解决冲突或证据缺口都已列出时，工作才算完成。

## 历史来源兼容

标准任务包使用其已有 inventory 和 reports。任务包缺少 Gate、使用旧 schema、缺少 manifest 或处于 active/non-terminal 状态时，切换到人工证据审计：

- 直接读取用户指定的 findings、progress、verification、code、tests 和 canonical docs；
- 继续使用相同的耐久性与路由规则分类候选；
- 把任务包状态作为上下文报告，不作为阻塞结论；
- 不要为了运行本通道而升级任务包、伪造 Gate 或增加任务包 bookkeeping。

只有真实事实冲突或证据缺失会阻塞应用 lesson。缺少 Gate 或需要 schema upgrade 本身不是 blocker。

## 汇报

无论单个来源还是批量来源，先报告数量：候选总数、已应用、已有覆盖、no-delta/ignored、source-insufficient 和待 Owner 决策。然后说明：

- 更新或创建了哪些 implementation、integration、migration 和 verification 文档；
- 更新或创建了哪些 debug/runbook 文档；
- 哪些稳定语义已交给 `backfill-stable-docs`；
- 哪些一次性、过期、未完成或 design-only 材料被拒绝及原因；
- entry map 是否改变以及原因；
- 哪些当前 code/test 证据缺失，或存在 canonical 冲突。

不要把审计完成、候选提炼、文档应用或任务包退休混称为同一个状态。
