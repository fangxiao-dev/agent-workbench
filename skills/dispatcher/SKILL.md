---
name: dispatcher
description: 当主控需要以 baby step 为硬门槛定义 implementation package 如何调度，或正在处理 task-queue.json、worker 返回、depOn 释放和下一步派发时使用；提供轻量调度指导与可选的单写动态队列，同时把 Ticket、Gate 和 package closure 留给外部权威。
compatibility: Python 3.10+ standard library
---

# Dispatcher

## Router

默认进入轻量模式：只提供调度判断、依赖分类和下一步动作建议，队列能力保持关闭。只有调用方明确请求处理 `task-queue.json`、`depOn`、`init`、`list`、`get-next-tasks`、`add`、`update-*` 或 `delete` 时，才进入队列模式并读取下方动态队列合同。未触发队列模式时，不创建、读取或修改队列文件。

Dispatcher 是一个面向上游主控、专门轻量定义“如何调度”的工具。它用四字段动态队列和一个小事件循环连接 worker 返回、依赖释放与下一批派发，不建立第二套 package runtime。

它与 `/impl-package:subagent-driven-development` 平级：Dispatcher 指导上游 queue/dispatch/return/idle；SDD 指导下游 bounded worker 的 Topic/dependency/lane/lifecycle。两者共享原则，但互不产出对方的输入。

## Baby step 派发门槛

**先切 baby step，再讨论队列、并行或 worker。** Topic 只是连续动作共享上下文的容器，不是一次派发的尺寸；一次派发只对应一个 Topic 内当前一个动作。这个门槛逐 Topic 生效，不把整个批次降为单线程。

派发前做一次**独立可返回性**检查：请求中的任一材料面、判断项或交付部分，只要能不依赖其余部分而独立返回、独立验证并被主控单独消费，它就是另一个 baby step；此时继续切分，由主控消费局部结果后综合，不把跨材料面的取证与综合包装成一次派发。多个材料族、逐项结论或完整候选表是需要检查的信号，不是按关键词机械拒绝。

这个门槛判断结果能否独立消费，不按文件数量或检索范围设硬上限。为一个窄问题在整个仓库检索时，检索范围宽仍可以是一个动作；为一个 coherent outcome 修改多个紧密相关文件时，跨文件也仍可以是一个动作，只要其中没有任何一部分能先形成独立可消费的结果。

动作只有在结果可二元判定、前置依赖已回答且能独立验证时才可派发；否则先继续切分，同一依赖链只派第一个已解锁动作。每轮扫描全部候选，把互不依赖的合格 baby steps fan out；文件 ownership 交叉时先交给 SDD 判断能否用隔离 worktree 分开，只有无法隔离的共享可变资源才串行。worker 返回后先消费结果，再决定该 Topic 的下一步。

## 原则

- **单写**：主控是 `task-queue.json` 的唯一 writer；worker 只返回结果。
- **可调度投影**：队列只回答“现在可以派什么”，不回答“这件事做完没有”。`[]` 表示当前没有队列工作，不表示 package closed；running worker、Ticket evidence、外部 blocker 和 Gate 仍由各自权威判断。
- **任务粒度**：一个队列项只对应 Topic 内一个合格 baby step，不等同于 Topic 或 Ticket。具体 write-set、worker 复用和 worktree 选择归 SDD 与主控，不进 JSON。
- **机械依赖**：只有“另一个队列项的产出”才有资格成为 `depOn`，用于表达实现地基、材料 seam 和共享可变资源的串行要求。Acceptance Gate、Checkpoint 与验收结论都不编码为 `depOn`；环境、fixture、权限、身份与数据准备只要不会使结果失真，就可以提前并行。队列本身无法判断一个阻塞是否真实，可靠性来自写入时的准入严格——杠杆在 `add`/`update-deps` 那一刻，不在 `get-next-tasks` 那一刻。
- **依赖是活的**：每轮派发前重新核对现存 `depOn` 是否仍然成立。发现新的实现地基就补依赖，地基解除就删依赖，不是一次写死。
- **占用而非运行**：`in-progress` 只表示“已被主控占用、不应再次派发”，不承诺 worker 此刻仍在运行，也不区分正在执行、等待复核还是暂时卡住。因此被外部因素阻塞的任务保持 `in-progress`，不退回 `planned`——否则 `get-next-tasks` 会把它当成 ready 返回。阻塞解除后再转回 `planned`，由下一轮扫描自然捡起。
- **确认后推进**：派发成功由宿主 receipt 确认后，才把任务标为 `in-progress`。迟到、重复、来源不明或结果不确定的 receipt 先由主控消除歧义。
- **Topic 生命周期**：同一 Topic 的 work lane 可以复用 live worker；review lane 保持独立但可在同 Topic 内承担 recheck；Topic 闭合后退役，新 Topic 使用 fresh worker。test wrapper 只在一轮有界 campaign 内复用。

队列不持久化 Topic、worker 或 session 映射；这些 live coordination 事实由主控持有。Version 0 也不拥有历史、时间戳、文件锁、自动 dispatch、Ticket readiness、acceptance、Gate 或 package closure。

## 阶段查询表

先用左列定位当前阶段，再执行推荐动作。`<queue>` 始终是调用方明确提供的 `<implementation-package>/task-queue.json`。

| 当前描述 | 主控判断 | 推荐动作 |
| --- | --- | --- |
| package 还没有动态队列 | 初始化空队列，保留已有路径 | `init` |
| 发现新的未完成工作 | 逐个候选切出其当前已解锁 baby step；写清唯一结果与成功条件，只加入已确定依赖；合格候选全部进入本轮投影 | `add --id <id> --summary <text> [--dep-on <id>]...` |
| 任务内容或确定依赖变化 | 只更新发生变化的字段 | `update-summary`、`update-status` 或 `update-deps --add\|--remove` |
| worker 返回，主控已判定该队列项 fully completed，或 cancelled/superseded 且下游已改依赖或退役 | 该项已经没有剩余工作，机械释放不会误派下游，可以从未完成投影 retire | `delete --id <id>`，机械释放所有下游 `depOn` |
| worker 返回，同一 Topic 仍需工作 | 先消费当前结果，再切下一 baby step；work lane 可复用 live worker，review lane 保持独立 | `update-*`，或 retire 当前项后登记下一动作；不制造 `done` 状态 |
| worker 返回 `BLOCKED` | 先分流阻塞来源，不直接删除任务 | 另一队列项的产出可解除 → 把 blocker 写成队列项，原任务设为 `planned + depOn=[blocker]`；外部/Owner 决策/上游 → 保持 `in-progress`，原因记在队列外；本轮内部共享依赖（环境、fixture、测试载体、端口、DB）→ 新建 blocker 队列项，所有受阻任务设为 `planned + depOn=[blocker]` |
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

队列每项固定包含 `id`、`summary`、`status` 和 `depOn`。`summary` 用一两句话同时说明工作与成功条件；`status` 只有 `planned` 与 `in-progress`。`delete` 表示从未完成投影 retire：主控先在队列外记录 fully completed、cancelled 或 superseded 的结论，确认该项没有剩余工作；cancelled/superseded 时还要确认下游已改依赖或退役，再执行机械删除与依赖释放。

首次使用执行 `init`；查询使用 `list` / `get-next-tasks`；其余命令都是写操作。需要精确参数时读取脚本 `--help`，不要缓存 CLI 可以直接给出的事实。

脚本严格校验 JSON、dependency 和 cycle，并用原子替换持久化。成功写操作输出更新后的完整队列；查询输出 JSON；失败返回非零且保留原文件。
