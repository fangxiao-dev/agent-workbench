# Simple repair

适用于 1–3 个已确认 findings。全部问题组成当前 worktree 中的一个 Topic；当前 task 不创建 ledger、branch 或额外 worktree。

## 保护当前工作树

先读取 repository instructions，并检查当前 branch、HEAD 与 dirty state。把 worker 启动前已经存在的 dirty paths 和 diff 记录为保护范围；它们不是 worker 的成果，也不能被清理、覆盖或顺手提交。

worker 工作期间，当前 task 让出整个 worktree 的写 ownership。直到 worker 返回或明确停止前，当前 task 不在该 worktree 并行编辑。

## Worker brief

由 `$dispatcher` 派发这个 Topic；下游 bounded worker 使用 `/impl-package:subagent-driven-development` 的 `fix` mode 与 work lane。brief 至少包含：

- 全部 finding ID、摘要和 acceptance points；
- 当前 worktree、branch 与启动 HEAD；
- worker 可写范围、启动前 dirty 保护范围和明确排除项；
- focused verification；
- 完整交付说明：修改路径、commits 或 working-tree diff、验证结果、逐 finding 结论和残余风险。

worker 可以按当前仓库规则提交 scoped commits，也可以留下可归因 diff；不得把启动前 dirty 内容混入自己的交付结论。

## 验收与返工

worker 返回后，当前 task 对比启动前后的 Git 状态，确认受保护 diff 未受损、所有新增修改都在允许范围内，并逐项核对 acceptance points。运行覆盖全部 findings 的 focused acceptance。

交付说明不完整、修改无法归因或任一 acceptance point 未通过时，本次尚未接受。上下文与 ownership 仍可信时继续同 Topic work lane；失效时由 Dispatcher 退役并重新派发，不把 worker 空闲或角色名当成复用依据。

## 完成条件

全部 findings 通过 focused acceptance，新增 diff 或 commits 可归因，启动前 dirty 保护范围保持完整，且没有未解释 residue。简单模式不产生 group bookkeeping。
