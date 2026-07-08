# Slice 到 DAG

当来源是宽泛的 implementation plan、bulk 实现请求、spec、PRD 或 handoff，
而不是一个已切好尺寸的 vertical slice 时，读本文件。

来源尚未切片时，不要把整个来源画成一张 DAG。先提议用 `to-issues` 的
vertical slicing 流程，向用户说明这是一个切片步骤，等确认后再做。
`to-issues` 用 slicing-only 模式：起草切片、与用户 review 分解结果，在
tracker 发布前停下，除非用户明确要求发布 tracker 工作项。用户确认切片
分解或提供已切片来源后，再继续画 task DAG。

## 先切片

先有垂直交付 slice，再分配 worker。slice 不是一个层；它是一段可以独立
验收的窄的端到端行为。

每个 slice 记录：

```markdown
| Slice | What to build | Blocked by | User stories covered | Acceptance gate |
| --- | --- | --- | --- | --- |
```

好的 slice：

- 交付用户或运营方可见的结果，或一个必需的外部验证 gate；
- 包含足以验证的 数据/API/UI/测试 工作；
- 可以独立 review；
- 显式点名依赖。

不要把层当成 slice。"更新所有 source adapter" 通常是一个任务；"阈值从 UI
持久化到外部就绪检查" 才是一个 slice。

## 再画任务

在每个 slice 内部画可并行的任务：

- 数据/来源/就绪；
- read model 构建；
- UI 骨架；
- i18n/文案 review；
- seam 集成；
- 本地/浏览器/外部验证；
- 最终 whole-slice review。

共享 DTO 契约等任务可能服务多个 slice。把它们当作契约任务，在并行 worker
消费之前冻结其产出。

DAG 使用横向前置任务时要显式说明。横向任务完成不等于 vertical slice 被
验收。slice 的验收 gate 必须点名该 slice 可演示或可外部验证前所需的任务集
和 seam 工作。

## 与 Tracker 的关系

用户要求发布 tracker issue 时，用 `to-issues` 或项目自己的 tracker skill。
本 skill 可以提供 slice 和 DAG 内容，但不自行发布 tracker 工作项。

用户只要求更新 plan 时，把 slice 表和 DAG 写进指定载体。standalone 模式下
可以是 plan、handoff 或仓库特定的进度文档。存在 `dev-with-track`
workspace 时按 `SKILL.md` 的持久化映射落盘：稳定 slice scope 与执行策略进
`plan.md`，验收语义变化进 `spec.md`，实时任务契约、cohort、ownership、
seam 和状态进 `dag.md`。不要为此询问 tracker 审批。
