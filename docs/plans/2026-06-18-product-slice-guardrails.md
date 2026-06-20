# Product Slice Guardrails Plan

**Goal:** Create a small governance skill that prevents frontend/backend integration drift by requiring a concrete product slice contract before implementation work is dispatched.

**Working name:** `product-slice-guardrails`

## Problem

Frontend design, backend implementation, API integration, test generation, and browser verification can each work well in isolation. The failure mode appears when they are composed late: UI assumptions do not match API behavior, error states are undefined, env and port contracts are implicit, and final browser validation discovers issues after the work is already spread across multiple tasks.

This skill should not become a large full-stack implementation skill. Its value is to create a narrow contract and hard gates so separate implementation skills or agents can work independently without losing the end-to-end product path.

## Non-Goals

- Do not replace `frontend-design`.
- Do not replace backend/API implementation work.
- Do not replace `api-integration-builder`.
- Do not replace `test-generator`.
- Do not replace `webapp-testing`.
- Do not own large implementation plans or worker orchestration.
- Do not create a generic "full-stack developer" skill.

## Core Concept

`product-slice-guardrails` produces and validates a **Slice Contract**.

A slice is a narrow, demoable product path that crosses the relevant layers:

```text
user entry -> user action -> UI state -> API request -> backend behavior -> data change -> UI feedback -> verification
```

The skill does not implement that path directly. It defines the contract that implementation tasks must satisfy and decides whether the path is ready to split across frontend, backend, integration, and testing work.

## Intended Workflow

### 1. Scope The Product Slice

Clarify the smallest useful user path:

- User entry point
- User action
- Successful outcome
- Failure outcome
- Product-visible acceptance criteria

If the requested slice is too broad, split it into a tracer bullet plus follow-up slices.

### 2. Draft The Slice Contract

Fill a structured contract with:

- Product path
- UI states
- API contract
- Data and persistence impact
- Auth and permission rules
- Error model
- Cache, refresh, and invalidation behavior
- Test data and fixture strategy
- Runtime environment
- Verification plan
- Dispatch boundaries

### 3. Apply Guardrail Gates

The skill blocks implementation handoff until the contract answers the required questions:

- No user path, no implementation.
- No API request/response contract, no implementation.
- No success, loading, empty, and error states, no frontend task.
- No auth and permission decision, no backend task.
- No fixture or seed strategy, no integration/E2E task.
- No env, port, startup command, and base URL, no browser verification task.
- No browser verification path, the slice is not done.
- If the slice touches too many modules or concerns, split before dispatch.

### 4. Dispatch Or Recommend Subtasks

The skill may produce task boundaries, but each boundary must be small and independently executable:

- UI task: consumes product path and UI state matrix.
- Backend/API task: consumes API contract, auth rules, and persistence impact.
- External integration task: invokes `api-integration-builder` only when third-party API/OAuth/webhook behavior exists.
- Test task: invokes `test-generator` against the contract.
- Browser verification task: invokes `webapp-testing` with explicit startup commands, env files, ports, and route path.

### 5. Final Integration Gate

A slice is complete only when:

- Contract fields are still accurate after implementation.
- API behavior matches the documented request/response/error model.
- UI displays each required state.
- Tests cover happy path and at least one failure path.
- Browser verification runs against the declared environment and validates the product-visible path.

## Proposed Skill Files

```text
skills/product-slice-guardrails/
  SKILL.md
  templates/
    slice-contract.md
    ui-state-matrix.md
    api-contract.md
    verification-plan.md
  scripts/
    validate-slice-contract.ps1
```

## Slice Contract Template Shape

```markdown
# Slice Contract: <name>

## Product Path
- Entry:
- Action:
- Success:
- Failure:

## UI State Matrix
- Initial:
- Loading:
- Empty:
- Success:
- Validation error:
- Server error:
- Unauthorized/forbidden:

## API Contract
- Method:
- Route:
- Request body/query:
- Success response:
- Error responses:
- Idempotency/retry behavior:

## Data Impact
- Reads:
- Writes:
- Migration/schema impact:
- Cache invalidation:

## Auth And Permissions
- Required identity:
- Required capability:
- Unauthorized behavior:
- Forbidden behavior:

## Runtime Contract
- Env file:
- Frontend command:
- Frontend URL:
- Backend command:
- Backend URL:
- Seed/migration command:

## Verification
- Unit tests:
- API/integration tests:
- Browser path:
- Manual demo notes:

## Dispatch Boundaries
- Frontend:
- Backend/API:
- Integration:
- Tests:
- Browser verification:
```

## Validation Script Scope

The first validator should be deliberately mechanical. It should not infer correctness. It should fail when required sections or fields are missing.

Initial checks:

- Required headings exist.
- Required fields are not blank.
- At least one success response and one error response are present.
- Runtime contract includes startup command and base URL.
- Verification includes a browser path.
- Dispatch boundaries are declared.

Later checks may inspect route strings, duplicate blank sections, and common placeholder values like `TBD`, `TODO`, or `unknown`.

## Interaction With Existing Skills

- `frontend-design`: optional downstream skill for UI implementation using the UI state matrix.
- `api-integration-builder`: optional downstream skill only for third-party APIs, OAuth, webhooks, rate limiting, or sync.
- `test-generator`: downstream skill for unit, API, integration, and E2E test code.
- `webapp-testing`: downstream skill for real browser verification using the runtime contract.
- `to-issues`: complementary planning skill when a larger plan must be split into independently grabbable vertical slices.

## Acceptance Criteria

- A new skill exists under `skills/product-slice-guardrails/`.
- The skill clearly states it is a guardrail and contract skill, not an implementation skill.
- The slice contract template captures product path, UI states, API contract, auth, data, runtime, verification, and dispatch boundaries.
- A PowerShell validator can fail incomplete contracts without modifying files.
- README or relevant workbench documentation explains when to use this skill versus `frontend-design`, `api-integration-builder`, `test-generator`, and `webapp-testing`.
- At least one example contract demonstrates a narrow tracer bullet slice.

## Open Questions

- Should generated slice contracts live under `docs/plans/`, `docs/exchange/`, or a dedicated `docs/slices/` directory?
- Should validation be advisory by default, or should the skill treat validator failures as a hard stop?
- Should the skill publish task drafts, or only produce boundaries for another planning skill to consume?
- Should the contract template stay host-neutral Markdown only, or include machine-readable frontmatter for future automation?
