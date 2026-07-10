# Documentation Routing Taxonomy

Use this reference when the short routing rules in `SKILL.md` are not enough.

## Documentation Homes

| Destination | Purpose |
|---|---|
| `docs/hands-on-knowledge/entry-map.md` | Routing and search strategy. Keep it as a map, not a full index. |
| `docs/hands-on-knowledge/implementation/` | Reusable implementation patterns, migration notes, verification notes, integration practices, and maintained implementation references. |
| `docs/hands-on-knowledge/debug/` | Investigations, runbooks, known failure modes, recovery procedures, postmortems, platform traps, and diagnostic references. |
| `docs/top-level-knowledge/` top-level PRDs | Product/journey-level intent: positioning, users, journeys, global scope/non-scope, outcomes, and success criteria. Before journey restructuring is complete, register new `top-level-prd` deltas as pending instead of expanding existing large PRDs. |
| `docs/module-knowledge/<module>/prd.md` | Module-level intent (`module-prd`): why the module exists and which value slice it owns. Create lazily; use `_pending.md` until minimum content and evidence are sufficient. |
| `docs/module-knowledge/<module>/spec.md` | Module behavior contract (`module-spec`): interfaces, states, boundaries, failure/recovery semantics, and directly verifiable acceptance behavior. A subdomain contract may be the narrower home. |
| `CONTEXT.md` | Canonical project language and vocabulary (`context-language`). |
| `docs/top-level-knowledge/` | Stable project, architecture, product, domain, or technology-stack facts that are not better represented by a PRD or module PRD. |
| `docs/exchange/req-*.md` | Requirement inbox, change request, or mini-PRD draft. Use these to capture new or changed requirements, discussion context, and owner decisions before they are merged into stable docs. |
| `docs/implementations/<slug>/` | Point-in-time change design, spec delta, execution plan, findings, and gate evidence. It is an event record, not the maintained module contract. |
| `AGENTS.md` or `CLAUDE.md` | Mandatory operating rules that must be seen in every session. Choose the repository's canonical agent entry file for the active host. |

Source material may come from conversation context, completed plans, handoffs, logs, code review notes, verification output, changed files, temporary notes, `docs/impl-plans/`, `docs/exchange/`, repo-root `exchange/`, or retrospectives. These are sources, not final homes.

## Atomic Item Triage

Before choosing a home, split the source into durable knowledge items. The unit of routing is not "one incident," "one PR," "one conversation," or "one deployment"; it is the smallest reusable lesson that has a stable future lookup path.

Ask these questions for each candidate:

1. What would a future developer search for when they need this?
2. Which source of truth keeps it correct: code/tests, deploy script, PRD, design doc, runbook, or operating rule?
3. Is the action diagnostic, implementation-facing, verification/release-facing, product-facing, or mandatory process?
4. Would merging it with a neighboring lesson make either one harder to find or maintain?
5. If implementation were replaced but user value stayed the same, must it still hold? If yes, route it as intent.
6. Can tests, interfaces, state queries, or failure drills directly verify it? If yes, route it as a behavior contract.

If two lessons differ on any of those axes, route them separately and cross-link if useful.

Examples:

- A production-like preview incident can yield a debug runbook for domain/CORS/deployment verification, plus a frontend implementation pattern for error redaction and stale state cleanup. The former is found by someone asking "which environment am I really testing?"; the latter is found by someone changing UI error handling.
- A migration PR can yield an implementation pattern for adapter boundaries, a verification note for smoke commands, and a requirement update for accepted behavior. Do not bury all three under the migration timeline.
- A failed release can yield a mandatory deploy rule in `AGENTS.md` or a deploy skill, plus a debug recovery runbook. The mandatory rule should not be hidden inside the runbook if every future session must see it.

## Requirement Lifecycle

Use this flow when the input is a new requirement, changed requirement, PRD cleanup, or product decision rather than implementation/debug experience:

