# Issue Workflow Labels

The shared `skills/issue-workflow/references/issue-contract.yaml` owns canonical strings and hard combination rules. This repo-local document may explain usage but must not redefine them.

- `work:initiative` is a coordinating parent and `work:investigation` is research; an Issue with neither is an ordinary leaf.
- Every leaf or investigation has exactly one type (`bug`, `enhancement`, `doc`, `maintenance`) and one readiness (`needs-info`, `ready-for-agent`, `ready-for-human`, `blocked`, `wontfix`).
- `wontfix` is closed, and `blocked` records an explicit dependency. High-priority executable work keeps its actual readiness; do not add a priority label.

Do not introduce `needs-triage` or a provenance label. `$issue-triage` proposes label and relation changes before publishing.
