# Router Routing

Use this file after the router `SKILL.md` has selected a mode. The authoritative protocol for pointers, locators, fact priority, and missing-locator behavior is `protocol.md`.

## Entry Decision

1. Read the user request and choose `global`, `module`, `review`, or `tooling protocol`.
2. If the user asks to directly implement module UI, run module pointer/readiness preflight before editing code.
3. If the user asks only for review, stay in review mode and do not rewrite the proposal or code unless explicitly asked.
4. If the user asks for capture/extract/hash/screenshot scripts, explain that v0 provides only protocol and templates; do not create a tooling child or scripts.

## Child Skill Index

| Child Skill | Use for |
| --- | --- |
| `../kaispan-ui-design-global/SKILL.md` | Global capture, snapshot/surface skeletons, shared UI candidates, publishability/security gate |
| `../kaispan-ui-design-module/SKILL.md` | Pointer discovery, readiness bridge, source priority, blocked locator behavior, module verification |
| `../kaispan-ui-design-review/SKILL.md` | Skill/toolbox review, fact-source conflict review, publishability/security review, discuss-ledger decision |

## Pointer Discovery

Read `.kaispan-ui-design.json` from the current repository root first. The committed pointer may contain only logical locators, repo-relative paths, and public aliases.
Use `projectContexts` for new pointers. Legacy `moduleContexts` may be read for compatibility, but should be normalized to project contexts before writing updates.
Do not write cross-repository checkout roots into the committed pointer; use `.kaispan-ui-design.local.json` for that local mapping.

Minimal skeleton:

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

`.kaispan-ui-design.local.json` may resolve local prototype source, screenshots, or cache. It is never a submitted fact source.

## Locator Resolution

Supported formats:

```text
ksui://snapshot/<snapshotId>
ksui://surface/<snapshotId>/<surfaceId>
ksui://shared-ui/<componentOrPatternId>
ksui://module/<moduleKey>/<surfaceId>
```

Resolution order:

1. Current repo `.kaispan-ui-design.json`.
2. Global context files: `docs/kaispan-ui-design/module-index.md`, `prototype-surfaces.md`, `shared-ui-candidates.md`.
3. Current project context: `docs/kaispan-ui-design/`.
4. Monorepo module subcontext: `docs/kaispan-ui-design/modules/<moduleKey>/`.
5. Legacy `moduleContexts`, when present.
6. Aliases registered in the committed pointer.
7. `.kaispan-ui-design.local.json` only for local prototype/source or cross-repository checkout lookup.

## Missing Locator Output

Module mode must resolve:

- `globalContextPath`
- `projectKey`
- `moduleKey` when a monorepo module subcontext is requested
- `contextPath`
- `activeSnapshotId`
- target `surfaceIds`

If any are missing, stop and output:

```text
blocked-by-skill-missing-locator
missing:
- <field or locator>
next:
- Add the committed pointer data to .kaispan-ui-design.json using projectContexts, or provide a resolvable ksui:// locator.
```

Do not generate a migration plan from names alone.

## Fallback Order

1. Router protocol: read `protocol.md`.
2. Child references: read the target child Skill's `references/`.
3. Target repo pointer and docs: use repo-relative context.
4. Lower-priority UI evidence: visual, naming, or methodology only.
5. Missing locator: stop with blocked output; do not guess.
