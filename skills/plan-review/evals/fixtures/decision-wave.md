# Current decision wave

1. Error contract: A = typed error; B = sentinel return.
2. Migration cutover: A = one-shot; B = dual-read then cut over; C = shadow-write then cut over.
3. Rollback ownership: A = service owner; B = release manager.
4. Cleanup timing: A = immediately after cutover; B = after one release. This depends on decision 2 being resolved first.

Decisions 1–3 are independent. Decision 4 depends on decision 2. The owner reply is: `1A, 2B, 2C, 4A`; decision 3 is unanswered.
