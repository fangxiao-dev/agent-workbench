---
name: req-align
description: Use when new or changed requirements need alignment before feature design, specification, or implementation planning. Owns the required Design and Spec gates and their design.md/spec.md artifacts.
---

# Requirement Alignment

Run the two mandatory entry gates for an Impl-Package: Design, then Spec. The gates are equal requirements. Design is never skipped, even when its standalone `design.md` would be empty ceremony.

Repository instructions and discovered project conventions determine knowledge sources. Do not assume a product domain or impose another workflow's document destinations.

## Owned Artifacts

Use `docs/implementations/<package-id>/` as the canonical package root. A package-id is `YYMMDD-<topic-slug>` (UTC creation date), for example `260711-catalog-readiness`; it is a directory identity, not a mutable title. This skill owns:

- `design.md`，活动变更期间的当前设计选择与 rationale SoT；blocked Design 必须持久化，lightweight passed path 可仅在 spec Design Gate Record 中保留最小证据；
- `spec.md`，活动变更期间的当前行为、数据、边界、失败恢复、约束与 Acceptance Semantics SoT。

Use [assets/templates/design.md](./assets/templates/design.md) and [assets/templates/spec.md](./assets/templates/spec.md). Do not publish a tracker spec or create a second spec for the same package. `impl-planning` consumes the gated `spec.md`; it does not own or synthesize a replacement.

Omitting standalone `design.md` is legal only after Design evaluates `PASSED` and the lightweight evidence fits in the `Design Gate Record` at the top of `spec.md`. “No design file” never means “no Design step.” Requirement source and alignment provenance belong in `design.md`; on the lightweight passed path, preserve their minimum durable form in that same `Design Gate Record`.

This skill may append to package `findings.md` when research establishes a fact, risk, or constraint that later stages can reuse. Keep ordinary research narrative in `design.md`; do not create an empty findings ledger when there is no substantive cross-stage finding. `dev-with-track` remains the owner of the findings format and final consolidation.

## Package Identity

For a **new** implementation package, choose a short semantic `topic-slug`, then generate one immutable `package-id` from the current UTC creation date:

```text
<package-id> = YYMMDD-<topic-slug>
```

Record both values in the Design/Spec metadata before creating downstream artifacts. Check whether the exact directory already exists; if it does, append `-02`, `-03`, and so on until it is unique. Use the resulting package-id in every package path, cross-package reference, truth pointer, and handoff. This prevents distinct short-lived changes with the same topic from sharing a workspace.

For an existing package, retain its current directory name as its legacy or timestamped package-id. Never rename it merely to add a timestamp. A post-gate patch remains in that owning package-id; it is not a new implementation package. 重新激活已关闭 package 前，按 impl-package-composition-contract.md 的 Module Knowledge Watermark 机制对账：重新计算相关 module-knowledge 文件当前 commit SHA，与上一 attempt plan 记录的 watermark 比对；不符时先 diff 确认 design/spec 是否仍成立，再判断属于实现偏离、行为 contract 变化还是设计选择变化。

## Discover Project Knowledge

1. Read every applicable `AGENTS.md` for the target repository and path.
2. Read the repository's project-context entry point when present or referenced.
3. Follow its routing to relevant product, architecture, domain, integration, operational, decision, testing, and nearby implementation records.
4. Inspect focused code and tests where needed to establish current behavior.
5. Record sources checked and expected knowledge that was absent.

Use the repository's vocabulary and source-of-truth hierarchy. If durable project knowledge should change, propose the change against the discovered authoritative source and wait for owner approval; never invent a fixed long-lived destination.

## Gate 1: Design (Required)

Design turns the requirement and repository facts into a decision-ready destination. Use the eight-section Design Research structure in the design template. The analysis and gate judgment always happen before `spec.md` is created. A passed lightweight Design may omit the file; a blocked Design may not.

The Design gate passes only when all of these are verifiably true:

- **Destination is answerable:** intended outcome, affected system boundary, and handoff to the implementation contract are explicit.
- **Repository fit is evidenced:** authority sources and current-state facts have been checked; conflicts and missing knowledge are named.
- **Choices are decided:** material options and trade-offs have a selected direction and rationale, or an explicit owner decision blocks the gate.
- **Open Questions are non-blocking for Spec:** every question is resolved, explicitly deferred with owner and consequence, or proven not to affect the contract.
- **Owner Decisions are durable:** resolved and outstanding decisions are written in `design.md`, or in `spec.md`'s `Design Gate Record` when no design file is earned.

If any criterion fails, create or update `design.md`, record `Design Gate: BLOCKED`, the missing evidence, and the owner decision required, and do not create `spec.md` or begin the Spec gate.

### Design Boundary

- `Decisions / Rationale` records choices and why they were selected. Put behavior, state, interface, and failure semantics only in `spec.md`; do not copy those contracts into design.
- `Backfill Candidates` is a non-binding research hint. It is not a durable-delta register, does not authorize stable-document edits, and need not be merged into spec. Canonical durable-delta capture happens at the execution gate and downstream backfill.

`design.md` 声明 `Design Revision: D<n>`。正文只保留当前选择；方向变化时升级 revision、重跑 Design Gate，并在 Revision History 中用一行记录 previous/new、变更摘要、authority、日期与 superseded 说明。完整旧正文由 Git 保存，不在当前正文并排维护。

## Gate 2: Spec (Required)

Start only after the Design gate passes. Synthesize the point-in-time contract from:

- repository facts and authoritative knowledge, distinguishing facts from assumptions;
- user-facing semantics and agreed outcomes, using repository domain language;
- selected seam/interface decisions and the highest practical behavioral testing seams;
- owner decisions from Design, without copying research narration into the contract.

