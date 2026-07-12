# Worker Prompts

派发实现或 review worker 时读本文件。

## 实现 Worker Prompt

```markdown
你在为 <implementation package> 实现 Task <ID>。

Workspace：
- <path>

Tracking：
- <standalone / dev-with-track>
- Progress ledger：<tasks/Tn-progress.md 或 N/A>
- Handoff ledger：<tasks/Tn-handoff.md 或 N/A>

Implementation 目标：
- <摘要>

你的 ownership：
- Primary owned files/modules：<正常写入范围>
- Conditional seam files/modules：<文件/模块 + 允许编辑的精确条件，或 none>
- Forbidden files/modules：<禁改>

契约：
- Input：<你消费的 DTO/API/props>
- Output：<你产出的 DTO/API/行为>
- Acceptance target：<contributes-to 或 enables 的 ticket-id:AC-id / spec:AC-id>
- Seam：<none 或 seam-id；若非 none，seam execution owner>

要求：
- <验收要点>

要跑的测试：
- <聚焦命令>

规则：
- 这个代码库里不止你一个人在工作。
- 不要回滚别人做的改动。
- 除非点名的 conditional seam 条件发生，不要在 primary ownership 之外编辑。
- 需要 forbidden 或未列出的编辑时，返回 NEEDS_SEAM，不要直接改。
- 计划内的跨任务依赖上报 NEEDS_SEAM，不是 BLOCKED。

返回：
- status：DONE / DONE_WITH_CONCERNS / NEEDS_SEAM / BLOCKED
- 改动的文件
- 跑过的测试和结果
- 编辑过的 conditional seam 文件及原因
- 非属地 seam 需求，已知时写明 seam execution owner
- 是否需要人类操作：yes/no
- 剩余风险
```

worker 返回状态或证据、且存在 `dev-with-track` progress ledger 时，更新 `tasks/Tn-progress.md`。只在任务需要向另一个 session、agent 或 worker 独立交接时创建 `tasks/Tn-handoff.md`。

## 状态处理

- `DONE`：进入任务 spec review。
- `DONE_WITH_CONCERNS`：review 前先读 concern；正确性或 scope concern 先解决。
- `NEEDS_SEAM`：main session 处理 seam、等待点名的任务 owner、或调整 ownership 后继续。用于计划内依赖、非属地文件、因另一任务未落地导致的广域测试失败、以及不需要人类判断的集成接线。
- `BLOCKED`：补上下文、拆任务、换模型/worker，或在计划有误时升级。只用于需要上下文、权限、数据、计划修正或人类决策的情况。

不要在不改变致因上下文的情况下让同一个 worker 原样重试。

（worker 返回状态到 DAG 板状态的映射见 `references/dag-and-ownership.md`。）

## 状态示例

预期内 seam：

```markdown
status: NEEDS_SEAM
seam execution owner: T3 <本地持久化任务>
reason: 聚焦 service 测试通过，但集成回读依赖 T3 所属的本地持久化，该任务尚未落地
human action required: no
```

真正的 blocker：

```markdown
status: BLOCKED
reason: 任务需要 mutate 真实外部系统做 smoke，但缺少 owner 授权
human action required: yes
```

## Review Worker Prompts

任务 spec reviewer：

```markdown
对照任务契约 review Task <ID>。

检查：
- 要求的行为已实现；
- 没有新增非属地 scope；
- 承诺的测试存在或已报告；
- output contract 与冻结的共享契约一致。

返回 APPROVED 或 NEEDS_CHANGES，附具体 finding。
```

任务质量 reviewer：

```markdown
Review Task <ID> 的实现质量。

检查：
- 可维护性；
- 是否符合本地模式；
- 风险行为的测试覆盖；
- 不必要的抽象或耦合；
- 隐藏的跨任务假设。

返回 APPROVED 或 NEEDS_CHANGES，附具体 finding。
```

Implementation-level review handoff：

```markdown
调用 `module-review` 的 Spec 轴 review 集成后的完整 implementation，不是单个任务。

输入：
- 固定 comparison point（commit、commit range 或固定 diff）；
- package spec/plan；
- 相关 Approved tickets 与 DAG；
- DAG、progress、handoff 或 tracking 产物；
- 验证证据。

按 module-review Spec 轴既有契约返回结论；不要在 create-task-dag 内另定义
whole-slice 或 contract-drift 检查表。
```
