# Publishability And Security Gate

## When To Run

Run this gate before copying, publishing, committing, or reusing prototype source, assets, screenshots, or extracted visual material. If the gate does not pass, rebuild equivalent UI and design tokens manually.

## Checks

| Category | Check |
| --- | --- |
| Source | Whether source summary, hash, or snippets may be submitted; whether source includes local paths or private comments |
| Fonts | Font origin, license, and redistribution status |
| Images | Image origin, license, and sensitive content |
| Screenshots | Redaction status; whether screenshots contain customer, personal, financial, token, or internal URL data |
| Demo data | Whether demo data is clearly marked and cannot be mistaken for production fact |
| Public docs | Whether submitted docs contain only public summaries, hashes, surface records, or redacted screenshots |

Screenshots created during Phase 0 are private/local evidence by default. A committed document may cite a screenshot only through metadata and hash until redaction, rights, and sensitive-content checks pass. Do not commit raw screenshots just because they are useful for visual comparison.

## Status Terms

- `public-ok`: may be submitted or shared.
- `internal-only`: internal docs only.
- `private-source`: source may stay only in local or controlled storage.
- `blocked-unknown-rights`: unknown rights; do not copy assets.
- `blocked-sensitive-data`: sensitive data present; redact or rebuild.

## Output Requirements

Record in snapshot metadata and surface records:

- Gate status.
- Content allowed for submission.
- Content blocked from copying.
- Required redaction or rebuild work.
- Owner or decision link when unresolved.

Completion criterion: no source, asset, or screenshot reuse proceeds without an explicit status.
