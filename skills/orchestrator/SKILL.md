---
name: orchestrator
description: >
  Turn an already-authored bulk implementation plan into an orchestration parent
  plan and GitHub issue drafts or published issues. Use when a large bulk plan
  needs a scheduler-facing 调度计划 / orchestration plan / 父计划, AFK/HITL
  issue slices, subagent dispatch boundaries, review gates, handoff checkpoints,
  or GitHub tracker output.
---

# Orchestrator

把 bulk implementation plan 转成两个执行产物：

- **Orchestration parent plan**：只保留目标、依赖、边界、seaming、guardrails、handoff、verification policy。
- **GitHub issue slices**：承载具体实现任务、验收标准、focused gate 和 ownership boundary。

主 session 默认承担 scheduler / integrator / validator 角色；bulk implementation 交给后续 worker subagent 或执行 session。

## When To Use

使用本 skill：

- 用户已有 bulk implementation plan，并要求转成 orchestration plan + issues。
- 用户要“调度计划 / orchestration plan / 父计划 / 拆分大计划 / Plan + GH Issues”。
- 用户希望主 session 负责调度、拆分、验收和 seaming，而 worker subagent 负责实现。

不要使用本 skill：

- 输入仍是原始需求、PRD 或讨论，还没有 implementation plan：先用 `feature-impl-planing`。
- 用户只要 issues、不需要把父计划改写成调度面：直接用 `to-issues`。
- 用户只是要执行已有 issues：转入执行流程，例如 `subagent-driven-development` 或项目执行约定。

## Required Sub-Skills

- **REQUIRED SUB-SKILL:** `to-issues`，用于用户 quiz / approval、发布顺序和 issue body 模板。
- **REQUIRED SUB-SKILL:** subagent decomposition + independent review，按本 skill 的流程和 `templates/decomposition-prompts.md`。
- **REFERENCE:** `feature-impl-planing`，仅当输入还不是 bulk implementation plan。
- **REFERENCE:** `superpowers:writing-plans`，作为 issue 内实现计划的质量标准。
- **REFERENCE:** `superpowers:subagent-driven-development`，作为后续执行模式。
- **REFERENCE:** `handoff-new-session`，用于跨 session / worktree / 外部状态的 durable handoff。

## Core Rules

- 父计划是调度面，不是实现手册。实现细节、测试命令和局部 acceptance criteria 下沉到 issues。
- 在环境支持且用户未明确禁止时，内部 subagent 拆解和审核不需要再次请求批准。
- Subagent 不得发布 issues、修改外部状态、绕过只读要求，除非用户明确授权该类副作用。
- 发布 GitHub issues 前必须经过 draft、两轮 review、用户批准 breakdown；不要按草稿直接发布。
- 发布后 GitHub issue number 是唯一规范 ID。父计划可保留一次 slice-to-issue 映射，之后全文使用 GitHub issue number；不要把 slice 序号写进 issue title。
- 改写父计划前必须确认 bulk 版已 durable：已 commit，或在只读/未授权提交时保存到明确的 source snapshot。不要覆盖唯一的 bulk plan 副本。
- Issue drafts 是临时交换产物。优先放在项目 ignored exchange 目录，例如 `docs/exchange/issue-drafts/<slug>/`；发布后 GitHub issues 是唯一耐久执行源，drafts 不提交、不回链。

## External Side Effects

- “输出 issues”默认是 drafts / breakdown。
- “创建 / 发布 GitHub issues”需要明确发布意图、tracker 目标、用户已批准的 breakdown。
- 不要 close、merge、push、修改 parent issue 状态，除非用户明确要求。
- 如果用户明确只读或禁止写文件，不要落盘 plan、drafts、ledger；在聊天中维护临时版本或先请求写入授权。

## Workflow

### 1. Ground The Source

- 读取 bulk implementation plan 全文。
- 查找相关 Func Design、PRD、ubiquitous language、architecture、existing impl plans、test-case index。
- 如果是从已有计划演进而来，检查 git history，理解 bulk 版和当前版差异。
- 确认 tracker、repo、分支、dirty worktree、已有 issue drafts 或已发布 issues。
- 只问无法从环境发现且会改变计划边界的问题。

### 2. Preserve The Bulk Plan

- 改写同一父计划文件前，运行并记录 `git status --short --branch` 和相关 plan 文件的 commit 状态。
- 如果 bulk plan 已 commit，可以就地改写。
- 如果 bulk plan 未 commit，先提交 checkpoint；若没有提交授权，保存一份 source snapshot，再改写。
- 不要把未提交 bulk checklist 直接删成 orchestration plan。

### 3. Dispatch Decomposition Subagents

使用 `templates/decomposition-prompts.md`。至少需要：

- decomposition worker：提出 phases、dependency graph、risk hotspots、candidate slices。
- orchestration/spec reviewer：核对 source coverage、scope、dependencies、HITL/AFK、seams。
- issue-quality reviewer：核对 issues 是否 independently grabbable、demoable/verifiable、acceptance criteria 和 focused gates 是否明确。