1. Capture new or changed requirements in `docs/exchange/req-*.md` when they still need review, traceability, or owner decisions.
2. Merge accepted journey/product intent into a top-level PRD, and accepted module intent into the relevant `docs/module-knowledge/<module>/prd.md`.
3. Use `docs/implementations/<slug>/` when a point-in-time change needs design or execution planning.
4. Promote verified current behavior into the relevant module `spec.md` or subdomain contract.
5. Route only reusable implementation or debugging lessons with reverse-lookup value into `docs/hands-on-knowledge/`.

Treat `req` files as inbox and audit records, not final long-term PRDs. If a statement contains both
why and how, split it into separate intent and contract deltas instead of copying it into both homes.

Create a module PRD only when its first content has evidence from a top-level PRD, approved design,
owner decision, or confirmed gate, and can establish Purpose, users or journeys, Outcomes,
Scope/Non-goals, plus links to the top-level PRD and module spec. Code alone is not intent evidence;
insufficient content remains in `docs/module-knowledge/_pending.md`.

## Examples

Input: `把这次 API schema refactor 的经验沉淀一下`

Route: `impl-knowledge-maintainer`

Reason: implementation/refactor lessons usually belong under `docs/hands-on-knowledge/implementation/`.

Input: `把刚才排查部署失败的过程整理成 runbook`

Route: `debug-knowledge-maintainer`

Reason: diagnostic and recovery procedures belong under `docs/hands-on-knowledge/debug/runbooks/`.

Input: `这次实现里发现了一个验证命令模式，也踩了一个预览链接 404 的坑，帮我沉淀`

Route: both

Reason: verification command pattern routes to implementation knowledge; preview-link 404 diagnosis routes to debug knowledge.

Input: `把项目背景写进 top-level docs`

Route: `docs/top-level-knowledge/`

Reason: stable project context should not be forced into implementation or debug hands-on knowledge.

Input: `新增一个 reporting workflow 需求，先帮我沉淀一下`

Route: `docs/exchange/req-*.md` first; later merge accepted stable behavior into the relevant product or module PRD.

Reason: a new requirement needs inbox traceability and owner decision history before becoming durable PRD content.

Input: `这个 PRD 太大了，帮我拆成顶层和模块 PRD`

Route: top-level PRDs plus relevant `docs/module-knowledge/<module>/prd.md` files.

Reason: PRD structure is a product documentation concern, not hands-on implementation or debug knowledge.

Input: `把“用户重复注册时必须走账号恢复流程”沉淀成 hands-on pattern`

Route: no hands-on write; split durable intent into the relevant PRD and verifiable behavior into the relevant module spec unless a real trap, recovery path, or missing reverse-lookup need emerges.

Reason: this is primarily a requirement/flow rule. Without extra trap or recovery value, it is not yet reusable hands-on knowledge.

Input: `把这次反复踩到的 API migration trap 沉淀一下`

Route: `impl-knowledge-maintainer` only if the note explains a reusable migration trap, safe pattern, or verification shortcut beyond ordinary design documentation.

Reason: recurring implementation traps can be hands-on knowledge, but ordinary API design decisions belong in design docs.

## Manual Routing Fixtures

Use these fixtures for manual acceptance after changing the routing rules.

| Input | Expected destination | Create/update durable file? |
| --- | --- | --- |
| "Checkout must reject a stale price snapshot and expose a retryable conflict." | `module-spec` -> `docs/module-knowledge/checkout/spec.md` | Yes, update the existing contract. |
| "Favorites exists so customers can resume recurring purchase intent across sessions." | `module-prd` -> `docs/module-knowledge/favorites/prd.md` | Only when first-file evidence and minimum content pass; otherwise `_pending.md`. |
| "Suppliers need one journey from catalog setup through first accepted order." | `top-level-prd` | Pending only until the journey-level PRD restructure is complete. |
| "Use Customer and Supplier as the canonical actor names across the project." | `context-language` -> `CONTEXT.md` | Yes, update the canonical vocabulary. |
| "For this migration, introduce an adapter before switching the persisted schema." | change design -> `docs/implementations/<slug>/` | Yes, in the active implementation package; not in evergreen PRD/spec yet. |
| "The refactor only renamed local helpers and changed no durable behavior or intent." | `none` with reason in the gate | No. |
