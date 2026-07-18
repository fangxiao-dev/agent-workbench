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

## 调度与返回

1. Working Branch owner 读取批准的 plan、关联 Ticket 和最小 Task DAG，只确认已知依赖、primary ownership 与禁改范围。
2. 使用 [`references/prompts.md`](references/prompts.md) 的 implementer 模板派发：目标、primary ownership、禁止越界范围、Known depends on、Contributes-to tickets、局部验证要求和 `BLOCKED` 返回格式是普通 Task 的完整默认输入。
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

每个 Ticket 进入最终验收前，只扫描 `contributes-to` 该 Ticket 的 `BLOCKED` Task：

- blocker 的未完成内容影响该 Ticket 的 AC、已声明行为或风险边界时，必须先解除阻塞，Ticket 不可验收通过；
- 不贡献且不影响该 Ticket 行为/风险边界的 blocker 不阻塞该 Ticket；
- 发现 Task 实际影响扩大到该 Ticket 时，先更新 contribution mapping，再按 blocker 规则处理，不能静默绕过。

Ticket 的 AC、evidence、正式 review 与 acceptance status 仍是唯一权威。正式 Ticket review 由 `dev-with-track` 的项目 review 路由执行；Task 局部验证或任何提前风险审查都不能替代它。

最终 package review 前，Working Branch owner 全局扫描未终结 Task：所有 Task 必须为 `DONE`，或有明确、已批准且带理由的 `WAIVED` / `SUPERSEDED`；不得遗留 `BLOCKED`。再以所有 Ticket AC 的实际 evidence 和整个 active Spec 覆盖判断 package，而不是以 Task 数量或 Task 状态代替验收。

## 条件化 progress

默认不创建 progress 文件。只有 Task 实际 `BLOCKED`、跨 session handoff、需要重试，或主 session 需要分发并行 subagent 时，才创建或更新 `docs/implementations/<package-id>/tasks/<task-id>-progress.md`。它只记录 blocker/原因、已做证据、下一可执行动作、影响 Ticket；不得复制 Ticket AC、维护第二套 Ticket 状态，或创建 attempt/ticket progress。

本 skill 不拥有 worktree、plan revision、runtime ledger、Git 或发布流程；这些由对应 owner 和 `dev-with-track` 管理。
