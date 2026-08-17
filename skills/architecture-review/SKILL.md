---
name: architecture-review
description: Use when reviewing a project's architecture, including its module boundaries, dependency structure, runtime composition, or foundational design decisions.
metadata:
  tags: architecture-review, platform-foundation, saas, tenant-isolation, audit, PR-review, production-readiness
  platforms: Claude, Codex, Gemini
---

# Architecture Review

Run an evidence-driven review of a system's architecture or platform foundation, and resist the strongest failure mode of reviews: **rubber-stamping**. A review earns its keep only when it separates what is *verified working* from what is merely *claimed, demoed, or designed*.

This skill is a **methodology**, deliberately domain-agnostic. The project supplies the domain content (a baseline of *what to review*); the skill supplies the discipline (*how to review without fooling yourself*). A full worked example for a multi-tenant SaaS foundation ships in [examples/kaispan-saas-foundation.md](examples/kaispan-saas-foundation.md).

## The one idea: baseline vs instance

Keep two kinds of artifact, and never let them bleed together:

| Layer | What it is | Lifetime |
| --- | --- | --- |
| **Baseline** | The catalog of *review domains* + *P0 gates* for this class of system — "what must always be checked." | Durable; rarely changes |
| **Instance** | One review's target, evidence, coverage, and findings. | One-off; lives in a scratch area |

Why this matters: pour one PR's findings into the baseline and it rots into a changelog; re-derive the domains every review and coverage drifts. So a single review *copies* the blank instance template, fills it, and at the end only its **durable conclusions** graduate into issues / ADRs — the instance itself stays scratch.

- Blank instance template: [assets/review-template.md](assets/review-template.md) — copy it per review.
- If the project has **no baseline yet**, build one first from [references/review-domains.md](references/review-domains.md) (a generic domain catalog you adapt to the system), then proceed.

## Match the depth to the ask

Use the full baseline + instance workflow for broad foundation reviews, launch / production-readiness calls, or large PRs that claim multiple platform capabilities. For a small slice ("quick check this guard" / "does this repository look scoped?"), do a compact inline review with the same evidence discipline: claims, status, findings, and follow-up probes. Do not create scratch review files unless the user asked for artifacts or the review is broad enough to benefit from them.

## Workflow

### Step 0 — Establish the baseline

Find the project's review baseline (a checklist of domains + P0 gates). If none exists, draft one from [references/review-domains.md](references/review-domains.md), naming the domains that actually apply to *this* system. Read the baseline before judging — it tells you the coverage you owe and which missing evidence is launch-blocking rather than merely incomplete.

### Step 1 — Open an instance and scope the review

Copy [assets/review-template.md](assets/review-template.md) to a scratch path (e.g. a gitignored `…/reviews/<target>-review.md`). Fill in:

- **Target**: PR / branch / commit, title, change size, whether a runnable environment exists.
- **Resolved baselines**: premises you've confirmed and will *not* re-litigate (e.g. "identity provider is X", "manual subscription is the v0.1 baseline").
- **Evidence inputs**: every external source you'll lean on. The discipline (full rules in [references/evidence-and-status.md](references/evidence-and-status.md)):
  - A contributor's progress note is a **claim**, not evidence.
  - A POC / reference repo is domain inspiration, not production truth — unless explicitly adopted as the runtime.
  - Local checkout paths and one-off facts belong in the instance, never the baseline.
- **Claim ledger**: extract every PR / user claim into a capability row before judging. For each row, record whether it is required by the baseline, what evidence exists, what negative evidence is missing, and the status.

### Step 2 — Run the passes (cheap → expensive)

Record evidence / gap / blocker per domain as you go.

- **Pass A — static / structural** (no running system). Read schema & migrations, routes / API contracts, guards, service-layer scoping, tests, CI, config. Build the module map and map each claim to evidence. This is where most P0 gaps actually surface; do it first and thoroughly.
- **Pass B — runtime probes** (only after Pass A flags high-risk paths, and only if a runnable env exists). Seed **≥2 tenants and ≥2 users**, run one happy path, then the **negative** probes: cross-tenant read/write, missing grant, disabled membership, suspended org, expired/invalid access. Negative probes are the whole point — a green happy path proves almost nothing.
- **Pass C — synthesis**. Convert coverage gaps into P0 / P1 / P2 findings. Crucially, separate *"not implemented because out of scope"* from *"missing required foundation"* — conflating them is how scope-creep and real gaps both get mis-graded.

### Step 3 — Findings output

Use this fixed structure so reviews are comparable over time:

```
## Review conclusion
Overall result · target · biggest risks · overstated claims · verified vs unverified capabilities

## P0 findings        (area · finding · evidence · risk · required action)
## P1 / P2 findings   (area · finding · evidence · risk · suggested action)
## Follow-up smoke tests   (specific manual/automated probes still owed)
## Open decisions     (product/architecture choices blocking a final judgment)
```

## Status taxonomy — the anti-rubber-stamp core

Every claimed capability gets exactly one status, and the bar for `verified` is deliberately high:

`verified` · `partial` · `design-only` · `not-found` · `blocked` · `not-applicable`

Do **not** mark something `verified` just because:

- a UI hides the button (hiding ≠ enforcing);
- a doc says the capability exists;
- one happy-path demo runs;
- the test data has only one tenant / customer;
- only generic unit tests exist, with no tenant / permission / audit / idempotency coverage.

Full guidance and more anti-patterns: [references/evidence-and-status.md](references/evidence-and-status.md).

## Precision guardrail

Calibrated reviews are stricter *and* fairer. Cite positive evidence as well as gaps: if `list()` and `detail()` are scoped but `stats()` is not, say exactly that. Treat `unverified` as "not enough evidence to claim verified," not as proof of a bug. Escalate to P0 only when the baseline, production-readiness claim, or defect risk makes the gap launch-blocking.

## P0 gates (fail-closed)

Some defects mean "do not call this foundation acceptable," no matter what else works — e.g. cross-tenant data access, auth bypass, external side effects with no idempotency, missing audit on money/permission changes. The project's baseline names its own P0 set; the review must check each one explicitly and **fail closed** when evidence is missing rather than assuming it's fine. Generic P0 families are listed in [references/review-domains.md](references/review-domains.md).

## Verify premises before you conclude

A review that repeats a wrong premise is worse than no review. When you cite a fact — a line number, a section anchor, a config value — check it against the source rather than memory. If someone else's premise is wrong but the conclusion still holds, keep the conclusion and **correct the premise**; don't let false reasoning become the record.

## Lifecycle

The instance is scratch. After the review: migrate durable decisions into issues / ADRs / architecture docs, and leave (or discard) the instance. Don't silently edit the reviewed system's docs or code to "fix" findings unless asked — the deliverable is the *findings*, not quiet rewrites.

## Worked example

[examples/kaispan-saas-foundation.md](examples/kaispan-saas-foundation.md) applies all of the above to a real multi-tenant B2B SaaS foundation: its ~16 review domains, its P0 gate list, and how a large foundational PR was graded (verified vs design-only vs scope-creep). Use it as the concrete model for adapting the generic catalog to a specific system.
