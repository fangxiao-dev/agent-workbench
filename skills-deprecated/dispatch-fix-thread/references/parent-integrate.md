# Parent: integrate (Deprecated)

只处理 fixer 的 terminal receipt。parent 读取结果、做机械核对并接回聚合分支，不重新管理 fixer 的内部过程。

## 读取终态

调用 [`../scripts/bookkeeping.py`](../scripts/bookkeeping.py) 的 parent view 读取 terminal projection。`status=working`、缺失记录或校验失败都不授权集成；向 Owner 报告当前事实即可。

只有 `status=ready` 时继续。`status=blocked` 时报告具名 blocker、已存在的部分 commits 和 records 路径；不要把部分结果当作 ready。

## 机械核对

读取仓库 instructions，并使用 `$git-workflow` 约束 dirty state、branch ownership、integration base 和冲突处理。核对：

- request 中每个 finding 都出现在一个 accepted group；
- 每组 `source_commits` 与 `integrated_commits` 数量相等、顺序对应且能在 Git 中解析；
- fixer branch/head、`reviewed_head` 和 projection 一致；
- fixer worktree clean；
- `reviewed_head..fixer_head` 的 diff 没有超出 request 的 allowed scope。

这些检查确认交付边界，不重复 fixer 已通过的 focused verification。

## 本地集成与验证

parent worktree 有未提交内容时停止；不自动 stash、clean 或移动这些内容。按目标仓库惯例选择 fast-forward 或 merge commit，把 fixer branch 本地集成到当前 parent branch。发生冲突时停止并保留可诊断状态，不猜测解决方案。

比较 parent 在 `reviewed_head` 后修改的路径与 fixer diff 路径：

- 没有重叠：只运行 request 中预留的 remaining verification；
- 有重叠：除 remaining verification 外，重跑受重叠影响的 focused checks。

parent 继续拥有最终 acceptance、merge 后记录与发布判断。本动作不授权 push、PR 或 deployment。

## 完成条件

只有聚合分支已进入 parent branch、所需 remaining verification 已取得当前 revision 的证据，且受路径重叠影响的 focused checks 已按需重跑，才能报告 integrate complete。分别报告集成方式、最终 HEAD、运行的验证和未解决事项。
