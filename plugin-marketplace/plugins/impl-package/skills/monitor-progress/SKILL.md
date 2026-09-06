---
name: monitor-progress
description: 打开 Impl-Package 实时进度页面，并在用户确认后从统一模板创建或更新只读主控监控 automation；调用者提供任务包路径和目标会话 ID。
disable-model-invocation: true
---

# Monitor Progress

默认打开目标任务包的实时进度页面，再询问是否启用 automation 评价。稳定合同、完整运行上下文和落盘由 [`../../scripts/monitor_progress.py`](../../scripts/monitor_progress.py) 承担；本 Skill 只负责编排页面、用户选择、一次性 baseline 和短 heartbeat。

## 输入

必需：

- `package`：implementation package 绝对路径；
- `target`：被评价的主控 Codex thread ID。

当前调用会话就是承接结果的 monitor thread；Codex 优先读取 `CODEX_THREAD_ID`，其它宿主使用其 calling-thread context，仍不可取得时才补问 monitor ID，不通过任务列表猜测。target 接受裸 UUID 或 `codex://threads/<id>`。可选输入为 `id`、`name`、`target-title`、`interval-minutes`；默认值：

- `id=monitor-progress-<target-id 后 8 位>`；
- `name=Impl-Package 监控 · <package 目录名>`；
- `target-title` 从 `read_thread(target)` 取得；
- `interval-minutes=20`。

缺少 package 或 target 时只询问缺失值；不猜测 package，不从网页下拉框替用户选择。

## 打开页面

1. 取得当前 Codex thread ID 作为 monitor；只读确认 package、target 和 monitor 可访问。
2. 调用 `monitor_progress.py open --target <target> --package <package>`。CLI 验证归属，启动或复用 v2 renderer，并打开精确 task/package 深链接。
3. CLI 非零退出时报告原始失败点并停止；页面未成功打开时不创建 sidecar 或 automation。
4. 页面打开后只问一次：“是否启用 automation 监控？”
5. 用户拒绝时返回页面 URL 并停止，保持工作区没有新增监控状态。

完成标准：用户已经看到目标页面，且是否创建 automation 仍由用户单独决定。

## 启用 automation

仅在用户确认后继续：

1. 用 package 所属 Git 根目录作为 monitor root；只读一次 `decision.md` 与 `spec.md`，提炼 `goal`、`chosenDirection`、`coreInvariants`、`nonGoals`、`requiredEvidence`、`requiredReviews`、`manualAcceptance`、`ownerDecisionBoundary` 八个 TARGET_BASELINE 字段。Decision 裁决方向，Spec 校准行为与 acceptance。
2. 调用 CLI `init` 创建 monitor 并复用或创建 package 级 observation store，再调用 `init-context`，从 stdin 写入 `{"targetTitle":"...","targetBaseline":{...}}`。CLI 创建只含固定 policy/baseline/identity/hash 的 context 文档和独立 runtime sidecar；同 ID 同快照幂等复用，身份或 hash 冲突时停止。Renderer 固定绑定 `127.0.0.1:43187`，启动或复用后在 workspace sidecar 原子记录 PID、instance ID 和启动时间。
3. 调用一次 `read-static`，把固定文档加载进当前 monitor chat并取得 snapshot hash；再调用 `seed-rollout-cursors`，把 monitor/target 的 canonical rollout cursor 初始化到当前完整行末尾，避免导入历史消息。正常 heartbeat 不再读取固定正文。
4. 读取 [`templates/automation-prompt.md`](templates/automation-prompt.md)，只替换 automation、workspace root、CLI path 和 snapshot hash placeholder。`*_JSON` 替换为不带外围引号的 JSON-escaped 字符串内容；`MONITOR_CLI_PATH_JSON` 使用当前已加载插件中的 CLI 绝对路径。
5. 同 ID automation 存在时先 view 并原地更新；不存在时创建。使用 heartbeat、destination thread、`targetThreadId=<当前 monitor>`、`RRULE:FREQ=MINUTELY;INTERVAL=<interval-minutes>`、ACTIVE，并保留既有 notification policy。
6. 再次 view automation，调用 CLI `read-cycle`，并验证 prompt 无 placeholder、staticRef hash/status、rollout cursor、`packageStatus`、`targetUpdates`、`observationDiff`、monitor/target/package/id 和 observations 一致，且输出不含 policy/baseline 正文。

完成标准：automation 已 ACTIVE；prompt 不携带固定正文或 mutable state，稳态只通过 CLI `read-cycle` / `write-cycle` 读写。

## 边界

