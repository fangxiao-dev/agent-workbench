# Package Retirement

A package is only a retirement candidate when:

1. its current Gate is terminal and names an available Git comparison commit;
2. the implementation is reachable from the configured target branch;
3. every durable delta is absorbed, already covered, or explicitly closed;
4. durable deltas are absorbed or closed in `records.done`, optional pending no longer needs the package, and inbound repository references no longer need it;
5. the directory contains no active attempt or unique evidence still required.

Audit reports candidates; deletion requires separate owner authorization and an exact repository-relative path list.
