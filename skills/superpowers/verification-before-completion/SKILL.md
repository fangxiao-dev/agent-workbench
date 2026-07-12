---
name: verification-before-completion
description: Use before claiming work is complete, fixed, passing, or ready to merge. Match each claim to direct evidence from the same revision and environment, and report any verification gap precisely.
---

# Verification Before Completion

Completion claims must be no broader than their evidence. Verification is a claim-to-evidence contract, not a requirement to rerun every possible check in the current message.

## Define the claim

Before reporting success, state what is being claimed:

- a specific behavior works;
- a targeted check passes;
- an implementation phase is complete;
- a merge, release, or production gate is satisfied.

A targeted claim may use targeted evidence. A broad readiness claim requires evidence across every relevant gate.

## Evidence contract

Evidence is usable when it:

- directly exercises or checks the claimed behavior;
- comes from the same worktree, revision, and relevant environment;
- is newer than the last change that could affect the result;
- includes the command or procedure, exit status, failure count, and any decisive artifact;
- covers repository-required gates for the claim being made.

Do not substitute nearby evidence: lint does not prove a build, a unit test does not prove an integration, and a passing regression test does not by itself prove the original symptom is resolved.

## Reuse and independent verification

You may reuse complete evidence from a subagent, execution record, CI run, or earlier turn when its provenance is clear and the relevant revision and environment have not changed. Inspect the evidence and resulting diff rather than trusting a success label.

Run an independent or broader verification when:

- evidence is incomplete, stale, conflicting, or from a different revision/environment;
- the change since that evidence could affect the result;
- the claim is a high-risk merge, release, migration, security, data-integrity, or external-side-effect gate;
- project policy explicitly requires a fresh run by the current owner.

Do not temporarily revert a fix merely to manufacture RED evidence when that operation is unsafe. Use an existing failing run, a controlled worktree, mutation of the test fixture, or document that RED was not independently demonstrated.

## Report the actual state

- Evidence covers the claim: state the claim and cite the evidence.
- Implementation exists but verification is missing: report `implemented, not verified`.
- Verification ran and failed: report the failure and the remaining work.
- Some gates pass and others remain: name the completed stage and the outstanding gates; do not call the whole task closed.

Never turn confidence, an agent report, or a partial adjacent check into a completion claim.
