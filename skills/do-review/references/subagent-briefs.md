# Do Review Subagent Briefs

Copy the common block plus exactly one track brief. If the assigned reviewer skill is `code-review` or `module-review`, append the matching default lens addendum. Add the anti-duplicate block only after round 1.

## Common Context Block

```text
Review target:
- Repo/worktree:
- Target revision or PR:
- Base/head:
- Scope source / package roots / included commits:
- Mode:
- Round:
- Track label:
- Assigned reviewer skill:
- Out of scope:
- User policy:

Known findings ledger:
<paste ledger; write "none yet" for round 1>

Return format:
- Normal review: findings in ledger schema.
- Closure verification: PASS/FAIL/UNCERTAIN per issue.
- Every finding needs evidence.
- Do not mutate files, issues, git state, data, or external systems.
```

## Generic Reviewer Track Brief

```text
Use the assigned reviewer skill.

Review the target in scope. Follow the assigned skill's review method, but return results in the do-review ledger schema so the main session can deduplicate and classify consistently.

Execute the assigned skill's full required reviewer topology. A track is a skill assignment, not a one-agent limit. If your skill requires independent child reviewers, dispatch every required child role and preserve its source/axis in the returned evidence. If capacity requires phasing, report the phase order; do not omit a child review.

For each finding:
- cite evidence;
- prefer file:line evidence when reviewing code;
- explain the concrete failure mode or broken invariant;
- classify severity from the risk described by the assigned skill;
- avoid known duplicates unless you add materially new evidence or impact.
```

## code-review Default Lens Addendum

```text
Default lens when the assigned skill is code-review:

Lens:
- reachable code-path bugs;
- local business invariants;
- error handling and partial failures;
- missing regression tests;
- local/mock behavior that can hide real bugs.

Avoid broad architecture unless it is directly visible in code.
Avoid known duplicates unless you add materially new evidence.

For each finding:
- cite file:line evidence;
- explain the concrete failure path;
- say whether a test exists or is missing;
- classify severity from code-path risk.
```

## module-review Default Lens Addendum

```text
Default lens when the assigned skill is module-review:

Run the skill's two independent axes: Standards and Spec. Return them as separate source labels (`Track B (module-review/Standards)` and `Track B (module-review/Spec)`); do not merge their findings before the main-session ledger step.

Lens:
- cross-module contracts;
- transaction semantics and crash points;
- replay, idempotency, and concurrency;
- runtime modes and environment matrix;
- external system boundaries;
- release and rollback risk.

Avoid style/local refactors unless they hide system risk.
Avoid known duplicates unless you add materially new impact.

For each finding:
- cite evidence where possible;
- name the broken invariant or seam;
- describe the observable failure mode;
- classify severity from business/release risk.
```

## Closure Verification Brief

```text
Use the assigned skill, but run closure verification only.

For each assigned issue/finding:
1. Read the issue body and acceptance criteria.
2. Inspect only code/tests needed to verify those criteria.
3. Do not report unrelated new problems.
4. Return PASS, FAIL, or UNCERTAIN.

For FAIL:
- quote the unsatisfied acceptance criterion;
- cite file:line evidence;
- state the minimal remaining work.

For UNCERTAIN:
- state exactly what evidence is missing.
```

## Round-N Anti-Duplicate Addendum

```text
Known findings are already recorded below. Do not re-report them.

Report a related finding only if it:
- breaks a different invariant;
- affects a different owner or release decision;
- changes severity/classification;
- gives narrower evidence that changes the fix.

Otherwise mark it duplicate/refinement and keep it short.
```
