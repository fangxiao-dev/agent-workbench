---
name: task-queue
description: 当调用方明确要求创建、读取或修改 task-queue.json、depOn，或执行 init、list、get-next-tasks、add、update-*、delete 队列命令时使用；把 Dispatcher 已裁决的 baby steps 持久化为单写动态队列。
compatibility: Requires the dispatcher skill and Python 3.10+ standard library
---

# Task Queue

先调用 `$dispatcher` 并读取 [Dispatcher](../dispatcher/SKILL.md)，取得当前已通过调度门槛的 baby steps；本 Skill 只把这些结论投影为四字段 JSON，并用一个小事件循环连接派发确认、worker return、依赖释放与下一批查询。

## 原则

- **单写**：主控是 `task-queue.json` 的唯一 writer；worker 只返回结果。
- **可调度投影**：队列只回答“现在可以派什么”，不回答“这件事做完没有”。`[]` 表示当前没有队列工作，不表示 package closed；running worker、Ticket evidence、外部 blocker 和 Gate 仍由各自权威判断。
- **任务粒度**：一个队列项只对应 Dispatcher 已裁决的一个 baby step，不等同于 Topic 或 Ticket。具体 write-set、worker 复用和 worktree 选择留在队列外。
- **机械依赖**：只有另一个队列项的产出才有资格成为 `depOn`，用于表达实现地基、材料 seam 和共享可变资源的串行要求。Acceptance Gate、Checkpoint 与验收结论不编码为 `depOn`。可靠性来自写入时的准入严格，而不是 `get-next-tasks` 自行判断 blocker 是否真实。
- **依赖是活的**：每轮查询前重新核对现存 `depOn`。发现新的实现地基就补依赖，地基解除就删依赖。
- **占用而非运行**：`in-progress` 只表示已被主控占用、不应再次派发，不承诺 worker 此刻仍在运行。外部因素阻塞的任务保持 `in-progress`，不退回 `planned`；阻塞解除后再转回 `planned`。
- **确认后推进**：派发成功由宿主 receipt 确认后，才把任务标为 `in-progress`。迟到、重复、来源不明或结果不确定的 receipt 先由主控消除歧义。

队列不持久化 Topic、worker 或 session 映射，也不拥有历史、时间戳、文件锁、自动 dispatch、Ticket readiness、acceptance、Gate 或 package closure。

## 阶段查询表

`<queue>` 始终是调用方明确提供的 `task-queue.json`。

| 当前描述 | 主控判断 | 推荐动作 |
| --- | --- | --- |
| 还没有动态队列 | 初始化空队列，保留已有路径 | `init` |
| Dispatcher 给出新的合格 baby step | 写清唯一结果与成功条件，只加入已确定依赖 | `add --id <id> --summary <text> [--dep-on <id>]...` |
| 任务内容或确定依赖变化 | 只更新发生变化的字段 | `update-summary`、`update-status` 或 `update-deps --add\|--remove` |
| worker 返回，主控已判定该队列项 fully completed，或 cancelled/superseded 且下游已改依赖或退役 | 该项已经没有剩余工作，机械释放不会误派下游 | `delete --id <id>`，释放所有下游 `depOn` |
| worker 返回，同一 Topic 仍需工作 | 先消费当前结果，再登记 Dispatcher 给出的下一 baby step | `update-*`，或 retire 当前项后 `add` 下一动作；不制造 `done` 状态 |
| worker 返回 `BLOCKED` | 先分流阻塞来源，不直接删除任务 | 另一队列项可解除 → 原任务设为 `planned + depOn=[blocker]`；外部/Owner → 保持 `in-progress`；本轮共享依赖 → 新建 blocker 并让受阻任务依赖它 |
| 两个 test campaign 共享可变资源 | 用 dependency 串行 | `update-deps --id <later> --add <earlier>` |
| 需要查询下一批工作 | 取得原顺序中全部 `planned && depOn=[]` 的任务 | `get-next-tasks` |
| 单个派发已被宿主确认 | 立即记录该任务正在执行 | `update-status --id <id> --status in-progress` |
| 派发结果不确定或 receipt 无法唯一映射 | 暂停推进，先消除歧义 | `list [--id <id>]`；此时不写队列 |
| `get-next-tasks` 返回 `[]` | 本轮 idle，等待 worker return 或新的 Dispatcher 结论 | 无写动作；按需 `list` 审计 |

完成一个队列轮次的可观察条件是：每个成功派发的任务均为 `in-progress`，不存在未解决的 receipt/派发歧义，最后一次 `get-next-tasks` 返回 `[]`。

## CLI 用法

从当前已加载 Skill 目录解析脚本；脚本不发现 package，也不读取或同步 package state：

```text
python <task-queue-skill>/scripts/task_queue.py --path <task-queue.json> <command>
```

队列每项固定包含 `id`、`summary`、`status` 和 `depOn`。`summary` 用一两句话同时说明工作与成功条件；`status` 只有 `planned` 与 `in-progress`。`delete` 表示从未完成投影 retire：主控先在队列外记录 fully completed、cancelled 或 superseded 的结论，确认该项没有剩余工作；cancelled/superseded 时还要确认下游已改依赖或退役，再执行机械删除与依赖释放。

首次使用执行 `init`；查询使用 `list` / `get-next-tasks`；其余命令都是写操作。需要精确参数时读取脚本 `--help`。

脚本严格校验 JSON、dependency 和 cycle，并用原子替换持久化。成功写操作输出更新后的完整队列；查询输出 JSON；失败返回非零且保留原文件。
