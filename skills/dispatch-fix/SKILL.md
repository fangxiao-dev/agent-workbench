---
name: dispatch-fix
description: 当一批已确认的业务代码 findings 适合委派修复时使用；少量问题由一个 subagent 原地修复，四个以上按 topic 与共写风险分组到独立 worktrees。用户也可以显式调用 `$dispatch-fix`。
---

# Dispatch Fix

由当前 task 控制一组已确认 findings 的修复。先去重并只计算需要修改业务代码的 findings；文档修正、重复项和仍需调查的问题不进入数量门槛。

## 路由

- 1–3 个 findings：完整读取 [`references/simple.md`](references/simple.md)，由一个 worker 在当前 worktree 处理。
- 4 个及以上：完整读取 [`references/grouped.md`](references/grouped.md)，按 topic 与潜在共写范围形成 groups，每组使用独立 worktree。

根文件只负责计数和路由，不足以执行任一路径。只读取选中的 reference。

## 共同合同

- 当前 task 始终拥有分组、验收和最终集成判断。
- 每个 bounded unit 使用 `/impl-package:subagent-driven-development` 形成当前策略，固定 `mode=fix`、`worker=@luna-worker` 和 fresh invocation；其他策略字段服从该 Skill 的当前合同。
- 使用 `$git-workflow` 约束 dirty state、branch ownership、integration base 和冲突处理。
- finding 是验收点；worker 的局部 DONE、commit 或测试通过都不单独代表 finding 已关闭。
- 授权只覆盖明确范围内的本地修改和验证。push、PR、deployment 与外部系统副作用需要另行授权。

## 完成条件

选中路径中的全部 findings 都有可归因结论，当前 task 已完成该路径要求的 focused acceptance，且没有未解释的越界修改或 residue，才可报告本次修复完成。
