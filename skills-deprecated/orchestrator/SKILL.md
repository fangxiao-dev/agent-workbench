---
name: orchestrator
description: >
  Orchestrate an already-authored bulk implementation plan into a scheduler-facing
  parent plan plus AFK/HITL GitHub issue slices. Use when the user asks for
  调度计划 / 父计划 / orchestration plan, review gates, handoff checkpoints,
  or tracker-ready issue output from an existing implementation plan.
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

- 输入仍是原始需求、PRD 或讨论，还没有 implementation plan：先用 `feature-impl-planning`。
- 用户只要 tickets、不需要把父计划改写成调度面：直接用 `to-tickets`。
- 用户只是要执行已有 issues：转入执行流程，例如 `subagent-driven-development` 或项目执行约定。

## Required Sub-Skills

- **REFERENCE:** `to-tickets`，作为 tracer-bullet vertical slice 与 blocking edges 的质量背景；本 skill 的 `Tracker Contract` 是 approval / publish / issue body 的直接规范。
- **REFERENCE:** `feature-impl-planning`，仅当输入还不是 bulk implementation plan。
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
- Issue drafts 是临时交换产物。优先放在项目 ignored exchange 目录，例如 `docs/exchange/issue-drafts/<slug>/`；写入前必须确认 draft path 已被 ignore / exclude。若无法确认，使用 chat-only output，或先询问是否创建 ignore / exclude 规则。发布后 GitHub issues 是唯一耐久执行源，drafts 不提交、不回链。
- 每个 candidate slice 必须带 size/risk 估计并给出明确 sizing decision（见 `Slice Sizing & Risk`）。偏宽或高风险 slice 不得不经决策就直接成 issue，须先 split / narrow / 加 `design-interface-gate` / 跟用户对齐。

## External Side Effects

- “输出 issues”默认是 drafts / breakdown。
- “创建 / 发布 GitHub issues”需要明确发布意图、tracker 目标、用户已批准的 breakdown。
- 不要 close、merge、push、修改 parent issue 状态，除非用户明确要求。
- 如果用户明确只读或禁止写文件，不要落盘 plan、drafts、ledger；在聊天中维护临时版本或先请求写入授权。

## Tracker Contract

`to-tickets` 是背景参考，不是 mandatory behavior 的唯一来源。本 skill 直接规定 tracker contract：

- Approval quiz 必须按 step 7 展示 breakdown，并迭代到用户明确批准。
- 发布只发生在用户批准 breakdown 且明确要求创建 / 发布 GitHub issues 后。
- 发布必须按依赖顺序：blocker 先发布，dependent issue 后发布，并用真实 tracker ID 填 `Blocked by`。
- Issue body 必须包含：Parent（如果来源是 tracker parent issue）、What to build、Acceptance criteria、Blocked by、Ownership Boundary / Out Of Scope、Verification。
- 不要 close 或修改 parent issue，除非用户明确要求。
- Issue title 不包含本地 slice 序号；发布后 GitHub issue number 是唯一规范 ID。

## Slice Sizing & Risk

Sizing 是 gate，不是说明文字。拆解、review、用户 approval 前都要读取并应用 `references/slice-sizing.md`。

每个 candidate slice 必须输出 size/risk signals 和 sizing decision enum：`keep` / `vertical-split` / `tracer-bullet-follow-ups` / `design-interface-gate` / `escalate-to-user`。Wide、high-risk、cross-cutting slice 不得不经决策就直接成 issue。

Completion criterion：每个 candidate slice 都有明确 sizing decision；每个 wide / high-risk / cross-cutting slice 都已 split、narrow、加 `design-interface-gate`，或在 step 7 带选项升级给用户。

## HITL Pull-Forward Review

HITL 是可提前消化的阻塞风险，不是默认执行期停等。拆解、review、用户 approval 前都要读取并应用 `references/hitl-pull-forward.md`。

每个 HITL / gate / external-side-effect slice 必须分类为：`pull forward` / `convert to validation gate` / `simplify overdesign` / `keep HITL`。

Completion criterion：每个 HITL 相关 slice 都有 pull-forward decision packet；已批准的 standing authorization 写入父计划和 issue label/gate changes；未批准或信息不足的项保留为 explicit remaining owner decision。

## Example Calibration

