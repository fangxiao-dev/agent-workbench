# Review Orchestrator Subagent Briefs

Copy and fill these briefs when dispatching subagents. Keep the two tracks intentionally different.

## Common Context Block

```text
Review target:
- Repo/worktree:
- Target revision or PR:
- Base/head:
- Mode:
- Round:
- Out of scope:
- User policy:

Known findings ledger:
<paste ledger; write "none yet" for round 1>

Return format:
- PASS/FAIL/UNCERTAIN per issue for closure verification, or findings in ledger schema for normal review.
- Every finding needs evidence.
- Do not mutate files, issues, git state, data, or external systems.
```

## code-review Track Brief

```text
Use the code-review skill.

Lens:
- reachable code-path bugs;
- local business invariants;
- error handling and partial failures;
- tests and missing regressions;
- local/mock behavior that can hide real bugs;
- maintainability only when it affects correctness or verification.

Do not spend time on broad architecture unless it is directly visible in code.
Do not duplicate known findings unless you add materially new evidence.

For each finding:
- cite file:line evidence;
- explain the concrete failure path;
- state whether a test exists or is missing;
- classify severity from the code-path risk.
```

## review Track Brief

```text
Use the review skill.

Lens:
- cross-module seams;
- transaction semantics and crash points;
- replay, idempotency, and concurrency;
- runtime modes and environment matrix;
- external system boundaries;
- release and rollback risk.

Do not spend time on style or local refactors unless they hide a system risk.
Do not duplicate known findings unless you add materially new impact.

For each finding:
- cite evidence where possible;
- name the broken invariant or seam;
- describe the observable failure mode;
- classify severity from business/release risk.
```

## Closure Verification Brief

Use this instead of the normal finding-hunt brief when the user says not to find new issues.

```text
Use the assigned skill, but run closure verification only.

For each assigned issue/finding:
1. Read the issue body and acceptance criteria.
2. Inspect only the code/tests needed to verify those criteria.
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

Append this from round 2 onward.

```text
Known findings are already recorded below. Do not re-report them.

You may report a related finding only if one of these is true:
- it is a different broken invariant;
- it affects a different owner or release decision;
- it changes severity/classification;
- it provides narrower evidence that changes the fix.

Otherwise mark it as duplicate/refinement and keep it short.
```

