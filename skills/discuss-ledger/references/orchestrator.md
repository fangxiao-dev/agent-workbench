# Orchestrated Auto-Discussion

Use this reference before invoking `scripts/discuss_orchestrator.py`.

## Running It

A full run takes minutes (`--timeout-s` is per agent, per call). Run it in the background, wait for the process to exit, then read the ledger; do not hold a foreground tool call open for it.

If the user asks for `组织审核`, `discuss orchestrator`, `自动讨论`, "Codex 作为 orchestrator", or asks to "用 discuss 审" a target, do not perform a normal single-agent review. Run the orchestrator unless the user explicitly asks for manual ledger editing. If both root and target are clear, start without asking for confirmation:

```bash
python <skill>/scripts/discuss_orchestrator.py --root <target-project-root> --topic <target-doc-or-topic>
```

When the user gives a target file path, prefer the nearest ancestor containing `.git` as `--root` and pass the target relative to it as `--topic`; the script's built-in root/topic resolution handles ordinary clones, worktrees and `.worktrees/<name>/...`.

Defaults are `--agents codex,claude`, `--max-rounds 5`, `--timeout-s 300`. One round means each participant speaks once. Settings are listed in [SKILL.md](../SKILL.md).

## After It Stops

Report:

- ledger path
- convergence summary
- open/deadlocked points
- whether user裁决 is needed
- **观点评估**: briefly judge the discussion quality, the findings that materially changed the outcome, weak spots in coverage/evidence, and whether continued discussion is useful or the next step should be revising the target followed by focused review.

If a participant failed, the ledger written so far is kept and its path is printed on stderr. Rerunning with the same `--slug` starts the round from the first participant again, so a failed second participant means the first one speaks twice; prefer fixing the cause and, if needed, a new `--slug`.

## Claude Availability

When `claude -p` reports auth/login, hangs, or looks unavailable while the user says they are already logged in, read [claude-code-noninteractive.md](claude-code-noninteractive.md) before declaring Claude unavailable.
