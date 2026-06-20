# Evidence Discipline & Status Taxonomy

The hard part of a review is not finding domains to check — it's being honest about how strong your evidence is. This file is the reference for that honesty.

## Status taxonomy

Assign exactly one status to each claimed capability:

| Status | Meaning |
| --- | --- |
| `verified` | You saw direct evidence it works *and* fails closed: code path + a negative test or runtime probe, not just a happy path. |
| `partial` | Works for the main path but a boundary (tenant, permission, error, concurrency) is unproven or weak. |
| `design-only` | Designed/documented/seam exists, but no working implementation behind it. |
| `not-found` | Claimed, but no code/schema/test/runtime evidence located. |
| `blocked` | Couldn't assess — missing access, un-runnable env, or a dependency not ready. Say *why*. |
| `not-applicable` | Out of scope for this system/phase; record so it isn't mistaken for a gap. |

## What does NOT earn `verified`

These are the everyday ways reviews fool themselves. None of them is evidence of a working boundary:

- **A hidden button.** The UI not showing an action says nothing about whether the API enforces it. Authorization lives in the backend.
- **A doc that says so.** Documentation is intent, not implementation.
- **One happy-path demo.** A single successful run with cooperative data exercises none of the failure modes.
- **Single-tenant test data.** If the fixtures contain one organization/customer, no test could have caught a cross-tenant leak.
- **Generic unit tests only.** Tests that never assert tenant scope, permission allow/deny, audit emission, or idempotency don't cover the things that actually break in production.
- **"It compiles / types pass."** Type safety is real but orthogonal to runtime authorization, isolation, and side-effect correctness.

## Status is not severity

Status says how strong the evidence is; severity says how dangerous the gap is for this review. Keep them separate:

| Status / condition | Default severity posture |
| --- | --- |
| `verified` | No finding unless the implementation creates a separate risk. |
| `partial` | Usually a follow-up or P1/P2 unless the missing boundary is a baseline P0 gate. |
| `design-only` / `not-found` | P0 only when the capability is required for launch, security, money, permissions, tenant/file access, or the PR claims production readiness for it. |
| `blocked` | Do not invent a defect; state what access/evidence is missing and whether the missing evidence blocks the decision. |
| `not-applicable` | No finding; record why it is outside this system or phase. |

This prevents two common mistakes: rubber-stamping a happy path as `verified`, and overcorrecting by turning every unverified claim into a critical defect. A missing negative test for a plausible implementation is a calibration gap; a bypassable authorization path is a defect.

## Precision guardrails

- Cite positive evidence and gaps together. Example: "`list()` and `detail()` are tenant-scoped, but `getStats()` is global."
- Do not false-flag a path that is correctly scoped just because a neighboring path is broken.
- Distinguish "not enough evidence" from "evidence of failure." Missing tests usually justify `partial`; broken code or a bypass justifies a finding.
- Use the baseline to decide whether a missing capability is out of scope, a follow-up, or launch-blocking.

## Claims vs evidence

Map every input to its real epistemic weight:

- **Contributor progress note / PR description** → *claim*. Convert each claim into an evidence row and classify it; never carry it forward as fact.
- **POC / reference repository** → domain and test *reference*, not production truth — unless the project explicitly adopted it as the runtime.
- **Prior conversation / memory** → not evidence. Re-verify against the source; cite line numbers and command output over recollection.

## Verify premises before concluding

A conclusion built on a wrong fact is a liability even when it sounds right. Before you converge on a finding:

- Check the cited anchor actually exists (section title, file path, line, config key). Section *numbers* drift — prefer titles.
- If a counterpart's premise is wrong but the practical conclusion still holds, **keep the conclusion and correct the premise** in writing, so the false reasoning doesn't become the record.
- If the premise being wrong changes the conclusion, contest it with evidence instead of agreeing for the sake of closure.

## Negative-probe checklist (Pass B)

A capability is only as isolated as its rejection paths. When a runnable environment exists, probe at least:

- Cross-tenant read and write (org A touching org B).
- Missing module/feature grant.
- Disabled membership / suspended / closed tenant.
- Expired or invalid temporary access.
- Duplicate submit / retry (idempotency).
- Export and stats endpoints under all of the above (these leak most often).

Each probe should *fail closed* and avoid leaking existence, names, amounts, or status of the forbidden resource.
