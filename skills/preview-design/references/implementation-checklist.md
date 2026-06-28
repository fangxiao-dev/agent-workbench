# Implementation Checklist

Use this only for Real UI Component mode. Do not read or apply this checklist for Prototype mode; delegate that mode to the `prototype` skill.

## 1. Map The Host App

Read repo instructions first: root `AGENTS.md`, app-level instructions, and local routing/test/style rules.

Locate:

- route conventions and existing dev/preview route patterns;
- the selected prototype route or target page;
- real app shell/layout components;
- reusable cards, tables, panels, forms, badges, empty states, and navigation primitives;
- auth/session boundaries real pages normally require;
- data loaders, action containers, route actions, server actions, and external service imports near the chosen surface;
- fixture/test data conventions.

If suitable real components do not exist, report that instead of inventing a new design system.

## 2. Carve The Preview Boundary

Create a clearly named preview route following the app convention, for example `/dev/<surface>-preview`, `/__preview/<surface>`, or an existing local preview namespace.

The route is public-in-dev only:

- do not require user login, cookies, SSO, role selection, or production session state;
- if the real shell requires an identity, inject an obvious fixture identity such as `fixture-user`, `operator@example.test`, or `TEST_PREVIEW_OPERATOR`;
- do not reuse real auth loaders just to satisfy the shell.

Add a production guard before rendering:

- server-rendered frameworks: block in the server route/page before importing or rendering the surface when possible;
- client-rendered SPAs: guard the route with the framework production/build env signal, redirect away when disabled, and hide preview nav in production;
- middleware/auth bypasses must be scoped to the preview route only;
- if the framework cannot make the route server-inaccessible, document the limitation and add focused redirect/nav tests.

If the non-production route will be internet-reachable, confirm exposure is acceptable or add non-app access control such as preview deployment protection, basic auth, VPN, or IP allowlisting.

## 3. Extract The Selected Shape

When the input came from `prototype`, do not keep the prototype switcher or losing variants.

Extract the chosen shape into a named component that receives plain props. The preview route should only:

- provide shell/layout wrappers;
- import fixture data;
- pass fixture props into the component;
- add preview-only labels or route-level guard UI.

Keep layout and row/card logic in the reusable component, not in the route. Prefer existing real components over new primitives. Create new reusable primitives only when the repo already has that pattern and the primitive is needed beyond this preview.

## 4. Build Fake Fixtures

Place fixtures in a clearly named fixture module or factory near the preview or feature, unless the repo has a better convention.

Fixture data must be recognizable as fake/test data:

- IDs like `TEST-*`, `fixture-*`, or `preview-*`;
- emails under `example.test`;
- filenames like `test-*.pdf` or `fixture-*.csv`;
- visible UI label such as `Fixture only`, `Fake test data`, or `No backend reads`;
- no real customer names, IBANs, tokens, production IDs, private emails, or copied screenshots containing sensitive data.

Cover the states humans need to inspect:

- normal populated state;
- empty state;
- loading placeholder only if the real component supports it without network access;
- error or permission-denied state when relevant;
- disabled future or unavailable actions when the real capability is not wired.

## 5. Make It Screenshotable

Add stable markers for inspection and screenshot targeting:

- route-level marker such as `data-fixture-preview="surface-name"`;
- section markers such as `data-preview-surface="orders-overview"`;
- visible fixture/safety badges.

Keep the route visually close to the real app: use the real shell/chrome, keep representative density and responsive behavior, and avoid isolated decorative frames unless the real app uses them.

## 6. Verify The Boundary

Run the smallest useful verification set available in the repo.

Prefer focused tests for:

- production guard blocks the route;
- preview navigation is hidden or disabled in production;
- route is reachable without login in non-production/test mode;
- internet-reachable non-production exposure is explicitly accepted or protected;
- fake/test safety copy is visible;
- disabled actions stay disabled;
- fixture route does not import obvious backend clients or action containers;
- the selected component renders from fixture props.

Also run typecheck or the repo focused frontend test command when practical.

Browser screenshots, evidence paths, and process/gate updates belong to `dev-with-track`; this skill only ensures the surface is ready to screenshot.
