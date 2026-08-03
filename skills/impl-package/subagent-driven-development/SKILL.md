---
name: subagent-driven-development
description: 当已批准的 plan、ticket 或 DAG 含有边界明确、可委派的执行单元时使用；Working Branch owner 保留集成与 Ticket 最终判断责任。
---

# Subagent-Driven Development

本 skill 只调度横向 Task，不拥有 Ticket 验收、Spec/plan 的权威状态或 package gate。Task 是为 ownership、并行和依赖协调进行的执行拆分；Ticket 是纵向、独立可验收的功能/质量单元。一个 Task 可以贡献一个或多个 Ticket，一个 Ticket 也可由多个 Task 支撑；Task `DONE` 绝不等于 Ticket accepted。

Working Branch owner 是既有 branch/ticket owner，不是新增角色：其在 Task 返回、发生 `BLOCKED` 或 Ticket 最终验收前合并 Task 产出、处理实际 seam/冲突、运行共享验证与正式 review、把证据映射回 Ticket AC，并决定 Ticket 是否可验收。

## 何时派发

仅派发可以独立启动且不抢占其他 Task primary ownership 的工作。普通 Task 以模块、目录或明确共享 seam 划分，不要求预先列尽全部文件、消费者、失败模式或完整 contract。共享 migration、tenant/auth/permission、安全边界、公共 contract 或 rollback 边界的工作默认不拆；若可形成独立、纵向可验收结果，改拆为 Ticket，而不是人为制造复杂 Task。

单 owner、机械、局部可逆且委派成本高于收益的修改，由 Working Branch owner 直接完成，不创建额外 Task artifact。Task 可以是 feature、test、documentation、verification 或实际出现的 seaming 工作；它们没有额外类型系统。

## 集成性工作委派

Working Branch owner 对集成决策、边界、验收证据和最终状态负责；这表示 owner 对结果负责，不表示 owner 必须亲自编写跨模块、跨阶段或被称为 seaming 的代码。已经决策闭合且可隔离的集成性实现应优先派发，让 owner 保持在决策、验收和冲突处理位置。

当一项集成性工作同时满足下列条件时，优先作为普通 Task 派发给专门 worker：

1. **边界可声明**：输入、输出、不可改变的约束和完成判据可在派发前写清。
2. **写入可隔离**：可限定文件、资源和外部权限；不会与活跃 worker 的核心写入范围重叠，或冲突已被明确串行化。
3. **决策已闭合**：worker 不需要自行选择业务语义、mutation authority、兼容策略或风险取舍。
4. **结果可复核**：owner 能以测试、diff、运行记录或明确人工检查独立验收。
5. **失败可回收**：发现接口漂移、权限不足、验证矛盾或范围扩张时，worker 停止并交回 owner，而不是自行扩大任务。

任一条件不满足时，owner 先完成澄清、接口冻结、排序或风险决策，再重新评估是否派发。这里的“集成性工作”同样适用于测试补强、迁移适配、文档回填、跨 worktree 合并前验证和配置接入；不要因名称不同绕过这套判断。

## 调度与返回

1. Working Branch owner 读取批准的 plan、关联 Ticket 和最小 Task DAG，只确认已知依赖、primary ownership 与禁改范围。
2. 使用 [`references/prompts.md`](references/prompts.md) 的 implementer 模板派发：目标、primary ownership、禁止越界范围、Known depends on、Contributes-to tickets、局部验证要求和 `BLOCKED` 返回格式是普通 Task 的完整默认输入。对已决策闭合的集成性 Task，额外写清两侧冻结接口、允许修改的连接层、不得修改的核心实现及必须证明的正反向行为。
3. 可独立运行的 Task 可以并行；已知依赖必须先满足。不要为了证明所有潜在依赖而在派发前进行广泛调研。
4. worker 不扩大 primary ownership。发现共享 seam、未决 contract、越权动作或无法可靠继续时返回 `BLOCKED`，附最小 blocker 原因、建议动作和受影响 Ticket；seam 直接记录为 blocker，不新增实体或状态。

