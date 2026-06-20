# Architecture Review — <target>

Updated at: <fill on copy>

A single review's working doc. Copy this template per review into a scratch area (e.g. a gitignored `…/reviews/<target>-review.md`). The durable *what-to-review* (domains, P0 gates, status taxonomy, findings format) lives in the project baseline + the `architecture-review` skill; this file only records *this* review's target, evidence, coverage, and findings. After the review, migrate durable conclusions into issues / ADRs / architecture docs and leave this as scratch.

## 1. Target

| Field | Value |
| --- | --- |
| Target PR / branch / commit | TODO |
| Review title | TODO |
| Research date | TODO |
| Reviewer(s) | TODO |
| Change size / scope | TODO |
| Runtime environment available? | TODO: yes / partial / no |
| Baseline used | TODO: path to project review baseline |

## 2. Resolved baselines

Premises confirmed for this review and not to be re-litigated.

| Premise | Decision | Evidence |
| --- | --- | --- |
| TODO | TODO | TODO |

## 3. Evidence inputs

External sources leaned on this review. Local checkout paths and one-off facts stay here, not in the baseline.

| Source | Purpose | URL / title | Local path | Branch / commit / date | Source type | Not to import |
| --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | evidence / claim / reference | TODO |

## 4. Coverage matrix

One row per claimed capability / acceptance item. Status from the taxonomy; the bar for `verified` is high (see skill `references/evidence-and-status.md`).

| Capability / acceptance item | Scope | Required by baseline? | Status | Evidence | Gap / next action |
| --- | --- | --- | --- | --- | --- |
| Example item | TODO | TODO: yes / no / out of scope | TODO: verified / partial / design-only / not-found / blocked / not-applicable | TODO | TODO |

## 5. Module map + risk flags

### Implemented (with evidence)
| Area | Code / schema / test evidence | Notes |
| --- | --- | --- |
| TODO | TODO | TODO |

### Design / seam only
| Area | Seam / contract evidence | Risk if missing |
| --- | --- | --- |
| TODO | TODO | TODO |

### First-pass risk flags
| Area | Risk | Priority | Severity rationale | Next action |
| --- | --- | --- | --- | --- |
| TODO | TODO | P0 / P1 / P2 | TODO: baseline gate / production-readiness claim / follow-up only | TODO |

## 6. Pass records

Single source of truth for review *flow* is the project baseline / skill. These sections only record evidence per pass.

### Pass A — static / structural
| Domain | Evidence | Gap / blocker | Follow-up |
| --- | --- | --- | --- |
| TODO | TODO | TODO | TODO |

### Pass B — runtime probes (negative probes are the point)
| Probe | Result | Leak? | Follow-up |
| --- | --- | --- | --- |
| cross-tenant read/write | TODO | TODO | TODO |
| missing grant | TODO | TODO | TODO |
| disabled / suspended | TODO | TODO | TODO |
| expired temp access | TODO | TODO | TODO |
| duplicate submit / retry | TODO | TODO | TODO |

### Pass C — synthesis
Separate "not implemented because out of scope" from "missing required foundation."

## 7. Findings

| Section | Content |
| --- | --- |
| Review conclusion | TODO: overall result · biggest risks · overstated claims · verified vs unverified |
| P0 findings | TODO: area · finding · evidence · risk · required action |
| P1 / P2 findings | TODO |
| Follow-up smoke tests | TODO |
| Open decisions | TODO |
