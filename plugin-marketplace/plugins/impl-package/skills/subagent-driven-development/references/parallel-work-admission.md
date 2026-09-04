# Dependency and Resource Admission

存在多个当前候选或一步 `look-ahead` 准备时读取本页。先逐项分类；`foundation`、`acceptance`、`resource`、`authorization` 四类 dependency 的定义以 [SKILL.md](../SKILL.md) 的「Step 2 · 分类 dependency」表为唯一权威，本页不重复。

- `resource`：文件 ownership、integration carrier、端口、DB、测试数据、输出目录或外部记录；能否隔离并行按当前 baby step 的 effect footprint 判断，能隔离才并行，否则串行。caller 可以为文件写入选择当前或新隔离 worktree；DB、端口和其他运行资源分别验证。

每个并行的 baby step 必须有互斥 ownership、隔离资源和 cleanup owner。环境、fixture、权限、身份、数据或 test carrier 只有在不绑定未稳定业务语义、结果可回收且不提前充当 acceptance evidence 时，才能作为一步前瞻准备。

新隔离 worktree 承担 format/lint/typecheck 等 mechanical 载体前，先确认它能解析到所需本地 binary/shim（如 Prettier、DOM shim、node_modules）；无法确认时先归位到当前 worktree 或派一步最小验证，不假定新 worktree 与主 workspace 工具链等价。mechanical step 的完成声明要有可观察证据（diff、文件 mtime、命令输出）支撑，不能只采信 worker 的文本自述——载体本身失败、结果不达标是两回事，前者需要先确认再决定是否重派。

返回当前批次的 `PARALLEL | SERIAL | BLOCKED` 结论，附实际 dependency、worktree 选择、资源顺序和 cleanup。上游 `$dispatcher` 消费这些结论并执行派发循环。

完成标准：并行单元不存在共享可变 ownership；串行单元有唯一顺序；阻断项明确缺失的 foundation、授权或隔离条件。