如果没有 subagent 能力，执行同样的两轮 inline review，并记录 fallback reason。

### 4. Draft The Orchestration Parent Plan

父计划保留：

- execution-mode header：说明后续 agent 应实现 linked issues，并使用 `subagent-driven-development` 或项目执行约定。
- Goal / Architecture。
- Prerequisite / cross-plan dependencies。
- Source Context。
- Current Baseline。
- Business / Domain Context。
- Issues table：发布前是 drafts；发布后回填 GitHub issue links，并声明 GitHub issues 是 durable execution source。
- Parallel Assignment Plan。
- Slice / issue ownership boundaries。
- Handoff contracts。
- Seaming / Integration Seams To Watch。
- Guardrails。
- Verification Policy / Final Gate。

父计划移除：

- 文件级、函数级、TDD 级实现步骤。
- 长代码片段和 mock 实现。
- 单个 issue 的局部 acceptance criteria。
- 易过期行号和内部 helper 细节。

### 5. Draft Issue Slices Only

这里不要发布。

`to-issues` 接缝如下：

- `to-issues` 步骤 1-3（context / explore / draft）由本 skill 的 grounding 和 decomposition subagents 替代。
- `to-issues` 步骤 4（quiz user，迭代到批准）原样沿用，但发生在 review gate 之后。
- `to-issues` 步骤 5（按依赖序发布、issue body 模板）原样沿用，但只能在用户批准后执行。

对 `to-issues` issue 模板做增量扩展，每个 issue 额外包含：

```markdown
## Ownership Boundary / Out Of Scope

## Verification
```

`Verification` 必须列 focused gate；contract-changing issue 还要列 schema/API gate。不要把父计划 guardrails 全量复制到每个 issue，只放该 issue 必须知道的局部约束。

### 6. Review Gate

Review 必须在用户批准和 GitHub 发布之前完成。

- Orchestration/spec reviewer 检查 bulk plan coverage、scope creep、dependencies、HITL/AFK、seams、父计划是否仍然 orchestration-only。
- Issue-quality reviewer 检查每个 issue 是否 independently grabbable，是否有 ownership boundary、out of scope、acceptance criteria、focused gate。
- Reviewer 提出问题后，必须修复并 re-review，循环直到 approve；不要用主 session 判断“差不多”跳过复审。

### 7. User Breakdown Approval

沿用 `to-issues` quiz 环节，向用户展示：

- issue title。
- type：AFK / HITL。
- blocked by。
- user stories / source requirements covered。
- ownership boundary。
- verification gate。

如果用户已经明确批准同一 breakdown，可记录该事实并继续。不要为 subagent 使用、draft 生成或父计划改写增加额外审批。

### 8. Publish, Link, Commit

仅当用户批准 breakdown 且明确要求发布 GitHub issues 时执行：

- 按依赖顺序发布 blocker，再发布 dependent issue。
- Issue title 不包含本地 slice 序号。
- 发布后回填父计划 issues table，使用 GitHub issue links。
- 父计划写明：published GitHub issues are the durable execution source; local drafts are temporary.
- 提交 checkpoint，至少包含 orchestration parent plan 和 issue-link 回填；不要提交 ignored drafts。

如果只需要 drafts，停止在 draft + review + user-approved breakdown，并返回 draft paths。

### 9. Execution Handoff

当用户要把 issues 交给 session 执行，或任务跨 session / worktree / 外部状态时：

- 调用 `handoff-new-session`，不要手写丢失 git state 的短总结。
- Handoff 必须包含 workspace、branch、HEAD、dirty/clean 状态、issue 顺序、已验证 gate、协作契约、next action。
- 如果 orchestration 工作本身跨 session，使用 `templates/progress-ledger.md` 维护临时 ledger；否则发布记录回填父计划即可。

## Output Contract

最终回复包含：

- orchestration parent plan path。
- GitHub issue links 或 issue draft paths。
- 如果用户要求只读或禁止写文件，返回 chat-only parent plan outline 和 issue breakdown summary，而不是虚构 paths。
- review 方法和 reviewer 结果。
- corrections applied。
- remaining owner decisions。
- ready for execution: yes/no。

## Quality Red Lines

- 不要把 bulk implementation plan 原样换标题。
- 不要在 review 和用户批准前发布 issues。
- 不要完整重跑 `to-issues` 的 context/draft 阶段；这部分由 orchestrator 替代。
- 不要跳过 `to-issues` 的用户 quiz / approval 和 dependency-order publish。
- 不要让 subagent 继承模糊上下文。
- 不要把 issue 拆成纯水平层，除非该层能独立验证。
- 不要把高风险 publish/retry/recovery 语义藏在普通 AFK issue 中。
- 不要省略 final regression / orchestration cleanup issue。
- 不要承诺未实际发生的 gate、commit、issue publish 或 handoff。
