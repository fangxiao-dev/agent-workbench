# Generic Review Domains + P0 Gates

A project-agnostic catalog of architecture/foundation review domains. Use it to **build a baseline** when the project has none, or to sanity-check that an existing baseline isn't missing a cross-cutting concern. Keep only the domains that apply to the system under review, and rename them in the system's own language.

Each domain below lists the **review questions** (what to ask) and **common risks** (what tends to be wrong). For a fully instantiated version, see `../examples/kaispan-saas-foundation.md`.

## How to use this file

1. Pick the domains that apply. Not every system is multi-tenant or has files/jobs.
2. For each, write down the *evidence you'd need* to call it verified (schema, route, test, audit row, runtime probe).
3. Mark which domains carry a **P0 gate** — a defect there blocks acceptance outright.

## Domain adaptation

Start from the system's actual shape, not from the SaaS example. For a single-tenant internal service, tenant isolation may be `not-applicable` while idempotency, audit, queue leasing, and side-effect ordering are P0. For a public API gateway, credentials, rate limiting, request signing, replay protection, and audit may matter more than UI route protection. For a library or SDK, compatibility, error contracts, versioning, and migration safety may be the foundation.

When a domain does not apply, record why and move on. Do not manufacture a finding because a generic catalog item is absent from a system that intentionally does not have that concern.

## Domains

### Identity, accounts & sessions
- Is the external identity provider only proving *who you are*, while the app's own DB owns *what you can access*?
- How are missing/disabled accounts, no-org, suspended/closed tenants handled?
- Are human, system, worker, and API-credential actors distinguished in authorization and audit?
- Risks: trusting a JWT claim or a request header as authorization; JIT user creation auto-granting access; losing actor attribution after deletion.

### Tenant / data isolation *(multi-tenant systems — usually P0)*
- Do all tenant-owned tables carry a tenant key? Are hybrid/global tables explicitly justified?
- Do list, search, detail, update, delete, export, stats, file, worker, and audit queries all apply tenant scope?
- Do rejection paths avoid leaking cross-tenant existence, names, amounts, or status?
- Risks: API tenant-safe but export/stats/diagnostics globally readable; main record scoped but related files/audit/jobs not; raw SQL / admin client bypassing scope.

### Authorization / RBAC & temporary access
- Are membership, module/feature grants, roles, and permission definitions separated in code *and* UI?
- Does a missing grant fail closed across entry points, API, files, jobs, exports?
- Does each permission declare a scope dimension (org / unit / own), and do assignments respect it?
- Is temporary/delegated access separate from permanent roles, with expiry, scope, and audit?
- Risks: `role === "admin"` scattered checks; controller checks permission but service skips resource scope; org-level permission assigned at unit scope; delegation that never expires.

### Entitlements, plans & usage *(if the system meters or gates by plan)*
- Single source of truth for plans mapped to grants/features? Stable error codes on denial?
- Null / inactive / expired / downgraded subscription handled? Concurrent usage can't exceed a limit?
- Risks: treating a plan as a role; usage ledger good for audit but not strongly consistent; downgrade deletes data with no grace/audit.

### Files & storage *(if the system stores user files)*
- Are object keys non-enumerable and free of sensitive text? Are upload URLs signed only after auth?
- Is download authorized server-side every time (not a long-lived public URL)? Confirm validates size/mime/ownership?
- Lifecycle for pending uploads, expired exports, legal-retention files?
- Risks: signed URL outliving authorization; listing by prefix without access check; export artifacts protected weaker than source.

### Async jobs, queues & outbox *(if the system has background work)*
- Is the DB job/outbox record the source of truth and the transport just delivery?
- Does each job persist tenant, actor, idempotency key, attempts, status, error summary?
- Can two workers double-claim? Is stale-job recovery bounded and audited? Retry without duplicate side effects?
- Risks: transport succeeded but DB still "queued" (or vice-versa); external side effects inside the DB transaction; retry re-charging/re-emailing.

### External APIs, credentials & rate limiting *(if the system exposes/consumes APIs)*
- Are API credentials a distinct actor type, scoped, rotatable, revocable, audited?
- Are browser-only routes closed to API credentials by default? Multi-instance rate-limit state?
- Risks: API credential modeled as a fake user; all browser routes open to API clients; in-memory rate limit in multi-instance prod; logging raw keys.

### Audit, logging & observability *(usually P0 for money/permission/security events)*
- Business audit separated from operational logs? Auth/tenant/permission rejects produce structured, durable security audit where needed?
- Are secrets, tokens, bank data, full documents, full prompts, full PII redacted?
- Does a request id thread through API, worker, storage, queue, audit?
- Risks: stdout called "audit"; debug mode capturing raw payloads in prod; sensitive action with no customer-visible audit trail.

### Transactions & external side effects *(usually P0)*
- Do DB transactions write only business state + job/outbox + audit + credential refs?
- Are HTTP calls, emails, exports, third-party calls, webhooks performed *outside* the committing transaction?
- Idempotency for user retry, webhook retry, worker retry, double-submit? Partial failure recoverable without manual DB edits?
- Risks: email sent inside a transaction that later rolls back; calling the external API before the local write succeeds; treating "enqueued" as "committed."

### Extensibility / seams
- Do seams expose a stable interface, with a mock path *and* a real/stub path proving the boundary?
- Can a module developer consume a seam by registering an adapter/policy/handler without forking foundation code?
- Do seams preserve tenant context, actor attribution, idempotency, audit, error mapping?
- Risks: provider SDK leaking into business services; mock accidentally becoming the production contract; "future capability" surfaced in UI/API with no `design-only` status.

### Environment, deploy & ops
- Are identity/DB/storage/queue/secrets isolated across local/dev/staging/prod? Does startup fail fast on dangerous prod credentials in non-prod?
- Are CI gates (type, test, build, schema, migration, contract drift) actually enforced (not placeholder scripts)?
- Risks: non-prod accepting prod credentials; hand-built/hand-deployed artifacts; migrations assuming clean data.

### Compliance & retention *(if regulated — GDPR/GoBD/finance/health)*
- Which records are legally retained vs deletable vs anonymized? How does a deletion request reconcile with retention?
- Risks: physical delete destroying accounting/audit evidence; retaining all raw provider payloads forever; immutable audit rows duplicating PII with no anonymization plan.

### Frontend surface *(if there's a UI)*
- Which pages are real API-backed vs demo/static vs placeholder? Does route protection match API protection?
- Does the UI show capability from session/grant state while still relying on backend enforcement?
- Risks: demo copy looking like finished product; org switch changing only UI state not API headers; ordinary user seeing an admin shell before a 403.

## Generic P0 gate families

A P0 is a defect that means "do not call this foundation acceptable," independent of everything else passing. Typical families:

- Core tenant-owned data lacking a tenant key or tenant-isolation tests.
- File/content access bypassable, or long-lived public URLs.
- Money / status / permission / security actions with no audit evidence.
- External side effects inside a business transaction with no outbox/idempotency.
- Auth/identity resolver that trusts a header or JWT claim as authorization.
- CI missing schema / migration / type / test / build / contract-drift gates.
- A claimed-critical capability that is actually `design-only` or `not-found`.

Adapt this list to the system; the worked example shows a concrete P0 set.
