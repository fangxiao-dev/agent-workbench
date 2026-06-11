---
name: handoff-new-session
description: Use when the user wants to hand off or migrate work to a new session or thread — summarize this session into a handoff, save context/progress/pitfalls to disk before switching conversations (总结落盘当前进度、坑、后续), generate a continuation prompt for a fresh session, fork or continue in a new Codex Desktop thread, or carry collaboration preferences across sessions.
---

# Handoff New Session

## 目的

把当前会话的工作交接给新会话：用精炼的 handoff 保留真正影响后续执行的上下文——当前状态、已验证事实、未完成边界，以及用户明确给过的协作偏好。

不要路由到这里：单纯总结一份文档、把 bug 写成 issue、新写一个 skill。

## 前置环境检查

线程操作只在 Codex Desktop host 可执行（`create_thread` / `fork_thread`）。在其他 host 上不要调用线程工具：生成交接产物（handoff 文件 + chat 内 continuation prompt），手动移交给用户去开新会话。

## 选择操作

| 用户意图 | 使用 | 环境 | 上下文行为 |
| --- | --- | --- | --- |
| 默认：把工作交给新 thread 继续 | `create_thread`（仅 Codex） | 当前项目 local environment | 不继承旧对话历史，只使用 handoff prompt |
| 用户明确要求继承会话历史 / fork 当前 session | `fork_thread`（仅 Codex） | `{ type: "same-directory" }` | 复制源 thread 已完成的历史 |
| 用户明确要求新 worktree 隔离 | `create_thread` 或 `fork_thread` | worktree environment | 按 host 工具能力和用户要求创建隔离环境 |
| 非 Codex host | 手动移交 | — | handoff 文件 + continuation prompt，由用户自己开新会话 |

注意：

- fork 只包含已完成的历史；源 thread 正在运行的当前 turn 不会被复制，fork 后也不再同步。
- same-directory 表示子 thread 使用当前目录，不是新建 worktree。
- 如果无法用 `create_thread` 创建干净新会话，不要自动 fallback 到 `fork_thread`；先说明阻塞并返回 handoff 文件与 continuation prompt，除非用户明确要求继承历史。

## 轻量 vs 耐久

满足任一条即为耐久交接，必须落盘 handoff 文件并走 quality gate：

- 任务跨天，或 child 将长时间无人值守推进。
- 涉及外部状态：issue/PR/comment、邮件、外部系统等已发生或待发生的动作。
- 多 agent 或多 worktree 分工。
- 存在未完成验证或已知风险需要 child 接力。

否则为轻量交接：chat 里一段短 continuation prompt 即可，不强制落盘、不强制 gate。

自动 handoff 触发点见 `rules/auto-handoff-triggers.md`。长流程 continuation prompt 必须在 Required Rule Context 中显式列出该 rule 路径，让 child session 自行读取规则细节。

## 交接产物

状态一律从实际 workspace 采集（git 命令输出），不靠对话记忆。

1. **handoff 文件**（耐久必须）：优先使用 rolling handoff：`docs/exchange/handoffs/handoff-<slug>-current.md`。slug 取自工作流，2–5 个小写连字符词（如 `lark-webhook-debug`），不要用 `session` 这类泛词。结构按 `templates/durable-handoff.md`。
2. **continuation prompt**（轻量、耐久都要）：文件写完后在 chat 直接返回，绝不写成第二个文件。结构见模板第二部分。

### Rolling vs Timestamped

默认维护一个 rolling handoff，而不是每个 checkpoint 都新增时间戳文件。rolling handoff 是继续工作的唯一入口，应该覆盖更新到最新可恢复状态，避免 child session 读到过期入口。

仅在以下情况额外写时间戳归档快照：用户明确要求保留历史；需要冻结审计证据；要交接给多个独立 child 且它们必须从不同时间点恢复；或某阶段完成后后续会长期分叉。归档命名为 `docs/exchange/handoffs/handoff-<slug>-MMDDhhmm.md`。如果写了归档，rolling handoff 顶部要写明 `Supersedes` / `Archived snapshot` 关系，并指向最新入口。

如果某个工作流已经积累了多个过期 timestamped handoff，先征得用户同意再整理；整理时保留/创建一个 `handoff-<slug>-current.md`，删除或归档旧入口，确保目录里不会出现多个看起来都可继续的同类 handoff。

涉及 worktree 或 branch 集成的交接，先读 `rules/worktree-handoff.md` 再写 Git 相关内容。

长流程自动交接时，把本 skill 的 `SKILL.md` 也作为 continuation prompt 的必读文件传给 child。这样 child 后续需要再次 handoff 时，会加载同一套规则，而不是只依赖本次 prompt 摘要。

