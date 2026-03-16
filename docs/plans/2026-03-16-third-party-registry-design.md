# Third-Party Registry Design

**Goal:** Record globally installed third-party skills, plugins, agents, and commands in this repo as a reproducible inventory.

**Decision:** Keep separate registry files by asset type under `registry/`, and optimize each entry for reinstallability first. Runtime-local details such as install paths and discovered versions are kept as supporting notes.

## Scope

- Include only third-party assets.
- Exclude assets authored in this repository.
- Cover globally installed assets discovered from Claude, Codex, and `.agents` state.

## File Layout

- `registry/third-party-skills.md`: third-party skills
- `registry/plugins.md`: third-party Claude/Codex plugins and MCP-style integrations
- `registry/agents.md`: third-party agents exposed globally or bundled by installed plugins
- `registry/commands.md`: third-party commands exposed globally or bundled by installed plugins

## Entry Fields

Each registry entry should prefer:

1. Asset name
2. Host/runtime
3. Source
4. Install command or install method
5. Config entry / activation point
6. Status
7. Notes

## Discovery Notes

- `.agents/.skill-lock.json` is the authoritative source for third-party skills installed through the agents skill manager.
- `~/.claude/plugins/installed_plugins.json`, `known_marketplaces.json`, and `settings.json` identify installed/enabled Claude plugins.
- Bundled agents and commands inside an installed plugin should be recorded in their own registries, with the parent plugin referenced as the installation method.
