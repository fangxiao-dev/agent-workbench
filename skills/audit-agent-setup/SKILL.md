---
name: audit-agent-setup
description: >
  Review and improve agent setup files and practices, including AGENTS.md,
  CLAUDE.md, GEMINI.md, agent definitions, skill definitions, slash commands,
  subagent setups, and agentic coding workflows. Use this whenever the user asks
  to audit, write, compare, repair, or give best-practice advice for agent
  instructions across Codex, Claude, Gemini, or mixed-agent projects.
---

This skill turns an agent setup review into a concrete, reproducible audit.
It is also the knowledge source for the `audit-agent-setup` subagent.

## When to use

Use this skill when the task involves any of these:

- Reviewing or writing `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or similar repo instructions.
- Auditing agent, subagent, skill, command, memory, or workflow definitions.
- Comparing setup quality across Codex, Claude, Gemini, or another agent host.
- Explaining agentic coding best practices, especially for repo-local instructions.
- Finding contradictions, unsafe permissions, missing verification, or vague rules in agent setup.

Do not use this skill for ordinary code review unless the subject is the agent setup itself.

## Reference files

Read only what is relevant to the audit:

- Official and reference sources: @rules/official.md
- Local review rules: @rules/custom.md
- Good instruction example: @examples/good-agent-instructions.md
- Bad instruction examples: @examples/bad-agent-instructions.md

## Audit workflow

1. **Identify the target and host context.**
   - List the files or setup surfaces being reviewed.
   - Identify the host context when possible: Codex, Claude, Gemini, mixed-host, or unknown.
   - Separate project-wide policy from host-specific behavior.

2. **Collect the review baseline.**
   - Read @rules/custom.md for reusable review criteria.
   - Read @rules/official.md when host-specific behavior matters.
   - If the task needs the latest behavior of a host, prefer official vendor docs. If you cannot verify current docs, say that the host-specific judgment is based on local references or general experience.

3. **Check for operational quality.**
   - Look for exact commands, working directories, success conditions, and verification gates.
   - Flag vague instructions such as "write clean code", "make sure it works", or "follow best practices" when they are not backed by concrete behavior.
   - Check whether rules can be executed by an agent without guessing.

4. **Check for conflicts and scope leaks.**
   - Flag contradictions, such as "always ask before changes" plus "work autonomously".
   - Flag host-specific rules that are written as project-wide rules.
   - Flag facts, etiquette, preferences, restrictions, and verification steps that are mixed together in a way that makes important constraints hard to find.

5. **Check safety boundaries.**
   - Flag secrets, credentials, tokens, production passwords, or private keys in instruction files.
   - Flag broad privileged commands, destructive commands, or permission escalation without explicit approval rules.
   - Flag unclear handling of production systems, customer data, deployments, migrations, or external side effects.

6. **Check maintainability.**
   - Prefer concise project facts, exact commands, clear ownership boundaries, and reusable host notes.
   - Recommend grouping by purpose: overview, project structure, commands, verification, safety, host notes.
   - Avoid recommending a large framework or process unless the setup actually needs it.

7. **Report findings first.**
   - Lead with issues ordered by severity.
   - Include concrete evidence from the reviewed setup.
   - Provide a specific fix direction for each finding.
   - Mention assumptions and unverified host behavior separately.

## Severity levels

- **CRITICAL**: Security exposure, dangerous permission guidance, direct contradiction that can cause unsafe behavior, or missing boundary around production/destructive actions.
- **WARNING**: Missing verification, vague or non-executable instruction, host coupling that can confuse another agent, important project fact missing or hard to find.
- **SUGGESTION**: Structure, readability, maintainability, or trigger-quality improvement that would help but is unlikely to cause immediate failure.

## Report format

Use this structure for audit responses unless the user asks for a different format:

```markdown
## Findings

- [CRITICAL/WARNING/SUGGESTION] Short finding title
  Evidence: Quote or summarize the relevant instruction.
  Impact: Explain what can go wrong.
  Suggested change: Give a concrete rewrite direction.

## Suggested changes

- Group related edits by behavior or section, not by every line.
- Include exact replacement text only when it is short and high-value.

## Host-specific notes

- Codex: Note only Codex-specific behavior that matters to the finding.
- Claude: Note only Claude-specific behavior that matters to the finding.
- Gemini: Note only Gemini-specific behavior that matters to the finding.
- If host behavior was not verified, say so.

## Unverified assumptions

- List any missing file, unavailable doc, or inference that affected the review.
```

If there are no findings, say that clearly and still mention any verification gaps or source limitations.