Only when the user asks for examples, plan-shape comparison, or template calibration, read `references/orchestration-exemplars.md`. Do not load examples during ordinary orchestration runs.

## Workflow

### 1. Ground The Source

- 读取 bulk implementation plan 全文。
- 查找相关 Func Design、PRD、ubiquitous language、architecture、existing impl plans、test-case index。
- 如果是从已有计划演进而来，检查 git history，理解 bulk 版和当前版差异。
- 确认 tracker、repo、分支、dirty worktree、已有 issue drafts 或已发布 issues。
- 只问无法从环境发现且会改变计划边界的问题。

Done when：source plan、相关 design/test/tracker context、git/tracker baseline、以及仍需用户决策的边界问题都已明确记录。

### 2. Preserve The Bulk Plan

- 改写同一父计划文件前，运行并记录 `git status --short --branch` 和相关 plan 文件的 commit 状态。
- 如果 bulk plan 已 commit，可以就地改写。
- 如果 bulk plan 未 commit，先提交 checkpoint；若没有提交授权，保存一份 source snapshot，再改写。
- 不要把未提交 bulk checklist 直接删成 orchestration plan。

Done when：bulk plan 已 commit，或已在授权下 checkpoint commit，或已有明确 source snapshot；只读/禁止写入时不得覆盖原计划。

### 3. Dispatch The Decomposition Worker

先读取 `references/slice-sizing.md` 和 `references/hitl-pull-forward.md`，再使用 `templates/decomposition-prompts.md` 的 Decomposition Worker prompt 派遣 worker：提出 phases、dependency graph、risk hotspots、candidate slices，并为每个 candidate slice 给出 size/risk 估计与建议的 sizing decision 以及 HITL pull-forward candidates。

两个 reviewer 角色在第 6 步 Review Gate 派遣；它们审的是第 4、5 步的草稿，不要在此处空派。

如果没有 subagent 能力，记录 fallback reason，并由主 session 使用同一 prompt inline 完成 decomposition；第 6 步仍执行同样的两轮 inline review。

Done when：subagent 或 inline decomposition 返回 phases、dependency graph、risk hotspots、candidate slices、sizing decisions、HITL pull-forward candidates；no-subagent fallback reason 已记录但不能替代 decomposition output。

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

Done when：父计划只保留 scheduler / integrator / validator 需要的调度信息，且每个源需求映射到父计划、issue draft 或 explicit exclusion。

### 5. Draft Issue Slices Only

这里不要发布。

遵守 `Tracker Contract`。本 skill 的 grounding 和 decomposition 替代普通 issue-splitting 的 context / explore / draft 阶段；approval quiz 在 review gate 之后；publish 只能在用户批准后执行。

在 `Tracker Contract` 的 issue body 基础上，每个 issue 额外包含：

```markdown
## Ownership Boundary / Out Of Scope

## Verification
```

`Verification` 必须列 focused gate；contract-changing issue 还要列 schema/API gate。Issue 正文避免易过期文件路径、行号和实现细节；例外是 prototype 产出的 decision-rich snippet。`Verification` 里的 gate 命令和测试路径不受此限。不要把父计划 guardrails 全量复制到每个 issue，只放该 issue 必须知道的局部约束。

Done when：每个 draft issue 都 independently grabbable，包含 acceptance criteria、Ownership Boundary / Out Of Scope、focused Verification gate、blocked-by 关系、sizing decision 和必要的 HITL/pull-forward 状态。

### 6. Review Gate

Review 必须在用户批准和 GitHub 发布之前完成。使用 `templates/decomposition-prompts.md` 的对应 prompt 派遣两个独立 reviewer：

- Orchestration/spec reviewer 检查 bulk plan coverage、scope creep、dependencies、HITL/AFK、seams、父计划是否仍然 orchestration-only。
- Issue-quality reviewer 检查每个 issue 是否 independently grabbable，是否有 ownership boundary、out of scope、acceptance criteria、focused gate。
- 两个 reviewer 都必须检查 HITL pull-forward：哪些停等可提前决策、哪些 gate 可转成 agent validation、哪些设计对当前 POC 过重、哪些 HITL 必须保留。
- Reviewer 提出问题后，必须修复并 re-review，循环直到 approve；不要用主 session 判断“差不多”跳过复审。

