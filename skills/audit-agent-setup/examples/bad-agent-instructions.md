# Bad Agent Instructions Examples

Examples of poor instruction files and setup guidance. These anti-patterns apply whether the file is named `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, or something host-specific.

---

## Anti-Pattern 1: Vague aspirational rules

```markdown
# My Project

Be helpful. Write clean code. Follow best practices. Make sure everything works.
Don't break anything.
```

**Problems:**
- [CRITICAL] Zero actionable instructions; the agent cannot infer what “clean” means here.
- [CRITICAL] No tech stack information.
- [CRITICAL] No verification steps.
- [WARNING] “Don't break anything” is a wish, not an operational rule.

---

## Anti-Pattern 2: Contradictory autonomy rules

```markdown
## Rules
- Always ask the user before making any file changes.
- Work autonomously and complete tasks without interrupting the user.
- Get confirmation before each step.
- Complete the full implementation in one pass.
```

**Problems:**
- [CRITICAL] Rules 1 and 2 directly contradict each other.
- [CRITICAL] Rules 3 and 4 directly contradict each other.
- The agent will behave unpredictably because the policy is internally inconsistent.

---

## Anti-Pattern 3: One-host branding masquerading as project policy

```markdown
Always follow Claude memory rules.
Use Claude subagents for every task.
If Claude says X, do X.
```

**Problems:**
- [CRITICAL] Project policy is incorrectly defined in terms of one host.
- [WARNING] The setup becomes hard to reuse in Codex or Gemini.
- [WARNING] Reviewers cannot tell which rules are product requirements versus host-specific preferences.

---

## Anti-Pattern 4: Security risks

```markdown
## Environment
- Database password: prod123
- API key: sk-abc123xyz
- Use sudo when you need to install things.
```

**Problems:**
- [CRITICAL] Never put secrets in instruction files; they are usually committed to git.
- [CRITICAL] Broad privileged commands create unnecessary risk.

---

## Anti-Pattern 5: No verification

```markdown
## Development
- Write the feature.
- Make sure tests pass.
- You're done.
```

**Problems:**
- [WARNING] “Make sure tests pass” gives no command or expected exit condition.
- [WARNING] No build or lint verification is specified.
- [WARNING] The agent may claim completion without actually checking anything.

**Fix:**
```markdown
## Verification
Run `npm test` and `npm run build`.
Both must exit with code 0 before completion.
```

---

## Anti-Pattern 6: Mixing facts, rules, and etiquette

```markdown
The project uses TypeScript. Always be polite. We use PostgreSQL. Don't use var.
The database is on port 5432. Always ask before deleting. We have Redis for caching.
Never use console.log in production. The Redis port is 6379. Be thorough.
```

**Problems:**
- [WARNING] Facts and rules are interleaved, which makes scanning hard.
- [WARNING] Important constraints are easy to miss.
- [SUGGESTION] Group content into sections such as Overview, Tech Stack, Behavior Rules, Verification, and Restrictions.

---

## Anti-Pattern 7: Heavy process with no project facts

```markdown
## Process
- Create a plan for every task.
- Spawn subagents for research.
- Run a review loop.
- Write a detailed final report.
```

**Problems:**
- [WARNING] The setup defines process but gives no tech stack, project structure, commands, or safety boundaries.
- [WARNING] The agent may perform a lot of ceremony while still guessing how the project works.
- [SUGGESTION] Add project facts and exact verification before adding advanced workflow rules.

---

## Anti-Pattern 8: Dangerous default permissions

```markdown
## Permissions
- Use sudo whenever a command fails.
- Delete stale files to keep the repo clean.
- Restart services on occupied ports.
```

**Problems:**
- [CRITICAL] Broad privileged commands create unnecessary risk.
- [CRITICAL] Deletion and service control rules lack approval boundaries.
- [WARNING] "Stale files" and "occupied ports" are ambiguous and can affect unrelated work.

---

## Anti-Pattern 9: Verification without execution context

```markdown
## Verification
- Run lint.
- Run tests.
- Build before finishing.
```

**Problems:**
- [WARNING] No working directory is specified.
- [WARNING] No exact commands are specified.
- [WARNING] No success condition is specified.

**Fix:**
```markdown
## Verification
From `web/`, run `npm run lint`, `npm test`, and `npm run build`.
All commands must exit with code 0 before claiming completion.
```
