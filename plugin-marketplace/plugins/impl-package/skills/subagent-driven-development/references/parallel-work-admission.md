# Parallel Work Admission

仅当两个以上 bounded work 候选可能并发执行时读取本页。

只有每个候选都具备独立目标和完成条件、没有未决前置依赖、primary ownership 不重叠且不共享可变运行资源时，才允许并行。端口、测试数据、输出目录、外部记录和其他共享资源必须先隔离；worktree 不在此隔离要求内，可由 scheduling contract 决定是否共享。

返回一个决定：

- `PARALLEL`：列出 batches、每个单元的 ownership、隔离资源和全部返回后的集成验证；
- `SERIAL`：指出要求有序执行的依赖、ownership 重叠、共享资源或未决 seam；
- `BLOCKED`：指出使串行和并行都无法安全开始的缺失决定或授权。

按问题 ownership 划分，而不是按文件数量划分。主 session 负责比较冲突结论或变更，并在全部结果返回后运行共享集成验证。本页只决定 batch 和资源隔离，不设计 Task、不选择 worker，也不派发或回收结果。