Task 只使用以下运行语义：

- `PENDING` / `RUNNING`：尚未或正在执行；
- `DONE`：横向产出与局部证据可交给 Working Branch owner 集成，不表示任何 Ticket 已验收；
- `BLOCKED`：暂时不能继续，必须记录一句原因及受影响 Ticket（如有）；
- `WAIVED` / `SUPERSEDED`：仅在 package 最终收口时由已有审批以理由和影响说明终结。

普通 Task 不因存在而要求完整合同、review basis、独立正式 review 或逐 Task gate。tenant isolation、auth/permission、migration、真实外部写入、金额、不可逆数据风险等高风险 diff，可按实际风险增加局部验证或提前风险审查；这仍是同一种 Task 的质量要求，不能替代或降低 Ticket 层正式 review/acceptance。

## 集成、Ticket 验收与收口

Task 返回后，Working Branch owner 检查实际产出与局部证据，并执行 integration step：

```text
合并 Task 产出
→ 处理已出现的 seam / 冲突
→ 运行共享验证和正式 review
→ 将证据映射回 Ticket AC
→ 决定 Ticket 是否可验收
```

Task worker 可以提供 primary ownership 内的局部、seam 或 checkpoint evidence；`DONE` 与局部绿色不能证明跨 Task 信息保真、authority 提交或完整业务动作。Working Branch owner 在 integration step 合并实际 checkpoint、确认其 authority/provenance，并选择必要的 shared/seam/assembled-action evidence。只有出现版本兼容、序列化/映射、authority 切换、跨 consumer 解释分歧或静默信息丢失时，owner 才对当前业务动作中共享受损表示或 authority fact 的语义相邻边界做有限 sweep；worker 派发前不需要穷举 consumer。遇到 contract ambiguity、超出 primary ownership 的 shared seam 或无法判定 authority 时，worker 返回 `BLOCKED`，不得自行定义共享语义。

每个 Ticket 进入最终验收前，只扫描 `contributes-to` 该 Ticket 的 `BLOCKED` Task：

- blocker 的未完成内容影响该 Ticket 的 AC、已声明行为或风险边界时，必须先解除阻塞，Ticket 不可验收通过；
- 不贡献且不影响该 Ticket 行为/风险边界的 blocker 不阻塞该 Ticket；
- 发现 Task 实际影响扩大到该 Ticket 时，先更新 contribution mapping，再按 blocker 规则处理，不能静默绕过。

Ticket 的 AC、evidence、正式 review 与 acceptance status 仍是唯一权威。正式 Ticket review 由 `dev-with-track` 的项目 review 路由执行；Task 局部验证或任何提前风险审查都不能替代它。

最终 package review 前，Working Branch owner 全局扫描未终结 Task：所有 Task 必须为 `DONE`，或有明确、已批准且带理由的 `WAIVED` / `SUPERSEDED`；不得遗留 `BLOCKED`。再以所有 Ticket AC 的实际 evidence 和整个 active Spec 覆盖判断 package，而不是以 Task 数量或 Task 状态代替验收。

## 条件化 Task handoff

默认不创建 Task handoff。只有 Task 实际 `BLOCKED`、跨 session handoff、需要重试，或主 session 需要分发并行 subagent 时，才创建或更新 `docs/implementations/<package-id>/tasks/<task-id>-handoff.md`。它只记录 blocker/原因、已做证据、下一可执行动作、影响 Ticket；不得复制 Ticket AC 或维护第二套 Ticket 状态。package 根 `progress.md` 由 state CLI 投影，公共判断与 checkpoint 由主 session 通过 `er-add` 写入 Attempt ER；subagent 默认不直接编辑 Ticket、progress 或 ER。

本 skill 不拥有 worktree、plan revision、runtime ledger、Git 或发布流程；这些由对应 owner 和 `dev-with-track` 管理。
