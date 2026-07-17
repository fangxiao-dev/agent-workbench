---
name: req-align
description: 当新增或变更 requirement 需要在 feature decision、specification 或 implementation planning 前完成对齐时使用；拥有必过的 Decision/Spec gates 及其 decision.md/spec.md artifact。
---

# Requirement Alignment

For a new or changed behavior contract, run the two mandatory entry gates for an Impl-Package: Decision, then Spec. The gates are equal requirements. Decision is never skipped for a contract-impacting change, even when its standalone `decision.md` would be empty ceremony. A `contract impact=none` request exits through the routing fast path below before gate execution; that is reuse of an already valid contract, not a skipped gate.

Repository instructions and discovered project conventions determine knowledge sources. Do not assume a product domain or impose another workflow's document destinations.

## Owned Artifacts

Use the project's configured implementations root (default `docs/implementations/`) as the canonical package parent. A package-id is an immutable date-prefixed topic slug; the project owns the date format, and the ID is a directory identity rather than a mutable title. This skill owns:

- `decision.md`，活动变更期间的聚焦需求定义（Focused PRD）与当前决策/rationale SoT；回答为什么做、要达到什么结果、为什么选择该方向。blocked Decision 必须持久化，lightweight passed path 可仅在 spec Decision Gate Record 中保留最小证据；
- `spec.md`，活动变更期间的当前行为、数据、边界、失败恢复、约束与 Acceptance Semantics SoT；
- 内部 `.impl-package/revision-bindings.json` 中 D/S current selection 与 append-only binding。共享 schema 与命令来自 [`../references/impl-package-state-schema.md`](../references/impl-package-state-schema.md)；plan/P binding 由 `impl-planning` 拥有。sidecar 不属于 owner-facing deliverable，decision/spec/handoff Markdown 必须自足呈现投影与校验结论。

Use [assets/templates/decision.md](./assets/templates/decision.md) and [assets/templates/spec.md](./assets/templates/spec.md). Do not publish a tracker spec or create a second spec for the same package. `impl-planning` consumes the gated `spec.md`; it does not own or synthesize a replacement.

## No-contract fast path

先按共享 contract 的 impact signals 判断当前变化是否真的触及 Decision/Spec。若 `contract impact=none`，且业务结果、Acceptance Semantics、安全/数据约束与 mutation authority 均未改变，则复用当前 D/S revision，不运行 brainstorming、Decision Gate、Spec Gate 或 `grill-me-smartly`，也不为这次局部修正新增 JSON 字段。把请求路由到直接 owning skill，并只返回“现有 contract 仍成立”及其依据。纯删除错误知识、修正证据/链接/分类、收缩未使用 authority，通常走这条路径；若删除会改变承诺行为或验收边界，则仍按真实 contract impact 处理。

Omitting standalone `decision.md` is legal only after Decision evaluates `PASSED` and the lightweight evidence fits in the `Decision Gate Record` at the top of `spec.md`. “No decision file” never means “no Decision step.” Requirement source and alignment provenance belong in `decision.md`; on the lightweight passed path, preserve their minimum durable form in that same `Decision Gate Record`.

`decision.md` 按内容价值 earn：新功能、明显体验变化或业务能力变化通常必须创建，因为其 Focused PRD 对后续理解和取舍具有持久价值；已有产品定义下、无需重述用户问题与价值的小型行为修正可以走 lightweight Decision。`contract impact=none` 的实现修复继续复用现有 D/S，不创建或扩写 `decision.md`。是否有独立文件不改变 Decision 步骤与 Gate 必经这一事实。

This skill may append to package `execution-findings.md` when research establishes an important confirmed fact, risk, methodological lesson, or cross-task finding that the package or later attempts can reuse. It is package-local provenance, not a second behavior contract or a temporary todo queue. Keep raw ideas, candidate hypotheses, experiment material, and incomplete investigation notes in an earned-only `investigations/<topic>.md`; never create an empty `investigations/` directory. Investigation content has no authority, runtime state, revision binding, or machine projection. Formal documents may link to it when useful, but `decision.md` and `spec.md` must remain self-contained and investigation files do not maintain backlinks or adoption status.

当用户点名一份由本次工作拥有的非权威调研文档，并要求“基于它对齐需求”时，该文档已经 earn `investigations/`：建立 package identity 后，把原文件移动为 `investigations/<topic>.md`，保留原始内容并用主题化文件名解决命名冲突，不在旧位置保留副本或迁移说明。随后从中提炼当前决定与行为合同到 `decision.md` / `spec.md`，正式文档只在有助于 provenance 时链接该 investigation。项目级权威知识、跨 package 共享文档、只读或不归本次任务拥有的来源不得移动，继续原位引用；“移动调研文档”不能改变 authority 层级，也不能让正式文档依赖读者通读原始材料。

