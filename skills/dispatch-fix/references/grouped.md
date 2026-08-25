# Grouped repair

适用于四个及以上已确认 findings。当前 task 是集成控制器；每个 group 是独立 Topic，并获得自己的 branch/worktree。

## Fix base

分组模式要求当前 worktree clean。读取 repository instructions，确认当前 branch，并把当前 HEAD 固定为已提交的 `fix_base`。未提交内容不复制、stash 或传播到 group worktrees；无法得到 clean base 时停止分组派发。

## Connected grouping

为每个 finding 标注 topic、预计 write scope 与共享可变资源。将满足任一条件的 findings 连接起来：

- topic 相同；
- 预计修改路径重叠；
- 会写同一生成物、配置、schema 或其他共享可变资源。

每个 connected component 是一个 group。无法证明两个 findings 独立时保守连接；只有 components 之间的 write scope 与共享资源都独立时才并行。即使所有 findings 最终只有一个 component，四个及以上仍使用独立 group worktree。

## Worktrees 与简记

每个 group 从 `fix_base` 创建唯一 branch/worktree，并记录完整 findings、topic 和 write scope。不同写 workers 不共享 worktree，当前 integration worktree 也不交给 worker。

创建 `%TEMP%\dispatch-fix\<fix-id>\groups.json`，由当前 task 单写。使用 [`../scripts/group_bookkeeping.py`](../scripts/group_bookkeeping.py) 原子写入、读取和校验；脚本 `--help` 是命令接口权威。workers 不读取或写入该文件。

只在分组完成、worker 返回、group 验收或集成结论变化时更新简记，不记录命令流水或 heartbeat。

## Worker brief

每个 group 由 `$dispatcher` 作为独立 Topic 派发；下游 bounded worker 使用 `/impl-package:subagent-driven-development` 的 `fix` mode 与 work lane。brief 至少包含：

- group id、topic 和全部 finding acceptance points；
- exact branch/worktree 与 `fix_base`；
- write scope、共享资源约束和排除项；
- focused verification；
- 完整交付说明：source commits、修改范围、验证结果、逐 finding 结论和残余风险。

交付不完整或只有未提交 residue 时不集成。保留原 worktree 作为证据；context/ownership 可信时继续同 Topic work lane，失效时从可验证 base 建 clean repair worktree 并重新派发。

## 验收与集成

当前 task 在 source branch 上核对 commit range、write scope、验证证据和全部 acceptance points。group 只有全部通过才可进入集成。

按可解释顺序把 accepted source commits cherry-pick 回当前分支，随后运行该 group 的 focused acceptance，并分别记录 source 与 integrated commits。集成期间当前 worktree 保持 clean，当前 task 不并行编辑。

cherry-pick 冲突时 abort，停止继续集成其他 groups。把实际重叠重新纳入共写边界，从当前分支建立 clean repair worktree，由该 Topic work lane 产生纠正 commits。集成后 focused acceptance 失败时采用同一 repair 边界。

## 完成条件

所有 groups 都是 `accepted`，全部 source/integrated commits 一一对应且可解析，每组 focused acceptance 通过，当前分支包含全部 accepted 结果并保持 clean。最终汇报引用 `groups.json` 的 group 结论与 integrated commits。
