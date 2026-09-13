---
name: knowledge-manager
description: 一键吸收已完成工作的实现经验、长期稳定语义和 Agent 环境改进；仅在用户显式调用时运行。
disable-model-invocation: true
---

# Knowledge Manager

这是完整知识吸收的一键入口，只响应用户显式调用 `$knowledge-manager`。它统一一次来源快照，协调两个知识 lane，并在主线程执行一个内部 environment scan：

- `$learn-lessons`：实现、集成、验证、迁移和排障的 hands-on knowledge；
- `/impl-package:backfill-stable-docs`：产品、架构、模块行为和词汇等 stable semantics；
- environment lane：从当前 session 发现可由环境消除的重复摩擦。它不是独立 Skill、命令或 alias。

## Source Snapshot

1. 从用户明确提供的来源或当前对话确定已完成工作范围，读取仓库指令和文档治理。
2. 只建立一次 `Source Snapshot`：仓库根、worktree、branch、Source HEAD、dirty 状态、来源数量和可读的来源引用。两个 worker 与主线程共享这份快照，不各自重猜范围。
3. 环境 lane 按此顺序读取 session：当前会话上下文；宿主原生 conversation/thread reference；用户提供的 transcript、file 或 link。不能读取时将该 lane 标为 `source-insufficient`，继续可运行的知识 lane。
4. 复用宿主现有引用方式；不创建自定义 session ID、manifest、registry、sidecar、索引或新 schema。

## Three lanes

1. 先读取 [`learn-lessons`](../learn-lessons/SKILL.md)、[`backfill-stable-docs`](../../plugin-marketplace/plugins/impl-package/skills/backfill-stable-docs/SKILL.md) 和 [`dispatcher`](../dispatcher/SKILL.md) 的当前合同。分类、证据、目标、metadata 及 stable-doc 阶段规则仍由 peer Skill 拥有。
2. 对有相应来源的知识 lane，通过 `$dispatcher` 派出只读审计；没有相应来源就跳过并报告 `skipped`。brief 必须带同一 Source Snapshot、lane 范围、`audit-only` 边界、返回格式和验证要求，不把 Manager 的 apply 授权传给 worker。worker 不得写任何文件；宿主没有 subagent 能力时，由主线程顺序完成相同的只读审计。
3. 主线程消费并核对返回：当前代码、测试和 canonical docs 是事实证据；缺少证据、来源不够或事实冲突的条目不得当作已确认知识。环境 lane 始终由主线程扫描以下七类：Navigation、Automated checks、Coding standards、Instruction placement、Tool economy、No-ops、Information access。
4. 以 primary intervention 去重：稳定行为合同只进入 stable docs；非显然的实现陷阱、恢复路径或验证经验只进入 hands-on；可重复且可机械消除的摩擦进入 environment recommendation。只有同一事件确实需要两种不同干预时才拆分；不要把 stable contract 复制到 hands-on。
5. 主线程是唯一写者。普通调用允许按 peer Skill 合同对 hands-on 与 stable docs 做最小的非破坏性更新，并完成相应 verify；environment 只生成报告，不修改代码、CI、工具、权限、instructions 或其他环境。`audit-only` 调用使三个 lane 全部只读，知识候选记为 `pending`。

## Candidate gates and boundaries

- 经验候选须通过 [`learn-lessons`](../learn-lessons/SKILL.md) 的耐久性门槛；stable candidate 须通过 stable-docs 的事实校准、disposition 和冲突规则。
- Environment recommendation 必须同时有具体证据、可执行干预和明确 owner。缺 owner 的条目进入独立 `owner-gap`，不能混入 recommendation；保留 owner-gap 的证据和建议干预。
- `already-covered`、`no-delta`、`source-insufficient` 和 `conflict` 是独立结果。冲突只停止受影响条目的语义写入，其他已校准条目继续；不以代码猜产品意图。
- Manager 的显式调用只授权本轮知识文档的非破坏性更新。移动、重命名、删除、retirement、package 状态修改、代码或外部系统变更，以及用户级宿主状态变更，都需要独立授权。

## Required report

报告必须给出精确整数，零项也写 `0`，不能用“若干”。至少包含：

1. `sources=<n>` 及一次 Source Snapshot（仓库、branch、Source HEAD、dirty、来源引用）。
2. 每个 lane 的 `status`（`ran | skipped | source-insufficient`）和计数：知识 lane 的 `candidates`、`applied`、`already-covered`、`no-delta`、`source-insufficient`、`pending`、`conflict`；environment lane 的 `recommendations`、`owner-gap`、`already-covered`、`no-delta`、`source-insufficient`。
3. 跨 lane 去重的 `considered`、`merged`、`split` 和各条目的 primary destination；不可静默丢弃候选。
4. 修改文件数与路径、verify 结果、未解决的 owner decision、证据缺口和 residue/cleanup。无 durable delta 时报告 `no-delta`，不制造文档。
