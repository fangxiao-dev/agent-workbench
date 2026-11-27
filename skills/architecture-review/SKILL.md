---
name: architecture-review
description: Use when reviewing a project's architecture — a foundation or large PR, a whole-system health audit across layers and modules, or a design/terminal checkpoint for one implementation package.
metadata:
  tags: architecture-review, layered-audit, platform-foundation, saas, tenant-isolation, PR-review, production-readiness
  platforms: Claude, Codex, Gemini
---

# Architecture Review

Run an evidence-driven review of a system's architecture, and resist the strongest failure mode of reviews: **rubber-stamping**. A review earns its keep only when it separates what is *verified working* from what is merely *claimed, demoed, or designed*.

The skill is a **methodology**, deliberately domain-agnostic. The project supplies the domain content (a baseline of *what to review*, a map of its layers); the skill supplies the discipline (*how to review without fooling yourself*).

## Pick the mode first

| Mode | Use when | Read |
| --- | --- | --- |
| **Foundation / PR review** | A foundational PR, a launch or production-readiness call, or "is this slice actually solid?" | The workflow below |
| **System layered audit** | "How healthy is the system?", "which layer/module is worst?", planning what to fix first | [references/system-audit.md](references/system-audit.md) + [references/layer-model.md](references/layer-model.md) |
| **Package checkpoint** | A design gate or terminal gate of one implementation package asks for an architecture check | [references/package-checkpoint.md](references/package-checkpoint.md) |

All three share the core below: baseline vs instance, the status taxonomy, evidence discipline, and fail-closed P0 gates. Match depth to the ask: a quick check of one guard gets a compact inline answer with the same discipline, no scratch files.

Completion criterion: the mode is named, and its reference (if any) has been read before judging.

## The one idea: baseline vs instance

Keep two kinds of artifact, and never let them bleed together:

| Layer | What it is | Lifetime |
| --- | --- | --- |
| **Baseline** | The catalog of *review domains* + *P0 gates* (and, for layered audits, the project's layer map and module list) — "what must always be checked." | Durable; rarely changes |
| **Instance** | One review's target, evidence, coverage, scores, and findings. | One-off; lives in a scratch area |

Pour one review's findings into the baseline and it rots into a changelog; re-derive the domains every review and coverage drifts. So a review *copies* the blank instance template, fills it, and only its **durable conclusions** graduate into issues / ADRs / guard tests — the instance stays scratch.

- Blank instance template: [assets/review-template.md](assets/review-template.md).
- No baseline yet: build one from [references/review-domains.md](references/review-domains.md) (domains) and [references/layer-model.md](references/layer-model.md) (layers), naming only what applies to *this* system.

## Foundation / PR review workflow

### Step 0 — Establish the baseline

Find the project's review baseline. Read it before judging — it tells you the coverage you owe and which missing evidence is launch-blocking rather than merely incomplete.

### Step 1 — Open an instance and scope the review

Copy the template to a scratch path. Fill in:

- **Target**: PR / branch / commit, change size, whether a runnable environment exists.
- **Resolved baselines**: premises you've confirmed and will *not* re-litigate.
- **Evidence inputs**: every source you'll lean on. A contributor's progress note is a **claim**, not evidence; a POC is inspiration, not production truth; local paths and one-off facts stay in the instance. Full rules: [references/evidence-and-status.md](references/evidence-and-status.md).
- **Claim ledger**: every PR / user claim becomes a capability row — required by baseline?, evidence, missing negative evidence, status.

### Step 2 — Run the passes (cheap → expensive)

- **Pass A — static / structural.** Schema & migrations, routes / contracts, guards, service scoping, tests, CI, config. Build the module map and map each claim to evidence. Most P0 gaps surface here. Also check the outer layers for parallel implementations of the same capability ([layer-model.md](references/layer-model.md) symptoms I1/P1).
- **Pass B — runtime probes** (only for high-risk paths, only with a runnable env). Seed **≥2 tenants and ≥2 users**, one happy path, then the **negative** probes: cross-tenant read/write, missing grant, disabled membership, suspended org, expired access.
- **Pass C — synthesis.** Convert gaps into P0 / P1 / P2. Separate *"out of scope"* from *"missing required foundation"*.

### Step 3 — Findings output

```
## Review conclusion
Overall result · target · biggest risks · overstated claims · verified vs unverified capabilities
## P0 findings        (area · finding · evidence · risk · required action)
## P1 / P2 findings   (area · finding · evidence · risk · suggested action)
## Follow-up smoke tests
## Open decisions
```

Completion criterion: every claim-ledger row has a status, and every P0 gate in the baseline is explicitly checked.

## Status taxonomy — the anti-rubber-stamp core

Every claimed capability gets exactly one status: `verified` · `partial` · `design-only` · `not-found` · `blocked` · `not-applicable`.

Do **not** mark something `verified` just because a UI hides the button, a doc says so, one happy-path demo runs, test data has one tenant, or only generic unit tests exist. More: [references/evidence-and-status.md](references/evidence-and-status.md).

## Precision guardrail

Cite positive evidence as well as gaps: if `list()` and `detail()` are scoped but `stats()` is not, say exactly that. `unverified` means "not enough evidence," not "bug." Escalate to P0 only when the baseline, a readiness claim, or defect risk makes the gap blocking.

## P0 gates (fail-closed)

Some defects mean "do not call this acceptable," no matter what else works — cross-tenant access, auth bypass, external side effects without idempotency, missing audit on money/permission changes. Check each baseline P0 explicitly and **fail closed** when evidence is missing.

## Verify premises before you conclude

When you cite a fact — a line number, a config value, a subagent's claim — check it against the source. If a premise is wrong but the conclusion holds, keep the conclusion and **correct the premise**. If the conclusion falls, downgrade it and say why (e.g. "a DB trigger already blocks the delete").

## Lifecycle

The instance is scratch. Afterwards, graduate durable conclusions into issues / ADRs / guard tests / architecture docs. Don't silently edit the reviewed system to "fix" findings unless asked — the deliverable is the findings.

## Worked examples

- [examples/kaispan-saas-foundation.md](examples/kaispan-saas-foundation.md) — foundation review of a multi-tenant SaaS: domains, P0 gates, grading a large PR.
- [examples/kaispan-layered-audit.md](examples/kaispan-layered-audit.md) — system layered audit of the same product: layer map, slicing, verification downgrades, heatmap, remediation order.
