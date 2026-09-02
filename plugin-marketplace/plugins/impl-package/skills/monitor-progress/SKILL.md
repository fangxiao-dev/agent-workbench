---
name: monitor-progress
description: 从统一模板创建或更新一个只读 Impl-Package 主控监控 automation；调用者提供任务包路径、监控会话 ID 和目标会话 ID。
disable-model-invocation: true
---

# Monitor Progress

把 [`templates/automation-prompt.md`](templates/automation-prompt.md) 实例化为一个 ACTIVE heartbeat。模板拥有全部运行期评价规则；本 Skill 只负责创建时的参数、一次性 baseline 和落盘入口。

## 输入

必需：

- `package`：implementation package 绝对路径；
- `monitor`：承接 heartbeat 结果的 Codex thread ID；
- `target`：被评价的主控 Codex thread ID。

接受裸 UUID 或 `codex://threads/<id>`，写入前统一为裸 ID。可选输入为 `id`、`name`、`target-title`、`interval-minutes`；默认值：

- `id=monitor-progress-<target-id 后 8 位>`；
- `name=Impl-Package 监控 · <package 目录名>`；
- `target-title` 从 `read_thread(target)` 取得；
- `interval-minutes=20`。

缺少任一必需输入时只询问缺失值，不猜测 thread。

## 创建

1. 只读确认 package 目录、`decision.md`、`spec.md` 与两个 thread 可访问。用 package 所属 Git 根目录作为 dashboard root；创建过程不读取 package 的运行状态、Ticket、Evidence 或 rollout。
2. 只读一次 `decision.md` 与 `spec.md`，提炼 `goal`、`chosenDirection`、`coreInvariants`、`nonGoals`、`requiredEvidence`、`requiredReviews`、`manualAcceptance`、`ownerDecisionBoundary` 八个 `TARGET_BASELINE` 字段。Decision 裁决方向，Spec 校准行为与 acceptance；不得补写未声明的产品决定。
3. 替换模板中的全部 `{{PLACEHOLDER}}`；`*_JSON` 替换为不带外围引号的 JSON-escaped 字符串内容，`TARGET_BASELINE_JSON` 替换为完整 JSON object。生成：
   - dashboard：`<root>/.progress-record/codex-progress-dashboard/monitors/<id>.json`；
   - Owner observations：`<root>/.progress-record/codex-progress-dashboard/observations/<id>.json`。
4. 初始化 dashboard 的固定 9 字段，`level=attention`、`latestAssistantAt=null`、summary 为“监控已创建，等待首次评价；Owner 暂无待决事项。”；observation ledger 初始化为 `version=1`、当前 automationId、UTC updatedAt、空 observations。它们属于监控状态，不属于 implementation package。
5. 检查同 ID automation：存在时先 view 并原地更新；不存在时创建。使用 heartbeat、destination thread、`targetThreadId=monitor`、`RRULE:FREQ=MINUTELY;INTERVAL=<interval-minutes>`、ACTIVE，并保留既有 notification policy。
6. 再次 view automation，并验证 prompt 无未替换 placeholder、两个 JSON 可解析、dashboard 恰有 9 字段、target/monitor/package/id 一致。

完成标准：automation 已 ACTIVE，下一轮能从两个 thread 回溯 `userMessage`，且写入范围只有 automation、dashboard 和 observation sidecar。

## 边界

- 创建阶段仅对 package 读取一次 Decision/Spec；运行期按模板不再读取 Skill、Decision/Spec、package、repo 或 rollout。
- 不向 target 发送消息，不创建或控制其 worker，不运行其代码、测试、数据库、浏览器或验证脚本。
- 不修改 implementation package、Decision/Spec、Ticket、Evidence、Checkpoint、State 或 Gate。
- 同一 ID 优先更新，避免重复 automation；不同任务使用独立 observation sidecar，避免共享写冲突。
- 本 Skill 不负责修改模板内的评价政策；政策升级应直接更新模板版本。

## 输出

只报告 automation ID、monitor/target、频率、dashboard/observation 路径、ACTIVE 验证结果，以及仍缺失的输入或失败点。
