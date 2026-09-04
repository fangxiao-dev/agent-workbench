---
name: dispatch-fix-thread
description: Deprecated archive of the former dedicated fixer task workflow. Do not invoke.
deprecated: true
disable-model-invocation: true
---

# Dispatch Fix Thread

> Deprecated historical archive. Do not invoke.

为一次有界修复工作建立独立 fixer task。parent 保留需求与最终验收所有权；fixer 独立管理分组、隔离 worktree、worker、聚焦验收和 fix branch。

本 Skill 只接受显式调用。它不依赖 `thread-harness`，也不承担通用 task 编排、心跳或恢复服务。

## 路由

先从调用内容确定唯一角色与动作，然后只读取对应文件：

- `role=parent, action=dispatch`：读取 [`references/parent-dispatch.md`](references/parent-dispatch.md)。parent 中只写 `$dispatch-fix-thread` 时默认走此路径。
- `role=fixer, action=run|resume`：读取 [`references/fixer.md`](references/fixer.md)。
- `role=parent, action=integrate`：读取 [`references/parent-integrate.md`](references/parent-integrate.md)。

在回答或行动前完整读取选中的 reference；根文件只负责路由，不足以执行任何路径。不要读取未选中的角色文件。若角色、动作或记录目录无法唯一确定，先停止有副作用的动作并要求调用者补齐。

## 共同边界

- 本次修复只消费 parent 已确认的 findings，不重新裁决需求或扩大验收范围。
- `reviewed_head` 是 fixer branch 的不可变起点；parent 未提交内容不复制、不 stash、不清理。
- 同时写代码的执行者各自拥有独立 branch/worktree；共享 worktree 不构成并行隔离。
- live records 位于 `%TEMP%\dispatch-fix-thread\<fix-id>\`。parent 创建一次 `request.json`；fixer 单写 `state.json`；worker 不读取或写入记录。
- 每次修复同时只有一个活跃 fixer task。替换它之前先确认旧 task 已停止。
- 授权仅覆盖本地 task、branch、worktree、commit、cherry-pick 和明确的本地验证。push、PR、deployment、远程系统和其他外部副作用仍需另行授权。

## 完成条件

选中路径必须满足其文件中的可观察完成条件。消息只用于唤醒和定位；`request.json`、`state.json` 与 Git anchors 才是交付事实。