长流程自动交接时，也把 `rules/auto-handoff-triggers.md` 作为 continuation prompt 的 Required Rule Context 传给 child。`SKILL.md` 只做规则索引；触发细节放在 rule 文件中。

## 耐久交接 Checkpoint

按这个顺序收口——commit 在写 handoff 之前，保证 handoff 出生即新鲜：

1. 确认当前要求的 gate 已通过，或明确写出未验证项。
2. 更新进度记录、外部 issue/PR/comment 状态和关键决策。
3. commit 当前 checkpoint；不提交则在 handoff 里明确说明原因。
4. 读取 fresh 状态：`git status --short --branch`、`git log -1 --oneline`。
5. 用 fresh 状态刷新 rolling handoff；只有符合归档条件时才额外写 timestamped snapshot。
6. 起草 continuation prompt；读 `rules/reviewer-input.md` 组织审核材料（含 prompt 草稿），让审核员 subagent 按 `rules/logger-handoff-quality-gate.md` 同审 handoff 与 prompt 草稿；按意见修改。
7. 创建新会话（prompt 用审核通过的草稿原样发送），或按前置环境检查的结果手动移交。
8. 新会话启动后按 host 能力处理首条进度更新：
   - Codex `create_thread` 新 thread 目前不能稳定作为可阻塞 IPC 使用：不要把 child 设计成“等 parent ACK 才继续”。child prompt 必须要求首条回复是 **First Progress Update**，发出后继续自动执行，直到下一个 handoff trigger、明确 blocker、plan 完成且 closure 收口、或 owner 要求停止。
   - 如果 host 提供可读取完整消息、可发送 follow-up、可等待的 child-session 控制能力，parent 可以做一次非阻塞纠偏：读取首条进度更新，核对 intent，不符则纠正一次；纠正后 child 仍应继续推进。
   - subagent 与新 Codex thread 不同：`multi_agent` worker/reviewer 可以 `wait` / `send_input`，适合阻塞式审核、实现和质量 gate。

## Child Prompt 必填内容

Child prompt 定规则和索引；**事实只住在 handoff 文件里，prompt 不复述 handoff 内容**。长流程 prompt 要短，目标是启动一个 orchestration runner，而不是把 handoff 重新写一遍，也不是让 child 一次性生成 closure report。一般控制在 10–25 行；超过这个范围时，优先把细节放进 rolling handoff / plan / issue，而不是塞进 prompt。

结构按 `templates/durable-handoff.md` 第二部分，至少包含：

- Role & Mission：接手什么工作流、本轮要推进到哪里。mission 必须可执行（以 rolling handoff 的 Next Action 为准），不能是“验证后等待”。
- Mode：明确 child 是 **orchestration runner**：先发一条短 progress update，说明会自动推进和如何使用 subagent，然后继续执行。不要把第一条可见回复当最终答复。
- Delegation authorization：必须在 prompt 中显式写出“主 session / 新 session 关注调度和 seaming，尽量派用 subagent 执行单个任务”。这是 owner 给 orchestration runner 的授权，不要只放在 handoff 或 skill 文件里。
- Handoff triggers：必须在 prompt 中显式写出“交接触发点：session context auto compact 了，或者自行识别到的大 gate”。这是 child 何时刷新 handoff / create next session 的执行条件，不要只引用 rule 文件。
- 执行规则（四条标准文本，原样复制进 prompt）：
  1. 先验证 `git status --short --branch` / `git log -1 --oneline` 与 handoff 一致。
  2. 以 rolling handoff 的 Next Action 为准持续推进，不要只确认状态后停止。
  3. 持续执行直到：下一个 handoff trigger、明确 blocker、plan 完成且 closure 收口、或 owner 要求停止。
  4. 如果 plan 已完成本地实现，进入 closure orchestration：列出仍需 owner 授权的外部动作，准备但不执行 push/PR/issue/merge（如起草 PR 描述、issue 更新文案、merge 清单），向 owner 请求下一步授权。不要发明新实现任务。
- Hard guardrails：最关键的 2–4 条硬护栏（如 push/PR/merge 禁令、subagent 分工）。安全关键规则不依赖 child 先读完文件才生效，必须留在 prompt 里。
- Required skill context / Required rule context / Required files：本 skill、`rules/auto-handoff-triggers.md`、rolling handoff、计划文档等索引。rolling handoff 是唯一事实源。
- First action：先读本 skill 和 auto-handoff rule，再验证 workspace；最多附一行 HEAD 校验和防漂移，不复制 handoff 的事实段；动手前确认 handoff 的 Open Issues / Not Completed / Next Action。
- First Progress Update Contract（长流程自动交接必填）：要求 child 第一条**可见更新**是进度更新，不是最终答复。内容只需包含 autonomy intent 和 subagent/orchestration intent 两个核心判断，可附 verified state；不要在这条更新里产出 PR body、issue 文案、closure packet 等 deliverables。除非验证失败、遇到 blocker、或 owner 明确要求等待，否则发出后继续自动推进。

