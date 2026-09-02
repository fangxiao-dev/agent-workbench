---
name: monitor-progress
description: 打开 Impl-Package 实时进度页面，并在用户确认后从统一模板创建或更新只读主控监控 automation；调用者提供任务包路径和目标会话 ID。
disable-model-invocation: true
---

# Monitor Progress

默认打开目标任务包的实时进度页面，再询问是否启用 automation 评价。稳定数据合同和落盘由 [`../../scripts/monitor_progress.py`](../../scripts/monitor_progress.py) 承担；本 Skill 只负责编排页面、用户选择、一次性 baseline 和 heartbeat。

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
2. 调用 CLI `init`，创建 v2 monitor 与 observation sidecar；同 ID 已存在且身份完全一致时幂等复用，身份冲突时停止。
3. 读取 [`templates/automation-prompt.md`](templates/automation-prompt.md)，替换全部 placeholder。`*_JSON` 替换为不带外围引号的 JSON-escaped 字符串内容，`TARGET_BASELINE_JSON` 替换为完整 JSON object；`MONITOR_CLI_PATH_JSON` 使用当前已加载插件中的 CLI 绝对路径。
4. 同 ID automation 存在时先 view 并原地更新；不存在时创建。使用 heartbeat、destination thread、`targetThreadId=<当前 monitor>`、`RRULE:FREQ=MINUTELY;INTERVAL=<interval-minutes>`、ACTIVE，并保留既有 notification policy。
5. 再次 view automation，调用 CLI `read`，并验证 prompt 无 placeholder、monitor/target/package/id 一致。

完成标准：automation 已 ACTIVE；runtime 只通过 CLI 读取或写入 v2 monitor 状态。

## 边界

- 页面分支不读取 Decision/Spec、不创建 sidecar；automation 分支仅在创建时读取一次 Decision/Spec。
- 运行期按模板不再读取 Skill、Decision/Spec、package、repo 或 rollout，且不手写 monitor JSON。
- 不向 target 发送消息，不创建或控制其 worker，不运行其代码、测试、数据库、浏览器或验证脚本。
- 不修改 implementation package、Decision/Spec、Ticket、Evidence、Checkpoint、State 或 Gate。
- 同一 ID 优先更新，避免重复 automation；不同任务使用独立 observation sidecar，避免共享写冲突。
- 本 Skill 不迁移 v1 sidecar；当前运行中的旧 automation 由 Owner 另行一次性切换。

## 输出

未启用 automation 时只报告页面 URL。启用后再报告 automation ID、monitor/target、频率、monitor/observation 路径、ACTIVE 与 CLI read 验证结果。
