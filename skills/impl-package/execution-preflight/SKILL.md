---
name: execution-preflight
description: 当准备从 handoff、plan、review、audit、Issue 或 execution artifact 开始任务时使用；在执行前一次性收齐 permission、owner authorization、HITL decision 与 subagent mode，并默认采用主 session 调度、subagent 充分执行的协作模式。
---

# Execution Preflight

在基于既有执行材料开工前，建立一次有边界的 execution authorization bundle。它只负责授权与协作合同，不做 readiness 分析、实现排序、代码侦察、测试、编辑或 subagent 派发。

## 核心合同

- 沿当前批准范围检查完整生命周期：实现、验证、证据、清理、外部工具以及计划内 Git/Issue 收口；不要只申请下一步权限。
- 将结果分为 `已授权`、`本次请求授权`、`明确禁止/不适用`。每项说明对象、环境、数据边界和最大副作用，使 owner 能以“全部批准 + 例外”一次作答。
- host 允许且 owner 未禁止时，默认推荐“调度优先”：主 session 负责授权、调度、决策、实际 seam、共享验证、验收和最终责任；subagent 充分承担可隔离、可复核的执行切片。
- 一次性授权只属于当前任务。它可按明确 Task 边界传递给 subagent，但不扩展到新系统、更高环境、真实数据或 materially broader/destructive scope。

## Workflow

### 1. 判断是否需要 Preflight

以下情况运行：请求从 handoff/plan/review/audit/Issue/execution artifact 开工，或涉及 delegation、外部环境、migration、cleanup、Git 发布、真实集成或 owner decision。

小型只读回答、简单本地命令，或授权已精确覆盖且来源没有额外权限边界的局部可逆修改可跳过；记录一句具体理由后继续。

完成标准：已明确跳过理由，或已识别需要读取的授权来源。

### 2. 提取完整授权边界

先收集当前 session 对本任务已经明确允许或禁止的事项，再读来源中的 permission/HITL、执行、验证、清理、发布和外部依赖部分。若 preflight 需要继续，在输出授权包前完整读取 [authorization-contract.md](references/authorization-contract.md)，按其中的生命周期扫描表检查遗漏。

若当前 plan earns Tickets/DAG，同时验证同一 Attempt/P revision 的完整 earned artifact set 已联合批准；缺失、错版或只批准部分 bundle 都阻止开工。不要从一般代码库知识推测来源未提及的外部系统。

完成标准：每项 source-stated/current-session authorization 与 HITL 事实只记录一次，没有遗漏可预见的 permission stop，也没有引入相邻系统。

### 3. 一次询问全部缺口

使用 reference 中的授权包模板，一次列出所有缺失权限；不要按执行顺序连续提问。已经回答的类别只重述，不再申请。计划明确禁止的事项只记录边界，除非 owner 主动要求跨越，否则不要求其反向确认。

用户说“充分使用”“尽量派发”“subagent 干活”或同义表达时，直接采用调度优先模式；否则按 reference 中三个模式让 owner 选择，并把推荐模式放在第一位。

完成标准：owner 可以用“全部批准”加可选例外，给出覆盖当前任务完整可预见生命周期的有界授权。

### 4. 记录并继续

用 reference 中的执行授权模板记录：subagent mode、完整 allowed scope、仍被禁止的边界及 HITL 结论。调度优先时还要记录主 session 保留职责、subagent 可执行范围、授权传递方式和必须串行化的共享资源。

授权只在当前任务内有效。记录完成后直接进入既定执行入口，不为已授权的验证、清理、同边界命令或执行者从主 session 变为明确派发的 subagent 再次询问。

完成标准：后续 session/agent 能从记录唯一判断某个操作是否在授权包内。

### 5. 执行期边界

只有操作引入未提及的外部系统、更高环境、真实/敏感数据、显著扩大或更具破坏性的范围、新财务/法律副作用，或真正 owner decision 时，才再次请求授权。预检遗漏计划中已可见的权限属于 preflight defect；若无法避免修正，应把全部剩余缺口一次补齐。

最终只报告实际影响完成度的授权缺口。面向 owner 汇报 readiness/status 时使用 `talk-to-boss`。

完成标准：执行在授权包内连续推进，或以唯一、精确的新权限/决策 blocker 停止。