Use the thick eight-section spec template. The Spec gate passes only when:

- all eight contract sections are present and substantive for the change, including Error Boundaries / Failure Recovery and Constraint Contracts;
- behavior, state transitions, workflows, boundaries, and failure recovery are internally consistent and actionable without reading the plan;
- Acceptance Semantics maps each promised outcome or constraint to observable evidence and names any manual verification owner;
- blocking owner decisions and unresolved contract ambiguity are zero.

If any criterion fails, record `Spec Gate: BLOCKED` with the exact missing contract or decision. Do not hand off to planning. A passing spec records `Spec Gate: PASSED`, date, evidence, and approver/owner.

The spec must not contain a `Stable Doc Backfill Map`, durable-delta queue, Composition, worker task steps, verification command log, or tracker publication metadata. `Composition` 由每次 attempt plan 独立决定。

`spec.md` 声明 `Spec Revision: S<n>`，并始终记录其绑定的 `Design Revision: D<n>`；lightweight Design 没有独立 design.md 时，这一字段与 Design Gate Record 共同提供 D revision 的 canonical 落点。纯实现修复以重新符合当前 spec 时复用 revision；行为 contract 变化时升级 S revision 并重跑 Spec Gate；设计选择变化时必须先完成新的 Design revision/Gate。正文只保留当前合同，旧合同通过 Revision History 与 Git 追溯。

### 自动 grill-me-smartly 通关

每次真正需要评估 Spec Gate 时（首次创建，或行为 contract/设计方向变化的 patch；纯实现漂移复用 revision、不评估 Spec Gate，因此不触发），在宣布 `Spec Gate: PASSED` 之前自动运行一遍 `grill-me-smartly` 的 review phase（只审查，不 apply）对当前 spec.md 草稿做独立对抗，用来抓自我审查容易漏掉的浅显问题。

- Ledger 住在 OS temp 目录，不是 package artifact，不落 `docs/implementations/<package-id>/`。
- 把 ledger 的「已收敛决策摘要」与「待用户裁决」汇报给用户；`待用户裁决` 条目直接计入上面 Spec Gate 标准里"blocking owner decisions 为零"这条——未清空前 Spec Gate 不能 PASSED，不新造阻断机制。
- 是否把已收敛的澄清写进 spec.md 正文，必须等用户明确要求 apply——这是 grill-me-smartly 自己的硬性契约（永不静默 apply），req-align 不得代为绕过。用户批准后按正常 S revision 流程原地修订。

## Workflow

1. Announce use of req-align; for a new package assign a topic slug and an immutable date-prefixed package-id, or identify the owning existing package-id for a patch/follow-up and classify drift against current module knowledge/code.
2. Discover authoritative project knowledge before detailed clarification.
3. Ask one focused question at a time for unresolved intent, scope, constraints, success criteria, trade-offs, or owner decisions.
4. Run Design Research, present the selected direction plus blockers, and evaluate the Design gate before creating `spec.md`.
5. If Design is blocked, create or update `design.md` with provenance, readiness evidence, blockers, and owner decisions; stop without creating `spec.md`.
6. If Design passes, either persist its substantive research in `design.md`, or take the lightweight path: create `spec.md` and write the minimum provenance, readiness, and owner-decision evidence into its Design Gate Record. Append reusable, verified cross-stage facts/risks/constraints to an already-needed `findings.md`; do not create it for ordinary research narration.
7. Synthesize the eight-section `spec.md`. For a patch, reuse D/S revisions for implementation-only drift without evaluating Spec Gate, rerun only Spec Gate for behavioral contract changes, and rerun Design then Spec for design-direction changes. When Spec Gate is actually being evaluated, automatically run `grill-me-smartly`'s review phase against the draft first, resolve or surface its findings per Gate 2's rule, then evaluate the Spec gate. Stop when the required gate is blocked.
8. After both gates pass, hand off the same `spec.md` to `impl-planning`; do not create another spec or publish to a tracker.

## Alignment Proposal

Before writing artifacts or editing long-lived knowledge, present:

```markdown
## Requirement Alignment Proposal

### Focused Requirement
<requirement using repository terms>

### Authoritative Knowledge Fit
- Product intent fit:
- Architecture and constraints fit:
- Current-state facts:
- Sources checked:
- Expected knowledge not found:

### Drift Or Conflict Check
- Confirmed alignment:
- Possible drift:
- Out of scope:

### Design Direction
- Selected option and rationale:
- Open questions:

### Proposed Durable Knowledge Changes
- File / change / reason, or "None"

### Owner Decisions
- <decision, owner, and blocking effect, or "None">

### Recommended Next Step
- Persist Design gate and proceed to Spec
- Stop for owner decision
```

## User-Facing Output

向 owner 汇报时使用 `talk-to-boss`：用人话说明需求/设计/规格对齐覆盖的功能范围、Design 与 Spec 分别完成到哪、剩余 owner decision 数量、整体是否可进入实施计划。不要以 slug、revision 或路径开场，也不要把 blocked gate 描述成完成。

随后附 canonical handoff：topic slug、package-id/path、两道 gate result 与 evidence location、changed files（只在 append 时列 `findings.md`）以及剩余 owner decisions。artifact 写入后不粘贴全文。

When Spec Gate was actually evaluated, name the `grill-me-smartly` ledger path and summarize its converged decisions and any resolved owner decisions. After Spec Gate PASSED, offer `grilling` as an optional deeper adversarial follow-up if the user wants more scrutiny before handing off to `impl-planning` — a suggestion, never a requirement.

Artifact `Status` and gate `Result` must agree: a Passed status requires `PASSED`, a Blocked status requires `BLOCKED`, and neither may be inferred from prose alone.
