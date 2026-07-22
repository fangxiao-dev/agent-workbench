---
name: audit-agent-setup
description: >
  Audit existing agent setup quality and cross-host consistency. Use this skill when
  the user explicitly asks to audit, review, or compare existing AGENTS.md, CLAUDE.md,
  GEMINI.md, agent, skill, command, or host-setup definitions. Default to the named
  files or root instruction files; use --full only for a project-wide setup audit and
  --include-global only when the user explicitly requests user-level host inspection.
  Do not use it to write or repair setup files, give general best-practice advice, or
  review ordinary code.
---

# Audit Agent Setup

Provide a read-only, evidence-backed audit of an existing agent setup. This is a low-frequency infrastructure check, not a default step for ordinary development or a replacement for `skill-creator`, project initialization, or code review.

## Scope selection

State the selected mode and files before analysing them.

- **Targeted audit (default):** inspect files named by the user. Without a named file, inspect only root `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` that exist in the current repository.
- **Project audit (`--full`):** inspect the targeted files plus nested instruction files and project-local host setup directories such as `.claude/`, `.codex/`, and `.gemini/`. When `--include-global` names hosts, limit host-specific project surfaces to the same hosts while retaining shared `AGENTS.md` files.
- **Host inventory (`--include-global`):** only when explicitly requested, inspect the named user-level host or hosts. If no host is named, inventory the installed hosts. Do not read user-level host state by default.

If the requested target is absent, report that fact; do not broaden the audit merely to find something to review.

The skill's own rule and example files are support material, not target-repository surfaces. Reading the relevant rule file does not authorize inspection of another project file.

## Review method

1. Read `rules/custom.md`. Read `rules/official.md` only when a finding depends on current host-specific behavior. Use the examples only when they clarify a concrete finding.
2. Identify the host context and separate host-neutral project rules from host-specific notes.
3. Assess only the selected surfaces for actionable commands and verification, contradictions and scope leaks, safety boundaries, and maintainability.
4. Base every finding on evidence in the reviewed files. Do not manufacture missing sections or criticize a file for concerns outside the selected scope.

## Findings and boundaries

- Use **CRITICAL** for exposed secrets, unsafe destructive or privileged defaults, and directly conflicting rules that can cause unsafe work.
- Use **WARNING** for non-executable rules, missing verification, host coupling, or important facts that are unclear.
- Use **SUGGESTION** for useful structure or trigger improvements that are not an immediate operational risk.
- Keep advice specific enough to apply, but do not edit files or tell the user that the setup was repaired.

## Report

Return only a concise report with:

1. **Scope:** selected mode, reviewed files, and any unavailable targets.
2. **Findings:** severity, evidence, impact, and a concrete change direction.
3. **Strengths:** only practices that materially reduce ambiguity or risk.
4. **Assumptions:** host behavior or files not verified during this audit.

When there are no findings, say so and retain the scope and assumption notes.
