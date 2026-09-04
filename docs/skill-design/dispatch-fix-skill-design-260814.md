# `dispatch-fix` Skill 设计

## 状态

- 日期：2026-08-14。
- 状态：已退役，仅保留历史归档。
- 取代：`dispatch-fix-thread-skill-design-260814.md`。
- Historical archives：`skills-deprecated/dispatch-fix/`、`skills-deprecated/dispatch-fix-thread/`。

## 核心判断

独立 fixer task 不是修复隔离的必要条件。真正影响并行安全的是 worktree ownership：当前 task 可以直接担任修复控制器，只有 findings 数量和共写关系要求时才建立 group worktrees。

Skill 不创建新 task。Owner 若需要额外上下文容量，可以在另一个 task 中调用同一 Skill；该选择不进入 active Skill 的角色、消息或数据合同。

Skill 可以由当前 agent 在符合适用条件时自主调用，也支持 Owner 显式调用；调用方式不改变两档路由与 ownership 合同。

## 两档调度

只统计 review 去重后、已确认且需要修改业务代码的 findings：

- 1–3 个：一个 fresh `@luna-worker` 在当前 worktree 打包修复。当前 task 让出该 worktree 的写 ownership，保护启动前 dirty diff，不创建 ledger、branch 或额外 worktree。
- 4 个及以上：当前 worktree 必须 clean，当前 HEAD 固定为 `fix_base`。按 topic 与预计共写范围形成 connected groups，每组使用独立 branch/worktree 和一个 fresh `@luna-worker`。

connected grouping 把 topic 相同、预计修改路径重叠或会写同一共享资源的 findings 连接起来。无法证明独立时保守合组；只有不同 components 之间可以并行。

## 集成与验收

两种模式都通过 `/impl-package:subagent-driven-development` 使用 `mode=fix`、`worker=@luna-worker` 和 fresh invocation。当前 task 始终拥有 acceptance。

简单模式直接核对当前 worktree 的可归因 diff/commits。分组模式先在 source branch 核对 group 交付，再把 accepted commits cherry-pick 回当前分支并运行 group-focused acceptance。冲突或集成后验收失败时停止后续集成，从当前分支建立 clean repair worktree 交给 fresh worker。

## 轻量简记

只有分组模式写 `%TEMP%\dispatch-fix\<fix-id>\groups.json`。当前 task 单写，workers 不读写。文件只记录 `fix_base`、integration branch/worktree 与每组 findings、topic、write scope、worktree/branch、worker、source/integrated commits、focused verification 和结论。

`group_bookkeeping.py` 只提供原子 `write`、`show`、`validate`；不执行 Git、不派发 worker、不维护命令流水、heartbeat 或工作流状态机。

## 验证

- L0：active/deprecated 结构、Skill validator、脚本 CLI/原子写与合同测试、simple/grouped 路由和数据边界。
- L1：`subagent-driven-development`、相邻 Skill 路由/Git 合同，以及三个 fresh `@luna-worker` 只读场景试跑。
- L0+L1 通过后停止，不运行全仓测试。
