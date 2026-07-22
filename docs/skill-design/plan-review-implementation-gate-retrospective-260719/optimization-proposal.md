# 优化计划：在 Bundle Plan 批准前增加独立 Plan Review

## 1. 目标

本次优化只解决一个问题：Impl-Package 的 bundle plan 在进入 owner approval 前，增加一次由独立 subagent 执行的工程计划审查，降低主 session 自行判断“计划已经够好”而漏掉复杂风险的概率。

现有 Impl-Package canonical model、D/S/P revision、Composition、owner approval、execution-preflight 和 completion gate 已经能够管理计划与执行。本次不新增 receipt schema、bundle identity、provenance 链、contract version 或第二套状态机；agent 继续理解计划语义，现有 canonical 只承担兜底、授权和恢复引导。

## 2. 核心原则

1. **相信 agent 的工程判断。** 提供独立 reviewer、审查视角和升级工具，不把复杂工程判断翻译成大量机器字段或固定打分。
2. **每个 bundle plan 都有一次真正的独立 review。** review 不能由产出计划的主 session 自问自答；由 fresh-context subagent 阅读当前计划及必要 contract 后给出判断。
3. **审查深度由风险决定。** 独立 reviewer 可以快速确认计划已足够，也可以在发现 material risk 时进入完整 `plan-review`；简单计划不被迫走完整仪式。
4. **主 session 只能加严。** 主 session 可以要求更深审查，但不能把 reviewer 的“需要修改”或“需要完整审查”自行降级为通过。
5. **复用现有能力。** 继续使用 `plan-review` 已有 ledger、工程判断和 guarded Apply，不建立平行 reviewer、rubric、findings registry 或 durable tracking chain。

## 3. 最小工作流

```text
Impl-Package bundle plan ready
        ↓
impl-planning 以确切名称编排 plan-review 的 bundle-admission mode
        ↓
独立 reviewer 判断
  ├─ ready：计划可进入 owner approval
  ├─ full review：发现 material risk，继续现有完整 plan-review
  └─ revise / unavailable：暂停 approval，修订或重试
        ↓
owner approval
        ↓
现有 execution-preflight 与实施流程
```

这只是现有计划生命周期中的一层 review gate，不新增持久化生命周期状态。`ready`、`full review`、`revise` 和 `unavailable` 是 agent 的审查结论与路由语言，不进入 Impl-Package canonical schema。

## 4. 独立 reviewer 的判断边界

只有 `impl-planning` 以确切名称选择时，`plan-review` 才进入 bundle-admission mode；用户直接调用 `$plan-review` 的既有完整审查、ledger 和 guarded Apply 合同不变。admission mode 启动 fresh subagent，向它提供当前 plan package、必要的 Decision/Spec contract、Composition 和审查目标，但不提供主 session 预写的结论或期望 verdict。它首先判断计划是否足以安全实施，并重点查看 Scope、Architecture、Code Quality、Tests、Performance 中实际相关的部分。

出现下列 material signal 时，reviewer 应继续现有完整 `plan-review`，而不是把信号机械映射为分数：跨模块或跨系统 contract 变化；权限、资金、外部 mutation、通知或不可逆动作；并发、锁、CAS、重复执行、partial success、unknown outcome、恢复或迁移；错误路径、rollback、operator signal 或 acceptance oracle 存在多种合理解释；mock 可能遮蔽真实协议边界。

没有 material signal 时，reviewer 可以用简短、证据化的说明判定 `ready`，无需创建 ledger、formal findings、固定四张表或结构化 manifest。出现 material signal 时输出 `full review` 并转入现有完整 `plan-review` workflow，由该 workflow 决定 ledger、Outside Voice、findings 和 owner decision；admission mode 本身不 Apply。计划材料不足时输出 `revise`；subagent 无法启动或无法形成独立判断时输出 `unavailable`，主 session 不得模拟独立 review。

reviewer 不替 owner 决定产品意图、风险偏好、外部 contract 或不可逆选择。遇到这些问题时，应明确指出 owner decision，而不是自行补完。

## 5. Gate 行为

`impl-planning` 负责在请求 owner approval 前显式编排这次 review，并在当前会话或计划交付中保留足以让 owner 看懂的 review 结论。只有 `ready`，或完整 `plan-review` 已按其现有合同收敛，才能请求 owner approval。

`revise` 必须回到对应 owning skill 修改计划、Ticket 或 DAG 后重审。`unavailable` 必须重试或暂停/取消该 approval；owner 可以决定等待、重试或取消，但不能把它改写成 `ready` 或在没有独立结论时放行 approval。

计划发生实质变化后应重新 review。materiality 由 agent 根据变化是否影响执行策略、contract、ownership、依赖、acceptance、风险或验证方式判断；纯格式、链接、投影或不改变含义的勘误不需要制造新的 revision/identity 机制。存在疑义时采取重审这一较安全的动作。

`execution-preflight` 不新增 readiness analyzer、receipt validator 或 review schema parser。它继续验证现有批准、revision freshness、HITL 与执行边界；plan review 是否已经完成由上游 `impl-planning` 的编排合同保证。

## 6. 实施范围

### Slice A：为 `plan-review` 增加轻量 admission 判断（已实施）

修改以下文件：

