# Do Review Subagent Briefs

Copy the common block and exactly one applicable review brief. Add the anti-duplicate block only after round 1. Do not append another track's output or same-round summary.

## Common Context Block

```text
Review target:
- Repo/worktree:
- Target revision or PR:
- Comparison point input:
- Resolved base SHA:
- Resolved head SHA:
- Diff command/range:
- Included commits:
- Scope source / package roots:
- Mode:
- Round:
- Track label:
- Assigned reviewer skill:
- Assigned reviewer skill path:
- Repository standards sources:
- Issue/Decision/Spec/Plan/DAG sources:
- Out of scope:
- User policy:

Known findings ledger:
<paste only the previous round's canonical ledger; write "none yet" for round 1>

Return format:
- Normal review: findings in ledger schema.
- Closure verification: PASS/FAIL/UNCERTAIN per issue.
- Every finding needs evidence.
- Do not mutate files, issues, git state, data, or external systems.
```

## Generic Leaf Reviewer Brief

```text
Read and use exactly the assigned reviewer skill path. Do not resolve a similarly named skill yourself.

You are a leaf reviewer in a topology already resolved by the parent do-review run. Do not invoke do-review, do not run its subagent gate, do not dispatch subagents, and do not re-evaluate reviewer topology or capacity. Perform only the review role defined by the assigned reviewer skill.

Review exactly the supplied complete diff and fixed comparison point. Do not inspect, request, or use findings produced by other tracks in the current round. This restriction remains in effect when the parent runs reviewers in phases.

Return results in the do-review ledger schema. The parent owns cross-track deduplication, evidence verification, classification, loop convergence, and the overall verdict.

For each finding:
- cite evidence;
- prefer file:line evidence when reviewing code;
- explain the concrete failure mode or broken invariant;
- classify severity from the risk described by the assigned skill;
- avoid known duplicates unless you add materially new evidence or impact.
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
The ledger below is the prior round's canonical ledger. Do not re-report those findings.

Report a related finding only if it:
- breaks a different invariant;
- affects a different owner or release decision;
- changes severity/classification;
- gives narrower evidence that changes the fix.

Otherwise mark it duplicate/refinement and keep it short.
```
