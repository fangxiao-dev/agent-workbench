---
name: investigate-before-implement
description: Use when about to write code, change shared state, or run a migration for a task whose cause, blast radius, or existing solution has not been established yet.
---

# Investigate Before Implement

按 investigate → implement 的顺序，先做调研再执行，不要直接开干；按需外派任务，以提高并行度并且降低 context 压缩损耗。

## Worker capability

如果存在 `@luna-worker`，implement 可以优先使用它；不可用或调用失败时使用当前 host 的 subagent。

## Investigate
调研的产出是判断依据，不是文档——**写不出判断依据就等于没调研**。
Investigate 按需外派；worker 选择服从当前 host 的可用能力和调用者给出的任务边界，不在本 skill 固定模型或推理档位。

### 什么时候必须先调研

- 你还说不出改动会波及哪些调用方；
- 你不确定现有实现里是不是已经有等价方案；
- 失败症状可能由多个原因产生，你还没排除掉其中任何一个；
- 改动要碰共享状态、外部服务或迁移。

反过来：改动只有一处、影响面已知、且有现成验证能立刻判对错时，直接做。

### 怎么调研

1. 先写下你要回答的具体问题，不要开放式"看看代码"。
2. 单个问题可以直接调查；存在两个或更多候选工作项时，先按 [Parallel Work Admission](references/parallel-work-admission.md) 判断并行、串行或阻塞。
3. 只派发已通过并行准入的 batch；每个 worker 都接收独立目标、scope、资源边界和返回合同。
4. 结论只留能改变决定的那几条，其余不进正文。

## 不适用

- 已经调研过、结论还没过期，只是想再确认一遍；
- 探索本身就是任务目标——此时调研就是实现；
- 问题小到调研成本高于直接试错并回滚。

调研的结论是作为调用者的输入和参考，并不是直接的结论；判断、具体的下一步 implement 计划起草与验收仍然由你自己完成。
