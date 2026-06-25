# Snapshot Capture Workflow

## Goal

Convert prototype input into traceable global UI evidence without storing source files, screenshots, real surface inventory, or module business mappings in the Skill directory.

## Step 1: Snapshot Metadata

Use `templates/snapshot-metadata.md`. At minimum record:

- `snapshotId`
- source locator
- capturedAt
- capture method
- hash
- surfaces
- assets policy
- publishability status
- known gaps

Source locator should be `ksui://snapshot/<snapshotId>` or a repo-relative path. Local source paths may appear only in `.kaispan-ui-design.local.json` and must not be copied into submitted docs.

Completion criterion: the snapshot can be identified without a local path.

## Step 2: Surface Records

Use `templates/surface-record.md`. At minimum record:

- `surfaceId`
- route/hash
- prototype label
- visual summary
- interaction inventory
- business semantics
- adoption decision
- security/publication notes

Business semantics are clues only. They require module readiness bridge and higher-priority fact sources before they can affect production implementation.

Completion criterion: every surface separates visual evidence from unverified business meaning.

## Step 3: Minimal Screenshot Evidence

Screenshots are optional evidence for visual review. Use them after metadata and surface records exist, not as the first or only source of truth.

For Phase 0, prefer a minimal set:

- desktop view of the target surface
- narrow/mobile view of the target surface
- one extra screenshot only when a sub-surface or state is essential to later review

Screenshots default to `private/local evidence`. Submitted docs may record screenshot metadata, viewport, capture tool, hash, storage policy, and publishability status. Do not commit raw or unredacted screenshots unless the publishability/security gate explicitly allows it.

Completion criterion: screenshots support the surface record without introducing unpublished assets, local paths, or sensitive content into submitted docs.

## Step 4: Shared UI Candidates

Register only cross-module visual and interaction shells:

- layout shell
- navigation pattern
- metric strip
- status badge
- table/card/toolbar pattern
- empty/error/permission/future-disabled state pattern

Do not put domain status, field semantics, permission logic, scope logic, Action Center wiring, or mutation behavior into shared UI candidates.

Completion criterion: each candidate can be reused without importing module-specific business meaning.

## Step 5: Index Updates

Update target repo global indexes, such as:

- `docs/kaispan-ui-design/prototype-surfaces.md`
- `docs/kaispan-ui-design/shared-ui-candidates.md`
- `docs/kaispan-ui-design/module-index.md`
- `docs/kaispan-ui-design/decision-register.md`

Use `ksui://...` locators and repo-relative paths only.
