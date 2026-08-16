# Parallel Work Admission

上游 Owner/`readyTickets` 已明确并行候选后才读取本页；候选发现、依赖释放和一般调度不由本页负责。它只做本体系的资源准入：共享可变运行资源（worktree、integration carrier、端口、测试数据、输出目录或外部记录）必须隔离；不能隔离就串行，并记录顺序、owner 和 cleanup。

返回一个决定：

- `PARALLEL`：列出 batches、每个单元的 ownership、隔离资源和全部返回后的集成验证；
- `SERIAL`：指出共享资源、ownership 或未决 seam 要求有序执行；
- `BLOCKED`：指出使串行和并行都无法安全开始的缺失决定或授权。

主 session 负责比较冲突结论或变更，并在全部结果返回后运行共享集成验证。本页只决定 batch 和资源隔离，不设计 Task、不选择 worker，也不派发或回收结果。
