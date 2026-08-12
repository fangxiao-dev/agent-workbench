---
name: subagent-driven-development
description: 当原因、影响面与必要前置事实已经建立，并且需要决定主 session 与 subagent 分工、串并行 batch 或共享资源顺序时使用；输出调度合同并路由后续执行。
---

# Subagent-Driven Development

本 skill 只决定工作留在主 session 还是交给 subagent、执行顺序以及进入哪个后续路由。业务合同、Task/Ticket、授权、worker 和验收由各自 owner 提供。

## 调度

1. 可委派的单个或有序 bounded unit 选择 `SERIAL`。存在两个以上并发候选时，读取 [Parallel Work Admission](references/parallel-work-admission.md) 决定 `SERIAL`、`PARALLEL` 或 `BLOCKED`。
2. `LOCAL` 只用于原子操作、与主 session 紧耦合的集成，或无法隔离的共享资源操作，并记录具体理由。
3. 预计长时间运行或高回显的既定只读测试作为单个 `SERIAL` verification unit 路由 `/impl-package:dispatch-bounded-task`，由其选择 Verifier；单条、快速且输出有界的原子检查满足上一条条件时可留在主 session。实现动作或有写副作用的命令不属于 Verifier。
4. 每个委派的 bounded unit 使用 fresh subagent。只有同一 source unit 尚在连续执行且依赖不可转移的 live resource/process state，或下游 skill 明确声明 standing role 时，才沿用既有 subagent 并记录连续性理由。已发生 context compaction 时，从 canonical input 启动 fresh subagent。角色相同、agent 空闲或共享 worktree 不构成复用理由。
5. 仅在实际共享数据库、browser/provider、生成目录、端口、测试数据或其他单写资源时，记录隔离方式或唯一顺序和 cleanup owner。
6. 选择下游路由，并只输出当前决定真正需要的内容；省略 `reuse` 表示使用 fresh subagent：

```text
Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED> · route=<route>
resources: <仅存在共享资源、顺序或 cleanup 责任时输出>
reuse: <仅显式沿用既有 subagent 时输出 source unit、agent 和连续性理由>
reason/blocker: <LOCAL 或 BLOCKED 时必填；其他情况仅决定不显然时输出>
```

## 路由

- 独立 review → `reviewer`。
- Impl-Package 基于批准的 Plan、Ticket 或 DAG 向 subagent 派发已释放的实现或只读验证单元 → `/impl-package:dispatch-bounded-task`；不要求 DAG Task artifact。
- 其他普通 bounded work → 按 scheduling contract 直接执行或委派。

主 session 始终拥有最终集成、证据采信和结果判断。
