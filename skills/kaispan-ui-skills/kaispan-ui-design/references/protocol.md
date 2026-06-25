# KaiSpan UI Design Protocol

This protocol is the shared contract for the `kaispan-ui-design` suite. Keep durable UI facts in target repositories; keep this suite limited to method, routing, gates, and reusable skeletons.

## Pointer Files

Committed pointer:

- File name: `.kaispan-ui-design.json`
- Purpose: discover global context, project contexts, active snapshots, surface IDs, and public aliases.
- Allowed content: logical locator, repo-relative path, project/module key, public alias.
- Forbidden content: local absolute path, private source path, raw prototype semantics, module business mapping, closure facts.
- Cross-repository rule: the committed pointer describes only the current repository root. Do not write another repository root or checkout path into it; map cross-repository checkouts only through `.kaispan-ui-design.local.json`.

Local override:

- File name: `.kaispan-ui-design.local.json`
- Purpose: resolve local prototype source, screenshot output, cache, temporary local files, or cross-repository checkout mapping.
- Required rule: it must be gitignored and must not be treated as a submitted fact source.

Minimal committed pointer skeleton:

```json
{
  "schemaVersion": 1,
  "projectKey": "<projectKey>",
  "mode": "global",
  "globalContextPath": "docs/kaispan-ui-design",
  "projectContexts": [
    {
      "projectKey": "<standaloneProjectKey>",
      "contextPath": "docs/kaispan-ui-design",
      "activeSnapshotId": "<snapshotId>",
      "surfaceIds": ["<surfaceId>"]
    },
    {
      "projectKey": "<monorepoProjectKey>",
      "moduleKey": "<moduleKey>",
      "contextPath": "docs/kaispan-ui-design/modules/<moduleKey>",
      "activeSnapshotId": "<snapshotId>",
      "surfaceIds": ["<surfaceId>"]
    }
  ],
  "aliases": [
    {
      "projectKey": "<aliasProjectKey>",
      "contextPath": "docs/<repo-relative-context>",
      "status": "legacy-alias"
    }
  ]
}
```

Legacy committed pointers may still contain `moduleContexts`. Treat each legacy entry as a project context, map `moduleKey` to `projectKey` when no project key exists, and write new or updated pointers with `projectContexts`.

## Canonical Locators

Use logical locators instead of source paths:

```text
ksui://snapshot/<snapshotId>
ksui://surface/<snapshotId>/<surfaceId>
ksui://shared-ui/<componentOrPatternId>
ksui://module/<moduleKey>/<surfaceId>
```

Locator resolution order:

1. Current repo `.kaispan-ui-design.json`.
2. Global context files such as `docs/kaispan-ui-design/module-index.md`, `prototype-surfaces.md`, and `shared-ui-candidates.md`.
3. Current project context under `docs/kaispan-ui-design/`.
4. Monorepo module subcontext under `docs/kaispan-ui-design/modules/<moduleKey>/`.
5. Legacy `moduleContexts`, when present.
6. Aliases registered in the committed pointer.
7. `.kaispan-ui-design.local.json` only for local prototype/source or cross-repository checkout lookup, never for submitted facts.

## Fact Source Priority

Resolve conflicts in this order:

1. Target project official docs, API, DB, RBAC, Action Center, file security, audit, and contracts.
2. Current project/module PRD, roadmap, implementation, and tests.
3. Global prototype capture and shared UI decisions.
4. Prototype input.
5. Pilot project/module reference.
6. Legacy proof-of-concept reference.

Lower-priority sources can provide visual intent, naming clues, or methodology. They cannot override production facts or promote demo data, demo state, or demo actions into production behavior.

## Missing Locator Behavior

Module mode must stop before readiness planning or implementation when any required locator is missing:

- `globalContextPath`
- `projectKey`
- `moduleKey` when a monorepo module subcontext is requested
- `contextPath`
- `activeSnapshotId`
- target `surfaceIds`
- any referenced `ksui://...` locator needed for the requested surface

Use this output shape:

```text
blocked-by-skill-missing-locator
missing:
- <field or locator>
next:
- Add the committed pointer data to .kaispan-ui-design.json using projectContexts, or provide a resolvable ksui:// locator.
```

Do not generate a plausible migration plan from names alone.

## Storage Boundaries

The Skill suite may contain:

- `SKILL.md` router and child instructions.
- `references/` method, protocol, gates, and checklist files.
- `templates/` reusable empty skeletons.

The Skill suite must not contain:

- Real prototype snapshot source or screenshots.
- Real surface inventory, business semantics, module mappings, readiness bridges, slice plans, or closure notes.
- Production data, customer data, demo data extracts, or publishability decisions for a real asset.
- Local absolute paths.
