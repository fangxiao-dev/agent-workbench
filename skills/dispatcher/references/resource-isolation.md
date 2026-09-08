# Resource Isolation

存在多个候选、共享可变资源、隔离 worktree 或一步前瞻准备时读取本页。

## Dependency

| dependency | 限制 | 可继续的工作 |
| --- | --- | --- |
| `foundation` | 会绑定未稳定语义、数据形状或材料 seam 的实现 | 与结论无关、已授权且可回收的调查或准备 |
| `acceptance` | 正式验收、evidence 采信和状态宣称 | 合同与实际前置已满足的实施或准备 |
| `resource` | 对同一不兼容 effect footprint 的同时执行 | 已隔离资源上的其他工作 |
| `authorization` | 未获授权的 mutation 或外部副作用 | 只读调查和授权范围内的准备 |

dependency 逐候选呈现；缺席候选带类型和受影响的 `subject` 或 `resource_key`。局部 barrier 不升级为全局 blocking。

## 实际资源

按当前动作声明并核验文件 write ownership、读取/观察影响、integration carrier、DB、端口、测试数据、输出目录和外部记录。两个稳定只读操作可以共享；一方会改变另一方的读取结果或验证 oracle 时隔离或排序。独立 worktree 只隔离文件，运行资源分别核验。

每个并行动作声明 `resource_keys`、整合 owner 与 cleanup owner。资源声明由派发方提供；系统不推断、不扫描，也不把业务 Ticket/Topic 当作互斥单位。无法隔离的共享可变资源使用唯一串行顺序。

主控按当前 dependency、授权、已知实际冲突和在途工作判断资源准入；相同 `resource_key` 本身不等于冲突。恢复旧 Attempt 时，只读旧 trail/候选清单以及 Execution Record、checkpoint、handoff，沿用其中仍成立的授权和资源限制，不另建 blocker fact，也不重写旧记录。

新 worktree 承担 format、lint 或 typecheck 前，先确认能解析所需 binary、shim 和本地依赖。完成声明用 diff、mtime 或命令输出证明；carrier 失败与产物失败分别处理。

环境、fixture、权限、身份、数据或 test carrier 只有在不绑定未稳定业务语义、结果可回收且不提前充当 acceptance evidence 时，才作为独立候选。

完成标准：并行动作没有不兼容的共享 effect footprint；串行动作有唯一顺序；每项 dependency、resource key、整合与 cleanup owner 均可核对。
