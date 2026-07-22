Use `audit-agent-setup` for a read-only review of existing agent setup.

- `/audit [path ...]` audits the named files; without paths, it audits only root `AGENTS.md`, `CLAUDE.md`, and `GEMINI.md` that exist.
- `/audit --full` expands the audit to project-local nested instructions and host setup directories.
- `/audit --full --include-global [host ...]` additionally inventories the named user-level host setup and limits host-specific project surfaces to those hosts; without a host name, it inventories installed hosts. Never inspect user-level host state without `--include-global`.

Return `Scope`, evidence-backed `Findings`, `Strengths`, and `Assumptions`. Do not modify files.