Done when：两个 reviewer 都返回 APPROVED；如果没有 subagent 能力，inline review 也必须按两个独立角色完成并记录结果。

### 7. User Breakdown Approval

按 `Tracker Contract` 运行 approval quiz，向用户展示：

- issue title。
- type：AFK / HITL。
- blocked by。
- user stories / source requirements covered。
- ownership boundary。
- verification gate。
- slice size/risk 与 sizing decision：对 wide / high-risk slice，说明拟采取的 split / `design-interface-gate` / `escalate-to-user`，让用户对齐是否需要进一步拆分。
- HITL pull-forward decision packet：列出可提前批准的 standing authorization、可转 agent validation 的 gate、建议删减的过度设计、仍必须保留的 owner decisions。

如果用户已经明确批准同一 breakdown，可记录该事实并继续。不要为 subagent 使用、draft 生成或父计划改写增加额外审批。

Done when：用户批准 breakdown，或用户要求的 merge/split/scope changes 已回流到 step 4-6 重新 draft/review。

### 8. Publish, Link, Commit

仅当用户批准 breakdown 且明确要求发布 GitHub issues 时执行：

- 按依赖顺序发布 blocker，再发布 dependent issue。
- Triage label：使用项目已提供的 label 约定；未提供时向用户确认或不加 label，不要编造 label 词汇。
- Issue title 不包含本地 slice 序号。
- 发布后回填父计划 issues table，使用 GitHub issue links。
- 父计划写明：published GitHub issues are the durable execution source; local drafts are temporary.
- 有提交授权时提交 checkpoint，至少包含 orchestration parent plan 和 issue-link 回填；不要提交 ignored drafts。没有提交授权时，报告 modified files 和建议的 checkpoint command。

如果只需要 drafts，停止在 draft + review + user-approved breakdown，并返回 draft paths。

Done when：issues 已按依赖顺序发布并回填父计划，或 draft-only 路径已返回；需要 commit 时已 commit，否则已明确报告未提交状态。

### 9. Execution Handoff

当用户要把 issues 交给 session 执行，或任务跨 session / worktree / 外部状态时：

- 调用 `handoff-new-session`，不要手写丢失 git state 的短总结。
- Handoff 必须包含 workspace、branch、HEAD、dirty/clean 状态、issue 顺序、已验证 gate、协作契约、next action。
- 如果 orchestration 工作本身跨 session，使用 `templates/progress-ledger.md` 维护临时 ledger；否则发布记录回填父计划即可。

Done when：handoff 由 `handoff-new-session` 生成，并包含 workspace、branch、HEAD、dirty/clean、issue 顺序、verified gates、collaboration contract、next action。

## Output Contract

最终回复按实际 branch 输出，不要虚构未发生的 path、link、commit、issue 或 handoff。

- **Draft-only**：orchestration parent plan path、issue draft paths、review 方法和 reviewer 结果、corrections applied、HITL pull-forward result、ready for execution。
- **Published**：orchestration parent plan path、GitHub issue links、issue-link 回填状态、checkpoint commit 状态、review 方法和 reviewer 结果、standing authorization scope、remaining owner decisions、ready for execution。
- **Readonly / no-write**：chat-only parent plan outline、issue breakdown summary、review method、remaining owner decisions、ready for execution；不要声称已落盘。
- **Handoff**：handoff target / path、workspace、branch、HEAD、dirty/clean、issue execution order、next action。

## Quality Red Lines

- 不要把 bulk implementation plan 原样换标题。
- 不要在 review 和用户批准前发布 issues。
- 不要完整重跑普通 issue-splitting 的 context/draft 阶段；这部分由 orchestrator 替代。
- 不要跳过 `Tracker Contract` 的 approval 和 dependency-order publish。
- 不要让 subagent 继承模糊上下文。
- 不要把 issue 拆成纯水平层，除非该层能独立验证。
- 不要让 wide / high-risk slice 不经 sizing decision 就直接发布；oversized 横切 slice 不要默认硬拆（会放大集成 seam），优先 `design-interface-gate` 或与用户对齐。
- 不要把高风险 publish/retry/recovery 语义藏在普通 AFK issue 中。
- 不要省略 final regression / orchestration cleanup issue。
- 不要承诺未实际发生的 gate、commit、issue publish 或 handoff。
