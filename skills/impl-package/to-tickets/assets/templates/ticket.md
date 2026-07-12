# <NN> — <Ticket title>

**Ticket ID:** <ticket-id>
**Publication Status:** Draft
**Attempt ID:** <attempt-id>
**Spec Revision:** S<n>
**Plan Revision:** P<n>

<!-- Plan Revision 是本 ticket 创建/最后确认时依据的 P<n>。plan 升级到更新的 P 号后，仍标着旧 P 号的 ticket 视为 NEEDS-REVALIDATION，直到确认在新 revision 下仍成立并更新此字段，或被重新生成。 -->

## What to build

<A narrow, complete user-visible delivery/acceptance boundary.>

## Acceptance criteria

- **AC-1:** <observable outcome or constraint>
  - Evidence: <planned evidence or manual verification owner>

## Blocked by

- <implementation|acceptance|release>: <ticket-id>

Use `None` when there are no blocking edges.

## Runtime Acceptance Status

> Owned and updated only by `dev-with-track` after publication. `to-tickets` leaves these
> fields unrecorded; they are not worker/task/file-step tracking.

- Value: [unrecorded]
- Direct evidence: [unrecorded]
- Revalidation: [unrecorded]

Do not add worker ownership, task assignments, file-level steps, or runtime task status.
