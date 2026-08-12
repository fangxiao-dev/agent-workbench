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
- Review phase: initial / finding-closure / terminal-final
- Round:
- Track label:
- Assigned reviewer skill:
- Assigned reviewer skill path:
- Repository standards sources:
- Immutable contract sources: <repo-relative path, Git object ID, SHA-256 from ReviewRun>
- Spec discovery record / tracker-only evidence / evidence gap:
- Out of scope:
- User policy:
- User review-depth preference:
- Safety applicability / evidence / coverage:
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

Read every repository contract source only from the immutable resolved head with `git show <resolved-head>:<path>`, using the exact repo-relative path in the ReviewRun record. Never read a contract source from the working tree, and do not recompute its hash or create a second capture; the ReviewRun's Git object ID and SHA-256 are the fixed provenance record. Tracker-only evidence is supplied directly in the discovery record.

Return natural-language candidates with enough location, evidence, impact, and suggested handoff for the parent to record and verify. You may surface an evidence-backed cross-domain candidate, but the parent owns cross-track attribution, deduplication, classification, loop convergence, and the overall verdict.

The canonical ledger artifact is owned by the main session. Read it only; never create, edit, replace, classify, or append to the file. Do not treat a copied prompt excerpt as a second source of truth.

Start each review round with a fresh leaf-worker session. Resume only to finish the same interrupted round; never carry raw worker session state into a later round. A cancelled, timed-out, stalled, max-turns, or explicitly `PARTIAL` worker is incomplete, not PASS.

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
