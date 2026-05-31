# Official and Reference Sources

## Universal guidance

- Focus on instruction quality that transfers across hosts: clear scope, actionable commands, explicit verification, conflict-free rules, and strong security boundaries.
- Treat vendor docs as primary sources when host-specific behavior matters.
- Distinguish verified official behavior from community references and local experience. Do not present community guidance as official vendor policy.

## Vendor-specific sources

### Claude

- Use Anthropic or Claude Code official documentation as the primary source when current Claude behavior matters.
- Community reference, not official: https://easyclaude.com/post/claude-code-official-best-practices
- Community reference, not official: https://easyclaude.com/post/claude-code-claude-md

### Codex

- Codex docs or repo instructions for `AGENTS.md` and skill usage should be fetched from the official source available in the current environment.

### Gemini

- Gemini CLI / agent instruction guidance should be fetched from the official source available in the current environment.

## Usage

- Before making host-specific claims, prefer fetching or reading official docs for that host.
- If official docs are unavailable in the current environment, explicitly say: "based on local references or general experience".
- When a rule applies only to one host, label it in the report. Do not present it as a universal project rule.
- When a community reference conflicts with official docs, follow the official docs and mention the conflict only if it affects the recommendation.