避免在 continuation prompt 里放这些内容：
- 完整 closure checklist、PR body、issue comment、merge checklist；这些应该由 child 从 handoff / plan 推导或写入 closure packet。
- 大量支持文件和旧 issue 文件；只列 rolling handoff、orchestration plan、必要 skill/rule。其他文件让 child 按 Next Action 自行发现。
- 具体完成状态、gate 结果、外部状态、ahead/behind 数字；这些是 handoff 事实。

轻量交接可用短 prompt：

```text
你正在接手一个已有任务。以这条 handoff 为当前事实，先确认 workspace 状态，然后继续：<具体下一步>。
```

## Collaboration Contract

协作偏好要显式继承，尤其是长任务、多 agent、worktree、提交和验证策略。

- Explicit user preferences carry forward.
  - 例子：用户说过“主线程主要做调度和验收，implementation 尽量交给 subagent”，child prompt 里要写成当前执行规则。
- Inferred behavior must be labeled as inferred.
  - 例子：旧 session 经常先跑测试再汇报但用户没明确要求，写成“inferred / pending confirmation：继续在汇报前做 focused verification”。
- One-time permissions do not become standing permissions.
  - 例子：用户批准“这次在 #9/#10/#11 前提交 checkpoint”，只能说明这个 checkpoint 已提交，不能告诉 child 以后可以自由提交。

Subagent 偏好要写清所有权边界，而不只是“可以用 subagent”：worker 实现边界清晰的任务，reviewer 做 spec/quality review，main session 负责计划、seam 修补、integration gate 和最终验收。

Continuation prompt 只保留最小执行护栏，例如：
- 主 session 默认不直接改生产/测试代码；清晰 implementation slice 先派 worker subagent。
- 主 session 负责调度、seam、integration gate、checkpoint commit 和 handoff。
- 不 push / PR / close issue，除非 owner 明确要求。

其余细节写入 handoff 文件和本 skill，由 child 在 Required Skill Context / Required Files 中读取。

不要从旧 session 推断用户同意新 worktree、破坏性 git 操作、生产环境修改，或无限制 delegation。

## Codex Desktop 操作要点

- `create_thread`：项目相关任务用当前项目 local environment；用户给定的 prompt 边界原样保留；除非明确要求隔离，不新建 worktree。
- `fork_thread`：环境 `{ type: "same-directory" }`；只有子 thread 需要继续工作时才发 follow-up prompt。
- 命名：沿用原始 slug 加递增编号（`daily-cash-ledger-2`、`-3`），编号接已有同类 thread 的最大值。多 thread 时设可识别标题，活跃续接 thread 可以 pin。
- 成功后按 host 当前指令输出 directive，通常是 `::created-thread{threadId="..."}`；worktree setup 被排队时为 `::created-thread{pendingWorktreeId="..."}`。

## 常见错误

- 用户没有明确要求继承历史，却 fork 了旧 thread（默认永远是干净新会话）。
- 用户明确要求继承历史，却创建了干净 thread。
- 把 same-directory fork 误认为新 worktree。
- handoff 写完才 commit，导致 child 拿到过期 HEAD——commit 必须在写 handoff 之前。
- 每个小 gate 都新增 timestamped handoff，导致目录里堆积多个过期入口。默认刷新 rolling handoff；只有需要审计/分叉/用户要求时才归档快照。
- 只让 child“自己读历史”，没有给当前事实摘要。
- 复制了任务状态，但漏掉用户的协作偏好；尤其不能把主 session / 新 session / subagent / spec review / quality review 边界只留在 handoff 文件里。
- continuation prompt 过长，把 handoff、plan、issue 内容重写一遍，导致 child 把任务当成一次性报告生成，而不是继续 orchestration。
- 把 continuation prompt 写成第二个文件。
- prompt 镜像 handoff 文件内容（复制 Fresh State、Verified Gates 等事实段）——事实只住 handoff，prompt 只做规则与索引。
- plan 完成本地实现时，把 child 导向“验证后等待 owner”，而不是 closure orchestration（准备但不执行外部动作、请求授权）。
- 把 `create_thread` 当成可阻塞 IPC：要求 child 第一条回复后等待 parent ACK，导致自动推进中断。
- 把 First Progress Update 当成最终答复：child 汇报 verified state / intent 后停止，而不是继续执行 Next Action。
- 长流程自动交接创建 child 后完全不检查首条进度更新；如果 host 能看到 child 回复，应做一次轻量纠偏，但不能设计成必须等待 ACK 才继续。
- 在 handoff 里贴 secrets、token、env 值或完整日志。
- 声称没有实际发生的验证，或混淆 verified 与 assumed。
