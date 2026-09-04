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
2. 调用 CLI `init` 创建 monitor 与 observation sidecar，再调用 `init-context`，从 stdin 写入 `{"targetTitle":"...","targetBaseline":{...}}`。CLI 创建只含固定 policy/baseline/identity/hash 的 context 文档和独立 runtime sidecar；同 ID 同快照幂等复用，身份或 hash 冲突时停止。Renderer 固定绑定 `127.0.0.1:43187`，启动或复用后在 workspace sidecar 原子记录 PID、instance ID 和启动时间。
3. 调用一次 `read-static`，把固定文档加载进当前 monitor chat并取得 snapshot hash；再调用 `seed-rollout-cursors`，把 monitor/target 的 canonical rollout cursor 初始化到当前完整行末尾，避免导入历史消息。正常 heartbeat 不再读取固定正文。
4. 读取 [`templates/automation-prompt.md`](templates/automation-prompt.md)，只替换 automation、workspace root、CLI path 和 snapshot hash placeholder。`*_JSON` 替换为不带外围引号的 JSON-escaped 字符串内容；`MONITOR_CLI_PATH_JSON` 使用当前已加载插件中的 CLI 绝对路径。
5. 同 ID automation 存在时先 view 并原地更新；不存在时创建。使用 heartbeat、destination thread、`targetThreadId=<当前 monitor>`、`RRULE:FREQ=MINUTELY;INTERVAL=<interval-minutes>`、ACTIVE，并保留既有 notification policy。
6. 再次 view automation，调用 CLI `read-cycle`，并验证 prompt 无 placeholder、staticRef hash/status、rollout cursor、`observationDiff`、monitor/target/package/id 和 observations 一致，且输出不含 policy/baseline 正文。

完成标准：automation 已 ACTIVE；prompt 不携带固定正文或 mutable state，稳态只通过 CLI `read-cycle` / `write-cycle` 读写。

## 边界

- 页面分支不读取 Decision/Spec、不创建 sidecar；automation 分支仅在创建时读取一次 Decision/Spec。
- 运行期按模板不再读取 Skill、Decision/Spec、package 或 repo；`read-cycle` 只通过 Codex 数据库登记的两个 canonical rollout 增量补偿 active-turn Owner 输入，不扫描子任务或任意 session。消息分类完成后才由 `write-cycle` 保存返回的下一 cursor，写回失败则下轮按 message ID 和 observation topic 幂等重放。
- observation 原地更新前，按 source、turn 和时间顺序结合同批前序消息、当前完整 observations 与 task 状态，明确 antecedent、主体、动作和范围；局部对象不扩大为整个类别，指代仍不明确时不改 confirmed observation、不授权 target 消息。
- `ownerInputs` 只证明消息已读取；`observationDiff` 区分 observation 的新增、原地更新和删除。diff 非空时下一次 automation 报告必须逐条写出变化类型、ID、topic 和完整当前内容，即使任务进度没有其它变化；`write-cycle` 成功后才确认，失败则下轮重放。
- confirmed observation 要求 dry-run 时不向 target 发送消息。只有实际满足纠偏条件，且原因或拟发送全文不同于 runtime 的 `lastSimulationCorrection` 时，报告“模拟纠偏（未发送）”、触发原因和拟发送全文；同一内容持续存在时不重复，无触发时写回 null，解除后再出现可重新报告。
- 每轮 `read-cycle` 以 workspace renderer sidecar 的 PID 加 `/api/health` instance ID 核对同一进程，不扫描进程列表。`rendererDiff` 变为 dead、missing 或 mismatch 时报告 PID、固定端口和页面不可用影响，并明确未自动重启；同一状态在 `write-cycle` 确认后不重复。Renderer 仅当前开机周期 detached 常驻，不使用 Docker、Task Scheduler 或 heartbeat 自动重启。
- 只有某条 confirmed observation 明确授权且当前事实符合其条件时，才向 target 发送一次幂等消息；其余情况不干预，不创建或控制 worker，不运行目标代码、测试、数据库、浏览器或验证脚本。
- observation 只记录直接改变目标任务授权、执行、验收或 Owner 决策边界的纠偏；监控模板、CLI、dashboard、prompt 或 observation 机制的调试反馈不进入目标任务 sidecar。
- 不修改 implementation package、Decision/Spec、Ticket、Evidence、Checkpoint、State 或 Gate。
- 同一 ID 优先更新，避免重复 automation；不同任务使用独立 observation sidecar，避免共享写冲突。
- 本 Skill 不迁移 v1 sidecar；当前运行中的旧 automation 由 Owner 另行一次性切换。

静态 policy 更新时，先暂停对应 automation；旧 runtime 首次升级时先调用 `seed-rollout-cursors`，再调用 `refresh-context-policy`。后者校验旧 snapshot hash，只替换固定 context，保留独立 runtime、monitor evaluation 和 observations；随后调用一次 `read-static`，把新 hash 写入短 prompt后恢复 automation。

## 输出

未启用 automation 时只报告页面 URL。启用后再报告 automation ID、monitor/target、频率、monitor/observation/context/runtime 路径、ACTIVE 与 CLI `read-cycle` 验证结果。
