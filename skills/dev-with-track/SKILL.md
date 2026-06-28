---
name: dev-with-track
description: Tracked development workflow for scoped work that uses process.md/findings.md/gate.md ledgers, evidence, verification notes, manual review gates, and follow-up tracking. Use when the user wants a tracked process, gate decisions, findings updates, evidence capture, or a reusable execution ledger for a slice.
user-invocable: true
---

# Dev With Track

Use this skill to run a small, evidence-driven implementation or design slice with explicit status, findings, gate, evidence, and next-step tracking.

The core loop is:

```text
restore process -> execute controlled slice -> capture evidence -> record findings -> decide gate -> update next step
```

This skill is generic. Domain-specific skills, project docs, and repo `AGENTS.md` files still own product vocabulary, safety rules, verification commands, and visual taste.

## When This Skill Applies

Use it when work needs lightweight execution tracking and the cost of losing state is higher than the cost of maintaining small ledgers:

- `process.md`, `findings.md`, or `gate.md` progress tracking
- evidence capture and verification notes
- manual review gates
- deciding whether a finding should stay in a checklist, become an issue, or move to backlog
- repeating a tracked execution pattern in another project

Do not use it as a replacement for:

- a domain design skill such as `kaispan-ui-design`
- a visual implementation skill such as `frontend-design`
- integration smoke testing for money, billing, email, ERP, or external systems

## First Reads

1. Read repo instructions first: root `AGENTS.md`, app-level instructions, and relevant verification docs.
2. Locate the active roadmap, `process.md`, `findings.md`, and gate/evidence document if they exist.
3. If the user is starting a new slice and asks for scaffolding, use the templates in `assets/templates/`.
4. Read `references/control-flow.md` when the phase boundary, gate semantics, or ledger structure is unclear.

## File Roles

- `roadmap`: phase definitions, gates, red lines, and execution principles.
- `process.md`: current phase, gate status, verification status, and next step.
- `findings.md`: observed UI issues, risks, judgments, and candidate follow-ups.
- `gate.md`: closure dossier for the current slice or phase.
- evidence README: local entry point, boundary, evidence list, verification result, and follow-ups.
- issue / PR: only for findings that have clear scope, acceptance criteria, and execution boundary.

## Phase Model

Do not invent a universal phase model inside this skill. Read the repo roadmap or user-provided plan and mirror its phases into `process.md`.

If the project has no phase model yet, use only a minimal placeholder until the user confirms:

- Current phase: what is being proven now.
- Gate: what must be true before moving on.
- Evidence: what proves the gate.
- Follow-up: what remains after this slice.

## Operating Rules

- Treat the active roadmap or plan as the source of phase truth.
- Keep evidence honest: record what was actually run, captured, skipped, or left for review.
- Record findings before deciding whether they are issues.
- Do not force issues during early exploration. Upgrade only when scope and Done Gate are clear.
- Use exact project verification commands from repo docs; do not copy stack commands from another repo.

## Minimal Execution Checklist

1. Restore status from `process.md`.
2. Confirm current phase and target scope.
3. Confirm safety boundary and gate.
4. Execute the next controlled slice.
5. Capture evidence.
6. Update `findings.md` with observed issues and candidate follow-ups.
7. Update `process.md` with gate status, verification status, and next step.
8. Update `gate.md` or evidence README when closing a slice.
9. Report what is proven, what is still awaiting manual review, and what should become the next issue/checklist item.

## Template Use

Use these templates when a project lacks the corresponding ledger:

- `assets/templates/process.md`
- `assets/templates/findings.md`
- `assets/templates/gate.md`
- `assets/templates/evidence-readme.md`

Replace placeholders with project-specific terms. Keep the files in the target repo, not inside this skill.