- 页面分支不读取 Decision/Spec、不创建 sidecar；automation 分支仅在创建时读取一次 Decision/Spec。
- 运行期不再读取 Skill、Decision/Spec 或 baseline 正文；`read-cycle` 每轮只读 package 的 `.impl-package/state.json` 取得正式 Ticket/Gate 状态，并通过 Codex 数据库登记的两个 canonical rollout 增量补偿 active-turn Owner 输入与 target 的用户可见进展，不扫描子任务或任意 session。消息分类完成后才由 `write-cycle` 保存返回的下一 cursor，写回失败则下轮按 message ID 和 observation topic 幂等重放。
- observation 原地更新前，按 source、turn 和时间顺序结合同批前序消息、当前完整 observations 与 task 状态，明确 antecedent、主体、动作和范围；局部对象不扩大为整个类别，指代仍不明确时不改 confirmed observation、不授权 target 消息。
- `packageStatus` 是正式 Ticket/Gate 状态的唯一运行期 authority；`ticketPresentation` 复用 Renderer 的 readiness 与执行轨迹，提供“开发中/调研中/可启动/未开始”的 Owner 展示状态；`targetUpdates` 只解释当前动作。通知优先写展示状态，并同时保留正式状态；不得把“开发中”升级为正式验收。
- 一个 observation topic 只承载一个能被未来消息独立修改的决策轴；一条消息改变多个轴时分别新增或更新，正式 Ticket 状态不写入 observation。
- observations 归属于被监控 package，并在 package 级 canonical store 中跨 automation、monitor task 与 Attempt 累积；Attempt 切换时冻结旧集合供 Renderer 历史查看，heartbeat 始终读取当前累计全集，不受浮窗或 Ticket 视图选择影响。
- 每条 observation 使用 `kind=one-time|pattern`。Owner 明示绑定具体 Ticket、session、本次动作或一次性决策时直接判为 one-time，不得靠改写正文泛化；仅在没有明示实例边界时做替换测试，替换具体实例后仍应约束后续同类场景才是 pattern。混合消息拆开记录；pattern 使用稳定的条件、行为和边界，高置信时 confirmed、不确定时 candidate；one-time 保留具体对象、动作与完成条件。
- `ownerInputs` 只证明消息已读取；`observationDiff` 区分 observation 的新增、原地更新和删除，并返回 before/after。`write-cycle` 在确认 diff 前生成确定性报告，按 ID 稳定排序；成功后才确认，失败则回滚并在下轮重放。
- confirmed observation 要求 dry-run 时不向 target 发送消息。只有实际满足纠偏条件，且原因或拟发送全文不同于 runtime 的 `lastSimulationCorrection` 时，才把新模拟纠偏传给 `write-cycle`；同一纠偏持续存在时不重复，解除后写回 null，再出现时重新报告。
- 用户可见报告格式只由 `write-cycle.notification` 生成。heartbeat 最终逐字输出 `reportText`，不得重新组织、增加标题或追加总结；`shouldNotify=false` 时其值为 `DONT_NOTIFY`。工具调用前的 commentary 属于宿主进度信息，不是报告正文。
- evaluation 的 `progress` 写 target 当前事实、执行进展和必须处理的 blocker、finding、失败测试或验收缺口；`improvements` 只写不采纳也不影响当前 Ticket/Gate 收口的可选建议，没有则为空数组；`next` 只写处理动作，`owner` 只写确需 Owner 裁决的事项。通知沿用这四个字段，不创造未定义栏目；monitor、renderer、sidecar、automation 或 canonical target 的维护问题只进入独立 `monitorHealthDiff`。
- 每轮 `read-cycle` 以 workspace renderer sidecar 的 PID 加 `/api/health` instance ID 核对同一进程，不扫描进程列表；同时验证 canonical target，并只从明确的 `::created-thread{threadId="..."}` 识别 handoff successor。健康变化单独报告并在 `write-cycle` 确认，同一状态不重复；Renderer 仅当前开机周期 detached 常驻，不自动重启。
- handoff 后使用 `retarget --target-thread <明确 ID>` 原子换绑；它把 successor cursor 初始化到当前完整行末尾，保留 baseline、observations、evaluation 和其它 runtime。不得用标题或时间猜测 successor，也不得通过 `write-cycle` 隐式换绑。
- heartbeat 改由另一个 monitor task 承接时，先暂停 automation，再用 `rebind-monitor --monitor-thread <明确 ID>` 换绑并从新 task 当前行末开始读取，随后把同一 automation 的 `targetThreadId` 更新为新 monitor 后恢复；不得只移动 automation 回调而保留旧 monitor cursor。
- 真实兜底的 blocker 范围完全由 confirmed observation 决定，模板不另设授权类白名单。任何 steer 前必须按时间顺序结合最新 `ownerInputs`、`targetUpdates`、完整 observations 与 package 状态识别当前对话：idle、turn completed、blocked 或 notLoaded 状态本身不证明 blocker，讨论、澄清、问答或等待 Owner 回复时不得发送。确认符合 observation 条件后才向 target 发送一次幂等消息。
- observation 只记录直接改变目标任务授权、执行、验收或 Owner 决策边界的纠偏；监控模板、CLI、dashboard、prompt 或 observation 机制的调试反馈不进入目标任务 sidecar。
- 不修改 implementation package、Decision/Spec、Ticket、Evidence、Checkpoint、State 或 Gate。
- 同一 ID 优先更新，避免重复 automation；不同 package 使用独立 observation store，避免共享写冲突。
- 本 Skill 不迁移 v1 sidecar；当前运行中的旧 automation 由 Owner 另行一次性切换。

静态 policy 更新时，先暂停对应 automation；旧 runtime 首次升级时先调用 `seed-rollout-cursors`，再调用 `refresh-context-policy`。后者校验旧 snapshot hash，只替换固定 context，保留独立 runtime、monitor evaluation 和 observations；随后调用一次 `read-static`，把新 hash 写入短 prompt后恢复 automation。

旧的 per-automation observation stores 迁移时，先暂停 automation，再用 `migrate-package-observations` 一次性写入累计 current store 与历史 Attempt 快照；命令幂等且内容冲突时停止，旧文件保留为只读证据。

## 输出

未启用 automation 时只报告页面 URL。启用后再报告 automation ID、monitor/target、频率、monitor/observation/context/runtime 路径、ACTIVE 与 CLI `read-cycle` 验证结果。