## Package Identity

For a **new** implementation package, choose a short semantic `topic-slug`, then generate one immutable `package-id` from the current UTC creation date:

```text
<package-id> = YYMMDD-<topic-slug>
```

Record both values in the Decision/Spec metadata before creating downstream artifacts. Check whether the exact directory already exists; if it does, append `-02`, `-03`, and so on until it is unique. Use the resulting package-id in every package path, cross-package reference, truth pointer, and handoff. This prevents distinct short-lived changes with the same topic from sharing a workspace.

For an existing package, retain its current directory name as its legacy or timestamped package-id. Never rename it merely to add a timestamp. A post-gate patch remains in that owning package-id; it is not a new implementation package. 重新激活已关闭 package 前，按 impl-package-composition-contract.md 的 Module Knowledge Watermark 机制对账：重新计算相关 module-knowledge 文件当前 commit SHA，与上一 attempt plan 记录的 watermark 比对；不符时先 diff 确认 decision/spec 是否仍成立，再判断属于实现偏离、行为 contract 变化还是设计选择变化。

## Discover Project Knowledge

1. Read every applicable `AGENTS.md` for the target repository and path.
2. Read the repository's project-context entry point when present or referenced.
3. Follow its routing to relevant product, architecture, domain, integration, operational, decision, testing, and nearby implementation records.
4. Inspect focused code and tests where needed to establish current behavior.
5. Record sources checked and expected knowledge that was absent.

Use the repository's vocabulary and source-of-truth hierarchy. If durable project knowledge should change, propose the change against the discovered authoritative source and wait for owner approval; never invent a fixed long-lived destination.

## Gate 1: Decision (Required)

Decision turns the focused product need and repository facts into a decision-ready destination. Use the eight-section Focused PRD + Decision Research structure in the decision template. The analysis and gate judgment always happen before `spec.md` is created. A new feature, material experience change, or business capability change normally earns the file; a passed lightweight correction under an existing product definition may omit it, while a blocked Decision may not.

The Decision gate passes only when all of these are verifiably true:

- **Destination is answerable:** intended outcome, affected system boundary, and handoff to the implementation contract are explicit. When delivery and validation use different paths, state the delivery path and the limit of what validation proves; validation convenience must not silently redefine the intended product path.
- **Focused need is defined at the right layer:** target user/scenario, current problem and trigger, expected result/value, scope/non-goals, core experience or business flow, and success signals are explicit when the change earns a Focused PRD; a lightweight correction points to the existing product definition and records the minimum delta evidence instead of manufacturing a duplicate PRD.
- **Repository fit is evidenced:** authority sources and current-state facts have been checked; conflicts and missing knowledge are named.
- **Choices are decided:** material options and trade-offs have a selected direction and rationale, or an explicit owner decision blocks the gate.
- **Open Questions are non-blocking for Spec:** every question is resolved, explicitly deferred with owner and consequence, or proven not to affect the contract.
- **Owner Decisions are durable:** resolved and outstanding decisions are written in `decision.md`, or in `spec.md`'s `Decision Gate Record` when no decision file is earned.

If any criterion fails, create or update `decision.md`, record `Decision Gate: BLOCKED`, the missing evidence, and the owner decision required, and do not create `spec.md` or begin the Spec gate.

### Decision Boundary

- `decision.md` owns the Focused PRD and selected direction: why this change exists, which user/business result it must reach, and why the chosen option is preferred. Focused PRD does not copy field-level contracts, state machines, error handling, or line-by-line Acceptance Criteria; `Decisions / Rationale` does not repeat the requirement background.
- `spec.md` owns the behavior contract: how the system must behave, including data/field contracts, states, boundaries, failure recovery, constraints, and Acceptance Semantics.
- `plan.md` owns implementation: how the approved contract is decomposed, implemented, integrated, and verified. Decision and spec do not grow file steps, task topology, or verification command logs.
- `Backfill Candidates` is a non-binding research hint. It is not a durable-delta register, does not authorize stable-document edits, and need not be merged into spec. Canonical durable-delta capture happens at the execution gate and downstream backfill.

`decision.md` 的唯一 revision 声明是 machine-owned `revision-set` marker 中的 `决策修订（Decision Revision）：D<n>`；不得在 marker 外再写 `Decision Revision` header。正文只保留当前聚焦需求与选择；用户/业务结果或决策方向发生实质变化时升级 revision、重跑 Decision Gate，并在 Revision History 中用一行记录 previous/new、变更摘要、authority、日期与 superseded 说明。纯模板重排、标题校准或把已存在信息归入 Focused PRD 不单独升级 D；应按 contract-impact-none editorial correction 规则处理。Gate 通过后计算最终 artifact 的 Git blob OID，在内部 sidecar 追加 D binding、更新 current decision 并刷新 projection；artifact 不记录自身 hash。完整旧正文由 Git 保存，不在当前正文并排维护。

