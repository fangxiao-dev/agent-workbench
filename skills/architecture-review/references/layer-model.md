# Layer Model

A generic six-layer lens for application systems. Map each layer to the project's real directories in the project baseline (see `../examples/kaispan-layered-audit.md` for one mapping). Layers that do not exist in a system are `not-applicable`, not findings.

Direction rule: **the lower the layer, the more stable it should be and the more strictly it should exist only once.** Upper layers change with screens and callers; lower layers should not.

| # | Layer | Owns | Does not own |
| --- | --- | --- | --- |
| 1 | **Page** (UI) | What the user sees, which actions render, client state | Business rules, cross-entity aggregation, authorization decisions |
| 2 | **Interface** (contract) | Routes, DTOs, generated client, error codes, idempotency headers | Caller-specific shapes per permission set |
| 3 | **Orchestration** (service) | One operation's flow: scope check → read → call rules → transactional write → audit → side effects | Business thresholds, formulas |
| 4 | **Rules** (domain) | Pure business judgements: calculations, thresholds, state transitions, eligibility | DB, request, clock acquisition |
| 5 | **Data** | Schema, migrations, tenant-scoped access, integrity constraints | Business rules |
| 6 | **Foundation** (platform) | Identity, tenant context, RBAC/scope, audit, files, jobs, clock, config | Module-specific logic |

## Health criteria and symptoms per layer

Each symptom has an ID so findings and evals can cite it. Treat these as *what to look for*, not as automatic findings — confirm each with evidence.

### 1. Page

Healthy: one component per business surface; actions gated per capability/row, not per page; data comes from contract-shaped queries, not client-side stitching; shared UI primitives are used.

- **P1 Parallel view per permission set** — a `*-minimal` / "lite" component re-implements the same surface (list, send/resend, upload, confirm) for a narrower permission. Same state machine maintained twice; mixed permissions can render both on one page.
- **P2 Page-level gating** — a whole route is gated by one permission, so a user with a different permission needing one section gets a *copied* component on another page instead of a section-level gate.
- **P3 Client-side stitching** — the client loops over units/pages (`Promise.all` per store, paginate-to-complete) to build an organization-level list the API should provide. Usually a missing interface-layer read (I2).
- **P4 Mirrored business values** — limits, enums, formulas or code tables copied from the server without a contract test; drift becomes user-visible (client accepts what server rejects, totals disagree).
- **P5 Divergent infrastructure per feature** — upload protocol, auth shell, request headers, scope/store pickers re-written per page; inconsistent "no access" behaviour.
- **P6 Dead or demo surfaces** — unreachable pages, demo routes without env gating, mock paths as the default branch.

### 2. Interface

Healthy: one entry per resource; the server projects fields/actions by the caller's capabilities; organization-level reads exist where callers need them; stable error codes; idempotency on side-effecting writes; the generated contract matches the controllers.

- **I1 Parallel endpoint or shape per permission** — a narrow DTO/route (or a query flag returning a different shape) exists only because a permission set cannot see the full one. The fix direction is **single entry + server-side capability projection**: one resource, fields and per-row action flags trimmed by what the caller may do.
- **I2 Missing aggregate read** — only per-unit routes exist for an organization-scoped capability, pushing stitching to the client (P3).
- **I3 Contract drift** — generated OpenAPI/client lags the controllers, or responses are hand-typed around the generated SDK.
- **I4 Idempotency gaps** on writes with money, permission, or external effects.
- **I5 Bloated controllers** owning many unrelated resources under one root.

### 3. Orchestration

Healthy: shared constraints live in one write channel (transaction + concurrency + audit + idempotency), not in every caller's memory; one service per capability; services sized by responsibility.

- **O1 Convention by discipline** — a correctness constraint (e.g. "bump the org row inside the serializable transaction", "claim idempotency after authorization") is a separate call each writer must remember. Leaks repeat; each fix finds the next leak. Fix direction: enforce in the channel/helper, plus an architecture guard test.
- **O2 Bypassing a platform seam** — direct writes to the job table, ad-hoc file records and signed URLs, direct `process.env` reads, instead of the queue port / protected-file service / config package.
- **O3 Parallel orchestration** — two services compute the same summary or workflow (e.g. two to-do aggregations with different scoping).
- **O4 God services** — a single service file in the thousands of lines owning many capabilities.
- **O5 Mechanical splits** — files split only to satisfy a size limit, without a sharper responsibility; fragmentation without abstraction.

### 4. Rules

Healthy: pure functions, clock and parameters passed in, one module per topic, rule IDs traceable to the rule book, an architecture guard against rules leaking outward.

- **R1 Rule leakage outward** — thresholds, formulas, code tables inside services, controllers, prompts, or the client.
- **R2 Duplicated rule** — the same rule copied into several modules (e.g. a tax-code parser in four places).
- **R3 Rules in prompt text** — business/tax rules expressed only as natural-language prompt content, untestable and unversioned.
- **R4 Asymmetric or ad-hoc numerics** — money rounding, unit conversion, date boundaries implemented per call site; sign-dependent rounding.
- **R5 Clock bypass** — `new Date()` / natural day where the business clock or business day is required.
- **R6 Dependency cycles** between rules and validation/DTO modules.

### 5. Data

Healthy: tenant key on every tenant table; tenant-scoped client enforced; admin access frozen by a baseline; append-only where the law or audit requires it.

- **D1 Business rules inside the data client** (state transitions, writable-field allowlists in a shared package).
- **D2 Guardrail lists that drift** from their names or the documented policy (verify the real enforcement — a DB trigger may already cover it).
- **D3 Parallel persistence** of the same concept.
- **D4 Migration hygiene** (colliding timestamps, unordered names).

### 6. Foundation

Healthy: one way to authenticate, resolve tenant, check scope, audit, store files, enqueue jobs, read the clock and config; modules plug in without editing a central file.

- **F1 Missing standard for a recurring need** — e.g. RBAC answers "can / in which scope" but offers no standard for "project fields and action flags by capability", so every module invents one (drives I1/P1).
- **F2 Inconsistent propagation** — a request-scoped value (business clock, actor) dropped on one code path.
- **F3 Central manual registries** that every new module must edit.
- **F4 Config not centralized** — fallbacks that differ per call site; fail-open defaults.

## Cross-layer causality

Symptoms usually *surface* one layer above where they were *caused*. Record both:

- P1/P3 surface in the page layer but are typically caused by I1/I2, which in turn are caused by F1.
- O1 leaks surface as data-integrity bugs but are caused by a channel that does not enforce its own contract.

When scoring, charge the *surface* layer for the symptom; when ordering fixes, start at the *cause* layer.
