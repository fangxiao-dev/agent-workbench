# Safety And Write Boundaries

## Skill Directory Boundary

`<agent-workbench>/skills/kaispan-ui-skills` may contain only:

- Router and child Skill instructions.
- Process, checklist, protocol, and gate references.
- Empty reusable templates.

It must not contain:

- Real prototype snapshot source or screenshots.
- Real surface inventory, module business mappings, readiness bridges, slice plans, or closure notes.
- Production data, customer data, demo data extracts, or publishability decisions for a real asset.
- Local absolute paths, private source paths, or unredacted assets.

## Fact Source Boundary

Resolve conflicts in this order:

1. KaiSpan official docs/API/DB/RBAC/Action Center/file security/audit/contracts.
2. Current module PRD, roadmap, implementation, and tests.
3. KaiSpan global prototype capture and shared UI decisions.
4. Prototype input.
5. Pilot module reference.
6. Legacy proof-of-concept reference.

When a lower-priority source conflicts with a higher-priority source, record the conflict and keep the higher-priority source. Lower-priority material can remain as `future`, `lab`, naming clues, or visual reference only.

## Publishability Boundary

- Prototype snapshot source is private by default.
- Run the publishability/security gate before copying, publishing, committing, or reusing source/assets/screenshots.
- Submitted or shareable docs may contain only public summaries, hashes, surface records, or redacted screenshots.
- If the gate fails, rebuild equivalent UI and design tokens manually instead of copying source/assets/screenshots.

## Module Implementation Boundary

Module implementation must not bypass:

- Tenant isolation.
- RBAC and data scope.
- Typed API contracts.
- Backend file authorization and organization-relative object keys.
- Audit log, stable error code, and idempotency requirements.
- Action Center source registry, `dedupeKey`, `visibilityPermissionKeys`, and URL-not-persisted rules.

Shared UI may carry visual structure and common interaction shell. Business state, field meaning, permission checks, scope checks, mutations, and audit behavior stay in the module.
