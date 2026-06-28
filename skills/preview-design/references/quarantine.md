# Quarantine

Use this in Real UI Component mode before claiming a fixture preview route is safe.

A preview is not quarantined merely because the initial fixture render works. Audit imports, route loaders, effects, and normal interactions.

## Remove, Disable, Or Replace

- route loaders/actions, prefetchers, module-level side effects, and imports that call services during module initialization;
- `fetch`, query hooks, API clients, server actions, route handlers, SDK clients, websocket/event subscriptions;
- writes to storage, database, queues, email, payment, ERP, Lark/Feishu, Redis, analytics, downloads, or uploads;
- telemetry/analytics calls unless the repo already has an explicit local no-op mode;
- buttons/forms that call real mutations after a click;
- links/forms that silently leave the fixture preview namespace and enter a real workflow.

## Preferred Fixes

- pass `readOnly`, `disabled`, or `previewMode` props if the component supports them;
- inject no-op handlers that visibly explain the action is unavailable in preview;
- split a presentational component from an action-wired container;
- render a disabled command surface rather than a clickable live action.

If a real component cannot be reused without live side effects, do not pretend it is safe. Extract a read-only presentational component first or report the blocker.

## Public-In-Dev Exposure

No-login preview routes are acceptable only inside the agreed non-production boundary.

Treat these as blockers until resolved:

- the route can render in production;
- a deployed preview route is internet-reachable without explicit acceptance or deployment-level protection;
- auth or middleware bypass affects non-preview routes;
- a fixture identity can pass real authorization checks, loaders, or actions;
- preview nav is discoverable in production;
- fixture data contains real customer or production records.

## Done Criteria

The preview is quarantined when passive render and normal preview interactions cannot read real backend data, mutate state, call external systems, emit unintended telemetry, or silently leave the preview route.