## Gate 2: Spec (Required)

Start only after the Decision gate passes. Synthesize the point-in-time contract from:

- repository facts and authoritative knowledge, distinguishing facts from assumptions;
- user-facing semantics and agreed outcomes, using repository domain language;
- selected seam/interface decisions and the highest practical behavioral testing seams;
- owner decisions from Decision, without copying research narration into the contract.

Use the thick eight-section spec template. The Spec gate passes only when:

- all eight contract sections are present and substantive for the change, including Error Boundaries / Failure Recovery and Constraint Contracts;
- behavior, state transitions, workflows, boundaries, and failure recovery are internally consistent and actionable without reading the plan;
- Acceptance Semantics maps each promised outcome or constraint to observable evidence and names any manual verification owner;
- blocking owner decisions and unresolved contract ambiguity are zero.

If any criterion fails, record `Spec Gate: BLOCKED` with the exact missing contract or decision. Do not hand off to planning. A passing spec records `Spec Gate: PASSED`, date, evidence, and approver/owner.

The spec must not contain a `Stable Doc Backfill Map`, durable-delta queue, Composition, worker task steps, verification command log, or tracker publication metadata. `Composition` 由每次 attempt plan 独立决定。

### Conditional Evidence-Integrity Contract

Evaluate this contract only when an acceptance conclusion depends on evidence whose authority, comparison, publication, compatibility, or consumption could change whether the system falsely passes. Examples are external-provider or integration proof, a durable `current`/latest pointer, atomic publish or archive, external mutation, a schema projected from another authority, or a public payload whose shape varies by state; these are examples, not prerequisites for every package.

When the signal is present, make the existing eight spec sections answer the relevant questions without creating a ninth section or a new artifact:

- In Terms / Data Contracts and Acceptance Semantics, define the primary assertion, the comparison unit and normalization, actual-versus-declared bounds where relevant, and the authoritative source for every projected contract field.
- In Behavior and Error Recovery, state each commit point; enumerate every input it trusts, such as caller declarations, persisted snapshots, external evidence, or upstream hashes, together with the authoritative source used to revalidate that input before the commit point; and state every material post-side-effect failure state, compensation or invalidation behavior, and what readers may treat as authoritative after an incomplete operation. A commit point whose trusted inputs or revalidation sources cannot be enumerated is unresolved contract ambiguity.
- In Constraints and Coherence, bind compatibility or frozen-format admission to the complete prior contract plus any explicit deltas; do not accept a hand-written field subset when complete structural validity matters, and exclude fields that are private to the source authority.
- In Acceptance Semantics, distinguish expected operational or acceptance failures from programmer failures, define the safe observable failure surface, and require a stable public shape across states when callers consume one.

The Spec gate passes under this signal only when the contract makes false-PASS counterexamples testable. It must name only the relevant concerns; an ordinary change with no evidence-integrity signal does not gain extra ceremony.

`spec.md` 的唯一 revision 声明是 machine-owned `revision-set` marker 中的 `决策修订（Decision Revision）：D<n>` 与 `规格修订（Spec Revision）：S<n>`；不得在 marker 外再写旧式 D/S header。lightweight Decision 没有独立 decision.md 时，这个 D projection 与 Decision Gate Record 共同提供 D revision 的 canonical 落点。纯实现修复以重新符合当前 spec 时复用 revision；行为 contract 变化时升级 S revision 并重跑 Spec Gate；决策变化时必须先完成新的 Decision revision/Gate。Gate 通过后计算最终 artifact 的 Git blob OID，在 registry 追加 S binding、更新 current spec 并刷新 projection；lightweight Decision 的 D/S 可以分别绑定同一个 spec blob。正文只保留当前合同，旧合同通过 Revision History、registry 和 Git 追溯。

### 风险驱动的 Grill

Spec Gate 本身不自动要求 `grill-me-smartly`。只在用户明确要求对抗审查，或当前 draft 存在高不确定性/高风险信号时运行其 review phase（只审查，不 apply）：未解决的实质 contract ambiguity、跨模块或外部接口、迁移/兼容窗口、安全或数据 authority、destructive-external mutation，或 evidence-integrity contract 的 false-PASS 风险。其余边界清晰的局部 Spec delta 直接按 Spec Gate 检查，不创建 ledger。

