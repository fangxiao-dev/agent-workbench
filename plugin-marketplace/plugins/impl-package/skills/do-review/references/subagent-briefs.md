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
- User review-depth preference:
- Canonical ledger artifact (read-only):

Known findings ledger:
<read the previous round's canonical ledger from the artifact; write "none yet" for round 1>

Return format:
- Normal review: natural-language candidates with enough location, evidence, impact, and suggested handoff for the parent to record and verify.
- Closure verification: PASS/FAIL/UNCERTAIN per issue.
- Every finding needs evidence.
- Do not mutate files, issues, git state, data, or external systems.
```

## Generic Leaf Reviewer Brief

```text
Read and use exactly the assigned reviewer skill path. Do not resolve a similarly named skill yourself.

You are a leaf reviewer in a topology already resolved by the parent do-review run. Do not invoke do-review, do not run its subagent gate, do not dispatch subagents, and do not re-evaluate reviewer topology or capacity. Follow the assigned skill's primary review intent and handoff guidance; it is not an exclusive capability boundary.

Review exactly the supplied complete diff and fixed comparison point. Do not inspect, request, or use findings produced by other tracks in the current round. This restriction remains in effect when the parent runs reviewers in phases.

Return natural-language candidates with enough location, evidence, impact, and suggested handoff for the parent to record and verify. You may surface an evidence-backed cross-domain candidate, but the parent owns cross-track attribution, deduplication, classification, loop convergence, and the overall verdict.

The canonical ledger artifact is owned by the main session. Read it only; never create, edit, replace, classify, or append to the file. Do not treat a copied prompt excerpt as a second source of truth.

For each finding:
- cite evidence;
- prefer file:line evidence when reviewing code;
- explain the concrete failure mode or broken invariant;
- state the risk urgency described by the assigned skill without making final classification;
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
The supplied artifact is the prior round's canonical ledger. Do not re-report those findings.

Read the prior round from the supplied `Canonical ledger artifact` path. The parent will update that same file after all tracks finish; do not write a round-specific ledger.

Report a related finding only if it:
- breaks a different invariant;
- affects a different owner or release decision;
- changes severity/classification;
- gives narrower evidence that changes the fix.

Otherwise mark it duplicate/refinement and keep it short.
```
