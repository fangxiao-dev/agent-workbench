# <NN> — <Ticket title>

**Ticket ID:** <ticket-id>
**Publication Status:** Draft
**Attempt ID:** <attempt-id>
**Spec Revision:** S<n>
**Plan Revision:** P<n>

<!-- Plan Revision 是本 ticket 创建/最后确认时依据的 P<n>。plan 升级后，旧 P 号表示需要按实际 delta 判断影响；未受影响 ticket 可批量确认并机械更新，不重新起草或重批相同内容。 -->

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
