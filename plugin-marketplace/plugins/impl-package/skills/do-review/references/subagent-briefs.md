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
- Track label / reviewer role:
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

You are a leaf reviewer in a topology already resolved by the parent do-review run. Do not invoke do-review, do not run its subagent gate, do not dispatch subagents, and do not re-evaluate reviewer topology or capacity. For `finding-closure`, you are the single reviewer for the complete named-finding set; there are no peer tracks. Follow the assigned skill's primary review intent and handoff guidance; it is not an exclusive capability boundary.

Review exactly the supplied complete diff and fixed comparison point. Do not inspect, request, or use findings produced by other tracks in the current round. For `finding-closure`, no other track is dispatched; review the supplied named findings together in this one invocation.

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
Use the assigned reviewer skill, but run closure verification only. The parent dispatches one fresh independent reviewer for the whole named-finding set; do not split findings by source track or add a separate Safety reviewer.

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

## Accepted Track C Source Recheck Brief

Use this brief only after the parent has accepted and classified a finding as Track C / Spec fidelity. This is one fresh independent, finding-scoped source check inside the existing ReviewRun; it is not `finding-closure` and does not search for unrelated implementation findings.

```text
Review only the supplied accepted finding and immutable design sources. Read the current Decision, Spec, subordinate contract-design.md when present at the fixed head, and any directly referenced Ticket or cross-module authority from the resolved ReviewRun head. An untouched legacy package may legitimately lack contract-design.md; absence alone is not a gap, so judge whether the available Spec contract uniquely decides the finding.

Answer one question: do those sources uniquely determine the expected behavior for this finding?

- If yes, cite the exact source sections and state that implementation/evidence may be corrected without changing the contract.
- If a source is missing, ambiguous, or conflicting, cite the exact gap and route the finding to req-align before implementation.
- If multiple product outcomes remain valid, state the owner decision required.

Do not inspect the implementation broadly, discover unrelated findings, propose a new review phase, or decide package/Ticket state. Return a concise conclusion with source citations.
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
