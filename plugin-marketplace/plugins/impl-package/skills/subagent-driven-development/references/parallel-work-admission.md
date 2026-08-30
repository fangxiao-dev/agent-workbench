# Dependency and Resource Admission

存在多个当前候选或一步 `look-ahead` 准备时读取本页。先逐项分类；`foundation`、`acceptance`、`resource`、`authorization` 四类 dependency 的定义以 [SKILL.md](../SKILL.md) 的「Step 2 · 分类 dependency」表为唯一权威，本页不重复。

- `resource`：文件 ownership、integration carrier、端口、DB、测试数据、输出目录或外部记录；能隔离才并行，否则串行。caller 可以为文件写入选择当前或新隔离 worktree；DB、端口和其他运行资源分别验证。

每个并行单元必须有互斥 ownership、隔离资源和 cleanup owner。环境、fixture、权限、身份、数据或 test carrier 只有在不绑定未稳定业务语义、结果可回收且不提前充当 acceptance evidence 时，才能作为一步前瞻准备。

返回当前批次的 `PARALLEL | SERIAL | BLOCKED` 结论，附实际 dependency、worktree 选择、资源顺序和 cleanup。上游 `$dispatcher` 消费这些结论并执行派发循环。

完成标准：并行单元不存在共享可变 ownership；串行单元有唯一顺序；阻断项明确缺失的 foundation、授权或隔离条件。