- Grill ledger 住在 OS temp 目录，不是 package artifact，不落 `docs/implementations/<package-id>/`。
- 运行 Grill 后，把其「已收敛决策摘要」与「待用户裁决」汇报给用户；`待用户裁决` 条目直接计入上面 Spec Gate 标准里"blocking owner decisions 为零"这条——未清空前 Spec Gate 不能 PASSED，不新造阻断机制。
- 是否把已收敛的澄清写进 spec.md 正文，必须等用户明确要求 apply——这是 grill-me-smartly 自己的硬性契约（永不静默 apply），req-align 不得代为绕过。用户批准后按正常 S revision 流程原地修订。

## Workflow

1. Announce use of req-align; for a new package assign a topic slug and an immutable date-prefixed package-id, create the package directory, then run `impl_package_state.py --package <path> init --package-id <id>` once so both empty sidecars exist before any D/S registration. For a patch/follow-up identify the owning existing package-id and classify drift against current module knowledge/code; do not reinitialize it from templates.
2. Discover authoritative project knowledge before detailed clarification. If the user supplied a task-owned non-authoritative research document as the alignment input, move it into the earned-only `investigations/<topic>.md` location after package identity is fixed; leave authoritative/shared/read-only sources in place.
3. Ask one focused question at a time for unresolved intent, scope, constraints, success criteria, trade-offs, or owner decisions.
4. Run Focused PRD + Decision Research, classify whether the standalone file is earned, present the focused outcome and selected direction plus blockers, and evaluate the Decision gate before creating `spec.md`.
5. If Decision is blocked, create or update `decision.md` with provenance, readiness evidence, blockers, and owner decisions; stop without creating `spec.md`.
6. If Decision passes, persist `decision.md` for a new feature, material experience change, business capability change, or any case where the Focused PRD/choice has durable value. For a small behavior correction under an existing product definition, take the lightweight path: create `spec.md` and write the minimum product-definition pointer, delta provenance, readiness, and owner-decision evidence into its Decision Gate Record. Append reusable confirmed cross-stage findings to an already-needed `execution-findings.md`; place raw investigation material in earned-only topic files under `investigations/` and never create either artifact as empty ceremony. A `contract impact=none` implementation fix does neither.
7. Synthesize the eight-section `spec.md` only when contract impact requires it, evaluating the conditional evidence-integrity contract only when its signal is present. For a patch, reuse D/S revisions for `contract impact=none` or implementation-only drift without evaluating Spec Gate, rerun only Spec Gate for behavioral contract changes, and rerun Decision then Spec for decision-direction changes. Run `grill-me-smartly` only when the risk-driven criteria above are present or the user asks for it; otherwise evaluate the Spec Gate directly. Stop when the required gate is blocked.
8. 两道 gate 通过后，对最终 decision/spec 分别运行 `impl_package_state.py --package <path> register-revision ...`，再运行 `refresh-projections`；新 package 的两份空 sidecar 已由步骤 1 的单次 `init` 建立，`register-revision` 继续对缺失 sidecar fail closed，不承担隐式初始化。命令失败时先处理 capture gap/drift，不手改 JSON 或 marker body。artifact 与 sidecar commit 后运行 `validate --committed`，并在 Markdown handoff 报告 D/S revision set 与校验结论。随后把同一份 `spec.md` 交给 `impl-planning`，不创建第二份 spec，也不发布 tracker。

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

### Decision Direction
- Selected option and rationale:
- Open questions:

### Proposed Durable Knowledge Changes
- File / change / reason, or "None"

### Owner Decisions
- <decision, owner, and blocking effect, or "None">

### Recommended Next Step
- Persist Decision gate and proceed to Spec
- Stop for owner decision
```

## User-Facing Output

向 owner 汇报时使用 `talk-to-boss`：用人话说明需求/决策/规格对齐覆盖的功能范围、Decision 与 Spec 分别完成到哪、剩余 owner decision 数量、整体是否可进入实施计划。不要以 slug、revision 或路径开场，也不要把 blocked gate 描述成完成。

随后附 canonical handoff：topic slug、package-id/path、当前 D/S revision set、binding validation 结论、两道 gate result 与 evidence location、changed files（只在 append 时列 `execution-findings.md`）以及剩余 owner decisions。正文不得要求 owner 打开 JSON；内部 sidecar 路径只可放 machine audit metadata。artifact 写入后不粘贴全文。

When Grill was actually run, name the `grill-me-smartly` ledger path and summarize its converged decisions and any resolved owner decisions. After Spec Gate PASSED, offer `grilling` as an optional deeper adversarial follow-up if the user wants more scrutiny before handing off to `impl-planning` — a suggestion, never a requirement.

Artifact `Status` and gate `Result` must agree: a Passed status requires `PASSED`, a Blocked status requires `BLOCKED`, and neither may be inferred from prose alone.
