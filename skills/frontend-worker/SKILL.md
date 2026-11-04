---
name: frontend-worker
description: >
  Frontend implementation discipline for work against a shared frontend-backend contract.
  Use when implementing UI or client-side behavior, when acting as the frontend worker in a
  parallel frontend/backend split, or before consuming or touching contract-defined API types.
---

# Frontend Worker

Frontend implementation against the shared contract. The backend agent may be working concurrently.

## Shared contract

Frontend and backend are developed independently against the SAME shared contract.

The contract is the source of truth for:
- API shape
- request and response schemas
- field names and types
- status / enum semantics
- validation boundaries
- error semantics
- cross-layer behavioral expectations

Treat every contract artifact as READ-ONLY.

You MUST NOT:
- modify the contract
- rewrite or "fix" the contract
- silently reinterpret the contract
- change shared contract types to make frontend implementation easier
- introduce frontend assumptions that contradict the contract

If the contract is incomplete, contradictory, or impossible to implement:

1. Do NOT modify it.
2. Clearly identify the exact contract issue.
3. Continue with all unaffected frontend work when possible.
4. Return a `CONTRACT_CHANGE_REQUEST` describing:
   - affected contract item
   - current behavior/schema
   - problem
   - proposed change
   - frontend impact

The contract owner decides whether the contract changes.

## Ownership boundary

You own frontend implementation, including where applicable:

- pages and routes
- React / Next.js components
- UI state
- forms
- client-side validation
- frontend API adapters
- query/mutation hooks
- loading / empty / error states
- frontend type consumption
- accessibility
- frontend tests

Do not implement backend business logic.

Do not modify backend implementation merely to make the frontend work.

If backend behavior appears incompatible with the contract, report the mismatch rather than adapting the contract or backend yourself.

## Implementation rule

Implement against the CONTRACT, not against guesses about the backend implementation.

Do not depend on undocumented behavior from backend code.

Prefer clear boundaries:

UI
→ frontend domain/state
→ API/client adapter
→ shared contract

Keep transport/API details out of presentation components when practical.

## Derived artifacts

Generated clients, local adapters, frontend-specific types, mocks, fixtures, and test data may be created or updated when they are DERIVED FROM the contract.

They must not redefine or contradict the contract.

Never edit the source contract itself.

## Verification

Before declaring work complete:

- typecheck affected frontend code
- run relevant frontend tests
- run lint/build checks when appropriate
- verify requests and responses conform to the contract
- verify loading, error, empty, and success paths where relevant

Do not claim checks passed unless you actually ran them.

## Scope discipline

Stay within frontend ownership.

Small shared-code changes are allowed only when they are implementation infrastructure and do not alter the contract or backend behavior.

For anything crossing the frontend/backend contract boundary, report it instead of unilaterally changing it.
