# Dependency and Resource Admission

存在多个当前候选或一步 `look-ahead` 准备时读取本页。先逐项分类：

- `foundation`：绑定未稳定语义的下游实现等待；无关准备可继续。
- `acceptance`：阻止正式验收、evidence 采信或状态宣称，不自动阻止隔离准备。
- `resource`：文件 ownership、integration carrier、端口、DB、测试数据、输出目录或外部记录；能隔离才并行，否则串行。caller 可以为文件写入选择当前或新隔离 worktree；DB、端口和其他运行资源分别验证。
- `authorization`：未获授权的 mutation/外部副作用等待；只读调查可继续。

每个并行单元必须有互斥 ownership、隔离资源和 cleanup owner。环境、fixture、权限、身份、数据或 test carrier 只有在不绑定未稳定业务语义、结果可回收且不提前充当 acceptance evidence 时，才能作为一步前瞻准备。

返回当前批次的 `PARALLEL | SERIAL | BLOCKED` 结论，附实际 dependency、worktree 选择、资源顺序和 cleanup。上游 `$dispatcher` 负责把已确定的任务写入动态队列并执行派发循环。

完成标准：并行单元不存在共享可变 ownership；串行单元有唯一顺序；阻断项明确缺失的 foundation、授权或隔离条件。
