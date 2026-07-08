---
name: create-task-dag
description: >
  当 vertical slice、implementation plan、spec、PRD、handoff 或 tracked
  implementation 需要变成支持并行执行的 task DAG 时使用。触发场景：分解
  slice、画/建 task DAG、分配 ownership、冻结契约、调度 worker、集成 seam、
  或执行最终 whole-slice review。
---

# Create Task DAG

把一个 vertical slice 或已切片的来源变成可派发的 worker cohort：明确的
ownership、稳定的契约、集成 seam 和最终的 slice 级 review。

来源是宽泛的 implementation plan、bulk 实现请求、spec、PRD 等未切片材料时，
不要闷头画一张超大 DAG。先提议用 `to-issues` 的 vertical slicing 流程，并在
执行切片前征得用户确认。`to-issues` 用 slicing-only 模式：切片草案经用户
确认即止，除非用户明确要求，不进入 tracker 发布步骤。用户确认切片或提供
已切片来源后，再在每个 slice 内部或跨 slice 的共享契约工作上画 task DAG。
并行发生在交付边界内部，不以丢失 vertical 验收 gate 为代价。DAG 含横向
前置任务时，写明哪些 slice gate 消费它们。

## 持久化映射

持久化可选。本 skill 可独立使用：把 DAG 产物输出到对话内、当前 plan、
handoff、tracker 笔记或用户指定的进度文档；不要求先有 tracking workspace。

存在 `dev-with-track` implementation workspace 时，优先落入它的文件角色。
本节是唯一的映射来源：

- 功能合同或验收语义的变化 -> `spec.md`。DAG 工作暴露出合同变化时，先补
  spec 或标记 blocker，不要只改 plan。
- 稳定 scope 与执行策略的变化 -> `plan.md`。
- 任务契约、cohort、ownership、状态、seam、验证 gate -> `dag.md`；patch
  模式下旧 `dag.md` 已标记 `Retired / gate passed` 时，写入当前的
  `YYYYMMDD-HHMM-<patch-topic>.patch-dag.md`。
- 持久的任务局部状态 -> `tasks/Tn-progress.md`。
- 任务交接 -> `tasks/Tn-handoff.md`。
- 跨任务风险与后续项 -> `findings.md`。
- 最终 review 与关闭决策 -> `gate.md`。

## 运行原则

- **Slice**：垂直交付单元，带用户可见行为、验收标准、完整测试矩阵、浏览器
  证据，必要时含外部 smoke。
- **Task DAG**：解锁并行 worker 的内部依赖图。
- **Main session**：调度者、契约 owner、seam owner、集成验证者、外部
  把关者。
- **Worker**：单任务或窄 cohort 的有界实现者。
- **Final reviewer**：任务产出集成后的 whole-slice reviewer。

不要因为存在共享文件就串行化实现。给共享文件明确 ownership，让 worker
上报 seam 需求，而不是越界编辑。

用 **ownership lanes** 代替扁平的文件清单。每个 worker prompt 和 DAG 任务
都区分 primary owned（正常写入范围）、conditional seam（仅在点名条件下可
改）、forbidden（禁改）三类文件。这让 plan ownership 与 worker prompt 保持
一致，也让有意的 seam 编辑可审查，而不是变成意外的 scope creep。

**Seam status** 用词精确：并行任务之间计划内的依赖是 `NEEDS_SEAM`，不是
`BLOCKED`。`BLOCKED` 只留给缺上下文、缺权限、数据不可用、计划错误或需要
人类决策的情况。

## 工作流

### 1. 立足 Slice

读活跃的 slice、implementation plan、spec、handoff、仓库指令和相关验证
文档。plan 和 spec 通常由 `feature-impl-planning` 产出在
`docs/implementations/<slug>/`。来源宽泛未切片时，用
`references/slice-to-dag.md`，并在以 slicing-only 模式调用 `to-issues` 前
征得用户确认。识别：

- 最终行为与验收标准；
- 当前分支与脏状态；
- 外部 mutation 权限与红线；
- 可能的共享 seam 文件；
- 需要的本地、浏览器和外部验证。

完成标准：main session 能说出 vertical slices、必须交付什么、不能碰什么、
哪些决策仍真正属于 owner。

### 2. 冻结共享契约

派发 worker 前，冻结它们独立工作所需的契约：

- DTO / 类型 / API 字段；
- fallback 与兼容规则；
- route / page prop 命名；
- i18n namespace / key 约定；
- worker 所属数据支撑的 UI 状态；
- 外部 smoke 的 marker 与清理协议。

完成标准：worker 不用发明形状、不用碰非属地文件，就能消费或产出其契约。

### 3. 画 DAG 与 Ownership Map

用 `references/dag-and-ownership.md`：任务记录、ownership 模式、cohort
规则和任务编号续编。

把 DAG 记录进用户要求的载体；存在 `dev-with-track` workspace 时按上方
持久化映射落盘。

完成标准：每个任务都有依赖、可并行邻居、ownership lanes、聚焦测试和完成
标准；每个 vertical slice 点名验收前必须完成的任务和 seam。

### 4. 派发并行 Worker Cohort

用 `references/worker-prompts.md` 生成 worker prompt 和处理返回状态。

同一 cohort 中契约已稳定、primary 写入集不重叠的任务一起派发。worker
prompt 从 DAG ownership lanes 生成；不要手写比 DAG 更窄或更宽的 ownership
清单。共享 seam 文件留给 main session 或一个明确点名的 seam worker。

完成标准：每个 worker 拿到有界 prompt，不可能把自己的任务误当成整个
slice。

### 5. 集成 Seam

main session 处理跨任务 seam：

- route / page 接线；
- 共享类型导出；
- 词典合并；
- prop 形状不匹配；
- 测试矩阵缺口；
- worker 产出之间的冲突。

完成标准：集成后的 worktree 是一个连贯的 vertical slice，不是相邻的任务
孤岛。

### 6. Review 并验证整个 Slice

用 `references/review-and-verification.md`：任务 review、最终 review 和
验证 gate。

任务级 review 不够。集成后，针对原始 slice/来源和完整 diff 派发或执行
whole-slice review。

完成标准：本地集成测试、必要的浏览器检查、外部 smoke gate 和最终 review
状态都被诚实记录。

## 输出契约

用于规划或执行准备时，输出或记录：

```markdown
## Task DAG
| Task | Depends on | Can run with | Primary owned | Conditional seam | Forbidden | Gate |
| --- | --- | --- | --- | --- | --- | --- |

## Shared Contracts
- ...

## Parallel Cohorts
- Cohort 1:
- Cohort 2:
- Final:

## Integration Seams
- ...

## Verification Gates
- ...
```

用于执行期时，最终汇报必须包含：

- 派发的 worker cohort；
- main session 处理的 seam；
- 实际运行的测试和浏览器/外部检查；
- 最终 whole-slice review 结果；
- 剩余风险或被阻塞的 gate。
