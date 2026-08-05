---
name: dispatching-parallel-agents
description: Use when two or more bounded tasks can run independently without overlapping writes, shared runtime resources, or sequential decisions.
---

# Dispatching Parallel Agents

并行的价值来自独立性，而不是 agent 数量。只有任务可以分别理解、分别产出，并在最后安全集成时才并行派发。

## 派发判断

派发前确认：

- 每个任务有独立目标和可判断的完成条件；
- 任务之间没有未解决的先后依赖；
- 不会同时修改同一文件或写入同一外部状态；
- 端口、测试数据、输出目录等共享资源已经隔离；
- 主 agent 知道结果回来后如何检查冲突和完成集成验证。

任一条件不成立时，改为串行执行，或先切出稳定 seam。

## 派发方式

1. 按问题边界拆分任务，不按文件数量机械拆分。
2. 给每个 agent 明确 scope、必要上下文、禁止事项和预期返回内容。
3. 说明允许的读写范围；没有授权时默认只读。
4. 并行启动真正独立的任务，主 agent 同时处理不冲突的协调工作。
5. 收回结果后检查重叠修改、相互矛盾的结论和未覆盖 seam，再运行必要的集成验证。

## 不适用

- 仍在探索根因，尚不知道问题是否相关；
- 一个修复可能同时消除多个失败；
- 任务依赖相同的可变环境或外部记录；
- 每个 agent 都必须先理解整个系统才能工作。

并行 agent 的结论是输入，不是最终证据；主 agent 仍负责集成和最终判断。
