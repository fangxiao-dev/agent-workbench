# Good Agent Instructions Example

This example is intentionally vendor-neutral. The same structure can be adapted to `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or another host-specific instruction file.

---

```markdown
# Project: Payment Service API

## Overview
A Node.js REST API for processing payments. Uses Stripe for payment processing and PostgreSQL for persistence.

## Tech Stack
- Runtime: Node.js 20 + TypeScript
- Framework: Express 5
- Database: PostgreSQL 16 via Prisma ORM
- Testing: Vitest + Supertest
- Linting: ESLint + Prettier

## Before Making Changes
- Read the file you plan to modify before editing it.
- Check existing tests to understand expected behavior.
- If requirements conflict, surface the conflict instead of guessing.

## Code Rules
- Use async/await, never `.then()` chains.
- All new functions must have TypeScript types; do not introduce `any` unless the file already relies on it and you justify the exception.
- Use the custom `AppError` class from `src/errors.ts` for user-facing errors.

## Testing
- Every new function needs a unit test.
- Integration tests live in `tests/integration/`.

## Verification
Run these before claiming the task is complete:
1. `npm run lint`
2. `npm test`
3. `npm run build`

All commands must exit with code 0.

If a command must be run from a subdirectory, include the directory:

1. From `api/`, run `npm test`.
2. From `api/`, run `npm run build`.

## Off-Limits
- Do not modify `prisma/migrations/` directly.
- Do not commit `.env` files or secrets.
- Do not use `process.exit()` in application code.

## Host Notes
- Codex: prefer `rg` for repo search when available.
- Claude: check project and global instructions for conflicts before following global defaults.
- Gemini: if a command needs shell-specific syntax, show the exact shell context in the response.
```

---

## Why this is good

- Clear project context appears before behavioral rules.
- Rules are concrete and testable, not aspirational.
- Verification uses exact commands instead of vague “make sure it works”.
- Verification includes the success condition and can include the working directory.
- Boundaries are explicit, which reduces risky agent behavior.
- Host-specific notes are isolated from project-wide rules.
