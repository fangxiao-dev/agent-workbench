---
name: preview-design
description: Use when the user chooses a preview mode for UI exploration: Prototype mode delegates to the prototype skill for multi-variant throwaway selection, while Real UI Component mode mounts a selected surface as a non-production, no-login, fixture-only preview route inside the real app shell. Trigger for explicit prototype-vs-real-component preview mode choices, dev preview routes, fixture preview harnesses, no-login visual review routes, or screenshotable preview surfaces with quarantined backend/auth/mutation side effects. Do not use for screenshot bookkeeping, domain semantics, or real-route absorption.
---

# Preview Design

Choose between two independent preview modes. This skill does not impose a complete workflow.

Read details only when needed:

- `prototype` skill: use for Prototype mode.
- `references/implementation-checklist.md`: read for Real UI Component mode.
- `references/quarantine.md`: read in Real UI Component mode before exposing a no-login route or reusing action-wired components.

## Modes

### Prototype Mode

Use when the user wants layout or interaction options, variants, or "which UI should we choose?" exploration.

Action: stop this skill's implementation path and invoke `prototype`. Let `prototype` own its own workflow, artifacts, switcher, and cleanup rules.

### Real UI Component Mode

Use when the user wants to inspect an already-selected shape with the target repo's real shell/components, fake fixtures, no login, and no backend side effects.

Action: build a public-in-dev preview route. The route is useful because it is **quarantined**: no production exposure, no login dependency, no real data, and no backend or external side effects.

During this mode, do not modify the authenticated/data-backed route except to extract or share a presentational component needed by both the preview route and later absorption.

## Real UI Component Invariants

The finished route must have:

- independent non-production preview URL;
- no app login, cookies, SSO, role selection, or production session dependency;
- production guard that prevents preview rendering;
- real app shell/layout/components where practical;
- static fake/test fixtures;
- quarantined backend reads, persistence, mutations, telemetry, and external side effects;
- reusable target surface component, with the route limited to shell plus fixtures;
- stable DOM markers for browser inspection or screenshots.

If a non-production route will be internet-reachable, explicit acceptance or deployment-level protection is part of the invariant. App-login bypass is not enough.

## Real UI Component Workflow

Follow the detailed checklist in `references/implementation-checklist.md`.

1. **Map the host app.** Done when route convention, selected shape, component candidates, auth/data boundaries, action boundaries, and fixture convention are known.
2. **Carve the preview boundary.** Done when the route is reachable without login in non-production/test mode, blocked in production, and deployed exposure is accepted or protected.
3. **Extract the selected shape.** Done when one reusable component can be mounted by the preview now and by the future real route later.
4. **Build fake fixtures.** Done when reviewed states are represented with visibly fake data and no production identifiers.
5. **Quarantine side effects.** Done when passive render and normal preview interactions cannot read real backend data, mutate state, call external systems, or silently leave the preview route. Read `references/quarantine.md`.
6. **Make it screenshotable.** Done when the full preview and major sections have stable selectors.
7. **Verify the boundary.** Done when the report states what passed, what was skipped, and any remaining quarantine risk.

## Completion Report

For Prototype mode, report that `prototype` owns the next steps.

For Real UI Component mode, report:

- preview route path;
- production guard;
- reusable component(s);
- fixture source and fake/test markers;
- login/auth bypass strategy;
- side-effect audit result;
- verification commands;
- residual risks.

## Red Flags

Stop or report a blocker when:

- the preview needs real login or production session state;
- an auth/middleware bypass affects non-preview routes;
- fixture identity can pass real authorization checks, loaders, or actions;
- the available component is tightly coupled to live mutations;
- fixture data would need real customer or production records;
- the route can render in production;
- the user is asking for screenshot bookkeeping or real-route absorption.