- `skills/plan-review/SKILL.md`：增加仅供确切 `impl-planning` 编排选择的 bundle-admission mode；保留现有 direct invocation 的完整 workflow，不放宽 explicit-only invocation gate。
- `skills/plan-review/references/subagent-prompts.md`：增加只读 admission prompt，要求返回 `ready | full review | revise | unavailable`、证据和 material signal；不泄漏主 session 结论。
- `skills/plan-review/references/final-report.md`：增加 admission 的短报告格式，并明确它不是 guarded Apply、manifest 或跨 session receipt。
- `skills/plan-review/evals/evals.json`：增加低风险 ready、高风险升级 full、缺 owner decision revise、subagent unavailable 四个 workflow eval；保留现有 explicit-only 正反例。

完整审查继续复用当前 ledger 和 guarded Apply 合同；轻量通过不新增 manifest、持久 receipt 或 ledger 字段。`review_ledger.py` 与其 schema 不因 admission mode 扩展。

### Slice B：把 review 接到 `impl-planning` 的 owner approval 之前（已实施）

修改以下文件：

- `skills/impl-package/impl-planning/SKILL.md`：在 earned Ticket/DAG 联合校验与 owner approval 之间插入 admission；`ready-for-review` 仍只表示 bundle 齐备，不能被表述成已审查。只有 `ready` 或完整 review 已收敛才可请求 owner approval。
- `skills/impl-package/impl-planning/assets/templates/plan.md`：在“执行尝试产物交接”增加人类可读的“计划审查交接”占位，仅写结论、理由和下一动作，不写 runtime state、hash 或 receipt。
- `skills/impl-package/impl-planning/evals/evals.json`：为 tickets-only、dag-only、material plan change 与 unavailable 分别增加 admission 期望；验证主 session 只能升级、不能把 `full review`/`revise`/`unavailable` 变为可批准状态。

主 session 可以升级到完整审查，但不能自行覆盖 subagent 的修订或升级结论。Ticket/DAG 的既有联合校验、owner 一次性 approval、publication 与 execution-preflight 顺序不变。

### Slice C：清理迁移残留（本分支已完成）

已删除已经被本仓 `plan-review` 吸收的旧 skill 实体及其 registry、installer test 和活跃文档引用。本计划不保留 alias、兼容转发或双入口；新编排只使用 `plan-review`。该清理不再是 Slice A/B 的依赖，也不需要改动 Impl-Package。

### Slice D：保持消费者稳定（已实施）

更新 `skills/impl-package/SKILL.md` 与必要 handoff 文案，说明 plan review 位于 owner approval 之前。禁止修改 `skills/impl-package/references/impl-package-state-schema.md`、`references/impl-package-composition-contract.md`、`assets/templates/revision-bindings.json`、`scripts/impl_package_state.py`、`execution-preflight/SKILL.md`、`dev-with-track/SKILL.md`；这些消费者继续只依赖现有 approval、revision freshness、HITL 与 execution gate。

## 7. 验证场景

1. 简单、单模块且无 material risk 的 bundle 由 fresh subagent 给出有依据的 `ready`，随后可以请求 owner approval，不生成额外 schema 工件。
2. 涉及外部 mutation、恢复歧义或跨系统 contract 的 bundle 被升级到完整 `plan-review`，主 session 不能降级。
3. reviewer 指出计划缺少 acceptance oracle 或 owner decision 时，approval 暂停，owning skill 修订后重新 review。
4. subagent 无法启动时，主 session 不得自问自答冒充独立 review；输出 `unavailable` 并重试、暂停或取消 approval，不能由 owner 把它直接放行。
5. review 后计划发生影响 contract、执行策略或验证方式的实质变化时重新 review；纯格式勘误不触发额外仪式。
6. 已批准计划进入 execution-preflight 时继续使用现有 canonical contract，不要求新的 receipt、bundle hash 或 migration。
7. skill discovery、registry 和 installer tests 中只保留 `plan-review` 入口，旧实体与活跃引用清零。

每次实现后运行：

```text
python -m unittest skills.plan-review.scripts.test_review_ledger
powershell -ExecutionPolicy Bypass -File tests/install.ps1
powershell -ExecutionPolicy Bypass -File skills/import-third-party-skill/scripts/test-import-third-party-skill.ps1
python -m json.tool skills/plan-review/evals/evals.json
python -m json.tool skills/impl-package/impl-planning/evals/evals.json
```

再用 diff 断言确认 Slice D 禁止的 canonical 文件为零改动，并人工执行四个 admission eval 的正负场景；eval 证明编排和 agent 判断，ledger/installer tests 只证明未破坏既有边界。

## 8. 完成定义

本次机制改造只有在以下条件同时满足后才算 closed：`plan-review` 能由 fresh subagent 进行轻量判断并按风险升级；`impl-planning` 在 owner approval 前显式调用它；主 session 不能自行降级独立结论；subagent 不可用时不会伪造通过；旧入口和物理实体已经清理；相关 eval 与 installer tests 通过；Impl-Package canonical schema 和既有 execution gate 未被扩展。

本文件的 Slice A 至 Slice D 已实施。admission 不扩展 canonical schema，完整 review、owner approval、execution-preflight 与 execution gate 继续各自承担原有职责。
