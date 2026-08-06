# Reviewer Prompts

When independent reviewers are requested, give each the same repository-relative candidate paths, Decision/Spec constraints, current Git commit and read-only boundary. Do not include another reviewer's findings or a desired verdict.

## Full review

Ask reviewers to inspect scope/architecture, verification/risk and delivery/ownership respectively. Each returns evidence-backed material findings, editorial notes and a verdict. The main reviewer deduplicates and resolves conflicts.

## Bundle admission

Use one fresh reviewer. Return `admitted` only when the bundle is complete and no material safety, external-mutation, data, security, concurrency or cross-module signal requires full review.

## Focused closure verification

Give a finite list of accepted findings/decisions and their expected evidence. Verify only their affected chains. Return `reopen-full-review` if scope or contract expanded; otherwise return `closure-verified` or `revise`.
