---
name: subagent-driven-development
description: 当原因、影响面与必要前置事实已经建立，并且需要决定主 session 与 subagent 分工、default-long/ordinary、串并行 batch 或共享资源顺序时使用；输出调度合同并路由后续执行。
---

# Subagent-Driven Development

本 skill 只决定工作留在主 session 还是交给 subagent、采用什么 mode 和执行顺序，以及进入哪个后续路由。业务合同、Task/Ticket、授权、worker 和验收由各自 owner 提供。

## 调度

1. 默认使用 `default-long`：主 session 保留目标解释、跨工作取舍和最终责任，subagent 承担边界明确且可独立复核的连续执行。聚焦或紧耦合工作可使用 `ordinary`，并用一句任务事实说明理由。
2. 单个聚焦单元选择 `LOCAL`；委派的单个或有序单元选择 `SERIAL`。存在两个以上并发候选时，读取 [Parallel Work Admission](references/parallel-work-admission.md) 决定 `SERIAL`、`PARALLEL` 或 `BLOCKED`。
3. 仅在实际共享数据库、browser/provider、生成目录、端口、测试数据或其他单写资源时，记录隔离方式或唯一顺序和 cleanup owner。
4. 选择下游路由，并只输出当前决定真正需要的内容：

```text
Scheduling: <LOCAL | SERIAL | PARALLEL | BLOCKED> · mode=<default-long | ordinary> · route=<route>
resources: <仅存在共享资源、顺序或 cleanup 责任时输出>
reason/blocker: <仅决定不显然或无法调度时输出>
```

## 路由

- 独立 review → `reviewer`。
- Impl-Package 基于批准的 Plan、Ticket 或 DAG 向 subagent 派发已释放的实现或只读验证单元 → `/impl-package:dispatch-bounded-task`；不要求 DAG Task artifact。
- 其他普通 bounded work → 按 scheduling contract 直接执行或委派。

主 session 始终拥有最终集成、证据采信和结果判断。
