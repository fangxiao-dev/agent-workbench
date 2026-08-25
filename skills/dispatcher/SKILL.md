---
name: dispatcher
description: 当主控需要轻量定义单个 implementation package 如何调度，或正在处理 task-queue.json、worker 返回、depOn 释放和下一批任务派发时使用；提供单写动态队列与 Dispatcher 小事件循环，同时把 Ticket、Gate 和 package closure 留给外部权威。
compatibility: Python 3.10+ standard library
---

# Dispatcher

Dispatcher 是一个面向上游主控、专门轻量定义“如何调度”的工具。它用四字段动态队列和一个小事件循环连接 worker 返回、依赖释放与下一批派发，不建立第二套 package runtime。

它与 `/impl-package:subagent-driven-development` 平级：Dispatcher 指导上游 queue/dispatch/return/idle；SDD 指导下游 bounded worker 的 Topic/dependency/lane/lifecycle。两者共享原则，但互不产出对方的输入。

## 原则

- **单写**：主控是 `task-queue.json` 的唯一 writer；worker 只返回结果。
- **小投影**：队列只保存未完成实施工作。`[]` 表示当前没有队列工作，不表示 package closed；running worker、Ticket evidence、外部 blocker 和 Gate 仍由各自权威判断。
- **机械依赖**：`depOn` 只表达实现地基、材料 seam 和共享可变资源的串行要求。Acceptance Gate 与 Checkpoint 是结论点；环境、fixture、权限、身份与数据准备只要不会使结果失真，就可以提前并行。
- **确认后推进**：派发成功由宿主 receipt 确认后，才把任务标为 `in-progress`。迟到、重复、来源不明或结果不确定的 receipt 先由主控消除歧义。
- **Topic 生命周期**：同一 Topic 的 work lane 可以复用 live worker；review lane 保持独立但可在同 Topic 内承担 recheck；Topic 闭合后退役，新 Topic 使用 fresh worker。test wrapper 只在一轮有界 campaign 内复用。

队列不持久化 Topic、worker 或 session 映射；这些 live coordination 事实由主控持有。Version 0 也不拥有历史、时间戳、文件锁、自动 dispatch、Ticket readiness、acceptance、Gate 或 package closure。

## 阶段查询表

先用左列定位当前阶段，再执行推荐动作。`<queue>` 始终是调用方明确提供的 `<implementation-package>/task-queue.json`。

| 当前描述 | 主控判断 | 推荐动作 |
| --- | --- | --- |
| package 还没有动态队列 | 初始化空队列，保留已有路径 | `init` |
| 发现新的未完成工作 | 写清任务与成功条件；只加入已确定依赖 | `add --id <id> --summary <text> [--dep-on <id>]...` |
| 任务内容或确定依赖变化 | 只更新发生变化的字段 | `update-summary`、`update-status` 或 `update-deps --add\|--remove` |
| worker 返回，任务已不再阻断下游 | 从队列删除并机械释放所有下游 `depOn` | `delete --id <id>` |
| worker 返回，同一 Topic 仍需工作 | work lane 复用 live worker，review lane 保持独立；Topic 闭合后退役，新 Topic 使用 fresh worker | `update-*`，或不改队列并继续原 Topic；不制造 `done` 状态 |
| 两个 test campaign 共享可变资源 | 用 dependency 串行；wrapper 只在各自有界 campaign 内复用并随后退役 | `update-deps --id <later> --add <earlier>` |
| 需要派发下一批工作 | 取得队列原顺序中全部 `planned && depOn=[]` 的任务 | `get-next-tasks` |
| 单个派发已被宿主确认 | 立即记录该任务正在执行 | `update-status --id <id> --status in-progress` |
| 派发结果不确定或 receipt 无法唯一映射 | 暂停队列推进，先消除歧义 | `list [--id <id>]`；此时不写队列 |
| `get-next-tasks` 返回 `[]` | 本轮 idle，等待下一个 worker 返回；整体 closure 另行判断 | 无写动作；按需 `list` 审计 |

完成一个调度轮次的可观察条件是：每个成功派发的任务均为 `in-progress`，不存在未解决的 receipt/派发歧义，最后一次 `get-next-tasks` 返回 `[]`。

## CLI 用法

从当前已加载 Skill 目录解析脚本；脚本不发现 package，也不读取或同步 package state：

```text
python <dispatcher-skill>/scripts/task_queue.py --path <task-queue.json> <command>
```

队列每项固定包含 `id`、`summary`、`status` 和 `depOn`。`summary` 用一两句话同时说明工作与成功条件；`status` 只有 `planned` 与 `in-progress`。删除在机械上不区分完成与取消，原因由主控在队列外记录。

首次使用执行 `init`；查询使用 `list` / `get-next-tasks`；其余命令都是写操作。需要精确参数时读取脚本 `--help`，不要缓存 CLI 可以直接给出的事实。

脚本严格校验 JSON、dependency 和 cycle，并用原子替换持久化。成功写操作输出更新后的完整队列；查询输出 JSON；失败返回非零且保留原文件。
